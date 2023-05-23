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

DEFAULT_CEILING_SSI_MIN: Final = 83.0
DEFAULT_CEILING_SSI_MAX: Final = 91.0

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
    PREREQUISITE_ENTITY = "prerequisite_entity"
    SPEED_MAX = "speed_max"
    SPEED_MIN = "speed_min"
    SSI_MAX = "ssi_max"
    SSI_MIN = "ssi_min"
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
    MANUAL_CONTROL_MINUTES = "manual_control_minutes"
    MOTION_SENSOR = "motion_sensor"
    ILLUMINANCE_CUTOFF = "illuminance_cutoff"
    ILLUMINANCE_SENSOR = "illuminance_sensor"
    ON_BLOCKER_ENTITY = "on_blocker_entity"
    OFF_BLOCKER_ENTITY = "off_blocker_entity"


class OccupancyConfig(StrEnum):
    """Occupancy configuration."""

    SENSOR_NAME = "sensor_name"
    MOTION_SENSORS = "motion_sensors"
    MOTION_OFF_MINUTES = "motion_off_minutes"
    DOOR_SENSORS = "door_sensors"
    REQUIRED_ENTITIES = "required_entities"
    OTHER_ENTITIES = "other_entities"
