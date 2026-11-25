"""IR outputs as remote entities."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    ATTR_TIMEOUT,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GlobalCacheConfigEntry, GlobalCacheData
from .api import GlobalCacheError
from .const import DOMAIN, LEARN_TIMEOUT, SERVICE_STOP_IR
from .entity import GlobalCacheEntity
from .ir import parse_ir_code


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlobalCacheConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        GlobalCacheRemote(entry.entry_id, data, c) for c in data.ir_connectors
    )
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_STOP_IR, {}, "async_stop_ir")


class GlobalCacheRemote(GlobalCacheEntity, RemoteEntity):
    """One IR connector."""

    _attr_supported_features = (
        RemoteEntityFeature.LEARN_COMMAND | RemoteEntityFeature.DELETE_COMMAND
    )

    def __init__(self, entry_id: str, data: GlobalCacheData, connector: str) -> None:
        super().__init__(entry_id, data, connector, "ir", "IR")
        self._entry_id = entry_id
        self._codes = data.codes

    # An IR output has no on/off state, so it is "on" whenever it is reachable.
    @property
    def is_on(self) -> bool:
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        return

    async def async_turn_off(self, **kwargs: Any) -> None:
        return

    def _resolve(self, device: str | None, command: str) -> str:
        if device and (code := self._codes.get(device, command)):
            return code
        try:
            return parse_ir_code(command)
        except ValueError as err:
            if device:
                raise ServiceValidationError(
                    f"Command '{command}' is not stored for device '{device}'"
                ) from err
            raise ServiceValidationError(f"Invalid IR code: {err}") from err

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        device = kwargs.get(ATTR_DEVICE)
        repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        codes = [self._resolve(device, cmd) for cmd in command]
        total = len(codes) * repeats
        sent = 0
        for _ in range(repeats):
            for code in codes:
                try:
                    await self._client.send_ir(self._connector, code)
                except GlobalCacheError as err:
                    raise HomeAssistantError(f"Failed to send IR: {err}") from err
                sent += 1
                if sent < total:
                    await asyncio.sleep(delay)

    async def async_stop_ir(self) -> None:
        """Abort an IR transmission in progress."""
        try:
            await self._client.stop_ir(self._connector)
        except GlobalCacheError as err:
            raise HomeAssistantError(f"Failed to stop IR: {err}") from err

    async def async_learn_command(self, **kwargs: Any) -> None:
        device = kwargs.get(ATTR_DEVICE)
        commands = kwargs.get(ATTR_COMMAND) or []
        timeout = kwargs.get(ATTR_TIMEOUT, LEARN_TIMEOUT)
        if not device:
            raise ServiceValidationError("A device name is required to learn commands")
        if not commands:
            raise ServiceValidationError("At least one command name is required")

        notification_id = f"{DOMAIN}_learn_{self._entry_id}"
        for command in commands:
            persistent_notification.async_create(
                self.hass,
                f"Point your remote at the iTach IR learner and press '{command}'.",
                title="Learning IR command",
                notification_id=notification_id,
            )
            try:
                code = await self._client.learn_ir(timeout)
            except GlobalCacheError as err:
                raise HomeAssistantError(f"Learning '{command}' failed: {err}") from err
            finally:
                persistent_notification.async_dismiss(self.hass, notification_id)
            await self._codes.async_set(device, command, code)

    async def async_delete_command(self, **kwargs: Any) -> None:
        device = kwargs.get(ATTR_DEVICE)
        commands = kwargs.get(ATTR_COMMAND) or []
        if not device:
            raise ServiceValidationError("A device name is required to delete commands")
        for command in commands:
            if not await self._codes.async_delete(device, command):
                raise ServiceValidationError(
                    f"Command '{command}' not found for device '{device}'"
                )
