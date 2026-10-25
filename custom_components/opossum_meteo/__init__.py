"""The OpoMeteo integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    Platform,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpoMeteoClient
from .const import (
    CONF_API_KEY,
    CONF_AUTO_ADD,
    CONF_KNOWN_STATIONS,
    CONF_STATIONS,
    CONF_UNITS,
    CONF_URL,
    DEFAULT_AUTO_ADD,
    DEFAULT_UNITS,
    DOMAIN,
    ISSUE_NEW_STATION,
)
from .coordinator import OpoMeteoConfigEntry, OpoMeteoCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# sensor device class -> unit per units option ("ha" removes the override)
UNIT_OVERRIDES: dict[SensorDeviceClass, dict[str, str]] = {
    SensorDeviceClass.TEMPERATURE: {
        "metric": UnitOfTemperature.CELSIUS,
        "imperial": UnitOfTemperature.FAHRENHEIT,
    },
    SensorDeviceClass.ATMOSPHERIC_PRESSURE: {
        "metric": UnitOfPressure.HPA,
        "imperial": UnitOfPressure.INHG,
    },
    SensorDeviceClass.PRECIPITATION: {
        "metric": UnitOfPrecipitationDepth.MILLIMETERS,
        "imperial": UnitOfPrecipitationDepth.INCHES,
    },
    SensorDeviceClass.PRECIPITATION_INTENSITY: {
        "metric": UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        "imperial": UnitOfVolumetricFlux.INCHES_PER_HOUR,
    },
}


async def async_setup_entry(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> bool:
    """Set up OpoMeteo from a config entry."""
    client = OpoMeteoClient(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_API_KEY]
    )
    coordinator = OpoMeteoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # before the platforms (and before the update listener) so nothing reloads twice
    _sync_stations(hass, entry, coordinator.data["stations"])
    _remove_deselected(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _apply_units(hass, entry)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    def _on_update() -> None:
        if coordinator.last_update_success:
            _sync_stations(hass, entry, coordinator.data["stations"])

    entry.async_on_unload(coordinator.async_add_listener(_on_update))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> None:
    """Reload so the new stations / units / interval take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _sync_stations(
    hass: HomeAssistant, entry: OpoMeteoConfigEntry, stations: dict[str, Any]
) -> None:
    """Handle stations that appeared on the server since the owner last chose.

    A station is "new" only when it is in neither the selection nor the stored
    known list, so one the owner deliberately unticked is never re-added.
    With auto-add the new ones are selected; otherwise a repair issue asks the
    owner to tick them. Updating the entry reloads it through the listener.
    """
    selected = list(entry.options.get(CONF_STATIONS, []))
    stored = entry.data.get(CONF_KNOWN_STATIONS)
    # entries created before this list existed: everything on the server is known
    known = set(stored) if stored is not None else set(stations)
    known |= set(selected)
    new = [sid for sid in stations if sid not in known]

    pending: list[str] = []
    if new and entry.options.get(CONF_AUTO_ADD, DEFAULT_AUTO_ADD):
        selected += new
        known |= set(new)
    elif new:
        pending = new

    if stored is None or set(stored) != known:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_KNOWN_STATIONS: sorted(known)},
            options={**entry.options, CONF_STATIONS: selected},
        )

    wanted = {f"{ISSUE_NEW_STATION}_{sid}" for sid in pending}
    for sid in pending:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{ISSUE_NEW_STATION}_{sid}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_NEW_STATION,
            translation_placeholders={"name": stations[sid].get("name") or sid},
        )
    # a station that got selected or vanished no longer needs its issue
    for domain, issue_id in list(ir.async_get(hass).issues):
        if (
            domain == DOMAIN
            and issue_id.startswith(f"{ISSUE_NEW_STATION}_")
            and issue_id not in wanted
        ):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


def _remove_deselected(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> None:
    """Drop devices (and their entities) of stations no longer selected."""
    selected = set(entry.options.get(CONF_STATIONS, []))
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        ids = {i for d, i in device.identifiers if d == DOMAIN}
        if ids and not ids & selected:
            registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


def _apply_units(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> None:
    """Set (or clear) the registry unit override of every convertible sensor."""
    units = entry.options.get(CONF_UNITS, DEFAULT_UNITS)
    registry = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
        if ent.domain != Platform.SENSOR:
            continue
        mapping = UNIT_OVERRIDES.get(ent.original_device_class)
        if mapping is None:
            continue
        unit = mapping.get(units)
        current = (ent.options.get("sensor") or {}).get("unit_of_measurement")
        if unit == current:
            continue
        registry.async_update_entity_options(
            ent.entity_id, "sensor", {"unit_of_measurement": unit} if unit else {}
        )
