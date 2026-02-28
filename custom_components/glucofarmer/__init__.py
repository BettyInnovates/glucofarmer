"""GlucoFarmer integration for Home Assistant."""

from __future__ import annotations

from datetime import datetime, timedelta
from email import encoders
import statistics as stats_module
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
import ssl
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
    ALARM_PRIORITY_CRITICAL,
    ALARM_PRIORITY_OFF,
    ATTR_AMOUNT,
    ATTR_CATEGORY,
    ATTR_DESCRIPTION,
    ATTR_EVENT_ID,
    ATTR_NOTE,
    ATTR_SUBJECT_NAME,
    ATTR_PRODUCT,
    ATTR_TIMESTAMP,
    CONF_ALARM_CRITICAL_LOW,
    CONF_ALARM_FALLING_QUICKLY,
    CONF_ALARM_HIGH,
    CONF_ALARM_LOW,
    CONF_ALARM_NO_DATA,
    CONF_ALARM_RISING_QUICKLY,
    CONF_ALARM_VERY_HIGH,
    CONF_ALARM_VERY_LOW,
    CONF_GLUCOSE_SENSOR,
    CONF_NOTIFY_TARGETS,
    CONF_SMTP_ENABLED,
    CONF_SMTP_ENCRYPTION,
    CONF_SMTP_HOST,
    CONF_SMTP_PASSWORD,
    CONF_SMTP_PORT,
    CONF_SMTP_RECIPIENTS,
    CONF_SMTP_SENDER,
    CONF_SMTP_SENDER_NAME,
    CONF_SMTP_USERNAME,
    CONF_SUBJECT_NAME,
    DEFAULT_ALARM_CRITICAL_LOW,
    DEFAULT_ALARM_FALLING_QUICKLY,
    DEFAULT_ALARM_HIGH,
    DEFAULT_ALARM_LOW,
    DEFAULT_ALARM_NO_DATA,
    DEFAULT_ALARM_RISING_QUICKLY,
    DEFAULT_ALARM_VERY_HIGH,
    DEFAULT_ALARM_VERY_LOW,
    DEFAULT_CRITICAL_LOW_THRESHOLD,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_NOTIFY_TARGETS,
    DEFAULT_VERY_HIGH_THRESHOLD,
    DOMAIN,
    EVENT_TYPE_FEEDING,
    EVENT_TYPE_INSULIN,
    PLATFORMS,
    SERVICE_DELETE_EVENT,
    SERVICE_LOG_FEEDING,
    SERVICE_LOG_INSULIN,
    SERVICE_SEND_DAILY_REPORT,
    STATUS_CRITICAL_LOW,
    STATUS_HIGH,
    STATUS_LOW,
    STATUS_NO_DATA,
    STATUS_NORMAL,
    STATUS_VERY_HIGH,
    STATUS_VERY_LOW,
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

# Maximum weight (minutes) for the last valid reading before a data gap.
# Mirrors coordinator._GAP_CAP_MINUTES -- one Dexcom transmission cycle.
_GAP_CAP_MINUTES = 5.0

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

    # Create coordinator and load persisted thresholds before first data refresh
    # so zone stats are computed with the correct thresholds from the start.
    coordinator = GlucoFarmerCoordinator(hass, entry, store)
    await coordinator.async_load_thresholds()
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
        "falling_quickly_notified": False,
        "rising_quickly_notified": False,
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

    async def handle_send_daily_report(_call: ServiceCall) -> None:
        """Manually trigger the daily report (for testing)."""
        domain_data = hass.data.get(DOMAIN, {})
        domain_data.pop("last_report_date", None)
        await _send_daily_report(hass)

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_DAILY_REPORT, handle_send_daily_report
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

    opts = coordinator.config_entry.options
    now = datetime.now()

    def _fire(title: str, message: str, conf_key: str, default_priority: str) -> None:
        """Send alarm if not configured as off. Maps config priority to internal priority."""
        configured = opts.get(conf_key, default_priority)
        if configured == ALARM_PRIORITY_OFF:
            return
        internal = "critical" if configured == ALARM_PRIORITY_CRITICAL else "high"
        hass.async_create_task(
            _send_notification(hass, title=title, message=message, priority=internal, opts=opts)
        )

    # Critical low
    if status == STATUS_CRITICAL_LOW and not state["critical_low_notified"]:
        _fire(
            f"CRITICAL: {subject_name} Glukose kritisch niedrig!",
            f"{subject_name}: {glucose} mg/dL — KRITISCH NIEDRIG!",
            CONF_ALARM_CRITICAL_LOW, DEFAULT_ALARM_CRITICAL_LOW,
        )
        state["critical_low_notified"] = True
        state["low_notified"] = True
    elif status in (STATUS_VERY_LOW, STATUS_LOW) and not state["low_notified"]:
        conf_key = CONF_ALARM_VERY_LOW if status == STATUS_VERY_LOW else CONF_ALARM_LOW
        default = DEFAULT_ALARM_VERY_LOW if status == STATUS_VERY_LOW else DEFAULT_ALARM_LOW
        _fire(
            f"Warnung: {subject_name} Glukose niedrig",
            f"{subject_name}: {glucose} mg/dL — unter Zielbereich",
            conf_key, default,
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
            conf_key = CONF_ALARM_VERY_HIGH if status == STATUS_VERY_HIGH else CONF_ALARM_HIGH
            default = DEFAULT_ALARM_VERY_HIGH if status == STATUS_VERY_HIGH else DEFAULT_ALARM_HIGH
            label = "sehr hoch" if status == STATUS_VERY_HIGH else "hoch"
            _fire(
                f"Warnung: {subject_name} Glukose {label}",
                f"{subject_name}: {glucose} mg/dL — {label}!",
                conf_key, default,
            )
            state["high_notified"] = True
    elif status == STATUS_NO_DATA and not state["no_data_notified"]:
        age = coordinator.data.reading_age_minutes
        age_text = f"{round(age)} min" if age is not None else "unbekannte Dauer"
        _fire(
            f"Datenlücke: {subject_name}",
            f"Kein Glukose-Signal von {subject_name} seit {age_text}",
            CONF_ALARM_NO_DATA, DEFAULT_ALARM_NO_DATA,
        )
        state["no_data_notified"] = True

    # Trend alarms
    trend = coordinator.data.glucose_trend
    if trend == "falling_quickly" and not state["falling_quickly_notified"]:
        _fire(
            f"CRITICAL: {subject_name} Glukose fällt schnell!",
            f"{subject_name}: {glucose} mg/dL und fällt stark",
            CONF_ALARM_FALLING_QUICKLY, DEFAULT_ALARM_FALLING_QUICKLY,
        )
        state["falling_quickly_notified"] = True
    elif trend != "falling_quickly":
        state["falling_quickly_notified"] = False

    if trend == "rising_quickly" and not state["rising_quickly_notified"]:
        _fire(
            f"Warnung: {subject_name} Glukose steigt schnell",
            f"{subject_name}: {glucose} mg/dL und steigt stark",
            CONF_ALARM_RISING_QUICKLY, DEFAULT_ALARM_RISING_QUICKLY,
        )
        state["rising_quickly_notified"] = True
    elif trend != "rising_quickly":
        state["rising_quickly_notified"] = False

    # Reset no_data flag as soon as signal returns (regardless of glucose level)
    if status != STATUS_NO_DATA:
        state["no_data_notified"] = False

    # Reset flags when status returns to normal
    if status == STATUS_NORMAL:
        if state["low_notified"] or state["critical_low_notified"]:
            _fire(
                f"{subject_name} Glukose wieder im Bereich",
                f"{subject_name}: {glucose} mg/dL — zurück im Zielbereich",
                CONF_ALARM_LOW, DEFAULT_ALARM_LOW,
            )
        state["low_notified"] = False
        state["critical_low_notified"] = False
        state["high_notified"] = False
        _high_glucose_since[subject_name] = None


async def _send_notification(
    hass: HomeAssistant,
    title: str,
    message: str,
    priority: str = "default",
    opts: dict | None = None,
) -> None:
    """Send a notification via persistent notification and configured notify targets.

    priority: "critical" (iOS DND-bypass + Android high) or "high" (Android high only).
    opts: config entry options dict, used to read CONF_NOTIFY_TARGETS.
          Falls back to notify.notify (broadcast) if no targets configured.
    """
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
        # Android: alarm_stream channel bypasses DND, ttl=0 ensures immediate delivery
        notify_data["channel"] = "alarm_stream"
        notify_data["ttl"] = 0

    # Determine notify targets
    targets_str = (opts or {}).get(CONF_NOTIFY_TARGETS, DEFAULT_NOTIFY_TARGETS)
    targets = [t.strip() for t in targets_str.split(",") if t.strip()] if targets_str else []

    if not targets:
        # No targets configured: broadcast via notify.notify
        targets = ["notify"]

    for target in targets:
        # target is either "notify" (broadcast) or a mobile_app_* service name
        service = "notify" if target == "notify" else target
        try:
            await hass.services.async_call(
                "notify",
                service,
                {
                    "title": title,
                    "message": message,
                    "data": notify_data,
                },
            )
        except Exception:
            _LOGGER.debug("Notify service 'notify.%s' not available", service)


def _get_smtp_config(hass: HomeAssistant) -> dict | None:
    """Return SMTP config from the first entry that has smtp_enabled=True.

    SMTP is treated as a global setting: only one subject entry needs to be
    configured. Returns None if no entry has SMTP enabled.
    """
    for entry in hass.config_entries.async_entries(DOMAIN):
        opts = entry.options
        if not opts.get(CONF_SMTP_ENABLED):
            continue
        recipients = [
            r.strip()
            for r in opts.get(CONF_SMTP_RECIPIENTS, "").split(",")
            if r.strip()
        ]
        if not recipients:
            continue
        return {
            "host": opts.get(CONF_SMTP_HOST, ""),
            "port": int(opts.get(CONF_SMTP_PORT, 465)),
            "encryption": opts.get(CONF_SMTP_ENCRYPTION, "tls"),
            "sender": opts.get(CONF_SMTP_SENDER, ""),
            "sender_name": opts.get(CONF_SMTP_SENDER_NAME, "GlucoFarmer"),
            "username": opts.get(CONF_SMTP_USERNAME, ""),
            "password": opts.get(CONF_SMTP_PASSWORD, ""),
            "recipients": recipients,
        }
    return None


def _build_csv(readings: list[tuple[datetime, float]]) -> str:
    """Build a semicolon-separated CSV string from glucose readings.

    Returns a plain UTF-8 string. Caller should encode with utf-8-sig
    (adds BOM) for Excel compatibility.
    Two timestamp columns:
    - Timestamp: ISO 8601 with timezone offset (for automated processing)
    - Datum_Uhrzeit: German date format without offset (for Excel)
    """
    lines = ["Timestamp;Datum_Uhrzeit;Glukose_mgdL"]
    for ts, value in sorted(readings, key=lambda x: x[0]):
        local_ts = dt_util.as_local(ts)
        iso_ts = local_ts.isoformat(timespec="seconds")
        de_ts = local_ts.strftime("%d.%m.%Y %H:%M:%S")
        lines.append(f"{iso_ts};{de_ts};{int(round(value))}")
    return "\n".join(lines)


async def _send_daily_report_email(
    hass: HomeAssistant,
    smtp_config: dict,
    subject_line: str,
    body: str,
    attachments: list[tuple[str, str]],
) -> None:
    """Send daily report email with CSV file attachments via smtplib.

    Runs the blocking SMTP call in an executor thread so the HA event loop
    is not blocked. Errors are logged but do not propagate -- the persistent
    notification is always created regardless of email success.

    Args:
        attachments: List of (filename, csv_content_str) tuples.
                     Content is encoded as UTF-8 with BOM for Excel.
    """
    def _do_send() -> None:
        msg = MIMEMultipart()
        msg["From"] = f"{smtp_config['sender_name']} <{smtp_config['sender']}>"
        msg["To"] = ", ".join(smtp_config["recipients"])
        msg["Subject"] = subject_line
        msg.attach(MIMEText(body, "plain", "utf-8"))

        for filename, csv_content in attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(csv_content.encode("utf-8-sig"))
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=filename,
            )
            msg.attach(part)

        host = smtp_config["host"]
        port = smtp_config["port"]
        if smtp_config["encryption"] == "tls":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context) as server:
                server.login(smtp_config["username"], smtp_config["password"])
                server.sendmail(
                    smtp_config["sender"],
                    smtp_config["recipients"],
                    msg.as_string(),
                )
        else:  # starttls
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(smtp_config["username"], smtp_config["password"])
                server.sendmail(
                    smtp_config["sender"],
                    smtp_config["recipients"],
                    msg.as_string(),
                )

    try:
        await hass.async_add_executor_job(_do_send)
        _LOGGER.info(
            "Daily report email sent to %s", smtp_config["recipients"]
        )
    except Exception as err:
        _LOGGER.error("Failed to send daily report email: %s", err)


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
    # Collect readings per subject for CSV attachments
    subject_readings: dict[str, list[tuple[datetime, float]]] = {}

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

        # Get yesterday's readings from HA Recorder.
        # Gap markers (unknown/unavailable) are retained as None values --
        # they are essential for accurate time-weighting and completeness.
        all_entries: list[tuple[datetime, float | None]] = []
        if recorder_instance is not None and glucose_sensor_id:
            states_dict = await recorder_instance.async_add_executor_job(
                state_changes_during_period,
                hass, yesterday_start, yesterday_end, glucose_sensor_id,
            )
            for state in states_dict.get(glucose_sensor_id, []):
                try:
                    entry_value: float | None = float(state.state)
                except (ValueError, TypeError):
                    s = state.state.lower() if state.state else ""
                    if s in {"low", "niedrig"}:
                        entry_value = crit_low - 1
                    elif s in {"high", "hoch"}:
                        entry_value = very_high + 1
                    else:
                        entry_value = None  # unknown/unavailable -- gap marker
                all_entries.append((state.last_changed, entry_value))

        # Numeric readings only (for CSV, completeness, min/max/median)
        readings = [(ts, v) for ts, v in all_entries if v is not None]
        subject_readings[subject_name] = readings

        if not readings:
            lines.append(f"{subject_name}: No readings recorded for {yesterday}")
            lines.append("")
            continue

        # Unweighted stats (min, max, median -- time-weighting not critical here)
        values = [v for _, v in readings]
        glucose_min = int(round(min(values)))
        glucose_max = int(round(max(values)))
        glucose_median = round(stats_module.median(values), 1)

        # Time-weighted zone percentages, mean and SD.
        # Weight per reading = time until next event (no cap for stable glucose),
        # capped at _GAP_CAP_MINUTES when the immediately following event is a gap marker.
        zone_weights = [0.0, 0.0, 0.0, 0.0, 0.0]
        weighted_readings: list[tuple[float, float]] = []  # (weight, value)
        covered_minutes = 0.0

        for i, (ts, value) in enumerate(all_entries):
            if value is None:
                continue  # gap marker -- contributes no zone time

            if i + 1 < len(all_entries):
                boundary_ts, next_val = all_entries[i + 1]
                has_gap_next = next_val is None
            else:
                boundary_ts = yesterday_end
                has_gap_next = False

            duration_min = (boundary_ts - ts).total_seconds() / 60.0
            w = min(duration_min, _GAP_CAP_MINUTES) if has_gap_next else duration_min
            w = max(0.0, w)
            covered_minutes += w

            if value < crit_low:
                zone_weights[0] += w
            elif value < low:
                zone_weights[1] += w
            elif value <= high:
                zone_weights[2] += w
            elif value <= very_high:
                zone_weights[3] += w
            else:
                zone_weights[4] += w

            weighted_readings.append((w, value))

        total_w = sum(w for w, _ in weighted_readings)
        if total_w > 0:
            pct_crit_low = round(zone_weights[0] / total_w * 100, 1)
            pct_low = round(zone_weights[1] / total_w * 100, 1)
            pct_in_range = round(zone_weights[2] / total_w * 100, 1)
            pct_high = round(zone_weights[3] / total_w * 100, 1)
            pct_very_high = round(zone_weights[4] / total_w * 100, 1)
            weighted_mean = sum(w * v for w, v in weighted_readings) / total_w
            glucose_mean = round(weighted_mean, 1)
            glucose_sd = round(
                (sum(w * (v - weighted_mean) ** 2 for w, v in weighted_readings) / total_w) ** 0.5,
                1,
            ) if len(weighted_readings) > 1 else 0.0
        else:
            pct_crit_low = pct_low = pct_in_range = pct_high = pct_very_high = 0.0
            glucose_mean = 0.0
            glucose_sd = 0.0

        # Time-based data completeness
        total_minutes = (yesterday_end - yesterday_start).total_seconds() / 60.0
        uncovered_min = round(max(0.0, total_minutes - covered_minutes))
        completeness = round(covered_minutes / total_minutes * 100, 1) if total_minutes > 0 else 0.0

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
            f"  Without valid data: {uncovered_min} min",
            f"  Min: {glucose_min} mg/dL  |  Max: {glucose_max} mg/dL",
            f"  Mean: {glucose_mean} mg/dL  |  Median: {glucose_median} mg/dL  |  SD: {glucose_sd}",
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

    # Send email with per-subject CSV attachments
    smtp_config = _get_smtp_config(hass)
    if smtp_config:
        attachments = [
            (f"{name}_{yesterday}.csv", _build_csv(readings))
            for name, readings in subject_readings.items()
            if readings
        ]
        await _send_daily_report_email(
            hass,
            smtp_config,
            f"GlucoFarmer daily report - {yesterday}",
            report_text,
            attachments,
        )
