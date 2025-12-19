"""Custom integration to add Smart Controller to Home Assistant.

For more details about this integration, please refer to
https://github.com/lymanepp/ha-smart-controller
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, Event, HomeAssistant

from .ceiling_fan_controller import CeilingFanController
from .const import Config, ControllerType
from .exhaust_fan_controller import ExhaustFanController
from .light_controller import LightController
from .occupancy_controller import OccupancyController
from .smart_controller import SmartController

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR]


@dataclass
class ControllerData:
    controller: SmartController


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[ControllerData]
) -> bool:
    """Set up this integration using UI."""
    _LOGGER.debug("Setting up integration: %s", entry.entry_id)

    if (controller := _create_controller(hass, entry)) is None:
        _LOGGER.error("Failed to create controller for entry: %s", entry.entry_id)
        return False

    entry.runtime_data.controller = controller

    async def start_controller(_: Event | None = None):
        if controller.is_setup:
            _LOGGER.warning("Controller already started for entry: %s", entry.entry_id)
            return
        _LOGGER.debug("Starting controller for entry: %s", entry.entry_id)
        await controller.async_setup(hass)
        controller.is_setup = True  # Mark as started

    if hass.state == CoreState.running:
        await start_controller()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_controller)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry[ControllerData]
) -> bool:
    """Handle removal of an entry."""
    _LOGGER.debug("Unloading integration: %s", entry.entry_id)

    controller = entry.runtime_data.controller
    if controller:
        _LOGGER.debug("Calling async_unload for controller: %s", entry.entry_id)
        controller.async_unload()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.debug("Reloading integration: %s", entry.entry_id)
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


# #### Internal functions ####


def _create_controller(
    hass: HomeAssistant, entry: ConfigEntry[ControllerData]
) -> SmartController | None:
    """Factory method to create the appropriate controller."""
    type_ = entry.data.get(Config.CONTROLLER_TYPE)

    match type_:
        case ControllerType.CEILING_FAN:
            return CeilingFanController(hass, entry)
        case ControllerType.EXHAUST_FAN:
            return ExhaustFanController(hass, entry)
        case ControllerType.LIGHT:
            return LightController(hass, entry)
        case ControllerType.OCCUPANCY:
            return OccupancyController(hass, entry)

    _LOGGER.error("Invalid controller type: %s", type_)
    return None
