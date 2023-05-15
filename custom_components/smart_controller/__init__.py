"""Custom integration to add Smart Controller to Home Assistant.

For more details about this integration, please refer to
https://github.com/lymanepp/ha-smart-controller
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, CoreState, Event, HomeAssistant

from .base_controller import BaseController
from .ceiling_fan_controller import CeilingFanController
from .const import DOMAIN, CommonConfig, ControllerType
from .exhaust_fan_controller import ExhaustFanController
from .light_controller import LightController


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    if (controller := _create_controller(hass, config_entry)) is None:
        return False

    async def start_controller(_: Event = None):
        domain_data[config_entry.unique_id] = await controller.async_setup(hass)

    if hass.state == CoreState.running:
        await start_controller()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_controller)

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    listener_remover: CALLBACK_TYPE = hass.data[DOMAIN].pop(config_entry.unique_id)
    listener_remover()
    return True


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)


def _create_controller(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> BaseController | None:
    match config_entry.data[CommonConfig.TYPE]:
        case ControllerType.LIGHT:
            return LightController(hass, config_entry)

        case ControllerType.CEILING_FAN:
            return CeilingFanController(hass, config_entry)

        case ControllerType.EXHAUST_FAN:
            return ExhaustFanController(hass, config_entry)

        case _:
            return None
