"""Relay outputs as switches."""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GlobalCacheConfigEntry, GlobalCacheData
from .api import GlobalCacheError
from .const import ATTR_DURATION, SERVICE_PULSE
from .entity import GlobalCacheEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlobalCacheConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        GlobalCacheRelay(entry.entry_id, data, c) for c in data.relay_connectors
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_PULSE,
        {
            vol.Optional(ATTR_DURATION, default=0.5): vol.All(
                vol.Coerce(float), vol.Range(min=0.05, max=60)
            )
        },
        "async_pulse",
    )


class GlobalCacheRelay(GlobalCacheEntity, SwitchEntity):
    """A single relay."""

    def __init__(self, entry_id: str, data: GlobalCacheData, connector: str) -> None:
        super().__init__(entry_id, data, connector, "relay", "Relay")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self._connector)

    async def _set(self, on: bool) -> None:
        try:
            state = await self._client.set_relay_state(self._connector, on)
        except GlobalCacheError as err:
            raise HomeAssistantError(f"Failed to switch {self._connector}: {err}") from err
        self.coordinator.async_set_updated_data(
            {**self.coordinator.data, self._connector: state}
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

    async def async_pulse(self, duration: float = 0.5) -> None:
        """Close the relay briefly, then open it again."""
        await self._set(True)
        try:
            await asyncio.sleep(duration)
        finally:
            await self._set(False)
