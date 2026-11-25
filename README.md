# Global Caché iTach for Home Assistant

Local-network integration for Global Caché **iTach** units (TCP port 4998).

| Hardware | Entities |
|---|---|
| iTach IP2CC (Ethernet relay) | one `switch` per relay + `global_cache.pulse` service |
| iTach IP2IR (Ethernet IR) | per IR connector: a `remote` and an `infrared` emitter (HA 2026.4+) |
| IR connector set to *sensor* mode | `binary_sensor` |

## Install

1. Copy `custom_components/global_cache` into `config/custom_components/` (or add the repo to HACS as a custom repository) and restart.
2. **Settings → Devices & services → Add integration → Global Caché iTach.**
   The flow listens for ~10 s for units on your network; pick one or choose *Enter address manually*.
   Units may also appear under *Discovered* automatically (DHCP).

Requires Home Assistant 2025.1+. The `infrared` emitters need 2026.4+ and are skipped on older versions.

If discovery finds nothing (Docker bridge networking, VLANs, multicast blocked), use manual entry with a DHCP reservation. Discovered units are tracked by MAC address so later IP changes are followed automatically; for manually added units use ⋮ → *Reconfigure*.

## Options

**Configure** on the integration card: poll interval (default 15 s) and network timeout (default 5 s).

## Relays

```yaml
action: global_cache.pulse     # momentary: gate, garage door, screen
target: { entity_id: switch.itach_relay_3_1 }
data: { duration: 0.5 }
```

## IR

### Using brand integrations (HA 2026.4+)
Integrations built on Home Assistant's `infrared` platform (e.g. LG Infrared) let you choose an emitter during setup. Pick **IR emitter 1:x** from your iTach.

### Using `remote.send_command`
```yaml
# Pronto hex
action: remote.send_command
target: { entity_id: remote.itach_ir_1_1 }
data: { command: "0000 006d 0022 0002 0157 00ac ..." }

# Global Caché sendir string (connector/ID are rewritten for you)
data: { command: "sendir,1:1,1,38000,1,1,342,171,21,21,..." }

# A command you learned
data: { device: tv, command: power }
```
`num_repeats` and `delay_secs` work as usual; `global_cache.stop_ir` aborts a transmission in progress.

### Learning (experimental)
```yaml
action: remote.learn_command
target: { entity_id: remote.itach_ir_1_1 }
data: { device: tv, command: [power, volume_up], timeout: 30 }
```
Hold the original remote at the unit's IR learner and press the button when the notification appears. Needs hardware with an IR learner; otherwise you'll see "learner is not available". Codes are stored in `.storage/`.

## Connector modes
Each iTach IR connector can be IR, IR blaster, sensor or LED lighting (set on the unit's web page). Modes are read at setup — **reload the integration after changing one**. LED-lighting connectors are ignored.

## Not (yet) supported
Serial ports (IP2SL / GC-100), GC-100 relays/IR beyond what `getdevices` reports, Global Connect IR receivers, per-command button entities, sensor push notifications (sensors are polled).

## Development
```
pip install pytest
pytest
```
The tests need no Home Assistant install: they exercise the TCP client against a fake iTach, plus IR conversion and beacon parsing.
