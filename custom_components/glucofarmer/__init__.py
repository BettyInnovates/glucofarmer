"""GlucoFarmer integration for Home Assistant.

Preclinical CGM monitoring for diabetized pigs.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_AMOUNT,
    ATTR_CATEGORY,
    ATTR_DESCRIPTION,
    ATTR_EVENT_ID,
    ATTR_NOTE,
    ATTR_PIG_NAME,
    ATTR_PRODUCT,
    ATTR_TIMESTAMP,
    CONF_PIG_NAME,
    DOMAIN,
    PLATFORMS,
    SERVICE_DELETE_EVENT,
    SERVICE_LOG_FEEDING,
    SERVICE_LOG_INSULIN,
    STATUS_CRITICAL_LOW,
    STATUS_HIGH,
    STATUS_LOW,
    STATUS_NO_DATA,
)
from .coordinator import GlucoFarmerConfigEntry, GlucoFarmerCoordinator
from .store import GlucoFarmerStore

_LOGGER = logging.getLogger(__name__)

SERVICE_LOG_INSULIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PIG_NAME): cv.string,
        vol.Required(ATTR_PRODUCT): cv.string,
        vol.Required(ATTR_AMOUNT): vol.Coerce(float),
        vol.Optional(ATTR_TIMESTAMP): cv.string,
        vol.Optional(ATTR_NOTE): cv.string,
    }
)

SERVICE_LOG_FEEDING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PIG_NAME): cv.string,
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

# Alarm tracking per pig
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

    # Register services (once)
    if not hass.services.has_service(DOMAIN, SERVICE_LOG_INSULIN):
        _register_services(hass)

    # Set up alarm monitoring
    pig_name = entry.data[CONF_PIG_NAME]
    _alarm_state.setdefault(pig_name, {
        "low_notified": False,
        "critical_low_notified": False,
        "high_notified": False,
        "no_data_notified": False,
    })
    _high_glucose_since.setdefault(pig_name, None)

    unsub = coordinator.async_add_listener(
        lambda: _check_alarms(hass, coordinator)
    )
    entry.async_on_unload(unsub)

    # Set up daily email report (once, at midnight)
    if "daily_report_unsub" not in hass.data[DOMAIN]:
        unsub_daily = async_track_time_interval(
            hass,
            lambda now: hass.async_create_task(_send_daily_report(hass)),
            timedelta(minutes=1),
        )
        hass.data[DOMAIN]["daily_report_unsub"] = unsub_daily
        hass.data[DOMAIN]["last_report_date"] = ""

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GlucoFarmerConfigEntry) -> bool:
    """Unload a config entry."""
    pig_name = entry.data[CONF_PIG_NAME]
    _alarm_state.pop(pig_name, None)
    _high_glucose_since.pop(pig_name, None)

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

    return unload_ok


@callback
def _register_services(hass: HomeAssistant) -> None:
    """Register GlucoFarmer services."""

    async def handle_log_insulin(call: ServiceCall) -> None:
        """Handle log_insulin service call."""
        store: GlucoFarmerStore = hass.data[DOMAIN]["store"]
        event_id = await store.async_log_insulin(
            pig_name=call.data[ATTR_PIG_NAME],
            product=call.data[ATTR_PRODUCT],
            amount=call.data[ATTR_AMOUNT],
            timestamp=call.data.get(ATTR_TIMESTAMP),
            note=call.data.get(ATTR_NOTE),
        )
        _LOGGER.info("Logged insulin event %s", event_id)
        # Refresh coordinators to update daily totals
        await _refresh_coordinator_for_pig(hass, call.data[ATTR_PIG_NAME])

    async def handle_log_feeding(call: ServiceCall) -> None:
        """Handle log_feeding service call."""
        store: GlucoFarmerStore = hass.data[DOMAIN]["store"]
        event_id = await store.async_log_feeding(
            pig_name=call.data[ATTR_PIG_NAME],
            amount=call.data[ATTR_AMOUNT],
            category=call.data[ATTR_CATEGORY],
            description=call.data.get(ATTR_DESCRIPTION),
            timestamp=call.data.get(ATTR_TIMESTAMP),
        )
        _LOGGER.info("Logged feeding event %s", event_id)
        await _refresh_coordinator_for_pig(hass, call.data[ATTR_PIG_NAME])

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


async def _refresh_coordinator_for_pig(hass: HomeAssistant, pig_name: str) -> None:
    """Refresh the coordinator for a specific pig."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_PIG_NAME) == pig_name
            and hasattr(entry, "runtime_data")
            and entry.runtime_data
        ):
            await entry.runtime_data.async_request_refresh()


@callback
def _check_alarms(hass: HomeAssistant, coordinator: GlucoFarmerCoordinator) -> None:
    """Check glucose levels and send alarm notifications."""
    if coordinator.data is None:
        return

    pig_name = coordinator.pig_name
    status = coordinator.data.glucose_status
    glucose = coordinator.data.glucose_value
    state = _alarm_state.get(pig_name)
    if state is None:
        return

    now = datetime.now()

    # Critical low - immediate, breaks through DND
    if status == STATUS_CRITICAL_LOW and not state["critical_low_notified"]:
        hass.async_create_task(
            _send_notification(
                hass,
                title=f"CRITICAL: {pig_name} glucose critically low!",
                message=f"{pig_name} glucose is {glucose} mg/dL - CRITICAL LOW!",
                priority="critical",
            )
        )
        state["critical_low_notified"] = True
        state["low_notified"] = True
    elif status == STATUS_LOW and not state["low_notified"]:
        hass.async_create_task(
            _send_notification(
                hass,
                title=f"Warning: {pig_name} glucose low",
                message=f"{pig_name} glucose is {glucose} mg/dL - below threshold",
                priority="high",
            )
        )
        state["low_notified"] = True
    elif status == STATUS_HIGH:
        # Delay high glucose notification by 5 minutes
        if _high_glucose_since.get(pig_name) is None:
            _high_glucose_since[pig_name] = now
        elif (
            not state["high_notified"]
            and (now - _high_glucose_since[pig_name]) >= HIGH_GLUCOSE_DELAY
        ):
            hass.async_create_task(
                _send_notification(
                    hass,
                    title=f"Warning: {pig_name} glucose high",
                    message=f"{pig_name} glucose is {glucose} mg/dL - above threshold",
                    priority="high",
                )
            )
            state["high_notified"] = True
    elif status == STATUS_NO_DATA and not state["no_data_notified"]:
        hass.async_create_task(
            _send_notification(
                hass,
                title=f"Data gap: {pig_name}",
                message=(
                    f"No glucose reading from {pig_name} for "
                    f"{coordinator.data.reading_age_minutes} minutes"
                ),
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
                    title=f"{pig_name} glucose back to normal",
                    message=f"{pig_name} glucose is {glucose} mg/dL - back in range",
                    priority="low",
                )
            )
        state["low_notified"] = False
        state["critical_low_notified"] = False
        state["high_notified"] = False
        state["no_data_notified"] = False
        _high_glucose_since[pig_name] = None


async def _send_notification(
    hass: HomeAssistant,
    title: str,
    message: str,
    priority: str = "default",
) -> None:
    """Send a notification via persistent notification and notify service."""
    # Always create a persistent notification
    hass.components.persistent_notification.async_create(
        message=message,
        title=title,
        notification_id=f"glucofarmer_{title[:30].replace(' ', '_').lower()}",
    )

    # Try to send via notify service if available
    try:
        await hass.services.async_call(
            "notify",
            "notify",
            {
                "title": title,
                "message": message,
                "data": {"priority": priority, "push": {"sound": {"critical": 1}}}
                if priority == "critical"
                else {"priority": priority},
            },
        )
    except Exception:
        _LOGGER.debug("Notify service not available, using persistent notification only")


async def _send_daily_report(hass: HomeAssistant) -> None:
    """Send daily email report at midnight."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    domain_data = hass.data.get(DOMAIN)
    if domain_data is None:
        return

    # Only send once per day, around midnight (00:00-00:01)
    if domain_data.get("last_report_date") == today_str:
        return
    if now.hour != 0 or now.minute > 1:
        return

    domain_data["last_report_date"] = today_str
    store: GlucoFarmerStore = domain_data["store"]

    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return

    # Build report
    lines = [
        f"GlucoFarmer daily report - {(now - timedelta(days=1)).strftime('%Y-%m-%d')}",
        "=" * 60,
        "",
    ]

    for entry in entries:
        pig_name = entry.data.get(CONF_PIG_NAME, "Unknown")
        coordinator: GlucoFarmerCoordinator | None = getattr(
            entry, "runtime_data", None
        )
        if coordinator is None or coordinator.data is None:
            lines.append(f"{pig_name}: No data available")
            lines.append("")
            continue

        data = coordinator.data
        lines.extend([
            f"--- {pig_name} ---",
            f"  Current glucose: {data.glucose_value or 'N/A'} mg/dL ({data.glucose_trend or 'N/A'})",
            f"  Status: {data.glucose_status}",
            f"  Time in range: {data.time_in_range_pct}%",
            f"  Time below range: {data.time_below_range_pct}%",
            f"  Time above range: {data.time_above_range_pct}%",
            f"  Data completeness: {data.data_completeness_pct}%",
            f"  Total insulin today: {data.daily_insulin_total} IU",
            f"  Total feeding today: {data.daily_bes_total} BE",
        ])

        # Add notable events
        yesterday_events = store.get_today_events(pig_name)
        emergencies = [
            e for e in yesterday_events
            if e.get("category") in ("emergency_single", "emergency_double")
        ]
        interventions = [
            e for e in yesterday_events if e.get("category") == "intervention"
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
                "title": f"GlucoFarmer daily report - {(now - timedelta(days=1)).strftime('%Y-%m-%d')}",
                "message": report_text,
            },
        )
        _LOGGER.info("Daily report sent successfully")
    except Exception:
        _LOGGER.debug("Could not send daily report via notify service")

    # Also create persistent notification
    hass.components.persistent_notification.async_create(
        message=report_text,
        title="GlucoFarmer daily report",
        notification_id="glucofarmer_daily_report",
    )
