# stepzero-daten

Orte für den Tab Lokal der App **Step Zero** von LAGGstudio: Gemeinschaftsgärten,
Fairteiler, Verschenkboxen, Bücherschränke, Repair-Cafés, Trinkbrunnen und
Refill-Stationen in Deutschland, Österreich und der Schweiz, wöchentlich aus
OpenStreetMap geholt und über GitHub Pages veröffentlicht.

## Daten und Lizenz

Die Daten stammen aus OpenStreetMap: **© OpenStreetMap-Mitwirkende**, siehe
<https://www.openstreetmap.org/copyright>. Sie stehen unter der
[Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
Wer sie weiterverwendet, nennt OpenStreetMap als Quelle und gibt abgeleitete
Datenbanken unter derselben Lizenz weiter.

Fehlt ein Ort oder stimmt etwas nicht, gehört die Korrektur in OpenStreetMap
selbst (<https://www.openstreetmap.org>); die nächste wöchentliche Abfrage
übernimmt sie.

## Dateien

Auf GitHub Pages (nicht im Repo; im Repo liegt nur die kleine `stand.json`
des letzten Laufs, siehe „Wächter“) unter <https://laggstudio.github.io/stepzero-daten/>:
[`de.json`](https://laggstudio.github.io/stepzero-daten/de.json),
[`at.json`](https://laggstudio.github.io/stepzero-daten/at.json),
[`ch.json`](https://laggstudio.github.io/stepzero-daten/ch.json) und eine
[Übersicht](https://laggstudio.github.io/stepzero-daten/) (`index.html`). Das
Repo liegt seit dem 10.11.2026 unter <https://github.com/LAGGstudio/stepzero-daten>;
die frühere Adresse unter moonblazer420 gilt nicht mehr. Jede Datei ist
kompaktes JSON:

```json
{"stand":"2026-11-09","lizenz":"ODbL 1.0 (https://opendatacommons.org/licenses/odbl/1-0/), © OpenStreetMap-Mitwirkende, https://www.openstreetmap.org/copyright",
 "eintraege":[{"id":"n123","k":"buecherschrank","lat":50.93759,"lon":6.96016,"name":"…","adresse":"Ring 1, 50667 Köln","oeffnung":"24/7"}]}
```

`lizenz` nennt seit dem 12.11.2026 auch die URI der ODbL 1.0 (ODbL 4.2.b
verlangt Lizenz oder URI in der Datenbank). `id`: OSM-Typ (`n`, `w`, `r`) und Nummer. `k`: Art. `lat`, `lon`: 5
Nachkommastellen, bei Wegen und Relationen die Mitte. `name`, `adresse`
(Straße Nr, PLZ Ort) und `oeffnung` (`opening_hours` roh) nur, wenn vorhanden.
Seit Runde 54 bei Märkten (`k` = `markt`) dazu `zeiten`, die Öffnungszeiten
als lesbarer Text, `{"de": "Mi, Sa 8–13 Uhr", "en": "Wed, Sat 8 a.m.–1 p.m."}`,
nur wenn `tools/oeffnungszeiten.py` sie sicher versteht (feste Regeln für
Tage, Tagesbereiche, Zeiten und mehrere Regeln mit Semikolon, kein
Sprachmodell; was nicht passt, etwa Feiertage, Monate oder n-te Wochentage,
bekommt keinen Text; Einzelheiten im Kopf der Datei). Ältere Apps übergehen
die Art und das Feld.

## Arten und Etiketten

| Art (`k`) | OSM-Etiketten |
| --- | --- |
| `garten` | `leisure=garden` mit `garden:type=community` |
| `fairteiler` | `amenity=food_sharing` |
| `verschenkbox` | `amenity=give_box` |
| `buecherschrank` | `amenity=public_bookcase` |
| `repaircafe` | `repair_cafe=yes` oder `repair=assisted_self_service` |
| `trinkbrunnen` | `amenity=drinking_water` |
| `refill` | `drinking_water:refill=yes` |
| `markt` | `amenity=marketplace` (seit Runde 54; Punkte, Flächen als Mitte; nur mit `name` oder `opening_hours`) |

Ein Ort bekommt die erste passende Art in dieser Reihenfolge. Ausgeschlossen:
`access=private` oder `no`, `drinking_water=no` und alles mit `disused:` oder
`abandoned:`.

`repaircafe`: `repair_cafe=yes` ist kein dokumentiertes Etikett und war am
9.11.2026 weltweit nicht in Gebrauch (taginfo). Die Wiki-Seite
[Repair cafe](https://wiki.openstreetmap.org/wiki/Repair_cafe) erfasst
Repair-Cafés mit `repair=assisted_self_service` (Status „in use“, 531
weltweit, 143 in Deutschland), darum zählt es mit.

Leihläden fehlen bewusst: Das Wiki nennt kein dafür dokumentiertes und
verbreitetes Etikett. `amenity=tool_library` ist dokumentiert, aber weltweit
nur 53-mal und in Deutschland 2-mal in Gebrauch, `amenity=library_of_things`
ist nicht dokumentiert (2), `amenity=toy_library` meint Spielzeug und
`shop=rental` gewerbliche Vermietung (taginfo, 9.11.2026).

## Doppelte

OpenStreetMap enthält manche Orte mehrfach (am 9.11.2026 in Deutschland 90
Paare gleicher Art und gleichen Namens unter 100 m, etwa zwei „Querbeet“ in
Köln 17 m auseinander). Die Pipeline führt sie zusammen
(`tools/orte.py`, `doppelte_zusammenfuehren`):

- gleich sind Einträge derselben Art mit demselben Namen, verglichen klein,
  mit umschriebenen Umlauten (ä→ae, ö→oe, ü→ue, ß→ss), ohne andere Akzente
  und ohne Leer- und Satzzeichen („Quer-Beet“ = „querbeet“, „Gießwasser“ =
  „giesswasser“);
- bei einem eigenen Namen (etwa „Querbeet“) unter 200 m (Haversine,
  Erdradius 6371,0088 km wie in der App; bis zum 12.11.2026 unter 100 m, dann
  blieb der Garten „Querbeet“ in Köln mit zwei Knoten 113 m auseinander
  doppelt);
- bei Märkten (seit Runde 54) immer unter 200 m, auch bei allgemeinen
  Namen: Ein Markt steht oft als Fläche und als Punkt in OSM, die Mitte der
  Fläche liegt weit vom Punkt, und fast jeder heißt „Wochenmarkt“ oder
  „Markt“;
- bei einem allgemeinen Namen nur unter 30 m (seit dem 13.11.2026; bis dahin
  wurden Gattungswörter und Standardnamen nie zusammengeführt, und ein
  Straßenname galt als eigener Name: zwei Trinkbrunnen „Dorfstrasse“ 193 m
  auseinander wurden zu einem). Allgemein ist ein
  Gattungswort aus `ALLERWELTSNAMEN` in `tools/orte.py` (`brunnen`,
  `trinkbrunnen`, `trinkwasser`, `wasser`, `wasch`, `giesswasser`,
  `wasserstelle`, `buecherschrank`, `offenerbuecherschrank`, `buecherbox`,
  `buecherzelle`, `givebox`, `verschenkbox`, `verschenkregal`, `fairteiler`,
  `foodsharing`, `gemeinschaftsgarten`, `garten`, `repaircafe`, `refill`,
  `wasserhahn`, `fontana`, `fontaine`, `fontaene`, `laufbrunnen`,
  `zierbrunnen`, `trinkwasserspender`, `thermalwassertrinkbrunnen`;
  normalisiert wie beim Vergleich), einer der Namen, die die App für Orte ohne
  Namen zeigt, deutsch oder englisch, für jede Art (etwa „Trinkbrunnen“,
  „Drinking fountain“, „Refill-Station“), oder nur ein Straßenname ohne
  Hausnummer und ohne weiteren Zusatz („Dorfstrasse“, „Karl-Marx-Straße“,
  „Lange Gasse“, „Am Markt“, „Rue du Marché“; `strassenname`). Zwei „Brunnen“
  50 m auseinander sind meist zwei Brunnen, zwei „Bücherzelle“ 1 m
  auseinander dieselbe. Sobald ein Name einer Gruppe allgemein ist, gilt
  für die Gruppe die kleinere Grenze. Die Standardnamen (`STANDARDNAMEN` in
  `tools/orte.py`) gehören zu `ortGarten` … `ortRefill` in den ARB-Dateien
  der App; wer das eine ändert, ändert das andere;
- behalten wird der Eintrag mit den meisten Angaben (Adresse, Öffnungszeiten),
  bei Gleichstand der mit der kleineren ID (erst Knoten, dann Weg, dann
  Relation, darin die kleinere Nummer);
- jeder weitere fällt nur weg, wenn er unter der Grenze von einem behaltenen
  liegt; so entstehen keine Ketten über mehrere hundert Meter;
- Einträge ohne Namen werden nie zusammengeführt (die meisten Trinkbrunnen).

Jeder Lauf gibt je Land und Art die Anzahl und die Zahl der zusammengeführten
aus.

## Ablauf

GitHub Actions (`.github/workflows/orte.yml`) läuft montags um 03:23 UTC (seit
dem 12.11.2026 eine krumme Minute; die GitHub-Doku: „High load times include the
start of every hour. If the load is sufficiently high enough, some queued jobs
may be dropped.“), alle Jobs fest auf `ubuntu-24.04` (seit dem 14.11.2026; GitHub
meldete in den Läufen, dass `ubuntu-latest` auf Ubuntu 26 umgestellt wird), und per Hand: Tests, je Land der tägliche Geofabrik-Auszug
(`tools/hole_orte.py` mit `tools/geofabrik.py`, siehe unten), Zusammenführen der
Doppelten, Prüfung gegen die veröffentlichte Fassung (`tools/pruefe_orte.py`:
Schema, Koordinaten im Land, höchstens 8 MB, Lizenz mit OpenStreetMap und der
URI der ODbL, je Land mindestens 1000 Einträge, Stand höchstens 30 Tage alt;
keine Art mit mindestens 20 Einträgen in der Vorgängerin und nicht das ganze
Land fällt um mehr als 30 %), dann die Übersicht und die Veröffentlichung auf
GitHub Pages. Schlägt die Prüfung fehl, bleibt die alte Fassung online.

Kleine Arten (unter 20 Einträgen vorher) zählen seit dem 12.11.2026 beim
Rückgang nicht mehr einzeln: In AT gab es online eine Refill-Station (refill 1),
9 Repair-Cafés, 11 Verschenkboxen und 17 Fairteiler; verschwand die eine
Refill-Station aus OSM, hätte jeder Lauf gegen dieselbe Vorgängerin
gescheitert und DE, AT und CH eingefroren. Die Summe des Lands prüft die
Pipeline immer.

### Wächter

- **Issue bei Fehlschlag:** Scheitert ein Job, legt der letzte Job `melden`
  (nur `issues: write`) per `gh` ein Issue mit dem Label `lauf-gescheitert`
  an; ist schon eins offen, kommt ein Kommentar mit dem Link zum Lauf dazu.
  Wer das Repo beobachtet („Watch“), bekommt das als Benachrichtigung. Ein
  Handstart mit `fehlerprobe` (`gh workflow run orte.yml -R
  LAGGstudio/stepzero-daten -f fehlerprobe=true`) scheitert absichtlich vor
  jedem Abruf und jeder Veröffentlichung und zeigt, dass das Issue entsteht.
- **stand.json:** Jeder erfolgreiche Lauf committet nach der Veröffentlichung
  `stand.json` auf `main` (Job `stand`, nur `contents: write`): Laufdatum,
  Quelle, Datenstand und Zahl der Einträge je Land, Commit als
  `github-actions[bot]`; ohne Änderung kein Commit. Vorher erzeugte ein Lauf
  keinen Commit.
- **60-Tage-Regel:** „In a public repository, scheduled workflows are
  automatically disabled when no repository activity has occurred in 60 days.“
  ([Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
  ebenso [Disabling and enabling a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)).
  Was als „repository activity“ zählt und ob GitHub vorher warnt, sagt die
  Doku nicht (12.11.2026 nachgelesen); ob der Commit von `github-actions[bot]`
  zählt, also auch nicht. Wieder an geht es laut derselben Seite so: „if a user
  with `write` permissions to the repository makes a commit that changes the
  `cron` schedule on the workflow, the workflow will be reactivated“, oder über
  „Enable workflow“ unter Actions.
- **Wer benachrichtigt wird:** „Notifications for scheduled workflows are sent
  to the user who last modified the cron syntax in the workflow file.“
  (Events-Seite) bzw. „… sent to the user who initially created the
  workflow.“ ([Notifications for workflow runs](https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs));
  die Cron-Zeile änderte zuletzt moonblazer420 (12.11.2026).

Lokal: `python3 -m unittest discover -s tests`, `python3 tools/hole_orte.py`,
`python3 tools/pruefe_orte.py ausgabe [vorher]`, `python3 tools/seite_bauen.py`,
`python3 tools/stand.py ausgabe`, `python3 tools/nachholen.py BASIS-URL`.
Bis auf pyosmium für den Auszug nur Python-Standardbibliothek.

### Hauptquelle: Geofabrik-Auszug

Seit dem 10.11.2026 liest `tools/hole_orte.py` den täglichen Auszug von
Geofabrik (`download.geofabrik.de/europe/germany`, `austria`, `switzerland`,
`.osm.pbf`) mit pyosmium (`tools/geofabrik.py`; im Workflow seit dem
12.11.2026 `osmium==4.3.*`, die Version des letzten grünen Laufs 42780352071
war 4.3.2). Seit dem 12.11.2026 muss der Download so lang sein wie
Content-Length und zur `.md5` passen, sonst gilt der Versuch als gescheitert
(auch bei 503; Versuche und Pausen unter „Wiederholung (ohne Rückfall)“).
Geofabrik leitet `-latest.osm.pbf` per 307 weiter, AT und CH auf die Datei mit
Datum (`switzerland-261111.osm.pbf`), DE auf den Spiegel der GWDG; am
12.11.2026 gab `germany-latest.osm.pbf.md5` bei Geofabrik 404, die Spiegel und
die Dateien mit Datum haben eine `.md5`. Seit dem 20.11.2026 liegen die Dateien
bei Geofabrik unter `europe/<land>/<land>-…`; die alte Adresse leitet per 301
dorthin (am selben Tag gegen 11:10 UTC für einige Minuten in einer Schleife,
jede Weiterleitung hängte `/<land>` an, und Dateien mit Datum kamen als 502). Darum gilt zuerst die `.md5` neben der Datei, die
wirklich kam, sonst die neben der `-latest`-Adresse. Fehlt der Zeitstempel im
Auszug, bricht der Lauf ab (bis zum 12.11.2026 setzte er das heutige Datum ein).
Weiter wie bisher:
dieselben Etiketten und Ausschlüsse, bei Wegen und Relationen die Mitte des
umschließenden Rechtecks wie bei Overpass `center`, `stand` aus dem
Zeitstempel des Auszugs. Das OSM-Wiki empfiehlt Auszüge plus osmium
ausdrücklich, wenn man viele Daten braucht. Die Auszüge folgen den Grenzen mit
einem kleinen Saum; die Prüfung fängt nur grobe Ausreißer.

### Wiederholung (ohne Rückfall)

Der zeitgesteuerte Lauf vom 16.11.2026 (43860656823, der erste auf
`ubuntu-24.04`; der Runner stand bei AWS in us-east-1, alle grünen Läufe davor
bei Azure) scheiterte im Schritt „Orte holen“ schon beim Auszug für DE:
dreimal in vier Minuten `<urlopen error [Errno 101] Network is unreachable>`,
jedes Mal sofort. Welche Adresse nicht erreichbar war, steht nicht im
Protokoll: Python meldet von allen Adressen eines Hosts nur den Fehler der
letzten. Seit dem 20.11.2026 deshalb:

- **Auszug:** bis zu fünf Versuche mit wachsender Pause (60, 120, 240, 480 s),
  zusammen höchstens 30 Minuten je Land (`PAUSEN`, `ZEITGRENZE` in
  `tools/geofabrik.py`). Kam gar keine Verbindung zustande, schreibt
  `netz_diagnose` nach dem letzten Versuch je Adresse des Hosts (IPv4, IPv6),
  was der Verbindungsaufbau ergab.
- **Kein Rückfall** (seit Runde 54, 21.11.2026): Bis dahin fragte ein Land,
  dessen Auszug nicht kam, Overpass (`overpass.private.coffee`). Dieser
  Server lieferte am 21.11.2026 Daten, die vier bis sechs Monate alt waren
  (AT Stand 31.05.2026, CH 24.07.2026), auf GitHub lief der Rückfall nie;
  auf Marcels Auftrag ist er ganz entfernt, auch der Handstart mit `ORTE_QUELLE=overpass`
  und die Eingabe `quelle` des Workflows.
- **Scheitert ein Auszug,** endet `hole_orte.py` mit Exit-Code 1: Die
  Schritte danach (Prüfung, Artefakt) laufen nicht, der Job `veroeffentlichen`
  wird übersprungen, online bleibt die alte Fassung, und `melden` legt das
  Issue an. Halbes gibt es nicht: Dateien einzelner Länder, die schon da
  waren, bleiben auf dem Runner. Der Dienstagslauf (unten) holt nach. Der Job
  `bauen` hat eine Obergrenze von 240 Minuten.
- **Woher ein Land kam,** steht im Protokoll („Quelle geofabrik“) und in
  `stand.json` unter `quelle` (seit Runde 54 immer `geofabrik`; bis dahin je
  Land auch `overpass (…)`).

- **Zweiter Lauf dienstags** (seit Runde 52): 24 Stunden nach dem Montagslauf,
  03:23 UTC. Der Job `vorab` liest das Feld `stand` der veröffentlichten
  Dateien (`tools/nachholen.py`); ist keiner älter als 7 Tage, werden alle
  weiteren Jobs übersprungen und der Lauf ist grün, ohne Abruf. Ist einer
  älter oder nicht lesbar (etwa weil der Montagslauf scheiterte), arbeitet
  der Lauf wie montags. Montags und von Hand arbeitet `vorab` nicht, dort gilt
  immer `noetig=true`.

Ein zweiter Server für Auszüge wäre der nähere Rückfall gewesen;
`download.openstreetmap.fr` schließt das selbst aus (`robots.txt`: „Disallow:
/“, am 20.11.2026 gelesen), und der Spiegel der GWDG führt nur DE.

### Sorgsam laden (Geofabrik, „Download responsibly!“)

Geofabriks Blog-Beitrag
[„Download responsibly!“](https://blog.geofabrik.de/index.php/2025/09/10/download-responsibly/)
(Frederik Ramm, 10.09.2025, am 21.11.2026 gelesen) bittet um drei Dinge. So
setzt das Repo sie um (Runde 54):

1. „If you want data for the whole planet, don't download it piecemeal“: passt
   nicht, wir brauchen nur DE, AT und CH.
2. „If you want a large region … updated daily, use … pyosmium-up-to-date“:
   **nicht umgesetzt.** Wir laden drei mittlere Länder einmal pro Woche
   (montags, dienstags nur, wenn der Montag scheiterte), nicht täglich eine
   große Region. Die Aktualisierung bräuchte die Auszüge von Lauf zu Lauf
   (rund 6,2 GB im Cache von GitHub Actions, der Einträge nach 7 Tagen ohne
   Zugriff verwirft, also genau in unserem Takt) und die Ordner
   `*-updates*`, die Geofabriks `robots.txt` für alle User-Agents sperrt.
   Steht im Backlog der App (`docs/claude/backlog.md`).
3. „Monitor what your script is doing or build in appropriate catches so that
   you don't end up downloading the same file 1000 times just because your
   disk is full“: **umgesetzt** in `tools/geofabrik.py`:
   - Was eine Wiederholung nicht heilt, bekommt keine: eine Sperre oder Bremse
     von Geofabrik (401, 403, 429 „Too Many Requests“, `ABLEHNUNG`), zu wenig
     Platz auf dem Runner für die angekündigte Länge plus 64 MB (`RESERVE`,
     geprüft vor dem ersten Byte), ein gescheitertes Schreiben (volle Platte;
     beides `Endgueltig`). Ein 404 wird wiederholt: Im ersten Lauf mit dieser
     Regel (21.11.2026, 01:06 UTC, Lauf 44848127410) gab der Auszug für DE
     einmal 404, und die erste Fassung, die alle 4xx sofort aufgab, ließ den
     Lauf damit scheitern; ein 404 überträgt keine Datei. Jede gescheiterte
     Antwort nennt seitdem die Adresse nach der Weiterleitung.
   - Je Land und Lauf höchstens zweimal die Länge des Auszugs
     (`HOECHSTENS_DOWNLOADS`); eine falsche Prüfsumme kostet so höchstens zwei
     ganze Downloads statt fünf. Abgebrochene Downloads zählen mit ihren Byte.
   - Jeder Versuch schreibt ins Protokoll, wie viel er geladen hat, und am
     Ende steht je Land die Summe („de: … Byte in 1 Versuch(en) geladen“).
   - Weiter wie bisher: kein paralleler Abruf (ein Land nach dem anderen,
     `concurrency: pages` im Workflow), feste Pausen zwischen Versuchen, eine
     Zeitgrenze je Land.

Dazu nennt jeder Abruf des Repos (Geofabrik, GitHub Pages) seit Runde 54
Projekt, Repo-Adresse und Kontakt: `USER_AGENT` in `tools/orte.py`,
`StepZero-Daten/1.0 (+https://github.com/LAGGstudio/stepzero-daten;
info.laggstudio@gmail.com)` (bis dahin ohne Repo-Adresse);
`tests/test_orte.py` (`Kennung`) prüft, dass jede Anfrage im Code sie trägt
und dass sie beim Server ankommt.
