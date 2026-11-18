"""Unit tests for GTT Smart API logic."""

from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path
import sys
import types

PKG_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "gtt_smart"

# Load const.py and api.py without executing __init__.py (which requires homeassistant)
pkg = types.ModuleType("gtt_smart")
pkg.__path__ = [str(PKG_DIR)]
sys.modules["gtt_smart"] = pkg


def _load_module(name: str):
    spec = importlib.util.spec_from_file_location(
        f"gtt_smart.{name}", PKG_DIR / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"gtt_smart.{name}"] = module
    spec.loader.exec_module(module)
    return module


const = _load_module("const")
api = _load_module("api")


def test_parse_hhmm_handles_suffixes_and_invalid_values() -> None:
    """Verify HH:MM parsing with GTT suffixes like 'D' or '*'."""
    assert api.parse_hhmm("12:20") == ("12:20", 12 * 60 + 20)
    assert api.parse_hhmm("15:40D") == ("15:40", 15 * 60 + 40)
    assert api.parse_hhmm("9:05*") == ("09:05", 9 * 60 + 5)
    assert api.parse_hhmm("N/A") is None
    assert api.parse_hhmm("") is None
    assert api.parse_hhmm(None) is None
    assert api.parse_hhmm("25:99") is None


def test_smart_merge_replaces_matching_scheduled_with_rt() -> None:
    """RT arrival within window replaces its corresponding PR time."""
    merged = api.merge_line_arrivals(
        rt_raw=["12:20"],
        pr_raw=["12:22", "12:41", "13:01"],
        mode=const.MODE_SMART,
        match_window=10,
    )
    assert [(t, rt) for t, _, rt in merged] == [
        ("12:20", True),
        ("12:41", False),
        ("13:01", False),
    ]


def test_smart_merge_keeps_first_pr_when_rt_drops_it() -> None:
    """If the first bus has no RT, it stays from PR instead of jumping to the next RT."""
    merged = api.merge_line_arrivals(
        rt_raw=["10:50"],
        pr_raw=["10:24", "10:50", "11:15"],
        mode=const.MODE_SMART,
        match_window=10,
    )
    assert [(t, rt) for t, _, rt in merged] == [
        ("10:24", False),
        ("10:50", True),
        ("11:15", False),
    ]


def test_process_stop_data_filters_and_min_minutes() -> None:
    """Test line/direction filtering, 'D' suffix parsing, and min_minutes_away."""
    raw = [
        {
            "Linea": "3106",
            "Direzione": "TORINO, CORSO GROSSETO",
            "PassaggiRT": [],
            "PassaggiPR": ["15:25"],
        },
        {
            "Linea": "49",
            "Direzione": "PORTA SUSA CAP",
            "PassaggiRT": ["15:20"],
            "PassaggiPR": ["15:21", "15:40D", "15:59"],
        },
    ]
    now_dt = datetime(2026, 11, 17, 15, 18)
    result = api.process_stop_data(
        raw_data=raw,
        line_filter="49",
        direction_filter="PORTA SUSA",
        mode=const.MODE_SMART,
        match_window=10,
        min_minutes=5,
        now_dt=now_dt,
    )
    # 15:20 is only 2 minutes away (< 5), so it should be skipped; 15:40D becomes 15:40
    assert [item["time"] for item in result["upcoming"]] == ["15:40", "15:59"]
    assert [item["minutes"] for item in result["upcoming"]] == [22, 41]


def test_process_stop_data_midnight_rollover() -> None:
    """Arrivals after midnight sort properly after late-night times."""
    raw = [
        {
            "Linea": "49",
            "Direzione": "PORTA SUSA CAP",
            "PassaggiRT": ["23:55"],
            "PassaggiPR": ["23:55", "00:10"],
        }
    ]
    now_dt = datetime(2026, 11, 17, 23, 50)
    result = api.process_stop_data(
        raw_data=raw,
        line_filter="49",
        direction_filter="",
        mode=const.MODE_SMART,
        match_window=10,
        min_minutes=0,
        now_dt=now_dt,
    )
    assert [(x["time"], x["minutes"], x["realtime"]) for x in result["upcoming"]] == [
        ("23:55", 5, True),
        ("00:10", 20, False),
    ]


def test_is_in_quiet_hours() -> None:
    """Verify quiet hours logic for same-night and overnight ranges."""
    assert api.is_in_quiet_hours(datetime(2026, 11, 17, 2, 0), "00:30:00", "05:00:00") is True
    assert api.is_in_quiet_hours(datetime(2026, 11, 17, 0, 30), "00:30:00", "05:00:00") is True
    assert api.is_in_quiet_hours(datetime(2026, 11, 17, 5, 0), "00:30:00", "05:00:00") is False
    assert api.is_in_quiet_hours(datetime(2026, 11, 17, 23, 50), "00:30:00", "05:00:00") is False

    assert api.is_in_quiet_hours(datetime(2026, 11, 17, 23, 45), "23:30:00", "05:00:00") is True
    assert api.is_in_quiet_hours(datetime(2026, 11, 17, 1, 15), "23:30:00", "05:00:00") is True
    assert api.is_in_quiet_hours(datetime(2026, 11, 17, 12, 0), "23:30:00", "05:00:00") is False