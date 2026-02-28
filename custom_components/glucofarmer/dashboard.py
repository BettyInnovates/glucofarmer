"""Auto-generated dashboard for GlucoFarmer.

Creates and updates a Lovelace dashboard automatically based on
configured subject entries. Uses apexcharts-card for glucose charts
with colored threshold zones.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lovelace import dashboard as lovelace_dashboard
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_SUBJECT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Colors for subjects in multi-subject charts
_SUBJECT_COLORS = [
    "#2196F3",
    "#FF9800",
    "#9C27B0",
    "#E91E63",
    "#00BCD4",
    "#795548",
    "#607D8B",
    "#F44336",
]

# Zone colors (symmetric around green)
_COLOR_CRITICAL = "#EF5350"   # rot
_COLOR_VERY_LOW = "#FF9800"   # orange
_COLOR_LOW = "#FFC107"        # gelb
_COLOR_NORMAL = "#4CAF50"     # gruen
_COLOR_HIGH = "#FFC107"       # gelb
_COLOR_VERY_HIGH = "#FF9800"  # orange

# HA gauge uses CSS color names or hex
_GAUGE_CRITICAL = "red"
_GAUGE_VERY_LOW = "orange"
_GAUGE_LOW = "yellow"
_GAUGE_NORMAL = "green"
_GAUGE_HIGH = "yellow"
_GAUGE_VERY_HIGH = "orange"

# Default thresholds (used when hass.data not yet populated)
_DEFAULT_THRESHOLDS = {
    "critical_low": 55,
    "very_low": 100,
    "low": 200,
    "high": 300,
    "very_high": 400,
}


def _get_subject_entities(
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


def _yaxis_max(thresholds: dict[str, Any]) -> int:
    """Return y-axis max rounded up to the next multiple of 50 above very_high."""
    very_high = int(thresholds.get("very_high", 400))
    return ((very_high // 50) + 1) * 50


def _zone_annotations_fill(thresholds: dict[str, Any]) -> list[dict[str, Any]]:
    """Build 6 filled yaxis zone annotations from thresholds."""
    crit = thresholds.get("critical_low", 55)
    very_low = thresholds.get("very_low", 100)
    low = thresholds.get("low", 200)
    high = thresholds.get("high", 300)
    very_high = thresholds.get("very_high", 400)
    chart_max = _yaxis_max(thresholds)

    return [
        {
            "y": 0,
            "y2": crit,
            "fillColor": _COLOR_CRITICAL,
            "opacity": 0.15,
            "label": {
                "text": f"Kritisch (<{int(crit)})",
                "position": "left",
                "textAnchor": "start",
                "offsetX": 5,
                "offsetY": 22,
                "style": {"color": _COLOR_CRITICAL, "background": "transparent"},
            },
        },
        {
            "y": crit,
            "y2": very_low,
            "fillColor": _COLOR_VERY_LOW,
            "opacity": 0.12,
            "label": {
                "text": f"Sehr niedrig (<{int(very_low)})",
                "position": "left",
                "textAnchor": "start",
                "offsetX": 5,
                "offsetY": 18,
                "style": {"color": _COLOR_VERY_LOW, "background": "transparent"},
            },
        },
        {
            "y": very_low,
            "y2": low,
            "fillColor": _COLOR_LOW,
            "opacity": 0.10,
            "label": {
                "text": f"Niedrig (<{int(low)})",
                "position": "left",
                "textAnchor": "start",
                "offsetX": 5,
                "offsetY": 18,
                "style": {"color": _COLOR_LOW, "background": "transparent"},
            },
        },
        {
            "y": low,
            "y2": high,
            "fillColor": _COLOR_NORMAL,
            "opacity": 0.08,
            "label": {
                "text": "Normal",
                "position": "left",
                "textAnchor": "start",
                "offsetX": 5,
                "offsetY": 18,
                "style": {"color": _COLOR_NORMAL, "background": "transparent"},
            },
        },
        {
            "y": high,
            "y2": very_high,
            "fillColor": _COLOR_HIGH,
            "opacity": 0.10,
            "label": {
                "text": f"Hoch (>{int(high)})",
                "position": "left",
                "textAnchor": "start",
                "offsetX": 5,
                "offsetY": 18,
                "style": {"color": _COLOR_HIGH, "background": "transparent"},
            },
        },
        {
            "y": very_high,
            "y2": chart_max,
            "fillColor": _COLOR_VERY_HIGH,
            "opacity": 0.12,
            "label": {
                "text": f"Sehr hoch (>{int(very_high)})",
                "position": "left",
                "textAnchor": "start",
                "offsetX": 5,
                "offsetY": 18,
                "style": {"color": _COLOR_VERY_HIGH, "background": "transparent"},
            },
        },
    ]


def _zone_annotations_lines(thresholds: dict[str, Any]) -> list[dict[str, Any]]:
    """Build 5 horizontal line annotations (zone boundaries) from thresholds."""
    crit = thresholds.get("critical_low", 55)
    very_low = thresholds.get("very_low", 100)
    low = thresholds.get("low", 200)
    high = thresholds.get("high", 300)
    very_high = thresholds.get("very_high", 400)

    return [
        {"y": crit, "borderColor": _COLOR_CRITICAL,
         "label": {"text": f"Kritisch (<{int(crit)})", "position": "left",
                   "textAnchor": "start", "offsetX": 5,
                   "style": {"background": "transparent", "color": _COLOR_CRITICAL}}},
        {"y": very_low, "borderColor": _COLOR_VERY_LOW,
         "label": {"text": f"Sehr niedrig (<{int(very_low)})", "position": "left",
                   "textAnchor": "start", "offsetX": 5,
                   "style": {"background": "transparent", "color": _COLOR_VERY_LOW}}},
        {"y": low, "borderColor": _COLOR_LOW,
         "label": {"text": f"Niedrig (<{int(low)})", "position": "left",
                   "textAnchor": "start", "offsetX": 5,
                   "style": {"background": "transparent", "color": _COLOR_LOW}}},
        {"y": high, "borderColor": _COLOR_HIGH,
         "label": {"text": f"Hoch (>{int(high)})", "position": "left",
                   "textAnchor": "start", "offsetX": 5,
                   "style": {"background": "transparent", "color": _COLOR_HIGH}}},
        {"y": very_high, "borderColor": _COLOR_VERY_HIGH,
         "label": {"text": f"Sehr hoch (>{int(very_high)})", "position": "left",
                   "textAnchor": "start", "offsetX": 5,
                   "style": {"background": "transparent", "color": _COLOR_VERY_HIGH}}},
    ]


def _build_overview_view(
    subjects: list[dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Build the overview view with gauges and apexcharts."""
    crit = thresholds.get("critical_low", 55)
    very_low = thresholds.get("very_low", 100)
    low = thresholds.get("low", 200)
    high = thresholds.get("high", 300)
    very_high = thresholds.get("very_high", 400)
    yaxis_max = _yaxis_max(thresholds)

    cards: list[dict[str, Any]] = []

    # ApexCharts: all subjects in one chart with 6-zone threshold areas
    series = []
    for i, subject in enumerate(subjects):
        entity_id = subject["entities"].get("glucose_value")
        if entity_id:
            series.append({
                "entity": entity_id,
                "name": subject["name"],
                "stroke_width": 2,
                "color": _SUBJECT_COLORS[i % len(_SUBJECT_COLORS)],
            })

    if series:
        cards.append({
            "type": "custom:apexcharts-card",
            "header": {
                "show": True,
                "title": "Glucose-Verlauf (alle Profile)",
                "show_states": True,
            },
            "graph_span": "6h",
            "apex_config": {
                "chart": {"height": 350},
                "legend": {"show": True},
                "yaxis": {
                    "min": 0,
                    "max": yaxis_max,
                    "opposite": True,
                    "tickAmount": yaxis_max // 50,
                    "forceNiceScale": False,
                    "decimalsInFloat": 0,
                },
                "annotations": {
                    "yaxis": _zone_annotations_fill(thresholds),
                },
            },
            "series": series,
        })

    # Per subject: gauge + info
    for subject in subjects:
        ents = subject["entities"]
        subject_cards: list[dict[str, Any]] = [
            {"type": "markdown", "content": f"## {subject['name']}"},
        ]

        row_cards: list[dict[str, Any]] = []
        glucose_entity = ents.get("glucose_value")
        link_status_entity = ents.get("link_status")
        reading_age_entity = ents.get("reading_age")

        if glucose_entity:
            # Gauge: only when sensor has a valid (numeric) reading
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
                    "max": yaxis_max,
                    "needle": True,
                    "segments": [
                        {"from": 0, "color": _GAUGE_CRITICAL, "label": "Kritisch"},
                        {"from": crit, "color": _GAUGE_VERY_LOW, "label": "Sehr niedrig"},
                        {"from": very_low, "color": _GAUGE_LOW, "label": "Niedrig"},
                        {"from": low, "color": _GAUGE_NORMAL, "label": "Normal"},
                        {"from": high, "color": _GAUGE_HIGH, "label": "Hoch"},
                        {"from": very_high, "color": _GAUGE_VERY_HIGH, "label": "Sehr hoch"},
                    ],
                },
            })
            # Warning card when signal is lost
            if link_status_entity:
                row_cards.append({
                    "type": "conditional",
                    "conditions": [
                        {"condition": "state", "entity": link_status_entity, "state": "lost"},
                    ],
                    "card": {
                        "type": "markdown",
                        "content": "## ⚠\n\n**Kein Messwert**\nSensor nicht verfuegbar",
                    },
                })
            else:
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

        # Right column: 4 entities (Glucose, Trend, Since, Coverage)
        status_entities = []
        for key, label in [
            ("glucose_value", "Glucose"),
            ("glucose_trend", "Trend"),
        ]:
            if key in ents:
                status_entities.append({"entity": ents[key], "name": label})

        if reading_age_entity:
            status_entities.append({"entity": reading_age_entity, "name": "Since"})

        comp_today_entity = ents.get("data_completeness_today")
        if comp_today_entity:
            status_entities.append({"entity": comp_today_entity, "name": "Coverage"})

        if status_entities:
            right_column = {"type": "entities", "entities": status_entities}
            row_cards.append(right_column)

        if row_cards:
            subject_cards.append({"type": "horizontal-stack", "cards": row_cards})

        cards.append({"type": "vertical-stack", "cards": subject_cards})

    return {
        "title": "Uebersicht",
        "path": "overview",
        "icon": "mdi:view-dashboard",
        "cards": cards,
    }


def _build_input_view(
    subjects: list[dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Build the input view: mini-graph, status, form buttons, conditional forms, events."""
    yaxis_max = _yaxis_max(thresholds)
    cards: list[dict[str, Any]] = []

    for subject in subjects:
        ents = subject["entities"]
        subject_name = subject["name"]
        subject_cards: list[dict[str, Any]] = [
            {"type": "markdown", "content": f"## {subject_name}"},
        ]

        # 1. Mini graph: last 3h, threshold lines only (no fill)
        glucose_entity = ents.get("glucose_value")
        if glucose_entity:
            subject_cards.append({
                "type": "custom:apexcharts-card",
                "header": {"show": False},
                "graph_span": "3h",
                "apex_config": {
                    "chart": {"height": 150, "toolbar": {"show": False}},
                    "legend": {"show": False},
                    "yaxis": {
                        "min": 0,
                        "max": yaxis_max,
                        "tickAmount": yaxis_max // 50,
                        "forceNiceScale": False,
                        "decimalsInFloat": 0,
                    },
                    "annotations": {
                        "yaxis": _zone_annotations_lines(thresholds),
                    },
                },
                "series": [{
                    "entity": glucose_entity,
                    "name": subject_name,
                    "stroke_width": 2,
                    "color": _SUBJECT_COLORS[0],
                }],
            })

        # 2. Status line
        status_entity = ents.get("glucose_status", "")
        trend_entity = ents.get("glucose_trend", "")
        insulin_entity = ents.get("daily_insulin_total", "")
        bes_entity = ents.get("daily_bes_total", "")

        if glucose_entity:
            subject_cards.append({
                "type": "markdown",
                "content": (
                    f"{{% set val = states('{glucose_entity}') %}}"
                    f"{{% set status = states('{status_entity}') %}}"
                    f"{{% set trend = states('{trend_entity}') %}}"
                    "{% if status in ['critical_low', 'very_high'] %}"
                    "**! Glucose: {{ val }} mg/dL !**"
                    "{% elif status in ['very_low', 'low', 'high'] %}"
                    "**Glucose: {{ val }} mg/dL**"
                    "{% else %}"
                    "Glucose: {{ val }} mg/dL"
                    "{% endif %}"
                    " | Trend: {{ trend }}"
                    f" | Insulin heute: {{{{ states('{insulin_entity}') }}}} IU"
                    f" | BE heute: {{{{ states('{bes_entity}') }}}} BE"
                ),
            })

        # 3. Two form-toggle buttons
        form_mode_entity = ents.get("form_mode")
        if form_mode_entity:
            subject_cards.append({
                "type": "horizontal-stack",
                "cards": [
                    {
                        "type": "button",
                        "name": "🍎 Fuetterung",
                        "tap_action": {
                            "action": "call-service",
                            "service": "select.select_option",
                            "service_data": {
                                "entity_id": form_mode_entity,
                                "option": "feeding",
                            },
                        },
                        "show_state": False,
                    },
                    {
                        "type": "button",
                        "name": "💉 Insulin",
                        "tap_action": {
                            "action": "call-service",
                            "service": "select.select_option",
                            "service_data": {
                                "entity_id": form_mode_entity,
                                "option": "insulin",
                            },
                        },
                        "show_state": False,
                    },
                ],
            })

        # 4. Conditional: feeding form
        meal_entity = ents.get("meal")
        be_entity = ents.get("be_amount")
        minutes_entity = ents.get("minutes_ago")
        log_feeding_entity = ents.get("log_feeding")

        if form_mode_entity and meal_entity and be_entity and minutes_entity:
            feeding_form_entities = []
            feeding_form_entities.append({"entity": meal_entity, "name": "Mahlzeit"})
            feeding_form_entities.append({"entity": be_entity, "name": "BE"})
            feeding_form_entities.append({"entity": minutes_entity, "name": "Vor ___ Minuten"})
            if log_feeding_entity:
                feeding_form_entities.append({
                    "entity": log_feeding_entity,
                    "name": "Speichern",
                    "icon": "mdi:check",
                })
            subject_cards.append({
                "type": "conditional",
                "conditions": [
                    {"condition": "state", "entity": form_mode_entity, "state": "feeding"},
                ],
                "card": {
                    "type": "entities",
                    "title": "Fuetterung",
                    "entities": feeding_form_entities,
                },
            })

        # 5. Conditional: insulin form
        insulin_type_entity = ents.get("insulin_type")
        insulin_units_entity = ents.get("insulin_units")
        log_insulin_entity = ents.get("log_insulin")

        if form_mode_entity and insulin_type_entity and insulin_units_entity:
            insulin_form_entities = []
            insulin_form_entities.append({"entity": insulin_type_entity, "name": "Typ"})
            insulin_form_entities.append({"entity": insulin_units_entity, "name": "IU"})
            if minutes_entity:
                insulin_form_entities.append({"entity": minutes_entity, "name": "Vor ___ Minuten"})
            if log_insulin_entity:
                insulin_form_entities.append({
                    "entity": log_insulin_entity,
                    "name": "Speichern",
                    "icon": "mdi:check",
                })
            subject_cards.append({
                "type": "conditional",
                "conditions": [
                    {"condition": "state", "entity": form_mode_entity, "state": "insulin"},
                ],
                "card": {
                    "type": "entities",
                    "title": "Insulin",
                    "entities": insulin_form_entities,
                },
            })

        # 6. Events (last 24h) -- markdown list, newest first
        events_entity = ents.get("recent_events")
        if events_entity:
            subject_cards.append({
                "type": "markdown",
                "content": (
                    "**Letzte Eintraege (24h)**\n\n"
                    f"{{% set evts = state_attr('{events_entity}', 'events') or [] %}}"
                    "{% if evts | length > 0 %}"
                    "{% for e in evts %}"
                    "{{ e.label }}\n\n"
                    "{% endfor %}"
                    "{% else %}"
                    "_Keine Eintraege in den letzten 24h._"
                    "{% endif %}"
                ),
            })

        cards.append({"type": "vertical-stack", "cards": subject_cards})

    return {
        "title": "Eingabe",
        "path": "input",
        "icon": "mdi:pencil-plus",
        "cards": cards,
    }


def _build_stats_view(
    subjects: list[dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Build the statistics view with 6-zone distribution and charts."""
    very_high = thresholds.get("very_high", 400)
    yaxis_max = _yaxis_max(thresholds)

    cards: list[dict[str, Any]] = []

    # Chart timerange selector (use first subject's entity)
    for subject in subjects:
        if "chart_timerange" in subject["entities"]:
            cards.append({
                "type": "entities",
                "entities": [{
                    "entity": subject["entities"]["chart_timerange"],
                    "name": "Zeitraum",
                }],
            })
            break

    for subject in subjects:
        ents = subject["entities"]
        subject_cards: list[dict[str, Any]] = [
            {"type": "markdown", "content": f"## {subject['name']}"},
        ]

        # 6-zone distribution as donut chart
        zone_series = []
        for key, name, color in [
            ("time_critical_low_pct", "Kritisch niedrig", _COLOR_CRITICAL),
            ("time_very_low_pct", "Sehr niedrig", _COLOR_VERY_LOW),
            ("time_low_pct", "Niedrig", _COLOR_LOW),
            ("time_in_range_pct", "Zielbereich", _COLOR_NORMAL),
            ("time_high_pct", "Hoch", _COLOR_HIGH),
            ("time_very_high_pct", "Sehr hoch", _COLOR_VERY_HIGH),
        ]:
            if key in ents:
                zone_series.append({
                    "entity": ents[key],
                    "name": name,
                    "color": color,
                })

        if zone_series:
            subject_cards.append({
                "type": "custom:apexcharts-card",
                "chart_type": "donut",
                "header": {
                    "show": True,
                    "title": "Zeit im Zielbereich",
                },
                "apex_config": {
                    "chart": {"height": 220},
                    "legend": {"show": True, "position": "bottom"},
                    "dataLabels": {"enabled": True},
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
                detail_entities.append({"entity": comp_range_entity, "name": "Signalabdeckung"})
                detail_entities.append({
                    "type": "attribute",
                    "entity": comp_range_entity,
                    "attribute": "missed_minutes",
                    "name": "Verpasst (min)",
                })

            if detail_entities:
                subject_cards.append({
                    "type": "entities",
                    "title": "Details",
                    "entities": detail_entities,
                })

        # Glucose chart with zoom/pan and 6-zone line annotations
        glucose_entity = ents.get("glucose_value")
        if glucose_entity:
            subject_cards.append({
                "type": "custom:apexcharts-card",
                "header": {
                    "show": True,
                    "title": f"{subject['name']} - Glucose-Verlauf",
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
                    "yaxis": {
                        "min": 0,
                        "max": yaxis_max,
                        "opposite": True,
                        "tickAmount": yaxis_max // 50,
                        "forceNiceScale": False,
                        "decimalsInFloat": 0,
                    },
                    "annotations": {
                        "yaxis": _zone_annotations_lines(thresholds),
                    },
                },
                "series": [{
                    "entity": glucose_entity,
                    "name": subject["name"],
                    "type": "line",
                    "color": "#2196F3",
                    "stroke_width": 2,
                }],
            })

        cards.append({"type": "vertical-stack", "cards": subject_cards})

    return {
        "title": "Statistiken",
        "path": "stats",
        "icon": "mdi:chart-bar",
        "cards": cards,
    }


def _build_settings_view(
    subjects: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the settings view with thresholds and catalog management."""
    cards: list[dict[str, Any]] = []

    # Thresholds only for first subject (global thresholds)
    if subjects:
        ents = subjects[0]["entities"]
        threshold_entities = []
        for key, label in [
            ("critical_low_threshold", "Kritisch niedrig (mg/dL)"),
            ("very_low_threshold", "Sehr niedrig (mg/dL)"),
            ("low_threshold", "Niedrig-Grenze (mg/dL)"),
            ("high_threshold", "Hoch-Grenze (mg/dL)"),
            ("very_high_threshold", "Sehr hoch (mg/dL)"),
            ("data_timeout", "Daten-Timeout (Minuten)"),
        ]:
            if key in ents:
                threshold_entities.append({"entity": ents[key], "name": label})

        if threshold_entities:
            cards.append({
                "type": "entities",
                "title": "Globale Schwellwerte",
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
            "- Subjekt-Profil bearbeiten (Gewicht, Sensor-Zuweisung)\n\n"
            "- Mahlzeiten hinzufuegen/entfernen (fixer BE-Wert oder BE/kg)\n\n"
            "- Insulin-Typen hinzufuegen/entfernen\n\n"
            "- E-Mail-Einstellungen fuer den Tagesbericht"
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
    subject entries are added, removed, or their options change.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return

    # Read current thresholds from shared hass.data (written by coordinator)
    domain_data = hass.data.get(DOMAIN, {})
    thresholds = domain_data.get("thresholds", _DEFAULT_THRESHOLDS)

    # Collect subject data from entity registry
    subjects: list[dict[str, Any]] = []
    for entry in entries:
        if not entry.data.get(CONF_SUBJECT_NAME):
            continue
        entities = _get_subject_entities(hass, entry.entry_id)
        subjects.append({
            "name": entry.data[CONF_SUBJECT_NAME],
            "entry_id": entry.entry_id,
            "entities": entities,
        })

    if not subjects:
        return

    # Build dashboard config
    config = {
        "views": [
            _build_overview_view(subjects, thresholds),
            _build_input_view(subjects, thresholds),
            _build_stats_view(subjects, thresholds),
            _build_settings_view(subjects),
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
        _LOGGER.debug("GlucoFarmer dashboard updated with %d subjects", len(subjects))
    except Exception:
        _LOGGER.exception("Failed to save GlucoFarmer dashboard config")
