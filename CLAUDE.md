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
  -f quelle=geofabrik`; ein Handstart veröffentlicht für echte Nutzer, also
  erst nach grünen Tests. Einzige Ausnahme im Repo: `stand.json`, die jeder
  erfolgreiche Lauf als `github-actions[bot]` auf `main` committet (vor eigenem
  Push `git pull`). Rote Probe des Wächters: `-f fehlerprobe=true`, dann das
  Issue mit dem Label `lauf-gescheitert` prüfen und schließen (README,
  „Wächter“).
- Einzige Quelle ist der Geofabrik-Auszug (fünf Versuche mit wachsender
  Pause, höchstens 30 Minuten je Land). Seit Runde 54 gibt es keinen Rückfall
  auf Overpass mehr (Marcels Auftrag; der Server lieferte Monate alte Daten):
  Scheitert ein Auszug, ist der Lauf rot, nichts wird veröffentlicht, online
  bleibt der alte Stand, der Dienstagslauf holt nach. README, „Wiederholung
  (ohne Rückfall)“. Vor einem neuen Server dessen Nutzungsregeln lesen
  (`robots.txt`, OSM-Wiki), bevor ihn irgendein Abruf trifft.
- Sorgsam laden (Geofabrik, „Download responsibly!“, README): Was eine
  Wiederholung nicht heilt (401, 403, 429, zu wenig Platz, Schreibfehler),
  wird nicht wiederholt (ein 404 schon, am 21.11.2026 war er vorübergehend); je Land und Lauf höchstens zweimal die Länge des Auszugs. Jeder
  Abruf trägt `USER_AGENT` aus `tools/orte.py` (Projekt, Repo, Kontakt); kein
  Abruf ohne ihn. Den `.osm.pbf` lädt nur der Lauf auf GitHub, nie eine
  Sitzung von Claude (Geofabriks `robots.txt` sperrt `*.osm.pbf` für alle
  User-Agents).
- Ändert sich das Format der Dateien (Felder, Arten `k`), muss die App es
  lesen können: unbekannte Arten übergeht sie, fehlende Pflichtfelder machen
  die Datei für sie kaputt; die App verwirft außerdem neue Dateien mit weniger
  als 100 Einträgen.
- **`STANDARDNAMEN` in `tools/orte.py` und `ortGarten` … `ortRefill`, `ortMarkt` in
  `lib/l10n/app_de.arb` und `app_en.arb` der App gehören zusammen** (die
  Namen, die die App für Orte ohne Namen zeigt; sie gelten wie die
  Gattungswörter und Straßennamen als allgemein, Einträge mit ihnen werden
  nur unter 30 m zusammengeführt, eigene Namen unter 200 m; README,
  „Doppelte“): Wer das eine ändert, ändert das andere.
  Kommt eine Art dazu, braucht sie hier einen Eintrag und in der App einen
  Standardnamen.
