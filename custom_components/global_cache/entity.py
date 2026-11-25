"""Shared entity base class."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import GlobalCacheCoordinator

if TYPE_CHECKING:
    from . import GlobalCacheData


class GlobalCacheEntity(CoordinatorEntity[GlobalCacheCoordinator]):
    """Entity bound to one connector of a unit; unavailable when the unit is."""

    _attr_has_entity_name = True

    def __init__(
        self, entry_id: str, data: GlobalCacheData, connector: str, kind: str, label: str
    ) -> None:
        super().__init__(data.coordinator)
        self._client = data.client
        self._connector = connector
        self._attr_unique_id = f"{entry_id}_{kind}_{connector}"
        self._attr_name = f"{label} {connector}"
        self._attr_device_info = data.device_info
