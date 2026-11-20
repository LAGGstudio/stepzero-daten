"""Holt die Orte je Land (DE, AT, CH) aus OpenStreetMap und schreibt
ausgabe/<land>.json (kompakt), doppelte Einträge zusammengeführt.

Hauptquelle ist seit dem 10.11.2026 der tägliche Geofabrik-Auszug
(tools/geofabrik.py, braucht pyosmium: `pip install osmium`). Kommt er nach
allen Versuchen nicht (am 16.11.2026: dreimal „Network is unreachable“),
fällt das Land seit dem 20.11.2026 auf Overpass zurück (seit Runde 52
nur overpass.private.coffee). Mit ORTE_QUELLE=overpass läuft nur Overpass (Handstart,
nur Standardbibliothek, ohne Rückfall auf den Auszug). Scheitert auch das,
endet der Lauf mit Exit-Code 1, und nichts wird veröffentlicht.

  python3 tools/hole_orte.py [ausgabe] [de at ch]
  ORTE_QUELLE=overpass python3 tools/hole_orte.py
"""
import json, os, re, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from orte import ART_NAMEN, ARTEN, LAENDER, LIZENZ, doppelte_zusammenfuehren, eintrag  # noqa: E402

# Private.coffee (vormals overpass.kumi.systems): laut OSM-Wiki „Feel free to
# use our service in any project, there is no rate limit in place“. Die
# Hauptinstanz overpass-api.de war am 9.11.2026 überlastet (502), und das Wiki
# bittet dort regelmäßige und kommerzielle Nutzung, auszuweichen (README).
#
# Am 20.11.2026 stand dahinter kurz als zweiter Server die Instanz von VK
# Maps (maps.mail.ru); Marcel hat sie herausgenommen (Runde 52, Block D).
# OVERPASS_URL (eine oder mehrere Adressen, durch Leerzeichen getrennt,
# nacheinander, nie gleichzeitig) ersetzt die Liste für einen Handstart.
ENDPUNKTE = tuple((os.environ.get('OVERPASS_URL') or '').split()) or (
    'https://overpass.private.coffee/api/interpreter',
)
USER_AGENT = 'StepZero-Daten/1.0 (info.laggstudio@gmail.com)'
ZEITLIMIT = 180
# Wie lange der Client auf die Antwort wartet: Unter Last stellt Overpass
# Anfragen erst in eine Warteschlange, bevor die 180 s der Abfrage laufen.
WARTEN_ANTWORT = 600
# Pausen in Sekunden nach dem 1. und 2. gescheiterten Versuch je Server (drei
# Versuche; das Wiki bittet nach 429 oder 406 um mindestens 30 s). Bis zum
# 20.11.2026 zwei Versuche mit 60 s Pause an einem Server.
OVERPASS_PAUSEN = (30, 90)
# Je Land für alle Server zusammen: Danach beginnt kein neuer Versuch.
OVERPASS_ZEITGRENZE = 20 * 60
PAUSE_LAENDER = 30
# Eine Antwort taugt nur, wenn ihr Datenstand höchstens so alt ist: Am
# 9.11.2026 lieferte overpass.private.coffee Daten vom Juni 2026.
MAX_ALTER_TAGE = 7


class Unbrauchbar(SystemExit):
    """Overpass hat geantwortet, aber nicht brauchbar (Fehlerhinweis, leer,
    veraltet); dann kommt ohne zweiten Versuch der nächste Server."""


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

# Woher jedes Land in diesem Lauf wirklich kam: 'geofabrik' oder
# 'overpass (<Server>)'; für das Protokoll und stand.json.
genutzt = {}


def holen(land):
    """Geofabrik-Auszug; kommt er nach allen Versuchen nicht, Overpass als
    Rückfall. Mit ORTE_QUELLE=overpass nur Overpass."""
    quelle = os.environ.get('ORTE_QUELLE') or 'geofabrik'
    if quelle == 'geofabrik':
        import geofabrik
        try:
            roh = geofabrik.holen(land)
        except geofabrik.Gescheitert as fehler:
            print('%s; Rückfall auf Overpass' % fehler, file=sys.stderr)
            return overpass_holen(land)
        genutzt[land] = 'geofabrik'
        return roh
    if quelle == 'overpass':
        return overpass_holen(land)
    raise SystemExit('ORTE_QUELLE %r unbekannt (%s)' % (quelle, ' oder '.join(QUELLEN)))


def _overpass_einmal(endpunkt, daten):
    anfrage = urllib.request.Request(endpunkt, data=daten, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(anfrage, timeout=WARTEN_ANTWORT) as antwort:
        return json.load(antwort)


def overpass_holen(land, endpunkte=None, pausen=OVERPASS_PAUSEN, grenze=OVERPASS_ZEITGRENZE,
                   schlafen=None, uhr=None):
    """Fragt die Server nacheinander: je Server ein Versuch mehr als `pausen`,
    mit wachsender Pause; eine unbrauchbare Antwort (Unbrauchbar) führt gleich
    zum nächsten Server. Alles zusammen höchstens `grenze` Sekunden, danach
    beginnt kein neuer Versuch. Taugt keine Antwort, SystemExit (war die
    letzte unbrauchbar, Unbrauchbar)."""
    endpunkte = endpunkte or ENDPUNKTE
    schlafen, uhr = schlafen or time.sleep, uhr or time.monotonic
    daten = urllib.parse.urlencode({'data': abfrage(land)}).encode()
    versuche = len(pausen) + 1
    anfang = uhr()
    letzter = None
    zeit_um = False
    for endpunkt in endpunkte:
        server = urllib.parse.urlsplit(endpunkt).hostname
        for versuch in range(1, versuche + 1):
            try:
                roh = _overpass_einmal(endpunkt, daten)
                brauchbar(land, roh)
                genutzt[land] = 'overpass (%s)' % server
                return roh
            except Unbrauchbar as fehler:
                letzter = fehler
                # Die Meldung nennt das Land schon selbst.
                print('%s: %s' % (server, fehler), file=sys.stderr)
                break
            except Exception as fehler:  # noqa: BLE001
                letzter = fehler
                print('%s: %s: Versuch %d von %d gescheitert: %s' % (land, server, versuch, versuche, fehler),
                      file=sys.stderr)
            if versuch == versuche:
                break
            pause = pausen[versuch - 1]
            if uhr() - anfang + pause > grenze:
                zeit_um = True
                break
            schlafen(pause)
        if zeit_um or uhr() - anfang > grenze:
            print('%s: Zeitgrenze von %d s für Overpass erreicht' % (land, grenze), file=sys.stderr)
            break
    if isinstance(letzter, Unbrauchbar):
        raise letzter
    raise SystemExit('%s: Overpass nicht erreichbar (%s)'
                     % (land, ', '.join(urllib.parse.urlsplit(e).hostname for e in endpunkte)))


def umwandeln(roh, land=''):
    """Overpass-artiges Ergebnis → (Datei, Anzahl zusammengeführter je Art).
    Ohne Datenstand bricht es ab (seit dem 12.11.2026, Audit 11.5); vorher
    setzte es das heutige Datum ein."""
    stand = (roh.get('osm3s', {}).get('timestamp_osm_base') or '')[:10]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', stand):
        raise SystemExit('%s: ohne Datenstand (Zeitstempel des Auszugs bzw. von Overpass), '
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


def main():
    ziel = sys.argv[1] if len(sys.argv) > 1 else 'ausgabe'
    laender = sys.argv[2:] or list(LAENDER)
    os.makedirs(ziel, exist_ok=True)
    for i, land in enumerate(laender):
        if i and os.environ.get('ORTE_QUELLE') == 'overpass':
            time.sleep(PAUSE_LAENDER)
        anfang = time.time()
        daten, zusammengefuehrt = umwandeln(holen(land), land)
        with open(os.path.join(ziel, land + '.json'), 'w', encoding='utf-8') as f:
            json.dump(daten, f, ensure_ascii=False, separators=(',', ':'))
        print('%s: %d Einträge, Stand %s, Quelle %s, %.0f s'
              % (land, len(daten['eintraege']), daten['stand'], genutzt.get(land, '?'), time.time() - anfang))
        print('\n'.join(zusammenfassung(land, daten, zusammengefuehrt)))
    # Woher jedes Land kam, für stand.json (tools/stand.py); nicht in den
    # Ordner mit den veröffentlichten Dateien.
    if os.environ.get('ORTE_QUELLEN_DATEI'):
        with open(os.environ['ORTE_QUELLEN_DATEI'], 'w', encoding='utf-8') as f:
            json.dump({land: genutzt.get(land, '?') for land in laender}, f, ensure_ascii=False)


if __name__ == '__main__':
    main()
