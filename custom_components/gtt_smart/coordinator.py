"""DataUpdateCoordinator for GTT Smart."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import GTTApiError, GTTClient, process_stop_data
from .const import (
    CONF_DIRECTION,
    CONF_LINE,
    CONF_MATCH_WINDOW,
    CONF_MIN_MINUTES,
    CONF_MODE,
    CONF_SCAN_INTERVAL,
    CONF_STOP_ID,
    DEFAULT_MATCH_WINDOW,
    DEFAULT_MIN_MINUTES,
    DEFAULT_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GTTSmartCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator fetching and processing GTT arrivals."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.cfg = {**entry.data, **entry.options}
        self.stop_id: str = str(self.cfg[CONF_STOP_ID]).strip()
        self.client = GTTClient(async_get_clientsession(hass))

        scan_seconds = int(self.cfg.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.stop_id}",
            update_interval=timedelta(seconds=scan_seconds),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch transits and compute upcoming arrivals."""
        try:
            raw_data = await self.client.async_get_stop_transits(self.stop_id)
        except GTTApiError as err:
            raise UpdateFailed(str(err)) from err

        return process_stop_data(
            raw_data=raw_data,
            line_filter=str(self.cfg.get(CONF_LINE, "")),
            direction_filter=str(self.cfg.get(CONF_DIRECTION, "")),
            mode=str(self.cfg.get(CONF_MODE, DEFAULT_MODE)),
            match_window=int(self.cfg.get(CONF_MATCH_WINDOW, DEFAULT_MATCH_WINDOW)),
            min_minutes=int(self.cfg.get(CONF_MIN_MINUTES, DEFAULT_MIN_MINUTES)),
            now_dt=dt_util.now(),
        )