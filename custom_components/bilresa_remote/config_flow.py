"""Config and options flow for the Bilresa Remote integration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import (
    ActionSelector,
    ActionSelectorConfig,
    BooleanSelector,
    DeviceFilterSelectorConfig,
    DeviceSelector,
    DeviceSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CHANNELS,
    CHANNEL_DEFAULTS,
    CONF_DEVICE_ID,
    COPY_CHANNELS,
    COPY_CHOICES,
    DEFAULTS,
    EDIT_CHANNELS,
    MANUFACTURER,
    MODEL,
    SCROLL_MODES,
    EVAL_INSTANT,
    EVAL_RELAXED,
    UI_ONLY_FIELDS,
)
from .mapping import Role  # noqa: F401  (kept for typing clarity)

TARGET_DOMAINS = ["light", "media_player", "fan"]


def _global_schema(options: dict[str, Any]) -> vol.Schema:
    def pre(key: str) -> vol.Optional:
        return vol.Optional(key, description={"suggested_value": options.get(key, DEFAULTS[key])})

    return vol.Schema(
        {
            pre("dim_step_pct"): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("dim_min_pct"): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("min_color_temp"): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("max_color_temp"): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("color_temp_step"): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("color_hue_step"): NumberSelector(
                NumberSelectorConfig(min=0, max=360, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("color_saturation"): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("light_transition_duration"): NumberSelector(
                NumberSelectorConfig(min=0, step=0.1, mode=NumberSelectorMode.BOX)
            ),
            pre("volume_step_pct"): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=0.5, mode=NumberSelectorMode.BOX)
            ),
            pre("volume_use_up_down_for_instant"): BooleanSelector(),
            pre("volume_max_pct"): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("fan_step_pct"): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("fan_max_pct"): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("fan_min_pct"): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
            ),
            pre("on_hold_delay"): NumberSelector(
                NumberSelectorConfig(min=0, step=0.1, mode=NumberSelectorMode.BOX)
            ),
            pre("max_queued_automation_calls"): NumberSelector(
                NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(COPY_CHANNELS, description={"suggested_value": ""}): SelectSelector(
                SelectSelectorConfig(options=list(COPY_CHOICES), mode=SelectSelectorMode.DROPDOWN)
            ),
            vol.Optional(EDIT_CHANNELS, description={"suggested_value": True}): BooleanSelector(),
        }
    )


def _channel_schema(channel: int, options: dict[str, Any]) -> vol.Schema:
    def pre(key: str) -> vol.Optional:
        return vol.Optional(
            f"{key}_ch{channel}",
            description={"suggested_value": options.get(f"{key}_ch{channel}", CHANNEL_DEFAULTS[key])},
        )

    return vol.Schema(
        {
            pre("click_action"): ActionSelector(ActionSelectorConfig()),
            pre("double_click_action"): ActionSelector(ActionSelectorConfig()),
            pre("triple_click_action"): ActionSelector(ActionSelectorConfig()),
            pre("long_click_action"): ActionSelector(ActionSelectorConfig()),
            pre("on_hold_action"): ActionSelector(ActionSelectorConfig()),
            pre("scroll_wheel_target"): EntitySelector(
                EntitySelectorConfig(domain=TARGET_DOMAINS, multiple=True)
            ),
            pre("scroll_wheel_mode"): SelectSelector(
                SelectSelectorConfig(options=SCROLL_MODES, mode=SelectSelectorMode.DROPDOWN)
            ),
            pre("scroll_wheel_mode_dynamic"): EntitySelector(
                EntitySelectorConfig(domain=["input_select"])
            ),
            pre("scroll_wheel_mode_ext"): SelectSelector(
                SelectSelectorConfig(options=[EVAL_RELAXED, EVAL_INSTANT])
            ),
            pre("scroll_wheel_user_action"): ActionSelector(ActionSelectorConfig()),
        }
    )


class BilresaRemoteConfigFlow(config_entries.ConfigFlow, domain="bilresa_remote"):
    """Handle the config flow: pick the BILRESA remote device."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BilresaRemoteOptionsFlow:
        """Create the options flow handler."""
        return BilresaRemoteOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get(device_id)
            title = "Bilresa Remote"
            if device is not None:
                title = device.name_by_user or device.name or title
            return self.async_create_entry(title=title, data={CONF_DEVICE_ID: device_id})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): DeviceSelector(
                        DeviceSelectorConfig(
                            filter=[
                                DeviceFilterSelectorConfig(
                                    manufacturer=MANUFACTURER, model=MODEL
                                )
                            ]
                        )
                    )
                }
            ),
            errors=errors,
        )


class BilresaRemoteOptionsFlow(config_entries.OptionsFlow):
    """Options flow: global settings, channel copy, per-channel config."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._options: dict[str, Any] = {
            key: value for key, value in entry.options.items() if key not in UI_ONLY_FIELDS
        }

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> OptionsFlowResult:
        if user_input is not None:
            data = dict(user_input)
            copy_choice = data.pop(COPY_CHANNELS, "") or ""
            edit_channels = data.pop(EDIT_CHANNELS, True)
            self._options.update(data)
            self._apply_copy(copy_choice)
            if not edit_channels:
                return self.async_create_entry(title="", data=self._options)
            return await self.async_step_channel_1()

        return self.async_show_form(step_id="init", data_schema=_global_schema(self._options))

    def _apply_copy(self, copy_choice: str) -> None:
        mapping = COPY_CHOICES.get(copy_choice)
        if not mapping:
            return
        source, destinations = mapping
        for destination in destinations:
            for field in CHANNEL_DEFAULTS:
                self._options[f"{field}_ch{destination}"] = deepcopy(
                    self._options.get(f"{field}_ch{source}", CHANNEL_DEFAULTS[field])
                )

    async def async_step_channel_1(self, user_input=None) -> OptionsFlowResult:
        return await self._async_channel_step(1, user_input)

    async def async_step_channel_2(self, user_input=None) -> OptionsFlowResult:
        return await self._async_channel_step(2, user_input)

    async def async_step_channel_3(self, user_input=None) -> OptionsFlowResult:
        return await self._async_channel_step(3, user_input)

    async def _async_channel_step(
        self, channel: int, user_input: dict[str, Any] | None
    ) -> OptionsFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            if channel < max(CHANNELS):
                return await getattr(self, f"async_step_channel_{channel + 1}")()
            return self.async_create_entry(title="", data=self._options)
        return self.async_show_form(
            step_id=f"channel_{channel}",
            data_schema=_channel_schema(channel, self._options),
            last_step=channel == max(CHANNELS),
        )
