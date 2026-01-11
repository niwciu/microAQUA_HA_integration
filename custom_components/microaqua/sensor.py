from __future__ import annotations

import asyncio
import logging
import re
import socket
from datetime import datetime
from typing import Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import DOMAIN, TIMEOUT, SCAN_INTERVAL as DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform from a config entry."""
    ip = config_entry.data["ip"]
    port = config_entry.data["port"]
    payload = config_entry.data["payload"]
    name = config_entry.data["name"]

    master = MicroAQUASensor(hass, ip, port, payload, name)

    # Udostępnij mastera innym platformom (switch/number) przez hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    hass.data[DOMAIN][config_entry.entry_id]["master"] = master

    async_add_entities(
        [
            master,

            # --- podstawowe ---
            DataValidSensor(master),
            DataAgeSensor(master),
            PHSensor(master),
            TempSensor(master, "Czujnik Temperatury 1", 1, "hass:thermometer"),
            TempSensor(master, "Czujnik Temperatury 2", 2, "hass:thermometer"),
            TempSensor(master, "Czujnik Temperatury 3", 3, "hass:thermometer"),
            TempSensor(master, "Czujnik Temperatury 4", 4, "hass:thermometer"),
            LEDSensor(master, 1),
            LEDSensor(master, 2),
            LEDSensor(master, 3),
            LEDSensor(master, 4),
            LastUpdateTime(master),

            # --- progi temperatury (20..22 z payloadu) ---
            AlarmTempMinValue(master),
            AlarmTempMaxValue(master),

            # --- statusy jak z YAML ---
            NoRegTime(master),          # [17]
            FanController(master),      # [5], [6], [17]
            ThermoregSocket(master),    # [7], [8], [17]
            CO2Socket(master),          # [9], [10], [17]
            O2Socket(master),           # [11], [12], [17]

            TempAlarms(master),         # [18]
            PhAlarms(master),           # [18]
            AcousticAlarmStatus(master),# [18]

            AlarmPhMinValue(master),    # [23]
            AlarmPhMaxValue(master),    # [24]

        ],
        True,
    )


# ---------------------- MASTER ENTITY ----------------------

def _derive_entity_prefix(name: str) -> str:
    if not name:
        return "uaqua_1"
    match = re.search(r"microaqua\s*(\d+)", name, re.IGNORECASE)
    if match:
        return f"uaqua_{match.group(1)}"
    return slugify(name)


class MicroAQUASensor(SensorEntity):
    """Master entity: connects, polls and parses the microAQUA payload."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:raspberry-pi"

    def __init__(self, hass, ip, port, payload, name):
        self._hass = hass
        self._display_name = name  # nazwa urządzenia z config flow
        self._entity_prefix = _derive_entity_prefix(name)
        self._ip = ip
        self._port = port
        self._payload = f"AT+{payload}\r\n"
        self._expected_prefix = f"AT+{payload}="

        self._state: Optional[str] = None
        self._error_count = 0
        self._last_update_dt: Optional[datetime] = None
        self._payload_parts: list[str] = []

        # Value used by number.py (No regulation time set, minutes)
        self._no_reg_set_minutes: int = 0

        # podstawowe
        self._ph_value = None
        self._temp_values = [None] * 7
        self._led = [None] * 4
        self._last_update_time = None

        # dodatkowe / YAML-like
        self._fan_driver_mode = None              # [5]
        self._fan_speed = None                    # [6]
        self._thermoreg_assigned_socket = None    # [7]
        self._thermoreg_socket_state = None       # [8]
        self._ph_meter_assigned_co2_socket = None # [9]
        self._ph_meter_co2_socket_state = None    # [10]
        self._ph_meter_assigned_o2_socket = None  # [11]
        self._ph_meter_o2_socket_state = None     # [12]
        self._regulation_off_marker = None        # [17]
        self._alarm_register = None               # [18]
        self._alarm_temp_hysteresis = None        # [22]
        self._alarm_ph_min = None                 # [23]
        self._alarm_ph_max = None                 # [24]
        self._alarm_ph_hysteresis = None          # [25]

        self._attr_name = self._entity_prefix

        # Kluczowe: nazwa urządzenia krótka, bez IP/port (żeby UI nie puchło)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._entity_prefix)},
            "name": self._display_name,
            "manufacturer": "microAQUA",
            "model": "microAQUA",
        }

    @property
    def unique_id(self):
        return self._entity_prefix

    @property
    def state(self):
        return self._state

    @property
    def available(self) -> bool:
        return self._state not in (None, "unknown", "unavailable")

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def entity_prefix(self) -> str:
        return self._entity_prefix

    def data_age_seconds(self) -> Optional[float]:
        if self._state in (None, "unknown", "unavailable"):
            return None
        if self._last_update_dt is None:
            return None
        return (dt_util.utcnow() - self._last_update_dt).total_seconds()

    def has_recent_data(self, max_age_seconds: int = 5) -> bool:
        age = self.data_age_seconds()
        return age is not None and age < max_age_seconds

    def get_part(self, idx: int) -> Optional[str]:
        return self._payload_parts[idx] if idx < len(self._payload_parts) else None

    def parts_length(self) -> int:
        return len(self._payload_parts)

    @property
    def extra_state_attributes(self):
        """Informacyjne atrybuty (nie muszą być osobnymi encjami)."""
        return {
            "ip": self._ip,
            "port": self._port,
            "alarm_temp_min_c": self._temp_values[4],
            "alarm_temp_max_c": self._temp_values[5],
            "alarm_temp_hysteresis_c": self._temp_values[6],
            "alarm_ph_min": self._alarm_ph_min,
            "alarm_ph_max": self._alarm_ph_max,
            "alarm_ph_hysteresis": self._alarm_ph_hysteresis,
            "fan_driver_mode_raw": self._fan_driver_mode,
            "fan_speed_raw": self._fan_speed,
            "thermoreg_assigned_socket": self._thermoreg_assigned_socket,
            "co2_assigned_socket": self._ph_meter_assigned_co2_socket,
            "o2_assigned_socket": self._ph_meter_assigned_o2_socket,
            "regulation_off_marker_min": self._regulation_off_marker,
            "alarm_register": self._alarm_register,
            "no_reg_set_minutes": self._no_reg_set_minutes,
        }

    async def async_send_command(self, command: str) -> None:
        """Send a raw command to device (adds CRLF). Used by switch.py."""
        loop = asyncio.get_event_loop()
        msg = f"{command}\r\n"

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(TIMEOUT)
            await loop.run_in_executor(None, sock.connect, (self._ip, self._port))
            await loop.run_in_executor(None, sock.sendall, msg.encode("utf-8"))
            try:
                await loop.run_in_executor(None, sock.recv, 1024)
            except Exception:
                pass

    async def async_update(self):
        if not self.entity_id:
            _LOGGER.debug("Entity ID is not set. Skipping update.")
            return

        try:
            data = await self._fetch_data()
            valid_data = self._validate_response(data)

            if not valid_data:
                _LOGGER.warning("Invalid response from device: %s", data)
                self._handle_error()
                return

            parsed = valid_data.split(";")
            self._payload_parts = parsed
            self._last_update_dt = dt_util.utcnow()

            # Bezpieczny getter (żeby nie wywalić integracji gdy payload jest krótszy)
            def g(idx: int) -> str:
                return parsed[idx] if idx < len(parsed) else "???"

            # --- podstawowe ---
            self._ph_value = self._parse_ph(g(0))
            temps_part = [g(i) for i in [1, 2, 3, 4, 20, 21, 22]]
            self._temp_values = [self._parse_temp(v) for v in temps_part]
            self._led = [self._parse_led(g(i)) for i in [13, 14, 15, 16]]
            self._last_update_time = self._parse_time_stamp(g(19))

            # --- dodatkowe ---
            self._fan_driver_mode = self._parse_int(g(5))
            self._fan_speed = self._parse_int(g(6))

            self._thermoreg_assigned_socket = self._parse_int(g(7))
            self._thermoreg_socket_state = self._parse_int(g(8))

            self._ph_meter_assigned_co2_socket = self._parse_int(g(9))
            self._ph_meter_co2_socket_state = self._parse_int(g(10))

            self._ph_meter_assigned_o2_socket = self._parse_int(g(11))
            self._ph_meter_o2_socket_state = self._parse_int(g(12))

            self._regulation_off_marker = self._parse_int(g(17))
            self._alarm_register = self._parse_int(g(18))

            self._alarm_temp_hysteresis = self._parse_temp(g(22))
            self._alarm_ph_min = self._parse_ph(g(23))
            self._alarm_ph_max = self._parse_ph(g(24))
            self._alarm_ph_hysteresis = self._parse_ph(g(25))

            self._state = valid_data
            self._error_count = 0
            self.async_write_ha_state()

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
        loop = asyncio.get_event_loop()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(TIMEOUT)
            await loop.run_in_executor(None, sock.connect, (self._ip, self._port))
            await loop.run_in_executor(None, sock.sendall, self._payload.encode("utf-8"))
            resp = await loop.run_in_executor(None, sock.recv, 2048)
            return resp.decode("utf-8").strip()

    def _validate_response(self, data: str):
        if self._expected_prefix in data:
            start_index = data.find(self._expected_prefix)
            return data[start_index + len(self._expected_prefix):]
        return None

    def _handle_error(self):
        self._error_count += 1
        if self._error_count >= 5:
            self._state = "unknown"
            self.async_write_ha_state()

    @staticmethod
    def _parse_int(value: str):
        try:
            if value in (None, "", "???"):
                return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _parse_ph(value: str):
        try:
            if value in (None, "", "???"):
                return None
            return float(value) / 100.0
        except Exception:
            return None

    @staticmethod
    def _parse_temp(value: str):
        try:
            if value in (None, "", "???"):
                return None
            return float(value) / 10.0
        except Exception:
            return None

    @staticmethod
    def _parse_led(value: str):
        try:
            if value in (None, "", "???"):
                return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _parse_time_stamp(value: str):
        try:
            time_obj = datetime.strptime(value, "%H:%M:%S")
            return time_obj.time()
        except Exception:
            return None


# ---------------------- BASE CHILD ENTITY ----------------------

class MicroAQUAChildSensor(SensorEntity):
    """Base class: attaches to device + uses master reference."""

    _attr_has_entity_name = False

    def __init__(self, master: MicroAQUASensor):
        self._m = master

    @property
    def device_info(self):
        return self._m.device_info

    @property
    def available(self) -> bool:
        return self._m.available

    def _data_ready(self, min_length: int) -> bool:
        return self._m.has_recent_data() and self._m.parts_length() >= min_length


# ---------------------- BASIC SENSORS ----------------------

class DataValidSensor(MicroAQUAChildSensor):
    _attr_icon = "mdi:check-network-outline"

    def __init__(self, master: MicroAQUASensor):
        super().__init__(master)
        self._attr_name = f"{self._m.display_name} - data valid"

    @property
    def state(self):
        if self._m.state in (None, "unknown", "unavailable"):
            return False
        return self._m.has_recent_data()

    @property
    def extra_state_attributes(self):
        age = self._m.data_age_seconds()
        return {"age_seconds": None if age is None else round(age)}

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_data_valid"


class DataAgeSensor(MicroAQUAChildSensor):
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = "s"

    def __init__(self, master: MicroAQUASensor):
        super().__init__(master)
        self._attr_name = f"{self._m.display_name} - data age"

    @property
    def state(self):
        age = self._m.data_age_seconds()
        if age is None:
            return None
        return round(age)

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_data_age"


class PHSensor(MicroAQUAChildSensor):
    _attr_name = "pH sensor"
    _attr_icon = "hass:raspberry-pi"

    @property
    def state(self):
        if not self._data_ready(26):
            return None
        return self._m._parse_ph(self._m.get_part(0))

    @property
    def unit_of_measurement(self):
        return "pH"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_pH"


class TempSensor(MicroAQUAChildSensor):
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, master: MicroAQUASensor, name: str, index: int, icon="mdi:thermometer"):
        super().__init__(master)
        self._index = index
        self._attr_name = name
        self._attr_icon = icon

    @property
    def state(self):
        if not self._data_ready(self._index + 1):
            return None
        return self._m._parse_temp(self._m.get_part(self._index))

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_Temp{self._index}"


class LEDSensor(MicroAQUAChildSensor):
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "hass:led-on"

    def __init__(self, master: MicroAQUASensor, index: int):
        super().__init__(master)
        self._index = index
        self._attr_name = f"LED {index}"

    @property
    def state(self):
        if not self._data_ready(12 + self._index + 1):
            return None
        return self._m._parse_led(self._m.get_part(12 + self._index))

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_LED_{self._index}_controller"


class LastUpdateTime(MicroAQUAChildSensor):
    _attr_name = "Czas ostatniego pomiaru test"
    _attr_icon = "hass:clock"

    @property
    def state(self):
        if not self._data_ready(20):
            return None
        return self._m.get_part(19)

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_data_update_time_stamp_test"


# ---------------------- YAML-LIKE STATUS SENSORS ----------------------

class NoRegTime(MicroAQUAChildSensor):
    """Czas bez regulacji (parsed_data[17]) — w YAML: uaqua_1_no_reg_time"""

    _attr_name = "Czas bez regulacji"
    _attr_icon = "hass:power-plug-off"

    @property
    def state(self):
        if not self._data_ready(18):
            return None
        v = self._m.get_part(17)
        if v in (None, "???"):
            return None
        return "--" if v == "0" else f"{v}min"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_no_reg_time"


class ThermoregSocket(MicroAQUAChildSensor):
    _attr_name = "Grzałka"
    _attr_icon = "hass:power-socket-eu"

    @property
    def state(self):
        if not self._data_ready(18):
            return None
        if self._m.get_part(17) != "0":
            return "off"
        assigned = self._m.get_part(7)
        if assigned == "7":
            return "brak przypisanego gniazda"
        v = self._m.get_part(8)
        if v is None or v == "???":
            return None
        return "OFF" if v == "0" else "ON"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_termoreg_socket"


class CO2Socket(MicroAQUAChildSensor):
    _attr_name = "Zawór CO2"
    _attr_icon = "hass:power-socket-eu"

    @property
    def state(self):
        if not self._data_ready(18):
            return None
        if self._m.get_part(17) != "0":
            return "off"
        assigned = self._m.get_part(9)
        if assigned == "7":
            return "brak przypisanego gniazda"
        v = self._m.get_part(10)
        if v is None or v == "???":
            return None
        return "OFF" if v == "0" else "ON"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_co2_socket"


class O2Socket(MicroAQUAChildSensor):
    _attr_name = "Zawór O2"
    _attr_icon = "hass:power-socket-eu"

    @property
    def state(self):
        if not self._data_ready(18):
            return None
        if self._m.get_part(17) != "0":
            return "off"
        assigned = self._m.get_part(11)
        if assigned == "7":
            return "brak przypisanego gniazda"
        v = self._m.get_part(12)
        if v is None or v == "???":
            return None
        return "off" if v == "0" else "on"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_o2_socket"


class FanController(MicroAQUAChildSensor):
    """Odtwarza tekstowy opis jak w YAML: uaqua_1_fan_controller"""

    _attr_name = "Wentylator"
    _attr_icon = "hass:fan"

    @property
    def state(self):
        if not self._data_ready(18):
            return None

        reg_off = self._m.get_part(17)
        mode = self._m.get_part(5)
        speed = self._m.get_part(6)

        if reg_off != "0":
            return "off"

        if mode is None or speed is None:
            return None

        if mode == "3":
            return "Moduł FAN wyłączony"

        if mode == "2":
            return "Praca okresowa: ON" if speed != "0" else "Praca okresowa: OFF"

        if mode == "1":
            power_map = {
                "1": "Regulacja mocy: Rozruch",
                "2": "Regulacja mocy: 20%",
                "3": "Regulacja mocy: 40%",
                "4": "Regulacja mocy: 60%",
                "5": "Regulacja mocy: 80%",
                "6": "Regulacja mocy: 100%",
            }
            return power_map.get(speed, "Regulacja mocy: OFF")

        return "Praca ON/OFF: ON" if speed != "0" else "Praca ON/OFF: OFF"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_FAN_controller"


# ---------------------- ALARM SENSORS ----------------------

def _bit_is_set(value: Optional[int], bitmask: int) -> bool:
    if value is None:
        return False
    return (value & bitmask) == bitmask


class TempAlarms(MicroAQUAChildSensor):
    _attr_name = "Alarm Temp min/max"
    _attr_icon = "hass:thermometer-alert"

    @property
    def state(self):
        if not self._data_ready(19):
            return None
        ar_raw = self._m.get_part(18)
        if ar_raw is None:
            return None
        ar = int(ar_raw)

        muted = _bit_is_set(ar, 128)

        if _bit_is_set(ar, 1):
            return "ALARM Temp MIN wyciszony" if muted else "ALARM Temp MIN"

        if _bit_is_set(ar, 2):
            return "ALARM Temp MAX wyciszony" if muted else "ALARM Temp MAX"

        return "---"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_temp_alarms"


class PhAlarms(MicroAQUAChildSensor):
    _attr_name = "Alarm pH min/max"
    _attr_icon = "hass:alert"

    @property
    def state(self):
        if not self._data_ready(19):
            return None
        ar_raw = self._m.get_part(18)
        if ar_raw is None:
            return None
        ar = int(ar_raw)

        muted = _bit_is_set(ar, 128)

        if _bit_is_set(ar, 4):
            return "ALARM pH MIN wyciszony" if muted else "ALARM pH MIN"

        if _bit_is_set(ar, 8):
            return "ALARM pH MAX wyciszony" if muted else "ALARM pH MAX"

        return "---"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_pH_alarms"


class AcousticAlarmStatus(MicroAQUAChildSensor):
    _attr_name = "Alarm Dźwiękowy Status"
    _attr_icon = "hass:volume-high"

    @property
    def state(self):
        if not self._data_ready(19):
            return None
        ar_raw = self._m.get_part(18)
        if ar_raw is None:
            return None
        ar = int(ar_raw)

        if (ar & 127) != 0:
            return "OFF" if _bit_is_set(ar, 128) else "ON"
        return "OFF"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_acoustic_alarm_status"


# ---------------------- temp alarm values ----------------------

class AlarmTempMinValue(MicroAQUAChildSensor):
    _attr_name = "Alarm Temp. min. value"
    _attr_icon = "hass:thermometer-alert"

    @property
    def state(self):
        if not self._data_ready(23):
            return None
        value = self._m.get_part(20)
        hysteresis = self._m.get_part(22)
        if value in (None, "???") or hysteresis in (None, "???"):
            return None
        return f"{self._m._parse_temp(value)} +/-{self._m._parse_temp(hysteresis)}"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_temp_alarm_min_value"


class AlarmTempMaxValue(MicroAQUAChildSensor):
    _attr_name = "Alarm Temp. max. value"
    _attr_icon = "hass:thermometer-alert"

    @property
    def state(self):
        if not self._data_ready(23):
            return None
        value = self._m.get_part(21)
        hysteresis = self._m.get_part(22)
        if value in (None, "???") or hysteresis in (None, "???"):
            return None
        return f"{self._m._parse_temp(value)} +/-{self._m._parse_temp(hysteresis)}"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_temp_alarm_max_value"


# ---------------------- pH threshold sensors ----------------------

class AlarmPhMinValue(MicroAQUAChildSensor):
    _attr_name = "Alarm pH min. value"
    _attr_icon = "hass:alert"

    @property
    def state(self):
        if not self._data_ready(26):
            return None
        value = self._m.get_part(23)
        hysteresis = self._m.get_part(25)
        if value in (None, "???") or hysteresis in (None, "???"):
            return None
        return f"{self._m._parse_ph(value)} +/-{self._m._parse_ph(hysteresis)} pH"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_pH_alarm_min_value"


class AlarmPhMaxValue(MicroAQUAChildSensor):
    _attr_name = "Alarm pH max. value"
    _attr_icon = "hass:alert"

    @property
    def state(self):
        if not self._data_ready(26):
            return None
        value = self._m.get_part(24)
        hysteresis = self._m.get_part(25)
        if value in (None, "???") or hysteresis in (None, "???"):
            return None
        return f"{self._m._parse_ph(value)} +/-{self._m._parse_ph(hysteresis)} pH"

    @property
    def unique_id(self):
        return f"{self._m.entity_prefix}_pH_alarm_max_value"


# ---------------------- optional raw debug sensors ----------------------

class FanDriverModeRaw(MicroAQUAChildSensor):
    _attr_name = "Fan driver mode (raw)"
    _attr_icon = "mdi:chip"

    @property
    def state(self):
        return self._m._fan_driver_mode

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_fan_driver_mode_raw"


class FanSpeedRaw(MicroAQUAChildSensor):
    _attr_name = "Fan speed (raw)"
    _attr_icon = "mdi:speedometer"

    @property
    def state(self):
        return self._m._fan_speed

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_fan_speed_raw"
