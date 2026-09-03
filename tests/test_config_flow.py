"""Config and options flow tests."""

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bilresa_remote.const import CONF_DEVICE_ID, DOMAIN


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_config_flow_creates_entry(hass: HomeAssistant, bilresa_device):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: bilresa_device.id}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_DEVICE_ID: bilresa_device.id}
    assert result["title"] == "BILRESA scroll wheel"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_config_flow_abort_duplicate(hass: HomeAssistant, bilresa_device):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=bilresa_device.id, data={CONF_DEVICE_ID: bilresa_device.id}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: bilresa_device.id}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _make_entry(hass, bilresa_device, options=None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BILRESA scroll wheel",
        data={CONF_DEVICE_ID: bilresa_device.id},
        options=options or {},
    )
    entry.add_to_hass(hass)
    return entry


async def _setup(hass, entry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _pick(hass, flow_id: str, option: str):
    """Select a menu option (the frontend posts next_step_id)."""
    return hass.config_entries.options.async_configure(flow_id, {"next_step_id": option})


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_menu_modular(hass: HomeAssistant, bilresa_device):
    """The options flow opens as a menu with one page per area."""
    entry = _make_entry(hass, bilresa_device)
    await _setup(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert set(result["menu_options"]) == {
        "lights", "media", "fan", "misc", "copy", "channels", "remove", "done",
    }

    # Each area is its own small form
    result = await _pick(hass, result["flow_id"], "lights")
    assert result["type"] is FlowResultType.FORM
    assert set(result["data_schema"].schema) and result["step_id"] == "lights"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"dim_step_pct": 15}
    )
    assert result["type"] is FlowResultType.MENU

    result = await _pick(hass, result["flow_id"], "media")
    assert result["step_id"] == "media"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"volume_max_pct": 50}
    )
    assert result["type"] is FlowResultType.MENU

    # Save and close from the menu
    result = await _pick(hass, result["flow_id"], "done")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["dim_step_pct"] == 15
    assert entry.options["volume_max_pct"] == 50


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_copy_channel_config(hass: HomeAssistant, bilresa_device):
    """Copy channel 1 config to channels 2 & 3 via the copy page, then edit channels."""
    entry = _make_entry(
        hass,
        bilresa_device,
        {
            "scroll_wheel_mode_ch1": "lights: on/off",
            "scroll_wheel_target_ch1": ["light.kitchen"],
        },
    )
    await _setup(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _pick(hass, result["flow_id"], "copy")
    assert result["step_id"] == "copy"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"copy_channels": "1 → 2 & 3"}
    )
    assert result["type"] is FlowResultType.MENU

    result = await _pick(hass, result["flow_id"], "channels")
    assert result["type"] is FlowResultType.MENU
    assert set(result["menu_options"]) == {"channel_1", "channel_2", "channel_3", "back"}

    result = await _pick(hass, result["flow_id"], "channel_1")
    assert result["step_id"] == "channel_1"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "button_actions": {"click_action_ch1": []},
            "scroll_wheel": {},
        },
    )
    assert result["type"] is FlowResultType.MENU  # back on the channels menu

    result = await _pick(hass, result["flow_id"], "channel_2")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"button_actions": {}, "scroll_wheel": {}}
    )
    result = await _pick(hass, result["flow_id"], "back")
    result = await _pick(hass, result["flow_id"], "done")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = entry.options
    # Copied config arrived on channels 2 and 3
    assert data["scroll_wheel_mode_ch2"] == "lights: on/off"
    assert data["scroll_wheel_mode_ch3"] == "lights: on/off"
    assert data["scroll_wheel_target_ch2"] == ["light.kitchen"]
    assert data["scroll_wheel_target_ch3"] == ["light.kitchen"]
    # Channel 1 edit from its own page was applied
    assert data["click_action_ch1"] == []


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_copy_without_editing(hass: HomeAssistant, bilresa_device):
    """Copy on its own page, then save directly from the menu."""
    entry = _make_entry(
        hass, bilresa_device, {"scroll_wheel_mode_ext_ch1": "instant"}
    )
    await _setup(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _pick(hass, result["flow_id"], "copy")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"copy_channels": "1 → 3"}
    )
    result = await _pick(hass, result["flow_id"], "done")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["scroll_wheel_mode_ext_ch3"] == "instant"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_remove_channel(hass: HomeAssistant, bilresa_device):
    """Removing a channel's configuration resets it to defaults."""
    entry = _make_entry(
        hass,
        bilresa_device,
        {
            "scroll_wheel_mode_ch1": "media: volume control",
            "scroll_wheel_target_ch1": ["media_player.speaker"],
            "click_action_ch1": [{"action": "light.toggle", "target": {"entity_id": "light.x"}}],
            "scroll_wheel_mode_ch2": "fan: speed control",
            "scroll_wheel_target_ch2": ["fan.ceiling"],
        },
    )
    await _setup(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _pick(hass, result["flow_id"], "remove")
    assert result["step_id"] == "remove"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"remove_channels": ["1", "3"]}
    )
    result = await _pick(hass, result["flow_id"], "done")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Channel 1 config removed entirely, channel 2 untouched
    assert "scroll_wheel_mode_ch1" not in entry.options
    assert "scroll_wheel_target_ch1" not in entry.options
    assert "click_action_ch1" not in entry.options
    assert entry.options["scroll_wheel_mode_ch2"] == "fan: speed control"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_remove_all_channels(hass: HomeAssistant, bilresa_device):
    entry = _make_entry(
        hass,
        bilresa_device,
        {
            "scroll_wheel_mode_ch1": "user defined",
            "scroll_wheel_mode_ext_ch2": "instant",
            "on_hold_action_ch3": [{"action": "light.toggle", "target": {"entity_id": "light.x"}}],
        },
    )
    await _setup(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _pick(hass, result["flow_id"], "remove")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"remove_channels": ["1", "2", "3"]}
    )
    result = await _pick(hass, result["flow_id"], "done")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not [k for k in entry.options if k.startswith(("click", "scroll", "on_hold", "double", "triple", "long"))]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unload_deletes_entry(hass: HomeAssistant, bilresa_device):
    """Deleting the config entry fully cleans up."""
    entry = _make_entry(hass, bilresa_device)
    await _setup(hass, entry)
    assert entry.entry_id in hass.data[DOMAIN]

    result = await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
