"""Number platform for GlucoFarmer thresholds and input amounts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_SUBJECT_NAME,
    DEFAULT_CRITICAL_LOW_THRESHOLD,
    DEFAULT_DATA_TIMEOUT,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_VERY_HIGH_THRESHOLD,
    DEFAULT_VERY_LOW_THRESHOLD,
    DOMAIN,
)
from .coordinator import GlucoFarmerConfigEntry, GlucoFarmerCoordinator
from .dashboard import async_update_dashboard


@dataclass(frozen=True, kw_only=True)
class GlucoFarmerNumberEntityDescription(NumberEntityDescription):
    """Describe a GlucoFarmer number entity."""

    default_value: float
    setter_fn: Callable[[GlucoFarmerCoordinator, float], None]


def _set_critical_low(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.critical_low_threshold = value
    coordinator._write_one_threshold_to_shared("critical_low", value)


def _set_very_low(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.very_low_threshold = value
    coordinator._write_one_threshold_to_shared("very_low", value)


def _set_low(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.low_threshold = value
    coordinator._write_one_threshold_to_shared("low", value)


def _set_high(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.high_threshold = value
    coordinator._write_one_threshold_to_shared("high", value)


def _set_very_high(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.very_high_threshold = value
    coordinator._write_one_threshold_to_shared("very_high", value)


def _set_data_timeout(coordinator: GlucoFarmerCoordinator, value: float) -> None:
    coordinator.data_timeout = int(value)


NUMBER_DESCRIPTIONS: tuple[GlucoFarmerNumberEntityDescription, ...] = (
    GlucoFarmerNumberEntityDescription(
        key="critical_low_threshold",
        translation_key="critical_low_threshold",
        native_unit_of_measurement="mg/dL",
        native_min_value=20,
        native_max_value=500,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        default_value=DEFAULT_CRITICAL_LOW_THRESHOLD,
        setter_fn=_set_critical_low,
    ),
    GlucoFarmerNumberEntityDescription(
        key="very_low_threshold",
        translation_key="very_low_threshold",
        native_unit_of_measurement="mg/dL",
        native_min_value=20,
        native_max_value=500,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        default_value=DEFAULT_VERY_LOW_THRESHOLD,
        setter_fn=_set_very_low,
    ),
    GlucoFarmerNumberEntityDescription(
        key="low_threshold",
        translation_key="low_threshold",
        native_unit_of_measurement="mg/dL",
        native_min_value=20,
        native_max_value=500,
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
        native_min_value=20,
        native_max_value=500,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        default_value=DEFAULT_HIGH_THRESHOLD,
        setter_fn=_set_high,
    ),
    GlucoFarmerNumberEntityDescription(
        key="very_high_threshold",
        translation_key="very_high_threshold",
        native_unit_of_measurement="mg/dL",
        native_min_value=20,
        native_max_value=500,
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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlucoFarmerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GlucoFarmer number entities."""
    coordinator = entry.runtime_data
    subject_name = entry.data[CONF_SUBJECT_NAME]

    # Threshold + config entities
    threshold_entities = [
        GlucoFarmerNumberEntity(coordinator, description, subject_name, entry.entry_id)
        for description in NUMBER_DESCRIPTIONS
    ]

    # Input entities for page 2 forms
    be_amount = GlucoFarmerBeAmountNumber(coordinator, subject_name, entry.entry_id)
    minutes_ago = GlucoFarmerMinutesAgoNumber(coordinator, subject_name, entry.entry_id)
    insulin_units = GlucoFarmerInsulinUnitsNumber(coordinator, subject_name, entry.entry_id)

    # Register form entities with coordinator for cross-entity access
    coordinator.be_amount_entity = be_amount
    coordinator.minutes_ago_entity = minutes_ago
    coordinator.insulin_units_entity = insulin_units

    async_add_entities(threshold_entities + [be_amount, minutes_ago, insulin_units])


class GlucoFarmerNumberEntity(NumberEntity, RestoreEntity):
    """GlucoFarmer number entity for configurable thresholds."""

    entity_description: GlucoFarmerNumberEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        description: GlucoFarmerNumberEntityDescription,
        subject_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the number entity."""
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_native_value = description.default_value
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=subject_name,
            manufacturer="GlucoFarmer",
            model="Subject CGM Monitor",
        )

    async def async_added_to_hass(self) -> None:
        """Set initial value from coordinator (loaded from persistent storage)."""
        await super().async_added_to_hass()
        if self.entity_description.entity_category == EntityCategory.CONFIG:
            # Coordinator already has correct values from Store (loaded in async_setup_entry).
            # Read directly from coordinator attribute -- no RestoreEntity needed.
            value = getattr(self._coordinator, self.entity_description.key, None)
            if value is not None:
                self._attr_native_value = float(value)
                self.async_write_ha_state()
            self._coordinator.schedule_dashboard_refresh()
            return
        # Non-CONFIG entities: restore from state machine
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in ("unknown", "unavailable"):
            try:
                self._attr_native_value = float(last_state.state)
                self.entity_description.setter_fn(self._coordinator, self._attr_native_value)
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        """Set new threshold value."""
        self._attr_native_value = value
        self.entity_description.setter_fn(self._coordinator, value)
        self.async_write_ha_state()
        if self.entity_description.entity_category == EntityCategory.CONFIG:
            await self._coordinator.async_save_thresholds()
            await self._coordinator.async_request_refresh()
            await async_update_dashboard(self._coordinator.hass)


def _make_device_info(entry_id: str, subject_name: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=subject_name,
        manufacturer="GlucoFarmer",
        model="Subject CGM Monitor",
    )


class GlucoFarmerBeAmountNumber(NumberEntity):
    """BE amount for feeding form. Can be auto-filled by meal selection."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "be_amount"
    _attr_native_unit_of_measurement = "BE"
    _attr_native_min_value = 0
    _attr_native_max_value = 50
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX
    _attr_native_value = 0.0

    def __init__(
        self, coordinator: GlucoFarmerCoordinator, subject_name: str, entry_id: str
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_be_amount"
        self._attr_device_info = _make_device_info(entry_id, subject_name)

    def set_suggested_value(self, value: float) -> None:
        """Push a new value from meal auto-fill without a full coordinator refresh."""
        self._attr_native_value = value
        self._coordinator.be_amount = value
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self._coordinator.be_amount = value
        self.async_write_ha_state()


class GlucoFarmerMinutesAgoNumber(NumberEntity):
    """Minutes-ago offset for event timestamp. 0 = now."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "minutes_ago"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_value = 0

    def __init__(
        self, coordinator: GlucoFarmerCoordinator, subject_name: str, entry_id: str
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_minutes_ago"
        self._attr_device_info = _make_device_info(entry_id, subject_name)

    def reset(self) -> None:
        """Reset to 0 (called after logging an event)."""
        self._attr_native_value = 0
        self._coordinator.minutes_ago = 0
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = int(value)
        self._coordinator.minutes_ago = int(value)
        self.async_write_ha_state()


class GlucoFarmerInsulinUnitsNumber(NumberEntity):
    """IU amount for insulin form."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "insulin_units"
    _attr_native_unit_of_measurement = "IU"
    _attr_native_min_value = 0
    _attr_native_max_value = 50
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_native_value = 0.0

    def __init__(
        self, coordinator: GlucoFarmerCoordinator, subject_name: str, entry_id: str
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_insulin_units"
        self._attr_device_info = _make_device_info(entry_id, subject_name)

    def reset(self) -> None:
        """Reset to 0 (called after logging an event)."""
        self._attr_native_value = 0.0
        self._coordinator.insulin_units = 0.0
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self._coordinator.insulin_units = value
        self.async_write_ha_state()
