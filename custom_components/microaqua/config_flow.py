from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_NAME, CONF_PAYLOAD, CONF_TIMEOUT, CONF_SCAN_INTERVAL, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_PAYLOAD, DEFAULT_TIMEOUT, DEFAULT_SCAN_INTERVAL

class MyTCPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for My TCP Sensor."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Optional(CONF_PAYLOAD, default=DEFAULT_PAYLOAD): str,
                    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): int,  # Nowa opcja
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,  # Nowa opcja
                })
            )

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
