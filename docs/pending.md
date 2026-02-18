# Pending Documentation Updates

Gesammelte Aenderungen fuer architecture.md und ha-internals.md.
Werden bei Gelegenheit (Milestone, Deploy) eingearbeitet und dann geleert.

---

## Stand: 18.02.2026

### Was in dieser Session gemacht wurde (v1.3.6 bis v1.3.14)

- v1.3.6: Completeness Seite 1/3 getauscht (today/range), in Entities-Card integriert
- v1.3.7: _last_valid_reading_time nach HA-Neustart aus Store wiederherstellen
- v1.3.8: Preset Config Flow mit HA-Selectors (TextSelector/SelectSelector/NumberSelector)
- v1.3.9: async_refresh() statt async_request_refresh() in allen Buttons
- v1.3.10: translations/en.json + translations/de.json erstellt (HA laedt aus translations/)
- v1.3.11: Achtung-Symbol wenn kein Sensor-Wert, Threshold-Fussnote Seite 3, Graph 6h
- v1.3.12: Coordinator-Polling 60s (war 5min, zu langsam nach Neustart)
- v1.3.13: Sync ganzzahlig, Coverage/missed-Label, Y-Achse links (noch nicht committed)
- v1.3.14: Stacked Bar Chart Seite 3, Threshold-Fussnote entfernt (noch nicht committed)

---

## Offene Bugs

### A. Coverage/missed: expected zaehlt ab Mitternacht, nicht ab erstem Reading
- expected = minutes_since_midnight / 5 (immer ab 00:00)
- actual = Readings im Store seit 00:00 UTC (timezone-mismatch moeglich!)
- Verdacht: missed erscheint zu hoch wenn Integration nicht seit Mitternacht laeuft
- Pruefen: actual * Laufzeit-Stunden * 12 -- stimmt das ueberein?
- Timezone-Problem: UTC-Timestamps im Store vs. naive Localtime in expected-Berechnung
  (Readings von 00:00-01:00 local/CET haben UTC-Datum von gestern -> werden nicht gezaehlt)
- Design-Frage: expected ab Mitternacht ODER ab erstem gespeicherten Reading heute?
- User beobachtet und meldet zurueck

### B. Preset-Logik hat noch Fehler
- Config Flow rendert jetzt korrekt (v1.3.8+v1.3.10)
- Aber Preset-Verhalten beim Anlegen/Verwenden hat noch logische Fehler
- Wird bei Seite-2-Ueberarbeitung gemeinsam mit neuem Layout besprochen und gefixt

---

## Naechste Schritte (Prioritaet)

### SOFORT: v1.3.13 committen
Commit-Message steht in CLAUDE.md bereit.

### 1. Seite 2 besprechen (MUSS besprochen werden vor Implementierung)
Geplante Aenderungen laut frueherer Diskussion:
- Layout: Graph oben (Uebersicht Schwein) + Buttons darunter
- Workflow: Button sichtbar -> nach Klick Formular einblenden
- Presets + manuelle Eingabe beide moeglich
- Zeitstempel: default=jetzt, Option "vor X min"
- BE/Insulin: summieren (nicht ueberschreiben), getrennt pro Typ
- Loeschen: Soft-Delete mit Sicherheitsabfrage; Admin-Ansicht fuer geloeschte Events
- Events nach Mitternacht duerfen nicht verschwinden (Bug)
- Preset-Logik Fehler hier mitfixen

### 2. ~~Seite 3: Stacked Balkendiagramm~~ -- DONE (v1.3.14)
- Umgesetzt als horizontal gestapeltes Balkendiagramm in apexcharts-card
- chart_type: bar, stacked: true, graph_span: 30min, group_by last
- Threshold-Fussnote entfernt (war zu ueberladen)
- IDEE fuer spaeter: kleine Schwellwert-Zahlen links am Balken anzeigen
  (statt Fussnote; erst entscheiden wenn User Diagramm gesehen hat)

### 3. Sync-Anzeige Echtzeit (Claude kann selbststaendig)
- reading_age friert zwischen Coordinator-Refreshes ein
- Fix: Dashboard-Template mit last_changed(dexcom_entity_id) + now()
- Nur dashboard.py aendern, kein Coordinator-Change noetig
- Implementierung: Jinja-Template in Markdown-Card oder entities-Template

### 4. Schwellwerte global fuer alle Schweine
- Aktuell: jedes Schwein hat eigene Number-Entities fuer Schwellwerte
- User will vorerst: alle Schweine teilen dieselben Schwellwerte
- Architektur-Optionen:
  a) Erste Schwein-Config gibt Werte vor, andere lesen davon
  b) Globale Config-Entry fuer Schwellwerte
  c) Beim Aendern bei Schwein A automatisch bei B/C mitaendern
- Vormerken: pro-Schwein-Schwellwerte koennte Projektleiter spaeter wollen
  (Architektur ist bereits vorhanden -- je eigene Number-Entities)

### 5. Sonstige kleinere Punkte
- Seite 1: Mehrere Schweine / Ampel-Konzept (Vordenken + Besprechen)
- Seite 1: Pig-Selektor ein/ausblenden (spaeter)
- Dexcom Share Delay ~12min -> no_data Alarm default_timeout (mittel, vor Alarm-Feintuning)
- No-Data Notification: laufend aktualisieren (gleiche notification_id updaten)

---

## ha-internals.md (einzuarbeiten)

### State-Listener auf externe Sensor-Entities

```python
from homeassistant.helpers.event import async_track_state_change_event

unsub = async_track_state_change_event(
    hass, [entity_id], callback_fn
)
entry.async_on_unload(unsub)  # sauber abmelden beim Entry-Unload
```

- Feuert sofort wenn eine andere Integration den State der Entity aendert
- Kein Polling -- rein event-basiert ueber HA-internen Event Bus
- `hass.states.async_set()` loest automatisch `state_changed` Event aus
- Kombinieren mit Safety-Polling (60s) als Fallback empfohlen
- Callback muss `@callback` dekoriert sein; Coroutines via `hass.async_create_task()`

### async_refresh() vs async_request_refresh()

- `async_request_refresh()`: debounced, kann verzoegert/geskippt werden
- `async_refresh()`: sofort, blockiert bis Update fertig
- Buttons verwenden async_refresh() fuer sofortige UI-Aktualisierung
- State-Listener verwendet async_request_refresh() (Debounce OK da Dexcom eh 5min)

### HA Config Flow Selectors (ab HA 2022+)

```python
from homeassistant.helpers.selector import (
    TextSelector, SelectSelector, SelectSelectorConfig,
    NumberSelector, NumberSelectorConfig, NumberSelectorMode,
)
```

- Immer Selectors verwenden statt roher vol.In()/str/vol.Coerce(float)
- Ohne Selectors rendert HA Frontend Felder ohne sichtbare Labels
- Optionale Felder (vol.Optional) nur ins Schema wenn sie tatsaechlich Optionen haben
  (leeres vol.In({}) kann das gesamte Formular-Rendering zerschiessen)

### translations/ Verzeichnis (Pflicht fuer Custom Components)

- HA Frontend laedt Strings aus `translations/{sprache}.json`, NICHT aus strings.json direkt
- strings.json = Quelle fuer Entwicklung; translations/ = was HA tatsaechlich laedt
- Mindestens translations/en.json und translations/de.json erstellen
- Ohne translations/ zeigt Options Flow komplett leere Texte

---

## architecture.md (einzuarbeiten)

### Datenfluss (aktuell, seit v1.3.1+v1.3.9)

```
Dexcom-Sensor (HA) --state_changed Event--> Listener (__init__.py)
                                            --> coordinator.async_request_refresh() (sofort)
                   --60s Safety-Polling---> Coordinator._async_update_data()

Button (log_feeding/log_insulin/preset/archive)
    --> store.async_log_*()
    --> coordinator.async_refresh()  (sofort, blockierend)
    --> CoordinatorEntity.async_write_ha_state() (automatisch)
```

### Store-Restore nach Neustart (v1.3.7)

- `_last_valid_reading_time` ist in-memory, geht bei Neustart verloren
- Fix: `_restore_last_reading_time()` laedt beim ersten `_async_update_data()`-Aufruf
  den letzten Messzeitpunkt aus Store (heute, fallback letzte 24h)
- Flag `_store_restored: bool` verhindert wiederholten Store-Zugriff
