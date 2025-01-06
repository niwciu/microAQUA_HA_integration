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
        self._expected_prefix = f"AT+{payload}="
        self._state = None
        self._error_count = 0  # Licznik błędów

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"MicroAQUA {self._ip}"

    @property
    def state(self):
        """Return the current state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"microaqua_{self._ip}"

    async def async_update(self):
        """Fetch new state data from the device."""
        try:
            data = await self._fetch_data()
            valid_data = self._validate_response(data)

            if valid_data:
                self._state = valid_data
                self._error_count = 0  # Zresetuj licznik błędów po poprawnej odpowiedzi
            else:
                _LOGGER.warning("Invalid response from device: %s", data)
                self._handle_error()

        except socket.timeout:
            _LOGGER.warning("Timeout while connecting to %s:%s", self._ip, self._port)
            self._handle_error()

        except (socket.error, socket.gaierror) as e:
            _LOGGER.error("TCP connection error: %s", e)
            self._handle_error()

        except Exception as e:
            _LOGGER.error("Unexpected error: %s", e)
            self._handle_error()


    async def _fetch_data(self):
        """Fetch data from the device."""
        loop = asyncio.get_event_loop()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(TIMEOUT)  # Ustawienie limitu czasu
                await loop.run_in_executor(None, sock.connect, (self._ip, self._port))
                await loop.run_in_executor(None, sock.sendall, self._payload.encode("utf-8"))
                response = await loop.run_in_executor(None, sock.recv, 1024)
                return response.decode("utf-8").strip()
        except Exception as e:
            raise e  # Przekazanie błędu do `async_update`


    def _validate_response(self, data):
        """Validate and parse the response from the device."""
        if self._expected_prefix in data:
            # Usuń ewentualne "śmieci" przed właściwą odpowiedzią
            start_index = data.find(self._expected_prefix)
            return data[start_index + len(self._expected_prefix):]
        return None

    def _handle_error(self):
        """Handle errors and increment error count."""
        self._error_count += 1
        if self._error_count >= 5:
            self._state = "unknown"  # Ustaw stan encji na unknown po 5 błędach
