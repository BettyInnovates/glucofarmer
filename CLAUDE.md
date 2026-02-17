# GlucoFarmer - Custom Integration for Home Assistant

## Was ist GlucoFarmer?

Praeklinische Studie mit diabetisierten Schweinen. Mehrere CGMs (Dexcom)
werden gleichzeitig ueberwacht. GlucoFarmer wird als eigenstaendiges
Custom-Component-Plugin installiert und nutzt die Daten der vorhandenen
Dexcom-Integration (die unveraendert bleibt).

## Architektur-Ueberblick

```
custom_components/glucofarmer/
  manifest.json       -- Plugin-Metadaten (domain: glucofarmer, Version 1.0.0)
  __init__.py          -- Setup, Service-Registrierung, Alarm-System, taeglicher Report
  const.py             -- Alle Konstanten, Defaults, Domain
  config_flow.py       -- ConfigFlow (Schwein einrichten) + OptionsFlow (Kataloge, Presets)
  coordinator.py       -- DataUpdateCoordinator: liest Dexcom-Sensoren, berechnet TIR/Stats
  sensor.py            -- 10 Sensor-Entities pro Schwein
  number.py            -- 4 Number-Entities pro Schwein (konfigurierbare Schwellwerte)
  button.py            -- Preset-Buttons (Ein-Klick-Logging)
  store.py             -- Persistente Event-Speicherung via HA Store API
  services.yaml        -- Service-UI-Definitionen
  strings.json         -- Texte fuer Config Flow + Entity-Namen
  icons.json           -- Icons fuer alle Entities
  dashboard.py         -- Auto-generiertes Dashboard (4 Tabs, apexcharts-card)
  dashboard.yaml       -- Statische Referenz (veraltet, wird nicht mehr benoetigt)
```

## Kernkonzepte

### Config Entry = Ein Schwein
Jedes Schwein ist ein eigener Config Entry mit:
- `pig_name`: Name (z.B. "Piggy-01")
- `glucose_sensor`: Entity-ID des Dexcom Glucose-Sensors
- `trend_sensor`: Entity-ID des Dexcom Trend-Sensors

### Globale Kataloge (Options Flow)
Pro Config Entry (Schwein) konfigurierbar:
- **Insulin-Produkte**: Liste mit {name, category (short/long/experimental)}
- **Fuetterungskategorien**: Liste von Strings (breakfast, dinner, reward, etc.)
- **Presets**: Liste mit {name, type (insulin/feeding), product/category, amount}

### Event-Speicherung (store.py)
- Alle Events (Insulin + Fuetterung) in `.storage/glucofarmer_events`
- JSON-Format via `homeassistant.helpers.storage.Store`
- Jedes Event hat UUID, Typ, Schwein, Menge, Zeitstempel, Notiz/Beschreibung

### Entities pro Schwein

**10 Sensoren:**
| Key | Beschreibung | Einheit |
|-----|-------------|---------|
| `glucose_value` | Aktueller Wert vom Dexcom | mg/dL |
| `glucose_trend` | Trend (ENUM: rising_quickly..falling_quickly) | - |
| `glucose_status` | Status (ENUM: normal/low/high/critical_low/no_data) | - |
| `reading_age` | Minuten seit letzter Messung | min |
| `time_in_range_today` | TIR % | % |
| `time_below_range_today` | TBR % | % |
| `time_above_range_today` | TAR % | % |
| `data_completeness_today` | Datenvollstaendigkeit | % |
| `daily_insulin_total` | Gesamt-IE heute | IU |
| `daily_bes_total` | Gesamt-BE heute | BE |

**4 Number-Entities (Schwellwerte):**
| Key | Default | Bereich |
|-----|---------|---------|
| `low_threshold` | 70 mg/dL | 40-100 |
| `high_threshold` | 180 mg/dL | 120-300 |
| `critical_low_threshold` | 55 mg/dL | 20-70 |
| `data_timeout` | 20 min | 5-120 |

**Button-Entities:** Pro Preset ein Button

### Services
- `glucofarmer.log_insulin` -- Schwein, Produkt, Menge (IU), opt. Zeitstempel, opt. Notiz
- `glucofarmer.log_feeding` -- Schwein, Menge (BE), Kategorie, opt. Beschreibung, opt. Zeitstempel
- `glucofarmer.delete_event` -- Event-ID (UUID)

### Alarm-System (__init__.py)
- Critical low: sofort, priority=critical (durchbricht DND)
- Low: sofort, priority=high
- High: 5 Minuten Verzoegerung
- No data: bei Timeout
- Reset + Recovery-Benachrichtigung bei Rueckkehr zu normal

### Taeglicher Report (__init__.py)
- Prueft jede Minute ob Mitternacht (00:00-00:01)
- Sendet pro Schwein: Werte, TIR/TBR/TAR, Completeness, Summen
- Hebt Notfallrationen und Interventionen hervor
- Geht an `notify.notify` + persistent_notification

## Datenfluss

```
Dexcom-Sensor (HA) ──> Coordinator (60s Polling) ──> Sensor-Entities
                                │
                                ├──> Status-Berechnung (Schwellwerte aus Number-Entities)
                                ├──> TIR/TBR/TAR (In-Memory-Tracking, Reset um Mitternacht)
                                ├──> Tages-Summen (aus Store)
                                └──> Alarm-Check (Listener auf Coordinator)

Service-Aufrufe ──> Store (persistent JSON) ──> Coordinator-Refresh ──> Sensor-Update
Button-Press ──> Store ──> Coordinator-Refresh ──> Sensor-Update
```

## Entwicklung

### Voraussetzungen
- Home Assistant Core Dev-Umgebung oder laufende HA-Instanz
- Python 3.13+
- Dexcom-Integration muss installiert sein

### Installation zum Testen
```bash
# In laufende HA-Instanz kopieren:
cp -r custom_components/glucofarmer /config/custom_components/
# HA neu starten
# Einstellungen > Geraete & Dienste > Integration hinzufuegen > GlucoFarmer
```

### Dashboard importieren
1. Einstellungen > Dashboards > Dashboard hinzufuegen > Name: "GlucoFarmer"
2. Dashboard oeffnen > Drei-Punkte > Raw-Konfigurationseditor
3. Inhalt von `dashboard.yaml` einfuegen
4. Entity-IDs anpassen (`piggy_01` durch tatsaechlichen Schweinenamen ersetzen)

## Deployment

- GitHub-Repo ist eingerichtet, HACS Custom Repository ist konfiguriert
- Workflow: Lokal aendern > git commit > git push > HACS Redownload > HA neu starten
- Projekt lebt unter `/home/mub/projects/glucofarmer/`
- NICHT in ha-core arbeiten (dort liegt eine veraltete Kopie unter custom_components/)

## Changelog

### v1.2.0 (17.02.2026)
Persistente Glucose-Speicherung + retrospektive Statistik:
- **store.py: Glucose-Readings persistent** -- Alle Messwerte werden dauerhaft in
  `.storage/glucofarmer_events` gespeichert (Format: `{pig_name, value, status, timestamp}`).
  Neue Methoden: `async_log_reading`, `get_readings_for_date`, `get_readings_for_range`,
  `get_readings_today`, `async_flush_readings`. Batch-Save alle 10 Readings fuer weniger I/O.
- **coordinator.py: Weg von In-Memory** -- `_readings_today` und `_last_reset_date` entfernt.
  `_track_reading` schreibt jetzt in den persistenten Store. `_compute_tir()` und
  `_compute_data_completeness()` lesen aus `store.get_readings_today()`.
  Deduplication via `_last_tracked_sensor_changed` bleibt erhalten.
- **__init__.py: Daily Report retrospektiv** -- `_send_daily_report` berechnet alle Stats
  (TIR/TBR/TAR/Completeness/Insulin/BE) aus dem Store fuer den Vortag. Kein Zugriff
  mehr auf coordinator.data fuer Statistik. Flush vor Report-Generierung.
- **__init__.py: Readings-Flush bei Shutdown** -- `async_unload_entry` flusht
  gepufferte Readings bevor HA herunterfaehrt.
- **Daten ueberleben HA-Neustarts** -- Alle Glucose-Werte und Events persistent.
- **Beliebige Zeitbereiche abfragbar** -- `get_readings_for_range(pig, start, end)`
  ermoeglicht Dashboard-Queries ueber beliebige Zeitraeume.

### v1.1.0 (17.02.2026)
Auto-generiertes dynamisches Dashboard:
- **Neues File: `dashboard.py`** -- Generiert Lovelace Dashboard automatisch
  basierend auf konfigurierten Schweinen. Verwendet HA Lovelace Storage API.
- **Dashboard wird automatisch erstellt** beim ersten Setup (erscheint in Sidebar)
- **Dashboard aktualisiert sich** bei Schwein hinzufuegen/entfernen und Options-Aenderungen
- **4 Tabs**: Uebersicht, Eingabe, Statistiken, Einstellungen (als echte Reiter)
- **ApexCharts Integration**: Glucose-Verlauf mit farbigen Schwellwert-Zonen
  (rot=kritisch, orange=niedrig/hoch, gruen=normal), alle Schweine in einem Chart
- **Entity-IDs dynamisch** aus Entity Registry ermittelt (kein Hardcoding)
- **Eingabe-Seite**: Preset-Buttons + manuelle Service-Buttons pro Schwein
- Altes statisches `dashboard.yaml` bleibt als Referenz erhalten

### v1.0.2 (16.02.2026)
Bugfixes TIR/Completeness und Benachrichtigungen:
- **Fix: TIR-Berechnung zaehlte jeden 60s-Poll statt echte Dexcom-Readings** --
  `_track_reading` in `coordinator.py` prueft jetzt `last_changed` des Sensors und
  zaehlt nur neue Dexcom-Werte (alle ~5 Min). Neues Feld `_last_tracked_sensor_changed`.
- **Fix: Datenvollstaendigkeit war immer ~100%** -- Gleiche Ursache, durch Deduplizierung
  jetzt korrekt (echte Readings / erwartete Readings).
- **Fix: "None minutes" in Datenausfall-Benachrichtigung** -- `_check_alarms` in
  `__init__.py` behandelt `reading_age_minutes=None` jetzt mit Fallback-Text.
- **Fix: Taeglicher Report ueberschrieb sich** -- `notification_id` enthaelt jetzt
  das Datum, alte Reports bleiben erhalten.

### v1.0.1 (14.02.2026)
Bugfixes nach erstem Live-Test:
- **Fix: `STATUS_NORMAL` Import fehlte** in `__init__.py` -- Alarm-Listener crashte
  bei jedem Coordinator-Update, blockierte Wert-Aktualisierung
- **Fix: `hass.components` API entfernt** -- `persistent_notification.async_create()`
  umgestellt auf `hass.services.async_call()` (2 Stellen: `_send_notification` +
  `_send_daily_report`)
- **Fix: Thread-Safety bei Timer-Callback** -- Lambda mit `hass.async_create_task`
  ersetzt durch async Callback-Funktion `_daily_report_callback`

### v1.0.0 (14.02.2026)
Initiale Implementation aller 11 Schritte.

### v1.2.1 (17.02.2026)
Bugfix Dashboard-Erstellung (LovelaceData API):
- **Fix: `AttributeError: 'LovelaceData' object has no attribute 'get'`** --
  `dashboard.py:async_update_dashboard` behandelte `LovelaceData` wie ein Dict.
  `LovelaceData` ist ein Dataclass (definiert in `homeassistant.components.lovelace`).
  - `hass.data.get("lovelace")` → `hass.data.get(LOVELACE_DATA)` (typsicherer HassKey)
  - `lovelace_data.get("dashboards")` → `lovelace_data.dashboards` (Attribut-Zugriff)
  - `lovelace_data.get("dashboards_collection")` existiert nicht auf LovelaceData →
    Eigene `DashboardsCollection` instanziieren + `async_load()` (wie HA intern)
  - `allow_single_word: True` noetig weil "glucofarmer" keinen Bindestrich hat

## OFFENE AENDERUNGEN (noch nicht committed/deployed)

### Bereits im Code aber noch nicht gepusht:
- v1.0.2 Bugfixes -- GEPUSHT UND DEPLOYED
- v1.1.0 dashboard.py (auto-generiert) -- GEPUSHT, Dashboard-Bug gefixt in v1.2.1
- v1.2.0 Persistente Glucose-Speicherung -- GEPUSHT
- v1.2.1 LovelaceData-Fix in dashboard.py -- IM CODE, NOCH NICHT COMMITTED

## Wichtige HA-Interna (Referenz fuer zukuenftige Aenderungen)

### LovelaceData Zugriff
`LovelaceData` ist ein Dataclass, KEIN Dict. Zugriff:
```python
from homeassistant.components.lovelace import dashboard as lovelace_dashboard
from homeassistant.components.lovelace.const import LOVELACE_DATA

lovelace_data = hass.data.get(LOVELACE_DATA)       # typisierter Key
dashboards = lovelace_data.dashboards               # dict[str|None, LovelaceConfig]
lovelace_data.resources                             # ResourceCollection
lovelace_data.yaml_dashboards                       # dict fuer YAML-Dashboards
```
Dashboard erstellen (kein `dashboards_collection` auf LovelaceData!):
```python
coll = lovelace_dashboard.DashboardsCollection(hass)
await coll.async_load()
await coll.async_create_item({"url_path": "x", "allow_single_word": True, "title": "X", ...})
dashboard_config = lovelace_data.dashboards["x"]
await dashboard_config.async_save(config_dict)
```

## Bekannte Einschraenkungen / TODOs

- Dashboard benoetigt `apexcharts-card` aus HACS (Frontend) fuer Glucose-Charts
- Keine automatischen Tests vorhanden
- E-Mail-Report nutzt generischen `notify.notify` Service
- Manuelle Eingabe auf Eingabe-Seite fuehrt zu Developer Tools (kein Inline-Formular)
