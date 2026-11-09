"""Gemeinsame Regeln für die Orte aus OpenStreetMap: Arten, Etiketten,
Ausschlüsse und die Umwandlung eines Overpass-Elements in einen Eintrag."""

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

LIZENZ = ('ODbL 1.0, © OpenStreetMap-Mitwirkende, '
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
