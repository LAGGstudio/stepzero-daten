"""Schreibt ausgabe/index.html: Stand, Zahlen je Art und Land, Adressen, Lizenzhinweis."""
import html, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from orte import ART_NAMEN, LAENDER  # noqa: E402

ADRESSE = 'https://laggstudio.github.io/stepzero-daten/'
REPO = 'https://github.com/LAGGstudio/stepzero-daten'
TITEL = {'garten': 'Gemeinschaftsgärten', 'fairteiler': 'Fairteiler', 'verschenkbox': 'Verschenkboxen',
         'buecherschrank': 'Bücherschränke', 'repaircafe': 'Repair-Cafés',
         'trinkbrunnen': 'Trinkbrunnen', 'refill': 'Refill-Stationen'}


def main():
    ordner = sys.argv[1] if len(sys.argv) > 1 else 'ausgabe'
    daten = {}
    for land in LAENDER:
        with open(os.path.join(ordner, land + '.json'), encoding='utf-8') as d:
            daten[land] = json.load(d)
    kopf = ''.join('<th>%s</th>' % l.upper() for l in LAENDER)
    zeilen = ''.join('<tr><td>%s</td>%s</tr>' % (TITEL[k], ''.join(
        '<td>%d</td>' % sum(1 for e in daten[l]['eintraege'] if e['k'] == k) for l in LAENDER)) for k in ART_NAMEN)
    summe = ''.join('<td><b>%d</b></td>' % len(daten[l]['eintraege']) for l in LAENDER)
    stand = ''.join('<li>%s: Stand %s, <a href="%s%s.json">%s%s.json</a> (%d Byte)</li>' % (
        l.upper(), html.escape(daten[l]['stand']), ADRESSE, l, ADRESSE, l,
        os.path.getsize(os.path.join(ordner, l + '.json'))) for l in LAENDER)
    seite = '''<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Step Zero Daten</title>
<style>body{font-family:system-ui,sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem;color:#23301F;background:#FBF5E8}
table{border-collapse:collapse}td,th{border-bottom:1px solid #EDE3CC;padding:.3rem .8rem;text-align:right}td:first-child,th:first-child{text-align:left}</style></head>
<body><h1>Step Zero: Orte in deiner Nähe</h1>
<p>Wöchentlich aus OpenStreetMap geholte Orte für die App Step Zero (DE, AT, CH),
gleiche Orte zusammengeführt (eigene Namen unter 200 m, allgemeine wie „Brunnen“ unter 30 m). Quelle und Ablauf: <a href="%s">%s</a>.</p>
<ul>%s</ul>
<table><tr><th>Art</th>%s</tr>%s<tr><td><b>Zusammen</b></td>%s</tr></table>
<p>Daten © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>,
verfügbar unter der <a href="https://opendatacommons.org/licenses/odbl/1-0/">Open Database License (ODbL) 1.0</a>.</p>
</body></html>
''' % (REPO, REPO, stand, kopf, zeilen, summe)
    with open(os.path.join(ordner, 'index.html'), 'w', encoding='utf-8') as d:
        d.write(seite)
    print('index.html geschrieben')


if __name__ == '__main__':
    main()
