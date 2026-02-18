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

**Version**: v1.3.1 (Dexcom State-Listener + 5min Safety-Polling)
**Deployed**: v1.3.1 (getestet, funktioniert)
**Naechster Schritt**: Issue #4 – Datenvollstaendigkeit falsch berechnet

### Offene Issues (Reihenfolge = Prioritaet)
1. ~~Tages-Zusammenfassung kommt nicht~~ -- FIXED (v1.3.2)
2. ~~Notification Datenverlust: Zeitangabe "unknown"~~ -- FIXED (v1.3.2)
3. ~~Statistik Seite 3: Zeitraum-Wechsel ohne Effekt~~ -- FIXED (v1.3.3)
4. Datenvollstaendigkeit falsch berechnet
5. Presets: Text unsichtbar + Logik kaputt
6. Seite 2: Layout/Workflow/Logik komplett ueberarbeiten
7. Graph-Fixes (Y-Achse links+sinnvoll, 6h auf Seite 1, konsistent)
8. Seite 3: Stacked Balkendiagramm Zonen
9. Seite 1: Ampel-System alle Schweine
10. Seite 1: Pig-Selektor ein/ausblenden
11. Fehlende Zeitstempel zaehlen (x von y missed)
-- Details in docs/pending.md --

## Bekannte Einschraenkungen / TODOs

- Dashboard benoetigt `apexcharts-card` aus HACS (Frontend)
- Keine automatischen Tests
- Taeglicher Report: 5-Zonen mit Schwellwerten (seit v1.3.0)
- Chart-Zeitraum beeinflusst nur Zonen-Statistik, nicht apexcharts graph_span

## Deployment

- GitHub-Repo + HACS Custom Repository konfiguriert
- Workflow: Lokal aendern > git commit > git push > HACS Redownload > HA neu starten
