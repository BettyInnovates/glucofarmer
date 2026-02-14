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
  dashboard.yaml       -- Lovelace Dashboard (4 Seiten, manuell importieren)
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

## Bekannte Einschraenkungen / TODOs

- TIR-Berechnung basiert auf In-Memory-Tracking (geht bei HA-Neustart verloren)
- Dashboard muss manuell importiert und Entity-IDs angepasst werden
- Kein HACS-Manifest vorhanden (bei Bedarf ergaenzen)
- Keine automatischen Tests vorhanden
- E-Mail-Report nutzt generischen `notify.notify` Service
