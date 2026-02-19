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

**Version**: v1.3.15 (noch nicht committed)
**Deployed**: v1.3.13
**Naechster Schritt**: v1.3.14 pushen + deployen, dann Seite 2 besprechen

### Was v1.3.14 enthaelt (bereit zum commit):
- Seite 3: Stacked Bar Chart (apexcharts) statt Emoji-Zonentext
- Seite 3: Threshold-Fussnote entfernt (war zu ueberladen)
- Version auf 1.3.14

### Commit-Message fuer v1.3.14:
```
feat: Stacked Bar Chart fuer Zonenverteilung Seite 3 (v1.3.14)

Seite 3 zeigt Zeit im Zielbereich jetzt als gestapeltes horizontales
Balkendiagramm (apexcharts). Fuenf Zonen farblich kodiert. Threshold-
Fussnote entfernt (war zu ueberladen; spaetere Idee: kleine Grenzwerte
am Balkendiagramm links).
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
-- Offene Bugs --
A. Coverage/missed: expected zaehlt ab Mitternacht, nicht ab erstem Reading heute
   → Verdacht: missed erscheint zu hoch; pruefen ob Design-Aenderung noetig
   → Details in pending.md
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
