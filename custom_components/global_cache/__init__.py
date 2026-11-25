"""The Global Caché iTach integration."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo

from .api import GlobalCacheClient, GlobalCacheError, Module
from .const import (
    CONF_MODEL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    IR_MODES,
    PLATFORMS,
    SENSOR_MODES,
)
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
    firmware: str | None
    relay_connectors: list[str]
    ir_connectors: list[str]
    sensor_connectors: list[str]
    ir_modes: dict[str, str]


type GlobalCacheConfigEntry = ConfigEntry[GlobalCacheData]


def _model_name(entry: ConfigEntry, modules: list[Module]) -> str:
    if model := entry.data.get(CONF_MODEL):
        return model.replace("iTach", "iTach ", 1).replace("  ", " ")
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
    client = GlobalCacheClient(
        host,
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        timeout=int(entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
    )

    try:
        modules = await client.get_devices()
        all_ir = [c for m in modules if m.is_ir for c in m.connectors]
        ir_modes = await client.get_ir_modes(all_ir) if all_ir else {}
    except GlobalCacheError as err:
        raise ConfigEntryNotReady(f"Unable to connect to {host}: {err}") from err

    firmware: str | None = None
    with suppress(GlobalCacheError):
        firmware = await client.get_version()
    firmware = firmware or None

    relay_connectors = [c for m in modules if m.is_relay for c in m.connectors]
    ir_connectors = [c for c, mode in ir_modes.items() if mode in IR_MODES]
    sensor_connectors = [c for c, mode in ir_modes.items() if mode in SENSOR_MODES]

    coordinator = GlobalCacheCoordinator(
        hass,
        entry,
        client,
        relay_connectors + sensor_connectors,
        int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
    )
    await coordinator.async_config_entry_first_refresh()

    codes = IRCodeStore(hass, entry.entry_id)
    await codes.async_load()

    entry.runtime_data = GlobalCacheData(
        client=client,
        coordinator=coordinator,
        codes=codes,
        modules=modules,
        firmware=firmware,
        relay_connectors=relay_connectors,
        ir_connectors=ir_connectors,
        sensor_connectors=sensor_connectors,
        ir_modes=ir_modes,
        device_info=DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Global Caché",
            model=_model_name(entry, modules),
            sw_version=firmware,
            configuration_url=f"http://{host}",
        ),
    )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GlobalCacheConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: GlobalCacheConfigEntry) -> None:
    """Delete learned codes when the entry is removed."""
    await IRCodeStore(hass, entry.entry_id).async_remove()
