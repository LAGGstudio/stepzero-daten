"""Holt die Orte je Land (DE, AT, CH) aus OpenStreetMap und schreibt
ausgabe/<land>.json (kompakt), doppelte Einträge zusammengeführt.

Einzige Quelle ist der tägliche Geofabrik-Auszug (tools/geofabrik.py, braucht
pyosmium: `pip install osmium`; Hauptquelle seit dem 10.11.2026). Der
Rückfall auf Overpass ist seit Runde 54 ganz entfernt: Der letzte Server
dafür lieferte am 21.11.2026 Daten, die vier bis sechs Monate alt waren
(README, „Wiederholung“). Kommt ein Auszug nach allen Versuchen nicht, endet der Lauf
mit Exit-Code 1, nichts wird veröffentlicht, online bleibt der alte Stand, und
der Dienstagslauf holt nach.

  python3 tools/hole_orte.py [ausgabe] [de at ch]
"""
import collections, json, os, re, sys, time

sys.path.insert(0, os.path.dirname(__file__))
from orte import ART_NAMEN, LAENDER, LIZENZ, doppelte_zusammenfuehren, eintrag  # noqa: E402

# Woher jedes Land in diesem Lauf kam, für das Protokoll und stand.json; seit
# Runde 54 immer 'geofabrik' (bis dahin auch 'overpass (<Server>)').
genutzt = {}


def holen(land):
    """Der Geofabrik-Auszug des Lands; scheitert er, geofabrik.Gescheitert
    (ein SystemExit mit Exit-Code ungleich 0), ohne Rückfall."""
    import geofabrik
    roh = geofabrik.holen(land)
    genutzt[land] = 'geofabrik'
    return roh


def umwandeln(roh, land=''):
    """Ergebnis von geofabrik.elemente (im Format, das früher Overpass mit
    `out center tags` lieferte) → (Datei, Anzahl zusammengeführter je Art).
    Ohne Datenstand bricht es ab (seit dem 12.11.2026, Audit 11.5); vorher
    setzte es das heutige Datum ein."""
    stand = (roh.get('osm3s', {}).get('timestamp_osm_base') or '')[:10]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', stand):
        raise SystemExit('%s: ohne Datenstand (Zeitstempel des Auszugs), '
                         'nichts geschrieben' % (land or '?'))
    gesehen, eintraege = set(), []
    for element in roh.get('elements', []):
        e = eintrag(element)
        if e and e['id'] not in gesehen:
            gesehen.add(e['id'])
            eintraege.append(e)
    eintraege.sort(key=lambda e: (e['k'], e['id']))
    eintraege, zusammengefuehrt = doppelte_zusammenfuehren(eintraege)
    return {'stand': stand, 'lizenz': LIZENZ, 'eintraege': eintraege}, zusammengefuehrt


def zusammenfassung(land, daten, zusammengefuehrt):
    """Zeilen für das Protokoll: je Art die Anzahl und wie viele zusammengeführt."""
    zeilen = []
    for k in ART_NAMEN:
        n = sum(1 for e in daten['eintraege'] if e['k'] == k)
        zeilen.append('%s:   %-15s %6d  (%d zusammengeführt)' % (land, k, n, zusammengefuehrt.get(k, 0)))
    zeilen.append('%s:   %-15s %6d  (%d zusammengeführt)'
                  % (land, 'zusammen', len(daten['eintraege']), sum(zusammengefuehrt.values())))
    return zeilen


def maerkte_zaehlen(roh, daten):
    """Runde 54, Block B: Marktplätze im Auszug (amenity=marketplace, ohne
    access=private/no und Aufgegebenes, das schon geofabrik.elemente
    weglässt), davon mit Name und mit Öffnungszeiten; aufgenommen (mit Name
    oder Öffnungszeiten, nach dem Zusammenführen) und davon mit lesbaren
    Öffnungszeiten; dazu die häufigsten nicht lesbaren Angaben."""
    roh_maerkte = [el.get('tags') or {} for el in roh.get('elements', [])
                   if (el.get('tags') or {}).get('amenity') == 'marketplace']
    maerkte = [e for e in daten['eintraege'] if e['k'] == 'markt']
    mit_oeffnung = [e for e in maerkte if 'oeffnung' in e]
    return {
        'gesamt': len(roh_maerkte),
        'mit_name': sum(1 for t in roh_maerkte if t.get('name')),
        'mit_oeffnung': sum(1 for t in roh_maerkte if t.get('opening_hours')),
        'aufgenommen': len(maerkte),
        'aufgenommen_mit_oeffnung': len(mit_oeffnung),
        'lesbar': sum(1 for e in mit_oeffnung if 'zeiten' in e),
        'nicht_lesbar': collections.Counter(e['oeffnung'] for e in mit_oeffnung if 'zeiten' not in e).most_common(10),
    }


def maerkte_zeilen(land, z):
    """Die Zahlen aus maerkte_zaehlen fürs Protokoll."""
    anteil = 100 * z['lesbar'] / z['aufgenommen_mit_oeffnung'] if z['aufgenommen_mit_oeffnung'] else 0
    zeilen = ['%s: Märkte im Auszug %d, mit Name %d, mit Öffnungszeiten %d; aufgenommen %d, davon mit '
              'Öffnungszeiten %d, lesbar %d (%.0f %%)'
              % (land, z['gesamt'], z['mit_name'], z['mit_oeffnung'], z['aufgenommen'],
                 z['aufgenommen_mit_oeffnung'], z['lesbar'], anteil)]
    for text, n in z['nicht_lesbar']:
        zeilen.append('%s:   nicht lesbar %4d× %s' % (land, n, text[:120]))
    return zeilen


def main():
    ziel = sys.argv[1] if len(sys.argv) > 1 else 'ausgabe'
    laender = sys.argv[2:] or list(LAENDER)
    os.makedirs(ziel, exist_ok=True)
    for land in laender:
        anfang = time.time()
        roh = holen(land)
        daten, zusammengefuehrt = umwandeln(roh, land)
        with open(os.path.join(ziel, land + '.json'), 'w', encoding='utf-8') as f:
            json.dump(daten, f, ensure_ascii=False, separators=(',', ':'))
        print('%s: %d Einträge, Stand %s, Quelle %s, %.0f s'
              % (land, len(daten['eintraege']), daten['stand'], genutzt.get(land, '?'), time.time() - anfang))
        print('\n'.join(zusammenfassung(land, daten, zusammengefuehrt)))
        print('\n'.join(maerkte_zeilen(land, maerkte_zaehlen(roh, daten))))
    # Woher jedes Land kam, für stand.json (tools/stand.py); nicht in den
    # Ordner mit den veröffentlichten Dateien.
    if os.environ.get('ORTE_QUELLEN_DATEI'):
        with open(os.environ['ORTE_QUELLEN_DATEI'], 'w', encoding='utf-8') as f:
            json.dump({land: genutzt.get(land, '?') for land in laender}, f, ensure_ascii=False)


if __name__ == '__main__':
    main()
