import socket
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME, CONF_PAYLOAD, CONF_TIMEOUT, CONF_SCAN_INTERVAL
import asyncio

_LOGGER = logging.getLogger(__name__)

class TCPSensor(SensorEntity):
    """Representation of a TCP Sensor."""

    def __init__(self, name, host, port, payload, timeout, scan_interval):
        self._name = name
        self._host = host
        self._port = port
        self._payload = payload + "\r\n"
        self._state = None
        self._timeout = timeout
        self._scan_interval = scan_interval
        self._response = None

        # Przechowywanie wartości pH i temperatur
        self._ph_value = "unknown"
        self._temp_values = ["unknown", "unknown", "unknown", "unknown"]

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        # Ustawienie stanu sensora na podstawie całej odpowiedzi
        return self._state

    async def async_update(self):
        """Fetch new state data for the sensor."""
        _LOGGER.debug("Running async_update for sensor: %s", self._name)

        try:
            response = await asyncio.to_thread(self._fetch_data)
            self._parse_response(response)

        except Exception as e:
            _LOGGER.error("Error during TCP communication: %s", str(e))
            self._state = "unknown"
            self._ph_value = "unknown"
            self._temp_values = ["unknown", "unknown", "unknown", "unknown"]

    def _fetch_data(self):
        """Fetch the TCP response synchronously."""
        with socket.create_connection((self._host, self._port), timeout=self._timeout) as sock:
            payload_with_prefix = "AT+" + self._payload
            _LOGGER.debug("Sending payload: %s", payload_with_prefix)
            sock.sendall(payload_with_prefix.encode("utf-8"))
            response = sock.recv(1024).decode("utf-8")
        return response

    def _parse_response(self, response):
        """Parse the response and update sensor values."""
        _LOGGER.debug("Parsing response: %s", response)

        if response.startswith(f"AT+{self._payload.strip()}="):
            response_data = response[len(f"AT+{self._payload.strip()}="):]
            _LOGGER.debug("Response after stripping prefix: %s", response_data)
            values = response_data.split(";")

            if len(values) >= 5:
                self._ph_value = self._parse_ph(values[0])
                self._temp_values = [self._parse_temp(values[i]) for i in range(1, 5)]
                self._state = self._ph_value
                _LOGGER.debug("Parsed values - pH: %s, Temps: %s", self._ph_value, self._temp_values)
            else:
                self._state = "unknown"
                self._ph_value = "unknown"
                self._temp_values = ["unknown", "unknown", "unknown", "unknown"]
                _LOGGER.warning("Response does not contain enough data. Setting values to unknown.")
        else:
            _LOGGER.error("Invalid token in response: %s", response)
            self._state = "unknown"
            self._ph_value = "unknown"
            self._temp_values = ["unknown", "unknown", "unknown", "unknown"]

    def _parse_ph(self, value):
        """Parse pH value."""
        try:
            return float(value) / 100.0
        except ValueError:
            return "unknown"

    def _parse_temp(self, value):
        """Parse temperature value."""
        try:
            return float(value) / 10.0
        except ValueError:
            return "unknown"

    def add_entities(self, async_add_entities):
        """Add pH and temperature sensors as entities."""
        ph_sensor = PHSensor(self)
        temp_sensors = [TempSensor(self, i) for i in range(1, 5)]
        async_add_entities([ph_sensor, *temp_sensors])


class PHSensor(Entity):
    """Representation of pH value from TCP Sensor."""

    def __init__(self, tcp_sensor):
        self._tcp_sensor = tcp_sensor
        self._unit_of_measurement = "pH"

    @property
    def name(self):
        return f"{self._tcp_sensor.name} pH"

    @property
    def state(self):
        return self._tcp_sensor._ph_value

    @property
    def icon(self):
        return "mdi:ph"

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    async def async_update(self):
        await self._tcp_sensor.async_update()


class TempSensor(Entity):
    """Representation of a temperature value from TCP Sensor."""

    def __init__(self, tcp_sensor, index):
        self._tcp_sensor = tcp_sensor
        self._index = index
        self._unit_of_measurement = "°C"

    @property
    def name(self):
        return f"{self._tcp_sensor.name} Temp {self._index}"

    @property
    def state(self):
        return self._tcp_sensor._temp_values[self._index - 1]

    @property
    def icon(self):
        return "mdi:thermometer"

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    async def async_update(self):
        await self._tcp_sensor.async_update()


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the TCP sensor platform."""
    _LOGGER.debug("Setting up TCP Sensor")

    data = config_entry.data
    _LOGGER.debug("Config data: %s", data)

    tcp_sensor = TCPSensor(
        data["name"], 
        data["host"], 
        data["port"], 
        data["payload"], 
        data["timeout"], 
        data["scan_interval"]
    )

    tcp_sensor.add_entities(async_add_entities)
    _LOGGER.debug("TCP Sensors added")
