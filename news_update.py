#!/usr/bin/env python3
"""NFL headlines from publishers' public RSS feeds -> news.json. Run every 30 minutes by the scores workflow.

Headline links only: each item keeps the headline, the source's name, the link to the original story and its publish time,
so the page can credit it and send readers there. No pictures and no story text are stored or shown (the feed's summary
is read only to tag which players a story is about, and then dropped). Any source that fails is skipped and its last
good items are kept, so one broken feed never stops the update. Items older than 7 days drop off.

Each item is tagged with the players it names, a category (injury, transaction, fantasy, betting, news), and, for
clear statements such as "ruled out" or "expected to miss time", a status the prop lines use to pull a line.

Set the repository variable BFF_NEWS_LINKS to off to stop collecting outside headlines altogether (the site then shows
BFF's own articles and the official injury report only).
"""
import json, os, re, html, datetime, urllib.request, email.utils
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

UA = {'User-Agent': 'BFF-fantasy-football/1.0 (+https://github.com)'}
SOURCES = [   # name, feed, homepage, kind, keep(link, title)
    ('CBS Sports', 'https://www.cbssports.com/rss/headlines/nfl/', 'https://www.cbssports.com/nfl/', 'rss', lambda u, t: '/nfl/' in u),
    ('Pro Football Talk', 'https://www.nbcsports.com/profootballtalk.rss', 'https://www.nbcsports.com/nfl/profootballtalk', 'rss', None),
    ('RotoBaller', 'https://www.rotoballer.com/category/nfl/feed', 'https://www.rotoballer.com/nfl', 'rss', None),
    ('PFF', 'https://www.pff.com/feed', 'https://www.pff.com/nfl', 'rss', None),
    ('Sharp Football Analysis', 'https://www.sharpfootballanalysis.com/feed/', 'https://www.sharpfootballanalysis.com/', 'rss', None),
]
ON = (os.environ.get('BFF_NEWS_LINKS') or 'on').strip().lower() not in ('off', '0', 'no', 'false')
COLLEGE = re.compile(r'\b(college football|cfb|ncaa|heisman|big ten|big 12|\bsec\b|\bacc\b|cfp|recruit|bowl game|draft prospect|mock draft 20\d\d|top 25)\b', re.I)
# (Nov 2026: "Todd Monken: Deshaun Watson not ruled out yet, but Shedeur Sanders preparing to start" was tagged as Watson
# ruled out: a negated "ruled out" / "expected to miss" is not a status)
OUT_RE = re.compile(r"((?<!not )(?<!n't )(?<!not been )(?<!n't been )(?<!not yet )(?<!never )(?<!not yet been )ruled out|(?<!n't )(?<!not )(?<!cannot )\brules? out\b|won't play|will not play|will miss|(?<!not )(?<!n't )expected to miss|out for (the )?(season|year|week|game|\w+ weeks?)|\bout for (the )?[\w.]+( [\w.]+)? (in|for) week \d+|out indefinitely|season[- ]ending|"
                    r"(miss|misses|missing|out for) (the )?(rest|remainder) of (the )?(season|year)|done for the (season|year)|"
                    r"placed on (ir|injured reserve)|lands on (ir|injured reserve)|to (ir|injured reserve)\b|inactive for)", re.I)
DOUBT_RE = re.compile(r"\bdoubtful\b(?!\s+to return)", re.I)
QUES_RE = re.compile(r"\b(questionable|probable|game[- ]time decision)\b(?!\s+to return)", re.I)   # doubtful is not out: "Emeka Egbuka considered doubtful for week 7"
OK_RE = re.compile(r"(cleared to play|will play|set to play|activated from|returns? to practice|full participant|no injury designation|good to go|ready to go|ready to play|expected to play|\bactive\b|will suit up)", re.I)
CLAUSE = re.compile(r"\s*(?:[,;|]|\s[-\u2013\u2014]\s|\bbut\b|\bwhile\b|\bas\b|\bafter\b)\s*", re.I)   # headline clauses
CONT = re.compile(r"(headed|heads|placed|lands|going|goes|expected|will|set|ruled|done|out)\b", re.I)   # a clause that carries on about the same player
INJ_RE = re.compile(r'(injur|hamstring|ankle|knee|concussion|questionable|doubtful|ruled out|\bIR\b|out for|miss time|limited|did not practice|MRI|surgery|sprain|strain|torn)', re.I)
TX_RE = re.compile(r'\b(sign(s|ed|ing)?|release[sd]?|waive[sd]?|trade[sd]?|acquire[sd]?|claim(s|ed)?|practice squad|re-sign|extension|contract|cut[s]?)\b', re.I)
FAN_RE = re.compile(r'(fantasy|waiver|start[/ ]sit|sleeper|rankings|\bPPR\b|DFS|dynasty|pickups?|buy low|sell high|breakout)', re.I)
BET_RE = re.compile(r'(\bodds\b|betting|\bbets?\b|\bprops?\b|parlay|spread|over/under|picks? against)', re.I)

def get(url, timeout=12):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r: return r.read()
def clean(s, n=None):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s or '')); s = re.sub(r'\s+', ' ', s).strip()
    if n and len(s) > n: s = s[:n].rsplit(' ', 1)[0].rstrip(',.;:') + '…'
    return s
def when(s):
    try:
        d = email.utils.parsedate_to_datetime(s)
        if d.tzinfo is None: d = d.replace(tzinfo=datetime.timezone.utc)
        return d.astimezone(datetime.timezone.utc).isoformat(timespec='seconds')
    except Exception:
        try: return datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(datetime.timezone.utc).isoformat(timespec='seconds')
        except Exception: return None

def rss(name, url, keep):
    root = ET.fromstring(get(url)); out = []
    for it in root.iter('item'):
        t = clean(it.findtext('title')); u = (it.findtext('link') or '').strip()
        if not t or not u.startswith('http'): continue
        if keep and not keep(u, t): continue
        out.append({'h': t, 'u': u, 'd': when(it.findtext('pubDate') or ''), 's': name, '_x': clean(it.findtext('description'), 300)})   # _x: for tagging only, never stored
    return out
def player_index():
    """Names to match in headlines (from the data job's inputs); only full names, so 'Wilson' alone never matches."""
    try: P = json.load(open('bet_inputs.json'))['players']
    except Exception:
        try: P = json.load(open('ff_data.json'))['players']
        except Exception: return []
    idx = []
    for p in P:
        n = re.sub(r'\s+(jr|sr|ii|iii|iv|v)\.?$', '', (p.get('n') or '').strip(), flags=re.I)   # 'Deebo Samuel Sr.' also matches 'Deebo Samuel'
        if len(n.split()) < 2: continue
        pat = re.escape(n).replace(r'\.', r'\.?').replace("\\'", "['’]?")
        idx.append((re.compile(r'(?<![\w])' + pat + r"(?:\s+(?:Jr|Sr|II|III|IV|V)\.?)?(?![\w])", re.I), p['id']))
    return idx

def tag(it, idx, now):
    txt = it['h'] + ' ' + (it.pop('_x', None) or '')
    for k in ('x', 'img', 'a', 'prem'): it.pop(k, None)   # items saved before Nov 2026 carried a teaser and a picture
    it['p'] = sorted({pid for rx, pid in idx if rx.search(it['h'])} or {pid for rx, pid in idx if rx.search(txt)})[:4]
    h = it['h']
    it['c'] = 'inj' if INJ_RE.search(h) else 'tx' if TX_RE.search(h) else 'bet' if BET_RE.search(h) else 'fan' if FAN_RE.search(h) else 'news'
    # the status applies to the player named in the same clause ("Saquon Barkley set to play, DeVonta Smith ruled out": only
    # Smith is out; "Puka Nacua active, Trent McDuffie inactive": nobody BFF ranks is out)
    for k in ('st', 'so', 'sd', 'sk'): it.pop(k, None)
    so, sd, sk = [], [], []
    if it['p']:
        hits = [(rx, pid) for rx, pid in idx if pid in it['p']]; prev = []; pend = []; lead = None
        out_ = {'out': so, 'doubtful': sd, 'ok': sk}
        for part in CLAUSE.split(h):
            part = part or ''
            ids = [pid for rx, pid in hits if rx.search(part)]
            if not ids and prev and CONT.match(part): ids = prev   # "Lamar Jackson needs thumb surgery, headed to injured reserve"
            s_ = ('out' if OUT_RE.search(part) and not OK_RE.search(part) else 'doubtful' if DOUBT_RE.search(part) and not OK_RE.search(part)
                  else 'ok' if OK_RE.search(part) else 'q' if QUES_RE.search(part) else None)
            if not s_:
                if not ids: prev = []; pend = []; lead = None; continue
                rest = part
                for rx, pid in hits: rest = rx.sub(' ', rest)
                if lead and len(re.findall(r"[A-Za-z]+", re.sub(r"\b(and|plus)\b", ' ', rest, flags=re.I))) <= 1:
                    if lead in out_: out_[lead] += ids   # "Cardinals rule out Jeremiyah Love, Bam Knight, Kendrick Bourne"
                    continue
                lead = None; pend += [i for i in ids if i not in pend]; prev = ids; continue
            # a status covers this clause's players and the names listed just before it ("DeVonta Smith, Dontayvion Wicks
            # ruled out"; "Mike Evans, Nick Bosa among several 49ers ruled out"); "questionable" is a status BFF does not tag
            if s_ in out_: out_[s_] += ids + [i for i in pend if i not in ids]
            first = min((m.start() for rx, pid in hits for m in [rx.search(part)] if m), default=None)
            sm = (OUT_RE if s_ == 'out' else DOUBT_RE if s_ == 'doubtful' else OK_RE if s_ == 'ok' else QUES_RE).search(part)
            lead = s_ if ids and first is not None and sm and sm.start() < first else None   # the status comes before the names
            pend = []; prev = []
    if it['p']: it['so'] = sorted(set(so))   # who the "out" is about (empty: nobody BFF ranks)
    sd = sorted(set(sd) - set(so))   # (sd: doubtful, not ruled out)
    if so: it['st'] = 'out'
    elif sd: it['st'] = 'doubtful'
    elif sk: it['st'] = 'ok'
    if sd: it['sd'] = sd
    if sk: it['sk'] = sorted(set(sk))
    return it

def build_news(write=True):
    now = datetime.datetime.now(datetime.timezone.utc); stamp = now.isoformat(timespec='seconds')
    old = {}
    try: old = json.load(open('news.json'))
    except Exception: pass
    idx = player_index()
    if not ON:   # outside headlines turned off: an empty list
        out = {'at': stamp, 'src': [], 'items': [], 'off': True}
        changed = bool(old.get('items')) or not old.get('off')
        if write and changed: json.dump(out, open('news.json', 'w'), separators=(',', ':'))
        return out, changed
    def run(src):
        name, url, home, kind, keep = src
        try: return name, rss(name, url, keep), None
        except Exception as e: return name, None, str(e)[:120]
    with ThreadPoolExecutor(max_workers=6) as ex: results = list(ex.map(run, SOURCES))
    seen_first = {it['u']: it.get('d') for it in old.get('items') or []}
    items, status = [], []
    for (name, url, home, kind, keep), (_, got, err) in zip(SOURCES, results):
        status.append({'s': name, 'home': home, 'ok': got is not None, 'n': len(got or []), 'err': err})
        for it in got or []:
            if COLLEGE.search(it['h']) or '/college' in it['u'] or 'ncaa' in it['u']: continue
            it['d'] = it['d'] or seen_first.get(it['u']) or stamp      # feeds without a date: first time we saw it
            items.append(it)
    # keep earlier items (short feeds only show their latest few), drop anything older than 7 days, de-duplicate
    cutoff = (now - datetime.timedelta(days=7)).isoformat()
    key = lambda it: re.sub(r'[^a-z0-9]', '', it['h'].lower())[:70]
    merged, keys, urls = [], set(), set()
    for it in sorted(items + (old.get('items') or []), key=lambda x: x.get('d') or '', reverse=True):
        k = key(it)
        if it['u'] in urls or k in keys or (it.get('d') or '') < cutoff: continue
        urls.add(it['u']); keys.add(k); merged.append(tag(it, idx, now))
    merged = merged[:400]
    keep_src = {x[0] for x in SOURCES}
    merged = [it for it in merged if it.get('s') in keep_src]        # sources no longer used (Nov 2026) drop out at once
    out = {'at': stamp, 'src': status, 'items': merged}
    changed = (merged != old.get('items')) or bool(old.get('trend'))
    if write and changed: json.dump(out, open('news.json', 'w'), separators=(',', ':'))
    return out, changed

def fetch_headlines():   # kept for the data job (ff_produce.py)
    return build_news(write=True)[0]['items']

if __name__ == '__main__':
    try:
        out, changed = build_news()
        ok = [s['s'] + f" ({s['n']})" for s in out['src'] if s['ok']]; bad = [s['s'] for s in out['src'] if not s['ok']]
        print(f"news: {len(out['items'])} items from {len(ok)} sources: {', '.join(ok)}" + (f" | unavailable this run: {', '.join(bad)}" if bad else '') + ('' if changed else ' (no change)'))
    except Exception as e:
        print('news update failed, keeping the previous news.json:', e)
