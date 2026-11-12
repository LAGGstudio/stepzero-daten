"""Die kleine stand.json, die jeder erfolgreiche Lauf auf main committet
(seit dem 12.11.2026, Audit 11.6): Laufdatum, Quelle, Datenstand und Zahl der
Einträge je Land. Sie ist zugleich Aktivität im öffentlichen Repo, ohne die
GitHub zeitgesteuerte Läufe nach 60 Tagen abschaltet (README, „Wächter“).

  python3 tools/stand.py ausgabe            # Zeile `stand=…` für $GITHUB_OUTPUT
  STAND='…' python3 tools/stand.py --schreiben stand.json
  python3 tools/stand.py --kurz stand.json  # eine Zeile für die Commit-Nachricht
"""
import datetime, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from orte import LAENDER  # noqa: E402


def berechnen(ordner, heute=None, quelle=None):
    stand, eintraege = {}, {}
    for land in LAENDER:
        with open(os.path.join(ordner, land + '.json'), encoding='utf-8') as d:
            daten = json.load(d)
        stand[land] = daten['stand']
        eintraege[land] = len(daten['eintraege'])
    return {
        'lauf': (heute or datetime.datetime.now(datetime.timezone.utc).date()).isoformat(),
        'quelle': quelle or os.environ.get('ORTE_QUELLE') or 'geofabrik',
        'stand': stand,
        'eintraege': eintraege,
    }


def schreiben(daten, pfad):
    with open(pfad, 'w', encoding='utf-8') as d:
        json.dump(daten, d, ensure_ascii=False, indent=2)
        d.write('\n')


def kurz(daten):
    return ', '.join('%s %s (%d)' % (l.upper(), daten['stand'][l], daten['eintraege'][l]) for l in LAENDER)


def main():
    if sys.argv[1:2] == ['--schreiben']:
        schreiben(json.loads(os.environ['STAND']), sys.argv[2])
    elif sys.argv[1:2] == ['--kurz']:
        with open(sys.argv[2], encoding='utf-8') as d:
            print(kurz(json.load(d)))
    else:
        ordner = sys.argv[1] if len(sys.argv) > 1 else 'ausgabe'
        print('stand=' + json.dumps(berechnen(ordner), ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    main()
