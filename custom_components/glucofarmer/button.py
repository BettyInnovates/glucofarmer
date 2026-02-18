"""Button platform for GlucoFarmer presets and actions."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_PIG_NAME,
    CONF_PRESETS,
    DOMAIN,
    PRESET_TYPE_FEEDING,
    PRESET_TYPE_INSULIN,
)
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
    pig_name = entry.data[CONF_PIG_NAME]
    store: GlucoFarmerStore = hass.data[DOMAIN]["store"]

    entities: list[ButtonEntity] = []

    # Preset buttons
    presets: list[dict[str, Any]] = entry.options.get(CONF_PRESETS, [])
    for preset in presets:
        entities.append(
            GlucoFarmerPresetButton(
                coordinator, store, preset, pig_name, entry.entry_id
            )
        )

    # Action buttons
    entities.extend([
        GlucoFarmerLogFeedingButton(coordinator, pig_name, entry.entry_id, store),
        GlucoFarmerLogInsulinButton(coordinator, pig_name, entry.entry_id, store),
        GlucoFarmerArchiveEventButton(coordinator, pig_name, entry.entry_id, store),
    ])

    async_add_entities(entities)


class GlucoFarmerPresetButton(ButtonEntity):
    """Button entity that logs a preset with one press."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        store: GlucoFarmerStore,
        preset: dict[str, Any],
        pig_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the preset button."""
        self._coordinator = coordinator
        self._store = store
        self._preset = preset
        self._pig_name = pig_name
        preset_slug = preset["name"].lower().replace(" ", "_")
        self._attr_unique_id = f"{entry_id}_preset_{preset_slug}"
        self._attr_name = preset["name"]
        self._attr_icon = (
            "mdi:needle" if preset["type"] == PRESET_TYPE_INSULIN else "mdi:food-apple"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=pig_name,
            manufacturer="GlucoFarmer",
            model="Pig CGM Monitor",
        )

    async def async_press(self) -> None:
        """Handle button press: log the preset event."""
        preset_type = self._preset["type"]
        amount = self._preset.get("amount", 0)

        if preset_type == PRESET_TYPE_INSULIN:
            product = self._preset.get("product", "")
            await self._store.async_log_insulin(
                pig_name=self._pig_name,
                product=product,
                amount=amount,
            )
            _LOGGER.info(
                "Preset '%s' executed: %s %s IU for %s",
                self._preset["name"],
                product,
                amount,
                self._pig_name,
            )
        elif preset_type == PRESET_TYPE_FEEDING:
            category = self._preset.get("category", "other")
            await self._store.async_log_feeding(
                pig_name=self._pig_name,
                amount=amount,
                category=category,
            )
            _LOGGER.info(
                "Preset '%s' executed: %s BE (%s) for %s",
                self._preset["name"],
                amount,
                category,
                self._pig_name,
            )

        await self._coordinator.async_request_refresh()


class GlucoFarmerLogFeedingButton(ButtonEntity):
    """Button that logs a feeding event from current input values."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "log_feeding"
    _attr_icon = "mdi:food-apple-outline"

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        pig_name: str,
        entry_id: str,
        store: GlucoFarmerStore,
    ) -> None:
        """Initialize the log feeding button."""
        self._coordinator = coordinator
        self._pig_name = pig_name
        self._store = store
        self._attr_unique_id = f"{entry_id}_log_feeding"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=pig_name,
            manufacturer="GlucoFarmer",
            model="Pig CGM Monitor",
        )

    async def async_press(self) -> None:
        """Handle button press - log feeding from input values."""
        amount = self._coordinator.feeding_amount
        category = self._coordinator.feeding_category or "other"
        timestamp = self._coordinator.event_timestamp or None

        await self._store.async_log_feeding(
            pig_name=self._pig_name,
            amount=amount,
            category=category,
            timestamp=timestamp,
        )
        _LOGGER.info(
            "Logged feeding: %s BE (%s) for %s", amount, category, self._pig_name
        )
        await self._coordinator.async_request_refresh()


class GlucoFarmerLogInsulinButton(ButtonEntity):
    """Button that logs an insulin event from current input values."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "log_insulin"
    _attr_icon = "mdi:needle"

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        pig_name: str,
        entry_id: str,
        store: GlucoFarmerStore,
    ) -> None:
        """Initialize the log insulin button."""
        self._coordinator = coordinator
        self._pig_name = pig_name
        self._store = store
        self._attr_unique_id = f"{entry_id}_log_insulin"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=pig_name,
            manufacturer="GlucoFarmer",
            model="Pig CGM Monitor",
        )

    async def async_press(self) -> None:
        """Handle button press - log insulin from input values."""
        amount = self._coordinator.insulin_amount
        product = self._coordinator.insulin_product or ""
        timestamp = self._coordinator.event_timestamp or None

        await self._store.async_log_insulin(
            pig_name=self._pig_name,
            product=product,
            amount=amount,
            timestamp=timestamp,
        )
        _LOGGER.info(
            "Logged insulin: %s IU (%s) for %s", amount, product, self._pig_name
        )
        await self._coordinator.async_request_refresh()


class GlucoFarmerArchiveEventButton(ButtonEntity):
    """Button that archives an event by ID."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "archive_event"
    _attr_icon = "mdi:archive-arrow-down"

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        pig_name: str,
        entry_id: str,
        store: GlucoFarmerStore,
    ) -> None:
        """Initialize the archive event button."""
        self._coordinator = coordinator
        self._pig_name = pig_name
        self._store = store
        self._attr_unique_id = f"{entry_id}_archive_event"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=pig_name,
            manufacturer="GlucoFarmer",
            model="Pig CGM Monitor",
        )

    async def async_press(self) -> None:
        """Handle button press - archive the event."""
        event_id = self._coordinator.archive_event_id
        if not event_id:
            _LOGGER.warning("No event ID provided for archiving")
            return

        deleted = await self._store.async_delete_event(event_id)
        if deleted:
            _LOGGER.info("Archived event %s", event_id)
            self._coordinator.archive_event_id = ""
            await self._coordinator.async_request_refresh()
        else:
            _LOGGER.warning("Event %s not found or already archived", event_id)
