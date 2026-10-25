"""The OpoMeteo integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpoMeteoClient
from .const import (
    CONF_API_KEY,
    CONF_APPLIED_UNITS,
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
from .entity import device_key
from .units import UNIT_OVERRIDES as UNIT_CLASSES
from .units import merged_sensor_options, unit_override

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

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
            _refresh_devices(hass, entry, coordinator.data["stations"])

    entry.async_on_unload(coordinator.async_add_listener(_on_update))
    return True


async def async_remove_entry(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> None:
    """Drop this entry's repair issues."""
    _delete_issues(hass, entry, keep=set())


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: OpoMeteoConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allow deleting a device whose station is no longer selected or present."""
    stations = (entry.runtime_data.data or {}).get("stations", {})
    selected = set(entry.options.get(CONF_STATIONS, []))
    active = {device_key(entry.entry_id, sid) for sid in selected if sid in stations}
    return not any(d == DOMAIN and i in active for d, i in device_entry.identifiers)


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

    wanted = {_issue_id(entry, sid) for sid in pending}
    for sid in pending:
        ir.async_create_issue(
            hass,
            DOMAIN,
            _issue_id(entry, sid),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_NEW_STATION,
            translation_placeholders={"name": stations[sid].get("name") or sid},
        )
    # a station that got selected or vanished no longer needs its issue
    _delete_issues(hass, entry, keep=wanted)


def _issue_id(entry: OpoMeteoConfigEntry, station_id: str) -> str:
    return f"{ISSUE_NEW_STATION}_{entry.entry_id}_{station_id}"


def _delete_issues(hass: HomeAssistant, entry: OpoMeteoConfigEntry, keep: set[str]) -> None:
    """Delete this entry's new-station issues except those in keep."""
    prefix = f"{ISSUE_NEW_STATION}_{entry.entry_id}_"
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith(prefix) and issue_id not in keep:
            ir.async_delete_issue(hass, DOMAIN, issue_id)


def _remove_deselected(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> None:
    """Drop devices (and their entities) of stations no longer selected."""
    selected = {device_key(entry.entry_id, s) for s in entry.options.get(CONF_STATIONS, [])}
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        ids = {i for d, i in device.identifiers if d == DOMAIN}
        if ids and not ids & selected:
            registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


def _refresh_devices(
    hass: HomeAssistant, entry: OpoMeteoConfigEntry, stations: dict[str, Any]
) -> None:
    """Keep device name / model in step with the station on the server."""
    registry = dr.async_get(hass)
    for sid, st in stations.items():
        device = registry.async_get_device(
            identifiers={(DOMAIN, device_key(entry.entry_id, sid))}
        )
        if device is None:
            continue
        name, model = st.get("name") or sid, st.get("type")
        if device.name != name or device.model != model:
            registry.async_update_device(device.id, name=name, model=model)


def _apply_units(hass: HomeAssistant, entry: OpoMeteoConfigEntry) -> None:
    """Convert existing sensors when the units option changed since last applied.

    Runs only on a change, so per-entity unit overrides the owner set survive
    restarts; other sensor options (display precision) are kept. Entities
    created later get the override when they are added (see sensor.py).
    """
    units = entry.options.get(CONF_UNITS, DEFAULT_UNITS)
    applied = entry.data.get(CONF_APPLIED_UNITS)
    if applied == units:
        return
    if applied is not None:
        registry = er.async_get(hass)
        for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
            if ent.domain != Platform.SENSOR:
                continue
            if ent.original_device_class not in UNIT_CLASSES:
                continue
            registry.async_update_entity_options(
                ent.entity_id,
                "sensor",
                merged_sensor_options(
                    ent.options.get("sensor"), unit_override(ent.original_device_class, units)
                ),
            )
    # entry is not yet listened to here, so this does not trigger a reload
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_APPLIED_UNITS: units}
    )
