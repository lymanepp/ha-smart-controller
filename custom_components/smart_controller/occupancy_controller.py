"""Representation of a Occupancy Controller."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State

from .const import _LOGGER, ON_OFF_STATES, OccupancyConfig
from .smart_controller import SmartController
from .util import remove_empty


class MyState(StrEnum):
    """State machine states."""

    UNOCCUPIED = "unoccupied"
    MOTION = "motion"
    WASP_IN_BOX = "wasp_in_box"
    OTHER = "other"


class MyEvent(StrEnum):
    """State machine events."""

    MOTION = "motion"
    TIMER = "timer"
    DOOR_OPENED = "door_opened"
    OTHER_OFF = "other_off"
    OTHER_ON = "other_on"


ON_STATES: Final = [MyState.MOTION, MyState.OTHER, MyState.WASP_IN_BOX]


class OccupancyController(SmartController):
    """Representation of an Occupancy Controller."""

    _doors_closed: bool | None = None
    _required_state: bool | None = None
    _other_state: bool | None = None

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Occupancy Controller."""
        super().__init__(
            hass, config_entry, initial_state=MyState.UNOCCUPIED, is_on_states=ON_STATES
        )

        self.motion_sensors: list[str] = self.data.get(
            OccupancyConfig.MOTION_SENSORS, []
        )

        motion_off_minutes = self.data.get(OccupancyConfig.MOTION_OFF_MINUTES)

        self._motion_off_period = (
            timedelta(minutes=motion_off_minutes) if motion_off_minutes else None
        )

        self.door_states: dict[str, bool | None] = {
            id: None for id in self.data.get(OccupancyConfig.DOOR_SENSORS, [])
        }

        self.required_states: dict[str, bool | None] = {
            id: None for id in self.data.get(OccupancyConfig.REQUIRED_ENTITIES, [])
        }

        self.other_states: dict[str, bool | None] = {
            id: None for id in self.data.get(OccupancyConfig.OTHER_ENTITIES, [])
        }

        self.tracked_entity_ids = remove_empty(
            [
                self.controlled_entity,
                *self.motion_sensors,
                *self.door_states,
                *self.required_states,
                *self.other_states,
            ]
        )

    async def on_state_change(self, state: State) -> None:
        """Handle entity state changes from base."""
        if state.entity_id in self.motion_sensors and state.state == STATE_ON:
            self._process_event(MyEvent.MOTION)

        elif state.entity_id in self.door_states and state.state in ON_OFF_STATES:
            self.door_states[state.entity_id] = state.state

            closed = all(value == STATE_OFF for value in self.door_states.values())
            if self._doors_closed != closed:
                self._doors_closed = closed

                if not closed:
                    self._process_event(MyEvent.DOOR_OPENED)

        elif state.entity_id in self.required_states and state.state in ON_OFF_STATES:
            self.required_states[state.entity_id] = state.state

            required = all(value == STATE_ON for value in self.required_states.values())
            if self._required_state != required:
                self._required_state = required

                # TODO: this is just a placeholder!
                self._process_event(MyEvent.OTHER_ON if required else MyEvent.OTHER_OFF)

        elif state.entity_id in self.other_states and state.state in ON_OFF_STATES:
            self.other_states[state.entity_id] = state.state

            other = any(value == STATE_ON for value in self.other_states.values())
            if self._other_state != other:
                self._other_state = other

                self._process_event(MyEvent.OTHER_ON if other else MyEvent.OTHER_OFF)

    async def on_timer_expired(self) -> None:
        """Handle timer expiration from base."""
        self._process_event(MyEvent.TIMER)

    def _process_event(self, event: MyEvent) -> None:
        _LOGGER.debug(
            "%s; state=%s; processing '%s' event",
            self.name,
            self._state,
            event,
        )

        def enter_unoccupied_state():
            self.set_timer(None)
            self.set_state(MyState.UNOCCUPIED)

        def enter_motion_state():
            self.set_timer(self._motion_off_period)
            self.set_state(MyState.MOTION)

        def enter_wasp_in_box_state():
            self.set_timer(None)
            self.set_state(MyState.WASP_IN_BOX)

        def enter_other_state():
            self.set_timer(None)
            self.set_state(MyState.OTHER)

        match (self._state, event):
            case (MyState.UNOCCUPIED, MyEvent.MOTION):
                if self._doors_closed:
                    enter_wasp_in_box_state()
                else:
                    enter_motion_state()

            case (MyState.UNOCCUPIED, MyEvent.OTHER_ON):
                enter_other_state()

            case (MyState.MOTION, MyEvent.MOTION) if self._doors_closed:
                enter_wasp_in_box_state()

            case (MyState.MOTION, MyEvent.TIMER):
                if self._other_state:
                    enter_other_state()
                else:
                    enter_unoccupied_state()

            case (MyState.WASP_IN_BOX, MyEvent.DOOR_OPENED):
                enter_motion_state()

            case (MyState.OTHER, MyEvent.MOTION):
                if self._doors_closed:
                    enter_wasp_in_box_state()
                else:
                    enter_motion_state()

            case (MyState.OTHER, MyEvent.OTHER_OFF):
                enter_unoccupied_state()

            case _:
                _LOGGER.debug(
                    "%s; state=%s; ignored '%s' event",
                    self.name,
                    self._state,
                    event,
                )
