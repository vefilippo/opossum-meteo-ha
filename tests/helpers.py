"""Shared test helpers."""

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.opossum_meteo.const import DOMAIN

ENTRY_ID = "test_entry"
URL = "https://meteo.example.com"
API = f"{URL}/api/v1/ha/stations"


def station(sid="Lignano", **over):
    base = {
        "id": sid,
        "name": sid,
        "type": "virtual",
        "latitude": 45.68,
        "longitude": 13.11,
        "altitude": 3.0,
        "online": True,
        "last_reading": 1792929600.0,
        "capabilities": ["temperature", "humidity", "pressure", "rain", "storm"],
        "values": {
            "temperature": 14.0,
            "humidity": 48.0,
            "pressure": 1013.25,
            "pressure_kind": "sea_level",
            "rain_today": 2.5,
            "rain_rate": 1.0,
            "battery": None,
            "battery_voltage": None,
            "rssi": None,
            "charging": None,
            "storm": False,
        },
    }
    base.update(over)
    return base


def payload(*stations):
    return {
        "server_version": "1.0.0",
        "silent_after_s": 3600,
        "generated_at": 1792930000.0,
        "stations": list(stations),
    }


async def setup(hass, aioclient_mock, stations, options=None, data_extra=None):
    aioclient_mock.get(API, json=payload(*stations))
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        unique_id=URL,
        data={"url": URL, "api_key": "k", **(data_extra or {})},
        options={
            "stations": [s["id"] for s in stations],
            "auto_add": True,
            "units": "ha",
            "scan_interval": 60,
            **(options or {}),
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def eid(hass, domain, sid, key):
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{ENTRY_ID}_{sid}_{key}")


async def refresh(hass, aioclient_mock, entry, *stations):
    aioclient_mock.clear_requests()
    aioclient_mock.get(API, json=payload(*stations))
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
