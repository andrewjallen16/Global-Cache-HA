"""Polling coordinator for relay state."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GlobalCacheClient, GlobalCacheError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class GlobalCacheCoordinator(DataUpdateCoordinator[dict[str, bool]]):
    """Fetches relay states ({connector: is_on})."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GlobalCacheClient,
        relay_connectors: list[str],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=SCAN_INTERVAL if relay_connectors else None,
        )
        self.client = client
        self.relay_connectors = relay_connectors

    async def _async_update_data(self) -> dict[str, bool]:
        if not self.relay_connectors:
            return {}
        try:
            return await self.client.get_relay_states(self.relay_connectors)
        except GlobalCacheError as err:
            raise UpdateFailed(f"Error talking to {self.client.host}: {err}") from err
