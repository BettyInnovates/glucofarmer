# Pending Documentation Updates

Gesammelte Aenderungen fuer architecture.md und ha-internals.md.
Werden bei Gelegenheit (Milestone, Deploy) eingearbeitet und dann geleert.

---

## Offene Issues (detailliert) -- Stand 18.02.2026

### P1 – Bugs

**#1 Tages-Zusammenfassung kommt nicht mehr**
- Letzte Nacht keine Zusammenfassung erhalten
- Ursache unklar, in __init__.py/_send_daily_report() untersuchen
- Spaeter: auch per Mail verschicken + CSV mit Glucose-Rohdaten als Daten-Backup

**#2 Notification Datenverlust: Zeitangabe falsch**
- Zeigt "unknown" oder "no data" statt Anzahl Minuten
- Betrifft _check_alarms() / STATUS_NO_DATA Branch in __init__.py
- reading_age_minutes ist None obwohl Sensor unavailable

**#3 Statistik Seite 3: Zeitraum-Wechsel ohne Effekt**
- Select chart_timerange aendert nichts an der Anzeige
- Alle Werte/Sensoren sollen sich beim Wechsel aktualisieren

**#4 Datenvollstaendigkeit falsch berechnet**
- Zeigt 37.8% obwohl fast keine Ausfaelle seit Mitternacht
- Springt zwischen 37.8% und 75% -- Logik inkonsistent
- Berechnung in coordinator._compute_data_completeness() pruefen
- Gewuenscht: nachvollziehbar, z.B. "x von y Messungen vorhanden"

**#5 Presets: Text unsichtbar + Logik kaputt**
- Preset-Buttons zeigen keinen Text
- Insulin-Preset nach Erstellung nicht in Auswahl sichtbar
- Gesamte Preset-Logik und Darstellung ueberdenken

### P2 – Dashboard UX

**#6 Seite 2: Komplett ueberarbeiten**
- Layout: zurueck zu Graph (Uebersicht Schwein) + Buttons darunter
- Workflow: erst Button sichtbar, nach Klick Formular einblenden
- Presets + manuelle Eingabe moeglich
- Zeitstempel: default=jetzt, Option "vor X min"
- BE/Insulin: summieren (nicht ueberschreiben), getrennt pro Typ
- Loeschen: Soft-Delete mit Sicherheitsabfrage ("wirklich loeschen?")
  Admin-Ansicht zum Einsehen + Wiederherstellen geloeschter Events
  Option: statt Loeschen auch Zeitstempel aendern
- Events nach Mitternacht duerfen nicht verschwinden (Bug)
- Vormerken: Icons (Apfel/Spritze) im Graph oder darunter als Timeline

**#7 Graph-Fixes (alle Seiten)**
- Seite 1: 6h statt 12h anzeigen
- Y-Achse: Labels LINKS (nicht rechts), sinnvolle Werte (Grenzwerte oder 50/100er Schritte)
- Konsistent auf allen Seiten umsetzen

**#8 Seite 3: Stacked Balkendiagramm Zonen**
- "Zeit im Zielbereich" als Stacked Bar, nicht nur Punkte/Zahlen
- Pruefen ob mit vorhandener Dashboard-Card moeglich

### P3 – Verbesserungen

**#9 Seite 1: Ampel-System alle Schweine**
- Ganz oben: schneller Ueberblick ob allen Schweinen gut geht
- Idee: Ampel oder Statuszeile pro Schwein

**#10 Seite 1: Pig-Selektor**
- Schweine im Graph ein-/ausblenden
- Vormerken: Gruppen (Kontrollgruppe / Testgruppe)

**#11 Fehlende Zeitstempel zaehlen**
- Anzeige: "x von y Messungen vorhanden" oder "N missed seit 0:00"
- Evtl. schon auf Seite 1 sichtbar

### Vormerken / Spaeter

- Mail-Versand Tages-Report + CSV Glucose-Rohdaten als Daten-Backup
  → Empfehlung: als HA Automation (Nutzer waehlt Uhrzeit + Mail-Provider selbst)
  → Unser Part: `glucofarmer.generate_report` Service mit pig_name, start, end, format (csv/text)
- Schweine-Gruppen im Graph
- Events als Icons im Graph (Fuetterung/Insulin-Zeitpunkte)
- Detailansicht pro Schwein + Datenexport on Demand
  → On-Demand Report: Button in Detailansicht ruft `glucofarmer.generate_report` auf
  → Nutzer kann auch eigene Automation bauen (z.B. nach critical_low, woechentlich etc.)

---

## ha-internals.md

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
- Kombinieren mit Safety-Polling (z.B. 5min) als Fallback empfohlen
- Callback muss `@callback` dekoriert sein; Coroutines via `hass.async_create_task()`

---

## architecture.md

### Datenfluss-Ergaenzung (Dexcom-Listener)

Im Abschnitt "Datenfluss" ergaenzen:

```
Dexcom-Sensor (HA) --state_changed Event--> Listener (__init__.py)
                                                --> coordinator.async_request_refresh() (sofort)
                   --5min Safety-Polling------> Coordinator._async_update_data()
```

Statt bisher nur:
```
Dexcom-Sensor (HA) --> Coordinator (60s Polling)
```
