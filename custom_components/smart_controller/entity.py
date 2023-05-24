"""BlueprintEntity class."""
from __future__ import annotations

from homeassistant.const import ATTR_SW_VERSION
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.loader import async_get_custom_components

from .const import DOMAIN, NAME
from .smart_controller import SmartController


class SmartControllerEntity(Entity):
    """SmartControllerEntity class."""

    def __init__(self, controller: SmartController) -> None:
        """Initialize."""
        self.hass = controller.hass
        self.controller = controller
        self._attr_unique_id = controller.config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            entry_type=DeviceEntryType.SERVICE,
            name=NAME,
            manufacturer=NAME,
        )
        self.hass.async_create_task(self._set_sw_version())

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(self.controller.async_add_listener(self._update_callback))
        self._update_callback()

    # #### Internal methods ####

    @callback
    def _update_callback(self) -> None:
        """Load data from controller."""
        self._attr_state = self.controller.state
        self.async_write_ha_state()

    async def _set_sw_version(self) -> None:
        custom_components = await async_get_custom_components(self.hass)
        self.device_info[ATTR_SW_VERSION] = custom_components[DOMAIN].version.string
