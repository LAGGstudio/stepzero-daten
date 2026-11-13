"""Tests für Umwandlung und Prüfung (ohne Netz): python3 -m unittest discover -s tests"""
import datetime, hashlib, http.server, io, json, os, sys, tempfile, threading, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import hole_orte  # noqa: E402
import pruefe_orte  # noqa: E402
import orte  # noqa: E402
from orte import abstand_m, adresse, allerweltsname, art, ausgeschlossen, doppelte_zusammenfuehren, eintrag, name_schluessel  # noqa: E402


def knoten(i, tags, lat=50.93759, lon=6.96016):
    return {'type': 'node', 'id': i, 'lat': lat, 'lon': lon, 'tags': tags}


class Umwandlung(unittest.TestCase):
    def test_arten(self):
        self.assertEqual(art({'leisure': 'garden', 'garden:type': 'community'}), 'garten')
        self.assertIsNone(art({'leisure': 'garden', 'garden:type': 'residential'}))
        self.assertEqual(art({'amenity': 'food_sharing'}), 'fairteiler')
        self.assertEqual(art({'amenity': 'give_box'}), 'verschenkbox')
        self.assertEqual(art({'amenity': 'public_bookcase'}), 'buecherschrank')
        self.assertEqual(art({'repair_cafe': 'yes'}), 'repaircafe')
        self.assertEqual(art({'repair': 'assisted_self_service'}), 'repaircafe')
        self.assertEqual(art({'amenity': 'drinking_water'}), 'trinkbrunnen')
        self.assertEqual(art({'shop': 'bakery', 'drinking_water:refill': 'yes'}), 'refill')
        # Trinkbrunnen mit Refill-Etikett bleibt Trinkbrunnen (erste Art gewinnt).
        self.assertEqual(art({'amenity': 'drinking_water', 'drinking_water:refill': 'yes'}), 'trinkbrunnen')
        self.assertIsNone(art({'amenity': 'cafe'}))

    def test_ausschluesse(self):
        self.assertTrue(ausgeschlossen({'amenity': 'drinking_water', 'access': 'private'}))
        self.assertTrue(ausgeschlossen({'amenity': 'drinking_water', 'access': 'no'}))
        self.assertTrue(ausgeschlossen({'amenity': 'drinking_water', 'drinking_water': 'no'}))
        self.assertTrue(ausgeschlossen({'amenity': 'public_bookcase', 'disused:amenity': 'public_bookcase'}))
        self.assertTrue(ausgeschlossen({'abandoned:amenity': 'give_box'}))
        self.assertFalse(ausgeschlossen({'amenity': 'drinking_water', 'access': 'yes'}))
        self.assertIsNone(eintrag(knoten(1, {'amenity': 'drinking_water', 'access': 'private'})))

    def test_eintrag_knoten_und_weg(self):
        e = eintrag(knoten(123, {'amenity': 'public_bookcase', 'name': 'Bücherschrank am Ring',
                                 'addr:street': 'Ring', 'addr:housenumber': '1', 'addr:postcode': '50667',
                                 'addr:city': 'Köln', 'opening_hours': '24/7'}, 50.937594, 6.960163))
        self.assertEqual(e, {'id': 'n123', 'k': 'buecherschrank', 'lat': 50.93759, 'lon': 6.96016,
                             'name': 'Bücherschrank am Ring', 'adresse': 'Ring 1, 50667 Köln', 'oeffnung': '24/7'})
        w = eintrag({'type': 'way', 'id': 45, 'center': {'lat': 48.2, 'lon': 16.37},
                     'tags': {'leisure': 'garden', 'garden:type': 'community'}})
        self.assertEqual(w, {'id': 'w45', 'k': 'garten', 'lat': 48.2, 'lon': 16.37})
        self.assertIsNone(eintrag({'type': 'relation', 'id': 6, 'tags': {'amenity': 'give_box'}}))

    def test_adresse(self):
        self.assertEqual(adresse({'addr:street': 'Ring', 'addr:housenumber': '1'}), 'Ring 1')
        self.assertEqual(adresse({'addr:postcode': '1010', 'addr:city': 'Wien'}), '1010 Wien')
        self.assertIsNone(adresse({'addr:housenumber': '1'}))

    def test_ohne_datenstand_abbrechen_statt_heute(self):
        # Bis zum 12.11.2026 setzte umwandeln dann das heutige Datum ein (Audit 11.5).
        for roh in ({'elements': [knoten(1, {'amenity': 'give_box'})]},
                    {'osm3s': {'timestamp_osm_base': ''}, 'elements': [knoten(1, {'amenity': 'give_box'})]},
                    {'osm3s': {'timestamp_osm_base': 'gestern'}, 'elements': []}):
            with self.assertRaises(SystemExit) as ctx:
                hole_orte.umwandeln(roh, 'at')
            self.assertIn('at: ohne Datenstand', str(ctx.exception))

    def test_lizenz_mit_uri_der_odbl(self):
        # ODbL 4.2.b: Lizenz oder URI in der Datenbank (Audit 11.10).
        self.assertIn('https://opendatacommons.org/licenses/odbl/1-0/', orte.LIZENZ)
        self.assertIn('OpenStreetMap', orte.LIZENZ)
        d, _ = hole_orte.umwandeln({'osm3s': {'timestamp_osm_base': '2026-11-09T18:00:00Z'}, 'elements': []})
        self.assertEqual(d['lizenz'], orte.LIZENZ)

    def test_umwandeln_kompakt_sortiert_ohne_doppel(self):
        roh = {'osm3s': {'timestamp_osm_base': '2026-11-09T18:00:00Z'}, 'elements': [
            knoten(2, {'amenity': 'drinking_water'}), knoten(1, {'amenity': 'give_box'}),
            knoten(2, {'amenity': 'drinking_water'}), knoten(3, {'shop': 'kiosk'})]}
        d, zusammengefuehrt = hole_orte.umwandeln(roh)
        self.assertEqual(zusammengefuehrt, {})
        self.assertEqual(d['stand'], '2026-11-09')
        self.assertIn('OpenStreetMap', d['lizenz'])
        self.assertEqual([e['id'] for e in d['eintraege']], ['n2', 'n1'])
        self.assertNotIn(' ', json.dumps(d['eintraege'][0], separators=(',', ':')))

    def test_abfrage(self):
        q = hole_orte.abfrage('at')
        self.assertIn('area["ISO3166-1"="AT"][admin_level=2]', q)
        self.assertIn('[timeout:180]', q)
        self.assertIn('out center tags;', q)
        self.assertIn('nwr["leisure"="garden"]["garden:type"="community"](area.land);', q)


class Rueckfall(unittest.TestCase):
    def test_mitte_des_rechtecks(self):
        import geofabrik
        self.assertEqual(geofabrik._mitte([(50.0, 7.0), (51.0, 9.0), (50.2, 7.5)]), {'lat': 50.5, 'lon': 8.0})
        self.assertIsNone(geofabrik._mitte([]))

    def test_etiketten_fuer_den_filter(self):
        import geofabrik
        self.assertIn(('leisure', 'garden'), geofabrik.ETIKETTEN)
        self.assertIn(('repair', 'assisted_self_service'), geofabrik.ETIKETTEN)
        self.assertIn(('drinking_water:refill', 'yes'), geofabrik.ETIKETTEN)

    def test_quelle_geofabrik_standard_overpass_nur_von_hand(self):
        import geofabrik
        aufrufe = []
        alt_o, alt_g = hole_orte.overpass_holen, geofabrik.holen
        try:
            def overpass(land):
                aufrufe.append(('overpass', land))
                raise SystemExit('nicht erreichbar')
            hole_orte.overpass_holen = overpass
            geofabrik.holen = lambda land: aufrufe.append(('geofabrik', land)) or {'elements': []}
            os.environ.pop('ORTE_QUELLE', None)
            self.assertEqual(hole_orte.holen('ch'), {'elements': []})
            self.assertEqual(aufrufe, [('geofabrik', 'ch')])
            os.environ['ORTE_QUELLE'] = 'geofabrik'
            hole_orte.holen('at')
            self.assertEqual(aufrufe[-1], ('geofabrik', 'at'))
            # Overpass nur von Hand und ohne Rückfall auf den Auszug.
            os.environ['ORTE_QUELLE'] = 'overpass'
            with self.assertRaises(SystemExit):
                hole_orte.holen('de')
            self.assertEqual(aufrufe[-1], ('overpass', 'de'))
            os.environ['ORTE_QUELLE'] = 'overpas'
            with self.assertRaises(SystemExit) as ctx:
                hole_orte.holen('de')
            self.assertIn('unbekannt', str(ctx.exception))
            self.assertEqual(len(aufrufe), 3)
        finally:
            os.environ.pop('ORTE_QUELLE', None)
            hole_orte.overpass_holen, geofabrik.holen = alt_o, alt_g


class OverpassAntwort(unittest.TestCase):
    def roh(self, basis='2026-11-08T21:00:00Z', elemente=1, remark=None):
        r = {'osm3s': {'timestamp_osm_base': basis}, 'elements': [{'type': 'node', 'id': i} for i in range(elemente)]}
        if remark:
            r['remark'] = remark
        return r

    def test_brauchbar(self):
        hole_orte.brauchbar('de', self.roh(), heute=HEUTE)
        hole_orte.brauchbar('de', self.roh(basis='2026-11-02T00:00:00Z'), heute=HEUTE)

    def test_veraltet_leer_oder_fehler(self):
        # So antwortete overpass.private.coffee am 9.11.2026 (Stand Juni, DE leer).
        for roh, text in (
            (self.roh(basis='2026-06-01T00:00:00Z'), '161 Tage alt'),
            (self.roh(basis='2026-11-01T00:00:00Z'), '8 Tage alt'),
            (self.roh(elemente=0), 'keine Elemente'),
            (self.roh(remark='runtime error: Query timed out in "query" at line 3 after 181 seconds.'), 'Overpass meldet'),
            ({'elements': [{'type': 'node', 'id': 1}]}, 'ohne Datenstand'),
        ):
            with self.assertRaises(hole_orte.Unbrauchbar) as ctx:
                hole_orte.brauchbar('de', roh, heute=HEUTE)
            self.assertIn(text, str(ctx.exception))

    def test_unbrauchbar_ohne_rueckfall(self):
        import geofabrik
        alt_g = geofabrik.holen
        alt_url = hole_orte.urllib.request.urlopen
        try:
            geofabrik.holen = lambda land: self.fail('kein Rückfall mehr')

            class Antwort(io.BytesIO):
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False
            veraltet = json.dumps(self.roh(basis='2026-06-01T00:00:00Z')).encode()
            hole_orte.urllib.request.urlopen = lambda *a, **k: Antwort(veraltet)
            os.environ['ORTE_QUELLE'] = 'overpass'
            with self.assertRaises(hole_orte.Unbrauchbar):
                hole_orte.holen('de')
        finally:
            os.environ.pop('ORTE_QUELLE', None)
            geofabrik.holen = alt_g
            hole_orte.urllib.request.urlopen = alt_url


def ort(i, name=None, lat=50.9, lon=6.9, k='garten', **mehr):
    e = {'id': i, 'k': k, 'lat': lat, 'lon': lon}
    if name is not None:
        e['name'] = name
    e.update(mehr)
    return e


class Doppelte(unittest.TestCase):
    # 0,00179° Breite sind etwa 199 m, 0,00181° etwa 201 m (seit dem
    # 12.11.2026 liegt die Grenze für eigene Namen bei 200 m, vorher bei
    # 100 m); 0,00026° etwa 28,9 m, 0,00028° etwa 31,1 m (seit dem
    # 13.11.2026 die Grenze für allgemeine Namen, vorher nie).
    NAH, WEIT = 50.9 + 0.00179, 50.9 + 0.00181
    NAH_ALLGEMEIN, WEIT_ALLGEMEIN = 50.9 + 0.00026, 50.9 + 0.00028

    def ids(self, eintraege):
        return [e['id'] for e in doppelte_zusammenfuehren(eintraege)[0]]

    def test_abstaende_der_testpunkte(self):
        self.assertEqual(orte.DOPPEL_ABSTAND_M, 200)
        self.assertEqual(orte.DOPPEL_ABSTAND_ALLGEMEIN_M, 30)
        self.assertLess(abstand_m(ort('n1'), ort('n2', lat=self.NAH)), 200)
        self.assertGreater(abstand_m(ort('n1'), ort('n2', lat=self.WEIT)), 200)
        self.assertLess(abstand_m(ort('n1'), ort('n2', lat=self.NAH_ALLGEMEIN)), 30)
        self.assertGreater(abstand_m(ort('n1'), ort('n2', lat=self.WEIT_ALLGEMEIN)), 30)
        # Gleiche Rechnung wie die App: 1° Breite = 111,195 km.
        self.assertAlmostEqual(abstand_m(ort('n1', lat=50), ort('n2', lat=51)), 111195.08, places=1)

    def test_name_schluessel(self):
        self.assertEqual(name_schluessel('Quer-Beet '), 'querbeet')
        self.assertEqual(name_schluessel('„Querbeet“'), 'querbeet')
        self.assertEqual(name_schluessel('Bücherschrank am Ring'), name_schluessel('BÜCHERSCHRANK  Am-Ring.'))
        # Gegenprobe: Buchstaben und Ziffern bleiben.
        self.assertNotEqual(name_schluessel('Garten 1'), name_schluessel('Garten 2'))
        self.assertNotEqual(name_schluessel('Rosengarten'), name_schluessel('Rosen garten Süd'))

    def test_name_schluessel_umschrift(self):
        self.assertEqual(name_schluessel('Gießwasser'), 'giesswasser')
        self.assertEqual(name_schluessel('Repair-Café'), 'repaircafe')
        self.assertEqual(name_schluessel('Offener Bücherschrank'), 'offenerbuecherschrank')
        self.assertEqual(name_schluessel('Bücherschrank'), name_schluessel('Buecherschrank'))
        self.assertEqual(name_schluessel('GÄRTEN'), 'gaerten')
        # Gegenprobe: ohne Umlaut bleibt der Name, wie er ist.
        self.assertNotEqual(name_schluessel('Garten'), name_schluessel('Gärten'))

    def test_liste_der_allerweltsnamen(self):
        self.assertEqual(sorted(orte.ALLERWELTSNAMEN), sorted([
            'brunnen', 'trinkbrunnen', 'trinkwasser', 'wasser', 'wasch', 'giesswasser',
            'wasserstelle', 'buecherschrank', 'offenerbuecherschrank', 'buecherbox',
            'buecherzelle', 'givebox', 'verschenkbox', 'verschenkregal', 'fairteiler',
            'foodsharing', 'gemeinschaftsgarten', 'garten', 'repaircafe', 'refill',
            'wasserhahn', 'fontana', 'fontaine', 'fontaene', 'laufbrunnen', 'zierbrunnen',
            'trinkwasserspender', 'thermalwassertrinkbrunnen', 'eurotrinkbrunnen', 'kastenbrunnen']))
        for n in orte.ALLERWELTSNAMEN:
            self.assertEqual(name_schluessel(n), n, 'normalisiert wie beim Vergleich')
        self.assertEqual(set(orte.STANDARDNAMEN), set(orte.ART_NAMEN), 'jede Art')

    def test_allgemeine_namen_nur_unter_30_m(self):
        # Seit dem 13.11.2026: unter 30 m derselbe Ort, darüber zwei (bis
        # dahin wurden allgemeine Namen nie zusammengeführt).
        for k, name in (('trinkbrunnen', 'Brunnen'), ('trinkbrunnen', 'Gießwasser'),
                        ('trinkbrunnen', 'Wasch'), ('trinkbrunnen', 'Wasser-Stelle'),
                        ('buecherschrank', 'Offener Bücherschrank'), ('buecherschrank', 'Bücher-Box'),
                        ('buecherschrank', 'Bücherzelle'), ('verschenkbox', 'Give-Box'),
                        ('fairteiler', 'Foodsharing'), ('garten', 'Garten'),
                        ('repaircafe', 'Repair Café'), ('refill', 'REFILL'),
                        ('trinkbrunnen', 'Wasserhahn'), ('trinkbrunnen', 'Fontana'),
                        ('trinkbrunnen', 'Fontaine'), ('trinkbrunnen', 'Fontäne'),
                        ('trinkbrunnen', 'Lauf-Brunnen'), ('trinkbrunnen', 'Zierbrunnen'),
                        ('trinkbrunnen', 'Trinkwasserspender'),
                        ('trinkbrunnen', 'Thermalwasser-Trinkbrunnen'),
                        ('trinkbrunnen', 'Euro-Trinkbrunnen'), ('trinkbrunnen', 'Kastenbrunnen')):
            self.assertTrue(allerweltsname(name), name)
            nah = [ort('n1', name, k=k), ort('n2', name, k=k, lat=self.NAH_ALLGEMEIN)]
            self.assertEqual(self.ids(nah), ['n1'], name)
            weit = [ort('n1', name, k=k), ort('n2', name, k=k, lat=self.WEIT_ALLGEMEIN)]
            self.assertEqual(self.ids(weit), ['n1', 'n2'], name)
        # Gegenprobe: ein Name, der ein Allerweltswort nur enthält, ist eigen
        # und gilt bis 200 m.
        for k, name in (('trinkbrunnen', 'Brunnen am Markt'), ('buecherschrank', 'Bücherschrank am Ring'),
                        ('garten', 'Garten am Mer'), ('trinkbrunnen', 'Fontana di Piazza'),
                        ('trinkbrunnen', 'Wasserhahn Friedhof Süd')):
            self.assertFalse(allerweltsname(name), name)
            e = [ort('n1', name, k=k), ort('n2', name, k=k, lat=self.NAH)]
            self.assertEqual(self.ids(e), ['n1'], name)

    def test_trinkwasserspender_150_m_bleiben_zwei(self):
        e = [ort('n1', 'Trinkwasserspender', k='trinkbrunnen'),
             ort('n2', 'Trinkwasserspender', k='trinkbrunnen', lat=50.9 + 0.001349)]
        self.assertAlmostEqual(abstand_m(e[0], e[1]), 150.0, delta=0.5)
        behalten, zusammen = doppelte_zusammenfuehren(e)
        self.assertEqual([x['id'] for x in behalten], ['n1', 'n2'])
        self.assertEqual(zusammen, {})

    def test_trinkwasserspender_10_m_werden_einer(self):
        e = [ort('n1', 'Trinkwasserspender', k='trinkbrunnen'),
             ort('n2', 'Trinkwasserspender', k='trinkbrunnen', lat=50.9 + 0.00009)]
        self.assertAlmostEqual(abstand_m(e[0], e[1]), 10.0, delta=0.5)
        behalten, zusammen = doppelte_zusammenfuehren(e)
        self.assertEqual([x['id'] for x in behalten], ['n1'])
        self.assertEqual(zusammen, {'trinkbrunnen': 1})

    def test_standardnamen_gelten_fuer_jede_art(self):
        # Die Standardnamen der App, deutsch und englisch, seit Runde 39 für
        # jede Art: auch zwei Trinkbrunnen namens „Refill-Station“ 31 m
        # auseinander bleiben zwei und ein Garten namens „Drinking fountain“.
        alle = [(k, n) for k, namen in orte.STANDARDNAMEN.items() for n in namen]
        self.assertEqual(len(alle), 14)
        for k_name, name in alle:
            for k in orte.ART_NAMEN:
                self.assertTrue(allerweltsname(name), name)
                weit = [ort('n1', name, k=k), ort('n2', name, k=k, lat=self.WEIT_ALLGEMEIN)]
                self.assertEqual(self.ids(weit), ['n1', 'n2'], (k, name))
                nah = [ort('n1', name, k=k), ort('n2', name, k=k, lat=self.NAH_ALLGEMEIN)]
                self.assertEqual(self.ids(nah), ['n1'], (k, name))
        # Gegenprobe: ein Name, der einen Standardnamen nur enthält, ist eigen.
        for name in ('Refill-Station am Markt', 'Trinkbrunnen Domplatte', 'Community garden Ehrenfeld'):
            self.assertFalse(allerweltsname(name), name)
            e = [ort('n1', name, k='trinkbrunnen'), ort('n2', name, k='trinkbrunnen', lat=self.NAH)]
            self.assertEqual(self.ids(e), ['n1'], name)

    def test_strassennamen_ohne_zusatz_sind_allgemein(self):
        for name in ('Dorfstrasse', 'Dorfstraße', 'Karl-Marx-Straße', 'Hauptstr.', 'Lindenweg',
                     'Brunngasse', 'Mittelgässli', 'Marktplatz', 'Lange Gasse', 'Kölner Straße',
                     'Am Markt', 'An der Allee', 'Rue du Marché', 'Via Cantonale', 'Place de la Gare'):
            self.assertTrue(orte.strassenname(name), name)
            self.assertTrue(allerweltsname(name), name)
        # Gegenprobe: mit Hausnummer, mit Zusatz oder ohne Straßenwort eigen.
        for name in ('Dorfstrasse 5', 'Brunnen Dorfstrasse', 'Brunnen am Markt', 'Brunnen Marktplatz',
                     'Gemeinschaftsgarten Lindenweg', 'Fontaine de la Place', 'Der Läufer', 'Querbeet',
                     'Rue', 'Am Brunnen', 'Die Lesebank'):
            self.assertFalse(orte.strassenname(name), name)
            self.assertFalse(allerweltsname(name), name)

    def test_dorfstrasse_zwei_brunnen(self):
        # Zwei Trinkbrunnen „Dorfstrasse“ in CH (Auszug vom 11.11.2026) 193 m
        # auseinander: Mit 200 m für alle Namen fiel n1094418955 weg (Pages-Stand
        # vom 12.11.2026); als Straßenname gelten 30 m, beide bleiben.
        e = [ort('n1094418955', 'Dorfstrasse', k='trinkbrunnen', lat=47.53396, lon=8.25474),
             ort('n791450067', 'Dorfstrasse', k='trinkbrunnen', lat=47.53267, lon=8.25646)]
        self.assertAlmostEqual(abstand_m(e[0], e[1]), 193.0, places=0)
        self.assertEqual(self.ids(e), ['n1094418955', 'n791450067'])

    def test_allgemein_gilt_fuer_die_ganze_gruppe(self):
        # „Dorf Strasse“ allein wäre eigen (kein Adjektiv vor „Strasse“), hat
        # aber denselben Schlüssel wie der Straßenname „Dorfstrasse“: Die Gruppe
        # gilt als allgemein, 100 m auseinander bleiben beide.
        self.assertFalse(allerweltsname('Dorf Strasse'))
        e = [ort('n1', 'Dorf Strasse', k='trinkbrunnen'),
             ort('n2', 'Dorfstrasse', k='trinkbrunnen', lat=50.9 + 0.0009)]
        self.assertEqual(self.ids(e), ['n1', 'n2'])
        self.assertEqual(self.ids(list(reversed(e))), ['n2', 'n1'])

    def test_querbeet_koeln_eine_einrichtung(self):
        # Die drei Knoten des Gartens „Querbeet“ in Köln (Auszug vom
        # 11.11.2026, Betreiber Querbeet e.V.): 113 m, 128 m und 17 m
        # auseinander, alle ohne Adresse und Öffnungszeiten. Ein eigener Name,
        # also 200 m: Es bleibt einer, der mit der kleinsten ID. Bis zum
        # 12.11.2026 (100 m) blieben zwei.
        e = [ort('n11199147603', 'Querbeet', lat=50.9384, lon=6.93289),
             ort('n11199147604', 'Querbeet', lat=50.93846, lon=6.9345),
             ort('n11199147605', 'Querbeet', lat=50.93854, lon=6.9347)]
        self.assertAlmostEqual(abstand_m(e[0], e[1]), 113.0, places=0)
        self.assertAlmostEqual(abstand_m(e[0], e[2]), 127.8, places=1)
        self.assertAlmostEqual(abstand_m(e[1], e[2]), 16.6, places=1)
        self.assertFalse(allerweltsname('Querbeet'))
        behalten, zusammen = doppelte_zusammenfuehren(e)
        self.assertEqual([x['id'] for x in behalten], ['n11199147603'])
        self.assertEqual(zusammen, {'garten': 2})

    def test_gleiche_art_gleicher_name_unter_200_m(self):
        e = [ort('n1', 'Querbeet'), ort('n2', 'querbeet', lat=self.NAH)]
        behalten, zusammen = doppelte_zusammenfuehren(e)
        self.assertEqual([x['id'] for x in behalten], ['n1'])
        self.assertEqual(zusammen, {'garten': 1})

    def test_gegenproben_nicht_zusammenfuehren(self):
        # Knapp über 200 m.
        self.assertEqual(self.ids([ort('n1', 'Querbeet'), ort('n2', 'Querbeet', lat=self.WEIT)]), ['n1', 'n2'])
        # Andere Art, gleicher Name, gleiche Stelle.
        self.assertEqual(self.ids([ort('n1', 'Am Markt', k='trinkbrunnen'),
                                   ort('n2', 'Am Markt', k='buecherschrank')]), ['n1', 'n2'])
        # Anderer Name an derselben Stelle.
        self.assertEqual(self.ids([ort('n1', 'Querbeet'), ort('n2', 'Querbeet 2')]), ['n1', 'n2'])
        # Ohne Namen nie, auch an derselben Stelle; ebenso ein Name nur aus Satzzeichen.
        self.assertEqual(self.ids([ort('n1', k='trinkbrunnen'), ort('n2', k='trinkbrunnen')]), ['n1', 'n2'])
        self.assertEqual(self.ids([ort('n1', '-'), ort('n2', '–')]), ['n1', 'n2'])
        self.assertEqual(self.ids([ort('n1', 'Querbeet'), ort('n2')]), ['n1', 'n2'])

    def test_behalten_wird_der_mit_den_meisten_angaben(self):
        e = [ort('n1', 'Querbeet', adresse='Ring 1'),
             ort('n2', 'Querbeet', adresse='Ring 1', oeffnung='Mo-Fr 10:00-18:00'),
             ort('n3', 'Querbeet')]
        behalten, zusammen = doppelte_zusammenfuehren(e)
        self.assertEqual([x['id'] for x in behalten], ['n2'])
        self.assertEqual(behalten[0]['oeffnung'], 'Mo-Fr 10:00-18:00')
        self.assertEqual(zusammen, {'garten': 2})
        # Öffnungszeiten zählen wie eine Adresse.
        self.assertEqual(self.ids([ort('n1', 'A'), ort('n2', 'A', oeffnung='24/7')]), ['n2'])

    def test_gleichstand_kleinere_id(self):
        # Als Zahl, nicht als Text: n9 vor n10 (als Text wäre n10 kleiner).
        self.assertEqual(self.ids([ort('n10', 'A'), ort('n9', 'A')]), ['n9'])
        # Typ in OSM-Reihenfolge: Knoten vor Weg vor Relation.
        self.assertEqual(self.ids([ort('w1', 'A'), ort('n5', 'A')]), ['n5'])
        self.assertEqual(self.ids([ort('r1', 'A'), ort('w7', 'A')]), ['w7'])

    def test_keine_ketten(self):
        # n1 und n3 liegen 360 m auseinander, n2 dazwischen: n2 geht in n1 auf,
        # n3 bleibt, weil es von n1 zu weit weg ist (Grenze 200 m).
        schritt = 0.00162  # etwa 180 m
        e = [ort('n1', 'A'), ort('n2', 'A', lat=50.9 + schritt), ort('n3', 'A', lat=50.9 + 2 * schritt)]
        self.assertEqual(self.ids(e), ['n1', 'n3'])

    def test_reihenfolge_bleibt(self):
        e = [ort('n5', 'B', k='fairteiler'), ort('n1', 'A'), ort('n3', 'C', k='refill'), ort('n2', 'A')]
        self.assertEqual(self.ids(e), ['n5', 'n1', 'n3'])

    def test_umwandeln_fuehrt_zusammen_und_zaehlt(self):
        roh = {'osm3s': {'timestamp_osm_base': '2026-11-09T18:00:00Z'}, 'elements': [
            knoten(1, {'leisure': 'garden', 'garden:type': 'community', 'name': 'Querbeet'}),
            knoten(2, {'leisure': 'garden', 'garden:type': 'community', 'name': 'Quer beet',
                       'opening_hours': 'Sa 10:00-14:00'}, lat=50.93759 + 0.0005),
            knoten(3, {'amenity': 'drinking_water'}), knoten(4, {'amenity': 'drinking_water'})]}
        d, zusammen = hole_orte.umwandeln(roh)
        self.assertEqual([e['id'] for e in d['eintraege']], ['n2', 'n3', 'n4'])
        self.assertEqual(zusammen, {'garten': 1})
        zeilen = hole_orte.zusammenfassung('de', d, zusammen)
        self.assertEqual(len(zeilen), len(orte.ART_NAMEN) + 1)
        self.assertIn('garten', zeilen[0])
        self.assertTrue(zeilen[0].endswith('1  (1 zusammengeführt)'), zeilen[0])
        self.assertTrue(zeilen[-1].endswith('3  (1 zusammengeführt)'), zeilen[-1])


HEUTE = datetime.date(2026, 11, 9)


def datei(eintraege, stand='2026-11-09'):
    return {'stand': stand, 'lizenz': orte.LIZENZ, 'eintraege': eintraege}


def gueltig(land='de', n=10, k='trinkbrunnen'):
    lat, lon = {'de': (50.9, 6.9), 'at': (48.2, 16.4), 'ch': (47.4, 8.5)}[land]
    return [{'id': 'n%d' % i, 'k': k, 'lat': lat, 'lon': lon} for i in range(n)]


class Pruefung(unittest.TestCase):
    # Die Testdateien sind klein; die Untergrenze prüfen eigene Tests.
    def setUp(self):
        self.min_alt = pruefe_orte.MIN_EINTRAEGE
        pruefe_orte.MIN_EINTRAEGE = 1

    def tearDown(self):
        pruefe_orte.MIN_EINTRAEGE = self.min_alt

    def pruefen(self, ordner, vorher=None):
        return pruefe_orte.pruefen(ordner, vorher, heute=HEUTE)

    def ordner(self, inhalte, roh=None):
        d = tempfile.mkdtemp()
        for land in ('de', 'at', 'ch'):
            with open(os.path.join(d, land + '.json'), 'w', encoding='utf-8') as f:
                if roh and land in roh:
                    f.write(roh[land])
                else:
                    json.dump(inhalte.get(land, datei(gueltig(land))), f, separators=(',', ':'))
        return d

    def test_gueltig(self):
        self.assertEqual(self.pruefen(self.ordner({})), [])

    def test_koordinate_ausserhalb(self):
        e = gueltig('ch')
        e[0]['lat'] = 52.5  # Berlin
        f = self.pruefen(self.ordner({'ch': datei(e)}))
        self.assertTrue(any('außerhalb' in x for x in f), f)

    def test_schema(self):
        e = gueltig()
        e[0]['k'] = 'leihladen'
        e[1]['lat'] = 50.123456
        e[2]['farbe'] = 'gruen'
        e[3]['id'] = 'n0'
        f = self.pruefen(self.ordner({'de': datei(e, stand='9.11.2026')}))
        self.assertTrue(any("Art 'leihladen'" in x for x in f), f)
        self.assertTrue(any('lat 50.123456' in x for x in f), f)
        self.assertTrue(any('farbe' in x for x in f), f)
        self.assertTrue(any("id 'n0'" in x for x in f), f)
        self.assertTrue(any('stand' in x for x in f), f)

    def test_kaputtes_json_und_fehlende_datei(self):
        d = self.ordner({}, roh={'at': '{"stand":'})
        os.remove(os.path.join(d, 'ch.json'))
        f = self.pruefen(d)
        self.assertTrue(any('at: kein JSON' in x for x in f), f)
        self.assertTrue(any('ch: Datei fehlt' in x for x in f), f)

    def test_rueckgang_ueber_30_prozent(self):
        vorher = self.ordner({'de': datei(gueltig(n=100))})
        self.assertEqual(self.pruefen(self.ordner({'de': datei(gueltig(n=70))}), vorher), [])
        f = self.pruefen(self.ordner({'de': datei(gueltig(n=69))}), vorher)
        self.assertTrue(any('fällt von 100 auf 69' in x for x in f), f)
        # Eine Art verschwindet ganz.
        f = self.pruefen(self.ordner({'de': datei(gueltig(n=100, k='refill'))}), vorher)
        self.assertTrue(any('trinkbrunnen fällt von 100 auf 0' in x for x in f), f)

    def test_ohne_vorherige_datei_kein_vergleich(self):
        leer = tempfile.mkdtemp()
        self.assertEqual(self.pruefen(self.ordner({'de': datei(gueltig(n=1))}), leer), [])

    def test_untergrenze_eintraege(self):
        # Am 9.11.2026 ging ohne sie eine leere DE-Datei raus.
        pruefe_orte.MIN_EINTRAEGE = 1000
        self.assertEqual(self.pruefen(self.ordner({l: datei(gueltig(l, n=1000)) for l in ('de', 'at', 'ch')})), [])
        f = self.pruefen(self.ordner({l: datei(gueltig(l, n=1000)) for l in ('at', 'ch')} | {'de': datei([])}))
        self.assertEqual(f, ['de: nur 0 Einträge (mindestens 1000)'])
        f = self.pruefen(self.ordner({l: datei(gueltig(l, n=1000)) for l in ('de', 'ch')} | {'at': datei(gueltig('at', n=999))}))
        self.assertEqual(f, ['at: nur 999 Einträge (mindestens 1000)'])

    def test_stand_hoechstens_30_tage_alt(self):
        self.assertEqual(self.pruefen(self.ordner({'de': datei(gueltig(), stand='2026-10-10')})), [])
        f = self.pruefen(self.ordner({'de': datei(gueltig(), stand='2026-10-09')}))
        self.assertEqual(f, ['de: stand 2026-10-09 ist 31 Tage alt (höchstens 30)'])

    def test_groesse_ueber_8_mb(self):
        d = self.ordner({})
        with open(os.path.join(d, 'de.json'), 'a', encoding='utf-8') as f:
            f.write(' ' * (8 * 1024 * 1024))
        f = self.pruefen(d)
        self.assertTrue(any('mehr als 8 MB' in x for x in f), f)


    def test_lizenz_ohne_uri(self):
        d = datei(gueltig())
        d['lizenz'] = 'ODbL 1.0, © OpenStreetMap-Mitwirkende'
        f = self.pruefen(self.ordner({'de': d}))
        self.assertEqual(f, ['de: lizenz ohne https://opendatacommons.org/licenses/odbl/1-0/'])


class Rueckgang(unittest.TestCase):
    """Audit 11.4: Der Rückgang einer Art zählt erst ab 20 Einträgen vorher,
    die Summe des Lands immer."""

    # So stand AT am 12.11.2026 online (gemessen).
    AT = {'buecherschrank': 567, 'fairteiler': 17, 'garten': 196, 'refill': 1,
          'repaircafe': 9, 'trinkbrunnen': 8489, 'verschenkbox': 11}

    def test_faelle_aus_dem_audit_laufen_durch(self):
        neu = dict(self.AT, refill=0, repaircafe=6)
        self.assertEqual(pruefe_orte.rueckgang_fehler('at', neu, self.AT), [])
        # Auch kleine Arten ganz weg (verschenkbox 11 → 0, fairteiler 17 → 0).
        neu = dict(self.AT, refill=0, verschenkbox=0, fairteiler=0)
        self.assertEqual(pruefe_orte.rueckgang_fehler('at', neu, self.AT), [])

    def test_echter_einbruch_scheitert(self):
        f = pruefe_orte.rueckgang_fehler('at', dict(self.AT, trinkbrunnen=5000), self.AT)
        self.assertEqual(f, ['at: trinkbrunnen fällt von 8489 auf 5000 (mehr als 30 %)',
                             'at: zusammen fällt von 9290 auf 5801 (mehr als 30 %)'])
        f = pruefe_orte.rueckgang_fehler('at', dict(self.AT, buecherschrank=300), self.AT)
        self.assertEqual(f, ['at: buecherschrank fällt von 567 auf 300 (mehr als 30 %)'])

    def test_grenze_bei_20(self):
        self.assertEqual(pruefe_orte.MIN_VORHER, 20)
        alt = {'refill': 20, 'trinkbrunnen': 5000}
        self.assertEqual(pruefe_orte.rueckgang_fehler('de', {'refill': 14, 'trinkbrunnen': 5000}, alt), [])
        self.assertEqual(pruefe_orte.rueckgang_fehler('de', {'refill': 13, 'trinkbrunnen': 5000}, alt),
                         ['de: refill fällt von 20 auf 13 (mehr als 30 %)'])
        alt = {'refill': 19, 'trinkbrunnen': 5000}
        self.assertEqual(pruefe_orte.rueckgang_fehler('de', {'trinkbrunnen': 5000}, alt), [])

    def test_summe_immer(self):
        # Lauter kleine Arten, jede unter 20: die Summe fällt trotzdem auf.
        alt = {k: 19 for k in orte.ART_NAMEN}
        f = pruefe_orte.rueckgang_fehler('ch', {k: 9 for k in orte.ART_NAMEN}, alt)
        self.assertEqual(f, ['ch: zusammen fällt von 133 auf 63 (mehr als 30 %)'])

    def test_ueber_pruefen_mit_vorheriger_datei(self):
        alt_min = pruefe_orte.MIN_EINTRAEGE
        pruefe_orte.MIN_EINTRAEGE = 1
        try:
            vorher = tempfile.mkdtemp()
            neu = tempfile.mkdtemp()
            for ordner, refill in ((vorher, 1), (neu, 0)):
                for land in ('de', 'at', 'ch'):
                    e = gueltig(land, n=100) + [dict(gueltig(land, n=1, k='refill')[0], id='n9%d' % i)
                                                 for i in range(refill)]
                    with open(os.path.join(ordner, land + '.json'), 'w', encoding='utf-8') as d:
                        json.dump(datei(e), d)
            self.assertEqual(pruefe_orte.pruefen(neu, vorher, heute=HEUTE), [])
        finally:
            pruefe_orte.MIN_EINTRAEGE = alt_min


class _Geofabrik(http.server.BaseHTTPRequestHandler):
    """Lokaler Ersatz für download.geofabrik.de: `antworten` je Pfad eine
    Liste von (Status, Kopfzeilen, Körper); die letzte gilt weiter."""
    antworten = {}
    anfragen = []

    def do_GET(self):
        type(self).anfragen.append(self.path)
        liste = type(self).antworten.get(self.path) or [(404, {}, b'')]
        status, kopf, koerper = liste.pop(0) if len(liste) > 1 else liste[0]
        self.send_response(status)
        for k, v in kopf.items():
            self.send_header(k, v)
        if 'Content-Length' not in kopf and status != 307:
            self.send_header('Content-Length', str(len(koerper)))
        self.end_headers()
        self.wfile.write(koerper)
        self.close_connection = True

    def log_message(self, *a):
        pass


class Download(unittest.TestCase):
    """Audit 11.5: Länge und .md5 prüfen, bis zu drei Versuche."""
    INHALT = b'PBF' * 400  # 1200 Byte

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(('127.0.0.1', 0), _Geofabrik)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.basis = 'http://127.0.0.1:%d/' % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        import geofabrik
        self.geofabrik = geofabrik
        _Geofabrik.anfragen = []
        md5 = hashlib.md5(self.INHALT).hexdigest()
        # Wie Geofabrik: -latest leitet auf die Datei mit Datum weiter.
        _Geofabrik.antworten = {
            '/europe/switzerland-latest.osm.pbf': [(307, {'Location': '/europe/switzerland-261111.osm.pbf'}, b'')],
            '/europe/switzerland-261111.osm.pbf': [(200, {}, self.INHALT)],
            '/europe/switzerland-261111.osm.pbf.md5': [(200, {}, ('%s  switzerland-261111.osm.pbf\n' % md5).encode())],
        }
        self.ziel = os.path.join(tempfile.mkdtemp(), 'ch.osm.pbf')
        self.stderr = sys.stderr
        sys.stderr = io.StringIO()

    def tearDown(self):
        sys.stderr = self.stderr

    def laden(self):
        return self.geofabrik.laden('ch', self.ziel, quelle=self.basis + '%s-latest.osm.pbf', pause=0)

    def pbf_abrufe(self):
        return [p for p in _Geofabrik.anfragen if p.endswith('261111.osm.pbf')]

    def test_vollstaendig_und_md5_neben_der_datei(self):
        ende = self.laden()
        self.assertTrue(ende.endswith('/europe/switzerland-261111.osm.pbf'), ende)
        with open(self.ziel, 'rb') as d:
            self.assertEqual(d.read(), self.INHALT)
        self.assertEqual(len(self.pbf_abrufe()), 1)

    def test_md5_der_latest_adresse_als_rueckfall(self):
        a = _Geofabrik.antworten
        a['/europe/switzerland-latest.osm.pbf.md5'] = a.pop('/europe/switzerland-261111.osm.pbf.md5')
        self.laden()
        self.assertIn('/europe/switzerland-latest.osm.pbf.md5', _Geofabrik.anfragen)

    def test_halber_download_dreimal_dann_abbruch(self):
        # Content-Length 1200, nach 600 Byte zu: Pythons read(amt) meldet das nicht selbst.
        _Geofabrik.antworten['/europe/switzerland-261111.osm.pbf'] = [
            (200, {'Content-Length': str(len(self.INHALT))}, self.INHALT[:600])]
        with self.assertRaises(SystemExit) as ctx:
            self.laden()
        self.assertIn('nach 3 Versuchen', str(ctx.exception))
        self.assertEqual(len(self.pbf_abrufe()), 3)
        self.assertIn('600 von 1200 Byte', sys.stderr.getvalue())

    def test_falsche_pruefsumme_dreimal_dann_abbruch(self):
        _Geofabrik.antworten['/europe/switzerland-261111.osm.pbf.md5'] = [
            (200, {}, b'0123456789abcdef0123456789abcdef  switzerland-261111.osm.pbf\n')]
        with self.assertRaises(SystemExit):
            self.laden()
        self.assertEqual(len(self.pbf_abrufe()), 3)
        self.assertIn('Prüfsumme', sys.stderr.getvalue())

    def test_ohne_md5_abbruch(self):
        del _Geofabrik.antworten['/europe/switzerland-261111.osm.pbf.md5']
        with self.assertRaises(SystemExit):
            self.laden()
        self.assertIn('keine .md5', sys.stderr.getvalue())

    def test_erst_503_dann_200(self):
        _Geofabrik.antworten['/europe/switzerland-261111.osm.pbf'] = [
            (503, {}, b'busy'), (200, {}, self.INHALT)]
        self.laden()
        self.assertEqual(len(self.pbf_abrufe()), 2)
        self.assertIn('Versuch 1 von 3 gescheitert', sys.stderr.getvalue())
        with open(self.ziel, 'rb') as d:
            self.assertEqual(d.read(), self.INHALT)

    def test_ohne_content_length(self):
        _Geofabrik.antworten['/europe/switzerland-261111.osm.pbf'] = [
            (200, {'Content-Length': 'x'}, self.INHALT)]
        with self.assertRaises(SystemExit):
            self.laden()
        self.assertIn('ohne Content-Length', sys.stderr.getvalue())


class Stand(unittest.TestCase):
    """stand.json auf main (Audit 11.6)."""

    def test_berechnen_schreiben_kurz(self):
        import stand
        ordner = tempfile.mkdtemp()
        for land, n in (('de', 3), ('at', 2), ('ch', 1)):
            with open(os.path.join(ordner, land + '.json'), 'w', encoding='utf-8') as d:
                json.dump(datei(gueltig(land, n=n), stand='2026-11-1%d' % n), d)
        daten = stand.berechnen(ordner, heute=datetime.date(2026, 11, 16), quelle='geofabrik')
        self.assertEqual(daten, {'lauf': '2026-11-16', 'quelle': 'geofabrik',
                                 'stand': {'de': '2026-11-13', 'at': '2026-11-12', 'ch': '2026-11-11'},
                                 'eintraege': {'de': 3, 'at': 2, 'ch': 1}})
        pfad = os.path.join(ordner, 'stand.json')
        stand.schreiben(daten, pfad)
        with open(pfad, encoding='utf-8') as d:
            self.assertEqual(json.load(d), daten)
        self.assertEqual(stand.kurz(daten), 'DE 2026-11-13 (3), AT 2026-11-12 (2), CH 2026-11-11 (1)')


class Workflow(unittest.TestCase):
    """Eckpunkte von .github/workflows/orte.yml (ohne YAML-Leser, als Text)."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(__file__), '..', '.github', 'workflows', 'orte.yml'),
                  encoding='utf-8') as d:
            cls.text = d.read()

    def job(self, name):
        """Der Job bis zum nächsten Job (zwei Leerzeichen eingerückt) oder zum Ende."""
        import re
        teile = self.text.split('\n  %s:\n' % name, 1)
        self.assertEqual(len(teile), 2, name)
        return re.split(r'\n  [a-z_]+:\n', teile[1], maxsplit=1)[0]

    def test_krumme_minute_und_osmium_gepinnt(self):
        self.assertIn("- cron: '23 3 * * 1'", self.text)
        self.assertIn("pip install 'osmium==4.3.*'", self.text)
        self.assertNotIn('pip install osmium\n', self.text)

    def test_fehlerprobe_vor_jedem_abruf(self):
        bauen = self.job('bauen')
        self.assertIn('fehlerprobe:', self.text)
        probe = bauen.index('if: ${{ inputs.fehlerprobe }}')
        self.assertLess(probe, bauen.index('actions/checkout'))
        self.assertLess(probe, bauen.index('hole_orte.py'))
        self.assertIn('exit 1', bauen[probe:bauen.index('actions/checkout')])

    def test_melden_bei_fehler_nur_mit_issues_write(self):
        melden = self.job('melden')
        self.assertIn('needs: [bauen, veroeffentlichen, stand]', melden)
        self.assertIn('if: ${{ failure() }}', melden)
        rechte = melden.split('permissions:\n', 1)[1].split('\n    env:', 1)[0]
        self.assertEqual(rechte.split(), ['issues:', 'write'])
        self.assertIn('--label lauf-gescheitert', melden)
        self.assertIn('gh issue comment', melden)

    def test_stand_nach_der_veroeffentlichung_nur_mit_contents_write(self):
        stand = self.job('stand')
        self.assertIn('needs: [bauen, veroeffentlichen]', stand)
        rechte = stand.split('permissions:\n', 1)[1].split('\n    steps:', 1)[0]
        self.assertEqual(rechte.split(), ['contents:', 'write'])
        self.assertIn('git push origin HEAD:main', stand)


if __name__ == '__main__':
    unittest.main()
