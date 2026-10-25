"""Config, re-auth and options flow tests."""

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.opossum_meteo.const import DOMAIN

URL = "https://meteo.example.com"
ENDPOINT = f"{URL}/api/v1/ha/stations"
PAYLOAD = {
    "server_version": "1.0.0",
    "silent_after_s": 3600,
    "generated_at": 1792930000.0,
    "stations": [
        {"id": "Lignano", "name": "Lignano", "values": {}, "capabilities": []},
        {"id": "s2", "name": None, "values": {}, "capabilities": []},
        {"id": "Aviano", "name": "Aviano", "values": {}, "capabilities": []},
    ],
}


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


def _select_options(result):
    for key, validator in result["data_schema"].schema.items():
        if str(key) == "stations":
            return validator.config["options"]
    raise AssertionError("no stations field")


async def test_user_flow_creates_entry_with_selected_stations(hass, aioclient_mock):
    aioclient_mock.get(ENDPOINT, json=PAYLOAD)
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": URL + "/", "api_key": "opo_good"}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "stations"
    # labels are names (id when no name), sorted by label
    assert [o["label"] for o in _select_options(result)] == ["Aviano", "Lignano", "s2"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"stations": ["Lignano", "s2"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"url": URL, "api_key": "opo_good"}
    assert result["options"] == {
        "stations": ["Lignano", "s2"],
        "auto_add": True,
        "units": "ha",
        "scan_interval": 60,
    }
    assert result["result"].unique_id == URL


async def test_user_flow_invalid_auth(hass, aioclient_mock):
    aioclient_mock.get(ENDPOINT, status=401, json={"error": "invalid api key"})
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": URL, "api_key": "bad"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass, aioclient_mock):
    aioclient_mock.get(ENDPOINT, status=500)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": URL, "api_key": "k"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_url_aborts(hass, aioclient_mock):
    MockConfigEntry(
        domain=DOMAIN, unique_id=URL, data={"url": URL, "api_key": "k"}
    ).add_to_hass(hass)
    aioclient_mock.get(ENDPOINT, json=PAYLOAD)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": URL + "/", "api_key": "k"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _entry(**options):
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=URL,
        data={"url": URL, "api_key": "old"},
        options={
            "stations": ["Lignano"],
            "auto_add": True,
            "units": "ha",
            "scan_interval": 60,
            **options,
        },
    )


async def test_invalid_auth_triggers_reauth(hass, aioclient_mock):
    entry = _entry()
    entry.add_to_hass(hass)
    aioclient_mock.get(ENDPOINT, status=401, json={"error": "invalid api key"})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == [config_entries.SOURCE_REAUTH]

    # a wrong key keeps the form open with an error
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {"api_key": "still_bad"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(ENDPOINT, json=PAYLOAD)
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {"api_key": "opo_new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["api_key"] == "opo_new"
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_options_flow_saves_options(hass, aioclient_mock):
    entry = _entry(stations=["Lignano", "gone"])
    entry.add_to_hass(hass)
    aioclient_mock.get(ENDPOINT, json=PAYLOAD)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.update_interval.total_seconds() == 60

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    # all server stations plus the selected one that disappeared
    assert {o["value"] for o in _select_options(result)} == {
        "Lignano",
        "s2",
        "Aviano",
        "gone",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "stations": ["Aviano"],
            "auto_add": False,
            "units": "imperial",
            "scan_interval": 120,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        "stations": ["Aviano"],
        "auto_add": False,
        "units": "imperial",
        "scan_interval": 120,
    }
    await hass.async_block_till_done()
    # the update listener reloaded the entry with the new interval
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.update_interval.total_seconds() == 120
