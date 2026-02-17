"""Auto-generated dashboard for GlucoFarmer.

Creates and updates a Lovelace dashboard automatically based on
configured pig entries. Uses apexcharts-card for glucose charts
with colored threshold zones.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_PIG_NAME, CONF_PRESETS, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Colors for pigs in multi-pig charts
_PIG_COLORS = [
    "#2196F3",
    "#FF9800",
    "#9C27B0",
    "#E91E63",
    "#00BCD4",
    "#795548",
    "#607D8B",
    "#F44336",
]


def _get_pig_entities(
    hass: HomeAssistant, entry_id: str
) -> dict[str, str]:
    """Map entity keys to actual entity_ids for a config entry."""
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry_id)

    prefix = f"{entry_id}_"
    result: dict[str, str] = {}
    for entity in entities:
        if entity.unique_id and entity.unique_id.startswith(prefix):
            key = entity.unique_id[len(prefix):]
            result[key] = entity.entity_id
    return result


def _build_overview_view(
    pigs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the overview view with gauges and apexcharts."""
    cards: list[dict[str, Any]] = []

    # ApexCharts: all pigs in one chart with colored threshold zones
    series = []
    for i, pig in enumerate(pigs):
        entity_id = pig["entities"].get("glucose_value")
        if entity_id:
            series.append({
                "entity": entity_id,
                "name": pig["name"],
                "stroke_width": 2,
                "color": _PIG_COLORS[i % len(_PIG_COLORS)],
            })

    if series:
        cards.append({
            "type": "custom:apexcharts-card",
            "header": {
                "show": True,
                "title": "Glucose-Verlauf (alle Schweine)",
                "show_states": True,
            },
            "graph_span": "12h",
            "yaxis": [{"min": 20, "max": 350}],
            "apex_config": {
                "chart": {"height": 350},
                "legend": {"show": True},
                "annotations": {
                    "yaxis": [
                        {
                            "y": 0,
                            "y2": 55,
                            "fillColor": "#EF5350",
                            "opacity": 0.12,
                            "label": {
                                "text": "Kritisch niedrig",
                                "style": {"color": "#EF5350"},
                            },
                        },
                        {
                            "y": 55,
                            "y2": 70,
                            "fillColor": "#FF9800",
                            "opacity": 0.12,
                            "label": {
                                "text": "Niedrig",
                                "style": {"color": "#FF9800"},
                            },
                        },
                        {
                            "y": 70,
                            "y2": 180,
                            "fillColor": "#4CAF50",
                            "opacity": 0.08,
                            "label": {
                                "text": "Normal",
                                "style": {"color": "#4CAF50"},
                            },
                        },
                        {
                            "y": 180,
                            "y2": 350,
                            "fillColor": "#FF9800",
                            "opacity": 0.12,
                            "label": {
                                "text": "Hoch",
                                "style": {"color": "#FF9800"},
                            },
                        },
                    ],
                },
            },
            "series": series,
        })

    # Per pig: gauge + current values
    for pig in pigs:
        ents = pig["entities"]
        pig_cards: list[dict[str, Any]] = [
            {"type": "markdown", "content": f"## {pig['name']}"},
        ]

        row_cards: list[dict[str, Any]] = []

        glucose_entity = ents.get("glucose_value")
        if glucose_entity:
            row_cards.append({
                "type": "gauge",
                "entity": glucose_entity,
                "name": "Glucose",
                "unit": "mg/dL",
                "min": 20,
                "max": 350,
                "needle": True,
                "segments": [
                    {"from": 0, "color": "red", "label": "Kritisch"},
                    {"from": 55, "color": "orange", "label": "Niedrig"},
                    {"from": 70, "color": "green", "label": "Normal"},
                    {"from": 180, "color": "orange", "label": "Hoch"},
                    {"from": 250, "color": "red", "label": "Sehr hoch"},
                ],
            })

        status_entities = []
        for key, label in [
            ("glucose_value", "Aktueller Wert"),
            ("glucose_trend", "Trend"),
            ("glucose_status", "Status"),
            ("reading_age", "Datenalter"),
        ]:
            if key in ents:
                status_entities.append({"entity": ents[key], "name": label})

        if status_entities:
            row_cards.append({
                "type": "entities",
                "entities": status_entities,
            })

        if row_cards:
            pig_cards.append({"type": "horizontal-stack", "cards": row_cards})

        cards.append({"type": "vertical-stack", "cards": pig_cards})

    return {
        "title": "Uebersicht",
        "path": "overview",
        "icon": "mdi:view-dashboard",
        "cards": cards,
    }


def _build_input_view(
    pigs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the input view with preset buttons and manual input links."""
    cards: list[dict[str, Any]] = []

    for pig in pigs:
        ents = pig["entities"]
        pig_name = pig["name"]
        pig_cards: list[dict[str, Any]] = [
            {"type": "markdown", "content": f"## {pig_name}"},
        ]

        # Current values as context
        context_entities = []
        for key, label in [
            ("glucose_value", "Glucose"),
            ("glucose_status", "Status"),
            ("daily_insulin_total", "Insulin heute"),
            ("daily_bes_total", "BE heute"),
        ]:
            if key in ents:
                context_entities.append({"entity": ents[key], "name": label})

        if context_entities:
            pig_cards.append({
                "type": "entities",
                "title": "Aktuell",
                "show_header_toggle": False,
                "entities": context_entities,
            })

        # Preset buttons
        preset_keys = sorted(k for k in ents if k.startswith("preset_"))
        if preset_keys:
            pig_cards.append({
                "type": "markdown",
                "content": "### Schnelleingabe",
            })

            button_cards = []
            for key in preset_keys:
                name = key.replace("preset_", "").replace("_", " ").title()
                is_insulin = "insulin" in key or "rapid" in key or "lantus" in key
                icon = "mdi:needle" if is_insulin else "mdi:food-apple"
                button_cards.append({
                    "type": "button",
                    "entity": ents[key],
                    "name": name,
                    "icon": icon,
                    "tap_action": {"action": "toggle"},
                    "show_state": False,
                })

            # Rows of 3
            for i in range(0, len(button_cards), 3):
                pig_cards.append({
                    "type": "horizontal-stack",
                    "cards": button_cards[i:i + 3],
                })

        # Manual input buttons
        pig_cards.append({
            "type": "markdown",
            "content": "### Manuelle Eingabe",
        })
        pig_cards.append({
            "type": "horizontal-stack",
            "cards": [
                {
                    "type": "button",
                    "name": "Insulin loggen",
                    "icon": "mdi:needle",
                    "icon_height": "40px",
                    "tap_action": {
                        "action": "perform-action",
                        "perform_action": "glucofarmer.log_insulin",
                        "data": {"pig_name": pig_name},
                    },
                    "show_state": False,
                },
                {
                    "type": "button",
                    "name": "Fuetterung loggen",
                    "icon": "mdi:food-apple",
                    "icon_height": "40px",
                    "tap_action": {
                        "action": "perform-action",
                        "perform_action": "glucofarmer.log_feeding",
                        "data": {"pig_name": pig_name},
                    },
                    "show_state": False,
                },
                {
                    "type": "button",
                    "name": "Event loeschen",
                    "icon": "mdi:delete",
                    "icon_height": "40px",
                    "tap_action": {
                        "action": "navigate",
                        "navigation_path": "/developer-tools/action",
                    },
                    "show_state": False,
                },
            ],
        })

        cards.append({"type": "vertical-stack", "cards": pig_cards})

    return {
        "title": "Eingabe",
        "path": "input",
        "icon": "mdi:pencil-plus",
        "cards": cards,
    }


def _build_stats_view(
    pigs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the statistics view with TIR gauges and charts."""
    cards: list[dict[str, Any]] = []

    for pig in pigs:
        ents = pig["entities"]
        pig_cards: list[dict[str, Any]] = [
            {"type": "markdown", "content": f"## {pig['name']}"},
        ]

        # TIR / TBR / TAR gauges
        gauge_cards = []
        for key, name, green, yellow, red in [
            ("time_in_range_today", "TIR", 70, 50, 0),
            ("time_below_range_today", "TBR", 0, 5, 10),
            ("time_above_range_today", "TAR", 0, 15, 25),
        ]:
            if key in ents:
                gauge_cards.append({
                    "type": "gauge",
                    "entity": ents[key],
                    "name": name,
                    "unit": "%",
                    "min": 0,
                    "max": 100,
                    "needle": True,
                    "severity": {
                        "green": green,
                        "yellow": yellow,
                        "red": red,
                    },
                })

        if gauge_cards:
            pig_cards.append({"type": "horizontal-stack", "cards": gauge_cards})

        # Completeness + totals
        detail_entities = []
        for key, label in [
            ("data_completeness_today", "Datenvollstaendigkeit"),
            ("daily_insulin_total", "Insulin gesamt (IU)"),
            ("daily_bes_total", "Fuetterung gesamt (BE)"),
        ]:
            if key in ents:
                detail_entities.append({"entity": ents[key], "name": label})

        if detail_entities:
            pig_cards.append({
                "type": "entities",
                "entities": detail_entities,
            })

        # 24h chart per pig
        glucose_entity = ents.get("glucose_value")
        if glucose_entity:
            pig_cards.append({
                "type": "custom:apexcharts-card",
                "header": {
                    "show": True,
                    "title": f"{pig['name']} - 24h Verlauf",
                },
                "graph_span": "24h",
                "yaxis": [{"min": 20, "max": 350}],
                "apex_config": {
                    "chart": {"height": 250},
                    "annotations": {
                        "yaxis": [
                            {"y": 0, "y2": 55, "fillColor": "#EF5350", "opacity": 0.12},
                            {"y": 55, "y2": 70, "fillColor": "#FF9800", "opacity": 0.12},
                            {"y": 70, "y2": 180, "fillColor": "#4CAF50", "opacity": 0.08},
                            {"y": 180, "y2": 350, "fillColor": "#FF9800", "opacity": 0.12},
                        ],
                    },
                },
                "series": [{
                    "entity": glucose_entity,
                    "name": pig["name"],
                    "stroke_width": 2,
                }],
            })

        cards.append({"type": "vertical-stack", "cards": pig_cards})

    return {
        "title": "Statistiken",
        "path": "stats",
        "icon": "mdi:chart-bar",
        "cards": cards,
    }


def _build_settings_view(
    pigs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the settings view with thresholds and catalog management."""
    cards: list[dict[str, Any]] = []

    for pig in pigs:
        ents = pig["entities"]

        threshold_entities = []
        for key, label in [
            ("low_threshold", "Untere Grenze (mg/dL)"),
            ("high_threshold", "Obere Grenze (mg/dL)"),
            ("critical_low_threshold", "Kritisch niedrig (mg/dL)"),
            ("data_timeout", "Daten-Timeout (Minuten)"),
        ]:
            if key in ents:
                threshold_entities.append({"entity": ents[key], "name": label})

        if threshold_entities:
            cards.append({
                "type": "entities",
                "title": f"{pig['name']} - Schwellwerte",
                "show_header_toggle": False,
                "entities": threshold_entities,
            })

    cards.append({
        "type": "markdown",
        "content": (
            "## Kataloge und Presets verwalten\n\n"
            "Insulin-Produkte, Fuetterungskategorien und Presets werden ueber "
            "den **Options Flow** der Integration verwaltet:\n\n"
            "**Einstellungen > Geraete & Dienste > GlucoFarmer > Konfigurieren**"
        ),
    })

    return {
        "title": "Einstellungen",
        "path": "settings",
        "icon": "mdi:cog",
        "cards": cards,
    }


async def async_update_dashboard(hass: HomeAssistant) -> None:
    """Generate and save the GlucoFarmer dashboard automatically.

    Creates the dashboard on first run, then updates it whenever
    pig entries are added, removed, or their options change.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return

    # Collect pig data from entity registry
    pigs: list[dict[str, Any]] = []
    for entry in entries:
        if not entry.data.get(CONF_PIG_NAME):
            continue
        entities = _get_pig_entities(hass, entry.entry_id)
        pigs.append({
            "name": entry.data[CONF_PIG_NAME],
            "entry_id": entry.entry_id,
            "entities": entities,
            "presets": entry.options.get(CONF_PRESETS, []),
        })

    if not pigs:
        return

    # Build dashboard config
    config = {
        "views": [
            _build_overview_view(pigs),
            _build_input_view(pigs),
            _build_stats_view(pigs),
            _build_settings_view(pigs),
        ],
    }

    # Access lovelace component
    lovelace_data = hass.data.get("lovelace")
    if not lovelace_data:
        _LOGGER.debug("Lovelace not available, skipping dashboard update")
        return

    dashboards = lovelace_data.get("dashboards", {})
    collection = lovelace_data.get("dashboards_collection")

    # Create dashboard if it doesn't exist yet
    if "glucofarmer" not in dashboards:
        if collection is None:
            _LOGGER.warning("Cannot create dashboard: lovelace collection unavailable")
            return
        try:
            await collection.async_create_item({
                "url_path": "glucofarmer",
                "title": "GlucoFarmer",
                "icon": "mdi:diabetes",
                "show_in_sidebar": True,
                "require_admin": False,
                "mode": "storage",
            })
        except Exception:
            _LOGGER.exception("Failed to create GlucoFarmer dashboard")
            return
        # Re-fetch after creation
        dashboards = lovelace_data.get("dashboards", {})

    dashboard = dashboards.get("glucofarmer")
    if dashboard is None:
        _LOGGER.warning("GlucoFarmer dashboard not found after creation")
        return

    try:
        await dashboard.async_save(config)
        _LOGGER.debug("GlucoFarmer dashboard updated with %d pigs", len(pigs))
    except Exception:
        _LOGGER.exception("Failed to save GlucoFarmer dashboard config")
