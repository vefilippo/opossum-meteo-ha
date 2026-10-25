"""Coordinator data shape."""

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.opossum_meteo.const import DOMAIN

URL = "https://meteo.example.com"


async def test_station_named_server_does_not_collide(hass, aioclient_mock):
    aioclient_mock.get(
        f"{URL}/api/v1/ha/stations",
        json={
            "server_version": "1.2.3",
            "silent_after_s": 3600,
            "generated_at": 1.0,
            "stations": [{"id": "server", "name": "S"}, {"id": "a", "name": None}],
        },
    )
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=URL, data={"url": URL, "api_key": "k"}, options={}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data.data
    assert set(data["stations"]) == {"server", "a"}
    assert data["stations"]["server"]["name"] == "S"
    assert data["server"]["server_version"] == "1.2.3"
