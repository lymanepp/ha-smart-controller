"""TODO."""

from collections.abc import Iterable
from math import e

from homeassistant import util
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.unit_conversion import TemperatureConverter

ON_OFF = (STATE_ON, STATE_OFF)


def absolute_humidity(temp: tuple[float, str], r_h: float):
    """Calculate absolution humidity."""
    t_c = TemperatureConverter.convert(*temp, TEMP_CELSIUS)

    return r_h * 6.112 * 2.1674 * e ** ((t_c * 17.67) / (t_c + 243.5)) / (t_c + 273.15)


def summer_simmer_index(hass: HomeAssistant, temp: tuple[float, str], r_h: float):
    """TODO."""
    t_f = TemperatureConverter.convert(*temp, TEMP_FAHRENHEIT)

    ssi = 1.98 * (t_f - (0.55 - (0.0055 * r_h)) * (t_f - 58)) - 56.83

    return TemperatureConverter.convert(
        ssi, TEMP_FAHRENHEIT, hass.config.units.temperature_unit
    )


def remove_empty(values):
    """Remove entries if they contain 'None'."""
    return [value for value in values if value is not None]


def state_with_unit(state: State, default_unit: str) -> tuple[float, str]:
    """Return state's value with unit of measurement as a tuple."""
    return (
        util.convert(state.state, float),
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, default_unit),
    )


def extrapolate_value(
    value: float,
    source_range: tuple[float, float],
    target_range: tuple[float, float],
    low_default: float | None = None,
    high_default: float | None = None,
):
    """TODO."""
    if value < source_range[0]:
        return target_range[0] if low_default is None else low_default

    if value > source_range[1]:
        return target_range[1] if high_default is None else high_default

    return percentage_to_ranged_value(
        target_range,
        ranged_value_to_percentage(source_range, value),
    )


def domain_entities(
    hass: HomeAssistant,
    domains: Iterable[str],
    device_class: str | None = None,
) -> list[str]:
    """Get list of matching entities."""

    entity_ids = set()
    ent_reg = entity_registry.async_get(hass)

    for state in hass.states.async_all(domains):
        entity = ent_reg.async_get(state.entity_id)
        if (entity is None or not entity.hidden) and (
            device_class is None
            or device_class == state.attributes.get(ATTR_DEVICE_CLASS)
        ):
            entity_ids.add(state.entity_id)

    return sorted(entity_ids)


def on_off_entities(
    hass: HomeAssistant,
    excluded_domains: Iterable[str],
) -> list[str]:
    """Get list of entities with on/off state."""

    entity_ids = set()
    ent_reg = entity_registry.async_get(hass)

    for state in hass.states.async_all():
        if state.domain not in excluded_domains and state.state in ON_OFF:
            entity = ent_reg.async_get(state.entity_id)
            if entity is None or not entity.hidden:
                entity_ids.add(state.entity_id)

    return sorted(entity_ids)
