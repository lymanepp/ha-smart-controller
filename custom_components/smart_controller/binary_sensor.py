"""Sensor platform for integration_blueprint."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CommonConfig, ControllerType
from .entity import SmartControllerEntity
from .smart_controller import SmartController

ENTITY_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key=ControllerType.OCCUPANCY,
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:account",
    ),
]


async def async_setup_entry(
    hass, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the sensor platform."""
    controller = hass.data[DOMAIN][config_entry.entry_id]
    controller_type = config_entry.data[CommonConfig.TYPE]

    for entity_description in ENTITY_DESCRIPTIONS:
        if entity_description.key == controller_type:
            entity_description.name = config_entry.title
            async_add_entities(
                [
                    SmartControllerBinarySensor(
                        controller=controller,
                        entity_description=entity_description,
                    )
                ]
            )


class SmartControllerBinarySensor(SmartControllerEntity, BinarySensorEntity):
    """Smart Controller Binary Sensor class."""

    def __init__(
        self,
        controller: SmartController,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(controller)
        self.entity_description = entity_description

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self.controller.is_on
