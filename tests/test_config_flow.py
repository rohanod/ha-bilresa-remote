"""Config and options flow tests."""

import pytest
from homeassistant import config_entries
from homeassistant.const import STATE_ON
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


def _submit(hass, flow_id, data):
    return hass.config_entries.options.async_configure(flow_id, data)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_copy_channel_config(hass: HomeAssistant, bilresa_device):
    """Copy channel 1 config to channels 2 & 3, then edit channels."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BILRESA scroll wheel",
        data={CONF_DEVICE_ID: bilresa_device.id},
        options={
            "scroll_wheel_mode_ch1": "lights: on/off",
            "scroll_wheel_target_ch1": ["light.kitchen"],
            "click_action_ch1": [{"action": "light.turn_on", "target": {"entity_id": "light.x"}}],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await _submit(
        hass,
        result["flow_id"],
        {"dim_step_pct": 15, "copy_channels": "1 → 2 & 3", "edit_channels": True},
    )
    assert result["step_id"] == "channel_1"

    result = await _submit(hass, result["flow_id"], {"click_action_ch1": []})
    assert result["step_id"] == "channel_2"
    result = await _submit(hass, result["flow_id"], {})
    assert result["step_id"] == "channel_3"
    result = await _submit(hass, result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = entry.options
    # Copied config arrived on channels 2 and 3
    assert data["scroll_wheel_mode_ch2"] == "lights: on/off"
    assert data["scroll_wheel_mode_ch3"] == "lights: on/off"
    assert data["scroll_wheel_target_ch2"] == ["light.kitchen"]
    assert data["scroll_wheel_target_ch3"] == ["light.kitchen"]
    # Channel 1 edit from its own step was applied
    assert data["click_action_ch1"] == []
    # Globals updated
    assert data["dim_step_pct"] == 15
    # UI-only fields are not persisted
    assert "copy_channels" not in data
    assert "edit_channels" not in data


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_copy_without_editing(hass: HomeAssistant, bilresa_device):
    """Copy and save without stepping through channel forms."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BILRESA scroll wheel",
        data={CONF_DEVICE_ID: bilresa_device.id},
        options={"scroll_wheel_mode_ext_ch1": "instant"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _submit(
        hass,
        result["flow_id"],
        {"copy_channels": "1 → 3", "edit_channels": False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["scroll_wheel_mode_ext_ch3"] == "instant"

