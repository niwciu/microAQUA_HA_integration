from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from .const import DOMAIN, TIMEOUT, SCAN_INTERVAL

import socket
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor from a config entry."""
    ip = config_entry.data["ip"]
    port = config_entry.data["port"]
    payload = config_entry.data["payload"]

    async_add_entities([MicroAQUASensor(ip, port, payload)], True)


class MicroAQUASensor(SensorEntity):
    """Representation of a MicroAQUA sensor."""

    def __init__(self, ip, port, payload):
        """Initialize the sensor."""
        self._ip = ip
        self._port = port
        self._payload = f"AT+{payload}\r\n"
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"MicroAQUA Sensor {self._ip}"

    @property
    def state(self):
        """Return the current state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"microaqua_{self._ip}_{self._port}"

    async def async_update(self):
        """Fetch new state data from the device."""
        try:
            data = await self._fetch_data()
            self._state = data
        except Exception as e:
            _LOGGER.error("Error updating sensor: %s", e)
            self._state = None

    async def _fetch_data(self):
        """Fetch data from the device."""
        loop = asyncio.get_event_loop()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(TIMEOUT)
            await loop.run_in_executor(None, sock.connect, (self._ip, self._port))
            await loop.run_in_executor(None, sock.sendall, self._payload.encode("utf-8"))
            response = await loop.run_in_executor(None, sock.recv, 1024)
            return response.decode("utf-8").strip()
