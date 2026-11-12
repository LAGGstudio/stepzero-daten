"""Prüft ausgabe/<land>.json vor dem Veröffentlichen: Schema, Koordinaten im
Land, Größe höchstens 8 MB, Lizenz mit OpenStreetMap und der URI der ODbL,
und die Anzahl gegen die zuletzt veröffentlichte Datei (fällt eine Art mit
mindestens 20 Einträgen oder das ganze Land um mehr als 30 %, schlägt es fehl).
Exit-Code 1 bei jedem Fehler; dann wird nichts veröffentlicht.

  python3 tools/pruefe_orte.py ausgabe [vorher]

`vorher` ist ein Ordner oder eine Basis-URL (die veröffentlichte Seite);
fehlt eine Datei dort (erste Veröffentlichung), entfällt der Vergleich.
"""
import json, os, re, sys, urllib.error, urllib.request
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from orte import ART_NAMEN, LAENDER, ODBL_URI, RAHMEN  # noqa: E402

MAX_BYTES = 8 * 1024 * 1024
MAX_RUECKGANG = 0.30
# Der Rückgang einer Art zählt erst ab so vielen Einträgen in der Vorgängerin
# (am 12.11.2026 in AT: refill 1, repaircafe 9, verschenkbox 11, fairteiler 17).
MIN_VORHER = 20
# Untergrenzen, damit auch die erste Veröffentlichung nichts Leeres oder
# Veraltetes durchlässt (am 9.11.2026 ging so eine leere DE-Datei raus):
# je Land mindestens so viele Einträge (gemessen DE 17 006, AT 9 304,
# CH 16 151) und ein Stand höchstens so viele Tage alt.
MIN_EINTRAEGE = 1000
MAX_ALTER_TAGE = 30
FELDER = {'id', 'k', 'lat', 'lon', 'name', 'adresse', 'oeffnung'}
USER_AGENT = 'StepZero-Daten/1.0 (info.laggstudio@gmail.com)'


def schema_fehler(land, daten, heute=None):
    import datetime
    f = []
    if not isinstance(daten, dict):
        return ['%s: kein Objekt' % land]
    if set(daten) != {'stand', 'lizenz', 'eintraege'}:
        f.append('%s: Felder %s' % (land, sorted(daten)))
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(daten.get('stand'))):
        f.append('%s: stand %r' % (land, daten.get('stand')))
    else:
        alter = ((heute or datetime.date.today()) - datetime.date.fromisoformat(daten['stand'])).days
        if alter > MAX_ALTER_TAGE:
            f.append('%s: stand %s ist %d Tage alt (höchstens %d)' % (land, daten['stand'], alter, MAX_ALTER_TAGE))
    if 'OpenStreetMap' not in str(daten.get('lizenz')):
        f.append('%s: lizenz ohne OpenStreetMap' % land)
    if ODBL_URI not in str(daten.get('lizenz')):
        f.append('%s: lizenz ohne %s' % (land, ODBL_URI))
    eintraege = daten.get('eintraege')
    if not isinstance(eintraege, list):
        return f + ['%s: eintraege keine Liste' % land]
    if len(eintraege) < MIN_EINTRAEGE:
        f.append('%s: nur %d Einträge (mindestens %d)' % (land, len(eintraege), MIN_EINTRAEGE))
    s, n, w, o = RAHMEN[land]
    ids = set()
    for e in eintraege:
        if not isinstance(e, dict) or not FELDER >= set(e) or not {'id', 'k', 'lat', 'lon'} <= set(e):
            f.append('%s: Eintrag %r' % (land, e)); continue
        if not re.fullmatch(r'[nwr]\d+', str(e['id'])) or e['id'] in ids:
            f.append('%s: id %r' % (land, e['id']))
        ids.add(e['id'])
        if e['k'] not in ART_NAMEN:
            f.append('%s %s: Art %r' % (land, e['id'], e['k']))
        for achse in ('lat', 'lon'):
            v = e[achse]
            if not isinstance(v, (int, float)) or isinstance(v, bool) or round(v, 5) != v:
                f.append('%s %s: %s %r' % (land, e['id'], achse, v))
        if isinstance(e['lat'], (int, float)) and isinstance(e['lon'], (int, float)):
            if not (s <= e['lat'] <= n and w <= e['lon'] <= o):
                f.append('%s %s: außerhalb des Lands (%s, %s)' % (land, e['id'], e['lat'], e['lon']))
        for feld in ('name', 'adresse', 'oeffnung'):
            if feld in e and (not isinstance(e[feld], str) or not e[feld].strip()):
                f.append('%s %s: %s leer' % (land, e['id'], feld))
    return f


def anzahlen(daten):
    return Counter(e['k'] for e in daten['eintraege'])


def rueckgang_fehler(land, neu, alt):
    """Je Art erst ab MIN_VORHER Einträgen in der Vorgängerin (Audit 11.4:
    in AT fiel eine einzige Refill-Station von 1 auf 0 und hätte jeden Lauf
    gestoppt); die Summe des Lands immer."""
    f = []
    for k, vorher in alt.items():
        if vorher >= MIN_VORHER and neu.get(k, 0) < vorher * (1 - MAX_RUECKGANG):
            f.append('%s: %s fällt von %d auf %d (mehr als %d %%)'
                     % (land, k, vorher, neu.get(k, 0), MAX_RUECKGANG * 100))
    summe_alt, summe_neu = sum(alt.values()), sum(neu.values())
    if summe_alt and summe_neu < summe_alt * (1 - MAX_RUECKGANG):
        f.append('%s: zusammen fällt von %d auf %d (mehr als %d %%)'
                 % (land, summe_alt, summe_neu, MAX_RUECKGANG * 100))
    return f


def vorher_laden(quelle, land):
    if not quelle:
        return None
    if quelle.startswith('http'):
        url = quelle.rstrip('/') + '/' + land + '.json'
        try:
            anfrage = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(anfrage, timeout=60) as a:
                return json.load(a)
        except urllib.error.HTTPError as fehler:
            if fehler.code == 404:
                return None
            raise
    pfad = os.path.join(quelle, land + '.json')
    if not os.path.exists(pfad):
        return None
    with open(pfad, encoding='utf-8') as d:
        return json.load(d)


def pruefen(ordner, vorher=None, heute=None):
    fehler = []
    for land in LAENDER:
        pfad = os.path.join(ordner, land + '.json')
        if not os.path.exists(pfad):
            fehler.append('%s: Datei fehlt' % land); continue
        groesse = os.path.getsize(pfad)
        if groesse > MAX_BYTES:
            fehler.append('%s: %d Byte, mehr als 8 MB' % (land, groesse))
        with open(pfad, encoding='utf-8') as d:
            try:
                daten = json.load(d)
            except ValueError as e:
                fehler.append('%s: kein JSON (%s)' % (land, e)); continue
        f = schema_fehler(land, daten, heute)
        fehler += f
        if f:
            continue
        alt = vorher_laden(vorher, land)
        if alt is not None:
            fehler += rueckgang_fehler(land, anzahlen(daten), anzahlen(alt))
    return fehler


def main():
    fehler = pruefen(sys.argv[1] if len(sys.argv) > 1 else 'ausgabe', sys.argv[2] if len(sys.argv) > 2 else None)
    for f in fehler:
        print('FEHLER', f, file=sys.stderr)
    print('Prüfung: %s' % ('gescheitert, %d Fehler' % len(fehler) if fehler else 'ok'))
    sys.exit(1 if fehler else 0)


if __name__ == '__main__':
    main()
