"""Text platform for GlucoFarmer."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_PIG_NAME, DOMAIN
from .coordinator import GlucoFarmerConfigEntry, GlucoFarmerCoordinator


@dataclass(frozen=True, kw_only=True)
class GlucoFarmerTextEntityDescription(TextEntityDescription):
    """Describe a GlucoFarmer text entity."""

    coordinator_attr: str


TEXT_DESCRIPTIONS: tuple[GlucoFarmerTextEntityDescription, ...] = (
    GlucoFarmerTextEntityDescription(
        key="event_timestamp",
        translation_key="event_timestamp",
        coordinator_attr="event_timestamp",
    ),
    GlucoFarmerTextEntityDescription(
        key="archive_event_id",
        translation_key="archive_event_id",
        coordinator_attr="archive_event_id",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlucoFarmerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GlucoFarmer text entities."""
    coordinator = entry.runtime_data
    pig_name = entry.data[CONF_PIG_NAME]

    async_add_entities(
        GlucoFarmerTextEntity(coordinator, description, pig_name, entry.entry_id)
        for description in TEXT_DESCRIPTIONS
    )


class GlucoFarmerTextEntity(TextEntity):
    """GlucoFarmer text input entity."""

    entity_description: GlucoFarmerTextEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_native_value = ""

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        description: GlucoFarmerTextEntityDescription,
        pig_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the text entity."""
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=pig_name,
            manufacturer="GlucoFarmer",
            model="Pig CGM Monitor",
        )

    async def async_set_value(self, value: str) -> None:
        """Set text value and update coordinator."""
        self._attr_native_value = value
        setattr(self._coordinator, self.entity_description.coordinator_attr, value)
        self.async_write_ha_state()
