"""Representation of a Light Controller."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State

from .base_controller import BaseController
from .const import LOGGER, LightConfig
from .util import remove_empty

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
    MOTION = "motion"
    TIMER = "timer"


class LightController(BaseController):
    """Representation of a Light Controller."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Light Controller."""
        super().__init__(hass, config_entry, MyState.INIT)

        self.motion_sensor: str | None = self.data.get(LightConfig.MOTION_SENSOR)
        self.illuminance_sensor = self.data.get(LightConfig.ILLUMINANCE_SENSOR)
        self.illuminance_cutoff = self.data.get(LightConfig.ILLUMINANCE_CUTOFF)
        self.on_blocker = self.data.get(LightConfig.ON_BLOCKER_ENTITY)
        self.off_blocker = self.data.get(LightConfig.OFF_BLOCKER_ENTITY)

        auto_off_minutes = self.data.get(LightConfig.AUTO_OFF_MINUTES)
        manual_control_minutes = self.data.get(LightConfig.MANUAL_CONTROL_MINUTES)

        self._auto_off_period = (
            timedelta(minutes=auto_off_minutes) if auto_off_minutes else None
        )

        self._manual_control_period = (
            timedelta(minutes=manual_control_minutes)
            if manual_control_minutes
            else None
        )

        self.tracked_entity_ids = remove_empty(
            [
                self.controlled_entity,
                self.motion_sensor,
            ]
        )

    async def on_state_change(self, state: State) -> None:
        """Handle entity state changes from base."""
        match state.entity_id:
            case self.controlled_entity if state.state in ON_OFF:
                await self._process_event(
                    MyEvent.ON if state.state == STATE_ON else MyEvent.OFF
                )

            case self.motion_sensor if state.state == STATE_ON:
                await self._process_event(MyEvent.MOTION)

    async def on_timer_expired(self) -> None:
        """Handle timer expiration from base."""
        await self._process_event(MyEvent.TIMER)

    async def _process_event(self, event: MyEvent) -> None:
        LOGGER.debug(
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
                self.set_timer(self._auto_off_period)

            case (MyState.OFF, MyEvent.ON):
                if self._manual_control_period:
                    self.set_state(MyState.ON_MANUAL)
                    self.set_timer(self._manual_control_period)
                else:
                    self.set_state(MyState.ON)
                    self.set_timer(self._auto_off_period)

            case (MyState.OFF, MyEvent.MOTION):
                if self.on_blocker:
                    blocker = self.hass.states.get(self.on_blocker)
                    if blocker and blocker.state == STATE_ON:
                        return

                if self.illuminance_sensor and self.illuminance_cutoff is not None:
                    illuminance = self.hass.states.get(self.illuminance_sensor)
                    if (
                        illuminance
                        and float(illuminance.state) > self.illuminance_cutoff
                    ):
                        return

                await self._set_light_mode(STATE_ON)
                self.set_state(MyState.ON)
                self.set_timer(self._auto_off_period)

            case (MyState.ON, MyEvent.OFF):
                if self._manual_control_period:
                    self.set_state(MyState.OFF_MANUAL)
                    self.set_timer(self._manual_control_period)
                else:
                    self.set_state(MyState.OFF)

            case (MyState.ON, MyEvent.MOTION):
                self.set_timer(self._auto_off_period)

            case (MyState.ON, MyEvent.TIMER):
                if self.off_blocker:
                    blocker = self.hass.states.get(self.off_blocker)
                    if blocker and blocker.state == STATE_ON:
                        return

                await self._set_light_mode(STATE_OFF)
                self.set_state(MyState.OFF)

            case (MyState.OFF_MANUAL, MyEvent.ON):
                self.set_state(MyState.ON)
                self.set_timer(self._auto_off_period)

            case (MyState.OFF_MANUAL, MyEvent.TIMER):
                self.set_state(MyState.OFF)

            case (MyState.ON_MANUAL, MyEvent.OFF):
                self.set_state(MyState.OFF)
                self.set_timer(None)

            case (MyState.ON_MANUAL, MyEvent.TIMER):
                self.set_state(MyState.ON)
                self.set_timer(self._auto_off_period)

            case _:
                LOGGER.debug(
                    "%s; state=%s; ignored '%s' event",
                    self.name,
                    self._state,
                    event,
                )

    async def _set_light_mode(self, mode: str):
        await self.async_service_call(
            Platform.LIGHT,
            SERVICE_TURN_ON if mode == STATE_ON else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self.controlled_entity},
        )
