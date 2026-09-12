#!/usr/bin/env python3
"""Test vectors for motoko/src/Rates.mo: the reference computation of exchange rates from
public sources, written independently here in Python (json, csv, Decimal at 34 digits), run
on real replies captured from each source (motoko/test/fixtures/rates/) and on
copies broken in the ways the contract must handle. Writes motoko/test/Rates.test.mo, which
requires the Motoko output to equal this oracle's byte for byte.

Attribution: Thebes Core Team. Licence: Apache 2.0.
"""
import csv, datetime as dt, hashlib, io, json, os, re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext

getcontext().prec = 34
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, '..', 'motoko', 'test', 'fixtures', 'rates')
OUT = os.path.join(HERE, '..', 'motoko', 'test', 'Rates.test.mo')
MAX_AGE, LATEST_SPREAD, PROCEDURE = 7, 3, 'P-TRE-009'
ECB = set('USD JPY CZK DKK GBP HUF PLN RON SEK CHF ISK NOK TRY AUD BRL CAD CNY HKD IDR ILS INR KRW MXN MYR NZD PHP SGD THB ZAR'.split())
MONTHS = {m: i + 1 for i, m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split())}


class Num(str):
    """A JSON number, kept as its literal text."""


def is_code(t): return len(t) == 3 and all('A' <= c <= 'Z' for c in t)
def on_ecb(c): return c == 'EUR' or c in ECB
def iso(t):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', t or ''):
        return None
    try:
        return dt.date(int(t[:4]), int(t[5:7]), int(t[8:]))
    except ValueError:
        return None


def sources(base, quote, as_of):
    if not is_code(base) or not is_code(quote):
        return 'ERR a currency is three capital letters (ISO 4217)'
    if base == quote:
        return 'ERR the two currencies must differ'
    b = base.lower()
    def fz(tag):
        return [('fawaz-jsdelivr', 'fawazahmed0', 'fawaz', f'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{tag}/v1/currencies/{b}.json'),
                ('fawaz-pages', 'fawazahmed0', 'fawaz', f'https://{tag}.currency-api.pages.dev/v1/currencies/{b}.json')]
    out = []
    if as_of is None:
        if on_ecb(base) and on_ecb(quote):
            out.append(('ecb-daily', 'ecb', 'ecbDaily', 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'))
        out += fz('latest')
        out.append(('exchangerate-api', 'exchangerate-api', 'erApi', f'https://open.er-api.com/v6/latest/{base}'))
        out.append(('floatrates', 'floatrates', 'floatrates', f'https://www.floatrates.com/daily/{b}.json'))
    else:
        d = iso(as_of)
        if on_ecb(base) and on_ecb(quote):
            series = quote if base == 'EUR' else base if quote == 'EUR' else f'{base}+{quote}'
            start = (d - dt.timedelta(days=MAX_AGE)).isoformat()
            out.append(('ecb-sdmx', 'ecb', 'ecbSdmx', f'https://data-api.ecb.europa.eu/service/data/EXR/D.{series}.EUR.SP00.A?startPeriod={start}&endPeriod={as_of}&format=csvdata'))
        out += fz(as_of)
    return out


def positive(t):
    if t is None:
        return None
    try:
        r = Decimal(t)
    except (InvalidOperation, ValueError):
        return None
    return r if r.is_finite() and r > 0 else None


def cross(rb, rq):
    b, q = positive(rb), positive(rq)
    return None if b is None or q is None else q / b


def rfc_date(s):
    if not isinstance(s, str) or isinstance(s, Num):
        return None
    p = [x for x in s.split(' ') if x]
    if len(p) < 4 or not p[1].isdigit() or not p[3].isdigit() or p[2] not in MONTHS:
        return None
    try:
        return dt.date(int(p[3]), MONTHS[p[2]], int(p[1]))
    except ValueError:
        return None


def get(j, k): return j.get(k) if isinstance(j, dict) else None
def num_text(v): return v if isinstance(v, str) else None
def str_of(v): return v if isinstance(v, str) and not isinstance(v, Num) else None


def parse(fmt, body, base, quote, as_of):
    if fmt == 'ecbSdmx':
        if as_of is None:
            return (False, 'the ECB data API is used only for a date')
        rows = [r for r in csv.reader(io.StringIO(body)) if r]
        if not rows:
            return (False, 'the reply is empty')
        head = rows[0]
        try:
            ic, idn, idd, iv = (head.index(c) for c in ('CURRENCY', 'CURRENCY_DENOM', 'TIME_PERIOD', 'OBS_VALUE'))
        except ValueError:
            return (False, 'the reply has no CURRENCY, CURRENCY_DENOM, TIME_PERIOD and OBS_VALUE columns')
        need = max(ic, idn, idd, iv)
        data = [(r[ic], r[idd], r[iv]) for r in rows[1:] if len(r) > need and r[idn] == 'EUR']
        def rate_on(c, day):
            if c == 'EUR':
                return '1'
            return next((v for cc, dd, v in data if cc == c and dd == day), None)
        lim, best = iso(as_of), None
        for _, day, _ in data:
            d = iso(day)
            if d and d <= lim:
                rb, rq = rate_on(base, day), rate_on(quote, day)
                if rb is not None and rq is not None and (best is None or d > best[0]):
                    best = (d, rb, rq)
        if best is None:
            return (False, f'no publication on or before {as_of} for both currencies')
        r = cross(best[1], best[2])
        return (True, (r, best[0])) if r is not None else (False, 'a rate is not a positive number')
    if fmt == 'ecbDaily':
        m = re.search(r"time='([^']*)'", body)
        d = iso(m.group(1)) if m else None
        def xml_rate(c):
            if c == 'EUR':
                return '1'
            m2 = re.search(r"currency='" + re.escape(c) + r"'.*?rate='([^']*)", body, re.S)
            return m2.group(1) if m2 else None
        rb, rq = xml_rate(base), xml_rate(quote)
        if d is None:
            return (False, 'the reply carries no publication date')
        if rb is None or rq is None:
            return (False, 'the reply does not carry both currencies')
        r = cross(rb, rq)
        return (True, (r, d)) if r is not None else (False, 'a rate is not a positive number')
    try:
        j = json.loads(body, parse_float=Num, parse_int=Num)
    except ValueError:
        return (False, 'the reply is not JSON')
    lb, lq = base.lower(), quote.lower()
    if fmt == 'fawaz':
        rate_text = num_text(get(get(j, lb), lq))
        ds = str_of(get(j, 'date'))
        day = iso(ds) if ds is not None else None
    elif fmt == 'erApi':
        if str_of(get(j, 'result')) != 'success':
            return (False, 'the source reported an error')
        if str_of(get(j, 'base_code')) != base:
            return (False, 'the reply is for another base currency')
        rate_text = num_text(get(get(j, 'rates'), quote))
        day = rfc_date(get(j, 'time_last_update_utc'))
    else:
        e = get(j, lq)
        if str_of(get(e, 'code')) != quote:
            return (False, f'the reply does not carry {quote}')
        rate_text = num_text(get(e, 'rate'))
        day = rfc_date(get(e, 'date'))
    if rate_text is None:
        return (False, f'the reply does not carry {quote} against {base}')
    if day is None:
        return (False, 'the reply carries no publication date')
    r = positive(rate_text)
    return (True, (r, day)) if r is not None else (False, 'a rate is not a positive number')


def check_age(o, as_of):
    if as_of is None:
        return (True, o)
    lim = iso(as_of)
    if o[1] > lim:
        return (False, f'published after {as_of}')
    if (lim - o[1]).days > MAX_AGE:
        return (False, f'published more than {MAX_AGE} days before {as_of}')
    return (True, o)


def bps(x): return str(x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
def gap_bps(a, m): return abs(a - m) * Decimal(10000) / m
def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / Decimal(2)
def plural(n): return f'{n} publisher' + ('' if n == 1 else 's')


def reduce(base, quote, as_of, fetched, min_p, bound_bps, corr):
    obs, pubs, got = [], [], []
    for (sid, pub, fmt, url), body, sha in fetched:
        if pub not in pubs:
            pubs.append(pub)
        if body[0] == 'err':
            r = (False, body[1])
        else:
            r = parse(fmt, body[1], base, quote, as_of)
            if r[0]:
                r = check_age(r[1], as_of)
        common = {'source': sid, 'publisher': pub, 'url': url, 'body_sha256': sha}
        if r[0]:
            got.append((pub, r[1][0], r[1][1]))
            obs.append({**common, 'status': 'ok', 'rate': str(r[1][0]), 'date': r[1][1].isoformat(), 'reason': None})
        else:
            obs.append({**common, 'status': 'refused', 'rate': None, 'date': None, 'reason': r[1]})
    cand, why, mirrors = {}, {}, {}
    for p in pubs:
        mine = [(r, d) for pp, r, d in got if pp == p]
        mirrors[p] = len(mine)
        if not mine:
            cand[p], why[p] = None, 'no usable observation'
        elif all(r == mine[0][0] and d == mine[0][1] for r, d in mine):
            cand[p] = mine[0]
        else:
            cand[p], why[p] = None, 'its mirrors disagree'
    if as_of is None:
        dates = [c[1] for c in cand.values() if c]
        if dates:
            newest = max(dates)
            for p in pubs:
                if cand[p] and (newest - cand[p][1]).days > LATEST_SPREAD:
                    why[p] = f'stale: dated {cand[p][1].isoformat()}, the newest source is dated {newest.isoformat()}'
                    cand[p] = None
    bound = Decimal(bound_bps)
    all_rates = [c[0] for c in cand.values() if c]
    if all_rates:
        m0 = median(all_rates)
        for p in pubs:
            if cand[p]:
                g = gap_bps(cand[p][0], m0)
                if g > bound:
                    cand[p], why[p] = None, f'outlier: {bps(g)} basis points from the median of all publishers'
    kept = [cand[p][0] for p in pubs if cand[p]]
    used = len(kept)
    med = median(kept) if kept else None
    spread = (max(kept) - min(kept)) * Decimal(10000) / med if kept else None
    corr_j, corr_gap = None, None
    if corr is not None:
        cr = positive(corr[0])
        if cr is not None and med is not None:
            corr_gap = gap_bps(cr, med)
            corr_j = {'rate': corr[0], 'note': corr[1], 'deviation_bps': bps(corr_gap)}
        else:
            corr_j = {'rate': corr[0], 'note': corr[1], 'deviation_bps': None}
    accepted, basis = False, None
    if med is not None:
        if spread > bound:
            reason = f'the publishers differ by {bps(spread)} basis points, more than the bound of {bound_bps}'
        elif used >= min_p:
            accepted, basis = True, 'publishers'
            reason = f'{plural(used)} {"is" if used == 1 else "agree"} within {bound_bps} basis points'
        elif corr is None:
            reason = f"only {plural(used)} (minimum {min_p}); enter the central bank's published rate to corroborate it"
        elif corr_gap is None:
            reason = 'the corroborating rate is not a positive number'
        elif corr_gap > bound:
            reason = f'the corroborating rate differs from the median by {bps(corr_gap)} basis points, more than the bound of {bound_bps}'
        else:
            accepted, basis = True, 'corroborated_by_auditor'
            reason = f'{plural(used)}, corroborated by the auditor within {bound_bps} basis points'
    else:
        reason = (f'the publishers disagree: none lies within {bound_bps} basis points of the median' if all_rates
                  else 'no publisher gave a usable rate')
    publishers = [{'publisher': p, 'used': bool(cand[p]), 'rate': str(cand[p][0]) if cand[p] else None,
                   'date': cand[p][1].isoformat() if cand[p] else None, 'mirrors': mirrors[p],
                   'reason': None if cand[p] else why[p]} for p in pubs]
    out = {'procedure': PROCEDURE, 'pair': f'{base}/{quote}', 'base': base, 'quote': quote,
           'mode': 'latest' if as_of is None else 'as_of', 'as_of': as_of, 'observations': obs,
           'publishers': publishers, 'used': used, 'min_publishers': min_p, 'bound_bps': bound_bps,
           'median': str(med) if med is not None else None, 'spread_bps': bps(spread) if spread is not None else None,
           'corroboration': corr_j, 'accepted': accepted, 'basis': basis, 'reason': reason}
    return accepted, json.dumps(out, sort_keys=True, separators=(',', ':'))


# ---------------------------------------------------------------------- the bodies

def fx(name): return open(os.path.join(FIX, name), encoding='utf-8').read()
def swap(s, old, new):
    assert s.count(old) == 1, old
    return s.replace(old, new)

BODIES = {
    'FAWAZ_LATEST': fx('fawaz-usd-latest.json'),
    'FAWAZ_1231': fx('fawaz-usd-2025-12-31.json'),
    'ERAPI': fx('erapi-usd-latest.json'),
    'FLOAT': fx('floatrates-usd.json'),
    'ECB_DAILY': fx('ecb-daily.xml'),
    'SDMX_1231': fx('ecb-sdmx-2025-12-31.csv'),
    'SDMX_WINDOW': fx('ecb-sdmx-2026-01-04-window.csv'),
    'WAF': "<html><head><title>Request Rejected</title></head>\n<body>The requested URL was rejected. Please consult with your administrator.</body></html>\n",
}
egp_float = re.search(r'"egp":\{[^}]*\}', BODIES['FLOAT']).group(0)
BODIES['FLOAT_OUTLIER'] = swap(BODIES['FLOAT'], egp_float, egp_float.replace('"rate":"51.24189171"', '"rate":"60.00000000"'))
egp_fz = re.search(r'"egp": *[0-9.]+', BODIES['FAWAZ_LATEST']).group(0)
BODIES['FAWAZ_TAMPER'] = swap(BODIES['FAWAZ_LATEST'], egp_fz, egp_fz[:-1] + ('1' if egp_fz[-1] != '1' else '2'))
stamp = re.search(r'"time_last_update_utc":"([^"]*)"', BODIES['ERAPI']).group(1)
BODIES['ERAPI_STALE'] = swap(BODIES['ERAPI'], stamp, 'Sat, 05 Sep 2026 00:02:31 +0000')
assert BODIES['FLOAT_OUTLIER'] != BODIES['FLOAT'] and BODIES['FAWAZ_TAMPER'] != BODIES['FAWAZ_LATEST']

def ok(name): return ('ok', name)
def err(msg): return ('err', msg)
CORR = 'CBE published rate, read by the auditor'

# (name, base, quote, as_of, {source id: body}, min publishers, bound bps, corroboration)
CASES = [
    ('USD/EGP today: three publishers agree', 'USD', 'EGP', None,
     {'fawaz-jsdelivr': ok('FAWAZ_LATEST'), 'fawaz-pages': ok('FAWAZ_LATEST'), 'exchangerate-api': ok('ERAPI'), 'floatrates': ok('FLOAT')}, 2, 50, None),
    ('USD/EGP today: three publishers required', 'USD', 'EGP', None,
     {'fawaz-jsdelivr': ok('FAWAZ_LATEST'), 'fawaz-pages': ok('FAWAZ_LATEST'), 'exchangerate-api': ok('ERAPI'), 'floatrates': ok('FLOAT')}, 3, 50, None),
    ('USD/EGP today: a tight bound leaves the furthest publisher out', 'USD', 'EGP', None,
     {'fawaz-jsdelivr': ok('FAWAZ_LATEST'), 'fawaz-pages': ok('FAWAZ_LATEST'), 'exchangerate-api': ok('ERAPI'), 'floatrates': ok('FLOAT')}, 2, 5, None),
    ('USD/EGP today: a planted wrong rate is outvoted', 'USD', 'EGP', None,
     {'fawaz-jsdelivr': ok('FAWAZ_LATEST'), 'fawaz-pages': ok('FAWAZ_LATEST'), 'exchangerate-api': ok('ERAPI'), 'floatrates': ok('FLOAT_OUTLIER')}, 2, 50, None),
    ('USD/EGP today: mirrors that disagree leave their publisher out', 'USD', 'EGP', None,
     {'fawaz-jsdelivr': ok('FAWAZ_LATEST'), 'fawaz-pages': ok('FAWAZ_TAMPER'), 'exchangerate-api': ok('ERAPI'), 'floatrates': ok('FLOAT')}, 2, 50, None),
    ('USD/EGP today: a stale publisher is left out', 'USD', 'EGP', None,
     {'fawaz-jsdelivr': ok('FAWAZ_LATEST'), 'fawaz-pages': ok('FAWAZ_LATEST'), 'exchangerate-api': ok('ERAPI_STALE'), 'floatrates': ok('FLOAT')}, 2, 50, None),
    ('USD/EGP today: failed fetches leave too few publishers', 'USD', 'EGP', None,
     {'fawaz-jsdelivr': ok('FAWAZ_LATEST'), 'fawaz-pages': ok('FAWAZ_LATEST'), 'exchangerate-api': err('no agreement at quorum 4'), 'floatrates': ok('WAF')}, 2, 50, None),
    ('USD/EGP today: two publishers too far apart for the bound', 'USD', 'EGP', None,
     {'fawaz-jsdelivr': ok('FAWAZ_LATEST'), 'fawaz-pages': ok('FAWAZ_LATEST'), 'exchangerate-api': err('no agreement at quorum 4'), 'floatrates': ok('FLOAT')}, 2, 1, None),
    ('USD/EGP at 31 December 2025: one publisher is not enough', 'USD', 'EGP', '2025-12-31',
     {'fawaz-jsdelivr': ok('FAWAZ_1231'), 'fawaz-pages': ok('FAWAZ_1231')}, 2, 50, None),
    ('USD/EGP at 31 December 2025: corroborated by the auditor', 'USD', 'EGP', '2025-12-31',
     {'fawaz-jsdelivr': ok('FAWAZ_1231'), 'fawaz-pages': ok('FAWAZ_1231')}, 2, 50, ('47.7200', CORR)),
    ('USD/EGP at 31 December 2025: a corroborating rate too far away', 'USD', 'EGP', '2025-12-31',
     {'fawaz-jsdelivr': ok('FAWAZ_1231'), 'fawaz-pages': ok('FAWAZ_1231')}, 2, 50, ('49.10', CORR)),
    ('USD/EGP at 31 December 2025: a corroborating rate that is not a number', 'USD', 'EGP', '2025-12-31',
     {'fawaz-jsdelivr': ok('FAWAZ_1231'), 'fawaz-pages': ok('FAWAZ_1231')}, 2, 50, ('about 47', CORR)),
    ('USD/GBP at 31 December 2025: the ECB and the currency-api agree', 'USD', 'GBP', '2025-12-31',
     {'ecb-sdmx': ok('SDMX_1231'), 'fawaz-jsdelivr': ok('FAWAZ_1231'), 'fawaz-pages': ok('FAWAZ_1231')}, 2, 50, None),
    ('USD/GBP at Sunday 4 January 2026: the last publication before it', 'USD', 'GBP', '2026-01-04',
     {'ecb-sdmx': ok('SDMX_WINDOW')}, 2, 50, None),
    ('USD/GBP at 20 January 2026: the publication is too old', 'USD', 'GBP', '2026-01-20',
     {'ecb-sdmx': ok('SDMX_WINDOW')}, 2, 50, None),
    ('USD/GBP at 20 December 2025: nothing published on or before it', 'USD', 'GBP', '2025-12-20',
     {'ecb-sdmx': ok('SDMX_WINDOW')}, 2, 50, None),
    ('EUR/USD today: replies for another base are refused', 'EUR', 'USD', None,
     {'ecb-daily': ok('ECB_DAILY'), 'fawaz-jsdelivr': ok('FAWAZ_LATEST'), 'fawaz-pages': ok('FAWAZ_LATEST'), 'exchangerate-api': ok('ERAPI'), 'floatrates': ok('FLOAT')}, 1, 50, None),
]

SOURCE_CASES = [('USD', 'EGP', None), ('USD', 'GBP', '2025-12-31'), ('EUR', 'USD', None), ('EUR', 'USD', '2026-01-04'), ('usd', 'EGP', None), ('USD', 'USD', None)]


def mo(s):
    out = []
    for c in s:
        o = ord(c)
        if c == '\\': out.append('\\\\')
        elif c == '"': out.append('\\"')
        elif c == '\n': out.append('\\n')
        elif c == '\r': out.append('\\r')
        elif c == '\t': out.append('\\t')
        elif o < 32 or o > 126: out.append('\\u{%x}' % o)
        else: out.append(c)
    return '"' + ''.join(out) + '"'

def mo_mode(as_of): return '#latest' if as_of is None else f'#asOf(d("{as_of}"))'
def sha(s): return hashlib.sha256(s.encode()).hexdigest()


def main():
    L = ['// Generated by tools/gen_rates_test.py: exchange rates from public sources, reduced across',
         '// publishers, byte-identical to the Python oracle. Do not edit by hand.',
         '// Attribution: Thebes Core Team. Licence: Apache 2.0.',
         'import R "../src/Rates";', 'import Dates "../src/Dates";', 'import Json "../src/Json";',
         'import Array "mo:core/Array";', 'import Nat "mo:core/Nat";', 'import Debug "mo:core/Debug";', 'import Runtime "mo:core/Runtime";', '',
         'var checks = 0;', 'var failed = 0;',
         'func check(name : Text, cond : Bool) { checks += 1; if (not cond) { failed += 1; Debug.print("FAIL " # name) } };',
         'func d(t : Text) : Dates.Date { switch (Dates.parse(t)) { case (?x) x; case null Runtime.trap(t) } };',
         'func listed(r : { #ok : [R.Source]; #err : Text }) : Text {',
         '  switch (r) { case (#err(m)) "ERR " # m; case (#ok(xs)) { var t = ""; for (s in xs.vals()) t #= s.id # " " # s.publisher # " " # s.url # "\\n"; t } }',
         '};',
         'func run(base : Text, quote : Text, mode : R.Mode, bodies : [(Text, { #ok : Text; #err : Text }, Text)], minP : Nat, bound : Nat, corr : ?R.Corroboration) : R.Result {',
         '  let srcs = switch (R.sources(base, quote, mode)) { case (#ok(s)) s; case (#err(m)) Runtime.trap(m) };',
         '  let fetched = Array.map<R.Source, R.Fetched>(srcs, func(s) {',
         '    switch (Array.find<(Text, { #ok : Text; #err : Text }, Text)>(bodies, func(b) { b.0 == s.id })) {',
         '      case (?b) { { source = s; body = b.1; bodySha256 = b.2 } };',
         '      case null { { source = s; body = #err("not fetched"); bodySha256 = "" } };',
         '    }',
         '  });',
         '  R.reduce(base, quote, mode, fetched, minP, bound, corr)',
         '};', '']
    for k, v in BODIES.items():
        L.append(f'let {k} = {mo(v)};')
    L.append('')
    for base, quote, as_of in SOURCE_CASES:
        s = sources(base, quote, as_of)
        want = s if isinstance(s, str) else ''.join(f'{i} {p} {u}\n' for i, p, _, u in s)
        L.append(f'check({mo(f"sources {base}/{quote} {as_of or chr(116)+chr(111)+chr(100)+chr(97)+chr(121)}")}, listed(R.sources({mo(base)}, {mo(quote)}, {mo_mode(as_of)})) == {mo(want)});')
    L.append('')
    accepted_count = 0
    for name, base, quote, as_of, bodies, min_p, bound, corr in CASES:
        srcs = sources(base, quote, as_of)
        fetched = []
        mo_bodies = []
        for sid, pub, fmt, url in srcs:
            b = bodies.get(sid)
            if b is None:
                fetched.append(((sid, pub, fmt, url), ('err', 'not fetched'), ''))
                continue
            if b[0] == 'ok':
                text = BODIES[b[1]]
                fetched.append(((sid, pub, fmt, url), ('ok', text), sha(text)))
                mo_bodies.append(f'({mo(sid)}, #ok({b[1]}), {mo(sha(text))})')
            else:
                fetched.append(((sid, pub, fmt, url), ('err', b[1]), ''))
                mo_bodies.append(f'({mo(sid)}, #err({mo(b[1])}), "")')
        acc, want = reduce(base, quote, as_of, fetched, min_p, bound, corr)
        accepted_count += acc
        mc = 'null' if corr is None else f'?{{ rate = {mo(corr[0])}; note = {mo(corr[1])} }}'
        L.append('do {')
        L.append(f'  let r = run({mo(base)}, {mo(quote)}, {mo_mode(as_of)}, [{", ".join(mo_bodies)}], {min_p}, {bound}, {mc});')
        L.append(f'  check({mo(name + ": accepted")}, r.accepted == {"true" if acc else "false"});')
        L.append(f'  let got = Json.toText(r.output);')
        L.append(f'  let want = {mo(want)};')
        L.append(f'  if (got != want) Debug.print("GOT  " # got # "\\nWANT " # want);')
        L.append(f'  check({mo(name + ": output")}, got == want);')
        L.append('};')
    L += ['', f'Debug.print("count: rate cases = {len(CASES)}");', f'Debug.print("count: accepted cases = {accepted_count}");',
          'Debug.print("count: checks = " # Nat.toText(checks));',
          'if (failed > 0) Runtime.trap(Nat.toText(failed) # " checks failed");', 'Debug.print("RATES GREEN");', '']
    open(OUT, 'w').write('\n'.join(L))
    print(f'wrote {OUT}: {len(CASES)} cases ({accepted_count} accepted), {len(SOURCE_CASES)} source lists')
    for name, base, quote, as_of, bodies, min_p, bound, corr in CASES:
        srcs = sources(base, quote, as_of)
        f = [((s[0], s[1], s[2], s[3]), (('ok', BODIES[bodies[s[0]][1]]) if bodies.get(s[0], ('err',))[0] == 'ok' else ('err', bodies.get(s[0], ('err', 'not fetched'))[1])), '') for s in srcs]
        acc, out = reduce(base, quote, as_of, f, min_p, bound, corr)
        o = json.loads(out)
        print(f'  {"ACCEPT" if acc else "refuse"}  {name}: median {o["median"]}, spread {o["spread_bps"]} bps; {o["reason"]}')


if __name__ == '__main__':
    main()
