"""Sensor platform for integration_blueprint."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ControllerData
from .const import Config, ControllerType
from .entity import SmartControllerEntity
from .smart_controller import SmartController

_LOGGER = logging.getLogger(__name__)

ENTITY_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key=ControllerType.OCCUPANCY,
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:account",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[ControllerData],
    async_add_entities: AddEntitiesCallback,
):
    """Set up the sensor platform."""
    controller = entry.runtime_data.controller
    type_ = entry.data.get(Config.CONTROLLER_TYPE)

    _LOGGER.debug("Binary sensor type from config: %s", type_)
    _LOGGER.debug(
        "Available entity descriptions: %s", [desc.key for desc in ENTITY_DESCRIPTIONS]
    )

    async_add_entities(
        [
            SmartControllerBinarySensor(
                controller=controller,
                entity_description=entity_description,
                name=entry.title,
            )
            for entity_description in ENTITY_DESCRIPTIONS
            if entity_description.key == type_
        ]
    )


class SmartControllerBinarySensor(SmartControllerEntity, BinarySensorEntity):
    """Smart Controller Binary Sensor class."""

    def __init__(
        self,
        controller: SmartController,
        entity_description: BinarySensorEntityDescription,
        name: str,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(controller)
        self.entity_description = entity_description
        self._attr_name = name

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self.controller.is_on
