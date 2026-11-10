"""Holt die Orte je Land (DE, AT, CH) aus OpenStreetMap und schreibt
ausgabe/<land>.json (kompakt), doppelte Einträge zusammengeführt.

Hauptquelle ist seit dem 10.11.2026 der tägliche Geofabrik-Auszug
(tools/geofabrik.py, braucht pyosmium: `pip install osmium`). Overpass bleibt
für einen Handstart mit ORTE_QUELLE=overpass (nur Standardbibliothek, ohne
Rückfall): Am 9.11.2026 war Overpass in allen Läufen überlastet oder lieferte
veraltete Daten.

  python3 tools/hole_orte.py [ausgabe] [de at ch]
  ORTE_QUELLE=overpass python3 tools/hole_orte.py
"""
import json, os, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from orte import ART_NAMEN, ARTEN, LAENDER, LIZENZ, doppelte_zusammenfuehren, eintrag  # noqa: E402

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
# Eine Antwort taugt nur, wenn ihr Datenstand höchstens so alt ist: Am
# 9.11.2026 lieferte overpass.private.coffee Daten vom Juni 2026.
MAX_ALTER_TAGE = 7


class Unbrauchbar(SystemExit):
    """Overpass hat geantwortet, aber nicht brauchbar (Fehlerhinweis, leer,
    veraltet); dann gilt der Rückfall, ohne zweiten Versuch."""


def brauchbar(land, roh, heute=None):
    """Wirft Unbrauchbar bei `remark` mit Fehler, ohne Elemente oder mit einem
    Datenstand älter als MAX_ALTER_TAGE."""
    import datetime
    remark = roh.get('remark') or ''
    if 'error' in remark.lower():
        raise Unbrauchbar('%s: Overpass meldet %s' % (land, remark[:200]))
    if not roh.get('elements'):
        raise Unbrauchbar('%s: Overpass lieferte keine Elemente' % land)
    basis = (roh.get('osm3s', {}).get('timestamp_osm_base') or '')[:10]
    heute = heute or datetime.date.today()
    try:
        alter = (heute - datetime.date.fromisoformat(basis)).days
    except ValueError:
        raise Unbrauchbar('%s: Overpass ohne Datenstand' % land)
    if alter > MAX_ALTER_TAGE:
        raise Unbrauchbar('%s: Overpass-Datenstand %s ist %d Tage alt' % (land, basis, alter))


def abfrage(land):
    teile = []
    for _, varianten in ARTEN:
        for etiketten in varianten:
            filt = ''.join('["%s"="%s"]' % kv for kv in etiketten.items())
            teile.append('  nwr%s(area.land);' % filt)
    return ('[out:json][timeout:%d];\narea["ISO3166-1"="%s"][admin_level=2]->.land;\n(\n%s\n);\nout center tags;'
            % (ZEITLIMIT, land.upper(), '\n'.join(teile)))


QUELLEN = ('geofabrik', 'overpass')


def holen(land):
    """Geofabrik-Auszug, mit ORTE_QUELLE=overpass stattdessen Overpass."""
    quelle = os.environ.get('ORTE_QUELLE') or 'geofabrik'
    if quelle == 'geofabrik':
        import geofabrik
        return geofabrik.holen(land)
    if quelle == 'overpass':
        return overpass_holen(land)
    raise SystemExit('ORTE_QUELLE %r unbekannt (%s)' % (quelle, ' oder '.join(QUELLEN)))


def overpass_holen(land):
    daten = urllib.parse.urlencode({'data': abfrage(land)}).encode()
    for versuch in (1, 2):
        try:
            anfrage = urllib.request.Request(ENDPUNKT, data=daten, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(anfrage, timeout=WARTEN_ANTWORT) as antwort:
                roh = json.load(antwort)
            brauchbar(land, roh)
            return roh
        except Unbrauchbar:
            raise
        except Exception as fehler:  # noqa: BLE001
            print('%s: Versuch %d gescheitert: %s' % (land, versuch, fehler), file=sys.stderr)
            if versuch == 1:
                time.sleep(WARTEN_WIEDERHOLUNG)
    raise SystemExit('%s: Overpass nicht erreichbar' % land)


def umwandeln(roh):
    """Overpass-artiges Ergebnis → (Datei, Anzahl zusammengeführter je Art)."""
    gesehen, eintraege = set(), []
    for element in roh.get('elements', []):
        e = eintrag(element)
        if e and e['id'] not in gesehen:
            gesehen.add(e['id'])
            eintraege.append(e)
    eintraege.sort(key=lambda e: (e['k'], e['id']))
    eintraege, zusammengefuehrt = doppelte_zusammenfuehren(eintraege)
    stand = (roh.get('osm3s', {}).get('timestamp_osm_base') or '')[:10] or time.strftime('%Y-%m-%d', time.gmtime())
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


def main():
    ziel = sys.argv[1] if len(sys.argv) > 1 else 'ausgabe'
    laender = sys.argv[2:] or list(LAENDER)
    os.makedirs(ziel, exist_ok=True)
    for i, land in enumerate(laender):
        if i and os.environ.get('ORTE_QUELLE') == 'overpass':
            time.sleep(PAUSE_LAENDER)
        anfang = time.time()
        daten, zusammengefuehrt = umwandeln(holen(land))
        with open(os.path.join(ziel, land + '.json'), 'w', encoding='utf-8') as f:
            json.dump(daten, f, ensure_ascii=False, separators=(',', ':'))
        print('%s: %d Einträge, Stand %s, %.0f s' % (land, len(daten['eintraege']), daten['stand'], time.time() - anfang))
        print('\n'.join(zusammenfassung(land, daten, zusammengefuehrt)))


if __name__ == '__main__':
    main()
