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

# Maximum weight (minutes) assigned to the last valid reading before a gap marker.
# One Dexcom transmission cycle -- after one cycle without a new reading we cannot
# guarantee the previous value is still valid.
_GAP_CAP_MINUTES = 5.0

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
            # Use last_updated (not last_changed) so SYNC reflects when the
            # sensor last polled, not when the glucose value last changed.
            # For stable glucose last_changed grows stale while last_updated
            # resets every ~6 min (assuming Dexcom calls async_set() each poll).
            last_updated = glucose_state.last_updated
            reading_age = (
                datetime.now(tz=last_updated.tzinfo) - last_updated
            ).total_seconds() / 60.0
            last_reading_time = last_updated
            self._last_valid_reading_time = last_updated
        elif self._last_valid_reading_time is not None:
            # Sensor unavailable -- compute age from last known good reading
            reading_age = (
                datetime.now(tz=self._last_valid_reading_time.tzinfo)
                - self._last_valid_reading_time
            ).total_seconds() / 60.0
            last_reading_time = self._last_valid_reading_time

        # Determine if the sensor currently reports a gap state.
        # STATUS_NO_DATA is only raised when the sensor actively signals unavailability.
        # A stable numeric reading (unchanged value, growing last_changed age) is NOT a gap.
        sensor_unavailable = (
            glucose_state is None
            or glucose_state.state in ("unknown", "unavailable")
        )

        # Determine glucose status
        glucose_status = self._compute_status(glucose_value, sensor_unavailable)

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
    ) -> list[tuple[datetime, float | None]]:
        """Fetch glucose readings from HA Recorder for the given time range.

        Maps Low/High string states to threshold-based values.
        Retains unknown/unavailable states as gap markers (value=None).

        Returns list of (utc_aware_timestamp, value_or_none) sorted by timestamp.
        None values indicate genuine data gaps (signal loss, sensor unavailable)
        and are essential for accurate time-weighting and alarm logic.
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

        readings: list[tuple[datetime, float | None]] = []
        for state in raw_states:
            try:
                value: float | None = float(state.state)
            except (ValueError, TypeError):
                s = state.state.lower() if state.state else ""
                if s in _LOW_STATES:
                    value = self.critical_low_threshold - 1
                elif s in _HIGH_STATES:
                    value = self.very_high_threshold + 1
                else:
                    value = None  # unknown/unavailable -- retain as gap marker
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
        self, glucose: float | None, sensor_unavailable: bool
    ) -> str:
        """Compute glucose status based on current sensor state and thresholds.

        STATUS_NO_DATA is returned only when the sensor actively reports
        unknown or unavailable -- a genuine signal loss or connectivity gap.
        A valid numeric reading that has not changed (stable glucose) does NOT
        produce STATUS_NO_DATA, regardless of how long ago last_changed was set.
        """
        if sensor_unavailable or glucose is None:
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
        """Compute 5-zone time percentages from HA Recorder using time-weighting.

        Each numeric reading contributes weight proportional to the time it
        represents. Weight depends on what follows it in the sorted entry list:

        - Next entry is another numeric reading (stable glucose, no gap):
          weight = full duration between readings, uncapped.
          Rationale: the value was genuinely stable for that entire period.

        - Next entry is a gap marker (unknown/unavailable state):
          weight = min(time_to_gap, _GAP_CAP_MINUTES).
          Rationale: after one Dexcom cycle the previous value cannot be trusted.

        - No next entry within range: weight = time to end_dt, uncapped.

        Gap markers themselves contribute no weight to any zone.
        """
        entries = await self._get_readings_from_recorder(start_dt, end_dt)
        if not entries:
            return 0.0, 0.0, 0.0, 0.0, 0.0

        zone_weights = [0.0, 0.0, 0.0, 0.0, 0.0]

        for i, (ts, value) in enumerate(entries):
            if value is None:
                continue  # gap marker -- contributes no zone time

            if i + 1 < len(entries):
                boundary_ts, next_val = entries[i + 1]
                has_gap_next = next_val is None
            else:
                boundary_ts = end_dt
                has_gap_next = False

            duration_min = (boundary_ts - ts).total_seconds() / 60.0
            weight = min(duration_min, _GAP_CAP_MINUTES) if has_gap_next else duration_min
            weight = max(0.0, weight)

            zone_weights[self._value_to_zone(value)] += weight

        total_w = sum(zone_weights)
        if total_w == 0.0:
            return 0.0, 0.0, 0.0, 0.0, 0.0

        return (
            round(zone_weights[0] / total_w * 100, 1),
            round(zone_weights[1] / total_w * 100, 1),
            round(zone_weights[2] / total_w * 100, 1),
            round(zone_weights[3] / total_w * 100, 1),
            round(zone_weights[4] / total_w * 100, 1),
        )

    def _value_to_zone(self, value: float) -> int:
        """Map a glucose value to zone index (0=crit_low, 1=low, 2=in_range, 3=high, 4=very_high)."""
        if value < self.critical_low_threshold:
            return 0
        if value < self.low_threshold:
            return 1
        if value <= self.high_threshold:
            return 2
        if value <= self.very_high_threshold:
            return 3
        return 4

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
        entries = await self._get_readings_from_recorder(start_dt, end_dt)
        # Only count numeric readings -- gap markers (None) are not actual readings
        timestamps = [ts for ts, v in entries if v is not None]
        return self._gap_based_completeness(timestamps, end_dt)

    def _compute_daily_insulin(self) -> float:
        """Compute total insulin IU administered today."""
        events = self.store.get_today_events(self.subject_name, EVENT_TYPE_INSULIN)
        return sum(e.get("amount", 0) for e in events)

    def _compute_daily_bes(self) -> float:
        """Compute total bread units (BE) fed today."""
        events = self.store.get_today_events(self.subject_name, EVENT_TYPE_FEEDING)
        return sum(e.get("amount", 0) for e in events)
