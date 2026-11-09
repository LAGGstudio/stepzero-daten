"""Tests für Umwandlung und Prüfung (ohne Netz): python3 -m unittest discover -s tests"""
import datetime, json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import hole_orte  # noqa: E402
import pruefe_orte  # noqa: E402
from orte import adresse, art, ausgeschlossen, eintrag  # noqa: E402


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

    def test_umwandeln_kompakt_sortiert_ohne_doppel(self):
        roh = {'osm3s': {'timestamp_osm_base': '2026-11-09T18:00:00Z'}, 'elements': [
            knoten(2, {'amenity': 'drinking_water'}), knoten(1, {'amenity': 'give_box'}),
            knoten(2, {'amenity': 'drinking_water'}), knoten(3, {'shop': 'kiosk'})]}
        d = hole_orte.umwandeln(roh)
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

    def test_overpass_gescheitert_dann_geofabrik(self):
        import geofabrik
        aufrufe = []
        alt_o, alt_g = hole_orte.overpass_holen, geofabrik.holen
        try:
            def overpass(land):
                aufrufe.append(('overpass', land))
                raise SystemExit('nicht erreichbar')
            hole_orte.overpass_holen = overpass
            geofabrik.holen = lambda land: aufrufe.append(('geofabrik', land)) or {'elements': []}
            self.assertEqual(hole_orte.holen('ch'), {'elements': []})
            self.assertEqual(aufrufe, [('overpass', 'ch'), ('geofabrik', 'ch')])
            os.environ['ORTE_QUELLE'] = 'overpass'
            with self.assertRaises(SystemExit):
                hole_orte.holen('ch')
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

    def test_unbrauchbar_fuehrt_zum_rueckfall(self):
        import geofabrik
        alt_o, alt_g = hole_orte.overpass_holen, geofabrik.holen
        try:
            def overpass(land):
                raise hole_orte.Unbrauchbar('de: Overpass-Datenstand 2026-06-01 ist 161 Tage alt')
            hole_orte.overpass_holen = overpass
            geofabrik.holen = lambda land: {'elements': ['auszug']}
            self.assertEqual(hole_orte.holen('de'), {'elements': ['auszug']})
        finally:
            hole_orte.overpass_holen, geofabrik.holen = alt_o, alt_g


HEUTE = datetime.date(2026, 11, 9)


def datei(eintraege, stand='2026-11-09'):
    return {'stand': stand, 'lizenz': 'ODbL 1.0, © OpenStreetMap-Mitwirkende', 'eintraege': eintraege}


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


if __name__ == '__main__':
    unittest.main()
