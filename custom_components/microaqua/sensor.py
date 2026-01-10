from __future__ import annotations

import asyncio
import logging
import socket
from datetime import datetime
from typing import Optional

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN, TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform from a config entry."""
    ip = config_entry.data["ip"]
    port = config_entry.data["port"]
    payload = config_entry.data["payload"]
    name = config_entry.data["name"]

    master = MicroAQUASensor(hass, ip, port, payload, name)

    # Udostępnij mastera innym platformom (button/number) przez hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    hass.data[DOMAIN][config_entry.entry_id]["master"] = master

    async_add_entities(
        [
            master,

            # --- podstawowe ---
            PHSensor(master),
            TempSensor(master, "Temp 1", 1),
            TempSensor(master, "Temp 2", 2),
            TempSensor(master, "Temp 3", 3),
            TempSensor(master, "Temp 4", 4),
            LED(master, 1),
            LED(master, 2),
            LED(master, 3),
            LED(master, 4),
            LastUpdateTime(master),

            # --- progi temperatury (20..22 z payloadu) ---
            TempSensor(master, "Alarm Temp min", 5, "mdi:thermometer-alert"),
            TempSensor(master, "Alarm Temp max", 6, "mdi:thermometer-alert"),
            TempSensor(master, "Alarm Temp histeresis", 7, "mdi:thermometer-alert"),

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
            AlarmPhHysteresis(master),  # [25]

            # --- debug / raw ---
            FanDriverModeRaw(master),   # [5]
            FanSpeedRaw(master),        # [6]
        ],
        True,
    )


# ---------------------- MASTER ENTITY ----------------------

class MicroAQUASensor(SensorEntity):
    """Master entity: connects, polls and parses the microAQUA payload."""

    def __init__(self, hass, ip, port, payload, name):
        self._hass = hass
        self._name = name
        self._ip = ip
        self._port = port
        self._payload = f"AT+{payload}\r\n"
        self._expected_prefix = f"AT+{payload}="

        self._state: Optional[str] = None
        self._error_count = 0

        # Value used by number.py (No regulation time set, minutes)
        # button.py should use this to send AT+TCPENRM;<minutes>
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

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._ip)},
            "name": f"{self._name} {self._ip} {self._port}",
            "manufacturer": "microAQUA",
            "model": "microAQUA",
        }

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{self._name}_{self._ip}"

    @property
    def extra_state_attributes(self):
        """Informacyjne atrybuty (nie muszą być osobnymi encjami)."""
        return {
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
        """Send a raw command to device (adds CRLF). Used by button.py."""
        loop = asyncio.get_event_loop()
        msg = f"{command}\r\n"

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(TIMEOUT)
            await loop.run_in_executor(None, sock.connect, (self._ip, self._port))
            await loop.run_in_executor(None, sock.sendall, msg.encode("utf-8"))
            # Nie zawsze jest odpowiedź, ale spróbuj odebrać żeby domknąć połączenie
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

            self._state = "updated"
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

    def __init__(self, master: MicroAQUASensor):
        self._m = master

    @property
    def device_info(self):
        return self._m.device_info


# ---------------------- BASIC SENSORS ----------------------

class PHSensor(MicroAQUAChildSensor):
    def __init__(self, master: MicroAQUASensor):
        super().__init__(master)

    @property
    def name(self):
        return f"{self._m.name} pH"

    @property
    def state(self):
        return self._m._ph_value

    @property
    def unit_of_measurement(self):
        return "pH"

    @property
    def icon(self):
        return "mdi:ph"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_ph"


class TempSensor(MicroAQUAChildSensor):
    def __init__(self, master: MicroAQUASensor, name: str, index: int, icon="mdi:thermometer"):
        super().__init__(master)
        self._index = index
        self._name = name
        self._icon = icon

    @property
    def name(self):
        return f"{self._m.name} {self._name}"

    @property
    def state(self):
        return self._m._temp_values[self._index - 1]

    @property
    def unit_of_measurement(self):
        return "°C"

    @property
    def icon(self):
        return self._icon

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_temp_{self._index}"


class LED(MicroAQUAChildSensor):
    def __init__(self, master: MicroAQUASensor, index: int):
        super().__init__(master)
        self._index = index

    @property
    def name(self):
        return f"{self._m.name} LED {self._index}"

    @property
    def state(self):
        return self._m._led[self._index - 1]

    @property
    def unit_of_measurement(self):
        return "%"

    @property
    def icon(self):
        return "mdi:led-on"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_led_{self._index}"


class LastUpdateTime(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} Last Update Time"

    @property
    def state(self):
        return self._m._last_update_time

    @property
    def icon(self):
        return "mdi:update"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_last_update_time"


# ---------------------- YAML-LIKE STATUS SENSORS ----------------------

class NoRegTime(MicroAQUAChildSensor):
    """Czas bez regulacji (parsed_data[17]) — w YAML: uaqua_1_no_reg_time"""

    @property
    def name(self):
        return f"{self._m.name} No regulation time"

    @property
    def state(self):
        v = self._m._regulation_off_marker
        if v is None:
            return None
        return "--" if v == 0 else f"{v}min"

    @property
    def icon(self):
        return "mdi:power-plug-off"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_no_reg_time"


def _socket_state_text(assigned: Optional[int], state: Optional[int], reg_off: Optional[int]) -> str | None:
    """
    Logika zgodna z YAML:
    - jeśli reg_off != 0 => off
    - jeśli assigned == 7 => brak przypisanego gniazda
    - else state: 0->off, 1->on
    """
    if reg_off is None:
        return None
    if reg_off != 0:
        return "off"
    if assigned is None:
        return None
    if assigned == 7:
        return "brak przypisanego gniazda"
    if state is None:
        return None
    return "off" if state == 0 else "on"


class ThermoregSocket(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} Thermoreg socket"

    @property
    def state(self):
        return _socket_state_text(
            self._m._thermoreg_assigned_socket,
            self._m._thermoreg_socket_state,
            self._m._regulation_off_marker,
        )

    @property
    def icon(self):
        return "mdi:power-socket-eu"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_thermoreg_socket"


class CO2Socket(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} CO2 socket"

    @property
    def state(self):
        return _socket_state_text(
            self._m._ph_meter_assigned_co2_socket,
            self._m._ph_meter_co2_socket_state,
            self._m._regulation_off_marker,
        )

    @property
    def icon(self):
        return "mdi:power-socket-eu"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_co2_socket"


class O2Socket(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} O2 socket"

    @property
    def state(self):
        return _socket_state_text(
            self._m._ph_meter_assigned_o2_socket,
            self._m._ph_meter_o2_socket_state,
            self._m._regulation_off_marker,
        )

    @property
    def icon(self):
        return "mdi:power-socket-eu"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_o2_socket"


class FanController(MicroAQUAChildSensor):
    """Odtwarza tekstowy opis jak w YAML: uaqua_1_fan_controller"""

    @property
    def name(self):
        return f"{self._m.name} Fan controller"

    @property
    def state(self):
        reg_off = self._m._regulation_off_marker
        mode = self._m._fan_driver_mode
        speed = self._m._fan_speed

        if reg_off is None or mode is None or speed is None:
            return None

        if reg_off != 0:
            return "off"

        if mode == 3:
            return "Moduł FAN wyłączony"

        if mode == 2:
            return "Praca okresowa: Stan ON" if speed != 0 else "Praca okresowa: Stan OFF"

        if mode == 1:
            power_map = {
                1: "Regulacja mocy: Rozruch",
                2: "Regulacja mocy: 20%",
                3: "Regulacja mocy: 40%",
                4: "Regulacja mocy: 60%",
                5: "Regulacja mocy: 80%",
                6: "Regulacja mocy: 100%",
            }
            return power_map.get(speed, "Regulacja mocy: OFF")

        return "Praca ON/OFF: Stan ON" if speed != 0 else "Praca ON/OFF: Stan OFF"

    @property
    def icon(self):
        return "mdi:fan"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_fan_controller"


# ---------------------- ALARM SENSORS ----------------------

def _bit_is_set(value: Optional[int], bitmask: int) -> bool:
    if value is None:
        return False
    return (value & bitmask) == bitmask


class TempAlarms(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} Temp alarms"

    @property
    def state(self):
        ar = self._m._alarm_register
        if ar is None:
            return None

        muted = _bit_is_set(ar, 128)

        if _bit_is_set(ar, 1):
            return "ALARM Temp MIN wyciszony" if muted else "ALARM Temp MIN"

        if _bit_is_set(ar, 2):
            return "ALARM Temp MAX wyciszony" if muted else "ALARM Temp MAX"

        return "---"

    @property
    def icon(self):
        return "mdi:thermometer-alert"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_temp_alarms"


class PhAlarms(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} pH alarms"

    @property
    def state(self):
        ar = self._m._alarm_register
        if ar is None:
            return None

        muted = _bit_is_set(ar, 128)

        if _bit_is_set(ar, 4):
            return "ALARM pH MIN wyciszony" if muted else "ALARM pH MIN"

        if _bit_is_set(ar, 8):
            return "ALARM pH MAX wyciszony" if muted else "ALARM pH MAX"

        return "---"

    @property
    def icon(self):
        return "mdi:alert"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_ph_alarms"


class AcousticAlarmStatus(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} Acoustic alarm"

    @property
    def state(self):
        ar = self._m._alarm_register
        if ar is None:
            return None

        if (ar & 127) != 0:
            return "OFF" if _bit_is_set(ar, 128) else "ON"
        return "OFF"

    @property
    def icon(self):
        return "mdi:volume-high"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_acoustic_alarm"


# ---------------------- pH threshold sensors ----------------------

class AlarmPhMinValue(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} Alarm pH min value"

    @property
    def state(self):
        return self._m._alarm_ph_min

    @property
    def unit_of_measurement(self):
        return "pH"

    @property
    def icon(self):
        return "mdi:alert"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_alarm_ph_min"


class AlarmPhMaxValue(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} Alarm pH max value"

    @property
    def state(self):
        return self._m._alarm_ph_max

    @property
    def unit_of_measurement(self):
        return "pH"

    @property
    def icon(self):
        return "mdi:alert"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_alarm_ph_max"


class AlarmPhHysteresis(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} Alarm pH hysteresis"

    @property
    def state(self):
        return self._m._alarm_ph_hysteresis

    @property
    def unit_of_measurement(self):
        return "pH"

    @property
    def icon(self):
        return "mdi:alert"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_alarm_ph_hysteresis"


# ---------------------- optional raw debug sensors ----------------------

class FanDriverModeRaw(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} Fan driver mode (raw)"

    @property
    def state(self):
        return self._m._fan_driver_mode

    @property
    def icon(self):
        return "mdi:chip"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_fan_driver_mode_raw"


class FanSpeedRaw(MicroAQUAChildSensor):
    @property
    def name(self):
        return f"{self._m.name} Fan speed (raw)"

    @property
    def state(self):
        return self._m._fan_speed

    @property
    def icon(self):
        return "mdi:speedometer"

    @property
    def unique_id(self):
        return f"{self._m.unique_id}_fan_speed_raw"
