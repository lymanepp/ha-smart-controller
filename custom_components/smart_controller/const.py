"""Constants for smart_controller."""
from logging import Logger, getLogger
from typing import Final

from homeassistant.backports.enum import StrEnum
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN

_LOGGER: Logger = getLogger(__package__)

DOMAIN: Final = "smart_controller"
NAME: Final = "Smart Controller"

IGNORE_STATES: Final = (STATE_UNKNOWN, STATE_UNAVAILABLE)
ON_OFF_STATES: Final = (STATE_ON, STATE_OFF)

GRAMS_PER_CUBIC_METER: Final = "g/m³"

DEFAULT_CEILING_SSI_MIN_FAHRENHEIT: Final = 81.0
DEFAULT_CEILING_SSI_MAX_FAHRENHEIT: Final = 91.0

DEFAULT_EXHAUST_FALLING_THRESHOLD: Final = 0.5
DEFAULT_EXHAUST_RISING_THRESHOLD: Final = 2.0
DEFAULT_EXHAUST_MANUAL_MINUTES: Final = 15.0


class ControllerType(StrEnum):
    """Supported controller types."""

    CEILING_FAN = "ceiling_fan"
    EXHAUST_FAN = "exhaust_fan"
    LIGHT = "light"
    OCCUPANCY = "occupancy"


class CommonConfig(StrEnum):
    """Config common to all controllers."""

    TYPE = "type"
    CONTROLLED_ENTITY = "controlled_entity"


class CeilingFanConfig(StrEnum):
    """Ceiling fan configuration."""

    CONTROLLED_ENTITY = "controlled_entity"
    TEMP_SENSOR = "temp_sensor"
    HUMIDITY_SENSOR = "humidity_sensor"
    SSI_MIN = "ssi_min"
    SSI_MAX = "ssi_max"
    SPEED_MIN = "speed_min"
    SPEED_MAX = "speed_max"
    REQUIRED_ON_ENTITIES = "required_on_entities"
    REQUIRED_OFF_ENTITIES = "required_off_entities"
    MANUAL_CONTROL_MINUTES = "manual_control_minutes"


class ExhaustFanConfig(StrEnum):
    """Exhaust fan configuration."""

    CONTROLLED_ENTITY = "controlled_entity"
    TEMP_SENSOR = "temp_sensor"
    HUMIDITY_SENSOR = "humidity_sensor"
    REFERENCE_TEMP_SENSOR = "reference_temp_sensor"
    REFERENCE_HUMIDITY_SENSOR = "reference_humidity_sensor"
    RISING_THRESHOLD = "rising_threshold"
    FALLING_THRESHOLD = "falling_threshold"
    MANUAL_CONTROL_MINUTES = "manual_control_minutes"


class LightConfig(StrEnum):
    """Light configuration."""

    CONTROLLED_ENTITY = "controlled_entity"
    AUTO_OFF_MINUTES = "auto_off_minutes"
    ILLUMINANCE_SENSOR = "illuminance_sensor"
    ILLUMINANCE_CUTOFF = "illuminance_cutoff"
    REQUIRED_ON_ENTITIES = "required_on_entities"
    REQUIRED_OFF_ENTITIES = "required_off_entities"
    # MANUAL_CONTROL_MINUTES = "manual_control_minutes"


class OccupancyConfig(StrEnum):
    """Occupancy configuration."""

    SENSOR_NAME = "sensor_name"
    MOTION_SENSORS = "motion_sensors"
    OFF_MINUTES = "motion_off_minutes"
    DOOR_SENSORS = "door_sensors"
    OTHER_ENTITIES = "other_entities"
    REQUIRED_ON_ENTITIES = "required_on_entities"
    REQUIRED_OFF_ENTITIES = "required_off_entities"
