"""Tests für Umwandlung und Prüfung (ohne Netz): python3 -m unittest discover -s tests"""
import datetime, io, json, os, sys, tempfile, unittest

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
    # 0,00089° Breite sind bei 50,9° etwa 99 m, 0,00091° etwa 101 m.
    NAH, WEIT = 50.9 + 0.00089, 50.9 + 0.00091

    def ids(self, eintraege):
        return [e['id'] for e in doppelte_zusammenfuehren(eintraege)[0]]

    def test_abstaende_der_testpunkte(self):
        self.assertLess(abstand_m(ort('n1'), ort('n2', lat=self.NAH)), 100)
        self.assertGreater(abstand_m(ort('n1'), ort('n2', lat=self.WEIT)), 100)
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
            'foodsharing', 'gemeinschaftsgarten', 'garten', 'repaircafe', 'refill']))
        for n in orte.ALLERWELTSNAMEN:
            self.assertEqual(name_schluessel(n), n, 'normalisiert wie beim Vergleich')
        self.assertEqual(set(orte.STANDARDNAMEN), set(orte.ART_NAMEN), 'jede Art')

    def test_allerweltsnamen_nie_zusammenfuehren(self):
        for k, name in (('trinkbrunnen', 'Brunnen'), ('trinkbrunnen', 'Gießwasser'),
                        ('trinkbrunnen', 'Wasch'), ('trinkbrunnen', 'Wasser-Stelle'),
                        ('buecherschrank', 'Offener Bücherschrank'), ('buecherschrank', 'Bücher-Box'),
                        ('buecherschrank', 'Bücherzelle'), ('verschenkbox', 'Give-Box'),
                        ('fairteiler', 'Foodsharing'), ('garten', 'Garten'),
                        ('repaircafe', 'Repair Café'), ('refill', 'REFILL')):
            self.assertTrue(allerweltsname(k, name), name)
            e = [ort('n1', name, k=k), ort('n2', name, k=k, lat=50.9 + 0.0001)]
            self.assertEqual(self.ids(e), ['n1', 'n2'], name)
        # Gegenprobe: ein Name, der nur ein Allerweltswort enthält, ist eigen.
        for k, name in (('trinkbrunnen', 'Brunnen am Markt'), ('buecherschrank', 'Bücherschrank am Ring'),
                        ('garten', 'Garten am Mer')):
            self.assertFalse(allerweltsname(k, name), name)
            e = [ort('n1', name, k=k), ort('n2', name, k=k, lat=50.9 + 0.0001)]
            self.assertEqual(self.ids(e), ['n1'], name)

    def test_standardname_der_eigenen_art(self):
        # Die Standardnamen der App, deutsch und englisch, zählen nur für ihre Art.
        for k, name in (('trinkbrunnen', 'Drinking fountain'), ('buecherschrank', 'Public bookcase'),
                        ('refill', 'Refill-Station'), ('refill', 'Refill station'),
                        ('verschenkbox', 'Give box'), ('fairteiler', 'Food-sharing point'),
                        ('garten', 'Community garden'), ('repaircafe', 'Repair café')):
            self.assertTrue(allerweltsname(k, name), (k, name))
            e = [ort('n1', name, k=k), ort('n2', name, k=k, lat=50.9 + 0.0001)]
            self.assertEqual(self.ids(e), ['n1', 'n2'], name)
        # Gegenprobe: der Standardname einer anderen Art (so am 10.11.2026 zwei
        # Trinkbrunnen namens „Refill-Station“) wird zusammengeführt.
        self.assertFalse(allerweltsname('trinkbrunnen', 'Refill-Station'))
        self.assertFalse(allerweltsname('garten', 'Drinking fountain'))
        e = [ort('n1', 'Refill-Station', k='trinkbrunnen'),
             ort('n2', 'Refill-Station', k='trinkbrunnen', lat=50.9 + 0.0001)]
        self.assertEqual(self.ids(e), ['n1'])

    def test_gleiche_art_gleicher_name_unter_100_m(self):
        e = [ort('n1', 'Querbeet'), ort('n2', 'querbeet', lat=self.NAH)]
        behalten, zusammen = doppelte_zusammenfuehren(e)
        self.assertEqual([x['id'] for x in behalten], ['n1'])
        self.assertEqual(zusammen, {'garten': 1})

    def test_gegenproben_nicht_zusammenfuehren(self):
        # Knapp über 100 m.
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
        # n1 und n3 liegen 180 m auseinander, n2 dazwischen: n2 geht in n1 auf,
        # n3 bleibt, weil es von n1 zu weit weg ist.
        schritt = 0.00081  # etwa 90 m
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
