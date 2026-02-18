"""Auto-generated dashboard for GlucoFarmer.

Creates and updates a Lovelace dashboard automatically based on
configured pig entries. Uses apexcharts-card for glucose charts
with colored threshold zones.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lovelace import dashboard as lovelace_dashboard
from homeassistant.components.lovelace.const import LOVELACE_DATA
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

    # ApexCharts: all pigs in one chart with colored 5-zone threshold areas
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
            "graph_span": "6h",
            "yaxis": [{"min": 20, "max": 350, "opposite": False}],
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
                                "position": "left",
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
                                "position": "left",
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
                                "position": "left",
                                "style": {"color": "#4CAF50"},
                            },
                        },
                        {
                            "y": 180,
                            "y2": 250,
                            "fillColor": "#FF9800",
                            "opacity": 0.12,
                            "label": {
                                "text": "Hoch",
                                "position": "left",
                                "style": {"color": "#FF9800"},
                            },
                        },
                        {
                            "y": 250,
                            "y2": 400,
                            "fillColor": "#EF5350",
                            "opacity": 0.12,
                            "label": {
                                "text": "Sehr hoch",
                                "position": "left",
                                "style": {"color": "#EF5350"},
                            },
                        },
                    ],
                },
            },
            "series": series,
        })

    # Per pig: conditional gauge + info
    for pig in pigs:
        ents = pig["entities"]
        pig_cards: list[dict[str, Any]] = [
            {"type": "markdown", "content": f"## {pig['name']}"},
        ]

        row_cards: list[dict[str, Any]] = []
        glucose_entity = ents.get("glucose_value")

        if glucose_entity:
            # Gauge: only when sensor available
            row_cards.append({
                "type": "conditional",
                "conditions": [
                    {"condition": "state", "entity": glucose_entity, "state_not": "unavailable"},
                    {"condition": "state", "entity": glucose_entity, "state_not": "unknown"},
                ],
                "card": {
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
                },
            })
            # Warning symbol when no data
            for no_data_state in ["unavailable", "unknown"]:
                row_cards.append({
                    "type": "conditional",
                    "conditions": [
                        {"condition": "state", "entity": glucose_entity, "state": no_data_state},
                    ],
                    "card": {
                        "type": "markdown",
                        "content": "## ⚠\n\n**Kein Messwert**\nSensor nicht verfuegbar",
                    },
                })

        # Info: Glucose, Trend, Sync + today completeness (integrated)
        status_entities = []
        for key, label in [
            ("glucose_value", "Glucose"),
            ("glucose_trend", "Trend"),
            ("reading_age", "Sync"),
        ]:
            if key in ents:
                status_entities.append({"entity": ents[key], "name": label})

        comp_today_entity = ents.get("data_completeness_today")
        if comp_today_entity:
            status_entities.append({"entity": comp_today_entity, "name": "Coverage"})
            status_entities.append({
                "type": "attribute",
                "entity": comp_today_entity,
                "attribute": "missed",
                "name": "missed",
                "suffix": " today",
            })

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
    """Build the input view with forms, presets, and event management."""
    cards: list[dict[str, Any]] = []

    for pig in pigs:
        ents = pig["entities"]
        pig_name = pig["name"]
        pig_cards: list[dict[str, Any]] = [
            {"type": "markdown", "content": f"## {pig_name}"},
        ]

        # Current status as markdown template (bold for critical values)
        glucose_entity = ents.get("glucose_value", "")
        status_entity = ents.get("glucose_status", "")
        trend_entity = ents.get("glucose_trend", "")
        insulin_entity = ents.get("daily_insulin_total", "")
        bes_entity = ents.get("daily_bes_total", "")

        if glucose_entity:
            pig_cards.append({
                "type": "markdown",
                "content": (
                    f"{{% set val = states('{glucose_entity}') %}}"
                    f"{{% set status = states('{status_entity}') %}}"
                    f"{{% set trend = states('{trend_entity}') %}}"
                    "{% if status in ['critical_low', 'very_high'] %}"
                    "**! Glucose: {{ val }} mg/dL !**"
                    "{% elif status in ['low', 'high'] %}"
                    "**Glucose: {{ val }} mg/dL**"
                    "{% else %}"
                    "Glucose: {{ val }} mg/dL"
                    "{% endif %}"
                    " | Trend: {{ trend }}"
                    f" | Insulin heute: {{{{ states('{insulin_entity}') }}}} IU"
                    f" | BE heute: {{{{ states('{bes_entity}') }}}} BE"
                ),
            })

        # Preset buttons (quick input)
        preset_keys = sorted(k for k in ents if k.startswith("preset_"))
        if preset_keys:
            pig_cards.append({
                "type": "markdown",
                "content": "### Schnelleingabe (Presets)",
            })
            pig_cards.append({
                "type": "markdown",
                "content": (
                    "Presets werden unter **Einstellungen > Geraete & Dienste > "
                    "GlucoFarmer > Konfigurieren** verwaltet."
                ),
            })

            button_cards = []
            for key in preset_keys:
                button_cards.append({
                    "type": "button",
                    "entity": ents[key],
                    "tap_action": {"action": "toggle"},
                    "show_state": False,
                    "show_name": True,
                })

            for i in range(0, len(button_cards), 3):
                pig_cards.append({
                    "type": "horizontal-stack",
                    "cards": button_cards[i:i + 3],
                })

        # Feeding form
        feeding_entities = []
        for key, label in [
            ("feeding_amount", "Menge (BE)"),
            ("feeding_category", "Kategorie"),
            ("event_timestamp", "Zeitstempel (leer = jetzt)"),
        ]:
            if key in ents:
                feeding_entities.append({"entity": ents[key], "name": label})

        if feeding_entities:
            pig_cards.append({"type": "markdown", "content": "### Fuetterung loggen"})
            pig_cards.append({"type": "entities", "entities": feeding_entities})
            if "log_feeding" in ents:
                pig_cards.append({
                    "type": "button",
                    "entity": ents["log_feeding"],
                    "name": "Fuetterung loggen",
                    "icon": "mdi:food-apple-outline",
                    "tap_action": {"action": "toggle"},
                    "show_state": False,
                })

        # Insulin form
        insulin_entities = []
        for key, label in [
            ("insulin_amount", "Menge (IU)"),
            ("insulin_product", "Produkt"),
            ("event_timestamp", "Zeitstempel (leer = jetzt)"),
        ]:
            if key in ents:
                insulin_entities.append({"entity": ents[key], "name": label})

        if insulin_entities:
            pig_cards.append({"type": "markdown", "content": "### Insulin loggen"})
            pig_cards.append({"type": "entities", "entities": insulin_entities})
            if "log_insulin" in ents:
                pig_cards.append({
                    "type": "button",
                    "entity": ents["log_insulin"],
                    "name": "Insulin loggen",
                    "icon": "mdi:needle",
                    "tap_action": {"action": "toggle"},
                    "show_state": False,
                })

        # Today's events list + archive
        events_entity = ents.get("today_events")
        if events_entity:
            pig_cards.append({
                "type": "markdown",
                "content": (
                    "### Letzte Eintraege\n\n"
                    f"{{% set events = state_attr('{events_entity}', 'events') or [] %}}"
                    "{% if events | length > 0 %}"
                    "| Zeit | Typ | Menge | ID |\n"
                    "|------|-----|-------|----|\n"
                    "{% for e in events %}"
                    "| {{ e.timestamp[11:16] if e.timestamp | length > 16 else e.timestamp }}"
                    " | {{ e.type }}"
                    " | {{ e.amount }} {{ 'IU' if e.type == 'insulin' else 'BE' }}"
                    " | `{{ e.id[:8] }}` |\n"
                    "{% endfor %}"
                    "{% else %}"
                    "Keine Eintraege heute."
                    "{% endif %}"
                ),
            })

        # Archive controls
        archive_entities = []
        if "archive_event_id" in ents:
            archive_entities.append({
                "entity": ents["archive_event_id"],
                "name": "Event-ID zum Archivieren",
            })
        if archive_entities:
            pig_cards.append({"type": "entities", "entities": archive_entities})
        if "archive_event" in ents:
            pig_cards.append({
                "type": "button",
                "entity": ents["archive_event"],
                "name": "Event archivieren",
                "icon": "mdi:archive-arrow-down",
                "tap_action": {"action": "toggle"},
                "show_state": False,
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
    """Build the statistics view with 5-zone distribution and charts."""
    cards: list[dict[str, Any]] = []

    # Chart timerange selector (use first pig's entity)
    for pig in pigs:
        if "chart_timerange" in pig["entities"]:
            cards.append({
                "type": "entities",
                "entities": [{
                    "entity": pig["entities"]["chart_timerange"],
                    "name": "Zeitraum",
                }],
            })
            break

    for pig in pigs:
        ents = pig["entities"]
        pig_cards: list[dict[str, Any]] = [
            {"type": "markdown", "content": f"## {pig['name']}"},
        ]

        # 5-zone distribution as stacked horizontal bar chart
        zone_series = []
        for key, name, color in [
            ("time_critical_low_pct", "Kritisch niedrig", "#B71C1C"),
            ("time_low_pct", "Niedrig", "#FF9800"),
            ("time_in_range_pct", "Zielbereich", "#4CAF50"),
            ("time_high_pct", "Hoch", "#FB8C00"),
            ("time_very_high_pct", "Sehr hoch", "#EF5350"),
        ]:
            if key in ents:
                zone_series.append({
                    "entity": ents[key],
                    "name": name,
                    "color": color,
                    "group_by": {"duration": "30min", "func": "last"},
                })

        if zone_series:
            pig_cards.append({
                "type": "custom:apexcharts-card",
                "chart_type": "bar",
                "stacked": True,
                "graph_span": "30min",
                "header": {
                    "show": True,
                    "title": "Zeit im Zielbereich",
                },
                "apex_config": {
                    "chart": {"height": 165},
                    "plotOptions": {
                        "bar": {
                            "horizontal": True,
                            "dataLabels": {"position": "center"},
                        },
                    },
                    "legend": {"show": True, "position": "bottom"},
                    "xaxis": {
                        "max": 100,
                        "labels": {
                            "formatter": "function(val) { return Math.round(val) + '%'; }",
                        },
                    },
                    "yaxis": {"labels": {"show": False}},
                    "dataLabels": {
                        "enabled": True,
                        "formatter": "function(val) { return val > 5 ? Math.round(val) + '%' : ''; }",
                    },
                    "tooltip": {
                        "y": {"formatter": "function(val) { return Math.round(val) + '%'; }"},
                    },
                },
                "series": zone_series,
            })

            # Details: insulin, feeding, completeness
            detail_entities = []
            for key, label in [
                ("daily_insulin_total", "Insulin gesamt"),
                ("daily_bes_total", "Fuetterung gesamt"),
            ]:
                if key in ents:
                    detail_entities.append({"entity": ents[key], "name": label})

            comp_range_entity = ents.get("data_completeness_range")
            if comp_range_entity:
                detail_entities.append({"entity": comp_range_entity, "name": "Vollstaendigkeit"})
                detail_entities.append({
                    "type": "attribute",
                    "entity": comp_range_entity,
                    "attribute": "missed",
                    "name": "Verpasst",
                })

            if detail_entities:
                pig_cards.append({
                    "type": "entities",
                    "title": "Details",
                    "entities": detail_entities,
                })

        # Glucose chart with zoom/pan and 5-zone annotations
        glucose_entity = ents.get("glucose_value")
        if glucose_entity:
            pig_cards.append({
                "type": "custom:apexcharts-card",
                "header": {
                    "show": True,
                    "title": f"{pig['name']} - Glucose-Verlauf",
                },
                "graph_span": "24h",
                "apex_config": {
                    "chart": {
                        "height": 300,
                        "toolbar": {
                            "show": True,
                            "tools": {
                                "download": True,
                                "selection": True,
                                "zoom": True,
                                "zoomin": True,
                                "zoomout": True,
                                "pan": True,
                                "reset": True,
                            },
                        },
                    },
                    "yaxis": [{
                        "min": 20,
                        "max": 350,
                        "opposite": False,
                        "tickAmount": 6,
                        "title": {"text": "mg/dL"},
                    }],
                    "annotations": {
                        "yaxis": [
                            {"y": 55, "borderColor": "#FF0000",
                             "label": {"text": "Kritisch", "position": "left"}},
                            {"y": 70, "borderColor": "#FFA500",
                             "label": {"text": "Niedrig", "position": "left"}},
                            {"y": 180, "borderColor": "#FFA500",
                             "label": {"text": "Hoch", "position": "left"}},
                            {"y": 250, "borderColor": "#FF0000",
                             "label": {"text": "Sehr hoch", "position": "left"}},
                        ],
                    },
                },
                "series": [{
                    "entity": glucose_entity,
                    "name": pig["name"],
                    "type": "line",
                    "color": "#2196F3",
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
            ("critical_low_threshold", "Kritisch niedrig (mg/dL)"),
            ("low_threshold", "Untere Grenze (mg/dL)"),
            ("high_threshold", "Obere Grenze (mg/dL)"),
            ("very_high_threshold", "Sehr hoch (mg/dL)"),
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
            "**Einstellungen > Geraete & Dienste > GlucoFarmer > Konfigurieren**\n\n"
            "Dort kannst du:\n\n"
            "- Insulin-Produkte hinzufuegen/entfernen\n\n"
            "- Fuetterungskategorien hinzufuegen/entfernen\n\n"
            "- Presets erstellen/loeschen (erscheinen als Buttons auf der Eingabe-Seite)"
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

    # Access lovelace component data
    lovelace_data = hass.data.get(LOVELACE_DATA)
    if not lovelace_data:
        _LOGGER.debug("Lovelace not available, skipping dashboard update")
        return

    dashboards = lovelace_data.dashboards

    # Create dashboard if it doesn't exist yet
    if "glucofarmer" not in dashboards:
        dashboards_collection = lovelace_dashboard.DashboardsCollection(hass)
        await dashboards_collection.async_load()
        try:
            await dashboards_collection.async_create_item({
                "url_path": "glucofarmer",
                "allow_single_word": True,
                "title": "GlucoFarmer",
                "icon": "mdi:diabetes",
                "show_in_sidebar": True,
                "require_admin": False,
            })
        except Exception:
            _LOGGER.exception("Failed to create GlucoFarmer dashboard")
            return
        # Re-fetch after creation
        dashboards = lovelace_data.dashboards

    dashboard_config = dashboards.get("glucofarmer")
    if dashboard_config is None:
        _LOGGER.warning("GlucoFarmer dashboard not found after creation")
        return

    try:
        await dashboard_config.async_save(config)
        _LOGGER.debug("GlucoFarmer dashboard updated with %d pigs", len(pigs))
    except Exception:
        _LOGGER.exception("Failed to save GlucoFarmer dashboard config")
