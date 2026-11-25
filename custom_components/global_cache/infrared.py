"""Native Home Assistant `infrared` emitters (HA 2026.4+).

Lets brand integrations such as LG Infrared use an iTach IR connector as
their emitter. Raw timings are converted to Global Caché's carrier-cycle format.
"""
from __future__ import annotations

from homeassistant.components.infrared import InfraredEmitterEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GlobalCacheConfigEntry, GlobalCacheData
from .api import GlobalCacheError
from .entity import GlobalCacheEntity
from .ir import timings_to_gc


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlobalCacheConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        GlobalCacheEmitter(entry.entry_id, data, c) for c in data.ir_connectors
    )


class GlobalCacheEmitter(GlobalCacheEntity, InfraredEmitterEntity):
    """An IR connector exposed as an infrared emitter."""

    def __init__(self, entry_id: str, data: GlobalCacheData, connector: str) -> None:
        super().__init__(entry_id, data, connector, "emitter", "IR emitter")

    async def async_send_command(self, command) -> None:
        try:
            body = timings_to_gc(
                command.get_raw_timings(), getattr(command, "modulation", None)
            )
        except ValueError as err:
            raise HomeAssistantError(f"Cannot send IR command: {err}") from err
        try:
            await self._client.send_ir(self._connector, body)
        except GlobalCacheError as err:
            raise HomeAssistantError(f"Failed to send IR: {err}") from err
