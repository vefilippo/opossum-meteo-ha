"""OpoMeteo binary sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_STATIONS
from .coordinator import OpoMeteoConfigEntry, OpoMeteoCoordinator
from .entity import OpoMeteoEntity, station_capable


@dataclass(frozen=True, kw_only=True)
class OpoMeteoBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor description plus the capability that enables it."""

    capability: str | None = None


BINARY_SENSORS: tuple[OpoMeteoBinaryDescription, ...] = (
    OpoMeteoBinaryDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OpoMeteoBinaryDescription(
        key="storm", capability="storm", icon="mdi:weather-lightning"
    ),
    OpoMeteoBinaryDescription(
        key="charging",
        capability="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpoMeteoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create binary sensors for selected stations; add late capabilities as they appear."""
    coordinator = entry.runtime_data
    added: set[tuple[str, str]] = set()

    def _add_new() -> None:
        new: list[OpoMeteoBinarySensor] = []
        for sid in entry.options.get(CONF_STATIONS, []):
            station = (coordinator.data or {}).get("stations", {}).get(sid)
            if station is None:
                continue
            for desc in BINARY_SENSORS:
                if (sid, desc.key) not in added and station_capable(station, desc.capability):
                    added.add((sid, desc.key))
                    new.append(OpoMeteoBinarySensor(coordinator, sid, desc))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class OpoMeteoBinarySensor(OpoMeteoEntity, BinarySensorEntity):
    """Online / storm / charging flag of a station."""

    entity_description: OpoMeteoBinaryDescription

    def __init__(
        self,
        coordinator: OpoMeteoCoordinator,
        station_id: str,
        description: OpoMeteoBinaryDescription,
    ) -> None:
        super().__init__(coordinator, station_id, description.key)
        self.entity_description = description
        self._needs_online = description.key != "online"

    @property
    def is_on(self) -> bool | None:
        station = self.station or {}
        value = station.get("online") if self._key == "online" else self.value
        return None if value is None else bool(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._key != "online":
            return None
        station = self.station or {}
        lat, lon = station.get("latitude"), station.get("longitude")
        if lat is None or lon is None:
            return None
        return {"latitude": lat, "longitude": lon}
