"""The OpoMeteo integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpoMeteoClient
from .const import CONF_API_KEY, CONF_URL
from .coordinator import OpoMeteoConfigEntry, OpoMeteoCoordinator

PLATFORMS: list[Platform] = []  # sensor / binary_sensor are added with the entity platforms


async def async_setup_entry(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> bool:
    """Set up OpoMeteo from a config entry."""
    client = OpoMeteoClient(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_API_KEY]
    )
    coordinator = OpoMeteoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> None:
    """Reload so the new stations / units / interval take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
