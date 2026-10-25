"""Data update coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpoMeteoAuthError, OpoMeteoClient, OpoMeteoConnectionError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type OpoMeteoConfigEntry = ConfigEntry[OpoMeteoCoordinator]


class OpoMeteoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the server; data is {"server": metadata, "stations": {station_id: station}}."""

    config_entry: OpoMeteoConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: OpoMeteoConfigEntry, client: OpoMeteoClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.setup_started = dt_util.utcnow()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            payload = await self.client.stations()
        except OpoMeteoAuthError as err:
            raise ConfigEntryAuthFailed("API key rejected") from err
        except OpoMeteoConnectionError as err:
            raise UpdateFailed(f"Error talking to OpoMeteo: {err}") from err
        return {
            "server": {
                k: payload.get(k)
                for k in ("server_version", "silent_after_s", "generated_at")
            },
            "stations": {st["id"]: st for st in payload["stations"]},
        }
