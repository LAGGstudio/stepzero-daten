"""Holt die Orte je Land (DE, AT, CH) aus OpenStreetMap über Overpass und
schreibt ausgabe/<land>.json (kompakt). Nur Python-Standardbibliothek.

  python3 tools/hole_orte.py [ausgabe] [de at ch]
"""
import json, os, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from orte import ARTEN, LAENDER, LIZENZ, eintrag  # noqa: E402

# Private.coffee (vormals overpass.kumi.systems): laut OSM-Wiki „Feel free to
# use our service in any project, there is no rate limit in place“. Die
# Hauptinstanz overpass-api.de war am 9.11.2026 überlastet (502), und das Wiki
# bittet dort regelmäßige und kommerzielle Nutzung, auszuweichen (README).
ENDPUNKT = os.environ.get('OVERPASS_URL', 'https://overpass.private.coffee/api/interpreter')
USER_AGENT = 'StepZero-Daten/1.0 (info.laggstudio@gmail.com)'
ZEITLIMIT = 180
# Wie lange der Client auf die Antwort wartet: Unter Last stellt Overpass
# Anfragen erst in eine Warteschlange, bevor die 180 s der Abfrage laufen.
WARTEN_ANTWORT = 600
WARTEN_WIEDERHOLUNG = 60
PAUSE_LAENDER = 30


def abfrage(land):
    teile = []
    for _, varianten in ARTEN:
        for etiketten in varianten:
            filt = ''.join('["%s"="%s"]' % kv for kv in etiketten.items())
            teile.append('  nwr%s(area.land);' % filt)
    return ('[out:json][timeout:%d];\narea["ISO3166-1"="%s"][admin_level=2]->.land;\n(\n%s\n);\nout center tags;'
            % (ZEITLIMIT, land.upper(), '\n'.join(teile)))


def holen(land):
    daten = urllib.parse.urlencode({'data': abfrage(land)}).encode()
    for versuch in (1, 2):
        try:
            anfrage = urllib.request.Request(ENDPUNKT, data=daten, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(anfrage, timeout=WARTEN_ANTWORT) as antwort:
                return json.load(antwort)
        except Exception as fehler:  # noqa: BLE001
            print('%s: Versuch %d gescheitert: %s' % (land, versuch, fehler), file=sys.stderr)
            if versuch == 1:
                time.sleep(WARTEN_WIEDERHOLUNG)
    raise SystemExit('%s: Overpass nicht erreichbar' % land)


def umwandeln(roh):
    gesehen, eintraege = set(), []
    for element in roh.get('elements', []):
        e = eintrag(element)
        if e and e['id'] not in gesehen:
            gesehen.add(e['id'])
            eintraege.append(e)
    eintraege.sort(key=lambda e: (e['k'], e['id']))
    stand = (roh.get('osm3s', {}).get('timestamp_osm_base') or '')[:10] or time.strftime('%Y-%m-%d', time.gmtime())
    return {'stand': stand, 'lizenz': LIZENZ, 'eintraege': eintraege}


def main():
    ziel = sys.argv[1] if len(sys.argv) > 1 else 'ausgabe'
    laender = sys.argv[2:] or list(LAENDER)
    os.makedirs(ziel, exist_ok=True)
    for i, land in enumerate(laender):
        if i:
            time.sleep(PAUSE_LAENDER)
        anfang = time.time()
        daten = umwandeln(holen(land))
        with open(os.path.join(ziel, land + '.json'), 'w', encoding='utf-8') as f:
            json.dump(daten, f, ensure_ascii=False, separators=(',', ':'))
        print('%s: %d Einträge, Stand %s, %.0f s' % (land, len(daten['eintraege']), daten['stand'], time.time() - anfang))


if __name__ == '__main__':
    main()
