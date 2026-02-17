# GlucoFarmer Architektur

## Dateien

```
custom_components/glucofarmer/
  manifest.json       -- Plugin-Metadaten (domain: glucofarmer)
  __init__.py          -- Setup, Service-Registrierung, Alarm-System, taeglicher Report
  const.py             -- Alle Konstanten, Defaults, Domain
  config_flow.py       -- ConfigFlow (Schwein einrichten) + OptionsFlow (Kataloge, Presets)
  coordinator.py       -- DataUpdateCoordinator: liest Dexcom-Sensoren, berechnet 5-Zonen-Stats
  sensor.py            -- 12 Sensor-Entities pro Schwein (inkl. 5-Zonen + Events)
  number.py            -- 7 Number-Entities pro Schwein (Schwellwerte + Eingabefelder)
  button.py            -- Preset-Buttons + Aktions-Buttons (Fuetterung/Insulin/Archiv)
  select.py            -- 3 Select-Entities (Fuetterungskategorie, Insulin-Produkt, Chart-Zeitraum)
  text.py              -- 2 Text-Entities (Event-Zeitstempel, Archiv-Event-ID)
  store.py             -- Persistente Event- und Readings-Speicherung via HA Store API
  services.yaml        -- Service-UI-Definitionen
  strings.json         -- Texte fuer Config Flow + Entity-Namen
  icons.json           -- Icons fuer alle Entities
  dashboard.py         -- Auto-generiertes Dashboard (4 Tabs, apexcharts-card)
  dashboard.yaml       -- Statische Referenz (nur fuer manuelles Setup)
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
- Events + Readings in `.storage/glucofarmer_events`
- JSON-Format via `homeassistant.helpers.storage.Store`
- Events: UUID, Typ, Schwein, Menge, Zeitstempel, Notiz; Soft-Delete (archived flag)
- Readings: pig_name, value, status, timestamp; Batch-Save alle 10 Readings

## Entities pro Schwein

**12 Sensoren:**
| Key | Beschreibung | Einheit |
|-----|-------------|---------|
| `glucose_value` | Aktueller Wert vom Dexcom | mg/dL |
| `glucose_trend` | Trend (ENUM: rising_quickly..falling_quickly) | - |
| `glucose_status` | Status (ENUM: normal/low/high/very_high/critical_low/no_data) | - |
| `reading_age` | Minuten seit letzter Messung | min |
| `time_critical_low_pct` | Zeit < critical_low Schwelle | % |
| `time_low_pct` | Zeit critical_low..low Schwelle | % |
| `time_in_range_pct` | Zeit im Zielbereich (low..high) | % |
| `time_high_pct` | Zeit high..very_high Schwelle | % |
| `time_very_high_pct` | Zeit > very_high Schwelle | % |
| `data_completeness_today` | Datenvollstaendigkeit | % |
| `daily_insulin_total` | Gesamt-IE heute | IU |
| `daily_bes_total` | Gesamt-BE heute | BE |
| `today_events` | Heutige Events (attr: events-Liste) | - |

**7 Number-Entities:**
| Key | Default | Bereich | Kategorie |
|-----|---------|---------|-----------|
| `critical_low_threshold` | 55 mg/dL | 20-70 | CONFIG |
| `low_threshold` | 70 mg/dL | 40-100 | CONFIG |
| `high_threshold` | 180 mg/dL | 120-300 | CONFIG |
| `very_high_threshold` | 250 mg/dL | 200-400 | CONFIG |
| `data_timeout` | 20 min | 5-120 | CONFIG |
| `feeding_amount` | 0 BE | 0-50 | - |
| `insulin_amount` | 0 IU | 0-100 | - |

**3 Select-Entities:**
| Key | Beschreibung |
|-----|-------------|
| `feeding_category` | Fuetterungskategorie (aus Options Flow) |
| `insulin_product` | Insulin-Produkt (aus Options Flow) |
| `chart_timerange` | Chart-Zeitraum (3h/6h/12h/24h) |

**2 Text-Entities:**
| Key | Beschreibung |
|-----|-------------|
| `event_timestamp` | Optionaler Zeitstempel fuer Eingabe (leer = jetzt) |
| `archive_event_id` | Event-ID zum Archivieren |

**3 Aktions-Buttons:**
| Key | Beschreibung |
|-----|-------------|
| `log_feeding` | Fuetterung loggen (liest feeding_amount/category/timestamp) |
| `log_insulin` | Insulin loggen (liest insulin_amount/product/timestamp) |
| `archive_event` | Event archivieren (liest archive_event_id) |

**Preset-Buttons:** Pro Preset ein Button (Ein-Klick-Logging)

## Services

- `glucofarmer.log_insulin` -- Schwein, Produkt, Menge (IU), opt. Zeitstempel, opt. Notiz
- `glucofarmer.log_feeding` -- Schwein, Menge (BE), Kategorie, opt. Beschreibung, opt. Zeitstempel
- `glucofarmer.delete_event` -- Event-ID (UUID)

## Alarm-System (__init__.py)

- Critical low: sofort, priority=critical (durchbricht DND)
- Low: sofort, priority=high
- High / Very high: 5 Min Verzoegerung (very_high: priority=critical, high: priority=high)
- No data: bei Timeout
- Reset + Recovery-Benachrichtigung bei Rueckkehr zu normal

## Taeglicher Report (__init__.py)

- Prueft jede Minute ob Mitternacht (00:00-00:01)
- Sendet pro Schwein: Werte, 5-Zonen-Verteilung mit Schwellwerten, Completeness, Summen
- Hebt Notfallrationen und Interventionen hervor
- Geht an `notify.notify` + persistent_notification

## Datenfluss

```
Dexcom-Sensor (HA) ──> Coordinator (60s Polling) ──> Sensor-Entities
                                │
                                ├──> Status-Berechnung (4 Schwellwerte aus Number-Entities)
                                ├──> 5-Zonen-Stats (aus persistentem Store, aktueller Zeitraum)
                                ├──> Tages-Summen (aus Store)
                                ├──> Today-Events (aus Store, nicht-archivierte)
                                └──> Alarm-Check (Listener auf Coordinator)

Service-Aufrufe ──> Store (persistent JSON) ──> Coordinator-Refresh ──> Sensor-Update
Preset-Button ──> Store ──> Coordinator-Refresh ──> Sensor-Update
Aktions-Button ──> liest Number/Select/Text Entities ──> Store ──> Coordinator-Refresh

Dashboard-Eingabe:
  Number (Menge) + Select (Kategorie/Produkt) + Text (Zeitstempel)
    ──> Aktions-Button (log_feeding/log_insulin) ──> Store

Chart-Zeitraum:
  Select (chart_timerange) ──> hass.data[DOMAIN]["chart_timerange"]
    ──> Coordinator._get_chart_timerange() ──> _compute_zone_stats(hours)
```

## Entwicklung

### Voraussetzungen
- Home Assistant Core Dev-Umgebung oder laufende HA-Instanz
- Python 3.13+
- Dexcom-Integration muss installiert sein

### Installation zum Testen
```bash
cp -r custom_components/glucofarmer /config/custom_components/
# HA neu starten
# Einstellungen > Geraete & Dienste > Integration hinzufuegen > GlucoFarmer
```

### Dashboard
Das Dashboard wird automatisch von `dashboard.py` erstellt und aktualisiert.
Fuer manuelles Setup: `dashboard.yaml` als Referenz (siehe Kommentare darin).
