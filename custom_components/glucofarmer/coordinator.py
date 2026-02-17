"""Data coordinator for GlucoFarmer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_GLUCOSE_SENSOR,
    CONF_PIG_NAME,
    CONF_TREND_SENSOR,
    DEFAULT_CRITICAL_LOW_THRESHOLD,
    DEFAULT_DATA_TIMEOUT,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DOMAIN,
    EVENT_TYPE_FEEDING,
    EVENT_TYPE_INSULIN,
    STATUS_CRITICAL_LOW,
    STATUS_HIGH,
    STATUS_LOW,
    STATUS_NO_DATA,
    STATUS_NORMAL,
)
from .store import GlucoFarmerStore

_LOGGER = logging.getLogger(__name__)

_SCAN_INTERVAL = timedelta(seconds=60)

type GlucoFarmerConfigEntry = ConfigEntry[GlucoFarmerCoordinator]


@dataclass
class GlucoFarmerData:
    """Data from coordinator update."""

    glucose_value: float | None
    glucose_trend: str | None
    glucose_status: str
    reading_age_minutes: float | None
    time_in_range_pct: float
    time_below_range_pct: float
    time_above_range_pct: float
    data_completeness_pct: float
    daily_insulin_total: float
    daily_bes_total: float
    last_reading_time: datetime | None


class GlucoFarmerCoordinator(DataUpdateCoordinator[GlucoFarmerData]):
    """GlucoFarmer data coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GlucoFarmerConfigEntry,
        store: GlucoFarmerStore,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.data[CONF_PIG_NAME]}",
            update_interval=_SCAN_INTERVAL,
        )
        self.pig_name: str = entry.data[CONF_PIG_NAME]
        self.glucose_sensor_id: str = entry.data[CONF_GLUCOSE_SENSOR]
        self.trend_sensor_id: str = entry.data[CONF_TREND_SENSOR]
        self.store = store

        # Thresholds (updated by number entities)
        self.low_threshold: float = DEFAULT_LOW_THRESHOLD
        self.high_threshold: float = DEFAULT_HIGH_THRESHOLD
        self.critical_low_threshold: float = DEFAULT_CRITICAL_LOW_THRESHOLD
        self.data_timeout: int = DEFAULT_DATA_TIMEOUT

        # Deduplication: only log genuinely new Dexcom readings
        self._last_tracked_sensor_changed: datetime | None = None

    async def _async_update_data(self) -> GlucoFarmerData:
        """Fetch data from Dexcom sensors and compute stats."""
        glucose_value = self._get_sensor_value(self.glucose_sensor_id)
        trend_value = self._get_sensor_state(self.trend_sensor_id)

        # Determine reading age
        reading_age: float | None = None
        last_reading_time: datetime | None = None
        glucose_state = self.hass.states.get(self.glucose_sensor_id)
        if glucose_state is not None and glucose_state.state not in (
            "unknown",
            "unavailable",
        ):
            last_changed = glucose_state.last_changed
            reading_age = (
                datetime.now(tz=last_changed.tzinfo) - last_changed
            ).total_seconds() / 60.0
            last_reading_time = last_changed

        # Determine glucose status
        glucose_status = self._compute_status(glucose_value, reading_age)

        # Persist reading to store (only new Dexcom values, deduplicated)
        await self._track_reading(glucose_value, glucose_status, last_reading_time)

        # Compute daily statistics from persistent store
        tir, tbr, tar = self._compute_tir()
        completeness = self._compute_data_completeness()
        daily_insulin = self._compute_daily_insulin()
        daily_bes = self._compute_daily_bes()

        return GlucoFarmerData(
            glucose_value=glucose_value,
            glucose_trend=trend_value,
            glucose_status=glucose_status,
            reading_age_minutes=round(reading_age, 1) if reading_age is not None else None,
            time_in_range_pct=tir,
            time_below_range_pct=tbr,
            time_above_range_pct=tar,
            data_completeness_pct=completeness,
            daily_insulin_total=daily_insulin,
            daily_bes_total=daily_bes,
            last_reading_time=last_reading_time,
        )

    def _get_sensor_value(self, entity_id: str) -> float | None:
        """Get numeric value from a sensor entity."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _get_sensor_state(self, entity_id: str) -> str | None:
        """Get string state from a sensor entity."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return state.state

    def _compute_status(
        self, glucose: float | None, reading_age: float | None
    ) -> str:
        """Compute glucose status based on value and thresholds."""
        if reading_age is not None and reading_age > self.data_timeout:
            return STATUS_NO_DATA
        if glucose is None:
            return STATUS_NO_DATA
        if glucose <= self.critical_low_threshold:
            return STATUS_CRITICAL_LOW
        if glucose <= self.low_threshold:
            return STATUS_LOW
        if glucose >= self.high_threshold:
            return STATUS_HIGH
        return STATUS_NORMAL

    async def _track_reading(
        self,
        glucose: float | None,
        status: str,
        sensor_changed: datetime | None,
    ) -> None:
        """Persist a glucose reading to the store.

        Only saves when the Dexcom sensor's last_changed timestamp differs
        from the previously tracked one (= a genuinely new 5-min reading).
        All readings are stored persistently and survive HA restarts.
        """
        if glucose is None or status == STATUS_NO_DATA:
            return

        # Only record if this is a new Dexcom reading (different last_changed)
        if (
            sensor_changed is not None
            and sensor_changed == self._last_tracked_sensor_changed
        ):
            return

        self._last_tracked_sensor_changed = sensor_changed
        timestamp = (
            sensor_changed.isoformat()
            if sensor_changed
            else datetime.now().isoformat()
        )
        await self.store.async_log_reading(
            pig_name=self.pig_name,
            value=glucose,
            status=status,
            timestamp=timestamp,
        )

    def _compute_tir(self) -> tuple[float, float, float]:
        """Compute time in range, below range, above range from persistent store."""
        readings = self.store.get_readings_today(self.pig_name)
        if not readings:
            return 0.0, 0.0, 0.0

        total = len(readings)
        in_range = sum(
            1 for r in readings if r["status"] == STATUS_NORMAL
        )
        below = sum(
            1
            for r in readings
            if r["status"] in (STATUS_LOW, STATUS_CRITICAL_LOW)
        )
        above = sum(
            1 for r in readings if r["status"] == STATUS_HIGH
        )

        return (
            round(in_range / total * 100, 1),
            round(below / total * 100, 1),
            round(above / total * 100, 1),
        )

    def _compute_data_completeness(self) -> float:
        """Compute data completeness from persistent store.

        Percentage of expected 5-min Dexcom readings actually received today.
        """
        now = datetime.now()
        minutes_today = now.hour * 60 + now.minute
        if minutes_today < 5:
            return 100.0
        # Dexcom delivers a reading every 5 minutes
        expected_readings = minutes_today / 5
        actual_readings = len(self.store.get_readings_today(self.pig_name))
        return round(min(actual_readings / expected_readings * 100, 100.0), 1)

    def _compute_daily_insulin(self) -> float:
        """Compute total insulin IU administered today."""
        events = self.store.get_today_events(self.pig_name, EVENT_TYPE_INSULIN)
        return sum(e.get("amount", 0) for e in events)

    def _compute_daily_bes(self) -> float:
        """Compute total bread units (BE) fed today."""
        events = self.store.get_today_events(self.pig_name, EVENT_TYPE_FEEDING)
        return sum(e.get("amount", 0) for e in events)
