"""Constants for the Bilresa Remote integration."""

from typing import Any

DOMAIN = "bilresa_remote"
MANUFACTURER = "IKEA of Sweden"
MODEL = "BILRESA scroll wheel"

CONF_DEVICE_ID = "device_id"

CHANNELS = (1, 2, 3)

MODE_LIGHTS_DIM = "lights: dim"
MODE_LIGHTS_ON_OFF = "lights: on/off"
MODE_COLOR_TEMP_AND_HUE = "lights: color temp and color hue"
MODE_COLOR_TEMP_ONLY = "lights: color temp only"
MODE_HUE_ONLY = "lights: color hue only"
MODE_MEDIA = "media: volume control"
MODE_FAN = "fan: speed control"
MODE_DYNAMIC = "dynamic: choose from input_select"
MODE_USER_DEFINED = "user defined"

SCROLL_MODES = [
    MODE_LIGHTS_DIM,
    MODE_LIGHTS_ON_OFF,
    MODE_COLOR_TEMP_AND_HUE,
    MODE_COLOR_TEMP_ONLY,
    MODE_HUE_ONLY,
    MODE_MEDIA,
    MODE_FAN,
    MODE_DYNAMIC,
    MODE_USER_DEFINED,
]

EVAL_RELAXED = "relaxed"
EVAL_INSTANT = "instant"

STATE_ON = "on"
STATE_OFF = "off"
STATE_UNAVAILABLE = "unavailable"

# Per-channel options. Key without suffix; stored as "<key>_ch<channel>".
CHANNEL_DEFAULTS: dict[str, Any] = {
    "click_action": [],
    "double_click_action": [],
    "triple_click_action": [],
    "long_click_action": [],
    "on_hold_action": [],
    "scroll_wheel_target": [],
    "scroll_wheel_mode": MODE_LIGHTS_DIM,
    "scroll_wheel_mode_dynamic": None,
    "scroll_wheel_mode_ext": EVAL_RELAXED,
    "scroll_wheel_user_action": [],
}
CHANNEL_FIELDS = tuple(CHANNEL_DEFAULTS)

# Global options with blueprint defaults.
DEFAULTS: dict[str, Any] = {
    "dim_step_pct": 10,
    "dim_min_pct": 5,
    "min_color_temp": 2200,
    "max_color_temp": 4000,
    "color_temp_step": 100,
    "color_hue_step": 6,
    "color_saturation": 100,
    "light_transition_duration": 0.5,
    "volume_step_pct": 3.5,
    "volume_use_up_down_for_instant": True,
    "volume_max_pct": 70,
    "fan_step_pct": 10,
    "fan_max_pct": 100,
    "fan_min_pct": 10,
    "on_hold_delay": 0.1,
    "max_queued_automation_calls": 10,
}

# UI-only options-flow choice for copying one channel's configuration to others.
COPY_CHOICES: dict[str, tuple[int, list[int]] | None] = {
    "": None,
    "1 → 2": (1, [2]),
    "1 → 3": (1, [3]),
    "2 → 1": (2, [1]),
    "2 → 3": (2, [3]),
    "3 → 1": (3, [1]),
    "3 → 2": (3, [2]),
    "1 → 2 & 3": (1, [2, 3]),
    "2 → 1 & 3": (2, [1, 3]),
    "3 → 1 & 2": (3, [1, 2]),
}

EDIT_CHANNELS = "edit_channels"
COPY_CHANNELS = "copy_channels"
REMOVE_CHANNELS = "remove_channels"
UI_ONLY_FIELDS = (COPY_CHANNELS, EDIT_CHANNELS)
