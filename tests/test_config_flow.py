import pytest
from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import InvalidData
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.smart_controller.const import (
    Config,
    ControllerType,
)


@pytest.mark.asyncio
async def test_user_flow_starts_at_menu(
    hass: HomeAssistant,
):
    result = await hass.config_entries.flow.async_init(
        "smart_controller",
        context={
            "source": "user",
        },
    )

    assert result["type"] == (
        data_entry_flow.FlowResultType.MENU
    )

    assert "menu_options" in result
    assert result["menu_options"]


@pytest.mark.asyncio
async def test_light_menu_selection_is_handled(
    hass: HomeAssistant,
):
    result = await hass.config_entries.flow.async_init(
        "smart_controller",
        context={
            "source": "user",
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "next_step_id": "light",
        },
    )

    assert result["type"] in (
        data_entry_flow.FlowResultType.FORM,
        data_entry_flow.FlowResultType.CREATE_ENTRY,
        data_entry_flow.FlowResultType.ABORT,
    )


@pytest.mark.asyncio
async def test_multiple_flow_inits_do_not_crash(
    hass: HomeAssistant,
):
    result1 = await hass.config_entries.flow.async_init(
        "smart_controller",
        context={
            "source": "user",
        },
    )

    result2 = await hass.config_entries.flow.async_init(
        "smart_controller",
        context={
            "source": "user",
        },
    )

    assert result1 is not None
    assert result2 is not None


@pytest.mark.asyncio
async def test_flow_result_has_required_structure(
    hass: HomeAssistant,
):
    result = await hass.config_entries.flow.async_init(
        "smart_controller",
        context={
            "source": "user",
        },
    )

    assert "type" in result


@pytest.mark.asyncio
async def test_flow_rejects_invalid_menu_option(
    hass: HomeAssistant,
):
    result = await hass.config_entries.flow.async_init(
        "smart_controller",
        context={
            "source": "user",
        },
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "next_step_id":
                    "this_does_not_exist",
            },
        )


@pytest.mark.asyncio
async def test_existing_entry_does_not_break_flow(
    hass: HomeAssistant,
):
    entry = MockConfigEntry(
        domain="smart_controller",
        title="Existing Controller",
        unique_id="existing-controller",
        data={
            Config.CONTROLLER_TYPE:
                ControllerType.LIGHT,
        },
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "smart_controller",
        context={
            "source": "user",
        },
    )

    assert result["type"] in (
        data_entry_flow.FlowResultType.MENU,
        data_entry_flow.FlowResultType.FORM,
    )


@pytest.mark.asyncio
async def test_all_menu_options_are_selectable(
    hass: HomeAssistant,
):
    result = await hass.config_entries.flow.async_init(
        "smart_controller",
        context={
            "source": "user",
        },
    )

    assert result["type"] == (
        data_entry_flow.FlowResultType.MENU
    )

    for option in result["menu_options"]:
        subresult = await hass.config_entries.flow.async_init(
            "smart_controller",
            context={
                "source": "user",
            },
        )

        subresult = await hass.config_entries.flow.async_configure(
            subresult["flow_id"],
            {
                "next_step_id": option,
            },
        )

        assert subresult["type"] in (
            data_entry_flow.FlowResultType.FORM,
            data_entry_flow.FlowResultType.CREATE_ENTRY,
            data_entry_flow.FlowResultType.ABORT,
            data_entry_flow.FlowResultType.MENU,
        )
