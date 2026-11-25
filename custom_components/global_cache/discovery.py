"""Discovery of Global Caché units via their UDP multicast beacons.

Every unit announces itself roughly every 10 s on 239.255.250.250:9131, e.g.

    AMXB<-UUID=GC100_000C1E024239_GlobalCache><-SDKClass=Utility>
    <-Make=GlobalCache><-Model=iTachIP2IR><-Revision=710-1005-05>
    <-Config-URL=http://192.168.1.70><-Status=Ready>

This module deliberately has no Home Assistant imports so it can be unit tested.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
import logging
import re
import socket

_LOGGER = logging.getLogger(__name__)

BEACON_GROUP = "239.255.250.250"
BEACON_PORT = 9131

_FIELD_RE = re.compile(r"<-([^=<>]+)=([^>]*)>")
_MAC_RE = re.compile(r"_([0-9A-Fa-f]{12})(?:_|$)")
_HOST_RE = re.compile(r"^https?://([^/:]+)")


@dataclass(frozen=True)
class DiscoveredUnit:
    """A unit found on the network."""

    mac: str  # 12 upper-case hex digits
    host: str
    model: str | None = None
    revision: str | None = None


def parse_beacon(data: bytes, sender_ip: str) -> DiscoveredUnit | None:
    """Parse a beacon datagram. Returns None for anything that isn't ours."""
    text = data.decode("ascii", errors="ignore")
    if not text.startswith("AMXB"):
        return None
    fields = dict(_FIELD_RE.findall(text))
    make = fields.get("Make", "GlobalCache")
    if make.lower() != "globalcache":
        return None
    mac_match = _MAC_RE.search(fields.get("UUID", ""))
    if not mac_match:
        return None
    host = sender_ip
    if url_match := _HOST_RE.match(fields.get("Config-URL", "")):
        host = url_match.group(1)
    return DiscoveredUnit(
        mac=mac_match.group(1).upper(),
        host=host,
        model=fields.get("Model") or None,
        revision=fields.get("Revision") or None,
    )


class _Listener(asyncio.DatagramProtocol):
    def __init__(self, found: dict[str, DiscoveredUnit]) -> None:
        self._found = found

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if unit := parse_beacon(data, addr[0]):
            self._found[unit.mac] = unit


async def async_scan(
    timeout: float = 11.0,
    *,
    port: int = BEACON_PORT,
    group: str | None = BEACON_GROUP,
    bind_host: str = "",
) -> dict[str, DiscoveredUnit]:
    """Listen for beacons for ``timeout`` seconds. Never raises."""
    found: dict[str, DiscoveredUnit] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with suppress(AttributeError, OSError):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind((bind_host, port))
        if group:
            mreq = socket.inet_aton(group) + socket.inet_aton("0.0.0.0")
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)
    except OSError as err:
        _LOGGER.debug("Beacon discovery unavailable: %s", err)
        sock.close()
        return found

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _Listener(found), sock=sock
    )
    try:
        await asyncio.sleep(timeout)
    finally:
        transport.close()
    return found
