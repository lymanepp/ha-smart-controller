"""Adds config flow for Light Controller."""
from __future__ import annotations

from collections.abc import MutableMapping
from typing import Final

import voluptuous as vol
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.fan import ATTR_PERCENTAGE_STEP
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import selector
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    DEFAULT_CEILING_SSI_MAX_FAHRENHEIT,
    DEFAULT_CEILING_SSI_MIN_FAHRENHEIT,
    DEFAULT_EXHAUST_FALLING_THRESHOLD,
    DEFAULT_EXHAUST_MANUAL_MINUTES,
    DEFAULT_EXHAUST_RISING_THRESHOLD,
    DOMAIN,
    GRAMS_PER_CUBIC_METER,
    CeilingFanConfig,
    CommonConfig,
    ExhaustFanConfig,
    LightConfig,
    OccupancyConfig,
)
from .util import domain_entities, on_off_entities

ErrorsType = MutableMapping[str, str]

FAN_TYPE: Final = "fan_type"


def make_controlled_entity_schema(
    hass: HomeAssistant, user_input: ConfigType, domain: str
) -> vol.Schema:
    """Create 'controlled_entity' config schema."""

    entities = domain_entities(hass, domain)
    entities.difference_update(_existing_controlled_entities(hass))
    entities = sorted(entities)

    if not entities:
        raise AbortFlow("nothing_to_control")

    return vol.Schema(
        {
            vol.Required(
                str(CommonConfig.CONTROLLED_ENTITY),
                default=user_input.get(CommonConfig.CONTROLLED_ENTITY, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=entities),
            ),
        }
    )


def make_ceiling_fan_schema(
    hass: HomeAssistant, user_input: ConfigType, controlled_entity: str
) -> vol.Schema:
    """Create 'ceiling_fan' config schema."""

    temp_sensors = domain_entities(
        hass,
        [Platform.SENSOR],
        device_classes=SensorDeviceClass.TEMPERATURE,
        units_of_measurement=[
            None,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
        ],
    )

    humidity_sensors = domain_entities(
        hass,
        [Platform.SENSOR],
        device_classes=SensorDeviceClass.HUMIDITY,
        units_of_measurement=[None, PERCENTAGE],
    )

    required_entities = domain_entities(
        hass, [Platform.BINARY_SENSOR, INPUT_BOOLEAN_DOMAIN]
    ) | on_off_entities(hass, [Platform.FAN])

    fan_state = hass.states.get(controlled_entity)
    assert fan_state
    speed_step = fan_state.attributes.get(ATTR_PERCENTAGE_STEP, 100)

    default_ssi_min = TemperatureConverter.convert(
        DEFAULT_CEILING_SSI_MIN_FAHRENHEIT,
        UnitOfTemperature.FAHRENHEIT,
        hass.config.units.temperature_unit,
    )

    default_ssi_max = TemperatureConverter.convert(
        DEFAULT_CEILING_SSI_MAX_FAHRENHEIT,
        UnitOfTemperature.FAHRENHEIT,
        hass.config.units.temperature_unit,
    )

    ssi_selector = selector.NumberSelector(
        selector.NumberSelectorConfig(
            unit_of_measurement=hass.config.units.temperature_unit,
            mode=selector.NumberSelectorMode.BOX,
        ),
    )

    speed_selector = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            step=speed_step,
            unit_of_measurement=PERCENTAGE,
            mode=selector.NumberSelectorMode.SLIDER,
        ),
    )

    minutes_selector = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=60,
            unit_of_measurement="minutes",
            mode=selector.NumberSelectorMode.SLIDER,
        ),
    )

    return vol.Schema(
        {
            # temperature sensor
            vol.Required(
                CeilingFanConfig.TEMP_SENSOR,
                default=user_input.get(CeilingFanConfig.TEMP_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=list(temp_sensors)),
            ),
            # humidity sensor
            vol.Required(
                str(CeilingFanConfig.HUMIDITY_SENSOR),
                default=user_input.get(CeilingFanConfig.HUMIDITY_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=list(humidity_sensors)),
            ),
            # minimum SSI
            vol.Required(
                str(CeilingFanConfig.SSI_MIN),
                default=user_input.get(
                    CeilingFanConfig.SSI_MIN, round(default_ssi_min, 1)
                ),
            ): ssi_selector,
            # maximum SSI
            vol.Required(
                str(CeilingFanConfig.SSI_MAX),
                default=user_input.get(
                    CeilingFanConfig.SSI_MAX, round(default_ssi_max, 1)
                ),
            ): ssi_selector,
            # minimum fan speed
            vol.Required(
                str(CeilingFanConfig.SPEED_MIN),
                default=user_input.get(CeilingFanConfig.SPEED_MIN, vol.UNDEFINED),
            ): speed_selector,
            # maximum fan speed
            vol.Required(
                str(CeilingFanConfig.SPEED_MAX),
                default=user_input.get(CeilingFanConfig.SPEED_MAX, vol.UNDEFINED),
            ): speed_selector,
            # required on entities
            vol.Optional(
                str(CeilingFanConfig.REQUIRED_ON_ENTITIES),
                default=user_input.get(
                    CeilingFanConfig.REQUIRED_ON_ENTITIES, vol.UNDEFINED
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    include_entities=list(required_entities), multiple=True
                ),
            ),
            # required off entities
            vol.Optional(
                str(CeilingFanConfig.REQUIRED_OFF_ENTITIES),
                default=user_input.get(
                    CeilingFanConfig.REQUIRED_OFF_ENTITIES, vol.UNDEFINED
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    include_entities=list(required_entities), multiple=True
                ),
            ),
            # manual control minutes (optional)
            vol.Optional(
                str(ExhaustFanConfig.MANUAL_CONTROL_MINUTES),
                default=user_input.get(
                    ExhaustFanConfig.MANUAL_CONTROL_MINUTES,
                    vol.UNDEFINED,
                ),
            ): vol.All(minutes_selector, vol.Coerce(int)),
        }
    )


def make_exhaust_fan_schema(hass: HomeAssistant, user_input: ConfigType) -> vol.Schema:
    """Create 'exhaust_fan' config schema."""

    temp_sensors = domain_entities(
        hass,
        [Platform.SENSOR],
        device_classes=SensorDeviceClass.TEMPERATURE,
        units_of_measurement=[
            None,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
        ],
    )

    humidity_sensors = domain_entities(
        hass,
        [Platform.SENSOR],
        device_classes=SensorDeviceClass.HUMIDITY,
        units_of_measurement=[None, PERCENTAGE],
    )

    abs_humidity_selector = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0.0,
            max=5.0,
            step=0.1,
            unit_of_measurement=GRAMS_PER_CUBIC_METER,
            mode=selector.NumberSelectorMode.SLIDER,
        ),
    )

    minutes_selector = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=60,
            unit_of_measurement="minutes",
            mode=selector.NumberSelectorMode.SLIDER,
        ),
    )

    return vol.Schema(
        {
            # temperature sensor
            vol.Required(
                str(ExhaustFanConfig.TEMP_SENSOR),
                default=user_input.get(ExhaustFanConfig.TEMP_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=list(temp_sensors)),
            ),
            # humidity sensor
            vol.Required(
                str(ExhaustFanConfig.HUMIDITY_SENSOR),
                default=user_input.get(ExhaustFanConfig.HUMIDITY_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=list(humidity_sensors)),
            ),
            # reference temperature sensor
            vol.Required(
                str(ExhaustFanConfig.REFERENCE_TEMP_SENSOR),
                default=user_input.get(
                    ExhaustFanConfig.REFERENCE_TEMP_SENSOR, vol.UNDEFINED
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=list(temp_sensors)),
            ),
            # reference humidity sensor
            vol.Required(
                str(ExhaustFanConfig.REFERENCE_HUMIDITY_SENSOR),
                default=user_input.get(
                    ExhaustFanConfig.REFERENCE_HUMIDITY_SENSOR, vol.UNDEFINED
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=list(humidity_sensors)),
            ),
            # rising threshold
            vol.Required(
                str(ExhaustFanConfig.RISING_THRESHOLD),
                default=user_input.get(
                    ExhaustFanConfig.RISING_THRESHOLD, DEFAULT_EXHAUST_RISING_THRESHOLD
                ),
            ): abs_humidity_selector,
            # falling threshold
            vol.Required(
                str(ExhaustFanConfig.FALLING_THRESHOLD),
                default=user_input.get(
                    ExhaustFanConfig.FALLING_THRESHOLD,
                    DEFAULT_EXHAUST_FALLING_THRESHOLD,
                ),
            ): abs_humidity_selector,
            # manual control minutes
            vol.Optional(
                str(ExhaustFanConfig.MANUAL_CONTROL_MINUTES),
                default=user_input.get(
                    ExhaustFanConfig.MANUAL_CONTROL_MINUTES,
                    DEFAULT_EXHAUST_MANUAL_MINUTES,
                ),
            ): vol.All(minutes_selector, vol.Coerce(int)),
        }
    )


def make_light_schema(hass: HomeAssistant, user_input: ConfigType) -> vol.Schema:
    """Create 'light' config schema."""

    illuminance_sensors = domain_entities(
        hass,
        [Platform.SENSOR],
        device_classes=SensorDeviceClass.ILLUMINANCE,
    )

    required_entities = domain_entities(
        hass, [Platform.BINARY_SENSOR, INPUT_BOOLEAN_DOMAIN]
    )

    minutes_selector = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=60,
            unit_of_measurement="minutes",
            mode=selector.NumberSelectorMode.SLIDER,
        ),
    )

    illuminance_selector = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            mode=selector.NumberSelectorMode.BOX,
        ),
    )

    return vol.Schema(
        {
            # required 'on' entities
            vol.Optional(
                str(LightConfig.REQUIRED_ON_ENTITIES),
                default=user_input.get(LightConfig.REQUIRED_ON_ENTITIES, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    include_entities=list(required_entities), multiple=True
                ),
            ),
            # required 'off' entities
            vol.Optional(
                str(LightConfig.REQUIRED_OFF_ENTITIES),
                default=user_input.get(LightConfig.REQUIRED_OFF_ENTITIES, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    include_entities=list(required_entities), multiple=True
                ),
            ),
            # auto off minutes
            vol.Optional(
                str(LightConfig.AUTO_OFF_MINUTES),
                default=user_input.get(LightConfig.AUTO_OFF_MINUTES, vol.UNDEFINED),
            ): vol.All(minutes_selector, vol.Coerce(int)),
            # illuminance sensor
            vol.Inclusive(
                str(LightConfig.ILLUMINANCE_SENSOR),
                "illumininance",
                default=user_input.get(LightConfig.ILLUMINANCE_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=list(illuminance_sensors)),
            ),
            # illuminance threshold
            vol.Inclusive(
                str(LightConfig.ILLUMINANCE_CUTOFF),
                "illumininance",
                default=user_input.get(LightConfig.ILLUMINANCE_CUTOFF, vol.UNDEFINED),
            ): vol.All(illuminance_selector, vol.Coerce(int)),
            # manual control minutes
            # vol.Optional(
            #    str(LightConfig.MANUAL_CONTROL_MINUTES),
            #    default=user_input.get(
            #        LightConfig.MANUAL_CONTROL_MINUTES, vol.UNDEFINED
            #    ),
            # ): vol.All(minutes_selector, vol.Coerce(int)),
        }
    )


def make_occupancy_schema(hass: HomeAssistant, user_input: ConfigType) -> vol.Schema:
    """Create 'occupancy' config schema."""

    motion_sensors = domain_entities(
        hass,
        [Platform.BINARY_SENSOR],
        device_classes=BinarySensorDeviceClass.MOTION,
    )

    minutes_selector = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=60,
            unit_of_measurement="minutes",
            mode=selector.NumberSelectorMode.SLIDER,
        ),
    )

    conditional_entities = domain_entities(
        hass, [Platform.BINARY_SENSOR, INPUT_BOOLEAN_DOMAIN]
    ) | on_off_entities(hass, [Platform.BINARY_SENSOR, INPUT_BOOLEAN_DOMAIN])

    conditional_entities -= motion_sensors

    door_sensors = domain_entities(
        hass,
        [Platform.BINARY_SENSOR],
        device_classes=[
            BinarySensorDeviceClass.DOOR,
            BinarySensorDeviceClass.GARAGE_DOOR,
        ],
    )

    return vol.Schema(
        {
            # name
            vol.Required(
                str(OccupancyConfig.SENSOR_NAME),
                default=user_input.get(OccupancyConfig.SENSOR_NAME, vol.UNDEFINED),
            ): str,
            # motion sensors
            vol.Optional(
                str(OccupancyConfig.MOTION_SENSORS),
                default=user_input.get(OccupancyConfig.MOTION_SENSORS, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    include_entities=list(motion_sensors), multiple=True
                ),
            ),
            # motion-off minutes
            vol.Optional(
                str(OccupancyConfig.OFF_MINUTES),
                default=user_input.get(OccupancyConfig.OFF_MINUTES, vol.UNDEFINED),
            ): vol.All(minutes_selector, vol.Coerce(int)),
            # other entities
            vol.Optional(
                str(OccupancyConfig.OTHER_ENTITIES),
                default=user_input.get(OccupancyConfig.OTHER_ENTITIES, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    include_entities=list(conditional_entities), multiple=True
                ),
            ),
            # door sensors
            vol.Optional(
                str(OccupancyConfig.DOOR_SENSORS),
                default=user_input.get(OccupancyConfig.DOOR_SENSORS, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    include_entities=list(door_sensors), multiple=True
                ),
            ),
            # required on entities
            vol.Optional(
                str(OccupancyConfig.REQUIRED_ON_ENTITIES),
                default=user_input.get(
                    OccupancyConfig.REQUIRED_ON_ENTITIES, vol.UNDEFINED
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    include_entities=list(conditional_entities), multiple=True
                ),
            ),
            # required off entities
            vol.Optional(
                str(OccupancyConfig.REQUIRED_OFF_ENTITIES),
                default=user_input.get(
                    OccupancyConfig.REQUIRED_OFF_ENTITIES, vol.UNDEFINED
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    include_entities=list(conditional_entities), multiple=True
                ),
            ),
        }
    )


# #### Internal functions ####


def _existing_controlled_entities(hass: HomeAssistant):
    return [
        entry.data.get(CommonConfig.CONTROLLED_ENTITY)
        for entry in hass.config_entries.async_entries(DOMAIN)
    ]
