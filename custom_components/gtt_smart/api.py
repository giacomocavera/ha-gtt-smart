"""API client and smart merging logic for GTT Smart."""

from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import Any

import aiohttp

from .const import (
    GTT_API_URL,
    MODE_PR_ONLY,
    MODE_RT_ONLY,
    MODE_SMART,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HomeAssistant-GTTSmart/1.0)",
    "Accept": "application/json, text/plain, */*",
}


class GTTApiError(Exception):
    """Raised when the GTT API request fails or returns invalid data."""


def parse_hhmm(raw: Any) -> tuple[str, int] | None:
    """Parse an HH:MM string (ignoring suffixes like 'D' or '*') into (str, minutes_of_day)."""
    if raw is None:
        return None
    match = TIME_RE.search(str(raw).strip())
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}", hour * 60 + minute


def circular_diff_minutes(min_a: int, min_b: int) -> int:
    """Return smallest distance in minutes on a 24h clock."""
    diff = abs(min_a - min_b)
    return min(diff, 1440 - diff)


def minutes_until(target_min: int, now_dt: datetime) -> int:
    """Return signed minutes from now_dt to target_min, handling midnight rollover."""
    now_min = now_dt.hour * 60 + now_dt.minute
    diff = (target_min - now_min) % 1440
    # Treat times up to 2 hours ago as past (-120..-1)
    if diff > 1320:
        diff -= 1440
    return diff


def is_in_quiet_hours(now_dt: datetime, start_str: str, end_str: str) -> bool:
    """Return True if now_dt is inside [start, end), supporting overnight ranges."""
    start_parsed = parse_hhmm(start_str)
    end_parsed = parse_hhmm(end_str)
    if not start_parsed or not end_parsed:
        return False

    now_m = now_dt.hour * 60 + now_dt.minute
    start_m = start_parsed[1]
    end_m = end_parsed[1]

    if start_m == end_m:
        return False
    if start_m < end_m:
        return start_m <= now_m < end_m
    return now_m >= start_m or now_m < end_m


def extract_pr_list(line_data: dict[str, Any]) -> list[str]:
    """Extract scheduled times from PassaggiPR, with fallback to Passaggi."""
    pr_raw = line_data.get("PassaggiPR")
    if isinstance(pr_raw, list) and pr_raw:
        return [str(x) for x in pr_raw]
    passaggi_str = line_data.get("Passaggi")
    if isinstance(passaggi_str, str) and passaggi_str.strip():
        return [p for p in passaggi_str.split(";") if p.strip()]
    return []


def merge_line_arrivals(
    rt_raw: list[Any],
    pr_raw: list[Any],
    mode: str,
    match_window: int,
) -> list[tuple[str, int, bool]]:
    """Return list of (time_str, minutes_of_day, is_realtime) for a single line."""
    rt_parsed: list[tuple[str, int]] = []
    for item in rt_raw or []:
        parsed = parse_hhmm(item)
        if parsed:
            rt_parsed.append(parsed)

    pr_parsed: list[tuple[str, int]] = []
    for item in pr_raw or []:
        parsed = parse_hhmm(item)
        if parsed:
            pr_parsed.append(parsed)

    if mode == MODE_RT_ONLY:
        return [(t, m, True) for t, m in rt_parsed]

    if mode == MODE_PR_ONLY:
        return [(t, m, False) for t, m in pr_parsed]

    # MODE_SMART: replace each scheduled time with its matching RT time when available
    merged: list[tuple[str, int, bool]] = []
    used_rt_indices: set[int] = set()

    for p_str, p_min in pr_parsed:
        best_idx: int | None = None
        best_diff = 9999
        for idx, (_, r_min) in enumerate(rt_parsed):
            if idx in used_rt_indices:
                continue
            diff = circular_diff_minutes(r_min, p_min)
            if diff <= match_window and diff < best_diff:
                best_diff = diff
                best_idx = idx

        if best_idx is not None:
            r_str, r_min = rt_parsed[best_idx]
            merged.append((r_str, r_min, True))
            used_rt_indices.add(best_idx)
        else:
            merged.append((p_str, p_min, False))

    # Keep any RT arrival that did not match a scheduled slot (e.g. delayed past PR)
    for idx, (r_str, r_min) in enumerate(rt_parsed):
        if idx not in used_rt_indices:
            merged.append((r_str, r_min, True))

    return merged


def process_stop_data(
    raw_data: list[dict[str, Any]],
    line_filter: str,
    direction_filter: str,
    mode: str,
    match_window: int,
    min_minutes: int,
    now_dt: datetime,
) -> dict[str, Any]:
    """Filter, merge, sort and format stop transit data."""
    allowed_lines = {
        part.strip().upper()
        for part in (line_filter or "").split(",")
        if part.strip()
    }
    dir_query = (direction_filter or "").strip().upper()

    upcoming: list[dict[str, Any]] = []
    raw_rt_all: list[str] = []
    raw_pr_all: list[str] = []
    available_lines: list[str] = []

    for entry in raw_data:
        if not isinstance(entry, dict):
            continue
        line_name = str(entry.get("Linea", "")).strip()
        direction_name = str(entry.get("Direzione", "")).strip()
        if line_name:
            available_lines.append(
                f"{line_name} -> {direction_name}" if direction_name else line_name
            )

        if allowed_lines and line_name.upper() not in allowed_lines:
            continue
        if dir_query and dir_query not in direction_name.upper():
            continue

        rt_raw = entry.get("PassaggiRT") or []
        pr_raw = extract_pr_list(entry)

        for item in rt_raw:
            parsed = parse_hhmm(item)
            if parsed:
                raw_rt_all.append(parsed[0])
        for item in pr_raw:
            parsed = parse_hhmm(item)
            if parsed:
                raw_pr_all.append(parsed[0])

        merged = merge_line_arrivals(
            rt_raw=rt_raw,
            pr_raw=pr_raw,
            mode=mode,
            match_window=match_window,
        )

        for time_str, time_min, is_rt in merged:
            delta = minutes_until(time_min, now_dt)
            if delta < min_minutes:
                continue
            upcoming.append(
                {
                    "time": time_str,
                    "minutes": delta,
                    "line": line_name,
                    "direction": direction_name,
                    "realtime": is_rt,
                }
            )

    upcoming.sort(key=lambda x: (x["minutes"], x["line"], x["direction"]))

    return {
        "upcoming": upcoming,
        "next_rt": raw_rt_all,
        "next_pr": raw_pr_all,
        "available_lines": available_lines,
    }


class GTTClient:
    """Async HTTP client for GTT transits."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_get_stop_transits(self, stop_id: str) -> list[dict[str, Any]]:
        """Fetch raw transits JSON list for a stop ID."""
        url = GTT_API_URL.format(stop_id=stop_id.strip())
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with self._session.get(url, headers=HEADERS, timeout=timeout) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise GTTApiError(f"Connection error for stop {stop_id}: {err}") from err
        except ValueError as err:
            raise GTTApiError(f"Invalid JSON for stop {stop_id}: {err}") from err

        if not isinstance(data, list):
            raise GTTApiError(f"Unexpected payload format for stop {stop_id}")

        return data