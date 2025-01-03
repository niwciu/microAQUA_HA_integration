import socket
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    host = entry.data.get("host")
    port = entry.data.get("port")
    sensor = TCPSensor(host, port)
    async_add_entities([sensor], update_before_add=True)

class TCPSensor(SensorEntity):
    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._state = None

    @property
    def name(self):
        return "TCP Sensor"

    @property
    def state(self):
        return self._state

    async def async_update(self):
        try:
            with socket.create_connection((self._host, self._port), timeout=5) as conn:
                self._state = "Connected"
        except Exception:
            self._state = "Disconnected"
