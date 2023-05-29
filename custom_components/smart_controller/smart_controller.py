"""Base class for controllers."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import CALLBACK_TYPE, Context, Event, HomeAssistant, State
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.util import dt

from .const import _LOGGER, IGNORE_STATES, CommonConfig


class MyContext(Context):
    """Makes it possible to identify state changes triggered by our service calls."""


DEFAULT_ON_STATES: Final = [STATE_ON]


class SmartController:
    """Base class for controllers."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        initial_state: str,
        is_on_states: list[str] | None = None,
    ) -> None:
        """Initialize the controller base."""

        self.hass = hass
        self.config_entry = config_entry
        self._state = initial_state
        self.data: Mapping[str, Any] = config_entry.data | config_entry.options
        self.controlled_entity: str | None = self.data.get(
            CommonConfig.CONTROLLED_ENTITY
        )
        self._is_on_states = is_on_states or DEFAULT_ON_STATES
        self.name: str | None = None
        self.tracked_entity_ids: list[str] = []
        self._timer_unsub: CALLBACK_TYPE | None = None
        self._unsubscribers: list[CALLBACK_TYPE] = []
        self._listeners: list[CALLBACK_TYPE] = []
        self._queued_events: list[Any] = []
        self._started: bool = False

    async def async_setup(self, hass) -> None:
        """Subscribe to state change events for all tracked entities."""
        for entity_id in self.tracked_entity_ids:
            state = hass.states.get(entity_id)
            if state is not None:
                if self.name is None and entity_id == self.controlled_entity:
                    self.name = state.name
                await self._on_state_change(None, state)
            else:
                _LOGGER.warning(
                    "%s; referenced entity '%s' is missing.", self.name, entity_id
                )

        await self._fire_events()
        self._started = True

        async def on_state_event(event: Event) -> None:
            # ignore state change events triggered by service calls from derived controllers
            if not isinstance(event.context, MyContext):
                await self._on_state_change(
                    event.data["old_state"], event.data["new_state"]
                )

        self._unsubscribers.append(
            async_track_state_change_event(
                hass, self.tracked_entity_ids, on_state_event
            )
        )

    def async_unload(self) -> None:
        """Call when controller is being unloaded."""
        while self._unsubscribers:
            unsubscriber = self._unsubscribers.pop()
            unsubscriber()

    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        """Listen for data updates."""

        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        self._listeners.append(update_callback)

        return remove_listener

    def async_update_listeners(self) -> None:
        """Update all registered listeners."""
        for update_callback in self._listeners:
            update_callback()

    @property
    def state(self) -> str:
        """Return the state."""
        return self._state

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state in self._is_on_states

    def set_timer(self, period: timedelta | None) -> None:
        """Start a timer or cancel a timer if time period is 'None'."""

        async def dispatch_timer_expiration() -> None:
            await self.on_timer_expired()
            await self._fire_events()

        def timer_expired(_: datetime) -> None:
            self._timer_unsub = None
            self.hass.add_job(dispatch_timer_expiration)

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
        if self._state == new_state:
            return

        _LOGGER.debug(
            "%s; state=%s; changing state to '%s'",
            self.name,
            self._state,
            new_state,
        )
        self._state = new_state
        self.async_update_listeners()

    def fire_event(self, event: Any) -> None:
        """Fire an event to the controller."""
        self._queued_events.insert(0, event)

    async def on_state_change(self, state: State) -> None:
        """Handle tracked entity state changes."""
        raise NotImplementedError("Must implement 'on_state_change' method.")

    async def on_timer_expired(self) -> None:
        """Handle timer expiration."""
        raise NotImplementedError("Must implement 'on_timer_expired' method.")

    async def on_event(self, event: Any) -> None:
        """Handle controller events."""
        raise NotImplementedError("Must implement 'on_event' method.")

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

    # #### Internal methods ####

    async def _on_state_change(self, old_state: State | None, new_state: State) -> None:
        if (
            new_state is None
            or new_state.state in IGNORE_STATES
            or (old_state and old_state.state == new_state.state)
        ):
            return

        _LOGGER.debug(
            "%s; state=%s; %s changed from '%s' to '%s'",
            self.name,
            self._state,
            new_state.name,
            old_state.state if old_state else None,
            new_state.state,
        )

        await self.on_state_change(new_state)

        if self._started:
            await self._fire_events()

    async def _fire_events(self) -> None:
        while self._queued_events:
            event = self._queued_events.pop()

            _LOGGER.debug(
                "%s; state=%s; processing '%s' event",
                self.name,
                self._state,
                event,
            )

            await self.on_event(event)
