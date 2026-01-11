from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    master = hass.data[DOMAIN][entry.entry_id]["master"]
    async_add_entities(
        [
            RegulationOnOffSwitch(master),
            DisarmSoundAlarmSwitch(master),
        ],
        True,
    )


class _MicroAquaSwitch(SwitchEntity):
    _attr_has_entity_name = False

    def __init__(self, master):
        self._m = master

    @property
    def device_info(self):
        return self._m.device_info

    @property
    def available(self) -> bool:
        return self._m.available


class RegulationOnOffSwitch(_MicroAquaSwitch):
    _attr_name = "Regulacja ON/OFF"

    @property
    def unique_id(self) -> str:
        return f"{self._m.entity_prefix}_regulation_on_off"

    @property
    def available(self) -> bool:
        return self._m.available and self._m.parts_length() > 17

    @property
    def is_on(self) -> bool:
        if not self.available:
            return False
        value = self._m.get_part(17)
        return value is not None and value != "0"

    @property
    def icon(self) -> str:
        if self._m.get_part(17) == "0":
            return "hass:power-plug"
        return "hass:power-plug-off"

    async def async_turn_on(self, **kwargs) -> None:
        try:
            minutes = int(getattr(self._m, "_no_reg_set_minutes", 0))
            await self._m.async_send_command(f"AT+TCPENRM;{minutes}")
            await self._m.async_update()
        except Exception as e:
            _LOGGER.error("Failed to set regulation ON: %s", e)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self._m.async_send_command("AT+TCPLNRM")
            await self._m.async_update()
        except Exception as e:
            _LOGGER.error("Failed to set regulation OFF: %s", e)


class DisarmSoundAlarmSwitch(_MicroAquaSwitch):
    _attr_name = "Wyłącz Alarm Dźwiękowy"

    @property
    def unique_id(self) -> str:
        return f"{self._m.entity_prefix}_disarm_sound_alarm"

    @property
    def available(self) -> bool:
        return self._m.available and self._m.parts_length() > 18

    @property
    def is_on(self) -> bool:
        if not self.available:
            return False
        raw = self._m.get_part(18)
        if raw is None:
            return False
        value = int(raw)
        return (value & 128) != 128 and (value & 127) != 0

    @property
    def icon(self) -> str:
        raw = self._m.get_part(18)
        if raw is None:
            return "hass:volume-off"
        value = int(raw)
        if (value & 127) != 0:
            return "hass:volume-off" if (value & 128) == 128 else "hass:volume-high"
        return "hass:volume-off"

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self._m.async_send_command("AT+TCPTOA")
            await self._m.async_update()
        except Exception as e:
            _LOGGER.error("Failed to disarm sound alarm: %s", e)

    async def async_turn_on(self, **kwargs) -> None:
        _LOGGER.debug("Sound alarm switch does not support turn_on.")
