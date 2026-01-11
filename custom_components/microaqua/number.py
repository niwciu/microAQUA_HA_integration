"""Number platform for microAQUA."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .const import DEFAULT_NAME, DOMAIN
from .models import MicroAQUACommandState
from .utils import device_info_from_entry, unique_id_prefix


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the number platform from a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    if not entry_data:
        return

    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)
    unique_prefix = unique_id_prefix(name)
    command_state: MicroAQUACommandState = entry_data["command_state"]

    async_add_entities(
        [
            NoRegTimeNumber(
                config_entry,
                name,
                unique_prefix,
                command_state,
            )
        ]
    )


class NoRegTimeNumber(NumberEntity):
    """Number entity for the no regulation time."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 240
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"

    def __init__(
        self,
        config_entry: ConfigEntry,
        name: str,
        unique_prefix: str,
        command_state: MicroAQUACommandState,
    ) -> None:
        self._config_entry = config_entry
        self._device_name = name
        self._command_state = command_state
        self._attr_unique_id = f"{unique_prefix}_set_no_reg_time"
        self._attr_name = "Ustaw czas bez regulaji"

    @property
    def device_info(self):
        return device_info_from_entry(self._config_entry, self._device_name)

    @property
    def native_value(self) -> float:
        return float(self._command_state.no_reg_time)

    async def async_set_native_value(self, value: float) -> None:
        self._command_state.no_reg_time = int(round(value))
        self.async_write_ha_state()
