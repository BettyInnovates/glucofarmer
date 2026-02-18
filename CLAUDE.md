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
**Deployed**: v1.3.0
**Offen**: v1.3.1 implementiert, bereit zum Testen/Committen

### Letzte Aenderung (v1.3.1)
- `coordinator.py`: `_SCAN_INTERVAL` 60s → 5min (Safety-Polling)
- `__init__.py`: State-Listener auf Dexcom-Glukose-Sensor via `async_track_state_change_event`
  → sofortiger `coordinator.async_request_refresh()` bei jedem neuen Dexcom-Wert
  → Listener wird sauber per `entry.async_on_unload` abgemeldet

## Bekannte Einschraenkungen / TODOs

- Dashboard benoetigt `apexcharts-card` aus HACS (Frontend)
- Keine automatischen Tests
- Taeglicher Report: 5-Zonen mit Schwellwerten (seit v1.3.0)
- Chart-Zeitraum beeinflusst nur Zonen-Statistik, nicht apexcharts graph_span

## Deployment

- GitHub-Repo + HACS Custom Repository konfiguriert
- Workflow: Lokal aendern > git commit > git push > HACS Redownload > HA neu starten
