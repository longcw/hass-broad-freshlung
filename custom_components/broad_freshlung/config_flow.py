"""Config flow: log in with the 远大新风 app account."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN
from .api import BroadAuthError, BroadClient, BroadError

SCHEMA = vol.Schema({vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str})


class FreshLungConfigFlow(ConfigFlow, domain=DOMAIN):
    """Validate the account and require at least one Fresh Lung device on it."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = BroadClient(async_get_clientsession(self.hass), user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            try:
                await client.login()
                devices = await client.devices()
            except BroadAuthError:
                errors["base"] = "invalid_auth"
            except BroadError:
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    if self.source == "reauth":
                        return self.async_update_reload_and_abort(self._get_reauth_entry(), data=user_input)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_user()
