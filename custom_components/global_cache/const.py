"""Constants for the Global Caché iTach integration."""
from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "global_cache"
DEFAULT_PORT = 4998
PLATFORMS = [Platform.SWITCH, Platform.REMOTE]
SCAN_INTERVAL = timedelta(seconds=15)
LEARN_TIMEOUT = 30
STORAGE_VERSION = 1

SERVICE_PULSE = "pulse"
ATTR_DURATION = "duration"
