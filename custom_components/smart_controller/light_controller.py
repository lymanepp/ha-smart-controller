"""Representation of a Light Controller."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.backports.enum import StrEnum
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant, State

from .const import _LOGGER, ON_OFF_STATES, LightConfig
from .smart_controller import SmartController
from .util import remove_empty


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
    REFRESH = "refresh"
    TIMER = "timer"


class LightController(SmartController):
    """Representation of a Light Controller."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Light Controller."""
        super().__init__(hass, config_entry, MyState.INIT)

        self.illuminance_sensor: str | None = self.data.get(
            LightConfig.ILLUMINANCE_SENSOR
        )
        self.illuminance_cutoff: int | None = self.data.get(
            LightConfig.ILLUMINANCE_CUTOFF
        )

        auto_off_minutes: int | None = self.data.get(LightConfig.AUTO_OFF_MINUTES)
        # manual_control_minutes: int | None = self.data.get(
        #    LightConfig.MANUAL_CONTROL_MINUTES
        # )

        self._auto_off_period = (
            timedelta(minutes=auto_off_minutes) if auto_off_minutes else None
        )

        self._low_light: bool | None = None if self.illuminance_sensor else True

        required_on_entities: list[str] = self.data.get(
            LightConfig.REQUIRED_ON_ENTITIES, []
        )
        required_off_entities: list[str] = self.data.get(
            LightConfig.REQUIRED_OFF_ENTITIES, []
        )
        self._required = {
            **{k: STATE_ON for k in required_on_entities},
            **{k: STATE_OFF for k in required_off_entities},
        }
        self._required_states: dict[str, str | None] = {k: None for k in self._required}

        # self._manual_control_period = (
        #    timedelta(minutes=manual_control_minutes)
        #    if manual_control_minutes
        #    else None
        # )

        self._occupancy_mode = False

        self.tracked_entity_ids = remove_empty(
            [
                self.controlled_entity,
                self.illuminance_sensor,
                *self._required,
            ]
        )

    async def async_setup(self, hass: HomeAssistant) -> None:
        """Subscribe to state change events for all tracked entities."""
        await super().async_setup(hass)

        self._occupancy_mode = any(
            (
                (state := hass.states.get(required_entity)) is not None
                and state.domain == Platform.BINARY_SENSOR
                and state.attributes.get(ATTR_DEVICE_CLASS)
                == BinarySensorDeviceClass.OCCUPANCY
            )
            for required_entity in self._required
        )

    async def on_state_change(self, state: State) -> None:
        """Handle entity state changes from base."""
        if state.entity_id == self.controlled_entity:
            if state.state in ON_OFF_STATES:
                await self._process_event(
                    MyEvent.ON if state.state == STATE_ON else MyEvent.OFF
                )

        elif state.entity_id == self.illuminance_sensor:
            assert self.illuminance_cutoff
            if state.state is not None:
                self._low_light = float(state.state) <= self.illuminance_cutoff
                await self._process_event(MyEvent.REFRESH)

        elif state.entity_id in self._required_states:
            if state.state in ON_OFF_STATES:
                self._required_states[state.entity_id] = state.state
                await self._process_event(MyEvent.REFRESH)

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

        def low_light():
            return self._low_light

        def have_required():
            return self._required_states == self._required

        def occupancy_mode():
            return self._occupancy_mode

        match (self._state, event):
            case (MyState.INIT, MyEvent.OFF):
                self.set_state(MyState.OFF)

            case (MyState.INIT, MyEvent.ON):
                self.set_state(MyState.ON)
                self.set_timer(self._auto_off_period)

            case (MyState.OFF, MyEvent.ON):
                self.set_state(MyState.ON_MANUAL)
                self.set_timer(self._auto_off_period)

            case (MyState.OFF, MyEvent.REFRESH):
                if low_light() and have_required():
                    self.set_state(MyState.ON)
                    await self._set_light_mode(STATE_ON)

            case (MyState.ON, MyEvent.OFF):
                self.set_state(MyState.OFF_MANUAL)
                self.set_timer(None)

            case (MyState.ON, MyEvent.REFRESH):
                if not have_required():
                    self.set_state(MyState.OFF)
                    self.set_timer(None)
                    await self._set_light_mode(STATE_OFF)

            case (MyState.ON, MyEvent.TIMER):
                assert not occupancy_mode()
                self.set_state(MyState.OFF)
                await self._set_light_mode(STATE_OFF)

            case (MyState.OFF_MANUAL, MyEvent.ON):
                if have_required():
                    self.set_state(MyState.ON)
                else:
                    self.set_state(MyState.ON_MANUAL)

            case (MyState.OFF_MANUAL, MyEvent.REFRESH):
                if not have_required():
                    self.set_state(MyState.OFF)

            case (MyState.ON_MANUAL, MyEvent.OFF):
                if have_required():
                    self.set_state(MyState.OFF_MANUAL)
                else:
                    self.set_state(MyState.OFF)

            case (MyState.ON_MANUAL, MyEvent.REFRESH):
                if have_required():
                    self.set_state(MyState.ON)

            case (MyState.ON_MANUAL, MyEvent.TIMER):
                assert not occupancy_mode()
                self.set_state(MyState.OFF)
                await self._set_light_mode(STATE_OFF)

            case _:
                _LOGGER.debug(
                    "%s; state=%s; ignored '%s' event",
                    self.name,
                    self._state,
                    event,
                )

    async def _set_light_mode(self, mode: str):
        await self.async_service_call(
            Platform.LIGHT,
            SERVICE_TURN_ON if mode == STATE_ON else SERVICE_TURN_OFF,
        )
