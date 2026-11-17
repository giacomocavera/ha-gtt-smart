"""Config flow and options flow for GTT Smart."""

from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GTTApiError, GTTClient
from .const import (
    CONF_DIRECTION,
    CONF_EMPTY_ATTR,
    CONF_EMPTY_STATE,
    CONF_LINE,
    CONF_MATCH_WINDOW,
    CONF_MIN_MINUTES,
    CONF_MODE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_STOP_ID,
    DEFAULT_EMPTY_ATTR,
    DEFAULT_EMPTY_STATE,
    DEFAULT_MATCH_WINDOW,
    DEFAULT_MIN_MINUTES,
    DEFAULT_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MODE_PR_ONLY,
    MODE_RT_ONLY,
    MODE_SMART,
)

MODE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(
                value=MODE_SMART,
                label="Smart (Real-Time + Scheduled fallback)",
            ),
            selector.SelectOptionDict(
                value=MODE_RT_ONLY,
                label="Real-Time only (PassaggiRT)",
            ),
            selector.SelectOptionDict(
                value=MODE_PR_ONLY,
                label="Scheduled only (PassaggiPR)",
            ),
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


class GTTSmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GTT Smart."""

    VERSION = 1

    def __init__(self) -> None:
        self._stop_id: str = ""
        self._discovered_lines: str = ""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GTTSmartOptionsFlow:
        """Return the options flow."""
        return GTTSmartOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: enter stop ID and validate against GTT API."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_id = str(user_input[CONF_STOP_ID]).strip()
            if not stop_id:
                errors[CONF_STOP_ID] = "invalid_stop"
            else:
                client = GTTClient(async_get_clientsession(self.hass))
                try:
                    data = await client.async_get_stop_transits(stop_id)
                except GTTApiError:
                    errors["base"] = "cannot_connect"
                else:
                    self._stop_id = stop_id
                    lines_found: list[str] = []
                    for item in data:
                        if isinstance(item, dict):
                            line = str(item.get("Linea", "")).strip()
                            direction = str(item.get("Direzione", "")).strip()
                            if line:
                                lines_found.append(f"• {line} → {direction}")
                    self._discovered_lines = (
                        "\n".join(lines_found)
                        if lines_found
                        else "No active trips found right now (you can still enter line and direction manually)."
                    )
                    return await self.async_step_details()

        schema = vol.Schema(
            {
                vol.Required(CONF_STOP_ID): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: configure name, line/direction filters and behavior."""
        if user_input is not None:
            name = str(user_input.get(CONF_NAME, "")).strip() or f"GTT {self._stop_id}"
            line = str(user_input.get(CONF_LINE, "")).strip()
            direction = str(user_input.get(CONF_DIRECTION, "")).strip()

            unique_id = f"{self._stop_id}|{line.upper()}|{direction.upper()}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            data = {
                CONF_STOP_ID: self._stop_id,
                CONF_NAME: name,
                CONF_LINE: line,
                CONF_DIRECTION: direction,
                CONF_MODE: str(user_input.get(CONF_MODE, DEFAULT_MODE)),
                CONF_MIN_MINUTES: int(
                    user_input.get(CONF_MIN_MINUTES, DEFAULT_MIN_MINUTES)
                ),
                CONF_SCAN_INTERVAL: int(
                    user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ),
                CONF_MATCH_WINDOW: int(
                    user_input.get(CONF_MATCH_WINDOW, DEFAULT_MATCH_WINDOW)
                ),
                CONF_EMPTY_STATE: DEFAULT_EMPTY_STATE,
                CONF_EMPTY_ATTR: DEFAULT_EMPTY_ATTR,
            }
            return self.async_create_entry(title=name, data=data)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=f"GTT {self._stop_id}"
                ): selector.TextSelector(),
                vol.Optional(CONF_LINE): selector.TextSelector(),
                vol.Optional(CONF_DIRECTION): selector.TextSelector(),
                vol.Required(CONF_MODE, default=DEFAULT_MODE): MODE_SELECTOR,
                vol.Required(
                    CONF_MIN_MINUTES, default=DEFAULT_MIN_MINUTES
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=60, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30, max=600, step=10, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_MATCH_WINDOW, default=DEFAULT_MATCH_WINDOW
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=20, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="details",
            data_schema=schema,
            description_placeholders={
                "stop_id": self._stop_id,
                "discovered_lines": self._discovered_lines,
            },
        )


class GTTSmartOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for GTT Smart."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit filters and polling options."""
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_LINE: str(user_input.get(CONF_LINE, "")).strip(),
                    CONF_DIRECTION: str(user_input.get(CONF_DIRECTION, "")).strip(),
                    CONF_MODE: str(user_input.get(CONF_MODE, DEFAULT_MODE)),
                    CONF_MIN_MINUTES: int(
                        user_input.get(CONF_MIN_MINUTES, DEFAULT_MIN_MINUTES)
                    ),
                    CONF_SCAN_INTERVAL: int(
                        user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                    ),
                    CONF_MATCH_WINDOW: int(
                        user_input.get(CONF_MATCH_WINDOW, DEFAULT_MATCH_WINDOW)
                    ),
                    CONF_EMPTY_STATE: str(
                        user_input.get(CONF_EMPTY_STATE, DEFAULT_EMPTY_STATE)
                    ).strip()
                    or DEFAULT_EMPTY_STATE,
                    CONF_EMPTY_ATTR: str(
                        user_input.get(CONF_EMPTY_ATTR, DEFAULT_EMPTY_ATTR)
                    ).strip()
                    or DEFAULT_EMPTY_ATTR,
                },
            )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_LINE,
                    description={"suggested_value": current.get(CONF_LINE, "")},
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_DIRECTION,
                    description={"suggested_value": current.get(CONF_DIRECTION, "")},
                ): selector.TextSelector(),
                vol.Required(
                    CONF_MODE, default=current.get(CONF_MODE, DEFAULT_MODE)
                ): MODE_SELECTOR,
                vol.Required(
                    CONF_MIN_MINUTES,
                    default=int(current.get(CONF_MIN_MINUTES, DEFAULT_MIN_MINUTES)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=60, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=int(current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30, max=600, step=10, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_MATCH_WINDOW,
                    default=int(current.get(CONF_MATCH_WINDOW, DEFAULT_MATCH_WINDOW)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=20, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_EMPTY_STATE,
                    default=current.get(CONF_EMPTY_STATE, DEFAULT_EMPTY_STATE),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_EMPTY_ATTR,
                    default=current.get(CONF_EMPTY_ATTR, DEFAULT_EMPTY_ATTR),
                ): selector.TextSelector(),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)