"""Persistent storage of learned IR commands."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION


class IRCodeStore:
    """Learned codes: {device: {command: sendir_body}}."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, dict[str, str]]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.codes"
        )
        self._codes: dict[str, dict[str, str]] = {}

    async def async_load(self) -> None:
        self._codes = await self._store.async_load() or {}

    async def async_remove(self) -> None:
        await self._store.async_remove()

    def get(self, device: str, command: str) -> str | None:
        return self._codes.get(device, {}).get(command)

    async def async_set(self, device: str, command: str, code: str) -> None:
        self._codes.setdefault(device, {})[command] = code
        await self._store.async_save(self._codes)

    async def async_delete(self, device: str, command: str) -> bool:
        if command not in self._codes.get(device, {}):
            return False
        del self._codes[device][command]
        if not self._codes[device]:
            del self._codes[device]
        await self._store.async_save(self._codes)
        return True
