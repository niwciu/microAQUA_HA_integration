import asyncio
import socket

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .const import CONF_PAYLOAD, DEFAULT_NAME, DEFAULT_PAYLOAD, DEFAULT_PORT, DOMAIN, TIMEOUT


class MicroAQUAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MicroAQUA."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate the user input (e.g., check connection to device)
                await self._test_connection(user_input)
                self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(
                    title=f"{user_input[CONF_NAME]} ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            except (OSError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema({
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Optional(CONF_PAYLOAD, default=DEFAULT_PAYLOAD): str,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def _test_connection(self, user_input):
        """Test if we can connect to the device."""
        await asyncio.to_thread(
            socket.create_connection,
            (user_input[CONF_HOST], user_input[CONF_PORT]),
            TIMEOUT,
        )
