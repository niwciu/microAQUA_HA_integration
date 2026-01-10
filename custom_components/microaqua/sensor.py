"""Sensor platform for microAQUA."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import time
import logging
import socket
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_PAYLOAD,
    DEFAULT_NAME,
    DEFAULT_PAYLOAD,
    DEFAULT_PORT,
    DOMAIN,
    SCAN_INTERVAL,
    TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MicroAQUAData:
    """Parsed data from the microAQUA controller."""

    ph: float | None
    temperatures: tuple[float | None, ...]
    leds: tuple[int | None, ...]
    last_update_time: str | None


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
        except (OSError, asyncio.TimeoutError, ValueError) as err:
            raise UpdateFailed(f"Unable to fetch data from {self._host}") from err

    def _fetch_data(self) -> str:
        with socket.create_connection((self._host, self._port), timeout=TIMEOUT) as sock:
            sock.sendall(self._payload.encode("utf-8"))
            response = sock.recv(1024)
        return response.decode("utf-8").strip()

    def _parse_payload(self, data: str) -> MicroAQUAData:
        if self._expected_prefix not in data:
            raise ValueError("Unexpected payload prefix")
        start_index = data.find(self._expected_prefix)
        payload = data[start_index + len(self._expected_prefix) :]
        parts = payload.split(";")
        if len(parts) < 23:
            raise ValueError("Incomplete payload")

        ph_value = _parse_float(parts[0], 100.0)
        temperatures = tuple(
            _parse_float(value, 10.0)
            for value in (parts[1:5] + parts[20:23])
        )
        leds = tuple(_parse_int(value) for value in parts[13:17])
        last_update_time = _parse_time(parts[19])

        return MicroAQUAData(
            ph=ph_value,
            temperatures=temperatures,
            leds=leds,
            last_update_time=last_update_time,
        )


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

    coordinator = MicroAQUADataUpdateCoordinator(hass, host, port, payload)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            PHSensor(coordinator, config_entry, name),
            TempSensor(coordinator, config_entry, name, "Temp 1", 0),
            TempSensor(coordinator, config_entry, name, "Temp 2", 1),
            TempSensor(coordinator, config_entry, name, "Temp 3", 2),
            TempSensor(coordinator, config_entry, name, "Temp 4", 3),
            LEDSensor(coordinator, config_entry, name, 1),
            LEDSensor(coordinator, config_entry, name, 2),
            LEDSensor(coordinator, config_entry, name, 3),
            LEDSensor(coordinator, config_entry, name, 4),
            LastUpdateTimeSensor(coordinator, config_entry, name),
            TempSensor(
                coordinator,
                config_entry,
                name,
                "Alarm Temp min",
                4,
                icon="mdi:thermometer-alert",
            ),
            TempSensor(
                coordinator,
                config_entry,
                name,
                "Alarm Temp max",
                5,
                icon="mdi:thermometer-alert",
            ),
            TempSensor(
                coordinator,
                config_entry,
                name,
                "Alarm Temp hysteresis",
                6,
                icon="mdi:thermometer-alert",
            ),
        ]
    )


class MicroAQUABaseEntity(CoordinatorEntity[MicroAQUAData]):
    """Base entity for microAQUA entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MicroAQUADataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_name = name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=self._device_name,
            manufacturer="microAQUA",
            model="microAQUA",
            configuration_url=f"tcp://{self._config_entry.data[CONF_HOST]}:{self._config_entry.data[CONF_PORT]}",
        )


class PHSensor(MicroAQUABaseEntity, SensorEntity):
    """Representation of pH value from microAQUA Sensor."""

    _attr_native_unit_of_measurement: Final = "pH"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: MicroAQUADataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
    ) -> None:
        super().__init__(coordinator, config_entry, name)
        self._attr_unique_id = f"{config_entry.entry_id}_ph"
        self._attr_name = "pH"
        self._attr_icon = "mdi:ph"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.ph


class TempSensor(MicroAQUABaseEntity, SensorEntity):
    """Representation of a temperature value from microAQUA Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: MicroAQUADataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        label: str,
        index: int,
        icon: str | None = None,
    ) -> None:
        super().__init__(coordinator, config_entry, name)
        self._index = index
        self._attr_unique_id = f"{config_entry.entry_id}_temp_{index}"
        self._attr_name = label
        if icon:
            self._attr_icon = icon

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.temperatures[self._index]


class LEDSensor(MicroAQUABaseEntity, SensorEntity):
    """Representation of a LED value from microAQUA Sensor."""

    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: MicroAQUADataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        index: int,
    ) -> None:
        super().__init__(coordinator, config_entry, name)
        self._index = index - 1
        self._attr_unique_id = f"{config_entry.entry_id}_led_{index}"
        self._attr_name = f"LED {index}"
        self._attr_icon = "mdi:led-on"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.leds[self._index]


class LastUpdateTimeSensor(MicroAQUABaseEntity, SensorEntity):
    """Representation of Last Update Time from microAQUA Sensor."""

    _attr_icon = "mdi:update"

    def __init__(
        self,
        coordinator: MicroAQUADataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
    ) -> None:
        super().__init__(coordinator, config_entry, name)
        self._attr_unique_id = f"{config_entry.entry_id}_last_update_time"
        self._attr_name = "Last Update Time"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.last_update_time


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


def _parse_time(value: str) -> str | None:
    try:
        return time.fromisoformat(value).strftime("%H:%M:%S")
    except ValueError:
        return None
