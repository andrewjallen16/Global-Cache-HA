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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GlobalCacheConfigEntry, GlobalCacheData
from .api import GlobalCacheError
from .const import ATTR_DURATION, SERVICE_PULSE
from .coordinator import GlobalCacheCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlobalCacheConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        GlobalCacheRelay(entry.entry_id, data, connector)
        for module in data.modules
        if module.is_relay
        for connector in module.connectors
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


class GlobalCacheRelay(CoordinatorEntity[GlobalCacheCoordinator], SwitchEntity):
    """A single relay."""

    _attr_has_entity_name = True

    def __init__(self, entry_id: str, data: GlobalCacheData, connector: str) -> None:
        super().__init__(data.coordinator)
        self._client = data.client
        self._connector = connector
        self._attr_unique_id = f"{entry_id}_relay_{connector}"
        self._attr_name = f"Relay {connector}"
        self._attr_device_info = data.device_info

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
