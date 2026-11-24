"""The Global Caché iTach integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo

from .api import GlobalCacheClient, GlobalCacheError, Module
from .const import DEFAULT_PORT, DOMAIN, PLATFORMS
from .coordinator import GlobalCacheCoordinator
from .store import IRCodeStore


@dataclass
class GlobalCacheData:
    """Runtime data for one config entry."""

    client: GlobalCacheClient
    coordinator: GlobalCacheCoordinator
    codes: IRCodeStore
    modules: list[Module]
    device_info: DeviceInfo


type GlobalCacheConfigEntry = ConfigEntry[GlobalCacheData]


def _model_name(modules: list[Module]) -> str:
    has_relay = any(m.is_relay for m in modules)
    has_ir = any(m.is_ir for m in modules)
    if has_relay and has_ir:
        return "iTach (IR + Relay)"
    if has_relay:
        return "iTach (Relay)"
    if has_ir:
        return "iTach (IR)"
    return "iTach"


async def async_setup_entry(hass: HomeAssistant, entry: GlobalCacheConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    client = GlobalCacheClient(host, entry.data.get(CONF_PORT, DEFAULT_PORT))

    try:
        modules = await client.get_devices()
    except GlobalCacheError as err:
        raise ConfigEntryNotReady(f"Unable to connect to {host}: {err}") from err
    version = await client.get_version()

    relay_connectors = [c for m in modules if m.is_relay for c in m.connectors]
    coordinator = GlobalCacheCoordinator(hass, entry, client, relay_connectors)
    await coordinator.async_config_entry_first_refresh()

    codes = IRCodeStore(hass, entry.entry_id)
    await codes.async_load()

    entry.runtime_data = GlobalCacheData(
        client=client,
        coordinator=coordinator,
        codes=codes,
        modules=modules,
        device_info=DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Global Caché",
            model=_model_name(modules),
            sw_version=version,
            configuration_url=f"http://{host}",
        ),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GlobalCacheConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: GlobalCacheConfigEntry) -> None:
    """Delete learned codes when the entry is removed."""
    await IRCodeStore(hass, entry.entry_id).async_remove()
