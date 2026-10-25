"""Client for the OpoMeteo server API."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class OpoMeteoAuthError(Exception):
    """The API key was rejected."""


class OpoMeteoConnectionError(Exception):
    """The server could not be reached or answered badly."""


def normalize_url(url: str) -> str:
    """Strip whitespace and trailing slashes."""
    return url.strip().rstrip("/")


class OpoMeteoClient:
    """Thin async client for GET /api/v1/ha/stations."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, key: str) -> None:
        self._session = session
        self._base_url = normalize_url(base_url)
        self._key = key

    async def stations(self) -> dict[str, Any]:
        """Fetch the station list; raises OpoMeteoAuthError / OpoMeteoConnectionError."""
        try:
            async with asyncio.timeout(20):
                resp = await self._session.get(
                    f"{self._base_url}/api/v1/ha/stations",
                    headers={"Authorization": f"Bearer {self._key}"},
                )
                if resp.status == 401:
                    raise OpoMeteoAuthError("invalid api key")
                if resp.status != 200:
                    raise OpoMeteoConnectionError(f"HTTP {resp.status}")
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise OpoMeteoConnectionError(str(err) or type(err).__name__) from err
        if not isinstance(data, dict) or not isinstance(data.get("stations"), list):
            raise OpoMeteoConnectionError("unexpected response")
        return data
