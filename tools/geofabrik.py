"""Hauptquelle für tools/hole_orte.py (seit dem 10.11.2026, vorher Rückfall):
die Orte eines Lands aus dem Geofabrik-Auszug (.osm.pbf), gelesen mit pyosmium
(`pip install osmium`).

Das OSM-Wiki empfiehlt Auszüge plus osmium, wenn man viele Daten braucht oder
die öffentlichen Overpass-Server überlastet sind (am 9.11.2026 alle drei).
Liefert dasselbe Format wie Overpass (`elements` mit `tags`, bei Wegen und
Relationen `center` als Mitte des umschließenden Rechtecks), damit dieselbe
Umwandlung (`hole_orte.umwandeln`) und dieselbe Prüfung greifen.

Der Download (seit dem 12.11.2026, Audit 11.5) muss so lang sein wie
Content-Length und zur .md5 passen, sonst gilt er als gescheitert. Geofabrik
leitet `-latest.osm.pbf` weiter (AT, CH auf die Datei mit Datum, DE auf den
Spiegel der GWDG; am 12.11.2026 gab `germany-latest.osm.pbf.md5` bei Geofabrik
404; seit dem 20.11.2026 zuerst per 301 auf `europe/<land>/<land>-latest…`),
darum gilt zuerst die .md5 neben der Datei, die wirklich kam, sonst die neben
der `-latest`-Adresse.

Seit dem 20.11.2026 (der Lauf vom 16.11.2026 scheiterte nach drei Versuchen
in vier Minuten, jedes Mal sofort mit „Network is unreachable“): bis zu fünf
Versuche mit wachsender Pause (PAUSEN), zusammen höchstens ZEITGRENZE; nach
einem Verbindungsfehler schreibt `netz_diagnose` je Adresse des Hosts, was
der Verbindungsaufbau ergab. Scheitert alles, wirft `laden` Gescheitert, und
`hole_orte.holen` fällt auf Overpass zurück.
"""
import hashlib, http.client, os, re, socket, sys, tempfile, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from orte import ARTEN, art, ausgeschlossen  # noqa: E402

REGION = {'de': 'europe/germany', 'at': 'europe/austria', 'ch': 'europe/switzerland'}
QUELLE = 'https://download.geofabrik.de/%s-latest.osm.pbf'
USER_AGENT = 'StepZero-Daten/1.0 (info.laggstudio@gmail.com)'

# Alle Etiketten aus ARTEN als (Schlüssel, Wert) für den Filter in C++; was
# genau passt (etwa garden:type=community), entscheidet danach `art`.
ETIKETTEN = sorted({kv for _, varianten in ARTEN for etiketten in varianten for kv in etiketten.items()})


# Pausen in Sekunden nach dem 1., 2., 3. und 4. gescheiterten Versuch, also
# bis zu fünf Versuche; bis zum 20.11.2026 drei Versuche mit je 120 s.
PAUSEN = (60, 120, 240, 480)
# Je Land für alle Versuche zusammen: Würde die nächste Pause darüber
# hinausführen, gibt es keinen weiteren Versuch (ein Download von DE dauerte
# in den Läufen bis zum 13.11.2026 zwischen 31 und 388 s).
ZEITGRENZE = 30 * 60


class Unvollstaendig(Exception):
    """Ein Versuch lieferte nicht die ganze Datei (Länge, Prüfsumme)."""


class Gescheitert(SystemExit):
    """Der Auszug kam nach allen Versuchen nicht vollständig; ohne Rückfall
    endet der Lauf damit (Exit-Code ungleich 0)."""


def netz_diagnose(url, aus=None, warten=10):
    """Nach einem Verbindungsfehler: jede Adresse des Hosts einzeln. Python
    meldet von allen Adressen nur den Fehler der letzten; am 16.11.2026 stand
    so nur „Network is unreachable“ im Protokoll, ohne Host und ohne Adresse."""
    aus = aus or sys.stderr
    teile = urllib.parse.urlsplit(url)
    host, port = teile.hostname, teile.port or (443 if teile.scheme == 'https' else 80)
    try:
        adressen = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as fehler:
        print('Diagnose %s: Namensauflösung gescheitert: %s' % (host, fehler), file=aus)
        return
    for familie, typ, proto, _, adresse in adressen:
        s = socket.socket(familie, typ, proto)
        s.settimeout(warten)
        try:
            s.connect(adresse)
            ergebnis = 'Verbindung steht'
        except OSError as fehler:
            ergebnis = str(fehler)
        finally:
            s.close()
        print('Diagnose %s: %s %s Port %d: %s'
              % (host, 'IPv6' if familie == socket.AF_INET6 else 'IPv4', adresse[0], port, ergebnis), file=aus)


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


def laden(land, ziel, quelle=QUELLE, pausen=PAUSEN, grenze=ZEITGRENZE, schlafen=None, uhr=None):
    """Lädt den Auszug nach `ziel` (Datei), in Stücken, geprüft gegen
    Content-Length und .md5; ein Versuch mehr als `pausen`, nach dem n-ten
    gescheiterten `pausen[n-1]` Sekunden Pause, alles zusammen höchstens
    `grenze` Sekunden. Gibt die Adresse zurück, von der er kam; sonst
    Gescheitert."""
    url = quelle % REGION[land]
    # Erst beim Aufruf nachsehen, nicht als Vorgabewert binden.
    schlafen, uhr = schlafen or time.sleep, uhr or time.monotonic
    versuche = len(pausen) + 1
    anfang = uhr()
    for versuch in range(1, versuche + 1):
        try:
            ende, summe = _einmal_laden(url, ziel)
            erwartet = _pruefsumme(ende, url)
            if summe != erwartet:
                raise Unvollstaendig('Prüfsumme %s, erwartet %s' % (summe, erwartet))
            return ende
        except (Unvollstaendig, OSError, http.client.HTTPException) as fehler:
            letzter = fehler
            print('%s: Versuch %d von %d gescheitert: %s' % (land, versuch, versuche, fehler), file=sys.stderr)
        if versuch == versuche:
            break
        pause = pausen[versuch - 1]
        if uhr() - anfang + pause > grenze:
            print('%s: Zeitgrenze von %d s erreicht, kein weiterer Versuch' % (land, grenze), file=sys.stderr)
            break
        schlafen(pause)
    # Kam gar keine Antwort (kein HTTP-Status), sagt die Diagnose, woran.
    if isinstance(letzter, OSError) and not isinstance(letzter, urllib.error.HTTPError):
        netz_diagnose(url)
    raise Gescheitert('%s: Geofabrik-Auszug nach %d Versuchen nicht vollständig' % (land, versuch))


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
