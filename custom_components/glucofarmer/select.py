"""Select platform for GlucoFarmer."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_INSULIN_TYPES,
    CONF_MEALS,
    CONF_SUBJECT_NAME,
    DEFAULT_INSULIN_TYPES,
    DOMAIN,
)
from .coordinator import GlucoFarmerConfigEntry, GlucoFarmerCoordinator

_LOGGER = logging.getLogger(__name__)

CHART_TIMERANGE_OPTIONS = ["3h", "6h", "12h", "24h"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlucoFarmerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GlucoFarmer select entities."""
    coordinator = entry.runtime_data
    subject_name = entry.data[CONF_SUBJECT_NAME]

    form_mode = GlucoFarmerFormModeSelect(coordinator, subject_name, entry)
    meal = GlucoFarmerMealSelect(coordinator, subject_name, entry)

    # Register form select entities with coordinator for cross-entity access
    coordinator.form_mode_entity = form_mode
    coordinator.meal_entity = meal

    async_add_entities([
        form_mode,
        meal,
        GlucoFarmerInsulinTypeSelect(coordinator, subject_name, entry),
        GlucoFarmerChartTimerangeSelect(coordinator, subject_name, entry),
    ])


def _device_info(entry: GlucoFarmerConfigEntry, subject_name: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=subject_name,
        manufacturer="GlucoFarmer",
        model="Subject CGM Monitor",
    )


class GlucoFarmerFormModeSelect(SelectEntity):
    """Controls which input form is visible on page 2."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "form_mode"
    _attr_icon = "mdi:form-select"

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        subject_name: str,
        entry: GlucoFarmerConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_form_mode"
        self._attr_device_info = _device_info(entry, subject_name)
        self._attr_current_option = "—"
        self._attr_options = ["—", "feeding", "insulin", "list"]

    @property
    def options(self) -> list[str]:
        return ["—", "feeding", "insulin", "list"]

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self._coordinator.form_mode = option
        self.async_write_ha_state()


class GlucoFarmerMealSelect(SelectEntity):
    """Meal selection for the feeding form. Auto-fills BE on selection."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "meal"
    _attr_icon = "mdi:food-apple"

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        subject_name: str,
        entry: GlucoFarmerConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_meal"
        self._attr_device_info = _device_info(entry, subject_name)
        self._attr_current_option = "Any"

    @property
    def options(self) -> list[str]:
        meals = self._entry.options.get(CONF_MEALS, [])
        return ["Any"] + [m["name"] for m in meals]

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self._coordinator.meal_selection = option
        # Compute and push BE value to be_amount entity
        be = self._compute_be(option)
        self._coordinator.be_amount = be
        if self._coordinator.be_amount_entity is not None:
            self._coordinator.be_amount_entity.set_suggested_value(be)
        self.async_write_ha_state()

    def _compute_be(self, meal_name: str) -> float:
        if meal_name == "Any":
            return 0.0
        meals = self._entry.options.get(CONF_MEALS, [])
        meal = next((m for m in meals if m["name"] == meal_name), None)
        if meal is None:
            return 0.0
        if "amount" in meal:
            return float(meal["amount"])
        if "be_per_kg" in meal:
            return round(float(meal["be_per_kg"]) * self._coordinator.weight_kg, 2)
        return 0.0


class GlucoFarmerInsulinTypeSelect(SelectEntity):
    """Insulin type selection for the insulin form."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "insulin_type"
    _attr_icon = "mdi:needle"

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        subject_name: str,
        entry: GlucoFarmerConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_insulin_type"
        self._attr_device_info = _device_info(entry, subject_name)
        # Default to first configured type
        types = entry.options.get(CONF_INSULIN_TYPES, DEFAULT_INSULIN_TYPES)
        self._attr_current_option = types[0] if types else None

    @property
    def options(self) -> list[str]:
        return self._entry.options.get(CONF_INSULIN_TYPES, DEFAULT_INSULIN_TYPES)

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self._coordinator.insulin_type_selection = option
        self.async_write_ha_state()


class GlucoFarmerChartTimerangeSelect(SelectEntity):
    """Chart time range selection (global)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "chart_timerange"
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        subject_name: str,
        entry: GlucoFarmerConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_chart_timerange"
        self._attr_device_info = _device_info(entry, subject_name)
        self._attr_current_option = "24h"

    @property
    def options(self) -> list[str]:
        return CHART_TIMERANGE_OPTIONS

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self._coordinator.hass.data.setdefault(DOMAIN, {})["chart_timerange"] = option
        # Refresh all subject coordinators -- chart_timerange is global
        for entry in self._coordinator.hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                await entry.runtime_data.async_request_refresh()
        self.async_write_ha_state()
