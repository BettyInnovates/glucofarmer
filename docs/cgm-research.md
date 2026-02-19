# CGM Multi-Tracker – Datenmodell & Architektur
## Home Assistant Custom Integration – Forschungsdokument

> **Zweck:** Dieses Dokument fasst zusammen, wie führende CGM-Hersteller (Dexcom, Libre) Daten handhaben,
> was das Open-Source-Projekt Nightscout daraus gelernt hat, und leitet daraus konkrete Empfehlungen
> für die eigene Home Assistant Integration ab.

---

## 1. Wie Dexcom Daten intern handhabt

### 1.1 API-Architektur (Dexcom API v3)

Dexcom stellt eine RESTful API bereit, die OAuth 2.0 zur Authentifizierung nutzt.
Daten werden in klar getrennten **Endpunkten** kategorisiert:

| Endpoint | Beschreibung | Einheit |
|---|---|---|
| `/v3/users/self/egvs` | Geschätzte Glukosewerte (CGM-Messung) | mg/dL, mmol/L |
| `/v3/users/self/events` | Manuelle Ereignisse (Mahlzeiten, Insulin, Sport) | g, units, minutes |
| `/v3/users/self/calibrations` | Kalibrierungen (Fingerstich-BZ) | mg/dL, mmol/L |
| `/v3/users/self/alerts` | Alarme (Hoch/Tief) | – |
| `/v3/users/self/devices` | Geräteinformationen | – |
| `/v3/users/self/dataRange` | Verfügbarer Datenzeitraum | – |

### 1.2 Datenpunkte bei manuellen Events

Der `/events`-Endpunkt liefert alle **manuell eingegebenen** Daten:

```json
{
  "eventId": "abc-123",
  "eventType": "carbs",
  "eventStatus": "created",
  "displayTime": "2024-01-15T12:30:00",
  "systemTime": "2024-01-15T11:30:00Z",
  "value": 45,
  "unit": "grams",
  "displayDevice": "iOS"
}
```

**Mögliche `eventType`-Werte:**
- `carbs` – Kohlenhydrataufnahme (g)
- `insulin` – Insulingabe (units)
- `exercise` – Sport (minutes, Intensität)
- `health` – Sonstige Gesundheitsereignisse

**Wichtige Zeitfelder:**
- `systemTime` – UTC-Zeit des Geräts (für Abfragen verwendet)
- `displayTime` – Lokal angezeigte Zeit (hat UTC-Offset wenn von iOS/Android)

**`eventStatus`:**
- `created` – Eintrag wurde erstellt
- `deleted` – Eintrag wurde gelöscht (bleibt erhalten, nur als gelöscht markiert)

> ⚠️ **Soft-Delete-Prinzip:** Dexcom löscht Events nie wirklich aus der Datenbank.
> Ein gelöschter Eintrag bekommt `eventStatus: "deleted"` – das ermöglicht Synchronisation
> ohne Datenverlust.

### 1.3 Glukosewerte (EGV)

```json
{
  "recordId": "xyz-456",
  "systemTime": "2024-01-15T11:25:00Z",
  "displayTime": "2024-01-15T12:25:00",
  "value": 142,
  "status": "high",
  "trend": "flat",
  "trendRate": 0.2,
  "unit": "mg/dL",
  "rateUnit": "mg/dL/min",
  "displayDevice": "iOS",
  "transmitterGeneration": "g7"
}
```

**Trend-Werte:** `none`, `doubleUp`, `singleUp`, `fortyFiveUp`, `flat`, `fortyFiveDown`, `singleDown`, `doubleDown`

**Status-Werte:** `low`, `ok`, `high`

### 1.4 Datenverfügbarkeit & Einschränkungen

- Daten sind mit **1 Stunde Verzögerung** (USA) bzw. **3 Stunden** (EU/Österreich) verfügbar
- Maximales Abfragefenster: **30 Tage**
- Rate Limit: **60.000 Anfragen/Stunde pro App**
- Zeitformat: **ISO 8601**
- Glukose immer in `mg/dL` – Umrechnung zu `mmol/L` ist Aufgabe der Client-App (÷ 18)

---

## 2. Was Nightscout (Open Source) daraus gelernt hat

Nightscout ist das wichtigste Open-Source-Referenzprojekt für CGM-Daten und wird aktiv von der
DIY-Diabetes-Community gepflegt. Es separiert Daten in drei klare Collections:

### 2.1 Nightscout Datenmodell

**Collection 1: `entries` (CGM-Werte)**
```json
{
  "type": "sgv",
  "sgv": 142,
  "direction": "Flat",
  "date": 1705315500000,
  "dateString": "2024-01-15T11:25:00.000Z",
  "device": "dexcom-g7"
}
```

**Collection 2: `treatments` (Manuelle Einträge – das Herzstück)**
```json
{
  "_id": "...",
  "eventType": "Meal Bolus",
  "created_at": "2024-01-15T12:30:00Z",
  "insulin": 3.5,
  "carbs": 45,
  "notes": "Mittagessen",
  "enteredBy": "user"
}
```

**Mögliche `eventType`-Werte in Nightscout:**
- `Meal Bolus` – Mahlzeit + Insulin kombiniert
- `Snack Bolus` – Snack + Insulin
- `Correction Bolus` – Nur Korrekturbolis
- `Carb Correction` – Nur Kohlenhydrate (z.B. Hypo-Behandlung)
- `Temp Basal` – Temporäre Basalrate
- `Exercise` – Sport
- `Note` – Freitext-Notiz
- `Announcement` – Mitteilung

**Collection 3: `profile` (Therapieprofil)**
```json
{
  "dia": 3,
  "carbratio": [{"time": "00:00", "value": 10}],
  "sens": [{"time": "00:00", "value": 50}],
  "basal": [{"time": "00:00", "value": 0.9}],
  "target_low": [{"time": "00:00", "value": 80}],
  "target_high": [{"time": "00:00", "value": 160}]
}
```

### 2.2 Berechnete Werte (IOB / COB)

Nightscout berechnet aus den Treatments laufend:
- **IOB** – Insulin on Board (noch wirksames Insulin im Körper)
- **COB** – Carbs on Board (noch aktive Kohlenhydrate)

Diese werden **nicht gespeichert**, sondern immer neu berechnet aus:
- Insulingaben + `dia` (Insulindauer in Stunden)
- Kohlenhydraten + `carbs_hr` (Verdauungsrate)

---

## 3. Bestehende Home Assistant Integrationen

### 3.1 Offizielle Dexcom Integration (HA)

- Nutzt **Dexcom Share API** (nicht die Developer API)
- Erstellt Sensoren: `sensor.dexcom_USERNAME_glucose_value`, `sensor.dexcom_USERNAME_glucose_trend`
- Attributes: aktueller Wert, Trend, Trend-Rate
- **Kein Support für manuelle Events** (Mahlzeiten, Insulin)
- Verwendet bei ~766 aktiven Installationen

### 3.2 Offizielle Nightscout Integration (HA)

- Liest `sensor.blood_glucose` mit Trend als Icon
- Ebenfalls **keine Unterstützung für manuelle Einträge** über HA

### 3.3 Community-Ansätze

- REST-Integration über Nightscout API (`/api/v1/entries/current.json`)
- Manuelle Konfiguration via `configuration.yaml`
- Keine standardisierte Lösung für mehrere CGMs gleichzeitig

---

## 4. Empfehlungen für die eigene Integration

### 4.1 Datenmodell – Was zu übernehmen ist

Basierend auf der Analyse von Dexcom und Nightscout empfiehlt sich folgendes Modell:

#### A) CGM-Sensor Entitäten (pro CGM-Gerät/Person)

```
sensor.<person>_glucose_value          → aktueller Wert (mg/dL oder mmol/L)
sensor.<person>_glucose_trend          → Trendpfeil (flat, up, down, etc.)
sensor.<person>_glucose_trend_rate     → Änderungsrate (mg/dL/min)
sensor.<person>_sensor_status          → ok / low / high / signal_loss
sensor.<person>_sensor_session_age     → Alter der Sensorverbindung in Stunden
```

#### B) Manuelle Event-Entitäten

```
input_number.<person>_carbs_intake     → Kohlenhydrate in Gramm
input_number.<person>_insulin_dose     → Insulineinheiten
input_select.<person>_insulin_type     → rapid / long / correction
input_text.<person>_meal_note         → Freitext-Notiz
```

#### C) Berechnete Entitäten (optional, aber wertvoll)

```
sensor.<person>_iob                    → Insulin on Board (berechnet)
sensor.<person>_cob                    → Carbs on Board (berechnet)
sensor.<person>_time_in_range          → % Zeit im Zielbereich (letzte 24h)
```

### 4.2 Datenspeicherung – Strategieempfehlung

#### Für CGM-Rohdaten (Glukosewerte)
→ **HA Recorder (SQLite/MariaDB)** ist ausreichend für 10-30 Tage Verlauf.
→ Für Langzeitdaten: **InfluxDB** + Grafana (Standard-Stack für HA Health Monitoring).

#### Für manuelle Einträge (Treatments)
→ Eigene **SQLite-Tabelle** in der Integration (ähnlich wie Nightscout's `treatments` Collection).
→ Alternativ: **JSON-Datei** pro Person in `/config/custom_components/<integration>/data/`.

**Empfohlenes Schema für eine eigene Treatments-Tabelle:**

```sql
CREATE TABLE treatments (
    id          TEXT PRIMARY KEY,          -- UUID
    person_id   TEXT NOT NULL,             -- Welche Person (z.B. "kind1", "erwachsener")
    created_at  TEXT NOT NULL,             -- ISO 8601 UTC
    event_type  TEXT NOT NULL,             -- meal | insulin | exercise | note
    carbs_g     REAL,                      -- Kohlenhydrate in Gramm
    insulin_u   REAL,                      -- Insulineinheiten
    insulin_type TEXT,                     -- rapid | long | correction
    exercise_min INTEGER,                  -- Sport in Minuten
    notes       TEXT,                      -- Freitext
    source      TEXT DEFAULT 'manual',     -- manual | dexcom_sync | libre_sync
    status      TEXT DEFAULT 'created'     -- created | deleted (Soft-Delete!)
);
```

> ✅ **Soft-Delete übernehmen!** Nie wirklich löschen – nur `status = 'deleted'` setzen.
> Das ermöglicht spätere Synchronisation und verhindert Datenverlust.

### 4.3 Event-Typen – Was zu implementieren ist

Basierend auf Dexcom + Nightscout, angepasst für Home Assistant:

| Event Type | Felder | Priorität |
|---|---|---|
| `meal` | `carbs_g`, `notes`, `timestamp` | ⭐ Hoch |
| `insulin` | `insulin_u`, `insulin_type`, `notes`, `timestamp` | ⭐ Hoch |
| `meal_bolus` | `carbs_g`, `insulin_u`, `notes`, `timestamp` | ⭐ Hoch |
| `exercise` | `exercise_min`, `intensity`, `notes`, `timestamp` | ⭐ Mittel |
| `correction` | `insulin_u`, `target_glucose`, `timestamp` | ⭐ Mittel |
| `hypo_treatment` | `carbs_g`, `notes`, `timestamp` | ⭐ Mittel |
| `note` | `notes`, `timestamp` | Niedrig |

### 4.4 Services in Home Assistant

Die Integration sollte folgende **HA-Services** bereitstellen:

```yaml
# Beispiel Service-Aufrufe

cgm_tracker.log_meal:
  person: kind1
  carbs: 45
  notes: "Mittagessen Nudeln"
  timestamp: "2024-01-15T12:30:00"   # optional, Standard: jetzt

cgm_tracker.log_insulin:
  person: kind1
  units: 3.5
  insulin_type: rapid
  notes: "Mahlzeitenbolus"

cgm_tracker.log_exercise:
  person: kind1
  duration_minutes: 45
  intensity: moderate   # light | moderate | intense
```

### 4.5 Zeitstempel – Best Practices

Wie Dexcom zeigt, ist Zeitstempel-Handling kritisch:

```python
# IMMER beide Zeitstempel speichern:
system_time = datetime.utcnow().isoformat() + "Z"   # UTC, für Berechnungen
display_time = datetime.now().isoformat()             # Lokale Zeit, für Anzeige

# ISO 8601 Format: "2024-01-15T12:30:00Z" (UTC)
# Mit Offset:      "2024-01-15T13:30:00+01:00" (Wien)
```

### 4.6 Einheiten

| Messgröße | Speichern als | Anzeigen als | Umrechnung |
|---|---|---|---|
| Glukose | `mg/dL` | `mg/dL` oder `mmol/L` | ÷ 18.0182 |
| Insulin | `units` (IE) | `units` | – |
| Kohlenhydrate | `grams` | `g` | – |
| Sport | `minutes` | `min` | – |
| Trend-Rate | `mg/dL/min` | je nach Einstellung | ÷ 18 |

---

## 5. Architektur-Überblick (für Claude Code)

```
custom_components/
└── cgm_multi_tracker/
    ├── __init__.py
    ├── manifest.json
    ├── config_flow.py          # UI-Konfiguration der Personen + CGM-Quellen
    ├── coordinator.py          # DataUpdateCoordinator (pollt CGM APIs)
    ├── sensor.py               # HA Sensor-Entitäten
    ├── services.py             # Log-Services (meal, insulin, exercise)
    ├── storage.py              # Treatments-Datenbank (SQLite)
    ├── cgm_sources/
    │   ├── dexcom.py           # Dexcom Share API Client
    │   ├── libre.py            # LibreView / LibreLinkUp API Client
    │   └── base.py             # Gemeinsames Interface
    └── data/
        └── treatments.db       # SQLite Datenbank (auto-erstellt)
```

### Datenfluss

```
CGM-Sensor (Hardware)
    ↓ Bluetooth
CGM-App (Dexcom / Libre)
    ↓ Cloud-Upload
CGM-Cloud-API
    ↓ HTTP Poll (alle 5 Min)
coordinator.py (DataUpdateCoordinator)
    ↓ Update
HA-Sensor Entitäten (sensor.kind1_glucose_value, etc.)
    ↓ HA Recorder
SQLite / MariaDB / InfluxDB (Langzeitdaten)

Manuelle Eingabe (HA UI / Service-Aufruf)
    ↓
services.py
    ↓ speichert
treatments.db (SQLite, eigene Tabelle)
    ↓
Berechnete Sensoren (IOB, COB)
```

---

## 6. Sicherheit & Datenschutz

Da es sich um **Gesundheitsdaten** handelt, sind folgende Punkte wichtig:

- **Credentials** (Dexcom/Libre Login) nie im Klartext – HA Secrets (`secrets.yaml`) verwenden
- **Tokens** in HA's eigenem Credential Storage speichern (`hass.auth`)
- **Lokale Daten** bleiben lokal (kein Cloud-Upload aus HA heraus)
- **Backups** regelmäßig (HA Backup schließt `custom_components/` ein)
- Nightscout warnt explizit: ohne HTTPS ist die URL öffentlich – bei HA: nur im lokalen Netz oder via HA Cloud / Nabu Casa

---

## 7. Zusammenfassung – Was übernehmen, was weglassen

### ✅ Übernehmen von Dexcom
- Klare Trennung: EGVs (Messwerte) vs. Events (manuelle Einträge)
- Beide Zeitstempel: `system_time` (UTC) + `display_time` (lokal)
- **Soft-Delete** (nie wirklich löschen, nur als deleted markieren)
- `eventStatus` pro Eintrag
- Einheit immer explizit mitspeichern
- Trend als String-Enum (`flat`, `singleUp`, etc.)

### ✅ Übernehmen von Nightscout
- Trennung in `entries` (CGM) und `treatments` (manuelle Einträge)
- Kombinierten Event `meal_bolus` (Mahlzeit + Insulin in einem)
- Freies Notizfeld bei jedem Eintrag
- `enteredBy`-Feld (Quelle des Eintrags: `manual`, `dexcom_sync`, etc.)
- Konzept von IOB/COB als berechnete Werte

### ❌ Weglassen / Vereinfachen
- Keine OAuth-Implementierung für eigene API nötig (nur Dexcom/Libre-Clients)
- Keine komplexen Therapieprofile (kann einfach in HA-Settings)
- Kein OpenAPS/Loop-Support (zu komplex für HA-Integration)
- Kein eigener Webserver (HA übernimmt das)

---

*Erstellt: 2025 | Quellen: Dexcom Developer API v3, Nightscout GitHub, Home Assistant Integrations Docs*
