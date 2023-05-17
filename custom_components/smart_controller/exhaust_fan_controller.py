"""Representation of an Exhaust Fan Controller."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State

from .base_controller import BaseController
from .const import _LOGGER, ExhaustFanConfig
from .util import absolute_humidity, remove_empty, state_with_unit

IGNORE_STATES = (STATE_UNKNOWN, STATE_UNAVAILABLE)
ON_OFF = (STATE_ON, STATE_OFF)


class MyState(StrEnum):
    """State machine states."""

    INIT = "init"
    OFF = "off"
    ON = "on"
    ON_MANUAL = "on_manual"
    OFF_MANUAL = "off_manual"


class MyEvent(StrEnum):
    """State machine events."""

    OFF = "off"
    ON = "on"
    TIMER = "timer"
    UPDATE_FAN_MODE = "update_fan_mode"


class ExhaustFanController(BaseController):
    """Representation of an Exhaust Fan Controller."""

    _temp: tuple[float, str] | None = None
    _humidity: tuple[float, str] | None = None
    _ref_temp: tuple[float, str] | None = None
    _ref_humidity: tuple[float, str] | None = None

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the controller."""
        super().__init__(hass, config_entry, MyState.INIT)

        self.temp_sensor: str = self.data[ExhaustFanConfig.TEMP_SENSOR]
        self.humidity_sensor: str = self.data[ExhaustFanConfig.HUMIDITY_SENSOR]
        self.ref_temp_sensor: str = self.data[ExhaustFanConfig.REFERENCE_TEMP_SENSOR]
        self.ref_humidity_sensor: str = self.data[
            ExhaustFanConfig.REFERENCE_HUMIDITY_SENSOR
        ]

        self.falling_threshold: float = self.data[ExhaustFanConfig.FALLING_THRESHOLD]
        self.rising_threshold: float = self.data[ExhaustFanConfig.RISING_THRESHOLD]

        manual_control_minutes = self.data.get(ExhaustFanConfig.MANUAL_CONTROL_MINUTES)
        self._manual_control_period = (
            timedelta(minutes=manual_control_minutes) if manual_control_minutes else None
        )

        self.tracked_entity_ids = remove_empty(
            [
                self.controlled_entity,
                self.temp_sensor,
                self.humidity_sensor,
                self.ref_temp_sensor,
                self.ref_humidity_sensor,
            ]
        )

    async def async_setup(self, hass) -> CALLBACK_TYPE:
        """Additional setup unique to this controller."""
        unsubscriber = await super().async_setup(hass)
        await self._process_event(MyEvent.UPDATE_FAN_MODE)
        return unsubscriber

    async def on_state_change(self, state: State) -> None:
        """Handle entity state changes from base."""
        match state.entity_id:
            case self.controlled_entity if state.state in ON_OFF:
                await self._process_event(
                    MyEvent.ON if state.state == STATE_ON else MyEvent.OFF
                )

            case self.temp_sensor:
                self._temp = state_with_unit(
                    state, self.hass.config.units.temperature_unit
                )
                await self._process_event(MyEvent.UPDATE_FAN_MODE)

            case self.humidity_sensor:
                self._humidity = state_with_unit(state, PERCENTAGE)
                await self._process_event(MyEvent.UPDATE_FAN_MODE)

            case self.ref_temp_sensor:
                self._ref_temp = state_with_unit(
                    state, self.hass.config.units.temperature_unit
                )
                await self._process_event(MyEvent.UPDATE_FAN_MODE)

            case self.ref_humidity_sensor:
                self._ref_humidity = state_with_unit(state, PERCENTAGE)
                await self._process_event(MyEvent.UPDATE_FAN_MODE)

    async def on_timer_expired(self) -> None:
        """Handle timer expiration from base."""
        await self._process_event(MyEvent.TIMER)

    async def _process_event(self, event: MyEvent) -> None:
        _LOGGER.debug(
            "%s; state=%s; processing '%s' event",
            self.name,
            self._state,
            event,
        )

        match (self._state, event):
            case (MyState.INIT, MyEvent.OFF):
                self.set_state(MyState.OFF)

            case (MyState.INIT, MyEvent.ON):
                self.set_state(MyState.ON)

            case (MyState.OFF, MyEvent.ON):
                self.set_state(
                    MyState.ON_MANUAL if self._manual_control_period else MyState.ON
                )
                self.set_timer(self._manual_control_period)

            case (MyState.OFF, MyEvent.UPDATE_FAN_MODE):
                if fan_on := await self._set_fan_mode():
                    self.set_state(MyState.ON)

            case (MyState.ON, MyEvent.OFF):
                self.set_state(
                    MyState.OFF_MANUAL if self._manual_control_period else MyState.OFF
                )
                self.set_timer(self._manual_control_period)

            case (MyState.ON, MyEvent.UPDATE_FAN_MODE):
                if not (fan_on := await self._set_fan_mode()):
                    self.set_state(MyState.OFF)

            case (MyState.OFF_MANUAL, MyEvent.ON):
                self.set_timer(None)
                fan_on = await self._set_fan_mode()
                self.set_state(MyState.ON if fan_on else MyState.OFF)

            case (MyState.OFF_MANUAL, MyEvent.TIMER):
                fan_on = await self._set_fan_mode()
                self.set_state(MyState.ON if fan_on else MyState.OFF)

            case (MyState.ON_MANUAL, MyEvent.OFF):
                self.set_timer(None)
                fan_on = await self._set_fan_mode()
                self.set_state(MyState.ON if fan_on else MyState.OFF)

            case (MyState.ON_MANUAL, MyEvent.TIMER):
                fan_on = await self._set_fan_mode()
                self.set_state(MyState.ON if fan_on else MyState.OFF)

            case _:
                _LOGGER.debug(
                    "%s; state=%s; ignored '%s' event",
                    self.name,
                    self._state,
                    event,
                )

    async def _set_fan_mode(self) -> bool:
        if None in (self._temp, self._humidity, self._ref_temp, self._ref_humidity):
            return False

        abs_hum = absolute_humidity(self._temp, self._humidity[0])
        ref_abs_hum = absolute_humidity(self._ref_temp, self._ref_humidity[0])
        difference = abs_hum - ref_abs_hum

        fan_state = self.hass.states.get(self.controlled_entity)
        curr_mode = fan_state.state

        if curr_mode == STATE_OFF and difference > self.rising_threshold:
            new_mode = STATE_ON
        elif curr_mode == STATE_ON and difference < self.falling_threshold:
            new_mode = STATE_OFF
        else:
            new_mode = curr_mode

        if new_mode != curr_mode:
            await self.async_service_call(
                Platform.FAN,
                SERVICE_TURN_ON if new_mode == STATE_ON else SERVICE_TURN_OFF,
            )

        return new_mode == STATE_ON
