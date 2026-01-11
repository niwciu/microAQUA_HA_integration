"""Sensor platform for microAQUA."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
import socket
from typing import Callable

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.typing import StateType

from .const import (
    CONF_PAYLOAD,
    DEFAULT_NAME,
    DEFAULT_PAYLOAD,
    DEFAULT_PORT,
    DOMAIN,
    SCAN_INTERVAL,
    TIMEOUT,
)
from .utils import device_info_from_entry, unique_id_prefix

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MicroAQUAData:
    """Parsed data from the microAQUA controller."""

    raw_payload: str | None
    parts: tuple[str, ...]
    updated_at: datetime | None


@dataclass(frozen=True, kw_only=True)
class MicroAQUASensorDescription:
    """Description of a microAQUA sensor entity."""

    name: str
    unique_id: str
    icon: str | None = None
    unit: str | None = None
    state_class: SensorStateClass | None = None
    value_fn: Callable[[MicroAQUAData | None, datetime], StateType]


class MicroAQUADataUpdateCoordinator(DataUpdateCoordinator[MicroAQUAData]):
    """Fetch data from a microAQUA controller."""

    def __init__(
        self, hass: HomeAssistant, host: str, port: int, payload: str
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._host = host
        self._port = port
        self._payload = f"AT+{payload}\r\n"
        self._expected_prefix = f"AT+{payload}="

    async def _async_update_data(self) -> MicroAQUAData:
        try:
            raw = await asyncio.to_thread(self._fetch_data)
            return self._parse_payload(raw)
        except (OSError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Unable to fetch data from {self._host}") from err

    def _fetch_data(self) -> str:
        with socket.create_connection((self._host, self._port), timeout=TIMEOUT) as sock:
            sock.sendall(self._payload.encode("utf-8"))
            response = sock.recv(1024)
        return response.decode("utf-8").strip()

    def _parse_payload(self, data: str) -> MicroAQUAData:
        now = dt_util.utcnow()
        if self._expected_prefix not in data:
            return MicroAQUAData(raw_payload="unknown", parts=(), updated_at=now)
        start_index = data.find(self._expected_prefix)
        payload = data[start_index + len(self._expected_prefix) :]
        parts = tuple(payload.split(";")) if payload else ()
        return MicroAQUAData(raw_payload=payload or None, parts=parts, updated_at=now)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the sensor platform from a config entry."""
    host = config_entry.data.get(CONF_HOST) or config_entry.data.get("ip")
    if not host:
        raise ConfigEntryNotReady("Missing host/IP address in configuration")
    port = config_entry.data.get(CONF_PORT, config_entry.data.get("port", DEFAULT_PORT))
    payload = config_entry.data.get(
        CONF_PAYLOAD, config_entry.data.get("payload", DEFAULT_PAYLOAD)
    )
    name = config_entry.data.get(CONF_NAME, config_entry.data.get("name", DEFAULT_NAME))

    entry_data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    coordinator = entry_data.get("coordinator") if entry_data else None
    if coordinator is None:
        coordinator = MicroAQUADataUpdateCoordinator(hass, host, port, payload)
        await coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {}).setdefault(
            config_entry.entry_id, {}
        )["coordinator"] = coordinator

    unique_prefix = unique_id_prefix(name)

    entities: list[SensorEntity] = [
        RawPayloadSensor(coordinator, config_entry, name, unique_prefix),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name=f"{name} - data valid",
                unique_id="data_valid",
                icon="mdi:check-network-outline",
                value_fn=_value_data_valid,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name=f"{name} - data age",
                unique_id="data_age",
                icon="mdi:timer-outline",
                unit="s",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_value_data_age,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="pH sensor",
                unique_id="pH",
                icon="hass:raspberry-pi",
                unit="pH",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_value_ph,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Czujnik Temperatury 1",
                unique_id="Temp1",
                icon="hass:thermometer",
                unit="°C",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_value_temp1,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Czujnik Temperatury 2",
                unique_id="Temp2",
                icon="hass:thermometer",
                unit="°C",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_value_temp2,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Czujnik Temperatury 3",
                unique_id="Temp3",
                icon="hass:thermometer",
                unit="°C",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_value_temp3,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Czujnik Temperatury 4",
                unique_id="Temp4",
                icon="hass:thermometer",
                unit="°C",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_value_temp4,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Zawór CO2",
                unique_id="co2_socket",
                icon="hass:power-socket-eu",
                value_fn=_value_co2_socket,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Zawór O2",
                unique_id="o2_socket",
                icon="hass:power-socket-eu",
                value_fn=_value_o2_socket,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Grzałka",
                unique_id="termoreg_socket",
                icon="hass:power-socket-eu",
                value_fn=_value_termoreg_socket,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Wentylator",
                unique_id="FAN_controller",
                icon="hass:fan",
                value_fn=_value_fan_controller,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="LED 1",
                unique_id="LED_1_controller",
                icon="hass:led-on",
                unit="%",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_value_led1,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="LED 2",
                unique_id="LED_2_controller",
                icon="hass:led-on",
                unit="%",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_value_led2,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="LED 3",
                unique_id="LED_3_controller",
                icon="hass:led-on",
                unit="%",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_value_led3,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="LED 4",
                unique_id="LED_4_controller",
                icon="hass:led-on",
                unit="%",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_value_led4,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Alarm Temp min/max",
                unique_id="temp_alarms",
                icon="hass:thermometer-alert",
                value_fn=_value_temp_alarms,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Alarm pH min/max",
                unique_id="pH_alarms",
                icon="hass:alert",
                value_fn=_value_ph_alarms,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Alarm Dźwiękowy Status",
                unique_id="acoustic_alarm_status",
                icon="hass:volume-high",
                value_fn=_value_acoustic_alarm_status,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Alarm Temp. min. value",
                unique_id="temp_alarm_min_value",
                icon="hass:thermometer-alert",
                value_fn=_value_temp_alarm_min_value,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Alarm Temp. max. value",
                unique_id="temp_alarm_max_value",
                icon="hass:thermometer-alert",
                value_fn=_value_temp_alarm_max_value,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Alarm pH min. value",
                unique_id="pH_alarm_min_value",
                icon="hass:alert",
                value_fn=_value_ph_alarm_min_value,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Alarm pH max. value",
                unique_id="pH_alarm_max_value",
                icon="hass:alert",
                value_fn=_value_ph_alarm_max_value,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Czas ostatniego pomiaru test",
                unique_id="data_update_time_stamp_test",
                icon="hass:clock",
                value_fn=_value_data_update_time_stamp_test,
            ),
        ),
        MicroAQUASensor(
            coordinator,
            config_entry,
            name,
            unique_prefix,
            MicroAQUASensorDescription(
                name="Czas bez regulacji",
                unique_id="no_reg_time",
                icon="hass:power-plug-off",
                value_fn=_value_no_reg_time,
            ),
        ),
    ]

    async_add_entities(entities)


class MicroAQUABaseEntity(CoordinatorEntity[MicroAQUAData]):
    """Base entity for microAQUA entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MicroAQUADataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        unique_prefix: str,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_name = name
        self._unique_prefix = unique_prefix

    @property
    def device_info(self):
        return device_info_from_entry(self._config_entry, self._device_name)


class RawPayloadSensor(MicroAQUABaseEntity, SensorEntity):
    """Representation of the raw payload sensor."""

    def __init__(
        self,
        coordinator: MicroAQUADataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        unique_prefix: str,
    ) -> None:
        super().__init__(coordinator, config_entry, name, unique_prefix)
        self._attr_name = unique_prefix

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if data is None:
            return None
        if data.raw_payload in (None, "", "unknown"):
            return "unknown"
        return data.raw_payload


class MicroAQUASensor(MicroAQUABaseEntity, SensorEntity):
    """Representation of a microAQUA sensor."""

    def __init__(
        self,
        coordinator: MicroAQUADataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        unique_prefix: str,
        description: MicroAQUASensorDescription,
    ) -> None:
        super().__init__(coordinator, config_entry, name, unique_prefix)
        self.entity_description = description
        self._attr_unique_id = f"{unique_prefix}_{description.unique_id}"
        self._attr_name = description.name
        if description.icon:
            self._attr_icon = description.icon
        if description.unit:
            self._attr_native_unit_of_measurement = description.unit
        if description.state_class:
            self._attr_state_class = description.state_class

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.data, dt_util.utcnow())




def _data_is_unknown(data: MicroAQUAData | None) -> bool:
    return data is None or data.raw_payload in (None, "", "unknown")


def _data_age_seconds(data: MicroAQUAData | None, now: datetime) -> float | None:
    if data is None or data.updated_at is None:
        return None
    return (now - data.updated_at).total_seconds()


def _data_is_fresh(data: MicroAQUAData | None, now: datetime) -> bool:
    if _data_is_unknown(data):
        return False
    age = _data_age_seconds(data, now)
    return age is not None and age < 5


def _get_parts(
    data: MicroAQUAData | None, now: datetime, min_length: int
) -> tuple[str, ...] | None:
    if not _data_is_fresh(data, now):
        return None
    if data is None or len(data.parts) < min_length:
        return None
    return data.parts


def _parse_float(value: str, divisor: float) -> float | None:
    try:
        return float(value) / divisor
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _value_data_valid(data: MicroAQUAData | None, now: datetime) -> bool:
    if _data_is_unknown(data):
        return False
    age = _data_age_seconds(data, now)
    return age is not None and age < 5


def _value_data_age(data: MicroAQUAData | None, now: datetime) -> int | None:
    if _data_is_unknown(data):
        return None
    age = _data_age_seconds(data, now)
    if age is None:
        return None
    return round(age)


def _value_ph(data: MicroAQUAData | None, now: datetime) -> float | None:
    parts = _get_parts(data, now, 26)
    if not parts:
        return None
    return _parse_float(parts[0], 100.0)


def _parse_temp(value: str) -> float | None:
    if value == "???":
        return None
    return _parse_float(value, 10.0)


def _value_temp1(data: MicroAQUAData | None, now: datetime) -> float | None:
    parts = _get_parts(data, now, 2)
    if not parts:
        return None
    return _parse_temp(parts[1])


def _value_temp2(data: MicroAQUAData | None, now: datetime) -> float | None:
    parts = _get_parts(data, now, 3)
    if not parts:
        return None
    return _parse_temp(parts[2])


def _value_temp3(data: MicroAQUAData | None, now: datetime) -> float | None:
    parts = _get_parts(data, now, 4)
    if not parts:
        return None
    return _parse_temp(parts[3])


def _value_temp4(data: MicroAQUAData | None, now: datetime) -> float | None:
    parts = _get_parts(data, now, 5)
    if not parts:
        return None
    return _parse_temp(parts[4])


def _value_co2_socket(data: MicroAQUAData | None, now: datetime) -> str | None:
    parts = _get_parts(data, now, 18)
    if not parts:
        return None
    if parts[17] == "0":
        if parts[9] == "7":
            return "brak przypisanego gniazda"
        return "OFF" if parts[10] == "0" else "ON"
    return "off"


def _value_o2_socket(data: MicroAQUAData | None, now: datetime) -> str | None:
    parts = _get_parts(data, now, 18)
    if not parts:
        return None
    if parts[17] == "0":
        if parts[11] == "7":
            return "brak przypisanego gniazda"
        return "off" if parts[12] == "0" else "on"
    return "off"


def _value_termoreg_socket(data: MicroAQUAData | None, now: datetime) -> str | None:
    parts = _get_parts(data, now, 18)
    if not parts:
        return None
    if parts[17] == "0":
        if parts[7] == "7":
            return "brak przypisanego gniazda"
        return "OFF" if parts[8] == "0" else "ON"
    return "off"


def _value_fan_controller(data: MicroAQUAData | None, now: datetime) -> str | None:
    parts = _get_parts(data, now, 18)
    if not parts:
        return None
    if parts[17] != "0":
        return "off"
    mode = parts[5]
    state = parts[6]
    if mode == "3":
        return "Moduł FAN wyłączony"
    if mode == "2":
        return "Praca okresowa: OFF" if state == "0" else "Praca okresowa: ON"
    if mode == "1":
        if state == "1":
            return "Regulacja mocy: Rozruch"
        if state == "2":
            return "Regulacja mocy: 20%"
        if state == "3":
            return "Regulacja mocy: 40%"
        if state == "4":
            return "Regulacja mocy: 60%"
        if state == "5":
            return "Regulacja mocy: 80%"
        if state == "6":
            return "Regulacja mocy: 100%"
        return "Regulacja mocy: OFF"
    return "Praca ON/OFF: OFF" if state == "0" else "Praca ON/OFF: ON"


def _value_led1(data: MicroAQUAData | None, now: datetime) -> int | None:
    parts = _get_parts(data, now, 14)
    if not parts:
        return None
    return _parse_int(parts[13])


def _value_led2(data: MicroAQUAData | None, now: datetime) -> int | None:
    parts = _get_parts(data, now, 15)
    if not parts:
        return None
    return _parse_int(parts[14])


def _value_led3(data: MicroAQUAData | None, now: datetime) -> int | None:
    parts = _get_parts(data, now, 16)
    if not parts:
        return None
    return _parse_int(parts[15])


def _value_led4(data: MicroAQUAData | None, now: datetime) -> int | None:
    parts = _get_parts(data, now, 17)
    if not parts:
        return None
    return _parse_int(parts[16])


def _value_temp_alarms(data: MicroAQUAData | None, now: datetime) -> str | None:
    parts = _get_parts(data, now, 19)
    if not parts:
        return None
    alarm_value = _parse_int(parts[18]) or 0
    if alarm_value & 1:
        return (
            "ALARM Temp MIN wyciszony"
            if alarm_value & 128
            else "ALARM Temp MIN"
        )
    if alarm_value & 2:
        return (
            "ALARM Temp MAX wyciszony"
            if alarm_value & 128
            else "ALARM Temp MAX"
        )
    return "---"


def _value_ph_alarms(data: MicroAQUAData | None, now: datetime) -> str | None:
    parts = _get_parts(data, now, 19)
    if not parts:
        return None
    alarm_value = _parse_int(parts[18]) or 0
    if alarm_value & 4:
        return (
            "ALARM pH MIN wyciszony" if alarm_value & 128 else "ALARM pH MIN"
        )
    if alarm_value & 8:
        return (
            "ALARM pH MAX wyciszony" if alarm_value & 128 else "ALARM pH MAX"
        )
    return "---"


def _value_acoustic_alarm_status(
    data: MicroAQUAData | None, now: datetime
) -> str | None:
    parts = _get_parts(data, now, 19)
    if not parts:
        return None
    alarm_value = _parse_int(parts[18]) or 0
    if alarm_value & 127:
        return "OFF" if alarm_value & 128 else "ON"
    return "OFF"


def _value_temp_alarm_min_value(
    data: MicroAQUAData | None, now: datetime
) -> str | None:
    parts = _get_parts(data, now, 23)
    if not parts:
        return None
    if parts[20] == "???":
        return None
    min_value = _parse_float(parts[20], 10.0)
    hyst = _parse_float(parts[22], 10.0)
    if min_value is None or hyst is None:
        return None
    return f"{min_value} +/-{hyst}"


def _value_temp_alarm_max_value(
    data: MicroAQUAData | None, now: datetime
) -> str | None:
    parts = _get_parts(data, now, 23)
    if not parts:
        return None
    if parts[21] == "???":
        return None
    max_value = _parse_float(parts[21], 10.0)
    hyst = _parse_float(parts[22], 10.0)
    if max_value is None or hyst is None:
        return None
    return f"{max_value} +/-{hyst}"


def _value_ph_alarm_min_value(
    data: MicroAQUAData | None, now: datetime
) -> str | None:
    parts = _get_parts(data, now, 26)
    if not parts:
        return None
    if parts[23] == "???":
        return None
    min_value = _parse_float(parts[23], 100.0)
    hyst = _parse_float(parts[25], 100.0)
    if min_value is None or hyst is None:
        return None
    return f"{min_value} +/-{hyst} pH"


def _value_ph_alarm_max_value(
    data: MicroAQUAData | None, now: datetime
) -> str | None:
    parts = _get_parts(data, now, 26)
    if not parts:
        return None
    if parts[24] == "???":
        return None
    max_value = _parse_float(parts[24], 100.0)
    hyst = _parse_float(parts[25], 100.0)
    if max_value is None or hyst is None:
        return None
    return f"{max_value} +/-{hyst} pH"


def _value_data_update_time_stamp_test(
    data: MicroAQUAData | None, now: datetime
) -> str | None:
    parts = _get_parts(data, now, 20)
    if not parts:
        return None
    return parts[19]


def _value_no_reg_time(data: MicroAQUAData | None, now: datetime) -> str | None:
    parts = _get_parts(data, now, 18)
    if not parts:
        return None
    value = parts[17]
    return "--" if value == "0" else f"{value}min"
