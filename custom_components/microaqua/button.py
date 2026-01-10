from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    master = hass.data[DOMAIN][entry.entry_id]["master"]
    async_add_entities(
        [
            DisarmSoundAlarmButton(master),
            NoRegOffButton(master),
            NoRegOnButton(master),
        ],
        True,
    )


class _MicroAquaButton(ButtonEntity):
    """Base: attached to microAQUA device."""

    _attr_has_entity_name = True

    def __init__(self, master):
        self._m = master

    @property
    def device_info(self):
        return self._m.device_info


class DisarmSoundAlarmButton(_MicroAquaButton):
    _attr_name = "Disarm sound alarm"
    _attr_icon = "mdi:volume-off"

    @property
    def unique_id(self) -> str:
        return f"{self._m.unique_id}_btn_disarm_sound_alarm"

    async def async_press(self) -> None:
        try:
            # AT+TCPTOA
            await self._m.async_send_command("AT+TCPTOA")
            await self._m.async_update()
        except Exception as e:
            _LOGGER.error("Failed to disarm sound alarm: %s", e)


class NoRegOffButton(_MicroAquaButton):
    _attr_name = "No regulation OFF"
    _attr_icon = "mdi:power-plug-off"

    @property
    def unique_id(self) -> str:
        return f"{self._m.unique_id}_btn_no_reg_off"

    async def async_press(self) -> None:
        try:
            # AT+TCPLNRM
            await self._m.async_send_command("AT+TCPLNRM")
            await self._m.async_update()
        except Exception as e:
            _LOGGER.error("Failed to set no-reg OFF: %s", e)


class NoRegOnButton(_MicroAquaButton):
    _attr_name = "No regulation ON"
    _attr_icon = "mdi:power-plug"

    @property
    def unique_id(self) -> str:
        return f"{self._m.unique_id}_btn_no_reg_on"

    async def async_press(self) -> None:
        try:
            minutes = int(getattr(self._m, "_no_reg_set_minutes", 0))
            # AT+TCPENRM;<minutes>
            await self._m.async_send_command(f"AT+TCPENRM;{minutes}")
            await self._m.async_update()
        except Exception as e:
            _LOGGER.error("Failed to set no-reg ON: %s", e)
