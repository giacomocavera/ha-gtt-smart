"""Binary sensor platform for GTT Smart."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, CONF_STOP_ID, DOMAIN
from .coordinator import GTTSmartCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GTT Smart binary sensor."""
    coordinator: GTTSmartCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GTTSmartRealtimeBinarySensor(coordinator, entry)])


class GTTSmartRealtimeBinarySensor(
    CoordinatorEntity[GTTSmartCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if the next bus is real-time (on) or scheduled (off)."""

    _attr_has_entity_name = True
    _attr_name = "Realtime"

    def __init__(self, coordinator: GTTSmartCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        cfg = {**entry.data, **entry.options}
        stop_id = str(cfg[CONF_STOP_ID])
        device_name = str(cfg.get(CONF_NAME, f"GTT {stop_id}"))

        self._attr_unique_id = f"{entry.entry_id}_realtime"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="GTT Torino",
            model=f"Stop {stop_id}",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if next bus is real-time, False if scheduled, None if no bus."""
        upcoming = (self.coordinator.data or {}).get("upcoming", [])
        if not upcoming:
            return None
        return bool(upcoming[0]["realtime"])

    @property
    def icon(self) -> str:
        """Dynamic small icon for RT vs PR."""
        state = self.is_on
        if state is True:
            return "mdi:access-point"
        if state is False:
            return "mdi:clock-outline"
        return "mdi:minus-circle-outline"