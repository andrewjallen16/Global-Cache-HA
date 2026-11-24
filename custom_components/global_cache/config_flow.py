"""Config flow for Global Caché iTach."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .api import GlobalCacheClient, GlobalCacheConnectionError, GlobalCacheError
from .const import DEFAULT_PORT, DOMAIN


class GlobalCacheConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def _validate(self, host: str, port: int) -> str | None:
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            await self.async_set_unique_id(host.lower())
            self._abort_if_unique_id_configured()
            if (error := await self._validate(host, port)) is None:
                title = user_input.get(CONF_NAME) or f"iTach {host}"
                return self.async_create_entry(
                    title=title, data={CONF_HOST: host, CONF_PORT: port}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            if (error := await self._validate(host, port)) is None:
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=host.lower(),
                    data={**entry.data, CONF_HOST: host, CONF_PORT: port},
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
