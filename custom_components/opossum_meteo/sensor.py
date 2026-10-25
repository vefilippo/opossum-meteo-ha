"""OpoMeteo sensors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_STATIONS
from .coordinator import OpoMeteoConfigEntry, OpoMeteoCoordinator
from .entity import OpoMeteoEntity, station_capable


@dataclass(frozen=True, kw_only=True)
class OpoMeteoSensorDescription(SensorEntityDescription):
    """Sensor description plus the station capability that enables it."""

    capability: str | None = None


SENSORS: tuple[OpoMeteoSensorDescription, ...] = (
    OpoMeteoSensorDescription(
        key="temperature",
        capability="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OpoMeteoSensorDescription(
        key="humidity",
        capability="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OpoMeteoSensorDescription(
        key="pressure",
        capability="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OpoMeteoSensorDescription(
        key="rain_today",
        capability="rain",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    OpoMeteoSensorDescription(
        key="rain_rate",
        capability="rain",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OpoMeteoSensorDescription(
        key="battery",
        capability="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OpoMeteoSensorDescription(
        key="last_reading",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OpoMeteoSensorDescription(
        key="battery_voltage",
        capability="battery",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    OpoMeteoSensorDescription(
        key="rssi",
        capability="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpoMeteoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors for selected stations; add late capabilities as they appear."""
    coordinator = entry.runtime_data
    added: set[tuple[str, str]] = set()

    def _add_new() -> None:
        new: list[OpoMeteoSensor] = []
        for sid in entry.options.get(CONF_STATIONS, []):
            station = (coordinator.data or {}).get("stations", {}).get(sid)
            if station is None:
                continue
            for desc in SENSORS:
                if (sid, desc.key) not in added and station_capable(station, desc.capability):
                    added.add((sid, desc.key))
                    new.append(OpoMeteoSensor(coordinator, sid, desc))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class OpoMeteoSensor(OpoMeteoEntity, SensorEntity):
    """A numeric measure of a station."""

    entity_description: OpoMeteoSensorDescription

    def __init__(
        self,
        coordinator: OpoMeteoCoordinator,
        station_id: str,
        description: OpoMeteoSensorDescription,
    ) -> None:
        super().__init__(coordinator, station_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        if self._key == "last_reading":
            ts = (self.station or {}).get("last_reading")
            return datetime.fromtimestamp(ts, UTC) if ts is not None else None
        return self.value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._key != "pressure":
            return None
        kind = ((self.station or {}).get("values") or {}).get("pressure_kind")
        return {"pressure_kind": kind} if kind else None
