from __future__ import annotations

import asyncio
import logging
import socket
from datetime import datetime

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN, TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor from a config entry."""
    ip = config_entry.data["ip"]
    port = config_entry.data["port"]
    payload = config_entry.data["payload"]
    name = config_entry.data["name"]

    # Główny sensor (trzyma połączenie i parsuje dane)
    sensor = MicroAQUASensor(hass, ip, port, payload, name)

    async_add_entities(
        [
            sensor,
            PHSensor(sensor),
            TempSensor(sensor, "Temp 1", 1),
            TempSensor(sensor, "Temp 2", 2),
            TempSensor(sensor, "Temp 3", 3),
            TempSensor(sensor, "Temp 4", 4),
            LED(sensor, 1),
            LED(sensor, 2),
            LED(sensor, 3),
            LED(sensor, 4),
            LastUpdateTime(sensor),
            TempSensor(sensor, "Alarm Temp min", 5, "mdi:thermometer-alert"),
            TempSensor(sensor, "Alarm Temp max", 6, "mdi:thermometer-alert"),
            TempSensor(sensor, "Alarm Temp histeresis", 7, "mdi:thermometer-alert"),
        ],
        True,
    )


class MicroAQUASensor(SensorEntity):
    """Representation of a MicroAQUA sensor (master entity)."""

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
        self._temp_values = [None] * 7
        self._led = [None] * 4
        self._last_update_time = None

        self._error_count = 0
# ToDo
        # self._fan_driver_mode # parsed_data[5]
        # self._fan_speed # parsed_data[6]
        # self._thermoreg_asssigned_socket # parsed_data[7]
        # self._thermoreg_socket_state # parsed_data[8]
        # self._ph_mether_asssigned_CO2_socket # parsed_data[9]
        # self._ph_mether_CO2_socket_state # parsed_data[10]
        # self._ph_mether_asssigned_O2_socket # parsed_data[11]
        # self._ph_mether_O2_socket_state # parsed_data[12]
        # self._regulation_off_marker # parsed_data[17]
        # self._alarm_temp_histeresis # parsed_data[22]
        # self._alarm_ph_min # parsed_data[23]
        # self._alarm_ph_max # parsed_data[24]
        # self._alarm_ph_histeresis # parsed_data[25] 
        # Done
        # self._alarm_register # parsed_data[18]
        # self._alarm_temp_min # parsed_data[20]
        # self._alarm_temp_max # parsed_data[21]
        
        # Device registry info (to tworzy urządzenie)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._ip)},
            "name": f"{self._name} {self._ip} {self._port}",
            "manufacturer": "microAQUA",
            "model": "microAQUA",
        }

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
        # Jeśli entity_id nie jest ustawione, pomiń (zostawiam jak było)
        if not self.entity_id:
            _LOGGER.debug("Entity ID is not set. Skipping update.")
            return

        try:
            data = await self._fetch_data()
            valid_data = self._validate_response(data)

            if valid_data:
                parsed_data = valid_data.split(";")

                self._ph_value = self._parse_ph(parsed_data[0])

                # Temperatury: 1..4 oraz alarmowe 20..22 => razem 7 wartości
                self._temp_values = [
                    self._parse_temp(temp)
                    for temp in (parsed_data[1:5] + parsed_data[20:23])
                ]

                self._led = [self._parse_led(led) for led in parsed_data[13:17]]

                self._last_update_time = self._parse_time_stamp(parsed_data[19])

                self._state = "updated"
                self._error_count = 0
                self.async_write_ha_state()
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

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(TIMEOUT)
            await loop.run_in_executor(None, sock.connect, (self._ip, self._port))
            await loop.run_in_executor(None, sock.sendall, self._payload.encode("utf-8"))
            response = await loop.run_in_executor(None, sock.recv, 1024)
            return response.decode("utf-8").strip()

    def _validate_response(self, data: str):
        """Validate and parse the response from the device."""
        if self._expected_prefix in data:
            start_index = data.find(self._expected_prefix)
            return data[start_index + len(self._expected_prefix) :]
        return None

    def _handle_error(self):
        """Handle errors and increment error count."""
        self._error_count += 1
        if self._error_count >= 5:
            self._state = "unknown"
            self.async_write_ha_state()

    @staticmethod
    def _parse_ph(value: str):
        try:
            return float(value) / 100.0
        except ValueError:
            return "unknown"

    @staticmethod
    def _parse_temp(value: str):
        try:
            return float(value) / 10.0
        except ValueError:
            return "unknown"

    @staticmethod
    def _parse_led(value: str):
        try:
            return int(value)
        except ValueError:
            return "unknown"

    @staticmethod
    def _parse_time_stamp(value: str):
        try:
            time_obj = datetime.strptime(value, "%H:%M:%S")
            return time_obj.time()
        except ValueError:
            return "unknown"


# --- Encje podrzędne (WSZYSTKIE mają device_info) ---


class PHSensor(SensorEntity):
    """Representation of pH value from microAQUA Sensor."""

    def __init__(self, sensor: MicroAQUASensor):
        self._sensor = sensor
        self._unit_of_measurement = "pH"

    @property
    def device_info(self):
        # KLUCZOWE: przypina encję do urządzenia
        return self._sensor.device_info

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
        return f"{self._sensor.unique_id}_ph"


class TempSensor(SensorEntity):
    """Representation of a temperature value from microAQUA Sensor."""

    def __init__(
        self,
        sensor: MicroAQUASensor,
        name: str,
        index: int,
        icon: str = "mdi:thermometer",
    ):
        self._sensor = sensor
        self._index = index
        self._unit_of_measurement = "°C"
        self._name = name
        self._icon = icon

    @property
    def device_info(self):
        return self._sensor.device_info

    @property
    def name(self):
        return f"{self._sensor.name} {self._name}"

    @property
    def state(self):
        return self._sensor._temp_values[self._index - 1]

    @property
    def icon(self):
        return self._icon

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    @property
    def unique_id(self):
        return f"{self._sensor.unique_id}_temp_{self._index}"


class LED(SensorEntity):
    """Representation of a LED value from microAQUA Sensor."""

    def __init__(self, sensor: MicroAQUASensor, index: int):
        self._sensor = sensor
        self._index = index
        self._unit_of_measurement = "%"

    @property
    def device_info(self):
        return self._sensor.device_info

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
        return f"{self._sensor.unique_id}_led_{self._index}"


class LastUpdateTime(SensorEntity):
    """Representation of LastUpdateTime value from microAQUA Sensor."""

    def __init__(self, sensor: MicroAQUASensor):
        self._sensor = sensor

    @property
    def device_info(self):
        return self._sensor.device_info

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
        return f"{self._sensor.unique_id}_last_update_time"
