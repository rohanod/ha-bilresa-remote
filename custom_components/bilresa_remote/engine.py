"""Engine that turns BILRESA remote entity events into configured actions.

Python port of the Ikea_bilresa_scroll_wheel blueprint:
- listens to state changes of the device's event/sensor entities,
- translates button event_types into per-channel actions,
- repeats on-hold actions while the button stays long-pressed,
- applies scroll-wheel modes to target entities,
- runs user-defined action sequences via homeassistant.helpers.script.Script.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
import logging
from typing import Any

from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.script import Script

from .const import (
    CHANNEL_DEFAULTS,
    CONF_DEVICE_ID,
    DOMAIN,
    EVAL_INSTANT,
    EVAL_RELAXED,
    MODE_COLOR_TEMP_AND_HUE,
    MODE_COLOR_TEMP_ONLY,
    MODE_DYNAMIC,
    MODE_FAN,
    MODE_HUE_ONLY,
    MODE_LIGHTS_DIM,
    MODE_LIGHTS_ON_OFF,
    MODE_MEDIA,
    MODE_USER_DEFINED,
    SCROLL_MODES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from .mapping import Key, map_device_entities

_LOGGER = logging.getLogger(__package__)

MAX_HOLD_REPEATS = 100

MULTI_PRESS_ACTIONS = {
    "multi_press_1": "click_action",
    "multi_press_2": "double_click_action",
    "multi_press_3": "triple_click_action",
}
LONG_PRESS = "long_press"


class BilresaEngine:
    """Per config-entry event engine."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self._entity_to_key: dict[str, Key] = {}
        self._key_to_entity: dict[Key, str] = {}
        self._registry_unsub = None
        self._state_unsub = None
        self._queue: asyncio.Queue[tuple[Key, State]] | None = None
        self._worker_task: asyncio.Task | None = None

    # -- lifecycle ---------------------------------------------------------

    async def async_start(self) -> None:
        self._rebuild_map()
        self._queue = asyncio.Queue(
            maxsize=max(1, int(self._global_option("max_queued_automation_calls")))
        )
        self._registry_unsub = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._handle_registry_updated
        )
        await self._resubscribe()
        if not self._entity_to_key:
            _LOGGER.warning(
                "No BILRESA event/sensor entities found for device %s. "
                "Check that the device is added via Matter and, for instant "
                "scroll mode, that the hidden sensor entities are enabled.",
                self.entry.data.get(CONF_DEVICE_ID),
            )
        self._worker_task = self.hass.async_create_task(
            self._worker_loop(), name=f"{DOMAIN}_worker_{self.entry.entry_id}"
        )

    async def async_stop(self) -> None:
        if self._registry_unsub is not None:
            self._registry_unsub()
            self._registry_unsub = None
        if self._state_unsub is not None:
            self._state_unsub()
            self._state_unsub = None
        if self._worker_task is not None:
            self._worker_task.cancel()
            self._worker_task = None

    # -- entity mapping ----------------------------------------------------

    def _rebuild_map(self) -> None:
        registry = er.async_get(self.hass)
        entity_ids = [
            entry.entity_id
            for entry in er.async_entries_for_device(
                registry, self.entry.data.get(CONF_DEVICE_ID, "")
            )
        ]
        mapped = map_device_entities(entity_ids)
        self._key_to_entity = mapped
        self._entity_to_key = {entity_id: key for key, entity_id in mapped.items()}

    @callback
    def _handle_registry_updated(self, _event) -> None:
        self.hass.async_create_task(self._refresh())

    async def _refresh(self) -> None:
        self._rebuild_map()
        await self._resubscribe()

    async def _resubscribe(self) -> None:
        if self._state_unsub is not None:
            self._state_unsub()
            self._state_unsub = None
        if self._entity_to_key:
            self._state_unsub = async_track_state_change_event(
                self.hass, list(self._entity_to_key), self._on_state_changed
            )

    # -- event intake ------------------------------------------------------

    @callback
    def _on_state_changed(self, event) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if old_state is None or new_state is None:
            return
        if old_state.state == STATE_UNAVAILABLE or new_state.state == STATE_UNAVAILABLE:
            return
        key = self._entity_to_key.get(event.data["entity_id"])
        if key is None or self._queue is None:
            return
        try:
            self._queue.put_nowait((key, new_state))
        except asyncio.QueueFull:
            # Blueprint equivalent: mode queued + max_exceeded: silent
            _LOGGER.debug("Event queue full, dropping event for %s", event.data["entity_id"])

    async def _worker_loop(self) -> None:
        assert self._queue is not None
        while True:
            key, new_state = await self._queue.get()
            try:
                await self._process(key, new_state)
            except Exception:  # noqa: BLE001 - keep the worker alive
                _LOGGER.exception("Error processing BILRESA event for %s", key)
            finally:
                self._queue.task_done()

    # -- options helpers ---------------------------------------------------

    def _global_option(self, key: str) -> Any:
        from .const import DEFAULTS

        return self.entry.options.get(key, DEFAULTS[key])

    def _channel_option(self, channel: int, field: str) -> Any:
        return self.entry.options.get(
            f"{field}_ch{channel}", CHANNEL_DEFAULTS[field]
        )

    # -- processing --------------------------------------------------------

    async def _process(self, key: Key, new_state: State) -> None:
        channel, role = key
        if role == "button":
            await self._handle_button(channel, new_state)
            return

        ext_mode = self._channel_option(channel, "scroll_wheel_mode_ext")
        if role.endswith("_ext"):
            if ext_mode != EVAL_INSTANT or new_state.state != "1":
                return
            clicks = 1
        else:
            if ext_mode != EVAL_RELAXED:
                return
            clicks = int(
                new_state.attributes.get("totalNumberOfPressesCounted") or 1
            )
        direction = "left" if role.startswith("scroll_left") else "right"
        await self._handle_scroll(channel, direction, clicks)

    async def _handle_button(self, channel: int, new_state: State) -> None:
        event_type = new_state.attributes.get("event_type")
        if action_field := MULTI_PRESS_ACTIONS.get(event_type):
            await self._run_actions(channel, action_field)
            return
        if event_type != LONG_PRESS:
            return
        await self._run_actions(channel, "long_click_action")
        button_entity = self._key_to_entity.get((channel, "button"))
        for _ in range(MAX_HOLD_REPEATS - 1):
            state = self.hass.states.get(button_entity) if button_entity else None
            if state is None or state.attributes.get("event_type") != LONG_PRESS:
                break
            await self._run_actions(channel, "on_hold_action")
            await asyncio.sleep(float(self._global_option("on_hold_delay")))

    async def _handle_scroll(self, channel: int, direction: str, clicks: int) -> None:
        mode = self._channel_option(channel, "scroll_wheel_mode")
        if mode == MODE_DYNAMIC:
            mode = self._resolve_dynamic_mode(channel)
            if mode is None:
                return
        if mode == MODE_USER_DEFINED:
            await self._run_actions(
                channel,
                "scroll_wheel_user_action",
                {"scroll_clicks": clicks, "scroll_direction": direction},
            )
            return
        for target in self._channel_option(channel, "scroll_wheel_target") or []:
            await self._apply_mode(mode, target, channel, direction, clicks)

    def _resolve_dynamic_mode(self, channel: int) -> str | None:
        dynamic_entity = self._channel_option(channel, "scroll_wheel_mode_dynamic")
        state = self.hass.states.get(dynamic_entity) if dynamic_entity else None
        mode = state.state if state else None
        if mode not in SCROLL_MODES:
            _LOGGER.warning(
                "Channel %s: dynamic scroll mode %r from %s is not a valid mode",
                channel,
                mode,
                dynamic_entity,
            )
            return None
        return mode

    # -- scroll modes ------------------------------------------------------

    async def _apply_mode(
        self, mode: str, entity_id: str, channel: int, direction: str, clicks: int
    ) -> None:
        state = self.hass.states.get(entity_id)
        up = direction == "right"

        if mode == MODE_LIGHTS_ON_OFF:
            if entity_id.startswith("light."):
                await self._call(
                    "light", "turn_on" if up else "turn_off", entity_id
                )
        elif mode == MODE_LIGHTS_DIM:
            if state is None or state.state != STATE_ON:
                return
            dim_step = float(self._global_option("dim_step_pct"))
            min_pct = float(self._global_option("dim_min_pct"))
            if up:
                step = clicks * dim_step
            else:
                brightness = state.attributes.get("brightness") or 0
                step = -min(clicks * dim_step, brightness * 100 / 254 - min_pct)
            await self._call(
                "light",
                "turn_on",
                entity_id,
                {
                    "brightness_step_pct": step,
                    "transition": float(self._global_option("light_transition_duration")),
                },
            )
        elif mode == MODE_COLOR_TEMP_ONLY or (
            mode == MODE_COLOR_TEMP_AND_HUE
            and state is not None
            and state.attributes.get("color_temp_kelvin") is not None
        ):
            await self._step_color_temp(entity_id, state, up, clicks)
        elif mode == MODE_HUE_ONLY or (
            mode == MODE_COLOR_TEMP_AND_HUE
            and (state is None or state.attributes.get("color_temp_kelvin") is None)
        ):
            await self._step_hs(entity_id, state, up, clicks)
        elif mode == MODE_MEDIA:
            if state is None or state.state not in ("playing", STATE_ON):
                return
            await self._apply_media(state, entity_id, channel, up, clicks)
        elif mode == MODE_FAN:
            if entity_id.startswith("fan."):
                await self._apply_fan(state, entity_id, up, clicks)

    async def _step_color_temp(
        self, entity_id: str, state: State | None, up: bool, clicks: int
    ) -> None:
        min_temp = float(self._global_option("min_color_temp"))
        max_temp = float(self._global_option("max_color_temp"))
        step = float(self._global_option("color_temp_step")) * clicks
        current = (
            state.attributes.get("color_temp_kelvin") if state is not None else None
        )
        if current is None:
            current = min_temp
        new = float(current) + (step if up else -step)
        new = min(max_temp, max(min_temp, new))
        attributes = state.attributes if state is not None else {}
        if (light_min := attributes.get("min_color_temp_kelvin")) is not None:
            new = max(new, float(light_min))
        if (light_max := attributes.get("max_color_temp_kelvin")) is not None:
            new = min(new, float(light_max))
        await self._call(
            "light",
            "turn_on",
            entity_id,
            {
                "color_temp_kelvin": round(new),
                "transition": float(self._global_option("light_transition_duration")),
            },
        )

    async def _step_hs(
        self, entity_id: str, state: State | None, up: bool, clicks: int
    ) -> None:
        saturation = float(self._global_option("color_saturation"))
        step = float(self._global_option("color_hue_step")) * clicks
        hue = 0.0
        if state is not None and (hs := state.attributes.get("hs_color")):
            hue = float(hs[0])
        new_hue = (hue + step) % 360 if up else (hue - step) % 360
        await self._call(
            "light",
            "turn_on",
            entity_id,
            {
                "hs_color": [round(new_hue, 2), saturation],
                "transition": float(self._global_option("light_transition_duration")),
            },
        )

    async def _apply_media(
        self, state: State, entity_id: str, channel: int, up: bool, clicks: int
    ) -> None:
        volume_pct = float(state.attributes.get("volume_level") or 0) * 100
        step = float(self._global_option("volume_step_pct"))
        max_pct = float(self._global_option("volume_max_pct"))
        relaxed = self._channel_option(channel, "scroll_wheel_mode_ext") == EVAL_RELAXED
        use_up_down = bool(self._global_option("volume_use_up_down_for_instant"))

        if relaxed or not use_up_down:
            target = volume_pct + (step * clicks if up else -step * clicks)
            target = min(max_pct, max(0, target))
            await self._call(
                "media_player", "volume_set", entity_id, {"volume_level": target / 100}
            )
        elif not up:
            await self._call("media_player", "volume_down", entity_id)
        elif volume_pct < max_pct:
            await self._call("media_player", "volume_up", entity_id)

    async def _apply_fan(
        self, state: State | None, entity_id: str, up: bool, clicks: int
    ) -> None:
        attributes = state.attributes if state is not None else {}
        current_pct = int(attributes.get("percentage") or 0)
        entity_step = int(attributes.get("percentage_step") or 0)
        configured_step = int(float(self._global_option("fan_step_pct")))
        step_pct = entity_step if entity_step > 0 else configured_step
        max_pct = int(float(self._global_option("fan_max_pct")))
        min_pct = int(float(self._global_option("fan_min_pct")))
        requested_step = clicks * step_pct

        if not up and current_pct <= min_pct:
            await self._call("fan", "turn_off", entity_id)
        elif up and (state is None or state.state == STATE_OFF):
            await self._call("fan", "turn_on", entity_id, {"percentage": min_pct})
        elif up and current_pct >= max_pct:
            return
        elif up:
            await self._call("fan", "increase_speed", entity_id, {"percentage_step": requested_step})
        else:
            await self._call("fan", "decrease_speed", entity_id, {"percentage_step": requested_step})

    # -- actions -----------------------------------------------------------

    async def _run_actions(
        self, channel: int, field: str, variables: dict[str, Any] | None = None
    ) -> None:
        actions = self._channel_option(channel, field)
        if not actions:
            return
        script = Script(
            self.hass,
            deepcopy(actions),
            f"{self.entry.title} channel {channel}: {field}",
            DOMAIN,
        )
        try:
            await script.async_run(variables=variables)
        except Exception:  # noqa: BLE001 - scripted actions may fail arbitrarily
            _LOGGER.exception("Error running %s for channel %s", field, channel)

    async def _call(
        self, domain: str, service: str, entity_id: str, data: dict | None = None
    ) -> None:
        await self.hass.services.async_call(
            domain, service, data, target={"entity_id": entity_id}, blocking=True
        )
