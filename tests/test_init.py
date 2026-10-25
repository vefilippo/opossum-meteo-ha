"""Station selection, new stations, removal."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.opossum_meteo.const import DOMAIN

from .helpers import eid, refresh, setup, station


async def test_new_station_auto_added(hass, aioclient_mock):
    a = station("A")
    entry = await setup(hass, aioclient_mock, [a], data_extra={"known_stations": ["A"]})
    assert eid(hass, "sensor", "B", "temperature") is None

    await refresh(hass, aioclient_mock, entry, a, station("B"))
    assert entry.options["stations"] == ["A", "B"]
    assert "B" in entry.data["known_stations"]
    assert eid(hass, "sensor", "B", "temperature")
    assert hass.states.get(eid(hass, "sensor", "B", "temperature")).state == "14.0"


async def test_new_station_not_auto_added_raises_issue(hass, aioclient_mock):
    a = station("A")
    entry = await setup(
        hass, aioclient_mock, [a], options={"auto_add": False}, data_extra={"known_stations": ["A"]}
    )
    await refresh(hass, aioclient_mock, entry, a, station("B", name="Beta"))
    assert entry.options["stations"] == ["A"]
    assert eid(hass, "sensor", "B", "temperature") is None
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "new_station_test_entry_B")
    assert issue is not None and not issue.is_fixable
    assert issue.translation_key == "new_station"
    assert issue.translation_placeholders == {"name": "Beta"}

    # ticking it in the options removes the issue
    hass.config_entries.async_update_entry(entry, options={**entry.options, "stations": ["A", "B"]})
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_station_test_entry_B") is None
    assert eid(hass, "sensor", "B", "temperature")


async def test_issue_removed_when_station_disappears(hass, aioclient_mock):
    a = station("A")
    entry = await setup(
        hass, aioclient_mock, [a], options={"auto_add": False}, data_extra={"known_stations": ["A"]}
    )
    await refresh(hass, aioclient_mock, entry, a, station("B"))
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_station_test_entry_B")
    await refresh(hass, aioclient_mock, entry, a)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_station_test_entry_B") is None


async def test_unticked_station_is_not_readded(hass, aioclient_mock):
    a, b = station("A"), station("B")
    entry = await setup(
        hass, aioclient_mock, [a, b],
        options={"stations": ["A"]}, data_extra={"known_stations": ["A", "B"]},
    )
    assert eid(hass, "sensor", "B", "temperature") is None
    await refresh(hass, aioclient_mock, entry, a, b)
    assert entry.options["stations"] == ["A"]
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_station_test_entry_B") is None


async def test_deselected_station_entities_removed(hass, aioclient_mock):
    a, b = station("A"), station("B")
    entry = await setup(hass, aioclient_mock, [a, b], data_extra={"known_stations": ["A", "B"]})
    assert eid(hass, "sensor", "B", "temperature")
    assert dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "test_entry_B")})

    hass.config_entries.async_update_entry(entry, options={**entry.options, "stations": ["A"]})
    await hass.async_block_till_done()
    assert eid(hass, "sensor", "B", "temperature") is None
    assert dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "test_entry_B")}) is None
    assert not [
        e
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if e.unique_id.startswith("test_entry_B_")
    ]
    assert eid(hass, "sensor", "A", "temperature")


async def test_entry_without_known_list_does_not_readd(hass, aioclient_mock):
    a, b = station("A"), station("B")
    entry = await setup(hass, aioclient_mock, [a, b], options={"stations": ["A"]})
    assert entry.options["stations"] == ["A"]
    assert set(entry.data["known_stations"]) == {"A", "B"}


async def test_remove_entry_deletes_its_issues(hass, aioclient_mock):
    a = station("A")
    entry = await setup(
        hass, aioclient_mock, [a], options={"auto_add": False}, data_extra={"known_stations": ["A"]}
    )
    await refresh(hass, aioclient_mock, entry, a, station("B"))
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_station_test_entry_B")
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_station_test_entry_B") is None


async def test_options_submit_marks_offered_as_known(hass, aioclient_mock):
    a = station("A")
    entry = await setup(
        hass, aioclient_mock, [a], options={"auto_add": False}, data_extra={"known_stations": ["A"]}
    )
    await refresh(hass, aioclient_mock, entry, a, station("B"))
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_station_test_entry_B")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"stations": ["A"], "auto_add": True, "units": "ha", "scan_interval": 60},
    )
    await hass.async_block_till_done()
    assert "B" in entry.data["known_stations"]
    assert entry.options["stations"] == ["A"]  # unticked stays out despite auto_add
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_station_test_entry_B") is None


async def test_remove_device_only_when_inactive(hass, aioclient_mock):
    from custom_components.opossum_meteo import async_remove_config_entry_device

    a, b = station("A"), station("B")
    entry = await setup(hass, aioclient_mock, [a, b], options={"stations": ["A"]})
    reg = dr.async_get(hass)
    dev_a = reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "test_entry_A")}
    )
    dev_b = reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "test_entry_B")}
    )
    assert await async_remove_config_entry_device(hass, entry, dev_a) is False
    assert await async_remove_config_entry_device(hass, entry, dev_b) is True
