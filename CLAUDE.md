# GlucoFarmer - Custom Integration for Home Assistant

Praeklinische CGM-Ueberwachung fuer diabetisierte Schweine.
Eigenstaendiges HACS-Plugin, nutzt Dexcom-Integration (unveraendert).

## Regeln

- **Arbeitsverzeichnis**: `/home/mub/projects/glucofarmer/` -- NUR hier arbeiten
- **NICHT in ha-core** arbeiten (dort liegt eine veraltete Kopie)
- **Git**: User handhabt git selbst, NIEMALS git-Befehle ausfuehren

## Dokumentation

| Datei | Inhalt |
|-------|--------|
| [docs/architecture.md](docs/architecture.md) | Dateien, Entities, Datenfluss, Konzepte, Services, Alarme |
| [docs/changelog.md](docs/changelog.md) | Versionshistorie (v1.0.0 bis aktuell) |
| [docs/ha-internals.md](docs/ha-internals.md) | HA-spezifische API-Patterns (LovelaceData etc.) |

## Aktueller Stand

**Version**: v1.3.0 (5-Zonen, Inline-Eingabe, variable Charts)
**Deployed**: v1.2.1
**Offen**: v1.3.0 ist fertig eingearbeitet, noch nicht committed/gepusht

## Bekannte Einschraenkungen / TODOs

- Dashboard benoetigt `apexcharts-card` aus HACS (Frontend)
- Keine automatischen Tests
- Taeglicher Report: 5-Zonen mit Schwellwerten (seit v1.3.0)
- Chart-Zeitraum beeinflusst nur Zonen-Statistik, nicht apexcharts graph_span

## Deployment

- GitHub-Repo + HACS Custom Repository konfiguriert
- Workflow: Lokal aendern > git commit > git push > HACS Redownload > HA neu starten
