"""Engine tests: verify blueprint behavior with real state_changed events."""

import asyncio

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bilresa_remote.const import CONF_DEVICE_ID, DOMAIN
from tests.conftest import register_remote_entity


async def wait_for(condition, timeout=2.0):
    """Wait until a condition is met."""
    for _ in range(int(timeout / 0.02)):
        if condition():
            return
        await asyncio.sleep(0.02)
    assert condition(), "condition not met in time"


def make_entry(hass, device, options=None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BILRESA scroll wheel",
        data={CONF_DEVICE_ID: device.id},
        options=options or {},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_button_click_runs_action(hass: HomeAssistant, bilresa_device):
    button = register_remote_entity(
        hass, bilresa_device, "event", "button_3", "2026-01-01T00:00:00.000+00:00",
        {"event_type": "multi_press_1"},
    )
    entry = make_entry(
        hass,
        bilresa_device,
        {"click_action_ch1": [{"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}}]},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls = []
    hass.services.async_register(
        "light", "turn_on", lambda call: calls.append(call)
    )
    hass.states.async_set(button, "2026-01-01T00:00:05.000+00:00", {"event_type": "multi_press_1"})
    await wait_for(lambda: len(calls) == 1)
    assert calls[0].data.get("entity_id") == ["light.kitchen"]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_scroll_relaxed_dim(hass: HomeAssistant, bilresa_device):
    scroll_left = register_remote_entity(
        hass, bilresa_device, "event", "scroller_2", "2026-01-01T00:00:00.000+00:00",
        {"event_type": "scrolling", "totalNumberOfPressesCounted": 2},
    )
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 128})
    entry = make_entry(hass, bilresa_device, {"scroll_wheel_target_ch1": ["light.kitchen"]})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls = []
    hass.services.async_register(
        "light", "turn_on", lambda call: calls.append(call)
    )
    # scroll left = dim down: -min(2*10, 128*100/254 - 5) = -20
    hass.states.async_set(
        scroll_left, "2026-01-01T00:00:05.000+00:00",
        {"event_type": "scrolling", "totalNumberOfPressesCounted": 2},
    )
    await wait_for(lambda: len(calls) == 1)
    assert calls[0].data["brightness_step_pct"] == -20


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_scroll_instant_requires_sensor_state_1(hass: HomeAssistant, bilresa_device):
    scroll_right_sensor = register_remote_entity(
        hass, bilresa_device, "sensor", "scroller_1", "0"
    )
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 128})
    entry = make_entry(
        hass, bilresa_device,
        {"scroll_wheel_mode_ext_ch1": "instant", "scroll_wheel_target_ch1": ["light.kitchen"]},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls = []
    hass.services.async_register(
        "light", "turn_on", lambda call: calls.append(call)
    )
    hass.states.async_set(scroll_right_sensor, "0")
    await asyncio.sleep(0.1)
    assert not calls

    hass.states.async_set(scroll_right_sensor, "1")
    await wait_for(lambda: len(calls) == 1)
    # instant = 1 click, right = up
    assert calls[0].data["brightness_step_pct"] == 10


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_hold_repeat_stops_on_release(hass: HomeAssistant, bilresa_device):
    button = register_remote_entity(
        hass, bilresa_device, "event", "button_3", "2026-01-01T00:00:00.000+00:00",
        {"event_type": "long_press"},
    )
    entry = make_entry(
        hass,
        bilresa_device,
        {"on_hold_action_ch1": [{"action": "light.toggle", "target": {"entity_id": "light.kitchen"}}]},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls = []
    hass.services.async_register(
        "light", "toggle", lambda call: calls.append(call)
    )
    # Release the button from within the first hold action.
    def release(call):
        calls.append(call)
        hass.states.async_set(
            button, "2026-01-01T00:00:06.000+00:00", {"event_type": "long_release"}
        )

    hass.services.async_register("light", "toggle", release)
    hass.states.async_set(
        button, "2026-01-01T00:00:05.000+00:00", {"event_type": "long_press"}
    )
    await wait_for(lambda: len(calls) >= 1)
    await asyncio.sleep(0.4)
    assert len(calls) == 1


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_media_volume_set(hass: HomeAssistant, bilresa_device):
    scroll_right = register_remote_entity(
        hass, bilresa_device, "event", "scroller_1", "2026-01-01T00:00:00.000+00:00",
        {"event_type": "scrolling", "totalNumberOfPressesCounted": 1},
    )
    hass.states.async_set("media_player.speaker", "playing", {"volume_level": 0.3})
    entry = make_entry(
        hass,
        bilresa_device,
        {
            "scroll_wheel_mode_ch1": "media: volume control",
            "scroll_wheel_target_ch1": ["media_player.speaker"],
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls = []
    hass.services.async_register(
        "media_player", "volume_set", lambda call: calls.append(call)
    )
    hass.states.async_set(
        scroll_right, "2026-01-01T00:00:05.000+00:00",
        {"event_type": "scrolling", "totalNumberOfPressesCounted": 1},
    )
    await wait_for(lambda: len(calls) == 1)
    # 30% + 3.5% = 33.5%
    assert calls[0].data["volume_level"] == pytest.approx(0.335)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_fan_speed_control(hass: HomeAssistant, bilresa_device):
    scroll_left = register_remote_entity(
        hass, bilresa_device, "event", "scroller_2", "2026-01-01T00:00:00.000+00:00",
        {"event_type": "scrolling", "totalNumberOfPressesCounted": 1},
    )
    hass.states.async_set("fan.ceiling", STATE_ON, {"percentage": 10})
    entry = make_entry(
        hass,
        bilresa_device,
        {
            "scroll_wheel_mode_ch1": "fan: speed control",
            "scroll_wheel_target_ch1": ["fan.ceiling"],
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls = []
    hass.services.async_register("fan", "turn_off", lambda call: calls.append(call))
    # scroll left at min speed 10% -> fan off
    hass.states.async_set(
        scroll_left, "2026-01-01T00:00:05.000+00:00",
        {"event_type": "scrolling", "totalNumberOfPressesCounted": 1},
    )
    await wait_for(lambda: len(calls) == 1)
    # fan service schema collapses a single entity to a plain string
    assert calls[0].data.get("entity_id") in (["fan.ceiling"], "fan.ceiling")


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_user_defined_scroll_action_variables(hass: HomeAssistant, bilresa_device):
    scroll_right = register_remote_entity(
        hass, bilresa_device, "event", "scroller_1", "2026-01-01T00:00:00.000+00:00",
        {"event_type": "scrolling", "totalNumberOfPressesCounted": 3},
    )
    entry = make_entry(
        hass,
        bilresa_device,
        {
            "scroll_wheel_mode_ch1": "user defined",
            "scroll_wheel_user_action_ch1": [
                {"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}}
            ],
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls = []
    hass.services.async_register(
        "light", "turn_on", lambda call: calls.append(call)
    )
    hass.states.async_set(
        scroll_right, "2026-01-01T00:00:05.000+00:00",
        {"event_type": "scrolling", "totalNumberOfPressesCounted": 3},
    )
    await wait_for(lambda: len(calls) == 1)
    assert calls[0].data.get("entity_id") == ["light.kitchen"]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unavailable_transitions_ignored(hass: HomeAssistant, bilresa_device):
    button = register_remote_entity(
        hass, bilresa_device, "event", "button_3", "2026-01-01T00:00:00.000+00:00",
        {"event_type": "multi_press_1"},
    )
    entry = make_entry(
        hass,
        bilresa_device,
        {"click_action_ch1": [{"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}}]},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls = []
    hass.services.async_register(
        "light", "turn_on", lambda call: calls.append(call)
    )
    # unavailable -> available transition must not fire the click action
    hass.states.async_set(button, "unavailable")
    hass.states.async_set(
        button, "2026-01-01T00:00:05.000+00:00", {"event_type": "multi_press_1"}
    )
    await asyncio.sleep(0.2)
    assert not calls

    # positive control: a normal transition still fires
    hass.states.async_set(
        button, "2026-01-01T00:00:06.000+00:00", {"event_type": "multi_press_1"}
    )
    await wait_for(lambda: len(calls) == 1)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unload_stops_engine(hass: HomeAssistant, bilresa_device):
    register_remote_entity(
        hass, bilresa_device, "event", "button_3", "2026-01-01T00:00:00.000+00:00",
        {"event_type": "multi_press_1"},
    )
    entry = make_entry(hass, bilresa_device)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id] is not None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_no_entities_issue_clears_when_entities_appear(
    hass: HomeAssistant, bilresa_device
):
    """A repair issue is raised when no entities exist and clears once they do."""
    entry = make_entry(hass, bilresa_device)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = ir.async_get(hass)
    issue_id = f"no_entities_{entry.entry_id}"
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    register_remote_entity(
        hass, bilresa_device, "event", "button_3", "2026-01-01T00:00:00.000+00:00",
        {"event_type": "multi_press_1"},
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0.05)
    assert registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_instant_mode_missing_sensors_issue(hass: HomeAssistant, bilresa_device):
    """Instant mode without the hidden sensor entities raises a repair issue."""
    register_remote_entity(
        hass, bilresa_device, "event", "button_3", "2026-01-01T00:00:00.000+00:00",
        {"event_type": "multi_press_1"},
    )
    entry = make_entry(
        hass, bilresa_device, {"scroll_wheel_mode_ext_ch1": "instant"}
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = ir.async_get(hass)
    issue_id = f"instant_sensors_missing_{entry.entry_id}"
    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert "Channel 1" in issue.translation_placeholders["channels"]

    # enabling one of the hidden sensor entities clears the issue
    register_remote_entity(hass, bilresa_device, "sensor", "scroller_1", "0")
    await hass.async_block_till_done()
    await asyncio.sleep(0.05)
    assert registry.async_get_issue(DOMAIN, issue_id) is None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, issue_id) is None
