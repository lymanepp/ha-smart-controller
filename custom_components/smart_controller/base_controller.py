"""TODO."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.util import dt

from .const import LOGGER, CommonConfig

IGNORE_STATES = (STATE_UNKNOWN, STATE_UNAVAILABLE)
ON_OFF = (STATE_ON, STATE_OFF)


class BaseController:
    """TODO."""

    name: str | None = None
    tracked_entity_ids: list[str] | None = None
    _timer_unsub: CALLBACK_TYPE | None = None
    _unsubscribers: list[CALLBACK_TYPE] = []

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, initial_state: str
    ) -> None:
        """Initialize the controller."""

        self.hass = hass
        self._state = initial_state
        self.data: Mapping[str, Any] = config_entry.data | config_entry.options
        self.controlled_entity: str = self.data[CommonConfig.CONTROLLED_ENTITY]

    async def async_setup(self, hass) -> CALLBACK_TYPE:
        """TODO."""
        for entity_id in self.tracked_entity_ids:
            state = hass.states.get(entity_id)
            if state is not None:
                if entity_id == self.controlled_entity:
                    self.name = state.name
                await self._on_state_change(state)
            else:
                LOGGER.warning(
                    "%s; referenced entity '%s' is missing.", self.name, entity_id
                )

        async def on_state_event(event: Event) -> None:
            await self._on_state_change(event.data["new_state"])

        self._unsubscribers.append(
            async_track_state_change_event(
                hass, self.tracked_entity_ids, on_state_event
            )
        )

        def remove_listeners() -> None:
            while self._unsubscribers:
                unsubscriber = self._unsubscribers.pop()
                unsubscriber()

        return remove_listeners

    @property
    def state(self) -> str | int:
        """Return the state."""
        return self._state

    async def _on_state_change(self, state: State) -> None:
        if state is None or state.state in IGNORE_STATES:
            return

        LOGGER.debug(
            "%s; state=%s; %s changed to '%s'",
            self.name,
            self._state,
            state.name,
            state.state,
        )

        await self.on_state_change(state)

    def set_timer(self, period: timedelta | None) -> None:
        """TODO."""

        def timer_expired(_: datetime) -> None:
            self._timer_unsub = None
            self.hass.add_job(self.on_timer_expired)

        if self._timer_unsub is not None:
            self._unsubscribers.remove(self._timer_unsub)
            self._timer_unsub()
            self._timer_unsub = None
            LOGGER.debug("%s; state=%s; canceled timer", self.name, self._state)

        if period is not None:
            self._timer_unsub = async_track_point_in_utc_time(
                self.hass, timer_expired, dt.utcnow() + period
            )
            self._unsubscribers.append(self._timer_unsub)
            LOGGER.debug(
                "%s; state=%s; started timer for '%s'",
                self.name,
                self._state,
                period,
            )

    def set_state(self, new_state):
        """TODO."""
        LOGGER.debug(
            "%s; state=%s; changing state to '%s'",
            self.name,
            self._state,
            new_state,
        )
        self._state = new_state

    async def on_state_change(self, state: State) -> None:
        """Handle entity state changes."""
        raise NotImplementedError

    async def on_timer_expired(self) -> None:
        """Handle timer expiration."""
        raise NotImplementedError
