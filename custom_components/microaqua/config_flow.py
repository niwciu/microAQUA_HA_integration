from homeassistant import config_entries
import voluptuous as vol

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_PAYLOAD,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_DATA_VALID_SECONDS,
    DEFAULT_NAME,
)

class MicroAQUAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MicroAQUA."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate the user input (e.g., check connection to device)
                await self._test_connection(user_input)
                return self.async_create_entry(title=user_input["ip"], data=user_input)
            except Exception:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Optional("name", default=DEFAULT_NAME): str,
                vol.Required("ip"): str,
                vol.Optional("port", default=DEFAULT_PORT): int,
                vol.Optional("payload", default=DEFAULT_PAYLOAD): str,
                vol.Optional("update_interval", default=DEFAULT_UPDATE_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Optional("timeout", default=DEFAULT_TIMEOUT): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Optional(
                    "data_valid_seconds", default=DEFAULT_DATA_VALID_SECONDS
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def _test_connection(self, user_input):
        """Test if we can connect to the device."""
        import asyncio
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(user_input.get("timeout", DEFAULT_TIMEOUT))
            await asyncio.get_event_loop().run_in_executor(
                None, sock.connect, (user_input["ip"], user_input["port"])
            )
