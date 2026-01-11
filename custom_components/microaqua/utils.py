from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify

from .const import DOMAIN


def unique_id_prefix(name: str) -> str:
    raw = name.lower().replace("microaqua", "uaqua")
    return slugify(raw) or "uaqua"


def device_info_from_entry(config_entry, name: str) -> DeviceInfo:
    host = config_entry.data.get(CONF_HOST) or config_entry.data.get("ip")
    port = config_entry.data.get(CONF_PORT, config_entry.data.get("port"))
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=name,
        manufacturer="microAQUA",
        model="microAQUA",
        configuration_url=f"tcp://{host}:{port}",
    )


def host_port_from_entry(config_entry) -> tuple[str | None, int | None]:
    host = config_entry.data.get(CONF_HOST) or config_entry.data.get("ip")
    port = config_entry.data.get(CONF_PORT, config_entry.data.get("port"))
    return host, port
