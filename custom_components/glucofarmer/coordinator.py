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
    DEFAULT_VERY_LOW_THRESHOLD,
    DOMAIN,
    EVENT_TYPE_FEEDING,
    EVENT_TYPE_INSULIN,
    STATUS_CRITICAL_LOW,
    STATUS_HIGH,
    STATUS_LOW,
    STATUS_NO_DATA,
    STATUS_NORMAL,
    STATUS_VERY_HIGH,
    STATUS_VERY_LOW,
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
    # 6-zone time percentages
    time_critical_low_pct: float
    time_very_low_pct: float
    time_low_pct: float
    time_in_range_pct: float
    time_high_pct: float
    time_very_high_pct: float
    # Signal coverage (time-based, since midnight and for selected range)
    covered_minutes_today: float
    total_minutes_today: float
    covered_minutes_range: float
    total_minutes_range: float
    daily_insulin_total: float
    daily_bes_total: float
    last_reading_time: datetime | None
    link_status: str               # "ok" | "lost"
    link_outage_minutes: int | None  # None when ok, else minutes since signal loss
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
        self.critical_low_threshold: float = DEFAULT_CRITICAL_LOW_THRESHOLD
        self.very_low_threshold: float = DEFAULT_VERY_LOW_THRESHOLD
        self.low_threshold: float = DEFAULT_LOW_THRESHOLD
        self.high_threshold: float = DEFAULT_HIGH_THRESHOLD
        self.very_high_threshold: float = DEFAULT_VERY_HIGH_THRESHOLD
        self.data_timeout: int = DEFAULT_DATA_TIMEOUT
        self._write_thresholds_to_shared()

        # Input state (updated by number/select/text entities, read by button entities)
        self.feeding_amount: float = 0
        self.feeding_category: str = ""
        self.insulin_amount: float = 0
        self.insulin_product: str = ""
        self.event_timestamp: str = ""
        self.archive_event_id: str = ""

        # Last time we had a valid glucose reading (used for age when sensor goes unavailable)
        self._last_valid_reading_time: datetime | None = None

        # Timestamp when the current signal-loss event started (None = signal ok)
        self._signal_lost_since: datetime | None = None

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

        # Compute link status: "ok" when signal present, "lost" when unknown/unavailable.
        # unknown = no data from Dexcom (BT/internet/range -- indistinguishable).
        # unavailable = HA integration artifact (restart etc.) -- treated the same.
        now_tz = datetime.now().astimezone()
        if not sensor_unavailable:
            self._signal_lost_since = None
            link_status = "ok"
            link_outage_minutes: int | None = None
        else:
            if self._signal_lost_since is None:
                self._signal_lost_since = now_tz
            link_outage_minutes = round(
                (now_tz - self._signal_lost_since).total_seconds() / 60
            )
            link_status = "lost"

        # Determine glucose status
        glucose_status = self._compute_status(glucose_value, sensor_unavailable)

        # Get selected time range for zone stats
        hours = self._get_chart_timerange()

        # Compute 6-zone stats and signal coverage from HA Recorder
        now_aware = datetime.now().astimezone()
        midnight_aware = now_aware.replace(hour=0, minute=0, second=0, microsecond=0)
        range_start_aware = now_aware - timedelta(hours=hours)

        zones = await self._compute_zone_stats(range_start_aware, now_aware)
        covered_today, total_today = await self._compute_signal_coverage(midnight_aware, now_aware)
        covered_range, total_range = await self._compute_signal_coverage(range_start_aware, now_aware)

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
            time_very_low_pct=zones[1],
            time_low_pct=zones[2],
            time_in_range_pct=zones[3],
            time_high_pct=zones[4],
            time_very_high_pct=zones[5],
            covered_minutes_today=covered_today,
            total_minutes_today=total_today,
            covered_minutes_range=covered_range,
            total_minutes_range=total_range,
            daily_insulin_total=daily_insulin,
            daily_bes_total=daily_bes,
            last_reading_time=last_reading_time,
            link_status=link_status,
            link_outage_minutes=link_outage_minutes,
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

    def _write_thresholds_to_shared(self) -> None:
        """Write all 5 thresholds to hass.data[DOMAIN]['thresholds'] for global access."""
        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}
        self.hass.data[DOMAIN]["thresholds"] = {
            "critical_low": self.critical_low_threshold,
            "very_low": self.very_low_threshold,
            "low": self.low_threshold,
            "high": self.high_threshold,
            "very_high": self.very_high_threshold,
        }

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
        if glucose < self.very_low_threshold:
            return STATUS_VERY_LOW
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
    ) -> tuple[float, float, float, float, float, float]:
        """Compute 6-zone time percentages from HA Recorder using time-weighting.

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
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        zone_weights = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

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
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        return (
            round(zone_weights[0] / total_w * 100, 1),  # critical_low
            round(zone_weights[1] / total_w * 100, 1),  # very_low
            round(zone_weights[2] / total_w * 100, 1),  # low
            round(zone_weights[3] / total_w * 100, 1),  # in_range
            round(zone_weights[4] / total_w * 100, 1),  # high
            round(zone_weights[5] / total_w * 100, 1),  # very_high
        )

    def _value_to_zone(self, value: float) -> int:
        """Map a glucose value to zone index (0=critical_low .. 5=very_high)."""
        if value < self.critical_low_threshold:
            return 0
        if value < self.very_low_threshold:
            return 1
        if value < self.low_threshold:
            return 2
        if value <= self.high_threshold:
            return 3
        if value <= self.very_high_threshold:
            return 4
        return 5

    async def _compute_signal_coverage(
        self,
        start_dt: datetime,
        end_dt: datetime,
    ) -> tuple[float, float]:
        """Signal-time-based coverage. Returns (covered_minutes, total_minutes).

        Uses the same time-weighting logic as _compute_zone_stats:
        - Numeric reading: contributes covered time until next event (capped at
          _GAP_CAP_MINUTES when the next event is a gap marker).
        - Gap marker: contributes 0 covered time.
        """
        total_minutes = (end_dt - start_dt).total_seconds() / 60.0
        if total_minutes <= 0:
            return 0.0, 0.0

        entries = await self._get_readings_from_recorder(start_dt, end_dt)
        if not entries:
            return 0.0, total_minutes

        covered_minutes = 0.0
        for i, (ts, value) in enumerate(entries):
            if value is None:
                continue  # gap marker -- no covered time

            if i + 1 < len(entries):
                boundary_ts, next_val = entries[i + 1]
                has_gap_next = next_val is None
            else:
                boundary_ts = end_dt
                has_gap_next = False

            duration_min = (boundary_ts - ts).total_seconds() / 60.0
            weight = min(duration_min, _GAP_CAP_MINUTES) if has_gap_next else duration_min
            covered_minutes += max(0.0, weight)

        return covered_minutes, total_minutes

    def _compute_daily_insulin(self) -> float:
        """Compute total insulin IU administered today."""
        events = self.store.get_today_events(self.subject_name, EVENT_TYPE_INSULIN)
        return sum(e.get("amount", 0) for e in events)

    def _compute_daily_bes(self) -> float:
        """Compute total bread units (BE) fed today."""
        events = self.store.get_today_events(self.subject_name, EVENT_TYPE_FEEDING)
        return sum(e.get("amount", 0) for e in events)
