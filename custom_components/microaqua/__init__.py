from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import CONF_PAYLOAD, DEFAULT_NAME, DEFAULT_PAYLOAD, DEFAULT_PORT, DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up microAQUA from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload microAQUA config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry data to the latest schema."""
    if entry.version >= 2:
        return True

    data = dict(entry.data)
    if "ip" in data:
        data[CONF_HOST] = data.pop("ip")
    data.setdefault(CONF_HOST, "")
    data.setdefault(CONF_NAME, DEFAULT_NAME)
    data.setdefault(CONF_PORT, DEFAULT_PORT)
    data.setdefault(CONF_PAYLOAD, DEFAULT_PAYLOAD)

    hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True
