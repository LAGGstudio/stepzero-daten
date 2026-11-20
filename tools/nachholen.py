"""Der zweite geplante Lauf (seit Runde 52, Block D): dienstags, etwa 24 Stunden
nach dem Montagslauf. Er arbeitet nur, wenn der veröffentlichte Stand eines
Lands älter als MAX_ALTER_TAGE ist, etwa weil der Montagslauf scheiterte;
sonst endet er gleich grün (orte.yml: Job `vorab`, `bauen` nur mit
`noetig=true`).

  python3 tools/nachholen.py BASIS-URL    # Zeile `noetig=true|false` für $GITHUB_OUTPUT

Der Stand ist das Feld `stand` der veröffentlichten Dateien (`de.json`,
`at.json`, `ch.json` auf GitHub Pages), also das Datum der Daten, nicht des
Laufs. Lässt sich ein Land nicht lesen (keine Datei, kein Netz, kein Datum),
arbeitet der Lauf lieber, als still zu schweigen.
"""
import datetime, os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
from orte import LAENDER  # noqa: E402
import pruefe_orte  # noqa: E402

# Ein Stand bis zu so vielen Tagen gilt als frisch (der Montagslauf liefert
# den Auszug vom Vortag).
MAX_ALTER_TAGE = 7


def staende(basis, laden=pruefe_orte.vorher_laden):
    """Je Land das Datum `stand` der veröffentlichten Datei, sonst None
    (Datei fehlt, Netzfehler, kein Datum). `laden` wie
    pruefe_orte.vorher_laden(basis, land)."""
    raus = {}
    for land in LAENDER:
        try:
            daten = laden(basis, land)
        except Exception as fehler:  # noqa: BLE001
            print('%s: veröffentlichte Datei nicht lesbar: %s' % (land, fehler), file=sys.stderr)
            daten = None
        stand = (daten or {}).get('stand') if isinstance(daten, dict) else None
        if isinstance(stand, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', stand):
            raus[land] = datetime.date.fromisoformat(stand)
        else:
            raus[land] = None
    return raus


def noetig(je_land, heute):
    """True, wenn ein Land keinen Stand hat oder sein Stand älter als
    MAX_ALTER_TAGE ist."""
    return any(s is None or (heute - s).days > MAX_ALTER_TAGE for s in je_land.values())


def main():
    basis = sys.argv[1]
    heute = datetime.datetime.now(datetime.timezone.utc).date()
    je_land = staende(basis)
    for land, s in je_land.items():
        print('%s: Stand %s%s' % (land, s or 'unbekannt', '' if s is None else ', %d Tage alt' % (heute - s).days),
              file=sys.stderr)
    ergebnis = noetig(je_land, heute)
    print('%s' % ('Ein Stand ist älter als %d Tage oder unbekannt: der Lauf arbeitet.' % MAX_ALTER_TAGE
                  if ergebnis else 'Alle Stände sind frisch: der Lauf endet ohne Abruf.'), file=sys.stderr)
    print('noetig=%s' % ('true' if ergebnis else 'false'))


if __name__ == '__main__':
    main()
