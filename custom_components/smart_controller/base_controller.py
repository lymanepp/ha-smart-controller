"""Base class for controllers."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Context, Event, HomeAssistant, State
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.util import dt

from .const import _LOGGER, CommonConfig


class MyContext(Context):
    """Makes it possible to identify state changes triggered by our service calls."""


IGNORE_STATES = (STATE_UNKNOWN, STATE_UNAVAILABLE)
ON_OFF = (STATE_ON, STATE_OFF)


class BaseController:
    """Base class for controllers."""

    name: str | None = None
    tracked_entity_ids: list[str] | None = None
    _timer_unsub: CALLBACK_TYPE | None = None
    _unsubscribers: list[CALLBACK_TYPE] = []

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, initial_state: str
    ) -> None:
        """Initialize the controller base."""

        self.hass = hass
        self._state = initial_state
        self.data: Mapping[str, Any] = config_entry.data | config_entry.options
        self.controlled_entity: str = self.data[CommonConfig.CONTROLLED_ENTITY]

    async def async_setup(self, hass) -> CALLBACK_TYPE:
        """Subscribe to state change events for all tracked entities."""
        for entity_id in self.tracked_entity_ids:
            state = hass.states.get(entity_id)
            if state is not None:
                if entity_id == self.controlled_entity:
                    self.name = state.name
                await self._on_state_change(state)
            else:
                _LOGGER.warning(
                    "%s; referenced entity '%s' is missing.", self.name, entity_id
                )

        async def on_state_event(event: Event) -> None:
            # ignore state change events triggered by service calls from derived controllers
            if not isinstance(event.context, MyContext):
                await self._on_state_change(event.data["new_state"])

        self._unsubscribers.append(
            async_track_state_change_event(hass, self.tracked_entity_ids, on_state_event)
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

        _LOGGER.debug(
            "%s; state=%s; %s changed to '%s'",
            self.name,
            self._state,
            state.name,
            state.state,
        )

        await self.on_state_change(state)

    def set_timer(self, period: timedelta | None) -> None:
        """Start a timer or cancel a timer if time period is 'None'."""

        def timer_expired(_: datetime) -> None:
            self._timer_unsub = None
            self.hass.add_job(self.on_timer_expired)

        if self._timer_unsub is not None:
            self._unsubscribers.remove(self._timer_unsub)
            self._timer_unsub()
            self._timer_unsub = None
            _LOGGER.debug("%s; state=%s; canceled timer", self.name, self._state)

        if period is not None:
            self._timer_unsub = async_track_point_in_utc_time(
                self.hass, timer_expired, dt.utcnow() + period
            )
            self._unsubscribers.append(self._timer_unsub)
            _LOGGER.debug(
                "%s; state=%s; started timer for '%s'",
                self.name,
                self._state,
                period,
            )

    def set_state(self, new_state: str):
        """Change the current state."""
        _LOGGER.debug(
            "%s; state=%s; changing state to '%s'",
            self.name,
            self._state,
            new_state,
        )
        self._state = new_state

    async def on_state_change(self, state: State) -> None:
        """Handle tracked entity state changes."""
        raise NotImplementedError

    async def on_timer_expired(self) -> None:
        """Handle timer expiration."""
        raise NotImplementedError

    async def async_service_call(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
    ) -> bool | None:
        """Call a service."""

        _LOGGER.debug(
            "%s; state=%s; calling '%s.%s' service",
            self.name,
            self._state,
            domain,
            service,
        )

        return await self.hass.services.async_call(
            domain,
            service,
            service_data,
            target={ATTR_ENTITY_ID: self.controlled_entity},
            context=MyContext(),
        )
