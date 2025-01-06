from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, DEFAULT_PORT, DEFAULT_PAYLOAD

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

        data_schema = vol.Schema({
            vol.Required("ip"): str,
            vol.Optional("port", default=DEFAULT_PORT): int,
            vol.Optional("payload", default=DEFAULT_PAYLOAD): str,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def _test_connection(self, user_input):
        """Test if we can connect to the device."""
        import asyncio
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            await asyncio.get_event_loop().run_in_executor(
                None, sock.connect, (user_input["ip"], user_input["port"])
            )
