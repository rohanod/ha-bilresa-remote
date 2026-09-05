"""Config and options flow for the Bilresa Remote integration.

The first-time flow ends with an optional quick setup for the most common use
(scroll wheel dimming lights on channel 1). The options flow is menu-driven
with one small page per area; channel pages group fields into collapsible
sections so only what is being changed needs attention.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
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
    COPY_FROM,
    COPY_TO,
    DEFAULTS,
    MANUFACTURER,
    MODEL,
    REMOVE_CHANNELS,
    SCROLL_MODES,
    EVAL_INSTANT,
    EVAL_RELAXED,
)
from .mapping import Role  # noqa: F401  (kept for typing clarity)

TARGET_DOMAINS = ["light", "media_player", "fan"]

MAIN_MENU = [
    "channel_1",
    "channel_2",
    "channel_3",
    "copy",
    "remove",
    "lights",
    "media",
    "fan",
    "misc",
    "done",
]

CHANNEL_CHOICES = [
    {"value": "1", "label": "Channel 1"},
    {"value": "2", "label": "Channel 2"},
    {"value": "3", "label": "Channel 3"},
]

REMOVE_CHOICES = CHANNEL_CHOICES

ACTION_FIELDS = (
    "click_action",
    "double_click_action",
    "triple_click_action",
    "long_click_action",
    "on_hold_action",
)


def _prefilled(options: dict[str, Any], key: str, default: Any) -> vol.Optional:
    return vol.Optional(key, description={"suggested_value": options.get(key, default)})


def _pct_field(options: dict[str, Any], key: str, max_value: float, step: float = 1) -> dict:
    """Return a splattable {marker: selector} entry for a percentage field."""
    return {
        _prefilled(options, key, DEFAULTS[key]): NumberSelector(
            NumberSelectorConfig(min=0, max=max_value, step=step, mode=NumberSelectorMode.BOX)
        )
    }


def _lights_schema(options: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            **_pct_field(options, "dim_step_pct", 100),
            **_pct_field(options, "dim_min_pct", 100),
            _prefilled(options, "min_color_temp", DEFAULTS["min_color_temp"]): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            _prefilled(options, "max_color_temp", DEFAULTS["max_color_temp"]): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            _prefilled(options, "color_temp_step", DEFAULTS["color_temp_step"]): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            **_pct_field(options, "color_hue_step", 360),
            **_pct_field(options, "color_saturation", 100),
            _prefilled(
                options, "light_transition_duration", DEFAULTS["light_transition_duration"]
            ): NumberSelector(
                NumberSelectorConfig(min=0, step=0.1, mode=NumberSelectorMode.BOX)
            ),
        }
    )


def _media_schema(options: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            **_pct_field(options, "volume_step_pct", 100, 0.5),
            vol.Optional(
                "volume_use_up_down_for_instant",
                description={
                    "suggested_value": options.get(
                        "volume_use_up_down_for_instant",
                        DEFAULTS["volume_use_up_down_for_instant"],
                    )
                },
            ): BooleanSelector(),
            **_pct_field(options, "volume_max_pct", 100),
        }
    )


def _fan_schema(options: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            **_pct_field(options, "fan_step_pct", 100),
            **_pct_field(options, "fan_max_pct", 100),
            **_pct_field(options, "fan_min_pct", 100),
        }
    )


def _misc_schema(options: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _prefilled(options, "on_hold_delay", DEFAULTS["on_hold_delay"]): NumberSelector(
                NumberSelectorConfig(min=0, step=0.1, mode=NumberSelectorMode.BOX)
            ),
            _prefilled(
                options, "max_queued_automation_calls", DEFAULTS["max_queued_automation_calls"]
            ): NumberSelector(NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)),
        }
    )


def _copy_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(COPY_FROM, default="1"): SelectSelector(
                SelectSelectorConfig(options=CHANNEL_CHOICES)
            ),
            vol.Required(COPY_TO): SelectSelector(
                SelectSelectorConfig(
                    options=CHANNEL_CHOICES, multiple=True, mode=SelectSelectorMode.LIST
                )
            ),
        }
    )


def _remove_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(REMOVE_CHANNELS): SelectSelector(
                SelectSelectorConfig(
                    options=REMOVE_CHOICES, multiple=True, mode=SelectSelectorMode.LIST
                )
            ),
        }
    )


def _quick_setup_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                "scroll_wheel_mode_ch1", description={"suggested_value": "lights: dim"}
            ): SelectSelector(SelectSelectorConfig(options=SCROLL_MODES)),
            vol.Optional(
                "scroll_wheel_target_ch1", description={"suggested_value": []}
            ): EntitySelector(EntitySelectorConfig(domain=TARGET_DOMAINS, multiple=True)),
            vol.Optional(
                "click_action_ch1", description={"suggested_value": []}
            ): ActionSelector(ActionSelectorConfig()),
        }
    )


def _channel_schema(channel: int, options: dict[str, Any]) -> vol.Schema:
    def pre(key: str) -> vol.Optional:
        return _prefilled(options, f"{key}_ch{channel}", CHANNEL_DEFAULTS[key])

    return vol.Schema(
        {
            vol.Required("button_actions"): section(
                vol.Schema(
                    {pre(key): ActionSelector(ActionSelectorConfig()) for key in ACTION_FIELDS}
                ),
            ),
            vol.Required("scroll_wheel"): section(
                vol.Schema(
                    {
                        pre("scroll_wheel_target"): EntitySelector(
                            EntitySelectorConfig(domain=TARGET_DOMAINS, multiple=True)
                        ),
                        pre("scroll_wheel_mode"): SelectSelector(
                            SelectSelectorConfig(
                                options=SCROLL_MODES, mode=SelectSelectorMode.DROPDOWN
                            )
                        ),
                        pre("scroll_wheel_mode_ext"): SelectSelector(
                            SelectSelectorConfig(options=[EVAL_RELAXED, EVAL_INSTANT])
                        ),
                    }
                ),
            ),
            vol.Required("scroll_advanced"): section(
                vol.Schema(
                    {
                        pre("scroll_wheel_mode_dynamic"): EntitySelector(
                            EntitySelectorConfig(domain=["input_select"])
                        ),
                        pre("scroll_wheel_user_action"): ActionSelector(ActionSelectorConfig()),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


class BilresaRemoteConfigFlow(config_entries.ConfigFlow, domain="bilresa_remote"):
    """Handle the config flow: pick the device, then an optional quick setup."""

    VERSION = 1

    def __init__(self) -> None:
        self._device_id: str | None = None
        self._title = "Bilresa Remote"

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
            self._device_id = user_input[CONF_DEVICE_ID]
            await self.async_set_unique_id(self._device_id)
            self._abort_if_unique_id_configured()
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get(self._device_id)
            if device is not None:
                self._title = device.name_by_user or device.name or self._title
            return await self.async_step_quick_setup()

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

    async def async_step_quick_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optional first-run setup for the most common use case."""
        if user_input is not None:
            options = {key: value for key, value in user_input.items() if value}
            return self.async_create_entry(
                title=self._title,
                data={CONF_DEVICE_ID: self._device_id},
                options=options,
            )
        return self.async_show_form(
            step_id="quick_setup",
            data_schema=_quick_setup_schema(),
            description_placeholders={"name": self._title},
        )


class BilresaRemoteOptionsFlow(config_entries.OptionsFlow):
    """Menu-driven options flow."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._options: dict[str, Any] = dict(entry.options)

    def _main_menu(self) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=MAIN_MENU)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self._main_menu()

    # -- channels ----------------------------------------------------------

    async def async_step_channel_1(self, user_input=None) -> ConfigFlowResult:
        return await self._async_channel_step(1, user_input)

    async def async_step_channel_2(self, user_input=None) -> ConfigFlowResult:
        return await self._async_channel_step(2, user_input)

    async def async_step_channel_3(self, user_input=None) -> ConfigFlowResult:
        return await self._async_channel_step(3, user_input)

    async def _async_channel_step(self, channel: int, user_input) -> ConfigFlowResult:
        if user_input is not None:
            # Section payloads arrive nested; flatten into flat options storage.
            for section_data in user_input.values():
                if isinstance(section_data, dict):
                    self._options.update(section_data)
            return self._main_menu()
        return self.async_show_form(
            step_id=f"channel_{channel}",
            data_schema=_channel_schema(channel, self._options),
        )

    # -- copy / remove -----------------------------------------------------

    async def async_step_copy(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            source = int(user_input[COPY_FROM])
            destinations = [int(dst) for dst in user_input[COPY_TO]]
            if source in destinations:
                errors[COPY_TO] = "copy_overlap"
            elif not destinations:
                errors[COPY_TO] = "copy_none"
            else:
                for destination in destinations:
                    for field in CHANNEL_DEFAULTS:
                        self._options[f"{field}_ch{destination}"] = deepcopy(
                            self._options.get(f"{field}_ch{source}", CHANNEL_DEFAULTS[field])
                        )
                return self._main_menu()
        return self.async_show_form(step_id="copy", data_schema=_copy_schema(), errors=errors)

    async def async_step_remove(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            for channel in user_input.get(REMOVE_CHANNELS, []):
                self._remove_channel(int(channel))
            return self._main_menu()
        return self.async_show_form(step_id="remove", data_schema=_remove_schema())

    def _remove_channel(self, channel: int) -> None:
        for field in CHANNEL_DEFAULTS:
            self._options.pop(f"{field}_ch{channel}", None)

    # -- global areas ------------------------------------------------------

    async def async_step_lights(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return self._main_menu()
        return self.async_show_form(step_id="lights", data_schema=_lights_schema(self._options))

    async def async_step_media(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return self._main_menu()
        return self.async_show_form(step_id="media", data_schema=_media_schema(self._options))

    async def async_step_fan(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return self._main_menu()
        return self.async_show_form(step_id="fan", data_schema=_fan_schema(self._options))

    async def async_step_misc(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return self._main_menu()
        return self.async_show_form(step_id="misc", data_schema=_misc_schema(self._options))

    # -- finish ------------------------------------------------------------

    async def async_step_done(self, user_input=None) -> ConfigFlowResult:
        return self.async_create_entry(title="", data=self._options)
