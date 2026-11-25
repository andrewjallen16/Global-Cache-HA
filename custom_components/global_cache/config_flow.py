"""Config flow for Global Caché iTach."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .api import GlobalCacheClient, GlobalCacheConnectionError, GlobalCacheError
from .const import (
    CONF_MODEL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DISCOVERY_SECONDS,
    DOMAIN,
)
from .discovery import DiscoveredUnit, async_scan

_LOGGER = logging.getLogger(__name__)
_MANUAL = "manual"
_MAC_RE = re.compile(r"^[0-9A-F]{12}$")


def _norm_mac(mac: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", mac).upper()


class GlobalCacheConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._scan_task: asyncio.Task | None = None
        self._discovered: dict[str, DiscoveredUnit] = {}
        self._dhcp_unit: DiscoveredUnit | None = None
        self._prefill_host: str = ""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> GlobalCacheOptionsFlow:
        return GlobalCacheOptionsFlow()

    @callback
    def async_remove(self) -> None:
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()

    # ------------------------------------------------------------- helpers
    @staticmethod
    async def _probe(host: str, port: int) -> str | None:
        """Return an error key, or None if the unit looks good."""
        try:
            modules = await GlobalCacheClient(host, port).get_devices()
        except GlobalCacheConnectionError:
            return "cannot_connect"
        except GlobalCacheError:
            return "unknown"
        if not any(m.is_relay or m.is_ir for m in modules):
            return "no_supported_modules"
        return None

    @callback
    def _adopt_legacy_entries(self, mac: str, host: str) -> None:
        """v0.1 entries used the host as unique id; upgrade them to the MAC."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.unique_id and entry.unique_id.lower() == host.lower():
                self.hass.config_entries.async_update_entry(entry, unique_id=mac)

    async def _async_scan(self) -> None:
        try:
            self._discovered = await async_scan(DISCOVERY_SECONDS)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Beacon scan failed", exc_info=True)
            self._discovered = {}

    def _unit_for_host(self, host: str) -> DiscoveredUnit | None:
        return next((u for u in self._discovered.values() if u.host == host), None)

    # --------------------------------------------------------- user: scan
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._scan_task is None:
            self._scan_task = self.hass.async_create_task(self._async_scan())
        if not self._scan_task.done():
            return self.async_show_progress(
                progress_action="scan", progress_task=self._scan_task
            )
        return self.async_show_progress_done(next_step_id="pick")

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        for unit in self._discovered.values():
            self._adopt_legacy_entries(unit.mac, unit.host)
        configured = {e.unique_id for e in self._async_current_entries()}
        available = {m: u for m, u in self._discovered.items() if m not in configured}

        if not available:
            return await self.async_step_manual()

        if user_input is not None:
            choice = user_input["unit"]
            if choice == _MANUAL:
                return await self.async_step_manual()
            unit = available[choice]
            return await self.async_step_manual(
                {CONF_HOST: unit.host, CONF_PORT: DEFAULT_PORT}
            )

        options = [
            SelectOptionDict(
                value=mac,
                label=f"{(u.model or 'iTach')} – {u.host}",
            )
            for mac, u in available.items()
        ]
        options.append(SelectOptionDict(value=_MANUAL, label="Enter address manually"))
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {vol.Required("unit"): SelectSelector(SelectSelectorConfig(options=options))}
            ),
        )

    # ------------------------------------------------------------- manual
    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            unit = self._unit_for_host(host)
            if unit:
                self._adopt_legacy_entries(unit.mac, host)
            await self.async_set_unique_id(unit.mac if unit else host.lower())
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            if (error := await self._probe(host, port)) is None:
                title = user_input.get(CONF_NAME) or (
                    f"{unit.model} {host}" if unit and unit.model else f"iTach {host}"
                )
                data: dict[str, Any] = {CONF_HOST: host, CONF_PORT: port}
                if unit and unit.model:
                    data[CONF_MODEL] = unit.model
                return self.async_create_entry(title=title, data=data)
            errors["base"] = error
            self._prefill_host = host

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._prefill_host): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

    # --------------------------------------------------------------- DHCP
    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        mac = _norm_mac(discovery_info.macaddress)
        host = discovery_info.ip
        self._adopt_legacy_entries(mac, host)
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        if await self._probe(host, DEFAULT_PORT) is not None:
            return self.async_abort(reason="cannot_connect")

        self._dhcp_unit = DiscoveredUnit(mac=mac, host=host)
        self.context["title_placeholders"] = {"name": f"iTach {host}"}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._dhcp_unit is not None
        host = self._dhcp_unit.host
        if user_input is not None:
            return self.async_create_entry(
                title=f"iTach {host}", data={CONF_HOST: host, CONF_PORT: DEFAULT_PORT}
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"host": host}
        )

    # ---------------------------------------------------------- reconfigure
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            if (error := await self._probe(host, port)) is None:
                kwargs: dict[str, Any] = {}
                if not _MAC_RE.match(entry.unique_id or ""):
                    kwargs["unique_id"] = host.lower()  # legacy host-based id
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_HOST: host, CONF_PORT: port}, **kwargs
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                    vol.Optional(
                        CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                }
            ),
            errors=errors,
        )


class GlobalCacheOptionsFlow(OptionsFlow):
    """Polling interval and network timeout."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={k: int(v) for k, v in user_input.items()}
            )
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=5, max=600, step=1,
                            unit_of_measurement="s", mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_TIMEOUT, default=opts.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=2, max=30, step=1,
                            unit_of_measurement="s", mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
