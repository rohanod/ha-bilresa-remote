"""The Bilresa Remote integration.

Turns the IKEA BILRESA scroll wheel remote (Matter) into a UI-configurable
companion: it listens to the remote's event/sensor entities and runs the
actions configured per channel.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .engine import BilresaEngine

PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Bilresa Remote config entry."""
    hass.data.setdefault(DOMAIN, {})
    engine = BilresaEngine(hass, entry)
    await engine.async_start()
    hass.data[DOMAIN][entry.entry_id] = engine
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    engine = hass.data[DOMAIN].pop(entry.entry_id, None)
    if engine is not None:
        await engine.async_stop()
    return True
