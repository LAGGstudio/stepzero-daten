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

Auf GitHub Pages (nicht im Repo): `de.json`, `at.json`, `ch.json` und eine
Übersicht `index.html`. Jede Datei ist kompaktes JSON:

```json
{"stand":"2026-11-09","lizenz":"ODbL 1.0, © OpenStreetMap-Mitwirkende, https://www.openstreetmap.org/copyright",
 "eintraege":[{"id":"n123","k":"buecherschrank","lat":50.93759,"lon":6.96016,"name":"…","adresse":"Ring 1, 50667 Köln","oeffnung":"24/7"}]}
```

`id`: OSM-Typ (`n`, `w`, `r`) und Nummer. `k`: Art. `lat`, `lon`: 5
Nachkommastellen, bei Wegen und Relationen die Mitte. `name`, `adresse`
(Straße Nr, PLZ Ort) und `oeffnung` (`opening_hours` roh) nur, wenn vorhanden.

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

## Ablauf

GitHub Actions (`.github/workflows/orte.yml`) läuft montags um 03:00 UTC und
per Hand: Tests, je Land eine Overpass-Abfrage (`tools/hole_orte.py`, Server
`overpass.private.coffee`, änderbar über `OVERPASS_URL`,
User-Agent `StepZero-Daten/1.0 (info.laggstudio@gmail.com)`, Zeitlimit 180 s,
eine Wiederholung nach 60 s, Pause zwischen den Ländern), Prüfung gegen die
veröffentlichte Fassung (`tools/pruefe_orte.py`: Schema, Koordinaten im Land,
höchstens 8 MB, keine Art fällt um mehr als 30 %), dann die Übersicht und die
Veröffentlichung auf GitHub Pages. Schlägt die Prüfung fehl, bleibt die alte
Fassung online.

Lokal: `python3 -m unittest discover -s tests`, `python3 tools/hole_orte.py`,
`python3 tools/pruefe_orte.py ausgabe [vorher]`, `python3 tools/seite_bauen.py`.
Nur Python-Standardbibliothek.

### Warum nicht overpass-api.de

Die Hauptinstanz war beim ersten Lauf am 9.11.2026 überlastet (Zeitüberschreitung,
dann 502 „at capacity … intended for browser-based and human-operated tools“).
Das [OSM-Wiki](https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances)
bittet dort bei regelmäßiger Nutzung um ein Hundertstel der üblichen Grenzen und
schreibt „Commercial use should use self-hosted or paid Overpass servers“; Step Zero
verkauft Pro. Private.coffee schreibt im selben Wiki: „Feel free to use our
service in any project, there is no rate limit in place. Please notify us in
advance if you intend to use our service in a large scale project.“ Drei Abfragen
pro Woche sind kein großes Projekt. Wächst der Bedarf: eigene Instanz oder
Geofabrik-Auszüge mit osmium (ebenfalls im Wiki empfohlen).
