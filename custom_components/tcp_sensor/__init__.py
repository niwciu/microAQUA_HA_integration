from homeassistant.core import HomeAssistant

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    return True
