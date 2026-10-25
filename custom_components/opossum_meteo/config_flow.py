"""Config, re-auth, reconfigure and options flows."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    OpoMeteoAuthError,
    OpoMeteoClient,
    OpoMeteoConnectionError,
    normalize_url,
)
from .const import (
    CONF_API_KEY,
    CONF_AUTO_ADD,
    CONF_KNOWN_STATIONS,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    CONF_UNITS,
    CONF_URL,
    DEFAULT_AUTO_ADD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNITS,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    UNITS,
)

_LOGGER = logging.getLogger(__name__)


def _station_options(
    stations: list[dict[str, Any]], extra_ids: list[str] | None = None
) -> list[SelectOptionDict]:
    """Options with id as value and name (or id) as label, sorted by label."""
    labels = {st["id"]: st.get("name") or st["id"] for st in stations}
    for sid in extra_ids or []:
        labels.setdefault(sid, sid)
    return [
        SelectOptionDict(value=sid, label=label)
        for sid, label in sorted(labels.items(), key=lambda kv: (kv[1].casefold(), kv[0]))
    ]


_KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


async def _validate(hass, url: str, api_key: str) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch the stations with these credentials; returns (payload, error key)."""
    client = OpoMeteoClient(async_get_clientsession(hass), url, api_key)
    try:
        return await client.stations(), None
    except OpoMeteoAuthError:
        return None, "invalid_auth"
    except OpoMeteoConnectionError:
        return None, "cannot_connect"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error validating the OpoMeteo server")
        return None, "unknown"


def _stations_selector(options: list[SelectOptionDict]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(options=options, multiple=True, mode=SelectSelectorMode.LIST)
    )


class OpoMeteoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the OpoMeteo config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._url = ""
        self._api_key = ""
        self._stations: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            client = OpoMeteoClient(
                async_get_clientsession(self.hass), url, user_input[CONF_API_KEY]
            )
            try:
                payload = await client.stations()
            except OpoMeteoAuthError:
                errors["base"] = "invalid_auth"
            except OpoMeteoConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating the OpoMeteo server")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                self._url = url
                self._api_key = user_input[CONF_API_KEY]
                self._stations = payload["stations"]
                return await self.async_step_stations()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL, default=(user_input or {}).get(CONF_URL, "")
                    ): str,
                    vol.Required(CONF_API_KEY): _KEY_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        options = _station_options(self._stations)
        if user_input is not None:
            return self.async_create_entry(
                title=f"OpoMeteo ({self._url})",
                data={
                    CONF_URL: self._url,
                    CONF_API_KEY: self._api_key,
                    CONF_KNOWN_STATIONS: [st["id"] for st in self._stations],
                },
                options={
                    CONF_STATIONS: user_input[CONF_STATIONS],
                    CONF_AUTO_ADD: DEFAULT_AUTO_ADD,
                    CONF_UNITS: DEFAULT_UNITS,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )
        return self.async_show_form(
            step_id="stations",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STATIONS, default=[o["value"] for o in options]
                    ): _stations_selector(options)
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            client = OpoMeteoClient(
                async_get_clientsession(self.hass),
                entry.data[CONF_URL],
                user_input[CONF_API_KEY],
            )
            try:
                await client.stations()
            except OpoMeteoAuthError:
                errors["base"] = "invalid_auth"
            except OpoMeteoConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating the OpoMeteo server")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): _KEY_SELECTOR}),
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the server address (and optionally the key) in place."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            api_key = user_input.get(CONF_API_KEY) or entry.data[CONF_API_KEY]
            _, error = await _validate(self.hass, url, api_key)
            if error:
                errors["base"] = error
            else:
                # the address is expected to change, so only other entries can clash
                existing = await self.async_set_unique_id(url)
                if existing is not None and existing.entry_id != entry.entry_id:
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=url,
                    title=f"OpoMeteo ({url})",
                    data_updates={CONF_URL: url, CONF_API_KEY: api_key},
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL,
                        default=(user_input or {}).get(CONF_URL, entry.data[CONF_URL]),
                    ): str,
                    vol.Optional(CONF_API_KEY): _KEY_SELECTOR,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OpoMeteoOptionsFlow:
        return OpoMeteoOptionsFlow()


class OpoMeteoOptionsFlow(OptionsFlow):
    """Stations, auto-add, units and polling interval."""

    _offered: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # every station shown is now a deliberate choice: not "new" any more
            entry = self.config_entry
            known = set(entry.data.get(CONF_KNOWN_STATIONS) or [])
            known |= set(self._offered) | set(user_input[CONF_STATIONS])
            if known != set(entry.data.get(CONF_KNOWN_STATIONS) or []):
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_KNOWN_STATIONS: sorted(known)}
                )
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        opts = entry.options
        client = OpoMeteoClient(
            async_get_clientsession(self.hass),
            entry.data[CONF_URL],
            entry.data[CONF_API_KEY],
        )
        try:
            stations = (await client.stations())["stations"]
        except (OpoMeteoAuthError, OpoMeteoConnectionError) as err:
            # fall back to the last data the coordinator fetched
            coordinator = getattr(entry, "runtime_data", None)
            if coordinator is None or coordinator.data is None:
                return self.async_abort(
                    reason="invalid_auth"
                    if isinstance(err, OpoMeteoAuthError)
                    else "cannot_connect"
                )
            stations = list(coordinator.data["stations"].values())

        selected = list(opts.get(CONF_STATIONS, []))
        options = _station_options(stations, selected)
        self._offered = [o["value"] for o in options]
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATIONS, default=selected): _stations_selector(options),
                    vol.Required(
                        CONF_AUTO_ADD, default=opts.get(CONF_AUTO_ADD, DEFAULT_AUTO_ADD)
                    ): bool,
                    vol.Required(
                        CONF_UNITS, default=opts.get(CONF_UNITS, DEFAULT_UNITS)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=UNITS,
                            translation_key=CONF_UNITS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(
                        NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_SCAN_INTERVAL,
                                max=3600,
                                step=1,
                                unit_of_measurement="s",
                                mode=NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Coerce(int),
                    ),
                }
            ),
        )
