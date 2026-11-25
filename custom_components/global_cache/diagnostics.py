"""Diagnostics for Global Caché iTach."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import GlobalCacheConfigEntry

TO_REDACT = {CONF_HOST, "configuration_url"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GlobalCacheConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data
    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options)}, TO_REDACT
        ),
        "firmware": data.firmware,
        "modules": [
            {"address": m.address, "count": m.count, "type": m.type}
            for m in data.modules
        ],
        "ir_modes": data.ir_modes,
        "states": data.coordinator.data,
        "last_update_success": data.coordinator.last_update_success,
        "learned_device_count": len(data.codes._codes),  # noqa: SLF001
    }
