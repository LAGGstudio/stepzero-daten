"""Öffnungszeiten aus OSM (`opening_hours`) als lesbarer Text, deutsch und
englisch (seit Runde 54, für die Art `markt`). Feste Regeln für die häufigen
Muster, kein Sprachmodell; was nicht sicher passt, bekommt keinen Text.

Verstanden wird (Leerraum um `-` und `,` ist erlaubt):
  - Tage `Mo Tu We Th Fr Sa Su`, einzeln, als Bereich (`Mo-Fr`) und als Liste
    (`We,Sa`, `Mo-Mi,Fr`);
  - Zeiten `HH:MM-HH:MM` (Stunde auch einstellig), mehrere mit Komma
    (`08:00-12:00,14:00-18:00`), Ende bis `24:00`, Anfang vor Ende;
  - eine Regel ohne Tage gilt täglich (`08:00-13:00`);
  - mehrere Regeln mit Semikolon (`Tu,Fr 08:00-13:00; Sa 07:00-12:00`), ein
    Semikolon am Ende stört nicht;
  - `<Tage> off`, wenn diese Tage in keiner anderen Regel vorkommen (dann sagt
    die Regel nichts Neues und fällt weg).

Keinen Text bekommt alles andere: Feiertage (`PH`, `SH`), Monate und Daten
(`Apr-Oct`), Wochen, n-te Wochentage (`Sa[1]`), `24/7`, offenes Ende
(`08:00+`), Sonnenauf- und -untergang, Kommentare in Anführungszeichen, `||`,
ein Komma zwischen Regeln (`Mo-Fr 08:00-12:00, Sa 09:00-12:00`, im Standard
eine Zusatzregel), Zeiten über Mitternacht, und ein Tag, der in zwei Regeln
mit Zeiten steht (die spätere ersetzte die frühere; ein Text mit beiden
täuschte).

Ausgabe: deutsch „Mi, Sa 8–13 Uhr“, „Mo–Fr 8–12, 14–18 Uhr“, „täglich
7:30–12 Uhr“, Regeln mit „; “; englisch im 12-Stunden-Format wie die
englischen Texte der App („10 p.m.“): „Wed, Sat 8 a.m.–1 p.m.“, „Mon–Fri
8 a.m.–12 p.m., 2 p.m.–6 p.m.“, „daily 7:30 a.m.–12 p.m.“; ein Ende um
24:00 heißt „24 Uhr“ bzw. „midnight“.
"""
import re

TAGE = ('Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su')
TAGE_DE = ('Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So')
TAGE_EN = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

# Längere Angaben sind fast immer Sonderfälle; sie bekommen keinen Text.
MAX_LAENGE = 200

_TAG = r'(?:Mo|Tu|We|Th|Fr|Sa|Su)'
_BEREICH = r'%s(?:\s*-\s*%s)?' % (_TAG, _TAG)
_TAGE = r'%s(?:\s*,\s*%s)*' % (_BEREICH, _BEREICH)
_ZEIT = r'\d{1,2}:\d{2}'
_SPANNE = r'%s\s*-\s*%s' % (_ZEIT, _ZEIT)
_SPANNEN = r'%s(?:\s*,\s*%s)*' % (_SPANNE, _SPANNE)
_REGEL_ZEITEN = re.compile(r'(?:(%s)\s+)?(%s)' % (_TAGE, _SPANNEN))
_REGEL_ZU = re.compile(r'(%s)\s+off' % _TAGE)


class _Unklar(ValueError):
    """Passt nicht sicher: kein Text."""


def _tage(text):
    """'Mo-Fr, Su' → ([(0, 4), (6, 6)], {0, 1, 2, 3, 4, 6}); ein Bereich über
    das Wochenende (`Fr-Mo`) läuft weiter bis Montag."""
    bereiche, menge = [], set()
    for teil in re.split(r'\s*,\s*', text.strip()):
        stuecke = [t.strip() for t in teil.split('-')]
        von = TAGE.index(stuecke[0])
        bis = TAGE.index(stuecke[-1])
        bereiche.append((von, bis))
        tag = von
        while True:
            if tag in menge:
                raise _Unklar('Tag doppelt')
            menge.add(tag)
            if tag == bis:
                break
            tag = (tag + 1) % 7
    return bereiche, menge


def _minuten(zeit, ende=False):
    stunde, minute = (int(x) for x in zeit.split(':'))
    if minute > 59 or stunde > 24 or (stunde == 24 and (minute or not ende)):
        raise _Unklar('Zeit %s' % zeit)
    return stunde * 60 + minute


def _spannen(text):
    raus = []
    for teil in re.split(r'\s*,\s*', text.strip()):
        von, bis = re.split(r'\s*-\s*', teil)
        a, b = _minuten(von), _minuten(bis, ende=True)
        if a >= b:
            raise _Unklar('Spanne %s' % teil)
        if raus and a < raus[-1][1]:
            raise _Unklar('Spannen überlappen')
        raus.append((a, b))
    return raus


def _tage_text(bereiche, namen):
    return ', '.join(namen[a] if a == b else '%s–%s' % (namen[a], namen[b]) for a, b in bereiche)


def _de_zeit(m):
    stunde, minute = divmod(m, 60)
    return '%d' % stunde if not minute else '%d:%02d' % (stunde, minute)


def _en_zeit(m):
    stunde, minute = divmod(m, 60)
    if stunde == 24:
        return 'midnight'
    teil = 'a.m.' if stunde % 24 < 12 else 'p.m.'
    h = stunde % 12 or 12
    return ('%d %s' % (h, teil)) if not minute else ('%d:%02d %s' % (h, minute, teil))


def _de_spannen(spannen):
    return ', '.join('%s–%s' % (_de_zeit(a), _de_zeit(b)) for a, b in spannen) + ' Uhr'


def _en_spannen(spannen):
    return ', '.join('%s–%s' % (_en_zeit(a), _en_zeit(b)) for a, b in spannen)


def lesbar(roh):
    """`opening_hours` → {'de': …, 'en': …} oder None, wenn es nicht sicher
    passt."""
    if not isinstance(roh, str):
        return None
    text = ' '.join(roh.split())
    if not text or len(text) > MAX_LAENGE:
        return None
    regeln = [r.strip() for r in text.split(';')]
    if regeln and not regeln[-1]:
        regeln.pop()
    if not regeln or any(not r for r in regeln):
        return None
    try:
        offen, zu = [], []
        for regel in regeln:
            m = _REGEL_ZEITEN.fullmatch(regel)
            if m:
                tage = _tage(m.group(1)) if m.group(1) else (None, set(range(7)))
                offen.append((tage, _spannen(m.group(2))))
                continue
            m = _REGEL_ZU.fullmatch(regel)
            if m:
                zu.append(_tage(m.group(1))[1])
                continue
            return None
        if not offen:
            return None
        belegt = set()
        for (_, menge), _ in offen:
            if belegt & menge:
                return None
            belegt |= menge
        for menge in zu:
            if belegt & menge:
                return None
    except (_Unklar, ValueError):
        return None
    de, en = [], []
    for (bereiche, _), spannen in offen:
        if bereiche is None:
            de.append('täglich ' + _de_spannen(spannen))
            en.append('daily ' + _en_spannen(spannen))
        else:
            de.append('%s %s' % (_tage_text(bereiche, TAGE_DE), _de_spannen(spannen)))
            en.append('%s %s' % (_tage_text(bereiche, TAGE_EN), _en_spannen(spannen)))
    return {'de': '; '.join(de), 'en': '; '.join(en)}
