"""Persistent event storage for GlucoFarmer."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
import uuid

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    EVENT_TYPE_FEEDING,
    EVENT_TYPE_INSULIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class GlucoFarmerStore:
    """Manage persistent storage for insulin and feeding events."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._hass = hass
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self._events: list[dict[str, Any]] = []
        self._loaded = False

    async def async_load(self) -> None:
        """Load data from storage."""
        data = await self._store.async_load()
        self._events = data.get("events", []) if data is not None else []
        self._loaded = True

    async def _async_save(self) -> None:
        """Save data to storage."""
        await self._store.async_save({"events": self._events})

    # ---- Events (insulin, feeding) ----

    async def async_log_insulin(
        self,
        subject_name: str,
        product: str,
        amount: float,
        timestamp: str | None = None,
        note: str | None = None,
    ) -> str:
        """Log an insulin event and return the event ID."""
        if not self._loaded:
            await self.async_load()

        event_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        event = {
            "id": event_id,
            "type": EVENT_TYPE_INSULIN,
            "subject_name": subject_name,
            "product": product,
            "amount": amount,
            "timestamp": timestamp or now,
            "created_at": now,
            "note": note,
        }
        self._events.append(event)
        await self._async_save()
        _LOGGER.debug("Logged insulin event %s for %s", event_id, subject_name)
        return event_id

    async def async_log_feeding(
        self,
        subject_name: str,
        amount: float,
        category: str,
        description: str | None = None,
        timestamp: str | None = None,
    ) -> str:
        """Log a feeding event and return the event ID."""
        if not self._loaded:
            await self.async_load()

        event_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        event = {
            "id": event_id,
            "type": EVENT_TYPE_FEEDING,
            "subject_name": subject_name,
            "amount": amount,
            "category": category,
            "description": description,
            "timestamp": timestamp or now,
            "created_at": now,
        }
        self._events.append(event)
        await self._async_save()
        _LOGGER.debug("Logged feeding event %s for %s", event_id, subject_name)
        return event_id

    async def async_delete_event(self, event_id: str) -> bool:
        """Archive an event by ID (soft-delete). Returns True if found."""
        if not self._loaded:
            await self.async_load()

        for event in self._events:
            if event["id"] == event_id and not event.get("archived"):
                event["archived"] = True
                await self._async_save()
                _LOGGER.debug("Archived event %s", event_id)
                return True
        return False

    @callback
    def get_events_for_subject(
        self,
        subject_name: str,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get events for a specific subject, optionally filtered."""
        result = [
            e for e in self._events
            if e["subject_name"] == subject_name and not e.get("archived")
        ]
        if event_type is not None:
            result = [e for e in result if e["type"] == event_type]
        if since is not None:
            since_iso = since.isoformat()
            result = [e for e in result if e["timestamp"] >= since_iso]
        return result

    @callback
    def get_events_for_date(
        self, subject_name: str, date_str: str, event_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get events for a specific date (YYYY-MM-DD)."""
        prefix = f"{date_str}T"
        result = [
            e for e in self._events
            if e["subject_name"] == subject_name and e["timestamp"].startswith(prefix)
        ]
        if event_type is not None:
            result = [e for e in result if e["type"] == event_type]
        return result

    @callback
    def get_today_events(
        self, subject_name: str, event_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get today's events for a subject."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.get_events_for_date(subject_name, today, event_type)

    @callback
    def get_all_events(self) -> list[dict[str, Any]]:
        """Get all events."""
        return list(self._events)
