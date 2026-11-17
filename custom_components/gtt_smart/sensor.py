"""Sensor platform for GTT Smart."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_EMPTY_ATTR,
    CONF_EMPTY_STATE,
    CONF_MODE,
    CONF_NAME,
    CONF_STOP_ID,
    DEFAULT_EMPTY_ATTR,
    DEFAULT_EMPTY_STATE,
    DEFAULT_MODE,
    DOMAIN,
)
from .coordinator import GTTSmartCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GTT Smart sensors from a config entry."""
    coordinator: GTTSmartCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            GTTSmartScheduleSensor(coordinator, entry),
            GTTSmartMinutesSensor(coordinator, entry),
        ]
    )


class GTTSmartBaseSensor(CoordinatorEntity[GTTSmartCoordinator], SensorEntity):
    """Base entity for GTT Smart sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GTTSmartCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._cfg = {**entry.data, **entry.options}
        self._stop_id = str(self._cfg[CONF_STOP_ID])
        device_name = str(self._cfg.get(CONF_NAME, f"GTT {self._stop_id}"))

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="GTT Torino",
            model=f"Stop {self._stop_id}",
        )


class GTTSmartScheduleSensor(GTTSmartBaseSensor):
    """Main sensor showing next arrival time and schedule attributes."""

    _attr_name = None
    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator: GTTSmartCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_schedule"

    @property
    def native_value(self) -> str:
        """Return next arrival time or configured empty state."""
        upcoming = (self.coordinator.data or {}).get("upcoming", [])
        if upcoming:
            return upcoming[0]["time"]
        return str(self._cfg.get(CONF_EMPTY_STATE, DEFAULT_EMPTY_STATE))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed schedule attributes."""
        data = self.coordinator.data or {}
        upcoming = data.get("upcoming", [])
        empty_attr = str(self._cfg.get(CONF_EMPTY_ATTR, DEFAULT_EMPTY_ATTR))

        def _slot(idx: int) -> str:
            return upcoming[idx]["time"] if len(upcoming) > idx else empty_attr

        next_rt_flag = upcoming[0]["realtime"] if upcoming else None

        return {
            "first": _slot(0),
            "second": _slot(1),
            "third": _slot(2),
            "fourth": _slot(3),
            "next_is_realtime": next_rt_flag,
            "next_source": ("RT" if next_rt_flag else "PR") if upcoming else None,
            "next_line": upcoming[0]["line"] if upcoming else None,
            "next_direction": upcoming[0]["direction"] if upcoming else None,
            "upcoming": upcoming,
            "next_rt": data.get("next_rt", []),
            "next_pr": data.get("next_pr", []),
            "available_lines": data.get("available_lines", []),
            "stop_id": self._stop_id,
            "mode": self._cfg.get(CONF_MODE, DEFAULT_MODE),
        }


class GTTSmartMinutesSensor(GTTSmartBaseSensor):
    """Sensor showing minutes remaining until next arrival."""

    _attr_name = "Minutes"
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: GTTSmartCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_minutes"

    @property
    def native_value(self) -> int | None:
        """Return minutes until the next bus."""
        upcoming = (self.coordinator.data or {}).get("upcoming", [])
        if upcoming:
            return upcoming[0]["minutes"]
        return None