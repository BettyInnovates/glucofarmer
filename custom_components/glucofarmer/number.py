"""Number platform for GlucoFarmer thresholds and input amounts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_PIG_NAME,
    DEFAULT_CRITICAL_LOW_THRESHOLD,
    DEFAULT_DATA_TIMEOUT,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_VERY_HIGH_THRESHOLD,
    DOMAIN,
)
from .coordinator import GlucoFarmerConfigEntry, GlucoFarmerCoordinator


@dataclass(frozen=True, kw_only=True)
class GlucoFarmerNumberEntityDescription(NumberEntityDescription):
    """Describe a GlucoFarmer number entity."""

    default_value: float
    setter_fn: Callable[[GlucoFarmerCoordinator, float], None]


def _set_low(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.low_threshold = value


def _set_high(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.high_threshold = value


def _set_critical_low(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.critical_low_threshold = value


def _set_very_high(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.very_high_threshold = value


def _set_data_timeout(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.data_timeout = int(value)


def _set_feeding_amount(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.feeding_amount = value


def _set_insulin_amount(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.insulin_amount = value


NUMBER_DESCRIPTIONS: tuple[GlucoFarmerNumberEntityDescription, ...] = (
    GlucoFarmerNumberEntityDescription(
        key="low_threshold",
        translation_key="low_threshold",
        native_unit_of_measurement="mg/dL",
        native_min_value=40,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        default_value=DEFAULT_LOW_THRESHOLD,
        setter_fn=_set_low,
    ),
    GlucoFarmerNumberEntityDescription(
        key="high_threshold",
        translation_key="high_threshold",
        native_unit_of_measurement="mg/dL",
        native_min_value=120,
        native_max_value=300,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        default_value=DEFAULT_HIGH_THRESHOLD,
        setter_fn=_set_high,
    ),
    GlucoFarmerNumberEntityDescription(
        key="critical_low_threshold",
        translation_key="critical_low_threshold",
        native_unit_of_measurement="mg/dL",
        native_min_value=20,
        native_max_value=70,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        default_value=DEFAULT_CRITICAL_LOW_THRESHOLD,
        setter_fn=_set_critical_low,
    ),
    GlucoFarmerNumberEntityDescription(
        key="very_high_threshold",
        translation_key="very_high_threshold",
        native_unit_of_measurement="mg/dL",
        native_min_value=200,
        native_max_value=400,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        default_value=DEFAULT_VERY_HIGH_THRESHOLD,
        setter_fn=_set_very_high,
    ),
    GlucoFarmerNumberEntityDescription(
        key="data_timeout",
        translation_key="data_timeout",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=5,
        native_max_value=120,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        default_value=DEFAULT_DATA_TIMEOUT,
        setter_fn=_set_data_timeout,
    ),
    GlucoFarmerNumberEntityDescription(
        key="feeding_amount",
        translation_key="feeding_amount",
        native_unit_of_measurement="BE",
        native_min_value=0,
        native_max_value=50,
        native_step=1,
        mode=NumberMode.BOX,
        default_value=0,
        setter_fn=_set_feeding_amount,
    ),
    GlucoFarmerNumberEntityDescription(
        key="insulin_amount",
        translation_key="insulin_amount",
        native_unit_of_measurement="IU",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.BOX,
        default_value=0,
        setter_fn=_set_insulin_amount,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlucoFarmerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GlucoFarmer number entities."""
    coordinator = entry.runtime_data
    pig_name = entry.data[CONF_PIG_NAME]

    async_add_entities(
        GlucoFarmerNumberEntity(coordinator, description, pig_name, entry.entry_id)
        for description in NUMBER_DESCRIPTIONS
    )


class GlucoFarmerNumberEntity(NumberEntity):
    """GlucoFarmer number entity for configurable thresholds."""

    entity_description: GlucoFarmerNumberEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        description: GlucoFarmerNumberEntityDescription,
        pig_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the number entity."""
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_native_value = description.default_value
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=pig_name,
            manufacturer="GlucoFarmer",
            model="Pig CGM Monitor",
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new threshold value."""
        self._attr_native_value = value
        self.entity_description.setter_fn(self._coordinator, value)
        self.async_write_ha_state()
