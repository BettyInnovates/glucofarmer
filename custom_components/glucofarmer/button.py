"""Button platform for GlucoFarmer presets."""

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
    """Set up GlucoFarmer preset button entities."""
    coordinator = entry.runtime_data
    pig_name = entry.data[CONF_PIG_NAME]
    presets: list[dict[str, Any]] = entry.options.get(CONF_PRESETS, [])
    store: GlucoFarmerStore = hass.data[DOMAIN]["store"]

    async_add_entities(
        GlucoFarmerPresetButton(
            coordinator, store, preset, pig_name, entry.entry_id
        )
        for preset in presets
    )


class GlucoFarmerPresetButton(ButtonEntity):
    """Button entity that logs a preset with one press."""

    _attr_has_entity_name = True
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
        self._attr_name = f"Preset: {preset['name']}"
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

        # Trigger coordinator refresh to update daily totals
        await self._coordinator.async_request_refresh()
