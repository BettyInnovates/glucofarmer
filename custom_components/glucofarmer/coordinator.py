"""Data coordinator for GlucoFarmer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

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
    DEFAULT_VERY_HIGH_THRESHOLD,
    DOMAIN,
    EVENT_TYPE_FEEDING,
    EVENT_TYPE_INSULIN,
    STATUS_CRITICAL_LOW,
    STATUS_HIGH,
    STATUS_LOW,
    STATUS_NO_DATA,
    STATUS_NORMAL,
    STATUS_VERY_HIGH,
)
from .store import GlucoFarmerStore

_LOGGER = logging.getLogger(__name__)

_SCAN_INTERVAL = timedelta(seconds=60)
_READINGS_PER_HOUR = 12  # Dexcom reads every 5 minutes

type GlucoFarmerConfigEntry = ConfigEntry[GlucoFarmerCoordinator]


@dataclass
class GlucoFarmerData:
    """Data from coordinator update."""

    glucose_value: float | None
    glucose_trend: str | None
    glucose_status: str
    reading_age_minutes: float | None
    # 5-zone time percentages
    time_critical_low_pct: float
    time_low_pct: float
    time_in_range_pct: float
    time_high_pct: float
    time_very_high_pct: float
    data_completeness_pct: float       # since midnight (today)
    data_completeness_range_pct: float  # for selected chart timerange
    readings_today_actual: int
    readings_today_expected: int
    readings_range_actual: int
    readings_range_expected: int
    daily_insulin_total: float
    daily_bes_total: float
    last_reading_time: datetime | None
    today_events: list[dict[str, Any]] = field(default_factory=list)


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
        self.very_high_threshold: float = DEFAULT_VERY_HIGH_THRESHOLD
        self.data_timeout: int = DEFAULT_DATA_TIMEOUT

        # Input state (updated by number/select/text entities, read by button entities)
        self.feeding_amount: float = 0
        self.feeding_category: str = ""
        self.insulin_amount: float = 0
        self.insulin_product: str = ""
        self.event_timestamp: str = ""
        self.archive_event_id: str = ""

        # Deduplication: only log genuinely new Dexcom readings
        self._last_tracked_sensor_changed: datetime | None = None
        # Last time we had a valid glucose reading (used for age when sensor goes unavailable)
        self._last_valid_reading_time: datetime | None = None
        # Restored from store on first run after restart (once is enough)
        self._store_restored: bool = False

    def _restore_last_reading_time(self) -> None:
        """Restore last valid reading timestamp from persistent store after restart."""
        readings = self.store.get_readings_today(self.pig_name)
        if not readings:
            now = datetime.now(tz=timezone.utc)
            start = (now - timedelta(hours=24)).isoformat()
            readings = self.store.get_readings_for_range(
                self.pig_name, start, now.isoformat()
            )
        if readings:
            last_ts = max(r["timestamp"] for r in readings)
            self._last_valid_reading_time = datetime.fromisoformat(last_ts)

    async def _async_update_data(self) -> GlucoFarmerData:
        """Fetch data from Dexcom sensors and compute stats."""
        if not self._store_restored:
            self._restore_last_reading_time()
            self._store_restored = True

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
            self._last_valid_reading_time = last_changed
        elif self._last_valid_reading_time is not None:
            # Sensor unavailable -- compute age from last known good reading
            reading_age = (
                datetime.now(tz=self._last_valid_reading_time.tzinfo)
                - self._last_valid_reading_time
            ).total_seconds() / 60.0
            last_reading_time = self._last_valid_reading_time

        # Determine glucose status
        glucose_status = self._compute_status(glucose_value, reading_age)

        # Persist reading to store (only new Dexcom values, deduplicated)
        await self._track_reading(glucose_value, glucose_status, last_reading_time)

        # Get selected time range for zone stats
        hours = self._get_chart_timerange()

        # Compute 5-zone stats from persistent store
        zones = self._compute_zone_stats(hours)
        completeness_today_pct, today_actual, today_expected = self._compute_data_completeness_today()
        completeness_range_pct, range_actual, range_expected = self._compute_data_completeness_range(hours)

        # Daily totals (always from midnight)
        daily_insulin = self._compute_daily_insulin()
        daily_bes = self._compute_daily_bes()

        # Today's events for display
        today_events = self.store.get_today_events(self.pig_name)

        return GlucoFarmerData(
            glucose_value=glucose_value,
            glucose_trend=trend_value,
            glucose_status=glucose_status,
            reading_age_minutes=round(reading_age) if reading_age is not None else None,
            time_critical_low_pct=zones[0],
            time_low_pct=zones[1],
            time_in_range_pct=zones[2],
            time_high_pct=zones[3],
            time_very_high_pct=zones[4],
            data_completeness_pct=completeness_today_pct,
            data_completeness_range_pct=completeness_range_pct,
            readings_today_actual=today_actual,
            readings_today_expected=today_expected,
            readings_range_actual=range_actual,
            readings_range_expected=range_expected,
            daily_insulin_total=daily_insulin,
            daily_bes_total=daily_bes,
            last_reading_time=last_reading_time,
            today_events=today_events,
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
        if glucose < self.critical_low_threshold:
            return STATUS_CRITICAL_LOW
        if glucose < self.low_threshold:
            return STATUS_LOW
        if glucose > self.very_high_threshold:
            return STATUS_VERY_HIGH
        if glucose > self.high_threshold:
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

    def _get_chart_timerange(self) -> int:
        """Get selected chart timerange in hours from shared state."""
        domain_data = self.hass.data.get(DOMAIN, {})
        timerange_str = domain_data.get("chart_timerange", "24h")
        try:
            return int(str(timerange_str).replace("h", ""))
        except (ValueError, AttributeError):
            return 24

    def _compute_zone_stats(
        self, hours: int
    ) -> tuple[float, float, float, float, float]:
        """Compute 5-zone time percentages from persistent store.

        Uses actual glucose values with current thresholds for accurate zones.
        """
        now = datetime.now()
        start = (now - timedelta(hours=hours)).isoformat()
        end = now.isoformat()
        readings = self.store.get_readings_for_range(self.pig_name, start, end)
        if not readings:
            return 0.0, 0.0, 0.0, 0.0, 0.0

        total = len(readings)
        crit_low = sum(
            1 for r in readings if r["value"] < self.critical_low_threshold
        )
        low = sum(
            1 for r in readings
            if self.critical_low_threshold <= r["value"] < self.low_threshold
        )
        in_range = sum(
            1 for r in readings
            if self.low_threshold <= r["value"] <= self.high_threshold
        )
        high = sum(
            1 for r in readings
            if self.high_threshold < r["value"] <= self.very_high_threshold
        )
        very_high = sum(
            1 for r in readings if r["value"] > self.very_high_threshold
        )

        return (
            round(crit_low / total * 100, 1),
            round(low / total * 100, 1),
            round(in_range / total * 100, 1),
            round(high / total * 100, 1),
            round(very_high / total * 100, 1),
        )

    def _compute_data_completeness_today(self) -> tuple[float, int, int]:
        """Compute data completeness since local midnight. Returns (pct, actual, expected)."""
        now = datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        minutes_since_midnight = (now - midnight).total_seconds() / 60.0
        expected = max(1, round(minutes_since_midnight / 5))
        actual = len(self.store.get_readings_today(self.pig_name))
        pct = round(min(actual / expected * 100, 100.0), 1)
        return pct, actual, expected

    def _compute_data_completeness_range(self, hours: int) -> tuple[float, int, int]:
        """Compute data completeness for selected chart timerange. Returns (pct, actual, expected)."""
        now = datetime.now()
        start = (now - timedelta(hours=hours)).isoformat()
        end = now.isoformat()
        actual = len(self.store.get_readings_for_range(self.pig_name, start, end))
        expected = hours * _READINGS_PER_HOUR
        if expected <= 0:
            return 100.0, actual, 0
        pct = round(min(actual / expected * 100, 100.0), 1)
        return pct, actual, expected

    def _compute_daily_insulin(self) -> float:
        """Compute total insulin IU administered today."""
        events = self.store.get_today_events(self.pig_name, EVENT_TYPE_INSULIN)
        return sum(e.get("amount", 0) for e in events)

    def _compute_daily_bes(self) -> float:
        """Compute total bread units (BE) fed today."""
        events = self.store.get_today_events(self.pig_name, EVENT_TYPE_FEEDING)
        return sum(e.get("amount", 0) for e in events)
