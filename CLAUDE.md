# GlucoFarmer - Custom Integration for Home Assistant

Praeklinische CGM-Ueberwachung fuer diabetisierte Schweine.
Eigenstaendiges HACS-Plugin, nutzt Dexcom-Integration (unveraendert).

## Regeln

- **Arbeitsverzeichnis**: `/home/mub/projects/glucofarmer/` -- NUR hier arbeiten
- **NICHT in ha-core** arbeiten (dort liegt eine veraltete Kopie)
- **Git**: User handhabt git selbst, NIEMALS git-Befehle ausfuehren

## Dokumentation

| Datei | Inhalt | Update-Strategie |
|-------|--------|-----------------|
| [docs/architecture.md](docs/architecture.md) | Dateien, Entities, Datenfluss, Konzepte, Services, Alarme | Nur bei strukturellen Aenderungen |
| [docs/changelog.md](docs/changelog.md) | Versionshistorie (v1.0.0 bis aktuell) | Immer sofort |
| [docs/ha-internals.md](docs/ha-internals.md) | HA-spezifische API-Patterns (LovelaceData etc.) | Aus pending.md einarbeiten |
| [docs/pending.md](docs/pending.md) | Gesammelte Aenderungen fuer arch/internals (wird geleert nach Einarbeitung) | Nach jeder Aenderung |

## Aktueller Stand

**Version**: v1.3.17 (noch nicht committed)
**Deployed**: v1.3.16
**Naechster Schritt**: v1.3.17 committen/deployen, dann Seite 2 besprechen

### Was v1.3.17 enthaelt (bereit zum commit):
- Gap-basierte Datenvollstaendigkeit (kein Wanduhr-expected mehr)
- Timestamps lokal naive statt UTC gespeichert
- timezone-Import entfernt, _READINGS_PER_HOUR durch _READING_INTERVAL_MINUTES ersetzt

### Commit-Message fuer v1.3.17:
```
fix: Datenvollstaendigkeit gap-basiert statt Wanduhr-Hochrechnung (v1.3.17)

Coverage berechnet sich jetzt aus Luecken zwischen gespeicherten Readings
statt aus Wanduhr-expected ab Mitternacht. HA-Neustarts erzeugen keine
falschen missed-Werte mehr. Zwei Schweine auf demselben Sensor zeigen
jetzt identische Coverage. Timestamps lokal naive statt UTC gespeichert.
```

### Offene Issues (Reihenfolge = Prioritaet)
1. ~~Tages-Zusammenfassung kommt nicht~~ -- FIXED (v1.3.2)
2. ~~Notification Datenverlust: Zeitangabe unknown~~ -- FIXED (v1.3.2)
3. ~~Statistik Seite 3: Zeitraum-Wechsel ohne Effekt~~ -- FIXED (v1.3.3)
4. ~~Datenvollstaendigkeit falsch berechnet~~ -- FIXED (v1.3.4)
5. ~~Presets: Text unsichtbar + Logik kaputt (Buttons)~~ -- FIXED (v1.3.5)
6. ~~Completeness auf Seite 1/3 vertauscht + Darstellung falsch~~ -- FIXED (v1.3.6)
7. ~~Nach HA-Neustart _last_valid_reading_time verloren~~ -- FIXED (v1.3.7)
8. ~~Preset-Text im Config Flow unsichtbar~~ -- FIXED (v1.3.8+v1.3.10)
9. ~~BE-Summe aktualisiert sich mit Verzoegerung~~ -- FIXED (v1.3.9)
10. ~~Seite 1: Gauge durch Achtung-Symbol ersetzen~~ -- FIXED (v1.3.11)
11. ~~Seite 3: Threshold-Fussnote~~ -- ENTFERNT (v1.3.14, war zu ueberladen)
12. ~~Graph-Fixes (6h Seite 1, Y-Achse)~~ -- FIXED (v1.3.11/v1.3.13)
13. ~~Coordinator-Polling 5min zu langsam nach Restart~~ -- FIXED (v1.3.12, zurueck auf 60s)
14. ~~Seite 3: Stacked Balkendiagramm Zonen~~ -- FIXED (v1.3.14)
A. ~~Coverage/missed: Wanduhr-expected ab Mitternacht, HA-Neustart blaest Zahl auf~~ -- FIXED (v1.3.17)
-- Offene Bugs --
B. Preset-Logik hat noch Fehler (wird bei Seite-2-Ueberarbeitung gefixt)
-- Dashboard Ueberarbeitung --
15. Seite 2: Layout/Workflow/Logik komplett ueberarbeiten -- MUSS BESPROCHEN WERDEN
    (Graph+Preset-Buttons+manuelle Eingabe, Summierung, Soft-Delete, Zeitstempel)
16. Seite 3: Schwellwerte am Bar Chart anzeigen -- IDEE (nach Seite-2)
    Evtl. kleine Zahlen links am Balken statt Fussnote; erst entscheiden
    wenn User das Diagramm gesehen hat.
17. Seite 1: Mehrere Schweine im Header / Ampel-Konzept (vordenken/besprechen)
18. Seite 1: Pig-Selektor ein/ausblenden (spaeter)
V. Sync-Anzeige Echtzeit (dashboard template -- kann Claude selbststaendig machen)
W. Schwellwerte global fuer alle Schweine (aktuell pro Schwein; besprechen wenn noetig)
X. Dexcom Share Delay ~12min -> no_data Alarm default_timeout ueberdenken
-- Details in docs/pending.md --

## Architektur-Grundsatzentscheidungen

Diese Entscheidungen sind BINDEND und duerfen nicht ohne explizite Absprache
mit dem User geaendert werden.

### Datenspeicherung (beschlossen 19.02.2026)

| Datentyp | Speicherort | Begruendung |
|----------|-------------|-------------|
| Glukose-Readings | **HA Recorder** (SQLite, bereits vorhanden) | Dexcom-Sensor laeuft sowieso, Daten sind schon da |
| Trend-Werte | **HA Recorder** (SQLite, bereits vorhanden) | Gleiche Begruendung wie Glukose |
| Insulin-Events | **GlucoFarmer Store** (eigener JSON) | Braucht benutzerdefinierten Timestamp (rueckdatieren moeglich) |
| Mahlzeiten-Events | **GlucoFarmer Store** (eigener JSON) | Gleiche Begruendung wie Insulin |
| Config/Mapping (Pig<->Sensor) | **GlucoFarmer Config Entry** | Wie bisher |

**Kernprinzip**: Glukose und Trend NICHT doppelt speichern. HA Recorder ist
die Single Source of Truth fuer alle CGM-Messwerte.

**Warum Insulin/Mahlzeiten NICHT im Recorder**: HA Recorder speichert den
Zeitpunkt der State-Aenderung in HA -- dieser ist unveraenderbar. Fuer Events
die rueckdatiert werden koennen muessen ("Insulin vor 15min gegeben") brauchen
wir einen eigenen `timestamp`-Feld getrennt von `created_at`.

**Langzeit-Speicherung**: HA Recorder muss mit `purge_keep_days: 730` (o.ae.)
konfiguriert werden damit Studiendaten nicht nach 10 Tagen geloescht werden.
Dies ist eine einmalige manuelle Konfiguration in `configuration.yaml`.

### Noch umzusetzen (keine Prioritaet gesetzt)
- GlucoFarmer eigenen Readings-Store abloesen: Zonen-Statistiken und Coverage
  aus HA Recorder berechnen statt aus eigenem JSON-Store
- CSV-Export aus Recorder (Glukose+Trend) + eigenem Store (Events) kombiniert
- Details in docs/pending.md

## Bekannte Einschraenkungen / TODOs

- Dashboard benoetigt `apexcharts-card` aus HACS (Frontend)
- Keine automatischen Tests
- Taeglicher Report: 5-Zonen mit Schwellwerten (seit v1.3.0)
- Chart-Zeitraum beeinflusst nur Zonen-Statistik, nicht apexcharts graph_span
- Schwellwerte aktuell pro Schwein (je eigene Number-Entities) -- fuer jetzt OK,
  Projektleiter koennte spaeter pro-Schwein-Schwellwerte wollen (Architektur bereits vorhanden)

## Deployment

- GitHub-Repo + HACS Custom Repository konfiguriert
- Workflow: Lokal aendern > git commit > git push > HACS Redownload > HA neu starten
