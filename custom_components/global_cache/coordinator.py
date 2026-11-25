"""Polling coordinator: relay/sensor state and unit availability."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GlobalCacheClient, GlobalCacheError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GlobalCacheCoordinator(DataUpdateCoordinator[dict[str, bool]]):
    """Fetches {connector: is_on} for relays and sensor inputs.

    On units with neither (pure IR) it polls the firmware version instead, so
    entities still go unavailable when the unit drops off the network.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GlobalCacheClient,
        state_connectors: list[str],
        interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.state_connectors = state_connectors

    async def _async_update_data(self) -> dict[str, bool]:
        try:
            if self.state_connectors:
                return await self.client.get_states(self.state_connectors)
            await self.client.get_version()
            return {}
        except GlobalCacheError as err:
            raise UpdateFailed(f"Error talking to {self.client.host}: {err}") from err
