"""Select platform for GlucoFarmer."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_FEEDING_CATEGORIES,
    CONF_INSULIN_PRODUCTS,
    CONF_PIG_NAME,
    DEFAULT_FEEDING_CATEGORIES,
    DEFAULT_INSULIN_PRODUCTS,
    DOMAIN,
)
from .coordinator import GlucoFarmerConfigEntry, GlucoFarmerCoordinator


CHART_TIMERANGE_OPTIONS = ["3h", "6h", "12h", "24h"]


@dataclass(frozen=True, kw_only=True)
class GlucoFarmerSelectEntityDescription(SelectEntityDescription):
    """Describe a GlucoFarmer select entity."""

    default_option: str | None = None


SELECT_DESCRIPTIONS: tuple[GlucoFarmerSelectEntityDescription, ...] = (
    GlucoFarmerSelectEntityDescription(
        key="feeding_category",
        translation_key="feeding_category",
    ),
    GlucoFarmerSelectEntityDescription(
        key="insulin_product",
        translation_key="insulin_product",
    ),
    GlucoFarmerSelectEntityDescription(
        key="chart_timerange",
        translation_key="chart_timerange",
        default_option="24h",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlucoFarmerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GlucoFarmer select entities."""
    coordinator = entry.runtime_data
    pig_name = entry.data[CONF_PIG_NAME]

    async_add_entities(
        GlucoFarmerSelectEntity(coordinator, description, pig_name, entry)
        for description in SELECT_DESCRIPTIONS
    )


class GlucoFarmerSelectEntity(SelectEntity):
    """GlucoFarmer select entity."""

    entity_description: GlucoFarmerSelectEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        description: GlucoFarmerSelectEntityDescription,
        pig_name: str,
        entry: GlucoFarmerConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        self.entity_description = description
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=pig_name,
            manufacturer="GlucoFarmer",
            model="Pig CGM Monitor",
        )
        self._attr_current_option = description.default_option

    @property
    def options(self) -> list[str]:
        """Return available options dynamically from config."""
        match self.entity_description.key:
            case "feeding_category":
                return list(
                    self._entry.options.get(
                        CONF_FEEDING_CATEGORIES, DEFAULT_FEEDING_CATEGORIES
                    )
                )
            case "insulin_product":
                products = self._entry.options.get(
                    CONF_INSULIN_PRODUCTS, DEFAULT_INSULIN_PRODUCTS
                )
                return [p["name"] for p in products]
            case "chart_timerange":
                return CHART_TIMERANGE_OPTIONS
        return []

    async def async_select_option(self, option: str) -> None:
        """Handle option selection."""
        self._attr_current_option = option
        match self.entity_description.key:
            case "feeding_category":
                self._coordinator.feeding_category = option
            case "insulin_product":
                self._coordinator.insulin_product = option
            case "chart_timerange":
                self._coordinator.hass.data.setdefault(DOMAIN, {})[
                    "chart_timerange"
                ] = option
        self.async_write_ha_state()
