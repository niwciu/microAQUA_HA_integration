"""Switch platform for microAQUA."""
from __future__ import annotations

import asyncio
import logging
import socket

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN, TIMEOUT
from .models import MicroAQUACommandState
from .sensor import MicroAQUAData
from .utils import device_info_from_entry, host_port_from_entry, unique_id_prefix

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the switch platform from a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    if not entry_data or "coordinator" not in entry_data:
        raise ConfigEntryNotReady("Coordinator not initialized")

    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)
    unique_prefix = unique_id_prefix(name)
    coordinator = entry_data["coordinator"]
    command_state: MicroAQUACommandState = entry_data["command_state"]

    async_add_entities(
        [
            NoRegSwitch(
                coordinator,
                config_entry,
                name,
                unique_prefix,
                command_state,
            ),
            DisarmSoundAlarmSwitch(
                coordinator,
                config_entry,
                name,
                unique_prefix,
            ),
        ]
    )


class MicroAQUABaseSwitch(CoordinatorEntity, SwitchEntity):
    """Base switch entity for microAQUA."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, config_entry, name, unique_prefix) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_name = name
        self._unique_prefix = unique_prefix

    @property
    def device_info(self):
        return device_info_from_entry(self._config_entry, self._device_name)

    def _data_parts(self) -> tuple[str, ...] | None:
        data: MicroAQUAData | None = self.coordinator.data
        if data is None or data.raw_payload in (None, "", "unknown"):
            return None
        return data.parts

    async def _async_send_command(self, command: str) -> None:
        host, port = host_port_from_entry(self._config_entry)
        if not host or not port:
            raise ConfigEntryNotReady("Missing host/port in configuration")

        await asyncio.to_thread(self._send_command, host, port, command)

    @staticmethod
    def _send_command(host: str, port: int, command: str) -> None:
        with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
            sock.sendall(command.encode("utf-8"))


class NoRegSwitch(MicroAQUABaseSwitch):
    """Switch for regulation on/off (no regulation mode)."""

    def __init__(
        self,
        coordinator,
        config_entry,
        name: str,
        unique_prefix: str,
        command_state: MicroAQUACommandState,
    ) -> None:
        super().__init__(coordinator, config_entry, name, unique_prefix)
        self._command_state = command_state
        self._attr_unique_id = f"{unique_prefix}_no_reg"
        self._attr_name = "Regulacja ON/OFF"

    @property
    def available(self) -> bool:
        parts = self._data_parts()
        return parts is not None and len(parts) > 17

    @property
    def is_on(self) -> bool:
        parts = self._data_parts()
        if parts is None or len(parts) <= 17:
            return False
        return parts[17] != "0"

    @property
    def icon(self) -> str:
        parts = self._data_parts()
        if parts is None or len(parts) <= 17:
            return "hass:power-plug"
        return "hass:power-plug" if parts[17] == "0" else "hass:power-plug-off"

    async def async_turn_on(self, **kwargs) -> None:
        command = f"AT+TCPENRM;{self._command_state.no_reg_time}\r\n"
        await self._async_send_command(command)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_send_command("AT+TCPLNRM\r\n")
        await self.coordinator.async_request_refresh()


class DisarmSoundAlarmSwitch(MicroAQUABaseSwitch):
    """Switch for disarming the sound alarm."""

    def __init__(self, coordinator, config_entry, name: str, unique_prefix: str) -> None:
        super().__init__(coordinator, config_entry, name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_disarm_sound_alarm"
        self._attr_name = "Wyłącz Alarm Dźwiękowy"

    @property
    def available(self) -> bool:
        parts = self._data_parts()
        return parts is not None and len(parts) > 18

    @property
    def is_on(self) -> bool:
        parts = self._data_parts()
        if parts is None or len(parts) <= 18:
            return False
        alarm_value = _parse_int(parts[18]) or 0
        return (alarm_value & 128) != 128 and (alarm_value & 127) != 0

    @property
    def icon(self) -> str:
        parts = self._data_parts()
        if parts is None or len(parts) <= 18:
            return "hass:volume-off"
        alarm_value = _parse_int(parts[18]) or 0
        if alarm_value & 127:
            return "hass:volume-off" if alarm_value & 128 else "hass:volume-high"
        return "hass:volume-off"

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_send_command("AT+TCPTOA\r\n")
        await self.coordinator.async_request_refresh()



def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        _LOGGER.debug("Unable to parse integer from %s", value)
        return None
