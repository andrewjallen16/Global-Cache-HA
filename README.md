# Global Caché iTach for Home Assistant

Custom integration for Global Caché **iTach** units over the local network (TCP port 4998).

| Hardware | Entities |
|---|---|
| iTach IP2CC (Ethernet relay) | one `switch` per relay, plus a `global_cache.pulse` service |
| iTach IP2IR (Ethernet IR) | one `remote` per IR connector |

Units are polled every 15 s for relay state. IR is send-only (optionally learn, see below).

## Install

1. Copy `custom_components/global_cache` into your HA `config/custom_components/` folder
   (or add this repo to HACS as a custom repository).
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → "Global Caché iTach"**, enter the unit's IP.
   Repeat for each unit. Use DHCP reservations so IPs don't change; if one does, use *Reconfigure*.

Requires Home Assistant 2024.12 or newer.

## Relays

Each relay is a normal switch. For momentary devices (garage door, projector screen, gate):

```yaml
action: global_cache.pulse
target:
  entity_id: switch.itach_relay_1_1
data:
  duration: 0.5
```

## IR

`remote.send_command` accepts any of these code formats (use whichever you already have):

```yaml
# Pronto hex
action: remote.send_command
target: { entity_id: remote.itach_ir_1_1 }
data:
  command: "0000 006d 0022 0002 0157 00ac 0015 0015 ..."

# Global Caché sendir string (connector/ID fields are rewritten for you)
data:
  command: "sendir,1:1,1,38000,1,1,342,171,21,21,21,64,..."

# A name you learned earlier
data:
  device: tv
  command: power
```

Optional `num_repeats` and `delay_secs` work as usual and accept multiple commands in a list.

### Learning (experimental)

```yaml
action: remote.learn_command
target: { entity_id: remote.itach_ir_1_1 }
data:
  device: tv
  command: [power, volume_up]
  timeout: 30
```

Point the original remote at the unit's IR learner window; a notification prompts you for each command. Learned codes are stored in `.storage/` and used with `remote.send_command` + `device`. This only works on units that have an IR learner; otherwise you'll get "learner is not available". `remote.delete_command` removes stored codes.

## Notes

- Each IR connector on an iTach can be configured as IR out, IR blaster, sensor, etc. via the unit's web page. Only connectors set to IR output will transmit.
- Commands are serialized per unit; if a connector reports busy, sends are retried automatically.
- Enable debug logs with `logger: logs: custom_components.global_cache: debug` to see the raw API traffic.
