from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

@callback
def configured_instances(hass):
    return {entry.data["host"] for entry in hass.config_entries.async_entries("tcp_sensor")}

class TCPConfigFlow(config_entries.ConfigFlow, domain="tcp_sensor"):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            host = user_input.get("host")
            port = user_input.get("port")

            if (host, port) in configured_instances(self.hass):
                errors["base"] = "already_configured"
            else:
                return self.async_create_entry(title=f"TCP Sensor ({host}:{port})", data=user_input)

        data_schema = vol.Schema({
            vol.Required("host"): str,
            vol.Required("port"): int,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
