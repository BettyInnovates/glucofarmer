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

**Version**: v1.3.10 (letzter commit: translations/)
**Deployed**: v1.3.3 (v1.3.4-v1.3.10 committed aber noch nicht in HA getestet/deployed)
**Naechster Schritt**: Dashboard-Ueberarbeitung (Issue #10+)

### Offene Issues (Reihenfolge = Prioritaet)
1. ~~Tages-Zusammenfassung kommt nicht~~ -- FIXED (v1.3.2)
2. ~~Notification Datenverlust: Zeitangabe unknown~~ -- FIXED (v1.3.2)
3. ~~Statistik Seite 3: Zeitraum-Wechsel ohne Effekt~~ -- FIXED (v1.3.3)
4. ~~Datenvollstaendigkeit falsch berechnet~~ -- FIXED (v1.3.4)
5. ~~Presets: Text unsichtbar + Logik kaputt~~ -- FIXED (v1.3.5)
6. ~~Completeness auf Seite 1/3 vertauscht + Darstellung falsch~~ -- FIXED (v1.3.6)
7. ~~Nach HA-Neustart lost_valid_reading_time verloren -> unknown bei Notification~~ -- FIXED (v1.3.7)
8. ~~Preset-Text beim Anlegen im Config Flow unsichtbar~~ -- FIXED (v1.3.8)
9. ~~BE-Summe aktualisiert sich mit Verzoegerung nach Logging~~ -- FIXED (v1.3.9)
-- Offene Bugs --
9. BE-Summe aktualisiert sich mit Verzoegerung nach Logging
-- Dashboard Ueberarbeitung --
10. Seite 1: Gauge durch Achtung-Symbol ersetzen wenn kein Wert (war schon geplant)
11. Seite 1: Mehrere Schweine im Header / Ampel-Konzept (vordenken)
12. Seite 2: Layout/Workflow/Logik komplett ueberarbeiten (Graph+Buttons, Summierung)
13. Seite 3: Threshold-Werte in Klammern - besser loesen (Fussnote oder ins Balkendiagramm)
14. Seite 3: Stacked Balkendiagramm Zonen
15. Graph-Fixes (Y-Achse links+sinnvoll, 6h auf Seite 1, konsistent)
16. Seite 1: Pig-Selektor ein/ausblenden
V. Sync-Anzeige Echtzeit (dashboard template)
W. Dexcom Share Delay ~12min -> no_data Alarm default_timeout ueberdenken
-- Details in docs/pending.md --

## Bekannte Einschraenkungen / TODOs

- Dashboard benoetigt `apexcharts-card` aus HACS (Frontend)
- Keine automatischen Tests
- Taeglicher Report: 5-Zonen mit Schwellwerten (seit v1.3.0)
- Chart-Zeitraum beeinflusst nur Zonen-Statistik, nicht apexcharts graph_span

## Deployment

- GitHub-Repo + HACS Custom Repository konfiguriert
- Workflow: Lokal aendern > git commit > git push > HACS Redownload > HA neu starten
