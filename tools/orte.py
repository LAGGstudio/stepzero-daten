"""Gemeinsame Regeln für die Orte aus OpenStreetMap: Arten, Etiketten,
Ausschlüsse, die Umwandlung eines Overpass-Elements in einen Eintrag und das
Zusammenführen doppelter Einträge."""
import math, re, unicodedata

LAENDER = ('de', 'at', 'ch')

# Je Art die Etiketten, die sie auslösen; die erste passende Art gewinnt.
# repaircafe: `repair_cafe=yes` wie vorgegeben (am 9.11.2026 weltweit nicht in
# Gebrauch) und `repair=assisted_self_service`, wie die Wiki-Seite „Repair
# cafe“ Repair-Cafés erfassen lässt. leihladen: weggelassen, das Wiki nennt
# kein dafür dokumentiertes, verbreitetes Etikett (siehe README).
ARTEN = (
    ('garten', ({'leisure': 'garden', 'garden:type': 'community'},)),
    ('fairteiler', ({'amenity': 'food_sharing'},)),
    ('verschenkbox', ({'amenity': 'give_box'},)),
    ('buecherschrank', ({'amenity': 'public_bookcase'},)),
    ('repaircafe', ({'repair_cafe': 'yes'}, {'repair': 'assisted_self_service'})),
    ('trinkbrunnen', ({'amenity': 'drinking_water'},)),
    ('refill', ({'drinking_water:refill': 'yes'},)),
)
ART_NAMEN = tuple(a for a, _ in ARTEN)

# Die ODbL verlangt in der Datenbank die Lizenz oder ihre URI (4.2.b); seit
# dem 12.11.2026 steht die URI mit drin (Audit 11.10). Die App liest das Feld
# nicht (nur `stand` und `eintraege`).
ODBL_URI = 'https://opendatacommons.org/licenses/odbl/1-0/'
LIZENZ = ('ODbL 1.0 (' + ODBL_URI + '), © OpenStreetMap-Mitwirkende, '
          'https://www.openstreetmap.org/copyright')

# Grobe Umrisse (Breite, Länge) für die Plausibilitätsprüfung.
RAHMEN = {
    'de': (47.2, 55.1, 5.8, 15.1),
    'at': (46.3, 49.1, 9.5, 17.2),
    'ch': (45.8, 47.9, 5.9, 10.6),
}


def ausgeschlossen(tags):
    """access=private/no, drinking_water=no, alles mit disused:/abandoned:."""
    if tags.get('access') in ('private', 'no'):
        return True
    if tags.get('drinking_water') == 'no':
        return True
    return any(k.startswith(('disused:', 'abandoned:')) for k in tags)


def art(tags):
    for name, varianten in ARTEN:
        for etiketten in varianten:
            if all(tags.get(k) == v for k, v in etiketten.items()):
                return name
    return None


def adresse(tags):
    strasse = tags.get('addr:street') or tags.get('addr:place')
    teil1 = ' '.join(x for x in (strasse, tags.get('addr:housenumber')) if x) if strasse else ''
    teil2 = ' '.join(x for x in (tags.get('addr:postcode'), tags.get('addr:city')) if x)
    return ', '.join(x for x in (teil1, teil2) if x) or None


def eintrag(element):
    """Overpass-Element (out center tags) → Eintrag oder None."""
    tags = element.get('tags') or {}
    if ausgeschlossen(tags):
        return None
    k = art(tags)
    if k is None:
        return None
    if 'lat' in element:
        lat, lon = element['lat'], element['lon']
    elif 'center' in element:
        lat, lon = element['center']['lat'], element['center']['lon']
    else:
        return None
    e = {'id': {'node': 'n', 'way': 'w', 'relation': 'r'}[element['type']] + str(element['id']),
         'k': k, 'lat': round(lat, 5), 'lon': round(lon, 5)}
    for feld, wert in (('name', tags.get('name')), ('adresse', adresse(tags)),
                       ('oeffnung', tags.get('opening_hours'))):
        if wert:
            e[feld] = wert
    return e


# Doppelte: OSM enthält denselben Ort mehrfach (am 9.11.2026 in DE 91 Paare
# gleicher Art und gleichen Namens unter etwa 100 m, z. B. dreimal „Querbeet“
# in Köln). Gleich sind Einträge derselben Art mit demselben Namen (klein, ohne
# Leer- und Satzzeichen); ohne Namen nie. Ein eigener Name gilt unter
# DOPPEL_ABSTAND_M als derselbe Ort, ein allgemeiner Name (`allerweltsname`:
# Gattungswort, Standardname der App oder nur ein Straßenname) nur unter
# DOPPEL_ABSTAND_ALLGEMEIN_M.
# Seit dem 12.11.2026 200 m statt 100 m: Der Garten „Querbeet“ in Köln
# (Betreiber Querbeet e.V., drei Knoten aus einem Changeset) blieb mit zwei
# Knoten 113 m auseinander doppelt in der App. Seit dem 13.11.2026 gelten die
# 200 m nur für eigene Namen, weil damit auch zwei Trinkbrunnen „Dorfstrasse“
# 193 m auseinander (CH) zu einem wurden; allgemeine Namen wurden bis dahin
# nie zusammengeführt, seitdem unter 30 m (in CH dreimal „Bücherzelle“
# innerhalb von 1 m).
DOPPEL_ABSTAND_M = 200
DOPPEL_ABSTAND_ALLGEMEIN_M = 30
ERDRADIUS_M = 6371008.8  # wie die App (lib/logic/orte_naehe.dart)

# Umlaute und ß wie in den Schritt-IDs der App (ä→ae …), damit die Liste
# unten in ASCII greift („Gießwasser“ → giesswasser); andere Akzente fallen
# weg („Repair-Café“ → repaircafe).
_UMSCHRIFT = str.maketrans({'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'})

# Allgemeine Namen, Teil 1: die Gattungswörter (Allerweltsnamen; Runde 38,
# ergänzt in Runde 39 und 45). Die einzige Liste dafür; schon normalisiert.
# Zwei Brunnen namens „Brunnen“ 50 m auseinander sind meist zwei Brunnen,
# keine Doppel (am 10.11.2026 fielen mit 100 m für alle Namen etwa „Wasch“
# 9-mal und „Gießwasser“ 4-mal auf Friedhöfen weg); darum gelten für sie nur
# DOPPEL_ABSTAND_ALLGEMEIN_M.
ALLERWELTSNAMEN = frozenset({
    'brunnen', 'trinkbrunnen', 'trinkwasser', 'wasser', 'wasch', 'giesswasser',
    'wasserstelle', 'buecherschrank', 'offenerbuecherschrank', 'buecherbox',
    'buecherzelle', 'givebox', 'verschenkbox', 'verschenkregal', 'fairteiler',
    'foodsharing', 'gemeinschaftsgarten', 'garten', 'repaircafe', 'refill',
    'wasserhahn', 'fontana', 'fontaine', 'fontaene', 'laufbrunnen', 'zierbrunnen',
    # Runde 45: Gattungswörter unter den Paaren, die 200 m für alle Namen am
    # 11.11.2026 zusammengeführt hatten (je zwei Brunnen, nach den Etiketten
    # in OSM verschiedene: Ratingen, Bad Hofgastein, Neuruppin, Meiningen).
    'trinkwasserspender', 'thermalwassertrinkbrunnen', 'eurotrinkbrunnen', 'kastenbrunnen',
})

# Allgemeine Namen, Teil 2: ein Straßenname ohne weiteren Zusatz (Runde 45),
# etwa „Dorfstrasse“, „Karl-Marx-Straße“, „Lange Gasse“, „Am Markt“,
# „Rue du Marché“, „Via Cantonale“ (`strassenname`). Zwei Trinkbrunnen
# „Dorfstrasse“ 193 m auseinander (CH, 11.11.2026) sind zwei Brunnen. Mit
# Hausnummer oder einem weiteren Wort („Brunnen Dorfstrasse“) ist der Name
# eigen.
STRASSEN_WOERTER = ('strasse', 'str', 'weg', 'gasse', 'gaessli', 'gaessle', 'allee', 'platz',
                    'ring', 'damm', 'steig', 'pfad', 'chaussee', 'promenade', 'zeile',
                    'markt', 'graben', 'kai', 'quai')
STRASSEN_VORSATZ = ('am', 'an', 'auf', 'im', 'in', 'zum', 'zur', 'beim', 'unter', 'hinter',
                    'vor', 'der', 'die', 'den', 'dem', 'des')
# Adjektive nur aus dieser Liste („Lange Gasse“, „Am Alten Markt“); eine Regel
# nach der Endung (-e, -er) hielt „Bücherzelle am Markt“ und „Trinkwassersäule
# Markt“ für Straßennamen. „Kölner Straße“ gilt darum als eigener Name.
STRASSEN_ADJEKTIVE = frozenset(w + e for w in ('alt', 'neu', 'lang', 'hoh', 'klein', 'gross', 'ober',
                                               'unter', 'breit', 'kurz', 'hinter', 'vorder', 'mittler')
                               for e in ('e', 'er', 'es', 'en'))
STRASSEN_ANFAENGE = ('rue', 'route', 'chemin', 'avenue', 'place', 'ruelle', 'via', 'viale',
                     'piazza', 'piazzetta', 'vicolo', 'strada', 'contrada')

# Allgemeine Namen, Teil 3: die Standardnamen, die die App für Orte ohne
# Namen zeigt, deutsch und englisch; seit Runde 39 gelten sie für jede Art
# (zwei Trinkbrunnen namens „Refill-Station“ 31 m auseinander bleiben zwei). Gehört zusammen mit ortGarten … ortRefill in
# lib/l10n/app_de.arb und app_en.arb der App: Wer das eine ändert, ändert das
# andere (CLAUDE.md hier, docs/claude/lokal.md im App-Repo).
STANDARDNAMEN = {
    'garten': ('Gemeinschaftsgarten', 'Community garden'),
    'fairteiler': ('Fairteiler', 'Food-sharing point'),
    'verschenkbox': ('Verschenkbox', 'Give box'),
    'buecherschrank': ('Bücherschrank', 'Public bookcase'),
    'repaircafe': ('Repair-Café', 'Repair café'),
    'trinkbrunnen': ('Trinkbrunnen', 'Drinking fountain'),
    'refill': ('Refill-Station', 'Refill station'),
}


def name_schluessel(name):
    """Klein, Umlaute umschrieben, ohne Akzente, Leer- und Satzzeichen:
    „Quer-Beet “ = „querbeet“, „Gießwasser“ = „giesswasser“."""
    zerlegt = unicodedata.normalize('NFKD', name.lower().translate(_UMSCHRIFT))
    return ''.join(c for c in zerlegt
                   if not unicodedata.combining(c) and not c.isspace()
                   and not unicodedata.category(c).startswith('P'))


_STANDARD_SCHLUESSEL = frozenset(name_schluessel(n) for namen in STANDARDNAMEN.values() for n in namen)


def _strassenwort(wort):
    """Ein Wort aus Buchstaben (Bindestriche dazwischen, ein Punkt am Ende),
    das auf eines der STRASSEN_WOERTER endet: „dorfstrasse“,
    „karl-marx-strasse“, „hauptstr.“."""
    return (re.fullmatch(r'[a-z]+(-[a-z]+)*\.?', wort) is not None
            and wort.rstrip('.').endswith(STRASSEN_WOERTER))


def strassenname(name):
    """Nur ein Straßenname, ohne Hausnummer und ohne weiteren Zusatz:
    ein Straßenwort („Dorfstrasse“), davor höchstens Präpositionen und
    Artikel aus STRASSEN_VORSATZ („Am Markt“) und Adjektive aus
    STRASSEN_ADJEKTIVE („Lange Gasse“, „Am Alten Markt“); oder ein
    französischer bzw. italienischer Straßenanfang mit Namen („Rue du
    Marché“)."""
    zerlegt = unicodedata.normalize('NFKD', name.lower().translate(_UMSCHRIFT))
    woerter = ''.join(c for c in zerlegt if not unicodedata.combining(c)).split()
    if not woerter or any(c.isdigit() for w in woerter for c in w):
        return False
    if woerter[0] in STRASSEN_ANFAENGE and len(woerter) > 1:
        return True
    letztes, davor = woerter[-1], woerter[:-1]
    if not _strassenwort(letztes):
        return False
    return all(w in STRASSEN_VORSATZ or w in STRASSEN_ADJEKTIVE for w in davor)


def allerweltsname(name):
    """Ein allgemeiner Name: ein Gattungswort aus ALLERWELTSNAMEN, ein
    Standardname irgendeiner Art oder nur ein Straßenname."""
    schluessel = name_schluessel(name)
    return (schluessel in ALLERWELTSNAMEN or schluessel in _STANDARD_SCHLUESSEL
            or strassenname(name))


def abstand_m(a, b):
    """Haversine zwischen zwei Einträgen in Metern."""
    p1, p2 = math.radians(a['lat']), math.radians(b['lat'])
    dp, dl = p2 - p1, math.radians(b['lon'] - a['lon'])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * ERDRADIUS_M * math.asin(math.sqrt(h))


def angaben(e):
    """Wie viele der Angaben Adresse und Öffnungszeiten ein Eintrag hat."""
    return sum(1 for feld in ('adresse', 'oeffnung') if feld in e)


def id_schluessel(e):
    """Kleinere ID: erst der Typ in OSM-Reihenfolge (Knoten, Weg, Relation),
    dann die Nummer als Zahl (n9 vor n10)."""
    return 'nwr'.index(e['id'][0]), int(e['id'][1:])


def grenze_m(gruppe):
    """Abstand, unter dem Einträge einer Gruppe (gleiche Art, gleicher
    Namensschlüssel) als derselbe Ort gelten: DOPPEL_ABSTAND_ALLGEMEIN_M,
    sobald ein Name der Gruppe allgemein ist (verschiedene Schreibweisen
    desselben Schlüssels, etwa „Lange Straße“ und „Langestraße“), sonst
    DOPPEL_ABSTAND_M."""
    if any(allerweltsname(e['name']) for e in gruppe):
        return DOPPEL_ABSTAND_ALLGEMEIN_M
    return DOPPEL_ABSTAND_M


def doppelte_zusammenfuehren(eintraege):
    """Führt doppelte Einträge zusammen und gibt (behaltene, Anzahl
    zusammengeführter je Art) zurück. Je Art und Name gewinnt der Eintrag mit
    den meisten Angaben, bei Gleichstand der mit der kleineren ID; jeder
    weitere fällt weg, wenn er unter `grenze_m` (200 m bei eigenen Namen, 30 m
    bei allgemeinen) von einem behaltenen liegt. So liegt jeder weggefallene
    Eintrag nah an dem, der ihn ersetzt (keine Ketten). Einträge ohne Namen
    bleiben alle. Die Reihenfolge der behaltenen bleibt wie in `eintraege`."""
    gruppen = {}
    for e in eintraege:
        if e.get('name'):
            schluessel = name_schluessel(e['name'])
            if schluessel:
                gruppen.setdefault((e['k'], schluessel), []).append(e)
    weg, zusammengefuehrt = set(), {}
    for (k, _), gruppe in gruppen.items():
        if len(gruppe) < 2:
            continue
        grenze, behalten = grenze_m(gruppe), []
        for e in sorted(gruppe, key=lambda e: (-angaben(e), id_schluessel(e))):
            if any(abstand_m(e, b) < grenze for b in behalten):
                weg.add(e['id'])
                zusammengefuehrt[k] = zusammengefuehrt.get(k, 0) + 1
            else:
                behalten.append(e)
    return [e for e in eintraege if e['id'] not in weg], zusammengefuehrt
