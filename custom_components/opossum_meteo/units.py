"""Unit overrides for the units option."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)

# sensor device class -> unit per units option ("ha" has no override)
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


def unit_override(device_class: str | None, units: str) -> str | None:
    """Unit to force for a device class, or None (no override / not convertible)."""
    return UNIT_OVERRIDES.get(device_class, {}).get(units) if device_class else None


def merged_sensor_options(current: dict | None, unit: str | None) -> dict:
    """Sensor options with the unit set (or removed), keeping e.g. display precision."""
    opts = dict(current or {})
    if unit:
        opts["unit_of_measurement"] = unit
    else:
        opts.pop("unit_of_measurement", None)
    return opts
