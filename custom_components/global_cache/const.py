"""Constants for the Global Caché iTach integration."""
from __future__ import annotations

from importlib.util import find_spec

from homeassistant.const import Platform

DOMAIN = "global_cache"

DEFAULT_PORT = 4998
DEFAULT_SCAN_INTERVAL = 15  # seconds
DEFAULT_TIMEOUT = 5  # seconds
LEARN_TIMEOUT = 30
STORAGE_VERSION = 1
DISCOVERY_SECONDS = 11  # iTach beacons go out every ~10 s

CONF_MODEL = "model"

# Connector modes reported by `get_IR`
IR_MODES = frozenset({"IR", "IR_BLASTER"})
SENSOR_MODES = frozenset({"SENSOR", "SENSOR_NOTIFY"})

SERVICE_PULSE = "pulse"
SERVICE_STOP_IR = "stop_ir"
ATTR_DURATION = "duration"

PLATFORMS: list[Platform | str] = [
    Platform.SWITCH,
    Platform.REMOTE,
    Platform.BINARY_SENSOR,
]

# The native `infrared` entity platform arrived in Home Assistant 2026.4.
try:
    if find_spec("homeassistant.components.infrared") is not None:
        PLATFORMS.append("infrared")
except (ImportError, ValueError):  # pragma: no cover
    pass
