"""IR connectors configured as contact-closure sensor inputs."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GlobalCacheConfigEntry, GlobalCacheData
from .entity import GlobalCacheEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlobalCacheConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        GlobalCacheSensor(entry.entry_id, data, c) for c in data.sensor_connectors
    )


class GlobalCacheSensor(GlobalCacheEntity, BinarySensorEntity):
    """Sensor input. On = contact closed / input active."""

    def __init__(self, entry_id: str, data: GlobalCacheData, connector: str) -> None:
        super().__init__(entry_id, data, connector, "sensor", "Sensor")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self._connector)
