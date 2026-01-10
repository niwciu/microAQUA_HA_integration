from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    master = hass.data[DOMAIN][entry.entry_id]["master"]
    async_add_entities([NoRegTimeMinutes(master)], True)


class NoRegTimeMinutes(NumberEntity):
    """Number: minutes for AT+TCPENRM;<minutes>."""

    _attr_has_entity_name = True
    _attr_name = "No regulation time (set)"
    _attr_native_min_value = 0
    _attr_native_max_value = 240
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:timer-cog"

    def __init__(self, master):
        self._m = master
        self._native_value = 0  # domyślnie

        # zsynchronizuj master z wartością początkową
        self._m._no_reg_set_minutes = self._native_value

    @property
    def unique_id(self) -> str:
        return f"{self._m.unique_id}_no_reg_time_set"

    @property
    def device_info(self):
        return self._m.device_info

    @property
    def native_value(self):
        return self._native_value

    async def async_set_native_value(self, value: float) -> None:
        self._native_value = int(round(value))

        # KLUCZOWE: zapisz też w masterze, żeby button nie musiał niczego szukać w registry
        self._m._no_reg_set_minutes = self._native_value

        self.async_write_ha_state()
