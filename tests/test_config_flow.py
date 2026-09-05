"""Config and options flow tests."""

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bilresa_remote.const import CONF_DEVICE_ID, DOMAIN


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_config_flow_quick_setup(hass: HomeAssistant, bilresa_device):
    """Device pick followed by the optional quick setup stores channel 1 options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: bilresa_device.id}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "quick_setup"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "scroll_wheel_mode_ch1": "lights: dim",
            "scroll_wheel_target_ch1": ["light.kitchen"],
            "click_action_ch1": [],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_DEVICE_ID: bilresa_device.id}
    assert result["title"] == "BILRESA scroll wheel"
    entry = result["result"]
    assert entry.options["scroll_wheel_target_ch1"] == ["light.kitchen"]
    assert entry.options["scroll_wheel_mode_ch1"] == "lights: dim"
    # empty values are not stored (defaults apply)
    assert "click_action_ch1" not in entry.options


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_config_flow_quick_setup_defaults(hass: HomeAssistant, bilresa_device):
    """Submitting the quick setup empty keeps all defaults."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: bilresa_device.id}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].options == {}


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
    """The options flow opens as a menu; channels are on the front page."""
    entry = _make_entry(hass, bilresa_device)
    await _setup(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert set(result["menu_options"]) == {
        "channel_1", "channel_2", "channel_3", "copy", "remove",
        "lights", "media", "fan", "misc", "done",
    }

    result = await _pick(hass, result["flow_id"], "channel_1")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "channel_1"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"button_actions": {"click_action_ch1": []}, "scroll_wheel": {}, "scroll_advanced": {}}
    )
    # back on the main menu after a channel page
    assert result["type"] is FlowResultType.MENU

    result = await _pick(hass, result["flow_id"], "lights")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"dim_step_pct": 15}
    )
    assert result["type"] is FlowResultType.MENU

    result = await _pick(hass, result["flow_id"], "done")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["dim_step_pct"] == 15


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_copy_channel_config(hass: HomeAssistant, bilresa_device):
    """Copy channel 1 config to channels 2 & 3 via the copy page."""
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
        result["flow_id"], {"copy_from": "1", "copy_to": ["2", "3"]}
    )
    assert result["type"] is FlowResultType.MENU

    result = await _pick(hass, result["flow_id"], "channel_2")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"button_actions": {}, "scroll_wheel": {}, "scroll_advanced": {}}
    )
    result = await _pick(hass, result["flow_id"], "done")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = entry.options
    assert data["scroll_wheel_mode_ch2"] == "lights: on/off"
    assert data["scroll_wheel_mode_ch3"] == "lights: on/off"
    assert data["scroll_wheel_target_ch2"] == ["light.kitchen"]
    assert data["scroll_wheel_target_ch3"] == ["light.kitchen"]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_copy_rejects_overlap(hass: HomeAssistant, bilresa_device):
    entry = _make_entry(hass, bilresa_device, {"scroll_wheel_mode_ch1": "lights: on/off"})
    await _setup(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _pick(hass, result["flow_id"], "copy")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"copy_from": "1", "copy_to": ["1", "2"]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"copy_to": "copy_overlap"}

    # fix the input and continue
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"copy_from": "1", "copy_to": ["2"]}
    )
    assert result["type"] is FlowResultType.MENU
    result = await _pick(hass, result["flow_id"], "done")
    assert entry.options["scroll_wheel_mode_ch2"] == "lights: on/off"


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
    assert not [
        k
        for k in entry.options
        if k.startswith(("click", "scroll", "on_hold", "double", "triple", "long"))
    ]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unload_deletes_entry(hass: HomeAssistant, bilresa_device):
    """Deleting the config entry fully cleans up."""
    entry = _make_entry(hass, bilresa_device)
    await _setup(hass, entry)
    assert entry.entry_id in hass.data[DOMAIN]

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
