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
- v1.3.14: Stacked Bar Chart Seite 3, Threshold-Fussnote entfernt (committed)

---

## Offene Bugs

### A. ~~Coverage/missed: expected zaehlt ab Mitternacht~~ -- FIXED (v1.3.17)
- Gap-basierte Berechnung statt Wanduhr-expected
- Timestamps jetzt lokal naive (statt UTC mit +00:00-Offset)

### B. Preset-Logik hat noch Fehler
- Config Flow rendert jetzt korrekt (v1.3.8+v1.3.10)
- Aber Preset-Verhalten beim Anlegen/Verwenden hat noch logische Fehler
- Wird bei Seite-2-Ueberarbeitung gemeinsam mit neuem Layout besprochen und gefixt

---

## Seite-2-Analyse fuer morgige Diskussion (18.02.2026)

### 1. Wie Seite 2 technisch funktioniert (aktueller Stand)

**Was die Seite zeigt:**
- Status-Zeile (Glucose, Trend, Insulin heute, BE heute) als Markdown-Template
- Preset-Buttons (max. 3 pro Zeile, kommen aus Config Options)
- Fuetterungsformular: Menge (number entity), Kategorie (select entity), Zeitstempel (text entity)
- Schaltflaeche "Fuetterung loggen"
- Insulinformular: Menge (number entity), Produkt (select entity), gleicher Zeitstempel!
- Schaltflaeche "Insulin loggen"
- Tabelle "Letzte Eintraege" (Jinja-Template ueber today_events Sensor-Attribut)
- Archiv-Steuerung: Textfeld fuer Event-ID + Schaltflaeche "Event archivieren"

**Datenfluss:**
```
User aendert Entitaet (Zahl/Auswahl/Text)
  → entity.py updated coordinator.feeding_amount / feeding_category / etc.

User drueckt "Loggen"-Button
  → button.async_press() liest coordinator.feeding_amount, .feeding_category, .event_timestamp
  → store.async_log_feeding() speichert als neues Event mit uuid
  → coordinator.async_refresh() → Tagessummen werden neu berechnet → UI aktualisiert

User drueckt Preset-Button
  → GlucoFarmerPresetButton.async_press() liest Werte direkt aus self._preset (dict)
  → Store.async_log_*() → Refresh
```

**Was der Coordinator im Speicher haelt (geht bei Neustart verloren):**
- `feeding_amount`, `feeding_category`
- `insulin_amount`, `insulin_product`
- `event_timestamp` (geteilt zwischen beiden Formularen!)
- `archive_event_id`

---

### 2. Alle identifizierten Bugs

**BUG M1: Events verschwinden nach Mitternacht (pending Issue-Liste)**
- `get_today_events()` filtert nach `datetime.now().strftime("%Y-%m-%d")` als Datumspraefix
- Event von 23:58 hat Timestamp `2026-02-18T23:58:...`
- Nach Mitternacht gilt `2026-02-19` als "heute" → Event erscheint nicht mehr
- Ursache: Datumsbasierter Filter statt rollendem 24h-Fenster
- Fix: Entweder `store.get_events_since(hours=24)` ODER Dashboard zeigt "letzten 24h" statt "heute"

**BUG M2: Zeitstempel-Feld geteilt zwischen Fuetterung und Insulin**
- `event_timestamp` ist EINE einzige Text-Entitaet, die beide Formulare nutzen
- Setzt User "15 min ago" fuer Fuetterung, dann vergisst er es → naechstes Insulin-Event bekommt denselben Zeitstempel
- Kann zu falschen Zeitstempeln fuehren, ohne dass User es merkt
- Fix: Zeitstempel nach jedem Log-Vorgang automatisch auf "" zuruecksetzen ODER zwei separate Entitaeten

**BUG M3: Preset-Formular zeigt immer alle Felder (Design-Bug)**
- Im Config Flow `add_preset`: Felder `product` (fuer Insulin) und `feeding_category` (fuer Fuetterung) erscheinen BEIDE gleichzeitig, als `Optional`
- HA Config Flow unterstuetzt kein bedingtes Anzeigen von Feldern je nach "type"
- Benutzer waehlt type=Fuetterung, sieht aber noch "Produkt"-Feld → verwirrend
- Wenn Fuetterungs-Preset angelegt und `feeding_category` nicht ausgefuellt:
  `user_input.get("feeding_category", "")` → `""` wird gespeichert
  Beim Druecken: `preset.get("category", "other")` → gibt `""` zurueck (nicht "other"!)
  → Event landet mit leerem Kategorie-String im Store

**BUG M4: Preset-Button aktualisiert keine UI-Felder**
- Nach Preset-Klick sind Menge/Kategorie/Produkt-Entitaeten unveraendert (zeigen noch alte Werte)
- User sieht im Formular nicht, was zuletzt geloggt wurde
- Kein kritischer Datenfehler, aber verwirrende UX

**BUG M5: Kein Loeschschutz beim Archivieren**
- User muss Event-ID (8-stelliger Hex-String) manuell tippen
- Kein Bestaetigung-Dialog
- Kein Undo
- Archivierte Events sind dauerhaft unsichtbar (kein Admin-View)

---

### 3. Was der User fuer Seite 2 will (aus Diskussion)

Aus pending.md und frueheren Besprechungen:
1. Graph oben (Glucose-Verlauf des Schweins, Kurzuebersicht)
2. Workflow: Button zuerst sichtbar → nach Klick Formular einblenden (Progressive Disclosure)
3. Presets + manuelle Eingabe beide moeglich
4. Zeitstempel: Default=jetzt, Option "vor X Minuten"
5. BE/Insulin: summieren = getrennte Events sind OK, aber Summe deutlich sichtbar
6. Loeschen: Sicherheitsabfrage; Admin-Ansicht fuer geloeschte Events
7. Events nach Mitternacht duerfen nicht verschwinden (BUG M1)
8. Preset-Fehler mitfixen

---

### 4. Technische Machbarkeit je Feature

**A. Graph oben** → EINFACH
- Copy-Paste von Seite 3, kurzer graph_span (z.B. 3h)
- Keine Backend-Aenderungen

**B. Progressive Disclosure (Formular bei Klick einblenden)** → MOEGLICH, aber Aufwand
- HA Lovelace: `conditional` Card zeigt/versteckt basierend auf Entity-State
- Braucht neue "form_open" Select-Entitaet: Werte = ["none", "feeding", "insulin"]
- Zwei "Oeffnen"-Buttons → setzen diese Select-Entitaet
- Formulare als `conditional` Card: nur sichtbar wenn form_open = "feeding" / "insulin"
- "Abbrechen"-Button setzt form_open = "none"
- Backend: neue Select-Entitaet (select.py Erweiterung), kein Coordinator-Refresh noetig
- **Risiko**: Mehr Entities, komplexere Dashboard-Logik

**C. "Vor X Minuten" statt Freitext-Zeitstempel** → MITTEL
- Neue Number-Entitaet "minutes_ago" (0–120 min, default 0)
- Button-Handler berechnet: `datetime.now() - timedelta(minutes=self._coordinator.minutes_ago)`
- Ersetzte die Text-Entitaet event_timestamp
- Vorteil: Kein Tipp-Fehler, HA zeigt einen Slider
- Leichte Einschraenkung: Keine beliebige Datumsangabe mehr (kann kein "gestern" eintragen)

**D. Summen deutlich anzeigen** → EINFACH
- Tagessummen (Insulin heute, BE heute) sind bereits als Sensor-Entities vorhanden
- Dashboard-Template kann diese prominent anzeigen
- Keine Backend-Aenderungen

**E. Loeschen mit Sicherheitsabfrage** → MITTEL
- HA hat keine nativen Bestaetigung-Dialoge
- Ansatz: Zwei-Schritt-Prozess
  1. User waehlt Event aus Dropdown (Select-Entitaet mit allen heutigen Events als Optionen)
  2. User drueckt "Archivieren" → Bestaetigungs-Feld erscheint (Conditional Card)
  3. Oder: Event-Auswahl + Bestaetigungsbutton als Mindestschutz
- Alternativ: Nur "EventID aus Liste" statt Freitext → weniger Fehleranfaelligkeit
- Admin-View: Coordinator muss archived events zurueckgeben + Conditional Card

**F. Midnight Bug (M1)** → EINFACH
- `get_today_events` oder das Dashboard auf "letzte 24h" umstellen
- Oder: separates Feld "Aktuelle Eintraege (24h)" + "Heutige Tagessummen (ab Mitternacht)"

**G. Preset-Formular-Fix (M3)** → KOMPLEX (HA-Einschraenkung)
- HA Config Flow kann keine Felder dynamisch ein/ausblenden
- Loesungen:
  a) Zwei separate Menu-Optionen: "Preset fuer Fuetterung" und "Preset fuer Insulin"
     → Jedes Formular zeigt nur die relevanten Felder
     → Sauberste Loesung, kein bedingte Logik noetig
  b) Beibehalten wie jetzt aber leere Felder korrekt behandeln (category="" → "other")

---

### 5. Empfehlung fuer die Diskussion

**Was ich empfehle (priorisiert):**

**Muss sein (Bugs):**
- BUG M1: Midnight-Bug fixen (rolling 24h, einfach)
- BUG M3: Preset-Formular aufteilen in zwei Menu-Optionen (sauber, behebt leere Kategorie)
- BUG M2: Zeitstempel nach Log-Vorgang automatisch zuruecksetzen

**Sollte sein (grosse UX-Verbesserung):**
- Graph oben auf Seite 2 (schnell umsetzbar)
- Event-Auswahl als Dropdown statt Freitext-ID (sicherer, weniger fehleranfaellig)
- "Vor X Minuten" Number-Entitaet statt Text

**Kann sein (grosse Arbeit, grosse Wirkung):**
- Progressive Disclosure (Formular auf Klick einblenden)
- Admin-View fuer archivierte Events

**ACHTUNG -- moeglicher blinder Fleck in dieser Analyse:**
User hat darauf hingewiesen, dass er wiederholt eine "ganz andere Usability" als die bisher
diskutierte gefordert hat. Vermuteter Kern: Events (Insulin, Fuetterung) als Icons/Marker
DIREKT IM GLUCOSE-GRAPHEN (X-Achse / Zeitstempel), wie es Dexcom Clarity / Nightscout machen.
Das erlaubt visuelle Korrelation: "Ich habe um 14:00 Insulin gegeben, Glucose fiel um 14:30."
Technisch umsetzbar mit apexcharts `annotations: xaxis` mit den Event-Zeitstempeln.
Klaerung im morgigen Gespraech.

**CGM-Recherche eingearbeitet (docs/cgm-research.md):**
Wichtigste Erkenntnisse fuer GlucoFarmer:

1. DOPPELTER ZEITSTEMPEL (Dexcom Best Practice)
   Dexcom speichert immer `systemTime` (UTC) UND `displayTime` (lokal).
   GlucoFarmer speichert nur einen Timestamp (lokal, ohne UTC-Offset).
   → Das ist Wurzel von BUG A (Coverage/missed Timezone-Mismatch)!
   → Fix: Events und Readings mit UTC-Timestamp + lokaler Anzeigezeit speichern.

2. KOMBINIERTER EVENT-TYP (Nightscout `meal_bolus`)
   Nightscout kennt "Meal Bolus" = Mahlzeit + Insulin IN EINEM Event.
   GlucoFarmer hat nur getrennte Events (feeding ODER insulin).
   → Frage: Will der User manchmal Fuetterung + Insulin gemeinsam loggen?
   → Relevant fuer Seite-2-Redesign.

3. NOTIZFELD pro Event
   Dexcom + Nightscout haben freies Notizfeld bei JEDEM Event.
   GlucoFarmer hat `description` (Feeding) und `note` (Insulin) im Store,
   aber KEIN Eingabefeld im Dashboard und KEINE Anzeige in der Ereignisliste.
   → Soll das Notizfeld auf Seite 2 erscheinen?

4. SOFT-DELETE (bereits korrekt)
   GlucoFarmer-Implementierung entspricht dem Industriestandard (archived-Flag).
   Dexcom nennt es `eventStatus: "deleted"` -- dasselbe Konzept.

5. EINHEIT: BE vs. Gramm
   Dexcom/Nightscout verwenden Gramm KH. GlucoFarmer verwendet BE (Broteinheiten).
   Fuer Schweine-Tierernährung ist BE moeglicherweise die korrekte Einheit.
   Fuer spaetere Diskussion vormerken: Umrechnungsfaktor? Oder BE beibehalten?

**Offene Fragen fuer den User:**
1. **Summieren**: Wird zweimal "2 BE Fruehstueck" druecken = 2 separate Events (je 2 BE) als korrekt angesehen? Oder soll ein einziges Event auf 4 BE aktualisiert werden?
   → Aktuell: 2 separate Events, Tagessumme = 4 BE (RICHTIG aber vielleicht unklar)

2. **"Vor X Minuten"**: Reicht ein Schieberegler 0–120 min? Oder brauchen wir manchmal "gestern 14:30 Uhr" (beliebiger Zeitpunkt)?

3. **Progressive Disclosure**: Ist es wichtig genug, neue Entitaeten dafuer anzulegen, oder reicht ein saubereres Layout mit allen Formularen sichtbar?

4. **Archiv-Bestaetigung**: Wuerde ein Zwei-Schritt-Prozess (Event aus Dropdown auswaehlen → dann Bestaetigen) reichen?

---

---

## Architektur-Grundsatzentscheidung: Datenspeicherung (19.02.2026)

### Beschlossen

**Glukose + Trend → HA Recorder (SQLite)**
- Dexcom-Integration speichert beide Sensoren bereits automatisch
- HA Recorder ist Single Source of Truth fuer alle CGM-Messwerte
- GlucoFarmer darf diese Daten NICHT doppelt in eigenem Store speichern
- Graph (apexcharts) liest bereits aus Recorder -- das ist korrekt so

**Insulin + Mahlzeiten → GlucoFarmer eigener Store (JSON)**
- Einziger Grund: Benutzer kann Zeitstempel manuell setzen / rueckdatieren
- HA Recorder speichert nur den Moment der State-Aenderung -- nicht aenderbar
- Datenmodell: `timestamp` (wann passiert) + `created_at` (wann geloggt) getrennt

**Config + Mapping → GlucoFarmer Config Entry**
- Welcher Sensor gehoert zu welchem Pig -- bleibt wie bisher

### Voraussetzung fuer Langzeit-Studie
HA `configuration.yaml` muss einmalig angepasst werden:
```yaml
recorder:
  purge_keep_days: 730  # 2 Jahre, oder Studiendauer + Puffer
```
Ohne diese Einstellung loescht HA Recorder Daten nach 10 Tagen!

### Was sich im Code aendern muss (noch nicht implementiert, kein Termin)

**coordinator.py:**
- `_compute_zone_stats()`: statt eigenem Store -> HA Recorder via
  `homeassistant.components.recorder.history.get_significant_states()`
- `_compute_data_completeness_today/range()`: ebenfalls aus Recorder
- `_track_reading()`: komplett entfernen (kein eigenes Readings-Speichern mehr)

**store.py:**
- `async_log_reading()`, `get_readings_today()`, `get_readings_for_range()`,
  `get_readings_for_date()`, `async_flush_readings()`: alle entfernen
- Nur Events (Insulin, Mahlzeiten) behalten

**GlucoFarmerData (coordinator.py):**
- `readings_today_actual`, `readings_today_expected` etc.: aus Recorder berechnen
- `time_*_pct`: aus Recorder berechnen

**Neuer CSV-Export (noch nicht implementiert):**
- Kombiniert Recorder-Daten (Glukose+Trend) + Store-Events (Insulin+Mahlzeiten)
- Eine Zeile pro Ereignis, chronologisch sortiert
- Format Clarity-aehnlich (kompatibel mit externen Tools)
- Erreichbar ueber Samba / File Editor fuer Backup

### Warum noch nicht implementiert
Dieser Umbau ist gross (betrifft coordinator.py, store.py, alle Statistiken).
Wird in einer eigenen Session besprochen und umgesetzt -- erst nach Seite-2-Redesign
oder als separater Meilenstein.

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
