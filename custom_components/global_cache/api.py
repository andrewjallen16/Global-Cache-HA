"""Async client for the Global Caché iTach TCP API (port 4998)."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
import itertools
import logging
import re

from .ir import parse_ir_code

_LOGGER = logging.getLogger(__name__)

IR_TIMEOUT = 15
IR_BUSY_RETRIES = 4
CONNECT_ATTEMPTS = 2

ERROR_CODES = {
    "001": "Invalid command",
    "002": "Invalid module address",
    "003": "Invalid connector address",
    "004": "Invalid ID value",
    "005": "Invalid frequency value",
    "006": "Invalid repeat count",
    "007": "Invalid offset value",
    "008": "Invalid pulse count",
    "009": "Invalid pulse data",
    "010": "Uneven amount of on/off statements",
    "011": "No carriage return found",
    "012": "Repeat count exceeded",
    "013": "IR command sent to input connector",
    "014": "Blaster command sent to non-blaster connector",
    "015": "No carriage return before buffer full",
    "016": "No carriage return",
    "017": "Bad command syntax",
    "018": "Sensor command sent to non-input connector",
    "019": "Repeated IR transmission failure",
    "020": "Above designated IR command max",
    "021": "Symbol odd boundary",
}

_DEVICE_RE = re.compile(r"^device,(\d+),(\d+)\s+(\S+)", re.IGNORECASE)
_ERR_RE = re.compile(r"^ERR[_ ]?(\S*?),(\d+)", re.IGNORECASE)


class GlobalCacheError(Exception):
    """Base error."""


class GlobalCacheConnectionError(GlobalCacheError):
    """Could not talk to the unit."""


class GlobalCacheCommandError(GlobalCacheError):
    """The unit rejected a command."""


class GlobalCacheBusyError(GlobalCacheCommandError):
    """The IR connector stayed busy."""


@dataclass(frozen=True)
class Module:
    """A module reported by the unit's ``getdevices`` command."""

    address: int
    count: int
    type: str

    @property
    def connectors(self) -> list[str]:
        return [f"{self.address}:{i}" for i in range(1, self.count + 1)]

    @property
    def is_relay(self) -> bool:
        return self.type == "RELAY"

    @property
    def is_ir(self) -> bool:
        return self.type.startswith("IR")


def _describe_error(line: str) -> str:
    match = _ERR_RE.match(line)
    if match and match.group(2) in ERROR_CODES:
        return f"{ERROR_CODES[match.group(2)]} ({line})"
    return line


class _Session:
    """One open TCP connection to the unit."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, timeout: float) -> None:
        self._reader = reader
        self._writer = writer
        self._timeout = timeout

    async def send(
        self, command: str, expect: Callable[[str], bool], timeout: float | None = None
    ) -> list[str]:
        _LOGGER.debug("-> %s", command)
        self._writer.write(f"{command}\r".encode("ascii"))
        await self._writer.drain()
        return await self.read_until(expect, timeout)

    async def read_until(
        self, expect: Callable[[str], bool], timeout: float | None = None
    ) -> list[str]:
        lines: list[str] = []
        async with asyncio.timeout(timeout or self._timeout):
            while True:
                raw = await self._reader.readuntil(b"\r")
                line = raw.decode("ascii", errors="ignore").strip()
                if not line:
                    continue
                _LOGGER.debug("<- %s", line)
                if line.startswith(("ERR", "unknowncommand")):
                    raise GlobalCacheCommandError(_describe_error(line))
                lines.append(line)
                if expect(line):
                    return lines


class GlobalCacheClient:
    """Talks to a single iTach. A new connection is used per operation."""

    def __init__(self, host: str, port: int = 4998, timeout: float = 5) -> None:
        self.host = host
        self.port = port
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._ir_ids = itertools.cycle(range(1, 65536))

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[_Session]:
        async with self._lock:
            last_err: Exception | None = None
            for attempt in range(CONNECT_ATTEMPTS):
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(self.host, self.port), self._timeout
                    )
                    break
                except (OSError, TimeoutError) as err:
                    last_err = err
                    if attempt + 1 < CONNECT_ATTEMPTS:
                        await asyncio.sleep(0.5)
            else:
                raise GlobalCacheConnectionError(
                    f"Cannot connect to {self.host}:{self.port}: {last_err or 'timed out'}"
                ) from last_err
            try:
                yield _Session(reader, writer, self._timeout)
            except (OSError, TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as err:
                raise GlobalCacheConnectionError(
                    f"Communication with {self.host} failed: {err or type(err).__name__}"
                ) from err
            finally:
                writer.close()
                with suppress(OSError, TimeoutError):
                    await asyncio.wait_for(writer.wait_closed(), 2)

    # ------------------------------------------------------------------ info
    async def get_devices(self) -> list[Module]:
        async with self._session() as session:
            lines = await session.send("getdevices", lambda l: l == "endlistdevices")
        modules = []
        for line in lines:
            if match := _DEVICE_RE.match(line):
                modules.append(Module(int(match[1]), int(match[2]), match[3].upper()))
        return modules

    async def get_version(self) -> str:
        """Firmware version string. Also serves as a cheap heartbeat."""
        async with self._session() as session:
            lines = await session.send("getversion", lambda l: True)
        return lines[-1]

    async def get_ir_modes(self, connectors: list[str]) -> dict[str, str]:
        """Return the configured mode of each IR connector (IR, SENSOR, ...)."""
        modes: dict[str, str] = {}
        async with self._session() as session:
            for connector in connectors:
                try:
                    lines = await session.send(
                        f"get_IR,{connector}", lambda l: l.upper().startswith("IR,")
                    )
                    modes[connector] = lines[-1].rsplit(",", 1)[-1].strip().upper()
                except GlobalCacheCommandError:
                    modes[connector] = "IR"  # older firmware without get_IR
        return modes

    # ---------------------------------------------------------------- relays
    @staticmethod
    def _state_from(line: str) -> bool:
        return line.rsplit(",", 1)[-1].strip() == "1"

    async def get_states(self, connectors: list[str]) -> dict[str, bool]:
        states: dict[str, bool] = {}
        async with self._session() as session:
            for connector in connectors:
                prefix = f"state,{connector},"
                lines = await session.send(
                    f"getstate,{connector}", lambda l, p=prefix: l.startswith(p)
                )
                states[connector] = self._state_from(lines[-1])
        return states

    async def set_relay_state(self, connector: str, on: bool) -> bool:
        prefix = f"state,{connector},"
        async with self._session() as session:
            lines = await session.send(
                f"setstate,{connector},{int(on)}", lambda l: l.startswith(prefix)
            )
        return self._state_from(lines[-1])

    # -------------------------------------------------------------------- IR
    async def send_ir(self, connector: str, body: str) -> None:
        """Send a normalised IR body (see ir.py) out of a connector."""
        for attempt in range(IR_BUSY_RETRIES):
            ir_id = next(self._ir_ids)
            async with self._session() as session:
                lines = await session.send(
                    f"sendir,{connector},{ir_id},{body}",
                    lambda l: l.lower().startswith(("completeir", "busyir")),
                    timeout=IR_TIMEOUT,
                )
            if lines[-1].lower().startswith("completeir"):
                return
            await asyncio.sleep(0.3 * (attempt + 1))
        raise GlobalCacheBusyError(f"IR connector {connector} stayed busy")

    async def stop_ir(self, connector: str) -> None:
        """Abort an IR transmission in progress on a connector."""
        async with self._session() as session:
            await session.send(
                f"stopir,{connector}", lambda l: l.lower().startswith("stopir")
            )

    async def learn_ir(self, timeout: float = 30) -> str:
        """Enable the IR learner and wait for a code. Returns a normalised body."""
        async with self._session() as session:
            lines = await session.send("get_IRL", lambda l: l.startswith("IR Learner"))
            if "Unavailable" in lines[-1]:
                raise GlobalCacheError("The IR learner is not available on this unit")
            try:
                try:
                    lines = await session.read_until(
                        lambda l: l.lower().startswith("sendir"), timeout
                    )
                except TimeoutError:
                    raise GlobalCacheError("Timed out waiting for an IR signal") from None
                try:
                    return parse_ir_code(lines[-1])
                except ValueError as err:
                    raise GlobalCacheError(f"Learned an unusable code: {err}") from err
            finally:
                with suppress(GlobalCacheError, TimeoutError, OSError):
                    await session.send(
                        "stop_IRL", lambda l: l.startswith("IR Learner Disabled")
                    )
