"""Sensor platform for GlucoFarmer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SUBJECT_NAME,
    DOMAIN,
    STATUS_CRITICAL_LOW,
    STATUS_HIGH,
    STATUS_LOW,
    STATUS_NO_DATA,
    STATUS_NORMAL,
    STATUS_VERY_HIGH,
)
from .coordinator import GlucoFarmerConfigEntry, GlucoFarmerCoordinator, GlucoFarmerData


@dataclass(frozen=True, kw_only=True)
class GlucoFarmerSensorEntityDescription(SensorEntityDescription):
    """Describe a GlucoFarmer sensor entity."""

    value_fn: Callable[[GlucoFarmerData], float | str | None]
    attrs_fn: Callable[[GlucoFarmerData], dict[str, Any]] | None = None


SENSOR_DESCRIPTIONS: tuple[GlucoFarmerSensorEntityDescription, ...] = (
    GlucoFarmerSensorEntityDescription(
        key="glucose_value",
        translation_key="glucose_value",
        native_unit_of_measurement="mg/dL",
        device_class=SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.glucose_value,
    ),
    GlucoFarmerSensorEntityDescription(
        key="glucose_trend",
        translation_key="glucose_trend",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "rising_quickly",
            "rising",
            "rising_slightly",
            "steady",
            "falling_slightly",
            "falling",
            "falling_quickly",
        ],
        value_fn=lambda data: data.glucose_trend,
    ),
    GlucoFarmerSensorEntityDescription(
        key="glucose_status",
        translation_key="glucose_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            STATUS_NORMAL,
            STATUS_LOW,
            STATUS_HIGH,
            STATUS_VERY_HIGH,
            STATUS_CRITICAL_LOW,
            STATUS_NO_DATA,
        ],
        value_fn=lambda data: data.glucose_status,
    ),
    GlucoFarmerSensorEntityDescription(
        key="reading_age",
        translation_key="reading_age",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.reading_age_minutes,
    ),
    # 5-zone time percentages
    GlucoFarmerSensorEntityDescription(
        key="time_critical_low_pct",
        translation_key="time_critical_low_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_critical_low_pct,
    ),
    GlucoFarmerSensorEntityDescription(
        key="time_low_pct",
        translation_key="time_low_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_low_pct,
    ),
    GlucoFarmerSensorEntityDescription(
        key="time_in_range_pct",
        translation_key="time_in_range_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_in_range_pct,
    ),
    GlucoFarmerSensorEntityDescription(
        key="time_high_pct",
        translation_key="time_high_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_high_pct,
    ),
    GlucoFarmerSensorEntityDescription(
        key="time_very_high_pct",
        translation_key="time_very_high_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_very_high_pct,
    ),
    GlucoFarmerSensorEntityDescription(
        key="data_completeness_today",
        translation_key="data_completeness_today",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data_completeness_pct,
        attrs_fn=lambda data: {
            "actual": data.readings_today_actual,
            "expected": data.readings_today_expected,
            "missed": max(0, data.readings_today_expected - data.readings_today_actual),
        },
    ),
    GlucoFarmerSensorEntityDescription(
        key="data_completeness_range",
        translation_key="data_completeness_range",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data_completeness_range_pct,
        attrs_fn=lambda data: {
            "actual": data.readings_range_actual,
            "expected": data.readings_range_expected,
            "missed": max(0, data.readings_range_expected - data.readings_range_actual),
        },
    ),
    GlucoFarmerSensorEntityDescription(
        key="daily_insulin_total",
        translation_key="daily_insulin_total",
        native_unit_of_measurement="IU",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.daily_insulin_total,
    ),
    GlucoFarmerSensorEntityDescription(
        key="daily_bes_total",
        translation_key="daily_bes_total",
        native_unit_of_measurement="BE",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.daily_bes_total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlucoFarmerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GlucoFarmer sensor entities."""
    coordinator = entry.runtime_data
    subject_name = entry.data[CONF_SUBJECT_NAME]

    entities: list[SensorEntity] = [
        GlucoFarmerSensorEntity(coordinator, description, subject_name, entry.entry_id)
        for description in SENSOR_DESCRIPTIONS
    ]
    # Add special events sensor
    entities.append(
        GlucoFarmerEventsSensor(coordinator, subject_name, entry.entry_id)
    )
    async_add_entities(entities)


class GlucoFarmerSensorEntity(
    CoordinatorEntity[GlucoFarmerCoordinator], SensorEntity
):
    """GlucoFarmer sensor entity."""

    entity_description: GlucoFarmerSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        description: GlucoFarmerSensorEntityDescription,
        subject_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=subject_name,
            manufacturer="GlucoFarmer",
            model="Subject CGM Monitor",
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return optional extra attributes."""
        if self.coordinator.data is None or self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class GlucoFarmerEventsSensor(
    CoordinatorEntity[GlucoFarmerCoordinator], SensorEntity
):
    """Sensor that exposes today's events as attributes for dashboard display."""

    _attr_has_entity_name = True
    _attr_translation_key = "today_events"

    def __init__(
        self,
        coordinator: GlucoFarmerCoordinator,
        subject_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the events sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_today_events"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=subject_name,
            manufacturer="GlucoFarmer",
            model="Subject CGM Monitor",
        )

    @property
    def native_value(self) -> int:
        """Return count of today's events."""
        if self.coordinator.data is None:
            return 0
        return len(self.coordinator.data.today_events)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return today's events as attributes."""
        if self.coordinator.data is None:
            return {"events": []}
        return {"events": self.coordinator.data.today_events}
