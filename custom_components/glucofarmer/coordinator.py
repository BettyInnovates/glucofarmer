"""Data coordinator for GlucoFarmer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import state_changes_during_period
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_GLUCOSE_SENSOR,
    CONF_SUBJECT_NAME,
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
_READING_INTERVAL_MINUTES = 5  # Dexcom sends one reading every 5 minutes

# String states from Dexcom when glucose is outside sensor range
_LOW_STATES = {"low", "niedrig"}
_HIGH_STATES = {"high", "hoch"}

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
            name=f"{DOMAIN}_{entry.data[CONF_SUBJECT_NAME]}",
            update_interval=_SCAN_INTERVAL,
        )
        self.subject_name: str = entry.data[CONF_SUBJECT_NAME]
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

        # Last time we had a valid glucose reading (used for age when sensor goes unavailable)
        self._last_valid_reading_time: datetime | None = None

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

        # Get selected time range for zone stats
        hours = self._get_chart_timerange()

        # Compute 5-zone stats and completeness from HA Recorder
        now_aware = datetime.now().astimezone()
        midnight_aware = now_aware.replace(hour=0, minute=0, second=0, microsecond=0)
        range_start_aware = now_aware - timedelta(hours=hours)

        zones = await self._compute_zone_stats(range_start_aware, now_aware)
        completeness_today_pct, today_actual, today_expected = await self._compute_data_completeness(midnight_aware, now_aware)
        completeness_range_pct, range_actual, range_expected = await self._compute_data_completeness(range_start_aware, now_aware)

        # Daily totals (always from midnight)
        daily_insulin = self._compute_daily_insulin()
        daily_bes = self._compute_daily_bes()

        # Today's events for display
        today_events = self.store.get_today_events(self.subject_name)

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

    async def _get_readings_from_recorder(
        self,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list[tuple[datetime, float]]:
        """Fetch glucose readings from HA Recorder for the given time range.

        Maps Low/High string states to threshold-based values.
        Filters unknown/unavailable states.
        Returns list of (utc_aware_timestamp, float_value) tuples.
        """
        instance = get_instance(self.hass)
        if instance is None:
            _LOGGER.warning("GlucoFarmer: Recorder not available")
            return []

        states_dict = await instance.async_add_executor_job(
            state_changes_during_period,
            self.hass, start_dt, end_dt, self.glucose_sensor_id,
        )
        raw_states = states_dict.get(self.glucose_sensor_id, [])

        readings: list[tuple[datetime, float]] = []
        for state in raw_states:
            try:
                value = float(state.state)
            except (ValueError, TypeError):
                s = state.state.lower() if state.state else ""
                if s in _LOW_STATES:
                    value = self.critical_low_threshold - 1
                elif s in _HIGH_STATES:
                    value = self.very_high_threshold + 1
                else:
                    continue  # unknown/unavailable -- skip
            readings.append((state.last_changed, value))

        return readings

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

    def _get_chart_timerange(self) -> int:
        """Get selected chart timerange in hours from shared state."""
        domain_data = self.hass.data.get(DOMAIN, {})
        timerange_str = domain_data.get("chart_timerange", "24h")
        try:
            return int(str(timerange_str).replace("h", ""))
        except (ValueError, AttributeError):
            return 24

    async def _compute_zone_stats(
        self,
        start_dt: datetime,
        end_dt: datetime,
    ) -> tuple[float, float, float, float, float]:
        """Compute 5-zone time percentages from HA Recorder."""
        readings = await self._get_readings_from_recorder(start_dt, end_dt)
        if not readings:
            return 0.0, 0.0, 0.0, 0.0, 0.0

        total = len(readings)
        crit_low = sum(1 for _, v in readings if v < self.critical_low_threshold)
        low = sum(
            1 for _, v in readings
            if self.critical_low_threshold <= v < self.low_threshold
        )
        in_range = sum(
            1 for _, v in readings
            if self.low_threshold <= v <= self.high_threshold
        )
        high = sum(
            1 for _, v in readings
            if self.high_threshold < v <= self.very_high_threshold
        )
        very_high = sum(1 for _, v in readings if v > self.very_high_threshold)

        return (
            round(crit_low / total * 100, 1),
            round(low / total * 100, 1),
            round(in_range / total * 100, 1),
            round(high / total * 100, 1),
            round(very_high / total * 100, 1),
        )

    def _gap_based_completeness(
        self,
        timestamps: list[datetime],
        end_dt: datetime,
    ) -> tuple[float, int, int]:
        """Calculate completeness from gaps between consecutive readings.

        Appends end_dt as a boundary so the gap from the last reading until
        now is counted -- fixes under-reporting of missed readings when the
        sensor has been offline for a while.

        Returns (pct, actual, total_expected).
        """
        actual = len(timestamps)
        if actual == 0:
            return 0.0, 0, 0

        sorted_ts = sorted(timestamps)
        boundary_ts = sorted_ts + [end_dt]

        missed = 0
        for i in range(1, len(boundary_ts)):
            gap_minutes = (boundary_ts[i] - boundary_ts[i - 1]).total_seconds() / 60
            missed_in_gap = max(0, round(gap_minutes / _READING_INTERVAL_MINUTES) - 1)
            missed += missed_in_gap

        total_expected = actual + missed
        pct = round(actual / total_expected * 100, 1)
        return pct, actual, total_expected

    async def _compute_data_completeness(
        self,
        start_dt: datetime,
        end_dt: datetime,
    ) -> tuple[float, int, int]:
        """Gap-based completeness for a time range. Returns (pct, actual, total_expected)."""
        readings = await self._get_readings_from_recorder(start_dt, end_dt)
        timestamps = [ts for ts, _ in readings]
        return self._gap_based_completeness(timestamps, end_dt)

    def _compute_daily_insulin(self) -> float:
        """Compute total insulin IU administered today."""
        events = self.store.get_today_events(self.subject_name, EVENT_TYPE_INSULIN)
        return sum(e.get("amount", 0) for e in events)

    def _compute_daily_bes(self) -> float:
        """Compute total bread units (BE) fed today."""
        events = self.store.get_today_events(self.subject_name, EVENT_TYPE_FEEDING)
        return sum(e.get("amount", 0) for e in events)
