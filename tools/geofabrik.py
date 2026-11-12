"""Hauptquelle für tools/hole_orte.py (seit dem 10.11.2026, vorher Rückfall):
die Orte eines Lands aus dem Geofabrik-Auszug (.osm.pbf), gelesen mit pyosmium
(`pip install osmium`).

Das OSM-Wiki empfiehlt Auszüge plus osmium, wenn man viele Daten braucht oder
die öffentlichen Overpass-Server überlastet sind (am 9.11.2026 alle drei).
Liefert dasselbe Format wie Overpass (`elements` mit `tags`, bei Wegen und
Relationen `center` als Mitte des umschließenden Rechtecks), damit dieselbe
Umwandlung (`hole_orte.umwandeln`) und dieselbe Prüfung greifen.

Der Download (seit dem 12.11.2026, Audit 11.5) muss so lang sein wie
Content-Length und zur .md5 passen, sonst gilt er als gescheitert; bis zu
VERSUCHE Versuche mit PAUSE dazwischen. Geofabrik leitet `-latest.osm.pbf`
per 307 weiter (AT, CH auf die Datei mit Datum, DE auf den Spiegel der GWDG;
am 12.11.2026 gab `germany-latest.osm.pbf.md5` bei Geofabrik 404), darum gilt
zuerst die .md5 neben der Datei, die wirklich kam, sonst die neben der
`-latest`-Adresse.
"""
import hashlib, http.client, os, re, sys, tempfile, time, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from orte import ARTEN, art, ausgeschlossen  # noqa: E402

REGION = {'de': 'europe/germany', 'at': 'europe/austria', 'ch': 'europe/switzerland'}
QUELLE = 'https://download.geofabrik.de/%s-latest.osm.pbf'
USER_AGENT = 'StepZero-Daten/1.0 (info.laggstudio@gmail.com)'

# Alle Etiketten aus ARTEN als (Schlüssel, Wert) für den Filter in C++; was
# genau passt (etwa garden:type=community), entscheidet danach `art`.
ETIKETTEN = sorted({kv for _, varianten in ARTEN for etiketten in varianten for kv in etiketten.items()})


VERSUCHE = 3
PAUSE = 120  # Sekunden zwischen zwei Versuchen


class Unvollstaendig(Exception):
    """Ein Versuch lieferte nicht die ganze Datei (Länge, Prüfsumme)."""


def _md5_lesen(url):
    anfrage = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(anfrage, timeout=60) as a:
        text = a.read(4096).decode('ascii', 'replace')
    treffer = re.match(r'\s*([0-9a-f]{32})\b', text)
    if not treffer:
        raise Unvollstaendig('%s: keine Prüfsumme' % url)
    return treffer.group(1)


def _pruefsumme(ende, url):
    """Die .md5 neben der Datei, die wirklich kam, sonst die neben `url`."""
    for kandidat in dict.fromkeys((ende + '.md5', url + '.md5')):
        try:
            return _md5_lesen(kandidat)
        except urllib.error.HTTPError as fehler:
            if fehler.code != 404:
                raise
    raise Unvollstaendig('keine .md5 zu %s' % ende)


def _einmal_laden(url, ziel):
    """Lädt `url` nach `ziel` und gibt (Adresse nach Weiterleitungen, md5)
    zurück; zu kurz oder ohne Content-Length: Unvollstaendig. Pythons
    `read(amt)` meldet einen abgebrochenen Download nicht selbst."""
    anfrage = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    summe, n = hashlib.md5(), 0
    with urllib.request.urlopen(anfrage, timeout=120) as a, open(ziel, 'wb') as d:
        laenge = a.headers.get('Content-Length')
        if laenge is None or not laenge.strip().isdigit():
            raise Unvollstaendig('ohne Content-Length')
        while True:
            stueck = a.read(1 << 20)
            if not stueck:
                break
            d.write(stueck)
            summe.update(stueck)
            n += len(stueck)
        ende = a.geturl()
    if n != int(laenge):
        raise Unvollstaendig('%d von %s Byte' % (n, laenge.strip()))
    return ende, summe.hexdigest()


def laden(land, ziel, quelle=QUELLE, versuche=VERSUCHE, pause=PAUSE):
    """Lädt den Auszug nach `ziel` (Datei), in Stücken, geprüft gegen
    Content-Length und .md5; bis zu `versuche` Versuche. Gibt die Adresse
    zurück, von der er kam."""
    url = quelle % REGION[land]
    for versuch in range(1, versuche + 1):
        try:
            ende, summe = _einmal_laden(url, ziel)
            erwartet = _pruefsumme(ende, url)
            if summe != erwartet:
                raise Unvollstaendig('Prüfsumme %s, erwartet %s' % (summe, erwartet))
            return ende
        except (Unvollstaendig, OSError, http.client.HTTPException) as fehler:
            print('%s: Versuch %d von %d gescheitert: %s' % (land, versuch, versuche, fehler), file=sys.stderr)
            if versuch < versuche:
                time.sleep(pause)
    raise SystemExit('%s: Geofabrik-Auszug nach %d Versuchen nicht vollständig' % (land, versuche))


def _mitte(punkte):
    if not punkte:
        return None
    lats = [p[0] for p in punkte]
    lons = [p[1] for p in punkte]
    return {'lat': (min(lats) + max(lats)) / 2, 'lon': (min(lons) + max(lons)) / 2}


def elemente(pfad):
    """Liest den Auszug in vier Durchgängen und liefert ein Overpass-artiges
    Ergebnis {'osm3s': {'timestamp_osm_base': …}, 'elements': […]}."""
    import osmium
    from osmium.filter import IdFilter, TagFilter

    tagfilter = TagFilter(*ETIKETTEN)
    kopf = osmium.io.Reader(pfad, osmium.osm.NOTHING)
    stand = kopf.header().get('osmosis_replication_timestamp') or ''
    kopf.close()

    # 1. Wege und Relationen mit unseren Etiketten.
    wege, relationen = {}, {}
    for o in osmium.FileProcessor(pfad, osmium.osm.WAY | osmium.osm.RELATION).with_filter(tagfilter):
        tags = {t.k: t.v for t in o.tags}
        if ausgeschlossen(tags) or art(tags) is None:
            continue
        if o.is_way():
            wege[o.id] = (tags, [n.ref for n in o.nodes])
        else:
            relationen[o.id] = (tags, [m.ref for m in o.members if m.type == 'w'],
                                [m.ref for m in o.members if m.type == 'n'])
    # 2. Die Wege, aus denen die Relationen bestehen.
    teilwege = {}
    gesucht = {w for _, ws, _ in relationen.values() for w in ws}
    if gesucht:
        for o in osmium.FileProcessor(pfad, osmium.osm.WAY).with_filter(IdFilter(gesucht)):
            teilwege[o.id] = [n.ref for n in o.nodes]
    # 3. Knoten mit unseren Etiketten.
    knoten = []
    for o in osmium.FileProcessor(pfad, osmium.osm.NODE).with_filter(tagfilter):
        tags = {t.k: t.v for t in o.tags}
        if ausgeschlossen(tags) or art(tags) is None or not o.location.valid():
            continue
        knoten.append({'type': 'node', 'id': o.id, 'lat': o.location.lat, 'lon': o.location.lon, 'tags': tags})
    # 4. Koordinaten der Knoten, die Wege und Relationen brauchen.
    noetig = {n for _, ns in wege.values() for n in ns}
    noetig |= {n for ns in teilwege.values() for n in ns}
    noetig |= {n for _, _, ns in relationen.values() for n in ns}
    lage = {}
    if noetig:
        for o in osmium.FileProcessor(pfad, osmium.osm.NODE).with_filter(IdFilter(noetig)):
            if o.location.valid():
                lage[o.id] = (o.location.lat, o.location.lon)
    raus = list(knoten)
    for wid, (tags, ns) in wege.items():
        m = _mitte([lage[n] for n in ns if n in lage])
        if m:
            raus.append({'type': 'way', 'id': wid, 'center': m, 'tags': tags})
    for rid, (tags, ws, ns) in relationen.items():
        punkte = [lage[n] for w in ws for n in teilwege.get(w, []) if n in lage]
        punkte += [lage[n] for n in ns if n in lage]
        m = _mitte(punkte)
        if m:
            raus.append({'type': 'relation', 'id': rid, 'center': m, 'tags': tags})
    return {'osm3s': {'timestamp_osm_base': stand}, 'elements': raus}


def holen(land):
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, land + '.osm.pbf')
        anfang = time.time()
        ende = laden(land, pfad)
        print('%s: Geofabrik-Auszug %d Byte in %.0f s, Länge und md5 geprüft (%s)'
              % (land, os.path.getsize(pfad), time.time() - anfang, ende))
        anfang = time.time()
        roh = elemente(pfad)
        print('%s: %d Elemente gelesen in %.0f s' % (land, len(roh['elements']), time.time() - anfang))
        return roh
