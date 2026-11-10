# stepzero-daten – Regeln für Claude Code

Öffentliches Daten-Repo der App Step Zero (App-Repo `~/StepZero`, dort
ausführlich in `docs/claude/lokal.md`, Abschnitt „Lokal V1.5b“; bis 10.11.2026
stand das in der CLAUDE.md des App-Repos). Hier entstehen wöchentlich
die Orte-Dateien `de.json`, `at.json`, `ch.json` aus OpenStreetMap
(ODbL), veröffentlicht unter `https://laggstudio.github.io/stepzero-daten/`.
Ablauf, Arten, Etiketten und Prüfungen stehen im README.

## Feste Regeln

- Nur Python-Standardbibliothek, für den Geofabrik-Auszug pyosmium. Tests:
  `python3 -m unittest discover -s tests` (kein Linter konfiguriert); Exit-Code
  aus einer Datei lesen, nie hinter einer Pipe.
- Keine Daten im Repo (`ausgabe/` steht in `.gitignore`); veröffentlicht wird
  nur über GitHub Actions (`.github/workflows/orte.yml`, Pages-Quelle „GitHub
  Actions“). Handstart: `gh workflow run orte.yml -R LAGGstudio/stepzero-daten
  -f quelle=geofabrik`.
- Hauptquelle ist der Geofabrik-Auszug; Overpass nur von Hand
  (`ORTE_QUELLE=overpass`), ohne Rückfall.
- Ändert sich das Format der Dateien (Felder, Arten `k`), muss die App es
  lesen können: unbekannte Arten übergeht sie, fehlende Pflichtfelder machen
  die Datei für sie kaputt; die App verwirft außerdem neue Dateien mit weniger
  als 100 Einträgen.
- **`STANDARDNAMEN` in `tools/orte.py` und `ortGarten` … `ortRefill` in
  `lib/l10n/app_de.arb` und `app_en.arb` der App gehören zusammen** (die
  Namen, die die App für Orte ohne Namen zeigt; Einträge mit diesen Namen
  werden nie zusammengeführt): Wer das eine ändert, ändert das andere.
  Kommt eine Art dazu, braucht sie hier einen Eintrag und in der App einen
  Standardnamen.
