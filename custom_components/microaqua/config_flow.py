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

async def _async_test_connection(user_input):
    """Test if we can connect to the device."""
    import asyncio
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(user_input.get("timeout", DEFAULT_TIMEOUT))
        await asyncio.get_event_loop().run_in_executor(
            None, sock.connect, (user_input["ip"], user_input["port"])
        )


class MicroAQUAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MicroAQUA."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate the user input (e.g., check connection to device)
                await _async_test_connection(user_input)
                title = user_input.get("name") or user_input["ip"]
                return self.async_create_entry(title=title, data=user_input)
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

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry):
        return MicroAQUAOptionsFlow(config_entry)


class MicroAQUAOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for MicroAQUA."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                await _async_test_connection(user_input)
                title = user_input.get("name") or user_input["ip"]
                self.hass.config_entries.async_update_entry(
                    self.config_entry, title=title
                )
                return self.async_create_entry(title="", data=user_input)
            except Exception:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Optional(
                    "name",
                    default=self.config_entry.options.get(
                        "name",
                        self.config_entry.data.get("name", DEFAULT_NAME),
                    ),
                ): str,
                vol.Required(
                    "ip",
                    default=self.config_entry.options.get(
                        "ip", self.config_entry.data.get("ip")
                    ),
                ): str,
                vol.Optional(
                    "port",
                    default=self.config_entry.options.get(
                        "port",
                        self.config_entry.data.get("port", DEFAULT_PORT),
                    ),
                ): int,
                vol.Optional(
                    "payload",
                    default=self.config_entry.options.get(
                        "payload",
                        self.config_entry.data.get("payload", DEFAULT_PAYLOAD),
                    ),
                ): str,
                vol.Optional(
                    "update_interval",
                    default=self.config_entry.options.get(
                        "update_interval",
                        self.config_entry.data.get(
                            "update_interval", DEFAULT_UPDATE_INTERVAL
                        ),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "timeout",
                    default=self.config_entry.options.get(
                        "timeout",
                        self.config_entry.data.get("timeout", DEFAULT_TIMEOUT),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "data_valid_seconds",
                    default=self.config_entry.options.get(
                        "data_valid_seconds",
                        self.config_entry.data.get(
                            "data_valid_seconds", DEFAULT_DATA_VALID_SECONDS
                        ),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )
