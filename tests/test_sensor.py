"""Sensor platform."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.opossum_meteo.const import DOMAIN

from pytest_homeassistant_custom_component.common import MockConfigEntry

from .helpers import eid, payload, refresh, setup, station


async def test_entities_follow_capabilities(hass, aioclient_mock):
    full = station("A", capabilities=["temperature", "humidity", "battery", "rssi", "charging"])
    bare = station("B", capabilities=[])
    await setup(hass, aioclient_mock, [full, bare])

    assert eid(hass, "sensor", "A", "temperature")
    assert eid(hass, "sensor", "A", "battery")
    assert eid(hass, "sensor", "A", "battery_voltage")
    assert eid(hass, "sensor", "A", "rssi")
    assert eid(hass, "binary_sensor", "A", "charging")
    assert eid(hass, "sensor", "A", "pressure") is None
    assert eid(hass, "sensor", "A", "rain_today") is None
    assert eid(hass, "binary_sensor", "A", "storm") is None
    # always present
    assert eid(hass, "sensor", "B", "last_reading")
    assert eid(hass, "binary_sensor", "B", "online")
    assert eid(hass, "sensor", "B", "temperature") is None

    dev = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "test_entry_A")})
    assert dev.name == "A" and dev.model == "virtual"
    assert dev.configuration_url == "https://meteo.example.com"


async def test_values_and_pressure_kind(hass, aioclient_mock):
    await setup(hass, aioclient_mock, [station()])
    assert hass.states.get(eid(hass, "sensor", "Lignano", "temperature")).state == "14.0"
    p = hass.states.get(eid(hass, "sensor", "Lignano", "pressure"))
    assert p.state == "1013.25" and p.attributes["pressure_kind"] == "sea_level"
    assert hass.states.get(eid(hass, "sensor", "Lignano", "rain_today")).state == "2.5"
    last = hass.states.get(eid(hass, "sensor", "Lignano", "last_reading"))
    assert last.state.startswith("2026-10-")


async def test_offline_station_measures_unavailable(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock, [station()])
    assert hass.states.get(eid(hass, "sensor", "Lignano", "temperature")).state == "14.0"

    await refresh(hass, aioclient_mock, entry, station(online=False))
    assert hass.states.get(eid(hass, "sensor", "Lignano", "temperature")).state == "unavailable"
    assert hass.states.get(eid(hass, "binary_sensor", "Lignano", "storm")).state == "unavailable"
    assert hass.states.get(eid(hass, "binary_sensor", "Lignano", "online")).state == "off"

    # the last reading is most useful while offline: it stays available
    last = hass.states.get(eid(hass, "sensor", "Lignano", "last_reading"))
    assert last.state.startswith("2026-10-")

    # station missing from the response: everything unavailable
    await refresh(hass, aioclient_mock, entry)
    assert hass.states.get(eid(hass, "sensor", "Lignano", "humidity")).state == "unavailable"
    assert hass.states.get(eid(hass, "binary_sensor", "Lignano", "online")).state == "unavailable"


async def test_diagnostic_entities_disabled_by_default(hass, aioclient_mock):
    s = station(capabilities=["battery", "rssi"])
    await setup(hass, aioclient_mock, [s])
    reg = er.async_get(hass)
    for key in ("battery_voltage", "rssi"):
        e = reg.async_get(eid(hass, "sensor", "Lignano", key))
        assert e.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    last = reg.async_get(eid(hass, "sensor", "Lignano", "last_reading"))
    assert last.disabled_by is None


async def test_units_option_imperial(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock, [station()])
    t = eid(hass, "sensor", "Lignano", "temperature")
    p = eid(hass, "sensor", "Lignano", "pressure")
    assert hass.states.get(t).attributes["unit_of_measurement"] == "°C"

    hass.config_entries.async_update_entry(entry, options={**entry.options, "units": "imperial"})
    await hass.async_block_till_done()
    ts = hass.states.get(t)
    assert ts.attributes["unit_of_measurement"] == "°F" and float(ts.state) == 57.2
    ps = hass.states.get(p)
    assert ps.attributes["unit_of_measurement"] == "inHg" and round(float(ps.state), 2) == 29.92
    r = hass.states.get(eid(hass, "sensor", "Lignano", "rain_today"))
    assert r.attributes["unit_of_measurement"] == "in"
    rr = hass.states.get(eid(hass, "sensor", "Lignano", "rain_rate"))
    assert rr.attributes["unit_of_measurement"] == "in/h"

    hass.config_entries.async_update_entry(entry, options={**entry.options, "units": "ha"})
    await hass.async_block_till_done()
    assert hass.states.get(t).attributes["unit_of_measurement"] == "°C"
    assert hass.states.get(p).attributes["unit_of_measurement"] == "hPa"


async def test_user_unit_override_and_precision_survive_reload(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock, [station()])
    reg = er.async_get(hass)
    t = eid(hass, "sensor", "Lignano", "temperature")
    reg.async_update_entity_options(t, "sensor", {"unit_of_measurement": "°F", "display_precision": 0})
    await hass.async_block_till_done()

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    opts = reg.async_get(t).options["sensor"]
    assert opts["unit_of_measurement"] == "°F" and opts["display_precision"] == 0
    assert hass.states.get(t).attributes["unit_of_measurement"] == "°F"

    # changing the option still converts, keeping the precision
    hass.config_entries.async_update_entry(entry, options={**entry.options, "units": "metric"})
    await hass.async_block_till_done()
    opts = reg.async_get(t).options["sensor"]
    assert opts["unit_of_measurement"] == "°C" and opts["display_precision"] == 0
    assert hass.states.get(t).attributes["unit_of_measurement"] == "°C"
    hass.config_entries.async_update_entry(entry, options={**entry.options, "units": "ha"})
    await hass.async_block_till_done()
    opts = reg.async_get(t).options["sensor"]
    assert "unit_of_measurement" not in opts and opts["display_precision"] == 0


async def test_late_capability_gets_units_override(hass, aioclient_mock):
    entry = await setup(
        hass, aioclient_mock, [station(capabilities=["humidity"])], options={"units": "imperial"}
    )
    assert eid(hass, "sensor", "Lignano", "temperature") is None
    await refresh(hass, aioclient_mock, entry, station())
    st = hass.states.get(eid(hass, "sensor", "Lignano", "temperature"))
    assert st.attributes["unit_of_measurement"] == "°F"


async def test_two_servers_same_station_id(hass, aioclient_mock):
    await setup(hass, aioclient_mock, [station("A")])
    other = "https://other.example.com"
    aioclient_mock.get(f"{other}/api/v1/ha/stations", json=payload(station("A")))
    entry2 = MockConfigEntry(
        domain=DOMAIN, entry_id="second", unique_id=other,
        data={"url": other, "api_key": "k"}, options={"stations": ["A"]},
    )
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()
    reg = er.async_get(hass)
    assert eid(hass, "sensor", "A", "temperature")
    assert reg.async_get_entity_id("sensor", DOMAIN, "second_A_temperature")
    assert len(dr.async_get(hass).devices) == 2


async def test_device_name_follows_station(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock, [station("A")])
    await refresh(hass, aioclient_mock, entry, station("A", name="Renamed", type="esp32"))
    dev = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "test_entry_A")})
    assert dev.name == "Renamed" and dev.model == "esp32"
