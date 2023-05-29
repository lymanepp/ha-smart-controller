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
    UPDATE = "update"
    DOOR_OPEN = "door_open"


ON_STATES: Final = [
    str(s) for s in [MyState.MOTION, MyState.OTHER, MyState.WASP_IN_BOX]
]


class OccupancyController(SmartController):
    """Representation of an Occupancy Controller."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Occupancy Controller."""
        super().__init__(
            hass, config_entry, initial_state=MyState.UNOCCUPIED, is_on_states=ON_STATES
        )

        self.name = config_entry.title
        self._motion_sensors: list[str] = self.data.get(
            OccupancyConfig.MOTION_SENSORS, []
        )
        motion_off_minutes = self.data.get(OccupancyConfig.OFF_MINUTES)

        self._motion_off_period = (
            timedelta(minutes=motion_off_minutes) if motion_off_minutes else None
        )

        self._other_entities: list[str] = self.data.get(
            OccupancyConfig.OTHER_ENTITIES, []
        )

        self._door_sensors: list[str] = self.data.get(OccupancyConfig.DOOR_SENSORS, [])

        required_on_entities: list[str] = self.data.get(
            OccupancyConfig.REQUIRED_ON_ENTITIES, []
        )
        required_off_entities: list[str] = self.data.get(
            OccupancyConfig.REQUIRED_OFF_ENTITIES, []
        )
        self._required: dict[str, str] = {
            **{k: STATE_ON for k in required_on_entities},
            **{k: STATE_OFF for k in required_off_entities},
        }

        self.tracked_entity_ids = remove_empty(
            [
                self.controlled_entity,
                *self._motion_sensors,
                *self._other_entities,
                *self._door_sensors,
                *self._required,
            ]
        )

    async def on_state_change(self, state: State) -> None:
        """Handle entity state changes from base."""
        if state.entity_id in self._motion_sensors:
            if state.state == STATE_ON:
                self.fire_event(MyEvent.MOTION)

        elif state.entity_id in self._other_entities:
            if state.state in ON_OFF_STATES:
                self.fire_event(MyEvent.UPDATE)

        elif state.entity_id in self._door_sensors:
            if state.state in STATE_ON:
                self.fire_event(MyEvent.DOOR_OPEN)

        elif state.entity_id in self._required:
            if state.state in ON_OFF_STATES:
                self.fire_event(MyEvent.UPDATE)

    async def on_timer_expired(self) -> None:
        """Handle timer expiration from base."""
        self.fire_event(MyEvent.TIMER)

    async def on_event(self, event: MyEvent) -> None:
        """Handle controller events."""

        def enter_unoccupied_state() -> None:
            self.set_timer(None)
            self.set_state(MyState.UNOCCUPIED)

        def enter_motion_state() -> None:
            self.set_timer(self._motion_off_period)
            self.set_state(MyState.MOTION)

        def enter_wasp_in_box_state() -> None:
            self.set_timer(None)
            self.set_state(MyState.WASP_IN_BOX)

        def enter_other_state() -> None:
            self.set_timer(None)
            self.set_state(MyState.OTHER)

        def have_other() -> bool:
            for entity in self._other_entities:
                state = self.hass.states.get(entity)
                if state and state.state == STATE_ON:
                    return True
            return False

        def doors_closed() -> bool:
            closed: list[bool] = []
            for entity in self._door_sensors:
                state = self.hass.states.get(entity)
                closed.append(state.state == STATE_ON if state else False)
            return any(closed) and all(closed)

        def have_required() -> bool:
            actual: dict[str, str | None] = {}
            for entity in self._required:
                state = self.hass.states.get(entity)
                actual[entity] = state.state if state else None
            return actual == self._required

        match (self._state, event):
            case (MyState.UNOCCUPIED, MyEvent.MOTION) if have_required():
                if doors_closed():
                    enter_wasp_in_box_state()
                else:
                    enter_motion_state()

            case (MyState.UNOCCUPIED, MyEvent.UPDATE) if have_required():
                if have_other():
                    enter_other_state()

            case (MyState.MOTION, MyEvent.MOTION):
                if doors_closed():
                    enter_wasp_in_box_state()
                else:
                    enter_motion_state()  # restart the timer

            case (MyState.MOTION, MyEvent.TIMER):
                if have_other():
                    enter_other_state()
                else:
                    enter_unoccupied_state()

            case (MyState.MOTION, MyEvent.UPDATE) if not have_required():
                enter_unoccupied_state()

            case (MyState.WASP_IN_BOX, MyEvent.DOOR_OPEN):
                enter_motion_state()

            case (MyState.WASP_IN_BOX, MyEvent.UPDATE) if not have_required():
                enter_unoccupied_state()

            case (MyState.OTHER, MyEvent.MOTION):
                if doors_closed():
                    enter_wasp_in_box_state()
                else:
                    enter_motion_state()

            case (MyState.OTHER, MyEvent.UPDATE):
                if not (have_other() and have_required()):
                    enter_unoccupied_state()

            case _:
                _LOGGER.debug(
                    "%s; state=%s; ignored '%s' event",
                    self.name,
                    self._state,
                    event,
                )
