# GlucoFarmer Changelog

## v1.3.0 (17.02.2026)
5-Zonen-System, Inline-Eingabe, variable Chart-Zeitraeume:
- **5-Zonen-Glucose-System** -- Altes 3-Zonen-Modell (TIR/TBR/TAR) ersetzt durch 5 Zonen:
  critical_low, low, in_range, high, very_high. Neue Sensoren: `time_critical_low_pct`,
  `time_low_pct`, `time_in_range_pct`, `time_high_pct`, `time_very_high_pct`.
  Neuer Schwellwert: `very_high_threshold` (Default 250 mg/dL).
  Status-ENUM erweitert um `very_high`.
- **Inline-Eingabe statt Developer Tools** -- Fuetterung und Insulin koennen jetzt
  direkt im Dashboard eingegeben werden ueber Number/Select/Text Entities + Aktions-Buttons.
  Neue Entities: `feeding_amount`, `insulin_amount` (Number), `feeding_category`,
  `insulin_product` (Select), `event_timestamp`, `archive_event_id` (Text),
  `log_feeding`, `log_insulin`, `archive_event` (Button).
- **Neue Plattformen: select.py, text.py** -- Select-Entities fuer Kategorien/Produkte/Zeitraum,
  Text-Entities fuer Zeitstempel und Event-ID Eingabe.
- **Event-Archivierung (Soft-Delete)** -- `store.async_delete_event` setzt jetzt
  `archived: True` statt Event zu loeschen. `get_events_for_pig` filtert archivierte Events.
  Neuer `today_events` Sensor zeigt heutige Events mit Attribut `events` (Liste).
- **Variable Chart-Zeitraeume** -- Select-Entity `chart_timerange` (3h/6h/12h/24h) steuert
  den Zeitraum fuer Zonen-Statistiken. Wert wird ueber `hass.data[DOMAIN]["chart_timerange"]`
  geteilt. Coordinator berechnet Zonen-Stats fuer den gewaehlten Zeitraum.
- **Dashboard komplett ueberarbeitet** -- Seite 1: Conditional Gauge (kein Crash bei
  unavailable), 5-Zonen-Annotationen. Seite 2: Inline-Formulare fuer Fuetterung/Insulin,
  Events-Tabelle mit Archiv-Funktion. Seite 3: Zeitraum-Selektor, 5-Zonen-Verteilung
  mit Emoji-Anzeige, apexcharts mit Zoom/Pan Toolbar. Seite 4: Alle 5 Schwellwerte.
- **Alarm-System erweitert** -- `very_high` Status wird jetzt erkannt und loest Alarm
  mit priority=critical aus (wie critical_low).
- **Taeglicher Report auf 5 Zonen** -- Report zeigt jetzt alle 5 Zonen mit
  Prozentwerten und die aktuell konfigurierten Schwellwerte pro Schwein.
- **dashboard.yaml aktualisiert** -- Statische Referenz auf v1.3.0 Stand gebracht.

## v1.2.1 (17.02.2026)
Bugfix Dashboard-Erstellung (LovelaceData API):
- **Fix: `AttributeError: 'LovelaceData' object has no attribute 'get'`** --
  `dashboard.py:async_update_dashboard` behandelte `LovelaceData` wie ein Dict.
  `LovelaceData` ist ein Dataclass (definiert in `homeassistant.components.lovelace`).
  - `hass.data.get("lovelace")` -> `hass.data.get(LOVELACE_DATA)` (typsicherer HassKey)
  - `lovelace_data.get("dashboards")` -> `lovelace_data.dashboards` (Attribut-Zugriff)
  - `lovelace_data.get("dashboards_collection")` existiert nicht auf LovelaceData ->
    Eigene `DashboardsCollection` instanziieren + `async_load()` (wie HA intern)
  - `allow_single_word: True` noetig weil "glucofarmer" keinen Bindestrich hat

## v1.2.0 (17.02.2026)
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

## v1.1.0 (17.02.2026)
Auto-generiertes dynamisches Dashboard:
- **Neues File: `dashboard.py`** -- Generiert Lovelace Dashboard automatisch
  basierend auf konfigurierten Schweinen. Verwendet HA Lovelace Storage API.
- **Dashboard wird automatisch erstellt** beim ersten Setup (erscheint in Sidebar)
- **Dashboard aktualisiert sich** bei Schwein hinzufuegen/entfernen und Options-Aenderungen
- **4 Tabs**: Uebersicht, Eingabe, Statistiken, Einstellungen (als echte Reiter)
- **ApexCharts Integration**: Glucose-Verlauf mit farbigen Schwellwert-Zonen
- **Entity-IDs dynamisch** aus Entity Registry ermittelt (kein Hardcoding)

## v1.0.2 (16.02.2026)
Bugfixes TIR/Completeness und Benachrichtigungen:
- **Fix: TIR-Berechnung zaehlte jeden 60s-Poll statt echte Dexcom-Readings** --
  `_track_reading` prueft jetzt `last_changed` des Sensors und zaehlt nur neue Werte.
- **Fix: Datenvollstaendigkeit war immer ~100%** -- Gleiche Ursache, durch Deduplizierung korrigiert.
- **Fix: "None minutes" in Datenausfall-Benachrichtigung** -- Fallback-Text bei `reading_age_minutes=None`.
- **Fix: Taeglicher Report ueberschrieb sich** -- `notification_id` enthaelt jetzt das Datum.

## v1.0.1 (14.02.2026)
Bugfixes nach erstem Live-Test:
- **Fix: `STATUS_NORMAL` Import fehlte** in `__init__.py`
- **Fix: `hass.components` API entfernt** -- umgestellt auf `hass.services.async_call()`
- **Fix: Thread-Safety bei Timer-Callback** -- async Callback statt Lambda

## v1.0.0 (14.02.2026)
Initiale Implementation.
