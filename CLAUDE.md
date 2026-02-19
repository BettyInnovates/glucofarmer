# GlucoFarmer - Custom Integration for Home Assistant

Multi-CGM Monitoring fuer Home Assistant.
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

## Lokaler Stand

Lies `CLAUDE.local.md` wenn vorhanden (gitignored -- aktuelle Version, offene Tasks, Issues).

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
| Config/Mapping (Profil<->Sensor) | **GlucoFarmer Config Entry** | Wie bisher |

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
- Schwellwerte aktuell pro Profil (je eigene Number-Entities) -- fuer jetzt OK,
  Projektleiter koennte spaeter pro-Profil-Schwellwerte wollen (Architektur bereits vorhanden)

## Deployment

- GitHub-Repo + HACS Custom Repository konfiguriert
- Workflow: Lokal aendern > git commit > git push > HACS Redownload > HA neu starten
