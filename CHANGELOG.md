# Changelog

## 0.2.0

**Discovery & setup**
- Auto-discovery: UDP multicast beacons (239.255.250.250:9131) and DHCP (`GlobalCache_*` hostname / 00:0C:1E OUI).
  "Add integration" now scans for ~10 s and lets you pick a unit, or enter an address manually.
- Units are identified by MAC address, so DHCP IP changes are followed automatically.
  v0.1 entries (host-based ids) are upgraded in place the first time the unit is discovered.
- Real model name (e.g. iTach IP2IR) is taken from the beacon.
- Options flow: poll interval and network timeout.

**New entities / services**
- Native Home Assistant `infrared` emitter per IR connector (HA 2026.4+), so brand integrations like LG Infrared can use an iTach. Skipped automatically on older HA.
- IR connectors configured as contact **sensors** become `binary_sensor`s; only connectors in IR / IR-blaster mode get remotes and emitters (read via `get_IR`).
- `global_cache.stop_ir` service.
- Diagnostics download (host redacted).

**Reliability**
- Every entity (including IR-only units) now goes unavailable when the unit is unreachable (heartbeat poll via `getversion`).
- Connection attempts are retried once.
- Test suite against a fake iTach server + CI (hassfest, HACS, pytest).

**Breaking / notes**
- Minimum Home Assistant is now 2025.1.
- Connector modes are read at setup; after changing a connector's mode on the unit's web page, reload the integration.

## 0.1.0
- Initial release: relay switches, IR remotes, Pronto/sendir support, learning.
