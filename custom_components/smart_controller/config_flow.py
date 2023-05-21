"""Adds config flow for Light Controller."""
from __future__ import annotations

from collections.abc import MutableMapping
from typing import Final

import voluptuous as vol
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.fan import ATTR_PERCENTAGE_STEP
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    DEFAULT_CEILING_SSI_MAX,
    DEFAULT_CEILING_SSI_MIN,
    DEFAULT_EXHAUST_FALLING_THRESHOLD,
    DEFAULT_EXHAUST_MANUAL_MINUTES,
    DEFAULT_EXHAUST_RISING_THRESHOLD,
    DOMAIN,
    GRAMS_PER_CUBIC_METER,
    CeilingFanConfig,
    CommonConfig,
    ControllerType,
    ExhaustFanConfig,
    LightConfig,
)
from .util import domain_entities, on_off_entities

ErrorsType = MutableMapping[str, str]

ON_OFF = (STATE_ON, STATE_OFF)

FAN_TYPE: Final = "fan_type"


class SmartControllerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Light Controller."""

    VERSION = 1

    _controlled_entity: str | None = None

    async def async_step_user(
        self,
        user_input: ConfigType | None = None,
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: ErrorsType = {}

        if user_input is not None:
            self._controlled_entity = user_input[CommonConfig.CONTROLLED_ENTITY]

            domain, _ = split_entity_id(self._controlled_entity)

            match domain:
                case Platform.FAN:
                    return await self.async_step_fan()
                case Platform.LIGHT:
                    return await self.async_step_light()

        return self.async_show_form(
            step_id="user",
            data_schema=make_controlled_entity_schema(self.hass, user_input or {}),
            errors=errors,
        )

    async def async_step_fan(
        self,
        user_input: ConfigType | None = None,
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: ErrorsType = {}

        if user_input is not None:
            fan_type = user_input[FAN_TYPE]
            step_method = getattr(self, f"async_step_{fan_type}")
            return await step_method()

        return self.async_show_form(
            step_id="fan",
            data_schema=make_fan_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_ceiling_fan(
        self,
        user_input: ConfigType | None = None,
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: ErrorsType = {}

        if user_input is not None:
            # TODO: validate dependencies between fields here (or in schema)

            unique_id = f"{DOMAIN}__" + slugify(self._controlled_entity)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            state = self.hass.states.get(self._controlled_entity)

            data = {
                CommonConfig.TYPE: ControllerType.CEILING_FAN,
                CommonConfig.CONTROLLED_ENTITY: self._controlled_entity,
                **user_input,
            }

            return self.async_create_entry(title=state.name, data=data)

        return self.async_show_form(
            step_id="ceiling_fan",
            data_schema=make_ceiling_fan_schema(
                self.hass, user_input or {}, self._controlled_entity
            ),
            errors=errors,
        )

    async def async_step_exhaust_fan(
        self,
        user_input: ConfigType | None = None,
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: ErrorsType = {}

        if user_input is not None:
            # TODO: validate dependencies between fields here (or in schema)

            unique_id = f"{DOMAIN}__" + slugify(self._controlled_entity)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            state = self.hass.states.get(self._controlled_entity)

            data = {
                CommonConfig.TYPE: ControllerType.EXHAUST_FAN,
                CommonConfig.CONTROLLED_ENTITY: self._controlled_entity,
                **user_input,
            }

            return self.async_create_entry(title=state.name, data=data)

        return self.async_show_form(
            step_id="exhaust_fan",
            data_schema=make_exhaust_fan_schema(self.hass, user_input or {}),
            errors=errors,
        )

    async def async_step_light(
        self,
        user_input: ConfigType | None = None,
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: ErrorsType = {}

        if user_input is not None:
            if user_input.get(
                LightConfig.MANUAL_CONTROL_MINUTES
            ) and not user_input.get(LightConfig.MOTION_SENSOR):
                errors["base"] = "manual_control_no_motion"

            unique_id = f"{DOMAIN}__" + slugify(self._controlled_entity)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            state = self.hass.states.get(self._controlled_entity)

            data = {
                CommonConfig.TYPE: ControllerType.LIGHT,
                CommonConfig.CONTROLLED_ENTITY: self._controlled_entity,
                **user_input,
            }

            return self.async_create_entry(title=state.name, data=data)

        return self.async_show_form(
            step_id="light",
            data_schema=make_light_schema(self.hass, user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback  # type: ignore
    def async_get_options_flow(config_entry: ConfigEntry) -> ConfigFlow:
        """Get the options flow for this handler."""
        return SmartControllerOptionsFlow(config_entry)


class SmartControllerOptionsFlow(OptionsFlow):  # type: ignore
    """Handle options."""

    def __init__(self, config_entry: ConfigEntry):
        """Initialize options flow."""
        data = config_entry.data | config_entry.options
        self.controller_type = data.pop(CommonConfig.TYPE)
        self.controlled_entity = data.pop(CommonConfig.CONTROLLED_ENTITY)
        self.original_data = data

    async def async_step_init(self, _: ConfigType = None) -> FlowResult:
        """Handle option flow 'init' step."""
        match self.controller_type:
            case ControllerType.CEILING_FAN:
                return await self.async_step_ceiling_fan()
            case ControllerType.EXHAUST_FAN:
                return await self.async_step_exhaust_fan()
            case ControllerType.LIGHT:
                return await self.async_step_light()

    async def async_step_ceiling_fan(self, user_input: ConfigType = None) -> FlowResult:
        """Handle option flow 'ceiling fan' step."""
        errors: ErrorsType = {}

        if user_input is not None:
            state = self.hass.states.get(self.controlled_entity)
            return self.async_create_entry(title=state.name, data=user_input)

        schema_data = user_input or self.original_data

        return self.async_show_form(
            step_id="ceiling_fan",
            data_schema=make_ceiling_fan_schema(
                self.hass, schema_data, self.controlled_entity
            ),
            errors=errors,
        )

    async def async_step_exhaust_fan(self, user_input: ConfigType = None) -> FlowResult:
        """Handle option flow 'exhaust fan' step."""
        errors: ErrorsType = {}

        if user_input is not None:
            state = self.hass.states.get(self.controlled_entity)
            return self.async_create_entry(title=state.name, data=user_input)

        schema_data = user_input or self.original_data

        return self.async_show_form(
            step_id="exhaust_fan",
            data_schema=make_exhaust_fan_schema(self.hass, schema_data),
            errors=errors,
        )

    async def async_step_light(self, user_input: ConfigType = None) -> FlowResult:
        """Handle option flow 'light' step."""
        errors: ErrorsType = {}

        if user_input is not None:
            state = self.hass.states.get(self.controlled_entity)
            return self.async_create_entry(title=state.name, data=user_input)

        schema_data = user_input or self.original_data

        return self.async_show_form(
            step_id="light",
            data_schema=make_light_schema(self.hass, schema_data),
            errors=errors,
        )


def make_controlled_entity_schema(
    hass: HomeAssistant, user_input: ConfigType
) -> vol.Schema:
    """Create 'user' config schema."""

    already_controlled = [
        entry.data.get(CommonConfig.CONTROLLED_ENTITY)
        for entry in hass.config_entries.async_entries(DOMAIN)
    ]

    controllable_entities = domain_entities(hass, [Platform.FAN, Platform.LIGHT])

    controllable_entities = sorted(
        set(controllable_entities).difference(already_controlled)
    )

    if not controllable_entities:
        raise AbortFlow("nothing_to_control")

    return vol.Schema(
        {
            vol.Required(
                str(CommonConfig.CONTROLLED_ENTITY),
                default=user_input.get(CommonConfig.CONTROLLED_ENTITY, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=controllable_entities),
            ),
        }
    )


def make_fan_schema(_: ConfigType) -> vol.Schema:
    """Create 'fan' config schema."""

    fan_types = [
        ControllerType.CEILING_FAN,
        ControllerType.EXHAUST_FAN,
    ]

    return vol.Schema(
        {
            vol.Required(FAN_TYPE): SelectSelector(
                SelectSelectorConfig(
                    options=fan_types,
                    mode=SelectSelectorMode.LIST,
                    translation_key="fan_type",  # TODO: create constant
                )
            )
        }
    )


def make_ceiling_fan_schema(
    hass: HomeAssistant, user_input: ConfigType, controlled_entity: str
) -> vol.Schema:
    """Create 'ceiling_fan' config schema."""

    temp_sensors = domain_entities(
        hass,
        [Platform.SENSOR],
        device_class=SensorDeviceClass.TEMPERATURE,
    )

    humidity_sensors = domain_entities(
        hass,
        [Platform.SENSOR],
        device_class=SensorDeviceClass.HUMIDITY,
    )

    prerequisite_entities = domain_entities(
        hass, [Platform.BINARY_SENSOR, INPUT_BOOLEAN_DOMAIN]
    ) + on_off_entities(hass, [Platform.FAN])

    prerequisite_entities = sorted(set(prerequisite_entities))

    fan_state = hass.states.get(controlled_entity)
    speed_step = fan_state.attributes.get(ATTR_PERCENTAGE_STEP, 100)

    speed_selector = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            step=speed_step,
            unit_of_measurement=PERCENTAGE,
            mode=selector.NumberSelectorMode.SLIDER,
        ),
    )

    ssi_selector = selector.NumberSelector(
        selector.NumberSelectorConfig(
            unit_of_measurement=hass.config.units.temperature_unit,
            mode=selector.NumberSelectorMode.BOX,
        ),
    )

    default_ssi_min = TemperatureConverter.convert(
        DEFAULT_CEILING_SSI_MIN,
        UnitOfTemperature.FAHRENHEIT,
        hass.config.units.temperature_unit,
    )

    default_ssi_max = TemperatureConverter.convert(
        DEFAULT_CEILING_SSI_MAX,
        UnitOfTemperature.FAHRENHEIT,
        hass.config.units.temperature_unit,
    )

    return vol.Schema(
        {
            # temperature sensor
            vol.Required(
                str(CeilingFanConfig.TEMP_SENSOR),
                default=user_input.get(CeilingFanConfig.TEMP_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=temp_sensors),
            ),
            # humidity sensor
            vol.Required(
                str(CeilingFanConfig.HUMIDITY_SENSOR),
                default=user_input.get(CeilingFanConfig.HUMIDITY_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=humidity_sensors),
            ),
            # prerequisite entity
            vol.Optional(
                str(CeilingFanConfig.PREREQUISITE_ENTITY),
                default=user_input.get(
                    CeilingFanConfig.PREREQUISITE_ENTITY, vol.UNDEFINED
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=prerequisite_entities),
            ),
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
            # manual control minutes (optional)
            vol.Optional(
                str(ExhaustFanConfig.MANUAL_CONTROL_MINUTES),
                default=user_input.get(
                    ExhaustFanConfig.MANUAL_CONTROL_MINUTES,
                    vol.UNDEFINED,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=60,
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.SLIDER,
                ),
            ),
        }
    )


def make_exhaust_fan_schema(hass: HomeAssistant, user_input: ConfigType) -> vol.Schema:
    """Create 'exhaust_fan' config schema."""

    temp_sensors = domain_entities(
        hass,
        [Platform.SENSOR],
        device_class=SensorDeviceClass.TEMPERATURE,
    )

    humidity_sensors = domain_entities(
        hass,
        [Platform.SENSOR],
        device_class=SensorDeviceClass.HUMIDITY,
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

    return vol.Schema(
        {
            # temperature sensor
            vol.Required(
                str(ExhaustFanConfig.TEMP_SENSOR),
                default=user_input.get(ExhaustFanConfig.TEMP_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=temp_sensors),
            ),
            # humidity sensor
            vol.Required(
                str(ExhaustFanConfig.HUMIDITY_SENSOR),
                default=user_input.get(ExhaustFanConfig.HUMIDITY_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=humidity_sensors),
            ),
            # reference temperature sensor
            vol.Required(
                str(ExhaustFanConfig.REFERENCE_TEMP_SENSOR),
                default=user_input.get(
                    ExhaustFanConfig.REFERENCE_TEMP_SENSOR, vol.UNDEFINED
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=temp_sensors),
            ),
            # reference humidity sensor
            vol.Required(
                str(ExhaustFanConfig.REFERENCE_HUMIDITY_SENSOR),
                default=user_input.get(
                    ExhaustFanConfig.REFERENCE_HUMIDITY_SENSOR, vol.UNDEFINED
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=humidity_sensors),
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
            # manual control minutes (optional)
            vol.Optional(
                str(ExhaustFanConfig.MANUAL_CONTROL_MINUTES),
                default=user_input.get(
                    ExhaustFanConfig.MANUAL_CONTROL_MINUTES,
                    DEFAULT_EXHAUST_MANUAL_MINUTES,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=60,
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.SLIDER,
                ),
            ),
        }
    )


def make_light_schema(hass: HomeAssistant, user_input: ConfigType) -> vol.Schema:
    """Create 'light' config schema."""

    motion_sensors = domain_entities(
        hass,
        [Platform.BINARY_SENSOR],
        device_class=BinarySensorDeviceClass.MOTION,
    )

    illuminance_sensors = domain_entities(
        hass,
        [Platform.SENSOR],
        device_class=SensorDeviceClass.ILLUMINANCE,
    )

    blockers = domain_entities(hass, [Platform.BINARY_SENSOR, INPUT_BOOLEAN_DOMAIN])

    return vol.Schema(
        {
            # motion sensor
            vol.Optional(
                str(LightConfig.MOTION_SENSOR),
                default=user_input.get(LightConfig.MOTION_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=motion_sensors),
            ),
            # manual control minutes (this is only valid with motion sensor)
            vol.Optional(
                str(LightConfig.MANUAL_CONTROL_MINUTES),
                default=user_input.get(
                    LightConfig.MANUAL_CONTROL_MINUTES, vol.UNDEFINED
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=60,
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.SLIDER,
                ),
            ),
            # auto off minutes
            vol.Optional(
                str(LightConfig.AUTO_OFF_MINUTES),
                default=user_input.get(LightConfig.AUTO_OFF_MINUTES, vol.UNDEFINED),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=60,
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.SLIDER,
                ),
            ),
            # illuminance sensor
            vol.Inclusive(
                str(LightConfig.ILLUMINANCE_SENSOR),
                "illumininance",
                default=user_input.get(LightConfig.ILLUMINANCE_SENSOR, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=illuminance_sensors),
            ),
            # illuminance threshold (this is required with illuminance sensor)
            vol.Inclusive(
                str(LightConfig.ILLUMINANCE_CUTOFF),
                "illumininance",
                default=user_input.get(LightConfig.ILLUMINANCE_CUTOFF, vol.UNDEFINED),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            # on blocker entity
            vol.Optional(
                str(LightConfig.ON_BLOCKER_ENTITY),
                default=user_input.get(LightConfig.ON_BLOCKER_ENTITY, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=blockers),
            ),
            # off blocker entity
            vol.Optional(
                str(LightConfig.OFF_BLOCKER_ENTITY),
                default=user_input.get(LightConfig.OFF_BLOCKER_ENTITY, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=blockers),
            ),
        }
    )
