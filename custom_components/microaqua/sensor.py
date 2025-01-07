from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.helpers.entity import Entity
from datetime import datetime
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
    name = config_entry.data["name"]

    # Tworzenie głównego sensora
    sensor = MicroAQUASensor(hass, ip, port, payload, name)
    async_add_entities(
        [
            sensor,
            PHSensor(sensor),
            TempSensor(sensor, 1),
            TempSensor(sensor, 2),
            TempSensor(sensor, 3),
            TempSensor(sensor, 4),
            LED(sensor, 1),
            LED(sensor, 2),
            LED(sensor, 3),
            LED(sensor, 4),
            LastUpdateTime(sensor),
        ],
        True,
    )

class MicroAQUASensor(SensorEntity):
    """Representation of a MicroAQUA sensor."""

    def __init__(self, hass, ip, port, payload, name):
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._ip = ip
        self._port = port
        self._payload = f"AT+{payload}\r\n"
        self._expected_prefix = f"AT+{payload}="
        self._state = None
        self._ph_value = None
        self._temp_values = [None] * 4
        self._led = [None] * 4
        self._last_update_time = None
        self._error_count = 0  # Licznik błędów

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._ip)},  # Identifiers umożliwiają automatyczną rejestrację urządzenia
            "name": f"{self._name} {self._ip} {self._port}",
            "manufacturer": "microAQUA",
            "model": "microAQUA"
        }
        # self.entity_id = generate_entity_id("sensor.{}", "my_awesome_sensor_id")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the current state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._name}_{self._ip}"

    async def async_update(self):
        """Fetch new state data from the device."""
            # Sprawdzenie, czy entity_id jest ustawione
        if not self.entity_id:
            _LOGGER.debug("Entity ID is not set. Skipping update.")
            return
        try:
            data = await self._fetch_data()
            valid_data = self._validate_response(data)

            if valid_data:
                # Parsowanie danych na różne encje
                parsed_data = valid_data.split(";")
                self._ph_value = self._parse_ph(parsed_data[0])  # pH
                self._temp_values = [self._parse_temp(temp) for temp in parsed_data[1:5]]  # Temperatury
                self._led = [self._parse_led(led) for led in parsed_data[13:17]]  # LEDy
                self._last_update_time = self._parse_time_stamp(parsed_data[19])  # LAst Update Time

                self._state = "updated"  # Stan sensora aktualny
                self._error_count = 0  # Zresetuj licznik błędów po poprawnej odpowiedzi
                self.async_write_ha_state()  # Aktualizacja stanu encji w Home Assistant
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
            start_index = data.find(self._expected_prefix)
            return data[start_index + len(self._expected_prefix):]
        return None

    def _handle_error(self):
        """Handle errors and increment error count."""
        self._error_count += 1
        if self._error_count >= 5:
            self._state = "unknown"  # Ustaw stan sensora na unknown po 5 błędach
            self.async_write_ha_state()  # Aktualizacja stanu encji w Home Assistant

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

    def _parse_led(self, value):
        """Parse led brightness value."""
        try:
            return int(value)
        except ValueError:
            return "unknown"
        
    def _parse_time_stamp(self, value):
        """Parse time_stamp value."""
        try:
            # Convert to datetime object
            time_obj = datetime.strptime(value, "%H:%M:%S")
            return time_obj.time()
        except ValueError:
            return "unknown"
        
        


# Klasy dla sensora pH, temperatury i LED

class PHSensor(Entity):
    """Representation of pH value from microAQUA Sensor."""

    def __init__(self, sensor):
        self._sensor = sensor
        self._unit_of_measurement = "pH"

    @property
    def name(self):
        return f"{self._sensor.name} pH"

    @property
    def state(self):
        return self._sensor._ph_value

    @property
    def icon(self):
        return "mdi:ph"

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement
    
    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._sensor.name}_ph"


class TempSensor(Entity):
    """Representation of a temperature value from microAQUA Sensor."""

    def __init__(self, sensor, index):
        self._sensor = sensor
        self._index = index
        self._unit_of_measurement = "°C"

    @property
    def name(self):
        return f"{self._sensor.name} Temp {self._index}"

    @property
    def state(self):
        return self._sensor._temp_values[self._index - 1]

    @property
    def icon(self):
        return "mdi:thermometer"

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement
    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._sensor.name}_tem_{self._index}"


class LED(Entity):
    """Representation of a LED value from microAQUA Sensor."""

    def __init__(self, sensor, index):
        self._sensor = sensor
        self._index = index
        self._unit_of_measurement = "%"

    @property
    def name(self):
        return f"{self._sensor.name} LED {self._index}"

    @property
    def state(self):
        return self._sensor._led[self._index - 1]

    @property
    def icon(self):
        return "mdi:led-on"

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement
    
    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._sensor.name}_led_{self._index}"
    
class LastUpdateTime(Entity):
    """Representation of LastUpdateTime value from microAQUA Sensor."""

    def __init__(self, sensor):
        self._sensor = sensor
        

    @property
    def name(self):
        return f"{self._sensor.name} Last Update Time"

    @property
    def state(self):
        return self._sensor._last_update_time

    @property
    def icon(self):
        return "mdi:update"
    
    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._sensor.name}_last_update_time"
