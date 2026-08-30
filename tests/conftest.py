"""Fixtures for Bilresa Remote tests."""

import pytest
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture
def bilresa_device(hass):
    """Create a BILRESA device in the device registry."""
    matter_entry = MockConfigEntry(domain="matter", title="Matter")
    matter_entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    return registry.async_get_or_create(
        config_entry_id=matter_entry.entry_id,
        identifiers={("matter", "bilresa-1")},
        manufacturer="IKEA of Sweden",
        model="BILRESA scroll wheel",
        name="BILRESA scroll wheel",
    )


def register_remote_entity(hass, device, domain, suffix, initial_state, attributes=None):
    """Register an entity registry entry belonging to the device and set its state."""
    entity_id = f"{domain}.bilresa_remote_{suffix}"
    er.async_get(hass).async_get_or_create(
        domain,
        "matter",
        f"bilresa-{suffix}",
        device_id=device.id,
        suggested_object_id=f"bilresa_remote_{suffix}",
    )
    hass.states.async_set(entity_id, initial_state, attributes or {})
    return entity_id
