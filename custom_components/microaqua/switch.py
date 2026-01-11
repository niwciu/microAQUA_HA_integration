from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_state_change_event

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
    _attr_should_poll = False

    def __init__(self, master):
        self._m = master
        self._unsub_state = None

    @property
    def device_info(self):
        return self._m.device_info

    @property
    def available(self) -> bool:
        return self._m.available

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._m.entity_id:
            self._unsub_state = async_track_state_change_event(
                self.hass,
                [self._m.entity_id],
                self._handle_master_state_change,
            )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None

    @callback
    def _handle_master_state_change(self, _event) -> None:
        self.async_write_ha_state()


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

    def _alarm_register(self) -> int:
        raw = self._m.get_part(18)
        if raw is None:
            return 0
        try:
            return int(raw)
        except ValueError:
            return 0

    @property
    def available(self) -> bool:
        return self._m.available and self._m.parts_length() > 18

    @property
    def is_on(self) -> bool:
        if not self.available:
            return False
        value = self._alarm_register()
        return (value & 128) != 128 and (value & 127) != 0

    @property
    def icon(self) -> str:
        value = self._alarm_register()
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
