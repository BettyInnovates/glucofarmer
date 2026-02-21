"""GlucoFarmer integration for Home Assistant."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_point_in_time, async_track_state_change_event
import homeassistant.util.dt as dt_util

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import state_changes_during_period

from .const import (
    ATTR_AMOUNT,
    ATTR_CATEGORY,
    ATTR_DESCRIPTION,
    ATTR_EVENT_ID,
    ATTR_NOTE,
    ATTR_SUBJECT_NAME,
    ATTR_PRODUCT,
    ATTR_TIMESTAMP,
    CONF_GLUCOSE_SENSOR,
    CONF_SUBJECT_NAME,
    DEFAULT_CRITICAL_LOW_THRESHOLD,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_VERY_HIGH_THRESHOLD,
    DOMAIN,
    EVENT_TYPE_FEEDING,
    EVENT_TYPE_INSULIN,
    PLATFORMS,
    SERVICE_DELETE_EVENT,
    SERVICE_LOG_FEEDING,
    SERVICE_LOG_INSULIN,
    STATUS_CRITICAL_LOW,
    STATUS_HIGH,
    STATUS_LOW,
    STATUS_NO_DATA,
    STATUS_NORMAL,
    STATUS_VERY_HIGH,
)
from .coordinator import GlucoFarmerConfigEntry, GlucoFarmerCoordinator
from .dashboard import async_update_dashboard
from .store import GlucoFarmerStore

_LOGGER = logging.getLogger(__name__)

SERVICE_LOG_INSULIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SUBJECT_NAME): cv.string,
        vol.Required(ATTR_PRODUCT): cv.string,
        vol.Required(ATTR_AMOUNT): vol.Coerce(float),
        vol.Optional(ATTR_TIMESTAMP): cv.string,
        vol.Optional(ATTR_NOTE): cv.string,
    }
)

SERVICE_LOG_FEEDING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SUBJECT_NAME): cv.string,
        vol.Required(ATTR_AMOUNT): vol.Coerce(float),
        vol.Required(ATTR_CATEGORY): cv.string,
        vol.Optional(ATTR_DESCRIPTION): cv.string,
        vol.Optional(ATTR_TIMESTAMP): cv.string,
    }
)

SERVICE_DELETE_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_EVENT_ID): cv.string,
    }
)

# Alarm tracking per subject
_alarm_state: dict[str, dict[str, bool]] = {}
# High glucose delay tracking
_high_glucose_since: dict[str, datetime | None] = {}
HIGH_GLUCOSE_DELAY = timedelta(minutes=5)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the GlucoFarmer integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GlucoFarmerConfigEntry) -> bool:
    """Set up GlucoFarmer from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Initialize shared store (one per HA instance)
    if "store" not in hass.data[DOMAIN]:
        store = GlucoFarmerStore(hass)
        await store.async_load()
        hass.data[DOMAIN]["store"] = store
    else:
        store = hass.data[DOMAIN]["store"]

    # Create coordinator
    coordinator = GlucoFarmerCoordinator(hass, entry, store)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Listen for Dexcom sensor state changes for immediate refresh
    @callback
    def _handle_dexcom_update(_event: Any) -> None:
        hass.async_create_task(coordinator.async_request_refresh())

    unsub_dexcom = async_track_state_change_event(
        hass, [coordinator.glucose_sensor_id], _handle_dexcom_update
    )
    entry.async_on_unload(unsub_dexcom)

    # Register services (once)
    if not hass.services.has_service(DOMAIN, SERVICE_LOG_INSULIN):
        _register_services(hass)

    # Set up alarm monitoring
    subject_name = entry.data[CONF_SUBJECT_NAME]
    _alarm_state.setdefault(subject_name, {
        "low_notified": False,
        "critical_low_notified": False,
        "high_notified": False,
        "no_data_notified": False,
    })
    _high_glucose_since.setdefault(subject_name, None)

    unsub = coordinator.async_add_listener(
        lambda: _check_alarms(hass, coordinator)
    )
    entry.async_on_unload(unsub)

    # Set up daily report (once per DOMAIN, fires at 00:05 each day)
    if "daily_report_unsub" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["last_report_date"] = ""
        _schedule_daily_report(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Auto-generate/update dashboard
    await async_update_dashboard(hass)

    # Regenerate dashboard when options change (e.g. new presets)
    entry.async_on_unload(
        entry.add_update_listener(_async_options_updated)
    )

    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: GlucoFarmerConfigEntry
) -> None:
    """Handle options update -- reload entry so new preset entities are created."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GlucoFarmerConfigEntry) -> bool:
    """Unload a config entry."""
    subject_name = entry.data[CONF_SUBJECT_NAME]
    _alarm_state.pop(subject_name, None)
    _high_glucose_since.pop(subject_name, None)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Clean up shared data if no more entries
    remaining = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != entry.entry_id
    ]
    if not remaining:
        if "daily_report_unsub" in hass.data[DOMAIN]:
            hass.data[DOMAIN]["daily_report_unsub"]()
        hass.data.pop(DOMAIN, None)

    # Update dashboard to remove the unloaded subject
    if remaining:
        await async_update_dashboard(hass)

    return unload_ok


@callback
def _register_services(hass: HomeAssistant) -> None:
    """Register GlucoFarmer services."""

    async def handle_log_insulin(call: ServiceCall) -> None:
        """Handle log_insulin service call."""
        store: GlucoFarmerStore = hass.data[DOMAIN]["store"]
        event_id = await store.async_log_insulin(
            subject_name=call.data[ATTR_SUBJECT_NAME],
            product=call.data[ATTR_PRODUCT],
            amount=call.data[ATTR_AMOUNT],
            timestamp=call.data.get(ATTR_TIMESTAMP),
            note=call.data.get(ATTR_NOTE),
        )
        _LOGGER.info("Logged insulin event %s", event_id)
        # Refresh coordinators to update daily totals
        await _refresh_coordinator_for_subject(hass, call.data[ATTR_SUBJECT_NAME])

    async def handle_log_feeding(call: ServiceCall) -> None:
        """Handle log_feeding service call."""
        store: GlucoFarmerStore = hass.data[DOMAIN]["store"]
        event_id = await store.async_log_feeding(
            subject_name=call.data[ATTR_SUBJECT_NAME],
            amount=call.data[ATTR_AMOUNT],
            category=call.data[ATTR_CATEGORY],
            description=call.data.get(ATTR_DESCRIPTION),
            timestamp=call.data.get(ATTR_TIMESTAMP),
        )
        _LOGGER.info("Logged feeding event %s", event_id)
        await _refresh_coordinator_for_subject(hass, call.data[ATTR_SUBJECT_NAME])

    async def handle_delete_event(call: ServiceCall) -> None:
        """Handle delete_event service call."""
        store: GlucoFarmerStore = hass.data[DOMAIN]["store"]
        deleted = await store.async_delete_event(call.data[ATTR_EVENT_ID])
        if deleted:
            _LOGGER.info("Deleted event %s", call.data[ATTR_EVENT_ID])
            # Refresh all coordinators
            for entry in hass.config_entries.async_entries(DOMAIN):
                if hasattr(entry, "runtime_data") and entry.runtime_data:
                    await entry.runtime_data.async_request_refresh()
        else:
            _LOGGER.warning("Event %s not found", call.data[ATTR_EVENT_ID])

    hass.services.async_register(
        DOMAIN, SERVICE_LOG_INSULIN, handle_log_insulin, schema=SERVICE_LOG_INSULIN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_LOG_FEEDING, handle_log_feeding, schema=SERVICE_LOG_FEEDING_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_EVENT, handle_delete_event, schema=SERVICE_DELETE_EVENT_SCHEMA
    )


async def _refresh_coordinator_for_subject(hass: HomeAssistant, subject_name: str) -> None:
    """Refresh the coordinator for a specific subject."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_SUBJECT_NAME) == subject_name
            and hasattr(entry, "runtime_data")
            and entry.runtime_data
        ):
            await entry.runtime_data.async_request_refresh()


@callback
def _check_alarms(hass: HomeAssistant, coordinator: GlucoFarmerCoordinator) -> None:
    """Check glucose levels and send alarm notifications."""
    if coordinator.data is None:
        return

    subject_name = coordinator.subject_name
    status = coordinator.data.glucose_status
    glucose = coordinator.data.glucose_value
    state = _alarm_state.get(subject_name)
    if state is None:
        return

    now = datetime.now()

    # Critical low - immediate, breaks through DND
    if status == STATUS_CRITICAL_LOW and not state["critical_low_notified"]:
        hass.async_create_task(
            _send_notification(
                hass,
                title=f"CRITICAL: {subject_name} glucose critically low!",
                message=f"{subject_name} glucose is {glucose} mg/dL - CRITICAL LOW!",
                priority="critical",
            )
        )
        state["critical_low_notified"] = True
        state["low_notified"] = True
    elif status == STATUS_LOW and not state["low_notified"]:
        hass.async_create_task(
            _send_notification(
                hass,
                title=f"Warning: {subject_name} glucose low",
                message=f"{subject_name} glucose is {glucose} mg/dL - below threshold",
                priority="high",
            )
        )
        state["low_notified"] = True
    elif status in (STATUS_HIGH, STATUS_VERY_HIGH):
        # Delay high glucose notification by 5 minutes
        if _high_glucose_since.get(subject_name) is None:
            _high_glucose_since[subject_name] = now
        elif (
            not state["high_notified"]
            and (now - _high_glucose_since[subject_name]) >= HIGH_GLUCOSE_DELAY
        ):
            severity = "very high" if status == STATUS_VERY_HIGH else "high"
            priority = "critical" if status == STATUS_VERY_HIGH else "high"
            hass.async_create_task(
                _send_notification(
                    hass,
                    title=f"Warning: {subject_name} glucose {severity}",
                    message=f"{subject_name} glucose is {glucose} mg/dL - {severity}!",
                    priority=priority,
                )
            )
            state["high_notified"] = True
    elif status == STATUS_NO_DATA and not state["no_data_notified"]:
        age = coordinator.data.reading_age_minutes
        age_text = f"{round(age)} min" if age is not None else "unknown duration"
        hass.async_create_task(
            _send_notification(
                hass,
                title=f"Data gap: {subject_name}",
                message=f"No glucose reading from {subject_name} for {age_text}",
                priority="default",
            )
        )
        state["no_data_notified"] = True

    # Reset flags when status returns to normal
    if status == STATUS_NORMAL:
        if state["low_notified"] or state["critical_low_notified"]:
            hass.async_create_task(
                _send_notification(
                    hass,
                    title=f"{subject_name} glucose back to normal",
                    message=f"{subject_name} glucose is {glucose} mg/dL - back in range",
                    priority="low",
                )
            )
        state["low_notified"] = False
        state["critical_low_notified"] = False
        state["high_notified"] = False
        state["no_data_notified"] = False
        _high_glucose_since[subject_name] = None


async def _send_notification(
    hass: HomeAssistant,
    title: str,
    message: str,
    priority: str = "default",
) -> None:
    """Send a notification via persistent notification and notify service."""
    # Always create a persistent notification
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "message": message,
            "title": title,
            "notification_id": f"glucofarmer_{title[:30].replace(' ', '_').lower()}",
        },
    )

    # Map internal priority to FCM-compatible Android priority (only "high"/"normal" valid)
    android_priority = "high" if priority in ("critical", "high") else "normal"
    notify_data: dict = {"priority": android_priority}
    if priority == "critical":
        # iOS: critical alert breaks through DND
        notify_data["push"] = {"sound": {"critical": 1}}

    # Try to send via notify service if available
    try:
        await hass.services.async_call(
            "notify",
            "notify",
            {
                "title": title,
                "message": message,
                "data": notify_data,
            },
        )
    except Exception:
        _LOGGER.debug("Notify service not available, using persistent notification only")


@callback
def _schedule_daily_report(hass: HomeAssistant) -> None:
    """Schedule next daily report at 00:05, reschedules itself after firing."""
    now = dt_util.now()
    next_run = now.replace(hour=0, minute=5, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)

    @callback
    def _fire(_now: Any) -> None:
        hass.async_create_task(_send_daily_report(hass))
        _schedule_daily_report(hass)

    if "daily_report_unsub" in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN]["daily_report_unsub"]()

    hass.data[DOMAIN]["daily_report_unsub"] = async_track_point_in_time(
        hass, _fire, next_run
    )
    _LOGGER.debug("Daily report scheduled for %s", next_run.isoformat())


async def _send_daily_report(hass: HomeAssistant) -> None:
    """Send daily report for the previous day.

    Runs at midnight (00:00-00:01). Computes all statistics retrospectively
    from persistent store data for the previous day -- no dependency on
    in-memory coordinator state that may have been reset.
    """
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    domain_data = hass.data.get(DOMAIN)
    if domain_data is None:
        return

    # Safety check: only send once per day
    if domain_data.get("last_report_date") == today_str:
        return

    domain_data["last_report_date"] = today_str
    store: GlucoFarmerStore = domain_data["store"]

    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return

    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_start = (
        now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    ).astimezone()
    yesterday_end = yesterday_start + timedelta(days=1)
    recorder_instance = get_instance(hass)

    # Build report
    lines = [
        f"GlucoFarmer daily report - {yesterday}",
        "=" * 60,
        "",
    ]

    for entry in entries:
        subject_name = entry.data.get(CONF_SUBJECT_NAME, "Unknown")
        glucose_sensor_id = entry.data.get(CONF_GLUCOSE_SENSOR, "")

        # Get thresholds from coordinator (if running) or use defaults
        coordinator: GlucoFarmerCoordinator | None = getattr(
            entry, "runtime_data", None
        )
        if coordinator is not None:
            crit_low = coordinator.critical_low_threshold
            low = coordinator.low_threshold
            high = coordinator.high_threshold
            very_high = coordinator.very_high_threshold
        else:
            crit_low = DEFAULT_CRITICAL_LOW_THRESHOLD
            low = DEFAULT_LOW_THRESHOLD
            high = DEFAULT_HIGH_THRESHOLD
            very_high = DEFAULT_VERY_HIGH_THRESHOLD

        # Get yesterday's events from persistent store
        insulin_events = store.get_events_for_date(
            subject_name, yesterday, EVENT_TYPE_INSULIN
        )
        feeding_events = store.get_events_for_date(
            subject_name, yesterday, EVENT_TYPE_FEEDING
        )

        # Get yesterday's readings from HA Recorder
        readings: list[tuple[datetime, float]] = []
        if recorder_instance is not None and glucose_sensor_id:
            states_dict = await recorder_instance.async_add_executor_job(
                state_changes_during_period,
                hass, yesterday_start, yesterday_end, glucose_sensor_id,
            )
            for state in states_dict.get(glucose_sensor_id, []):
                try:
                    value = float(state.state)
                except (ValueError, TypeError):
                    s = state.state.lower() if state.state else ""
                    if s in {"low", "niedrig"}:
                        value = crit_low - 1
                    elif s in {"high", "hoch"}:
                        value = very_high + 1
                    else:
                        continue
                readings.append((state.last_changed, value))

        if not readings:
            lines.append(f"{subject_name}: No readings recorded for {yesterday}")
            lines.append("")
            continue

        # Compute 5-zone stats
        total = len(readings)
        n_critical_low = sum(1 for _, v in readings if v < crit_low)
        n_low = sum(1 for _, v in readings if crit_low <= v < low)
        n_in_range = sum(1 for _, v in readings if low <= v <= high)
        n_high = sum(1 for _, v in readings if high < v <= very_high)
        n_very_high = sum(1 for _, v in readings if v > very_high)

        pct_crit_low = round(n_critical_low / total * 100, 1)
        pct_low = round(n_low / total * 100, 1)
        pct_in_range = round(n_in_range / total * 100, 1)
        pct_high = round(n_high / total * 100, 1)
        pct_very_high = round(n_very_high / total * 100, 1)

        # Gap-based data completeness
        timestamps = sorted(ts for ts, _ in readings)
        boundary = timestamps + [yesterday_end]
        missed = 0
        for i in range(1, len(boundary)):
            gap_minutes = (boundary[i] - boundary[i - 1]).total_seconds() / 60
            missed += max(0, round(gap_minutes / 5) - 1)
        total_expected = total + missed
        completeness = round(total / total_expected * 100, 1) if total_expected > 0 else 0.0

        # Daily totals from events
        insulin_total = sum(e.get("amount", 0) for e in insulin_events)
        bes_total = sum(e.get("amount", 0) for e in feeding_events)

        # Current state (if coordinator is available)
        current_glucose = "N/A"
        current_trend = "N/A"
        current_status = "N/A"
        if coordinator is not None and coordinator.data is not None:
            current_glucose = coordinator.data.glucose_value or "N/A"
            current_trend = coordinator.data.glucose_trend or "N/A"
            current_status = coordinator.data.glucose_status

        lines.extend([
            f"--- {subject_name} ---",
            f"  Current glucose: {current_glucose} mg/dL ({current_trend})",
            f"  Current status: {current_status}",
            f"  Thresholds: <{crit_low} critical | <{low} low | "
            f"{low}-{high} target | >{high} high | >{very_high} very high",
            f"  --- Yesterday ({yesterday}) ---",
            f"  Readings recorded: {total}",
            f"  Critical low (<{crit_low}): {pct_crit_low}%",
            f"  Low ({crit_low}-{low}): {pct_low}%",
            f"  In range ({low}-{high}): {pct_in_range}%",
            f"  High ({high}-{very_high}): {pct_high}%",
            f"  Very high (>{very_high}): {pct_very_high}%",
            f"  Data completeness: {completeness}%",
            f"  Total insulin: {insulin_total} IU",
            f"  Total feeding: {bes_total} BE",
        ])

        # Add notable events
        all_yesterday_events = store.get_events_for_date(subject_name, yesterday)
        emergencies = [
            e for e in all_yesterday_events
            if e.get("category") in ("emergency_single", "emergency_double")
        ]
        interventions = [
            e for e in all_yesterday_events if e.get("category") == "intervention"
        ]

        if emergencies:
            lines.append(f"  Emergency rations: {len(emergencies)}")
        if interventions:
            lines.append(f"  Interventions: {len(interventions)}")

        lines.append("")

    report_text = "\n".join(lines)

    # Send via email notify service
    try:
        await hass.services.async_call(
            "notify",
            "notify",
            {
                "title": f"GlucoFarmer daily report - {yesterday}",
                "message": report_text,
            },
        )
        _LOGGER.info("Daily report sent successfully")
    except Exception:
        _LOGGER.debug("Could not send daily report via notify service")

    # Also create persistent notification (unique per day so old reports are preserved)
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "message": report_text,
            "title": f"GlucoFarmer daily report - {yesterday}",
            "notification_id": f"glucofarmer_daily_report_{yesterday}",
        },
    )
