"""Button platform for GlucoFarmer log actions."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SUBJECT_NAME, DOMAIN
from .coordinator import GlucoFarmerConfigEntry, GlucoFarmerCoordinator
from .store import GlucoFarmerStore

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlucoFarmerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GlucoFarmer button entities."""
    coordinator = entry.runtime_data
    subject_name = entry.data[CONF_SUBJECT_NAME]
    store: GlucoFarmerStore = hass.data[DOMAIN]["store"]

    async_add_entities([
        GlucoFarmerLogFeedingButton(coordinator, subject_name, entry.entry_id, store),
        GlucoFarmerLogInsulinButton(coordinator, subject_name, entry.entry_id, store),
    ])


def _device_info(entry_id: str, subject_name: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=subject_name,
        manufacturer="GlucoFarmer",
        model="Subject CGM Monitor",
    )


class GlucoFarmerLogFeedingButton(ButtonEntity):
    """Logs a feeding event from current form values, then resets the form."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "log_feeding"
    _attr_icon = "mdi:food-apple-outline"

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        subject_name: str,
        entry_id: str,
        store: GlucoFarmerStore,
    ) -> None:
        self._coordinator = coordinator
        self._subject_name = subject_name
        self._store = store
        self._attr_unique_id = f"{entry_id}_log_feeding"
        self._attr_device_info = _device_info(entry_id, subject_name)

    async def async_press(self) -> None:
        """Log feeding event and reset form."""
        c = self._coordinator
        amount = c.be_amount
        meal_type = c.meal_selection
        minutes_ago = c.minutes_ago
        timestamp = (datetime.now() - timedelta(minutes=minutes_ago)).isoformat()

        await self._store.async_log_feeding(
            subject_name=self._subject_name,
            amount=amount,
            category=meal_type,
            timestamp=timestamp,
        )
        _LOGGER.info(
            "Logged feeding: %.1f BE (%s) for %s (-%d min)",
            amount, meal_type, self._subject_name, minutes_ago,
        )

        # Reset form entities
        if c.be_amount_entity is not None:
            c.be_amount_entity.set_suggested_value(0.0)
        if c.minutes_ago_entity is not None:
            c.minutes_ago_entity.reset()
        if c.meal_entity is not None:
            await c.meal_entity.async_select_option("Any")
        if c.form_mode_entity is not None:
            await c.form_mode_entity.async_select_option("list")

        await c.async_request_refresh()


class GlucoFarmerLogInsulinButton(ButtonEntity):
    """Logs an insulin event from current form values, then resets the form."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "log_insulin"
    _attr_icon = "mdi:needle"

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        subject_name: str,
        entry_id: str,
        store: GlucoFarmerStore,
    ) -> None:
        self._coordinator = coordinator
        self._subject_name = subject_name
        self._store = store
        self._attr_unique_id = f"{entry_id}_log_insulin"
        self._attr_device_info = _device_info(entry_id, subject_name)

    async def async_press(self) -> None:
        """Log insulin event and reset form."""
        c = self._coordinator
        amount = c.insulin_units
        insulin_type = c.insulin_type_selection
        minutes_ago = c.minutes_ago
        timestamp = (datetime.now() - timedelta(minutes=minutes_ago)).isoformat()

        await self._store.async_log_insulin(
            subject_name=self._subject_name,
            product=insulin_type,
            amount=amount,
            timestamp=timestamp,
        )
        _LOGGER.info(
            "Logged insulin: %.1f IU (%s) for %s (-%d min)",
            amount, insulin_type, self._subject_name, minutes_ago,
        )

        # Reset form entities
        if c.insulin_units_entity is not None:
            c.insulin_units_entity.reset()
        if c.minutes_ago_entity is not None:
            c.minutes_ago_entity.reset()
        if c.form_mode_entity is not None:
            await c.form_mode_entity.async_select_option("list")

        await c.async_request_refresh()
