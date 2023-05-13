"""TODO."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.backports.enum import StrEnum
from homeassistant.components.fan import ATTR_PERCENTAGE, ATTR_PERCENTAGE_STEP
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.fan import SERVICE_SET_PERCENTAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State
from homeassistant.helpers.event import async_track_time_interval

from .base_controller import BaseController
from .const import LOGGER, CeilingFanConfig
from .util import extrapolate_value, remove_empty, state_with_unit, summer_simmer_index

IGNORE_STATES = (STATE_UNKNOWN, STATE_UNAVAILABLE)
ON_OFF = (STATE_ON, STATE_OFF)


class MyState(StrEnum):
    """TODO."""

    INIT = "init"
    OFF = "off"
    ON = "on"
    ON_MANUAL = "on_manual"
    OFF_MANUAL = "off_manual"


class MyEvent(StrEnum):
    """TODO."""

    OFF = "off"
    ON = "on"
    TIMER = "timer"
    UPDATE_FAN_SPEED = "update_fan_speed"


class CeilingFanController(BaseController):
    """Representation of a Ceiling Fan Controller."""

    _temp: tuple[float, str] | None = None
    _humidity: tuple[float, str] | None = None
    _prereq_state: str | None = None

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the controller."""
        super().__init__(hass, config_entry, MyState.INIT)

        self.temp_sensor: str = self.data[CeilingFanConfig.TEMP_SENSOR]
        self.humidity_sensor: str = self.data[CeilingFanConfig.HUMIDITY_SENSOR]
        self.prerequisite_entity: str | None = self.data.get(
            CeilingFanConfig.PREREQUISITE_ENTITY
        )

        self.ssi_range = (
            float(self.data[CeilingFanConfig.SSI_MIN]),
            float(self.data[CeilingFanConfig.SSI_MAX]),
        )

        self.speed_range = (
            float(self.data[CeilingFanConfig.SPEED_MIN]),
            float(self.data[CeilingFanConfig.SPEED_MAX]),
        )

        manual_control_minutes = self.data.get(CeilingFanConfig.MANUAL_CONTROL_MINUTES)
        self._manual_control_period = (
            timedelta(minutes=manual_control_minutes)
            if manual_control_minutes
            else None
        )

        self.tracked_entity_ids = remove_empty(
            [
                self.controlled_entity,
                self.temp_sensor,
                self.humidity_sensor,
                self.prerequisite_entity,
            ]
        )

    async def async_setup(self, hass) -> CALLBACK_TYPE:
        """TODO."""
        unsubscriber = await super().async_setup(hass)

        self._unsubscribers.append(
            async_track_time_interval(hass, self._on_poll, timedelta(seconds=60))
        )

        await self._process_event(MyEvent.UPDATE_FAN_SPEED)
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

            case self.humidity_sensor:
                self._humidity = state_with_unit(state, PERCENTAGE)

            case self.prerequisite_entity:
                self._prereq_state = state.state
                await self._process_event(MyEvent.UPDATE_FAN_SPEED)

    async def on_timer_expired(self) -> None:
        """Handle timer expiration from base."""
        await self._process_event(MyEvent.TIMER)

    async def _on_poll(
        self,
        now: datetime,  # noqa: 501  pylint: disable=unused-argument
    ) -> None:
        LOGGER.debug("%s; state=%s; polling for changes", self.name, self._state)
        await self._process_event(MyEvent.UPDATE_FAN_SPEED)

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

            case (MyState.OFF, MyEvent.ON):
                self.set_state(
                    MyState.ON_MANUAL if self._manual_control_period else MyState.ON
                )
                self.set_timer(self._manual_control_period)

            case (MyState.OFF, MyEvent.UPDATE_FAN_SPEED):
                if fan_on := await self._set_fan_speed():
                    self.set_state(MyState.ON)

            case (MyState.ON, MyEvent.OFF):
                self.set_state(
                    MyState.OFF_MANUAL if self._manual_control_period else MyState.OFF
                )
                self.set_timer(self._manual_control_period)

            case (MyState.ON, MyEvent.UPDATE_FAN_SPEED):
                if not (fan_on := await self._set_fan_speed()):
                    self.set_state(MyState.OFF)

            case (MyState.OFF_MANUAL, MyEvent.ON):
                self.set_timer(None)
                fan_on = await self._set_fan_speed()
                self.set_state(MyState.ON if fan_on else MyState.OFF)

            case (MyState.OFF_MANUAL, MyEvent.TIMER):
                fan_on = await self._set_fan_speed()
                self.set_state(MyState.ON if fan_on else MyState.OFF)

            case (MyState.ON_MANUAL, MyEvent.OFF):
                self.set_timer(None)
                fan_on = await self._set_fan_speed()
                self.set_state(MyState.ON if fan_on else MyState.OFF)

            case (MyState.ON_MANUAL, MyEvent.TIMER):
                fan_on = await self._set_fan_speed()
                self.set_state(MyState.ON if fan_on else MyState.OFF)

            case _:
                LOGGER.debug(
                    "%s; state=%s; ignored '%s' event",
                    self.name,
                    self._state,
                    event,
                )

    async def _set_fan_speed(self) -> bool:
        if self._temp is None or self._humidity is None:
            return False

        ssi = summer_simmer_index(self.hass, self._temp, self._humidity[0])
        ssi_speed = extrapolate_value(
            ssi, self.ssi_range, self.speed_range, low_default=0
        )

        fan_state = self.hass.states.get(self.controlled_entity)
        speed_step = fan_state.attributes.get(ATTR_PERCENTAGE_STEP, 100)

        curr_speed = (
            fan_state.attributes.get(ATTR_PERCENTAGE, 100)
            if fan_state.state == STATE_ON
            else 0
        )
        new_speed = (
            round(ssi_speed / speed_step, 0) * speed_step
            if self._prereq_state != STATE_OFF
            else 0
        )

        if new_speed != curr_speed:
            LOGGER.debug(
                "%s; state=%s; changing speed to %.0f percent for SSI %.1f",
                self.name,
                self._state,
                new_speed,
                ssi,
            )
            await self.hass.services.async_call(
                FAN_DOMAIN,
                SERVICE_SET_PERCENTAGE,
                {ATTR_ENTITY_ID: self.controlled_entity, ATTR_PERCENTAGE: new_speed},
            )

        return new_speed > 0
