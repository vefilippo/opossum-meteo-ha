"""Binary sensor platform."""

from homeassistant.helpers import entity_registry as er

from .helpers import eid, refresh, setup, station


async def test_online_entity_has_location(hass, aioclient_mock):
    await setup(hass, aioclient_mock, [station()])
    st = hass.states.get(eid(hass, "binary_sensor", "Lignano", "online"))
    assert st.state == "on"
    assert st.attributes["latitude"] == 45.68 and st.attributes["longitude"] == 13.11
    assert st.attributes["device_class"] == "connectivity"


async def test_online_entity_without_position(hass, aioclient_mock):
    await setup(hass, aioclient_mock, [station(latitude=None, longitude=None)])
    st = hass.states.get(eid(hass, "binary_sensor", "Lignano", "online"))
    assert "latitude" not in st.attributes


async def test_storm_and_charging(hass, aioclient_mock):
    caps = ["storm", "charging"]
    s = station(capabilities=caps)
    s["values"].update(storm=True, charging=False)
    entry = await setup(hass, aioclient_mock, [s])
    assert hass.states.get(eid(hass, "binary_sensor", "Lignano", "storm")).state == "on"
    # diagnostic: registered but disabled by default, so it has no state until enabled
    charging = eid(hass, "binary_sensor", "Lignano", "charging")
    assert charging is not None and hass.states.get(charging) is None
    assert er.async_get(hass).async_get(charging).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    await refresh(hass, aioclient_mock, entry, station(online=False, capabilities=caps))
    assert hass.states.get(eid(hass, "binary_sensor", "Lignano", "storm")).state == "unavailable"
    assert hass.states.get(eid(hass, "binary_sensor", "Lignano", "online")).state == "off"
