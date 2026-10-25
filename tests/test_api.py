"""API client tests."""

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.opossum_meteo.api import (
    OpoMeteoAuthError,
    OpoMeteoClient,
    OpoMeteoConnectionError,
)

URL = "https://meteo.example.com"
ENDPOINT = f"{URL}/api/v1/ha/stations"
PAYLOAD = {"server_version": "1.0.0", "silent_after_s": 3600, "stations": []}


async def test_client_ok_and_errors(hass, aioclient_mock):
    session = async_get_clientsession(hass)
    client = OpoMeteoClient(session, URL + "/", "opo_key")

    aioclient_mock.get(ENDPOINT, json=PAYLOAD)
    assert await client.stations() == PAYLOAD
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer opo_key"

    aioclient_mock.clear_requests()
    aioclient_mock.get(ENDPOINT, status=401, json={"error": "invalid api key"})
    with pytest.raises(OpoMeteoAuthError):
        await client.stations()

    aioclient_mock.clear_requests()
    aioclient_mock.get(ENDPOINT, status=500)
    with pytest.raises(OpoMeteoConnectionError):
        await client.stations()

    aioclient_mock.clear_requests()
    aioclient_mock.get(ENDPOINT, status=200, text="not json")
    with pytest.raises(OpoMeteoConnectionError):
        await client.stations()

    aioclient_mock.clear_requests()
    aioclient_mock.get(ENDPOINT, exc=TimeoutError())
    with pytest.raises(OpoMeteoConnectionError):
        await client.stations()


async def test_client_rejects_malformed_stations(hass, aioclient_mock):
    client = OpoMeteoClient(async_get_clientsession(hass), URL, "k")
    for bad in ([{"name": "x"}], [{"id": 5}], ["Lignano"]):
        aioclient_mock.clear_requests()
        aioclient_mock.get(ENDPOINT, json={"stations": bad})
        with pytest.raises(OpoMeteoConnectionError):
            await client.stations()
