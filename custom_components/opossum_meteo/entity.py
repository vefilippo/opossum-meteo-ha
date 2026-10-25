"""Shared base entity."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_URL, DOMAIN
from .coordinator import OpoMeteoCoordinator


def device_key(entry_id: str, station_id: str) -> str:
    """Device identifier / unique-id prefix, namespaced per config entry."""
    return f"{entry_id}_{station_id}"


def station_capable(station: dict[str, Any], capability: str | None) -> bool:
    """True when the entity applies to the station (None = always)."""
    return capability is None or capability in (station.get("capabilities") or [])


class OpoMeteoEntity(CoordinatorEntity[OpoMeteoCoordinator]):
    """One measure of one station, grouped under the station's device."""

    _attr_has_entity_name = True
    # only the online entity stays available while the station is offline
    _needs_online = True

    def __init__(self, coordinator: OpoMeteoCoordinator, station_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._station_id = station_id
        self._key = key
        self._attr_unique_id = (
            f"{device_key(coordinator.config_entry.entry_id, station_id)}_{key}"
        )
        self._attr_translation_key = key
        station = self.station or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_key(coordinator.config_entry.entry_id, station_id))},
            name=station.get("name") or station_id,
            manufacturer="OpoMeteo",
            model=station.get("type"),
            configuration_url=coordinator.config_entry.data[CONF_URL],
        )

    @property
    def station(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get("stations", {}).get(self._station_id)

    @property
    def available(self) -> bool:
        station = self.station
        if not super().available or station is None:
            return False
        return bool(station.get("online")) if self._needs_online else True

    @property
    def value(self) -> Any:
        return ((self.station or {}).get("values") or {}).get(self._key)
