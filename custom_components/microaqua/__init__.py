from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_PAYLOAD, DEFAULT_NAME, DEFAULT_PAYLOAD, DEFAULT_PORT, DOMAIN
from .models import MicroAQUACommandState
from .sensor import MicroAQUADataUpdateCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up microAQUA from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data.get(CONF_HOST) or entry.data.get("ip")
    if not host:
        raise ConfigEntryNotReady("Missing host/IP address in configuration")
    port = entry.data.get(CONF_PORT, entry.data.get("port", DEFAULT_PORT))
    payload = entry.data.get(CONF_PAYLOAD, entry.data.get("payload", DEFAULT_PAYLOAD))

    coordinator = MicroAQUADataUpdateCoordinator(hass, host, port, payload)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "command_state": MicroAQUACommandState(),
    }
    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "switch", "number"]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload microAQUA config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        entry, ["sensor", "switch", "number"]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
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
