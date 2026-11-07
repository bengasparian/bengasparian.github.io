"""BFF Originals: data-driven fantasy football articles, written and updated automatically, like a weekly newsletter.

Runs every 30 minutes with the score job (standard library only). Each run decides what should exist right now (Eastern time):
  * Thursday outlook    - Thursday 8 AM, the Thursday game(s): matchup, fantasy breakdown, start/sit, props to know, the score Vegas implies.
  * Thursday recap      - Friday 7 AM (once the game is final): how it happened, every fantasy-relevant line, stock up and
                          down, waiver adds, what is next.
  * Injury report       - Friday 5 PM: who is out, game-time decisions, quarterback situations and who benefits.
  * Sunday outlook      - Saturday 8 AM: the whole Sunday slate, game by game, start/sit, sleepers and props to know.
  * Sunday recap        - once the afternoon games are final and nflverse has the box scores: scores, top performances, game by
                          game, stock up and down, injuries to watch and an early waiver look.
  * Sunday night recap  - once the night game is final.
  * Monday outlook      - Monday 8 AM; Monday recap once the game is final.
  * Other game days     - Friday, Saturday, Christmas or international games: an outlook that morning, a recap the next.
  * Fantasy landscape   - Tuesday 10 AM, after the week: MVPs, risers, fallers, injury fallout, waiver priorities, buy
                          low and sell high, next week's byes and best matchups, and our weekly calls scorecard.
  * Breaking news       - a relevant player ruled out, placed on injured reserve, traded or released (at most 3 a run, 12 a day).
Outlooks and the injury report are rewritten when their facts change (until kickoff), with a dated update note.

Writer: BFF's own writer (free, no outside service) writes every article from the data: BFF's projections, the nflverse
schedule, Vegas lines, official injury reports and box scores. No other site's text or pictures are used.

Inputs: index.html (the page's data), live.json (scores, box scores, scoring plays), news.json (headlines), lines.json,
proj_history.json, articles.json.   Output: articles.json.   Testing: BFF_NOW=2026-10-18T12:00:00Z python articles.py
"""
import json, os, re, sys, hashlib, datetime
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/New_York')
except Exception:
    ET = datetime.timezone(datetime.timedelta(hours=-4))
UTC = datetime.timezone.utc
NOW = datetime.datetime.fromisoformat(os.environ['BFF_NOW'].replace('Z', '+00:00')) if os.environ.get('BFF_NOW') else datetime.datetime.now(UTC)
OUT = 'articles.json'; KEEP_DAYS = 21; MAX_BRK_RUN = 3; MAX_BRK_DAY = 12
DOW = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


# ---------------------------------------------------------------- small helpers
def iso(d): return d.astimezone(UTC).isoformat(timespec='seconds')
def pdt(s):
    try:
        d = datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')); return (d if d.tzinfo else d.replace(tzinfo=UTC)).astimezone(UTC)
    except Exception: return None
def load(path, default):
    try: return json.load(open(path))
    except Exception: return default
def page_data():
    """the data embedded in index.html (ff_data.json is not kept in the repository)"""
    if os.path.exists('ff_data.json') and os.environ.get('BFF_USE_FF_DATA'): return json.load(open('ff_data.json'))
    h = open('index.html', encoding='utf-8').read(); i = h.index('const D=') + 8; j = h.index(';\n', i)
    return json.loads(h[i:j].replace('<\\/', '</'))
def f1(x): return f'{x:.1f}'
def fnum(x): return str(int(x)) if float(x) == int(x) else f1(x)
def seed(*a): return int(hashlib.md5('|'.join(map(str, a)).encode()).hexdigest()[:8], 16)
_USED = set()   # the openers already used in the article being written (reset by each writer), so none repeats
def pick(opts, *k):
    i = seed(*k) % len(opts)
    for j in range(len(opts)):   # the seeded choice, or the next one not used yet in this article
        # the wording without names and numbers ("was the story:" for every player), so two players in one article
        # never get the same phrase while another is free
        o = opts[(i + j) % len(opts)]; stem = ' '.join(re.sub(r"[^a-z]", "", x) for x in o.split() if x[:1].islower() and not re.search(r"\d", x))[:28]
        if not stem or len(opts) == 1: return o
        if stem not in _USED: _USED.add(stem); return o
    return opts[i]
def fresh():
    _USED.clear()
def normn(s): return re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', re.sub(r"[.'’`-]", '', str(s or '').lower())).strip()
def last(n): return re.sub(r'\s+(Jr\.?|Sr\.?|II|III|IV|V)$', '', n).split()[-1]
def poss(n): return n + ("'" if n.endswith('s') else "'s")
def plural(n, w, pl=None): return f"{fnum(n)} {w if n == 1 else (pl or w + 's')}"
def andj(L):
    L = [x for x in L if x]
    return '' if not L else L[0] if len(L) == 1 else ', '.join(L[:-1]) + ' and ' + L[-1]
def ordn(n): return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
def numw(n): return WORDS[n] if 0 <= n < len(WORDS) else str(n)
def cap(s): return s[:1].upper() + s[1:]
# ---- the analyst voice: counts as words, numbers with the right article, scoring plays told as sentences
def cnt(n, w, pl=None):
    """'two touchdowns', 'one catch', '12 targets' (whole numbers; words up to ten)"""
    n = int(round(float(n or 0))); return f"{numw(n) if 0 <= n <= 10 else n} {w if n == 1 else (pl or w + 's')}"
def one(n, w, pl=None):
    """'a touchdown', 'an interception', 'two touchdowns'"""
    n = int(round(float(n or 0))); return (('an ' if w[:1] in 'aeiou' else 'a ') + w) if n == 1 else cnt(n, w, pl)
def an_n(x):
    """'an 11.9' / 'a 12.3': the article a number takes when read aloud"""
    k = int(float(x)); d = str(k)
    return 'an' if d.startswith('8') or k in (11, 18) or 11000 <= k < 12000 or 18000 <= k < 19000 else 'a'
QW = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth'}
def qtr(q): q = int(q or 1); return f"the {QW[q]} quarter" if q in QW else 'overtime'
def play_txt(t):
    """a scoring play (box-score style, live_update.py) as a phrase: 'a 43-yard field goal by Cairo Santos', 'Caleb Williams' 24-yard touchdown pass to Luther Burden III'"""
    t = re.sub(r'\s+', ' ', str(t or '')).strip().rstrip('.')
    m = re.match(r"^(.+?) (\d+) Yd Field Goal", t)
    if m: return f"{an_n(m.group(2))} {m.group(2)}-yard field goal by {m.group(1)}"
    m = re.match(r"^(.+?) (\d+) Yd pass from (.+?)(?: \(.*\))?$", t)
    if m: return f"{poss(m.group(3))} {m.group(2)}-yard touchdown pass to {m.group(1)}"
    m = re.match(r"^(.+?) (\d+) Yd Rush(?: \(.*\))?$", t)
    if m: return f"{poss(m.group(1))} {m.group(2)}-yard touchdown run"
    m = re.match(r"^(.+?) (\d+) Yd (Interception|Fumble|Punt|Kickoff|Blocked Punt|Blocked Field Goal|Missed Field Goal) Return(?: \(.*\))?$", t)
    if m: return f"{poss(m.group(1))} {m.group(2)}-yard {m.group(3).lower()} return for a touchdown"
    m = re.match(r"^(.+?) touchdown(?: \(.*\))?$", t)
    if m: return f"a touchdown by {m.group(1)}"
    if t.lower() == 'safety': return 'a safety'
    return t
TEAMS = {'ARI': 'Cardinals', 'ATL': 'Falcons', 'BAL': 'Ravens', 'BUF': 'Bills', 'CAR': 'Panthers', 'CHI': 'Bears', 'CIN': 'Bengals', 'CLE': 'Browns', 'DAL': 'Cowboys', 'DEN': 'Broncos',
         'DET': 'Lions', 'GB': 'Packers', 'HOU': 'Texans', 'IND': 'Colts', 'JAX': 'Jaguars', 'KC': 'Chiefs', 'LA': 'Rams', 'LAC': 'Chargers', 'LV': 'Raiders', 'MIA': 'Dolphins',
         'MIN': 'Vikings', 'NE': 'Patriots', 'NO': 'Saints', 'NYG': 'Giants', 'NYJ': 'Jets', 'PHI': 'Eagles', 'PIT': 'Steelers', 'SEA': 'Seahawks', 'SF': '49ers', 'TB': 'Buccaneers',
         'TEN': 'Titans', 'WAS': 'Commanders'}
def tm_name(t): return TEAMS.get(t, t)
def a_an(w): return ('an ' if str(w)[:1].upper() in 'AEIOU' else 'a ') + str(w)
def the(t): return 'the ' + tm_name(t)
def The(t): return 'The ' + tm_name(t)
def et(d): return d.astimezone(ET)
def at_et(day, h, m=0): return datetime.datetime.combine(day, datetime.time(h, m), ET).astimezone(UTC)


# ---------------------------------------------------------------- the data
D = page_data(); P = D['players']; PI = {p['id']: p for p in P}; SEASON = D['asof']['season']
LIVE = load('live.json', {}); NEWS = load('news.json', {}); LINES = load('lines.json', None) or D.get('lines') or {}
PH = (load('proj_history.json', {}) or {}).get(str(SEASON), {})
OLD = load(OUT, {}); OLD = OLD if isinstance(OLD, dict) else {}
ARTS = {a['id']: a for a in OLD.get('items') or [] if isinstance(a, dict) and a.get('id')}
# November 2026: BFF uses no other site's data, so articles written before then lose the roster percentages they quoted
# (ESPN and Yahoo roster rates via FantasyPros); the rest of each article stays as published
_RP = [(re.compile(r' and is rostered in \d+% of leagues'), ''), (re.compile(r', rostered in \d+% of leagues\)'), ')'),
       (re.compile(r' is rostered in \d+% of leagues; he is'), ' is'), (re.compile(r' is rostered in \d+% of leagues(?=[.;])'), '')]
def _unroster(v):
    if isinstance(v, str):
        for rx, r in _RP: v = rx.sub(r, v)
        return v
    return [_unroster(x) for x in v] if isinstance(v, list) else v
for _a in ARTS.values():
    if (_a.get('wv') or 1) < 8: _a['body'] = _unroster(_a.get('body')); _a['dek'] = _unroster(_a.get('dek'))
if OLD.get('season') not in (None, SEASON): ARTS = {}
SEEN = dict(OLD.get('seen') or {}) if isinstance(OLD.get('seen'), dict) else {}
NAMEIX = {}
for p in P: NAMEIX.setdefault((p['t'], normn(p['n'])), p)
# BFF's rest-of-season rank at each position (rest-of-season points per game, 'rl'): who matters, and who is likely on
# waivers in a 12-team league (outside the top 20 QB, 50 RB, 60 WR, 20 TE: about how many teams roster)
_RR = {}
for _q in ('QB', 'RB', 'WR', 'TE'):
    for _k, _p in enumerate(sorted([p for p in P if p['p'] == _q and (p.get('rl') or 0) > 0], key=lambda p: -(p.get('rl') or 0))): _RR[_p['id']] = _k + 1
_ORR = {p['id']: k + 1 for k, p in enumerate(sorted([p for p in P if (p.get('rl') or 0) > 0], key=lambda p: -(p.get('rl') or 0)))}
ROST = {'QB': 20, 'RB': 50, 'WR': 60, 'TE': 20}
def pos_rank(p): return _RR.get(p['id'])
def ovr_rank(p): return _ORR.get(p['id'], 999)
def likely_free(p): return (pos_rank(p) or 999) > ROST.get(p['p'], 50)


def proj_wk(p, w):
    if p.get('nw') == w: return 0.0 if p.get('inj') in ('Out', 'IR', 'Doubtful') else float(p.get('proj') or 0)
    for r in p.get('ros') or []:
        if r[0] == w: return float(r[2] or 0)
    return 0.0
def proj_then(p, w):
    """what BFF projected for week w: the projection locked at kickoff when saved, else today's"""
    h = (PH.get(str(w)) or {}).get(p['id'])
    if h: return float(h[0])
    v = proj_wk(p, w); return v if v > 0 else None
def ppr(r): return (r.get('py') or 0) * .04 + (r.get('ptd') or 0) * 4 - (r.get('int') or 0) * 2 + (r.get('ry') or 0) * .1 + (r.get('rtd') or 0) * 6 + (r.get('ty') or 0) * .1 + (r.get('rectd') or 0) * 6 + (r.get('rec') or 0) - (r.get('fl') or 0) * 2
def tds(r): return int((r.get('rtd') or 0) + (r.get('rectd') or 0))
def yd(n): return plural(int(n), 'yard')


# ---------------------------------------------------------------- games
def games():
    """every game from the schedule (home team's row), with Vegas numbers and kickoff; final scores, quarters and game ids from live.json override"""
    G = {}
    for t, rows in (D.get('sched') or {}).items():
        for r in rows:
            if len(r) < 6 or not r[2] or not r[5]: continue
            opp_row = next((x for x in D['sched'].get(r[1], []) if x[0] == r[0]), None)
            G[(r[0], t)] = dict(wk=r[0], home=t, away=r[1], kick=pdt(r[5]), sp=r[6] if len(r) > 6 else None, ou=r[7] if len(r) > 7 else None, ih=r[3], ia=opp_row[3] if opp_row else None,
                                hs=r[4], as_=opp_row[4] if opp_row else None, ls=None, gid=None)
    for x in (LIVE.get('games') or []) + (LIVE.get('prev') or []):
        for g in G.values():
            if g['home'] == x.get('home') and g['away'] == x.get('away') and abs((g['kick'] - (pdt(x.get('kick')) or g['kick'])).total_seconds()) < 86400 * 3:
                g.update(state=x.get('state'), gid=str(x.get('id')), ls=x.get('ls'), hs=x.get('hs') if x.get('hs') is not None else g['hs'], as_=x.get('as') if x.get('as') is not None else g['as_'])
    for g in G.values():
        if 'state' not in g or g['state'] is None: g['state'] = 'post' if g['hs'] is not None else 'pre'
    return sorted(G.values(), key=lambda g: g['kick'])
GAMES = games()
def gday(g): return et(g['kick']).date()
def ghour(g): return et(g['kick']).hour
def gtime(g): t = et(g['kick']); return t.strftime('%-I:%M %p ET') if t.minute else t.strftime('%-I %p ET')
def gdaytime(g): return f"{DOW[gday(g).weekday()]} at {gtime(g)}"
def fav_of(g):
    """(favorite, points) from the home spread (negative = home favored)"""
    if g['sp'] is None or g['sp'] == 0: return None, 0
    return (g['home'], -g['sp']) if g['sp'] < 0 else (g['away'], g['sp'])
def win_prob(g, tm):
    if g['sp'] is None: return None
    z = -g['sp'] / 13.45; import math; ph = .5 * (1 + math.erf(z / math.sqrt(2)))
    return ph if tm == g['home'] else 1 - ph
def vegas(g):
    if g['sp'] is None or g['ou'] is None: return ''
    fav, sp = fav_of(g)
    return f"{the(fav)} favored by {fnum(sp)} and a total of {fnum(g['ou'])}" if fav else f"a pick'em with a total of {fnum(g['ou'])}"
def record(tm, through_wk):
    W = L = T = 0
    for x in (D.get('sched') or {}).get(tm, []):
        if x[0] > through_wk or not x[1] or x[4] is None: continue
        o = next((y for y in D['sched'].get(x[1], []) if y[0] == x[0]), None)
        if not o or o[4] is None: continue
        W, L, T = W + (x[4] > o[4]), L + (x[4] < o[4]), T + (x[4] == o[4])
    for g in GAMES:   # live finals not yet in the schedule data
        if g['wk'] <= through_wk and g['state'] == 'post' and tm in (g['home'], g['away']):
            row = next((x for x in D['sched'].get(tm, []) if x[0] == g['wk']), None)
            if row and row[4] is None and g['hs'] is not None and g['as_'] is not None:
                mine, theirs = (g['hs'], g['as_']) if tm == g['home'] else (g['as_'], g['hs'])
                W, L, T = W + (mine > theirs), L + (mine < theirs), T + (mine == theirs)
    return f"{W}-{L}" + (f"-{T}" if T else '')
def last_result(tm, before_wk):
    """(week, opponent, our score, their score) of the team's most recent finished game before week before_wk"""
    for x in sorted((D.get('sched') or {}).get(tm, []), reverse=True):
        if x[0] >= before_wk or not x[1] or x[4] is None: continue
        o = next((y for y in D['sched'].get(x[1], []) if y[0] == x[0]), None)
        if o and o[4] is not None: return x[0], x[1], x[4], o[4]
    return None
def result_words(tm, before_wk):
    r = last_result(tm, before_wk)
    if not r: return ''
    w_, opp, a, b = r
    return (f"beat the {tm_name(opp)} {a}-{b}" if a > b else f"lost to the {tm_name(opp)} {b}-{a}" if a < b else f"tied the {tm_name(opp)} {a}-{b}") + f" in week {w_}"
def hot_hand(teams, before_wk):
    best = None
    for p in P:
        if p['t'] not in teams or p.get('inj') in ('Out', 'Doubtful', 'IR'): continue   # a player ruled out can't come in hot
        L = [x for x in p.get('wk') or [] if x[0] < before_wk]
        if L and L[-1][1] is not None and L[-1][1] >= 20 and (best is None or L[-1][1] > best[1]): best = (p, L[-1][1], L[-1][0])
    return best
def next_game(tm, after_wk):
    return next(((x[0], x[1], x[2]) for x in sorted((D.get('sched') or {}).get(tm, [])) if x[0] > after_wk and x[1]), None)
def team_players(t, w, n=3, pos=None):
    L = [p for p in P if p['t'] == t and (pos is None or p['p'] in pos) and proj_wk(p, w) > 0]
    return sorted(L, key=lambda p: -proj_wk(p, w))[:n]
DVP = D.get('dvp') or {}
def dvp_rank(opp, pos):
    v = (DVP.get(opp) or {}).get(pos)   # [points allowed a game, games, factor, rank (1 = allows the fewest)]
    return v[3] if isinstance(v, list) and len(v) > 3 else None
def vs(mw):
    """'against a soft defense' / ', though he faces a tough one'"""
    return '' if not mw else (f", though he faces {mw}" if 'fewest' in mw else f" against {mw}")
def dot(s): return s if s.endswith('.') else s + '.'
def matchup_words(opp, pos):
    r = dvp_rank(opp, pos)
    if r is None: return ''
    if r >= 26: k = 33 - r; return f"{a_an(tm_name(opp))} defense that has allowed the {'' if k == 1 else ordn(k) + '-'}most fantasy points to {pos}s"
    if r <= 6: return f"{a_an(tm_name(opp))} defense that has allowed the {'' if r == 1 else ordn(r) + '-'}fewest fantasy points to {pos}s"
    return ''
def wk_val(q, w):
    """his week-w projection: today's while his game is ahead, else the one locked at its kickoff (proj_history.json), so a
    Monday or Sunday-night outlook ranks a player against the whole week, not just the few players still to play"""
    v = proj_wk(q, w)
    if v > 0: return v
    h = (PH.get(str(w)) or {}).get(q['id'])
    return float(h[0]) if h else 0.0
def wk_rank(p, w):
    L = sorted([q for q in P if q['p'] == p['p'] and wk_val(q, w) > 0], key=lambda q: -wk_val(q, w))
    return L.index(p) + 1 if p in L else None
def usual_rank(p):
    L = sorted([q for q in P if q['p'] == p['p'] and (q.get('rl') or q.get('fpg'))], key=lambda q: -(q.get('rl') or q.get('fpg') or 0))
    return L.index(p) + 1 if p in L else None
def lines_for(teams, w, k=None):
    """BFF's predicted prop lines for these teams' players this week (all of one market when k is given)"""
    lw = LINES.get('wk')
    return [x for x in (LINES.get('lines') or []) if PI.get(x.get('pid')) and x.get('t') in teams and (x.get('wk') or lw) == w and (k is None or x.get('k') == k)]
SNAME = {'py': 'passing yards', 'ptd': 'passing TDs', 'ry': 'rushing yards', 'ty': 'receiving yards', 'rec': 'receptions', 'td': 'anytime TD',
         'patt': 'pass attempts', 'cmp': 'completions', 'car': 'rush attempts', 'tg': 'targets', 'int': 'interceptions', 'td1': 'first-half TD'}
def low_snap(p, w):
    """his snap share in week w when it was far below his usual (a starter who barely played usually got hurt in the
    game or was eased back in), else None"""
    L = [x for x in (p.get('wk') or []) if x[3] is not None and x[0] <= w]
    if not L or L[-1][0] != w or L[-1][3] >= .4 or len(L) < 2: return None
    before = [x[3] for x in L[:-1]]
    return L[-1][3] if (sum(before) / len(before) >= .6 or max(before) >= .75) else None
def inj_word(p):
    """how to name a player's status in a sentence: an official listing by its name; BFF's own between-reports
    estimate (no injury report for the game yet) as what really happened, so it never reads like an official listing"""
    s = p.get('inj') or ''
    if s == 'IR': return 'injured reserve'
    if p.get('injs') == 'expected':
        m = re.search(r'week (\d+)', p.get('injn') or '')
        return ('expected out' if s == 'Out' else f"missed week {m.group(1)}, status not set yet" if m else 'status not set yet')
    if p.get('injs') == 'news' and s == 'Questionable': return 'questionable (back from the exempt list)' if 'exempt' in (p.get('injn') or '') else 'questionable'
    return s.lower()
def injured(teams, w, statuses=('Out', 'Doubtful', 'Questionable', 'IR')):
    out = [p for p in P if p['t'] in teams and p.get('inj') in statuses and ((p.get('rl') or 0) >= 7 or ovr_rank(p) <= 160 or (p.get('pj0') or 0) >= 6)]
    return sorted(out, key=lambda p: -((p.get('rl') or 0) + (p.get('pj0') or 0)))
def qb_of(tm): return next((q for q in P if q['t'] == tm and q['p'] == 'QB' and q.get('qbs')), None) or next((q for q in P if q['t'] == tm and q['p'] == 'QB' and q.get('role') == 'QB1'), None)
def pace(tm):
    q = next((p for p in P if p['t'] == tm and p.get('tpl')), None)
    return (q.get('tpl'), q.get('tpr')) if q else (None, None)
def season_games(p, before_wk): return [x for x in (p.get('wk') or []) if x[0] < before_wk]


# ---------------------------------------------------------------- article pieces
def P_(text): return ['p', text]
def H_(text): return ['h', text]
def UL(items): return ['ul', [x for x in items if x]]
def PL(p, note): return ['pl', p['id'], note]
def gref(g): return g.get('gid') or f"w{g['wk']}{g['home']}"   # the nflverse game id, else the schedule id the page also understands
def GH(g): return ['game', g['away'], g['home'], gref(g)]
def SCORE(g): return ['score', g['away'], g['home'], g['as_'], g['hs'], (g.get('ls') or [None, None])[0], (g.get('ls') or [None, None])[1], gref(g)]
def SCORES(gs): return ['scores', [[g['away'], g['home'], g['as_'], g['hs'], gref(g)] for g in gs]]
def PULL(text): return ['pull', text]
def facts_digest(players, gs):
    return {'p': {p['id']: [p.get('inj'), round(proj_wk(p, p.get('nw') or 0), 1)] for p in players}, 'g': {f"{g['away']}@{g['home']}": [g['sp'], g['ou']] for g in gs}}
def change_notes(old, new):
    """what changed since the last version (injury statuses, projections, lines)"""
    notes = []
    for pid, (st, pj) in new.get('p', {}).items():
        o = (old or {}).get('p', {}).get(pid)
        if not o or pid not in PI: continue
        n = PI[pid]['n']
        if o[0] != st: notes.append(f"{n} is now {st.lower() if st else 'off the injury report'}" if st not in ('Out', 'IR') else f"{n} has been ruled out")
        elif abs((o[1] or 0) - (pj or 0)) >= 1.5: notes.append(f"{poss(n)} projection moved from {f1(o[1])} to {f1(pj)}")
    for k, (sp, ou) in new.get('g', {}).items():
        o = (old or {}).get('g', {}).get(k)
        if o and o[1] is not None and ou is not None and abs(o[1] - ou) >= 1.5: notes.append(f"the {k.replace('@', ' at ')} total moved from {fnum(o[1])} to {fnum(ou)}")
    return notes[:4]
def uniq(L):
    seen = []; [seen.append(p['id'] if isinstance(p, dict) else p) for p in L if (p['id'] if isinstance(p, dict) else p) not in seen]; return seen
SRC_PRE = [{'s': 'BFF projections', 'u': ''}, {'s': 'Vegas lines and schedule (nflverse)', 'u': 'https://github.com/nflverse/nflverse-data/releases/tag/schedules'}, {'s': 'Official injury reports (nflverse)', 'u': 'https://github.com/nflverse/nflverse-data'}]
SRC_POST = [{'s': 'Official stats, box scores and play-by-play (nflverse)', 'u': 'https://github.com/nflverse/nflverse-data'}, {'s': 'BFF projections', 'u': ''}]


# ---------------------------------------------------------------- what happened in a game
def box_rows(g):
    """[(player, stat row, team)] for a game: the live box score, else the official weekly stats in the page data"""
    B = (LIVE.get('box') or {}).get(str(g.get('gid'))) if g.get('gid') else None
    rows = []
    BL = B.get('players') if isinstance(B, dict) else B if isinstance(B, list) else None
    if BL:
        for r in BL:
            p = NAMEIX.get((r.get('t'), normn(r.get('n'))))
            if p: rows.append((p, r, r.get('t')))
    if not rows:
        for p in P:
            wkr = next((x for x in p.get('wk') or [] if x[0] == g['wk']), None)
            gl = next((x for x in p.get('gl') or [] if x[0] == g['wk']), None)
            if not gl or not wkr: continue
            opp = wkr[6]
            if opp not in (g['home'], g['away']): continue
            tm = g['away'] if opp == g['home'] else g['home']
            rows.append((p, dict(pc=gl[1], pa=gl[2], py=gl[3], ptd=gl[4], int=gl[5], ra=gl[6], ry=gl[7], rtd=gl[8], rec=gl[9], tg=gl[10], ty=gl[11], rectd=gl[12], fl=gl[13], snap=wkr[3]), tm))
    return rows
def scoring_plays(g):
    """[quarter, clock, team, type, text, away score, home score] for each score: live.json's play-by-play (pbp), else an
    older box score's copy"""
    gid = str(g.get('gid') or '')
    if not gid: return []
    sp = (((LIVE.get('pbp') or {}).get(gid) or {}).get('sp')) or []
    sp = [[x.get('q'), x.get('c'), x.get('tm'), x.get('ty'), x.get('t'), x.get('as'), x.get('hs')] if isinstance(x, dict) else x for x in sp]
    if not sp:
        B = (LIVE.get('box') or {}).get(gid); sp = (B.get('sp') if isinstance(B, dict) else None) or []
    return [x for x in sp if isinstance(x, list) and len(x) >= 7]
class Game:
    """a finished game, read for the story"""
    def __init__(s, g):
        s.g = g; s.w = g['wk']; s.rows = box_rows(g); hs, as_ = g['hs'] or 0, g['as_'] or 0
        s.win, s.lose = (g['home'], g['away']) if hs > as_ else (g['away'], g['home']); s.tie = hs == as_
        s.ws, s.ls = max(hs, as_), min(hs, as_); s.margin = s.ws - s.ls; s.total = hs + as_
        fav, sp = fav_of(g); s.fav, s.sp = fav, sp
        s.upset = bool(fav and fav == s.lose and sp >= 3); s.covered = bool(fav and fav == s.win and s.margin > sp)
        s.ot = bool(g.get('ls') and max(len(g['ls'][0] or []), len(g['ls'][1] or [])) > 4)
        s.half = None
        if g.get('ls') and len(g['ls'][0] or []) >= 2 and len(g['ls'][1] or []) >= 2:
            a2, h2 = sum(g['ls'][0][:2]), sum(g['ls'][1][:2]); s.half = (a2, h2)
        s.comeback = None; s.lead_h = None   # the winner's lead at halftime (negative: he trailed)
        if s.half:
            lead_h = s.half[1] - s.half[0] if s.win == g['home'] else s.half[0] - s.half[1]; s.lead_h = lead_h
            if lead_h <= -7: s.comeback = -lead_h
        s.plays = scoring_plays(g)
        s.pts = sorted([(p, r, t, ppr(r)) for p, r, t in s.rows], key=lambda x: -x[3])
    def team_rows(s, tm): return [x for x in s.pts if x[2] == tm]
    def top(s): return s.pts[0] if s.pts else None


def halfscore(G):
    """the halftime score, leader first ('13-10'), or 'tied 7-7'"""
    a, h = G.half
    return f"tied {a}-{h}" if a == h else f"{max(a, h)}-{min(a, h)}"


def lede_recap(G, key):
    g = G.g; W, L = tm_name(G.win), tm_name(G.lose); sc = f"{G.ws}-{G.ls}"; rw, rl = record(G.win, g['wk']), record(G.lose, g['wk'])
    if G.tie: return f"{tm_name(g['away'])} and {tm_name(g['home'])} played to {an_n(G.ws)} {sc} tie" + (" in overtime" if G.ot else '') + '.'
    ot = ' in overtime' if G.ot else ''
    if G.comeback: s = pick([f"The {W} erased {an_n(G.comeback)} {G.comeback}-point halftime deficit and beat the {L} {sc}{ot}.", f"Down {G.comeback} at the half, the {W} came all the way back to beat the {L} {sc}{ot}."], key, 'cb')
    elif G.upset: s = pick([f"The {W} won outright as {fnum(G.sp)}-point underdogs, beating the {L} {sc}{ot}.", f"Underdogs by {fnum(G.sp)}, the {W} took down the {L} {sc}{ot}."], key, 'up')
    elif G.margin >= 14 and G.half and G.lead_h is not None and G.lead_h <= 7: s = pick([f"The {W} pulled away in the second half to beat the {L} {sc}.", f"It was a game at halftime ({halfscore(G)}), and then it wasn't: the {W} beat the {L} {sc}.", f"The {W} took over after halftime and beat the {L} {sc}."], key, 'pa')
    elif G.margin >= 17: s = pick([f"The {W} rolled past the {L}, {sc}.", f"It was never close: the {W} beat the {L} {sc}.", f"The {W} handled the {L} {sc}."], key, 'bl')
    elif G.margin <= 3: s = pick([f"The {W} survived the {L}, {sc}{ot}.", f"The {W} edged the {L} {sc}{ot}.", f"The {W} held on to beat the {L} {sc}{ot}."], key, 'cl')
    # (no "pulled away" here: the scoring plays, not the final margin, say whether a team pulled away)
    elif G.margin >= 8: s = pick([f"The {W} beat the {L} {sc}{ot}.", f"The {W} took care of the {L}, {sc}{ot}.", f"The {W} got the better of the {L}, {sc}{ot}."], key, 'md')
    else: s = pick([f"The {W} beat the {L} {sc}{ot}.", f"The {W} got past the {L}, {sc}{ot}.", f"The {W} came out on top against the {L}, {sc}{ot}."], key, 'md')
    s += ' ' + pick([f"The {W} move to {rw}, while the {L} fall to {rl}.", f"That puts the {W} at {rw}; the {L} drop to {rl}.", f"The {W} are now {rw}, and the {L} slip to {rl}."], key, 'rec')
    if g['ou']:
        diff = G.total - g['ou']
        if diff >= 10: s += f" The {G.total} combined points blew past the {fnum(g['ou'])}-point total, the kind of game fantasy managers dream about."
        elif diff <= -10: s += f" The {G.total} combined points came in well under the {fnum(g['ou'])}-point total, and fantasy scoring suffered for it."
    return s
def flow_paragraph(G, key):
    """how it unfolded, from the scoring plays (touchdowns, and the score that decided it)"""
    g = G.g; pl = G.plays
    if not pl:
        if G.half: return f"{The(g['away'])} led {G.half[0]}-{G.half[1]} at halftime." if G.half[0] > G.half[1] else (f"{The(g['home'])} led {G.half[1]}-{G.half[0]} at halftime." if G.half[1] > G.half[0] else f"It was tied {G.half[0]}-{G.half[1]} at halftime.")
        return ''
    out = []; first = pl[0]
    out.append(pick([f"{The(first[2])} struck first in {qtr(first[0])} on {play_txt(first[4])}.", f"{The(first[2])} got on the board first, in {qtr(first[0])}, on {play_txt(first[4])}."], key, 'f1'))
    lead = None; changes = 0; decisive = None
    for x in pl:
        a, h = x[5] or 0, x[6] or 0; now = g['home'] if h > a else g['away'] if a > h else None
        if now and now != lead:
            if lead is not None: changes += 1
            lead = now; decisive = x
    tdl = [x for x in pl if (x[3] or '').upper() == 'TD' or 'touchdown' in (x[4] or '').lower()]
    if changes >= 2: out.append(pick([f"From there it was a back-and-forth affair: the lead changed hands {numw(changes) if changes <= 10 else changes} times.", f"Neither side could pull away; the lead changed hands {numw(changes) if changes <= 10 else changes} times."], key, 'lc'))
    if decisive and decisive is not first and not G.tie:
        q = int(decisive[0] or 4); clk = re.sub(r'^0(\d:)', r'\1', str(decisive[1] or '').strip())
        when = f"with {clk} left in {qtr(q)}" if clk and q <= 4 else ('in overtime' if q > 4 else f"in {qtr(q)}")
        out.append(pick([f"{The(G.win)} went ahead for good {when} on {play_txt(decisive[4])}.", f"The go-ahead score that held up came {when}: {play_txt(decisive[4])}."], key, 'dec'))
    if G.half and not G.tie:   # a second half that decided a lopsided game
        wh, lh = (G.half[1], G.half[0]) if G.win == g['home'] else (G.half[0], G.half[1])
        w2, l2 = G.ws - wh, G.ls - lh
        if w2 - l2 >= 10:
            td2 = [play_txt(x[4]) for x in pl if x[2] == G.win and int(x[0] or 0) >= 3 and ((x[3] or '').upper() == 'TD')][:2]
            out.append(f"After halftime the {tm_name(G.win)} outscored the {tm_name(G.lose)} {w2}-{l2}" + (f", with {andj(td2)}" if td2 else '') + '.')
    margin = abs((g.get('as_') or 0) - (g.get('hs') or 0)); wtd = sum(1 for x in tdl if x[2] == G.win); ltd = len(tdl) - wtd
    ntd = numw(len(tdl)) if len(tdl) <= 10 else str(len(tdl))
    if not G.tie and margin >= 17:   # a rout reads like one
        out.append(pick([f"It was never really close: the {tm_name(G.lose)} managed {cnt(ltd, 'touchdown')} all game." if ltd <= 1 else f"The {tm_name(G.lose)} kept scoring, but never kept pace.",
                         f"The {tm_name(G.win)} controlled this one, and the {tm_name(G.lose)} found the end zone {('only once' if ltd == 1 else 'just ' + cnt(ltd, 'time')) if ltd else 'not at all'}."], key, 'rout'))
    elif len(tdl) >= 4 and changes < 2 and wtd >= 2 and ltd >= 2 and margin <= 10:
        out.append(pick([f"The offenses traded blows: {ntd} touchdowns in all, a good day for anyone with a piece of this game.", f"Both offenses moved the ball, with {ntd} touchdowns between them."], key, 'td'))
    elif len(tdl) >= 5:
        out.append(f"In all there were {ntd} touchdowns, {wtd} of them by the {tm_name(G.win)}." if not G.tie else f"In all there were {ntd} touchdowns.")
    elif len(tdl) <= 2 and (g.get('as_') or 0) + (g.get('hs') or 0) <= 30:
        out.append(pick([f"Points were hard to come by: {cnt(len(tdl), 'touchdown')} in the whole game.", f"It was a grind, with only {cnt(len(tdl), 'touchdown')} all day."], key, 'low'))
    return ' '.join(out)


def player_note(p, r, pts, w, key):
    """one player's game in an analyst's words: the verdict first, then the line, then what it means (the same facts as
    the box score and BFF's projection)"""
    n = p['n']; pj = proj_then(p, w); prev = [x[1] for x in season_games(p, w)]; d = (pts - pj) if pj else 0
    i = lambda v: int(round(float(v or 0)))
    if p['p'] == 'QB' and r.get('pa'):
        line = f"{i(r.get('pc'))} of {i(r['pa'])} for {yd(i(r.get('py')))}"
        tds_, ints_ = i(r.get('ptd')), i(r.get('int'))
        line += (f" and {one(tds_, 'touchdown')}" if tds_ else '') + (f", with {one(ints_, 'interception')}" if ints_ else '')
        run_ = ([f"{yd(i(r['ry']))} on the ground"] if (r.get('ry') or 0) >= 20 else []) + ([one(i(r['rtd']), 'rushing score')] if r.get('rtd') else [])
        if run_: line += ', plus ' + andj(run_)
        verb = pick(['went', 'finished', 'was'], key, n, 'qbv')
        core = f"{verb} {line}"
        # a quarterback filling in (2 or fewer earlier games this season while his team's usual starter sits) is said to be
        usual = max([q for q in P if q['t'] == p['t'] and q['p'] == 'QB' and q['id'] != p['id']], key=lambda q: q.get('g') or 0, default=None)
        if len(prev) <= 2 and usual and (usual.get('g') or 0) >= 3 and (usual.get('g') or 0) > len(prev) + 1:
            core += f", {'in his first start of the season' if not prev else 'in a rare start'} in place of {usual['n']}"
    elif p['p'] == 'RB' or (r.get('ra') or 0) >= 6:
        core = f"carried {cnt(i(r.get('ra')), 'time')} for {yd(i(r.get('ry')))}" + (f" and {one(i(r['rtd']), 'touchdown')}" if r.get('rtd') else '')
        if r.get('rec'): core += f", adding {cnt(i(r['rec']), 'catch', 'catches')} for {yd(i(r.get('ty')))}" + (" and a receiving score" if r.get('rectd') else '')
    else:
        rc, tg = i(r.get('rec')), i(r.get('tg'))
        core = (f"caught all {numw(rc) if rc <= 10 else rc} of his targets" if rc == tg and rc >= 2 else f"caught {numw(rc) if rc <= 10 else rc} of {cnt(tg, 'target')}") + f" for {yd(i(r.get('ty')))}" + (f" and {one(i(r['rectd']), 'touchdown')}" if r.get('rectd') else '')
    ratio = pts / pj if pj else 1
    if pj and d >= 8: lead = pick([f"{n} stole the show:", f"{n} was the story:", f"{n} broke out:", f"Nobody did more damage than {n}, who", f"{n} went off:",
                                   f"It was a huge day for {n}, who", f"{n} had a monster game:", f"{n} carried his managers:"], key, n, 'big')
    elif pj and d >= 2.5 and pts >= 12: lead = pick([f"{n} delivered:", f"{n} came through:", f"{n} paid off for his managers:"], key, n, 'good')
    elif pj and d >= 2.5 and ratio >= 1.8: lead = pick([f"{n} doubled a modest projection:", f"{n} made the most of a small role:", f"{n} outplayed his projection by a mile:"], key, n, 'goodx')
    elif pj and d >= 2.5: lead = pick([f"{n} beat a modest projection:", f"{n} did a little more than expected:", f"{n} cleared a low bar:"], key, n, 'goodlo')
    elif pj and d <= -2.5 and pj >= 8 and ratio < .45: lead = pick([f"{n} never got going:", f"{n} was a nonfactor:", f"{n} all but disappeared:"], key, n, 'awful')
    elif pj and d <= -2.5 and pj >= 8: lead = pick([f"{n} was a letdown:", f"It was a quiet day for {n}, who", f"{n} came in under expectations:"], key, n, 'bad')
    elif pj and d <= -2.5: lead = pick([f"{n} came up short:", f"{n} gave his managers little:", f"It was a quiet one for {n}, who"], key, n, 'badlo')
    elif pts >= 10: lead = pick([f"{n} did his job:", f"{n} was steady:", f"{n} gave you what you expected:"], key, n, 'flat')
    else: lead = pick([f"{n} had a modest day:", f"{n}"] + ([] if p['p'] == 'QB' else [f"{n} chipped in:"]), key, n, 'flatlo')
    lead = lead if lead.endswith((':', 'who')) else lead
    s = f"{lead} {'he ' if lead.endswith(':') else ''}{core}."
    if pj:
        if d >= 8: tail = pick([f"That's {f1(pts)} PPR points, {'more than double' if pts >= 2 * pj else 'well above'} the {f1(pj)} we projected.", f"Good for {f1(pts)} PPR points against {an_n(pj)} {f1(pj)} projection."], key, n, 't1')
        elif d >= 2.5: tail = pick([f"That's {f1(pts)} PPR points, {f1(d)} better than our {f1(pj)} projection.", f"He finished with {f1(pts)} PPR points; we had him at {f1(pj)}."], key, n, 't2')
        elif d <= -2.5: tail = pick([f"Just {f1(pts)} PPR points, {f1(-d)} short of our {f1(pj)} projection.", f"That added up to {f1(pts)} PPR points against {an_n(pj)} {f1(pj)} projection."], key, n, 't3')
        else: tail = pick([f"That's {f1(pts)} PPR points, right around the {f1(pj)} we expected.", f"He finished with {f1(pts)} PPR points, close to our {f1(pj)} projection.", f"He scored {f1(pts)} PPR points, about what we projected ({f1(pj)})."], key, n, 't4')
    else: tail = f"That's {f1(pts)} PPR points."
    s += ' ' + tail
    if len(prev) >= 2 and pts > max(prev) + .5 and pts >= 12: s = s.rstrip('.') + pick(['; a new season high.', ', his best game of the season.', ', easily his top game of the year.'], key, n, 'hi')
    return s


def brief(p, r, pts, key):
    """one short sentence for a game capsule: what he did (the box score), then his PPR points"""
    i = lambda v: int(round(float(v or 0))); n = p['n']; td = tds(r)
    if p['p'] == 'QB' and (r.get('pa') or 0) >= 10:
        did = f"threw for {yd(i(r.get('py')))}" + (f" and {one(i(r['ptd']), 'touchdown')}" if r.get('ptd') else '')
        if (r.get('ry') or 0) >= 25: did += f", and ran for {yd(i(r.get('ry')))}" + (f" and {one(i(r['rtd']), 'score')}" if r.get('rtd') else '')
        elif r.get('rtd'): did += f", plus {one(i(r['rtd']), 'rushing score')}"
    elif (r.get('ra') or 0) >= 6 and (r.get('ra') or 0) >= (r.get('tg') or 0):
        did = f"ran for {yd(i(r.get('ry')))} on {cnt(i(r['ra']), 'carry', 'carries')}"
        if (r.get('rec') or 0) >= 2: did += f" and caught {numw(i(r['rec']))} passes for {yd(i(r.get('ty')))}"
        if td: did += f", with {one(td, 'touchdown')}"
    elif r.get('tg'):
        rc, tg = i(r.get('rec')), i(r.get('tg'))
        did = (f"caught all {numw(rc) if rc <= 10 else rc} of his targets" if rc == tg and rc >= 2 else f"caught {numw(rc) if rc <= 10 else rc} of {cnt(tg, 'target')}") + f" for {yd(i(r.get('ty')))}" + (f" and {one(td, 'touchdown')}" if td else '')
    else:
        return f"{n} added {f1(pts)} points."
    return pick([f"{n} {did} ({f1(pts)} points).", f"{n} {did}, good for {f1(pts)} points.", f"{n} {did}: {f1(pts)} PPR points."], key, n, 'br')


def team_breakdown(G, tm, key):
    """the fantasy story of one team in a game: quarterback, backfield, pass catchers"""
    R = G.team_rows(tm)
    if not R: return []
    out = []; w = G.w
    tg_tot = sum((r.get('tg') or 0) for _, r, _, _ in R) or 0; rb_car = sum((r.get('ra') or 0) for p, r, _, _ in R if p['p'] == 'RB') or 0
    qb = next((x for x in R if x[0]['p'] == 'QB' and (x[1].get('pa') or 0) >= 10), None)
    if qb: out.append(player_note(qb[0], qb[1], qb[3], w, key))
    rbs = sorted([x for x in R if x[0]['p'] == 'RB' and (x[1].get('ra') or 0) + (x[1].get('tg') or 0) >= 4], key=lambda x: -((x[1].get('ra') or 0) + (x[1].get('tg') or 0)))
    if rbs:
        p, r, _, pts = rbs[0]; s = player_note(p, r, pts, w, key)
        if rb_car >= 8 and r.get('ra'):
            sh = r['ra'] / rb_car
            s += ' ' + (pick([f"The bigger story is the workload: {round(sh * 100)}% of the backfield carries, a true bell-cow share.", f"He handled {round(sh * 100)}% of the running back carries, and that kind of volume travels week to week."], key, 'wh') if sh >= .7
                        else pick([f"It's still a committee, though: he took {round(sh * 100)}% of the running back carries.", f"Don't read too much into it yet; he split the work, taking {round(sh * 100)}% of the running back carries."], key, 'sp') if sh <= .55 else f"He took {round(sh * 100)}% of the running back carries, the lead role but not all of it.")
        out.append(s)
        if len(rbs) > 1 and (rbs[1][1].get('ra') or 0) + (rbs[1][1].get('tg') or 0) >= 7: out.append(player_note(rbs[1][0], rbs[1][1], rbs[1][3], w, key))
    rec = sorted([x for x in R if x[0]['p'] in ('WR', 'TE', 'RB') and (x[1].get('tg') or 0) >= 4 and x not in rbs[:2]], key=lambda x: -((x[1].get('tg') or 0) * 2 + x[3]))
    for i, (p, r, _, pts) in enumerate(rec[:3]):
        s = player_note(p, r, pts, w, key)
        if i == 0 and tg_tot >= 15 and r.get('tg'):
            sh = r['tg'] / tg_tot
            if sh >= .28: s += ' ' + pick([f"He commanded {round(sh * 100)}% of the targets, the kind of volume a true number one gets.", f"With {round(sh * 100)}% of the team's targets, he is clearly the first read."], key, 'ts')
        out.append(s)
    return out


def stock_lists(G_list, key):
    """stock up / down / waiver, from what happened and how it happened (volume says more than a touchdown)"""
    up, down, wav = [], [], []
    for G in G_list:
        for p, r, t, pts in G.pts:
            pj = proj_then(p, G.w) or 0; vol = (r.get('tg') or 0) + (r.get('ra') or 0); td = tds(r)
            td_heavy = td >= 1 and (pts - 6 * td) < pts * .5
            if pts - pj >= 7 and pts >= 14 and NOW > G.g['kick']:
                why = (f"{plural(r.get('tg', 0), 'target')} is real volume" if (r.get('tg') or 0) >= 8 else f"{r.get('ra', 0)} carries is a featured role" if (r.get('ra') or 0) >= 16
                       else 'a big arm day' if p['p'] == 'QB' and (r.get('py') or 0) >= 300 else 'the touchdowns did the heavy lifting, so temper expectations' if td_heavy
                       else f"but only {plural(vol, 'carry and target', 'carries and targets')}, so big plays did the work" if p['p'] != 'QB' and vol < 8
                       else f"{plural(vol, 'carry and target', 'carries and targets')} is a solid workload" if p['p'] != 'QB' and vol >= 12
                       else 'efficient work on modest volume' if p['p'] != 'QB' else 'a strong all-around game')
                up.append((pts - pj, p, f"{p['n']} ({p['p']}, {t}): {f1(pts)} points" + (f" against {an_n(pj)} {f1(pj)} projection" if pj >= 1 else " out of nowhere") + f"; {why}."))
            elif pj >= 9 and pj - pts >= 6:
                why = ((f"{plural(r.get('tg', 0), 'target')} but only {r.get('rec', 0)} for {yd(r.get('ty', 0))}" if (r.get('tg') or 0) >= 7 else f"only {plural(r.get('tg', 0), 'target')}") if p['p'] in ('WR', 'TE')
                       else (f"{r.get('ra', 0)} carries went for just {yd(r.get('ry', 0))}" if (r.get('ra') or 0) >= 14 else f"only {plural(r.get('ra', 0), 'carry', 'carries')}") if p['p'] == 'RB'
                       else (f"just {plural(r.get('pa', 0), 'pass', 'passes')}" if (r.get('pa') or 0) < 15 else f"{r.get('pc', 0)} of {r.get('pa', 0)} for {yd(r.get('py', 0))}" + (f" with {one(int(r['int']), 'interception')}" if r.get('int') else '')))
                sn = low_snap(p, G.w)
                if p.get('inj') == 'IR' or 'for the season' in (p.get('injn') or ''): why += f"; he has since been {'placed on injured reserve' if p.get('inj') == 'IR' else 'ruled out for the season'}"
                elif sn is not None: why += f"; he played just {round(sn * 100)}% of the snaps, which often points to an injury, so watch this week's injury report"
                down.append((pj - pts, p, f"{p['n']} ({p['p']}, {t}): {f1(pts)} points on {an_n(pj)} {f1(pj)} projection, {why}."))
            if likely_free(p) and (pts >= 12 or (r.get('tg') or 0) >= 7 or (r.get('ra') or 0) >= 13) and p['p'] != 'QB':
                wav.append((pts + vol, p, f"{p['n']} ({p['p']}, {t}, outside BFF's top {ROST[p['p']]} at {p['p']}, so likely on waivers): {f1(pts)} points on {andj([plural(r['tg'], 'target') if r.get('tg') else '', plural(r['ra'], 'carry', 'carries') if r.get('ra') else ''])}." + (" The volume is worth chasing." if vol >= 10 else " One week is not a role, so check his snaps first.")))
    srt = lambda L: [x[2] for x in sorted(L, key=lambda x: -x[0])[:4]]
    return srt(up), srt(down), srt(wav), [x[1] for x in up + down + wav]


def looking_ahead(G_list, key):
    out = []
    for G in G_list:
        for tm in (G.win, G.lose):
            nx = next_game(tm, G.w)
            if not nx: continue
            w2, opp, home = nx; top = team_players(tm, w2, 1)
            if top:
                p = top[0]; mw = matchup_words(opp, p['p'])
                out.append(f"{The(tm)} {'host' if home else 'visit'} the {tm_name(opp)} in week {w2}; {p['n']} projects for {f1(proj_wk(p, w2))} points" + vs(mw) + '.')
    return out[:4]


def recap_title(G_list, label, key):
    if len(G_list) == 1:
        G = G_list[0]; W, L = tm_name(G.win), tm_name(G.lose); top = G.top(); sc = f"{G.ws}-{G.ls}"
        verb = 'rally past' if G.comeback else 'stun' if G.upset else 'roll past' if G.margin >= 17 else 'hold off' if G.margin <= 3 else 'beat'
        hook = f"{top[0]['n']} leads the fantasy winners" if top else 'the fantasy fallout'
        return pick([f"{W} {verb} {L} {sc}: {hook}", f"{label} recap: {W} {verb} {L}, and what it means for fantasy", f"{W} {G.ws}, {L} {G.ls}: winners, losers and waiver adds"], key, 't')
    tops = sorted([G.top() for G in G_list if G.top()], key=lambda x: -x[3])
    return pick([f"{label} recap: {tops[0][0]['n']} leads the way" if tops else f"{label} recap", f"{label} recap: winners, surprises and waiver adds", f"Everything that mattered from {label.lower() if not label.startswith('Week') else label}"], key, 't')


def write_recap(gs, key, label):
    """an in-depth recap of one game, or a few (Thursday, Sunday night, Monday, other days)"""
    fresh()
    G_list = [Game(g) for g in gs]; G_list = [G for G in G_list if G.rows]
    if not G_list: return None, None
    body = []; ment = []
    multi = len(G_list) > 1
    if multi: body.append(SCORES([G.g for G in G_list]))
    for G in G_list:
        if multi: body.append(H_(f"{tm_name(G.win)} {G.ws}, {tm_name(G.lose)} {G.ls}" if not G.tie else f"{tm_name(G.g['away'])} {G.g['as_']}, {tm_name(G.g['home'])} {G.g['hs']}"))
        else: body.append(SCORE(G.g))
        body.append(P_(lede_recap(G, key)))
        fl = flow_paragraph(G, key)
        if fl and not multi: body.append(H_('How it happened'))
        if fl: body.append(P_(fl))
        top = G.top()
        if top and not multi: body.append(PULL(f"{top[0]['n']}: {f1(top[3])} PPR points"))
        for tm in (G.win, G.lose):
            notes = team_breakdown(G, tm, key)
            if notes: body.append(H_(f"Fantasy breakdown: {tm_name(tm)}")); body.append(P_(' '.join(notes)))
            ment += [x[0] for x in G.team_rows(tm)[:5]]
    up, down, wav, sm = stock_lists(G_list, key)
    if up: body.append(H_('Stock up')); body.append(UL(up))
    if down: body.append(H_('Stock down')); body.append(UL(down))
    if wav: body.append(H_('Waiver wire')); body.append(UL(wav))
    la = looking_ahead(G_list, key)
    if la: body.append(H_('Looking ahead')); body.append(P_(' '.join(la)))
    ment += sm
    tops = sorted([G.top() for G in G_list if G.top()], key=lambda x: -x[3])
    if tops:
        tn, tp = tops[0][0]['n'], tops[0][3]
        lead_ = (f"{tn} went off for {f1(tp)} PPR points. " if tp >= 25 else f"{tn} led the way with {f1(tp)} PPR points. " if tp >= 18
                 else f"A quiet fantasy {'night' if label and 'night' in label.lower() else 'game' if not multi else 'slate'}: {poss(tn)} {f1(tp)} PPR points led everyone. ")
    else: lead_ = ''
    dek = lead_ + "How it happened, what it means for every fantasy-relevant player, and who to grab off waivers."
    one = G_list[0]
    img = {'k': 'game', 'away': one.g['away'], 'home': one.g['home'], 'gid': one.g.get('gid')} if not multi else ({'k': 'player', 'pid': tops[0][0]['id']} if tops else None)
    return dict(kind='recap', src=SRC_POST, title=recap_title(G_list, label, key), dek=dek, body=body, players=uniq(ment), teams=sorted({t for G in G_list for t in (G.g['home'], G.g['away'])}), wk=one.w, img=img), None


def write_window_recap(gs, key, label, still):
    """a slate of games (Sunday afternoon): scores, top performances, game by game, stock, injuries, waivers, what is left"""
    fresh()
    G_list = [Game(g) for g in gs]; G_list = [G for G in G_list if G.rows]
    if not G_list: return None, None
    w = G_list[0].w; body = [SCORES([G.g for G in G_list])]; ment = []
    allp = sorted([x + (G,) for G in G_list for x in G.pts], key=lambda x: -x[3])
    ups = [G for G in G_list if G.upset]; hi = max(G_list, key=lambda G: G.total); cb = [G for G in G_list if G.comeback]
    intro = f"{cap(numw(len(G_list)) if len(G_list) <= 10 else str(len(G_list)))} games are in the books."
    if ups: intro += f" The biggest surprise: the {tm_name(ups[0].win)} beat the {tm_name(ups[0].lose)} as {fnum(ups[0].sp)}-point underdogs."
    if cb: intro += f" The {tm_name(cb[0].win)} came back from {cb[0].comeback} down at the half."
    intro += f" The {tm_name(hi.g['away'])}-{tm_name(hi.g['home'])} game was the highest-scoring at {hi.total} points."
    if allp: intro += f" {allp[0][0]['n']} led every fantasy scorer with {f1(allp[0][3])} PPR points."
    body.append(P_(intro))
    body.append(H_('The top performances'))
    body.append(UL([player_note(p, r, pts, w, key) for p, r, t, pts, G in allp[:6]]))
    ment += [x[0] for x in allp[:6]]
    body.append(H_('Game by game'))
    for G in sorted(G_list, key=lambda G: G.g['kick']):
        tps = G.pts[:2]
        cap_ = lede_recap(G, key) + ' ' + ' '.join(brief(p, r, pts, key) for p, r, t, pts in tps)
        body.append(GH(G.g)); body.append(P_(cap_)); ment += [x[0] for x in tps]
    up, down, wav, sm = stock_lists(G_list, key); ment += sm
    if up: body.append(H_('Stock up')); body.append(UL(up))
    if down: body.append(H_('Stock down')); body.append(UL(down))
    teams = {t for G in G_list for t in (G.g['home'], G.g['away'])}; start = min(G.g['kick'] for G in G_list)
    inj = []; isrc = []; seen = set()   # in BFF's words; the outlet's report is linked in the sources (no outside text in the article)
    for h in NEWS.get('items') or []:
        d = pdt(h.get('d'))
        if not d or d < start or h.get('c') != 'inj': continue
        ps = [PI[i] for i in h.get('p') or [] if i in PI and PI[i]['t'] in teams and i not in seen]
        if not ps or len(inj) >= 5: continue
        p_ = ps[0]; seen.add(p_['id']); ment.append(p_)
        inj.append(f"{p_['n']} ({p_['p']}, {tm_name(p_['t'])}): in the injury news since kickoff; {h.get('s') or 'the outlet'}'s report is linked in the sources below.")
        if h.get('u'): isrc.append({'s': f"{h.get('s') or 'News'}: injury report on {p_['n']}", 'u': h['u']})
    if inj: body.append(H_('Injuries to watch')); body.append(UL(inj))
    if wav: body.append(H_('Early waiver look')); body.append(UL(wav))
    if still: body.append(H_('Still to come')); body.append(P_(' '.join(f"{tm_name(g['away'])} at {tm_name(g['home'])}, {gdaytime(g)}" + (f" ({vegas(g)})" if vegas(g) else '') + '.' for g in still)))
    title = pick([f"{label} recap: {allp[0][0]['n']} leads {an_n(len(G_list))} {len(G_list)}-game afternoon" if allp else f"{label} recap",
                  f"{label} recap: the performances, surprises and waiver adds that matter", f"{label}: what we learned from {numw(len(G_list)) if len(G_list) <= 10 else len(G_list)} games"], key, 't')
    dek = "Every score, the best fantasy days, who's rising and falling, injuries to watch and the first waiver targets of the week."
    return dict(kind='recap', src=SRC_POST + isrc, title=title, dek=dek, body=body, players=uniq(ment), teams=sorted(teams), wk=w, img={'k': 'player', 'pid': allp[0][0]['id']} if allp else None), None


# ---------------------------------------------------------------- outlooks
def start_sit(gs, w):
    teams = {t for g in gs for t in (g['home'], g['away'])}; starts = []; sits = []
    for p in P:
        if p['t'] not in teams or proj_wk(p, w) <= 0: continue
        wr, ur = wk_rank(p, w), usual_rank(p)
        if not wr or not ur: continue
        cut = {'QB': 12, 'RB': 24, 'WR': 30, 'TE': 12}[p['p']]
        if wr <= cut and ur > cut + 4: starts.append((ur - wr, p, wr, ur))
        if ur <= cut and wr > cut + 4 and p.get('inj') not in ('Out', 'IR'): sits.append((wr - ur, p, wr, ur))
    starts.sort(key=lambda x: -x[0]); sits.sort(key=lambda x: -x[0])
    return starts[:3], sits[:3]
def team_outlook(g, tm, key, deep=True):
    """one offense's fantasy outlook for a game"""
    w = g['wk']; opp = g['away'] if tm == g['home'] else g['home']; it = g['ih'] if tm == g['home'] else g['ia']; out = []
    qb = qb_of(tm)
    if qb and proj_wk(qb, w) > 0:
        r = wk_rank(qb, w); mw = matchup_words(opp, 'QB')
        out.append(pick([f"{qb['n']} projects for {f1(proj_wk(qb, w))} points" + (f" (QB{r} this week)" if r else '') + vs(mw) + '.', f"Under center, {qb['n']} is at {f1(proj_wk(qb, w))} projected points" + (f", QB{r} on the week" if r else '') + vs(mw) + '.'], key, qb['id']))
    elif qb is None or proj_wk(qb, w) <= 0:
        q2 = next((q for q in P if q['t'] == tm and q['p'] == 'QB' and q.get('qbs')), None)
        if q2: out.append(f"{q2['n']} is expected to start at quarterback.")
    rbs = team_players(tm, w, 2, ('RB',))
    if rbs:
        p = rbs[0]; cs = p.get('cs'); mw = matchup_words(opp, 'RB')
        s = pick([f"{p['n']} leads the backfield" + (f" with {round(cs * 100)}% of the carries this season" if cs else '') + f" and projects for {f1(proj_wk(p, w))}" + vs(mw) + '.',
                  f"The backfield belongs to {p['n']}" + (f", who has taken {round(cs * 100)}% of the carries" if cs else '') + f"; he projects for {f1(proj_wk(p, w))}" + vs(mw) + '.'], key, p['id'])
        if len(rbs) > 1 and proj_wk(rbs[1], w) >= 7: s += f" {rbs[1]['n']} ({f1(proj_wk(rbs[1], w))}) is involved enough to flex in deeper leagues."
        out.append(s)
    rec = team_players(tm, w, 3, ('WR', 'TE'))
    if rec:
        p = rec[0]; ts = p.get('ts'); mw = matchup_words(opp, p['p'])
        s = pick([f"{p['n']} is the top target" + (f", drawing {round(ts * 100)}% of the looks" if ts else '') + f"; he projects for {f1(proj_wk(p, w))}" + vs(mw) + '.',
                  f"In the passing game, {p['n']} is the go-to option" + (f" ({round(ts * 100)}% target share)" if ts else '') + f" at {f1(proj_wk(p, w))} projected points" + vs(mw) + '.'], key, p['id'])
        if len(rec) > 1: s += ' ' + andj([f"{q['n']} ({f1(proj_wk(q, w))})" for q in rec[1:]]) + ' round out the passing game.'
        out.append(s)
    if deep and it:
        tpl, tpr = pace(tm)
        if tpl and tpr: out.append(f"The {tm_name(tm)} run {f1(tpl)} plays a game and pass {round(tpr * 100)}% of the time; Vegas expects {f1(it)} points from them.")
    return ' '.join(out)
def injury_line(gs, w):
    L = injured({t for g in gs for t in (g['home'], g['away'])}, w)
    if not L: return ''
    return 'Injury report: ' + '; '.join(f"{p['n']} ({p['t']}, {inj_word(p)}{', ' + p['injd'].lower() if p.get('injd') else ''})" for p in L[:6]) + '.'
def prediction(g):
    if g['ih'] is None or g['ia'] is None: return ''
    h, a = round(g['ih']), round(g['ia'])
    if h == a: h += 1 if (g['sp'] or 0) <= 0 else 0; a += 1 if (g['sp'] or 0) > 0 else 0
    wp = win_prob(g, g['home'] if h > a else g['away'])
    wn = g['home'] if h > a else g['away']
    return f"{tm_name(wn)} {max(h, a)}, {tm_name(g['away'] if wn == g['home'] else g['home'])} {min(h, a)}" + (f" ({an_n(round(wp * 100))} {round(wp * 100)}% win chance from the spread)" if wp else '')
def props_lines(gs, w, n=3):
    """props to know: BFF's predicted lines for the game's headliners and its best touchdown chances (no picks: BFF
    sets lines where it expects books to, from its own numbers, and says how often such overs have hit)"""
    T = {t for g in gs for t in (g['home'], g['away'])}; out = []
    td = sorted(lines_for(T, w, 'td'), key=lambda x: -x['po'])[:2]
    if td:
        tdw = [PI[x['pid']]['n'] + ' ' + str(round(x['po'] * 100)) + '%' for x in td]
        out.append(f"Most likely to score: {andj(tdw)} (BFF's chance of any rushing, receiving or return touchdown).")
    yds = sorted([x for x in lines_for(T, w) if x['k'] in ('py', 'ty', 'ry')], key=lambda x: -x['line'])
    seen = set()
    for x in yds:
        if x['pid'] in seen or len(out) >= n + 1: continue
        seen.add(x['pid']); p = PI[x['pid']]
        out.append(f"{p['n']}: BFF expects his {SNAME[x['k']]} line around {x['line']} (projects {fnum(round(x['mm'], 1))}).")
    return out


def write_outlook(gs, key, label):
    """Thursday, Monday or any other day's game(s), in depth"""
    fresh()
    w = gs[0]['wk']; body = []; ment = []
    g0 = gs[0]
    for g in gs:
        body.append(GH(g))
        ra, rh = record(g['away'], w - 1), record(g['home'], w - 1)
        lede = pick([f"The {tm_name(g['away'])} ({ra}) visit the {tm_name(g['home'])} ({rh}) {gdaytime(g)}.", f"{tm_name(g['away'])} ({ra}) at {tm_name(g['home'])} ({rh}) kicks off {gdaytime(g)}."], key, g['home'])
        if vegas(g): lede += ' ' + line_story(g, key) + (f" Translated into points, the books expect about {fnum(round(g['ia'] or 0))} from {the(g['away'])} and {fnum(round(g['ih'] or 0))} from {the(g['home'])}." if g['ia'] and g['ih'] else '')
        ra_, rh_ = result_words(g['away'], w), result_words(g['home'], w)
        if ra_ and rh_: lede += f" The {tm_name(g['home'])} {rh_}; the {tm_name(g['away'])} {ra_}."
        hh = hot_hand({g['home'], g['away']}, w)
        if hh: lede += ' ' + pick([f"{hh[0]['n']} comes in hot after {an_n(hh[1])} {f1(hh[1])}-point game.", f"Watch {hh[0]['n']}, who is coming off {an_n(hh[1])} {f1(hh[1])}-point outing."], key, 'hh')
        body.append(P_(lede))
        body.append(H_(f"{tm_name(g['away'])} outlook")); body.append(P_(team_outlook(g, g['away'], key)))
        body.append(H_(f"{tm_name(g['home'])} outlook")); body.append(P_(team_outlook(g, g['home'], key)))
        il = injury_line([g], w)
        if il: body.append(P_(il))
        ment += team_players(g['away'], w, 5) + team_players(g['home'], w, 5)
    st, sit = start_sit(gs, w)
    if st or sit:
        body.append(H_("Start 'em, sit 'em"))
        body.append(UL([f"Start {p['n']} ({p['p']}, {p['t']}): ranks {p['p']}{wr} this week, well above his usual {p['p']}{ur}." for _, p, wr, ur in st]
                       + [f"Sit {p['n']} ({p['p']}, {p['t']}): only {p['p']}{wr} this week after ranking {p['p']}{ur} most weeks." for _, p, wr, ur in sit]))
        ment += [x[1] for x in st + sit]
    bl = props_lines(gs, w)
    if bl: body.append(H_('Props to know')); body.append(UL(bl + ['Lines are BFF\'s predictions of where books will post them, not picks. For entertainment, 21+ where legal.']))
    preds = [prediction(g) for g in gs if prediction(g)]
    if preds: body.append(H_('The score Vegas implies')); body.append(P_(' '.join(f"{x}." for x in preds) + " That score is Vegas' implied points, not a BFF model; the fantasy calls above are ours, and this outlook updates until kickoff."))
    night = ghour(g0) >= 19 and len(gs) == 1
    day = DOW[gday(g0).weekday()]
    show = {'Thursday': 'Thursday Night Football', 'Monday': 'Monday Night Football', 'Sunday': 'Sunday Night Football'}.get(day) if night else None
    if len(gs) == 1:
        title = pick([f"{show or label + ' outlook'}: {tm_name(g0['away'])} at {tm_name(g0['home'])}, the fantasy breakdown", f"{tm_name(g0['away'])} at {tm_name(g0['home'])}: {label} outlook, start/sit and props",
                      f"{label} outlook: what to expect from {tm_name(g0['away'])} at {tm_name(g0['home'])}"], key, 't')
    else: title = f"{label} outlook: all {numw(len(gs))} games, start/sit and props"
    dek = f"The matchup, both offenses' fantasy outlook, injuries, start/sit calls and props to know for {'the game' if len(gs) == 1 else 'every game'}. Updates until kickoff."
    return dict(kind='outlook', src=SRC_PRE, title=title, dek=dek, body=body, players=uniq(ment), teams=sorted({t for g in gs for t in (g['home'], g['away'])}), wk=w,
                img={'k': 'game', 'away': g0['away'], 'home': g0['home'], 'gid': g0.get('gid')}), facts_digest([PI[i] for i in uniq(ment)], gs)


def line_story(g, key):
    """what the Vegas line says about a game, as an analyst would put it (the same spread and total, in words)"""
    if g['sp'] is None or g['ou'] is None: return ''
    fav, sp = fav_of(g); ou = g['ou']; F = tm_name(fav) if fav else None
    if not fav: s = pick([f"Vegas can't split these two: it's a pick'em", f"The books see a true coin flip, a pick'em"], key, 'ls0')
    elif sp >= 10: s = pick([f"The {F} are double-digit favorites ({fnum(sp)} points)", f"Vegas makes the {F} {fnum(sp)}-point favorites, a mismatch on paper"], key, 'ls1')
    elif sp >= 6.5: s = pick([f"The {F} are favored by {fnum(sp)}, more than a touchdown", f"The {F} are solid {fnum(sp)}-point favorites"], key, 'ls2')
    elif sp >= 3: s = pick([f"The {F} are {fnum(sp)}-point favorites", f"Vegas leans the {F}' way by {fnum(sp)}"], key, 'ls3')
    else: s = pick([f"The {F} are slim {fnum(sp)}-point favorites, so expect a close one", f"It's close to a coin flip, with the {F} favored by just {fnum(sp)}"], key, 'ls4')
    if ou >= 50: t = pick([f", and the {fnum(ou)} total says shootout: start your guys with confidence.", f" in a game totaled at {fnum(ou)}, one of the best fantasy environments of the week."], key, 'lt1')
    elif ou >= 46: t = f", with a healthy {fnum(ou)} total."
    elif ou <= 39.5: t = pick([f", and {an_n(ou)} {fnum(ou)} total points to a low-scoring grind, so temper expectations.", f", but the {fnum(ou)} total is one of the lowest you'll see: think field goals and punts."], key, 'lt2')
    else: t = f", with a middle-of-the-road {fnum(ou)} total."
    return s + t
def capsule(g, key):
    """a few sentences on one game: the line, the best play, one more angle, who is out"""
    w = g['wk']; ls_ = line_story(g, key); s = (ls_ + ' ' if ls_ else '') + f"Kickoff is {gtime(g)}."
    tops = sorted(team_players(g['away'], w, 4) + team_players(g['home'], w, 4), key=lambda p: -proj_wk(p, w))
    if tops:
        p = tops[0]; opp = g['home'] if p['t'] == g['away'] else g['away']; mw = matchup_words(opp, p['p'])
        s += ' ' + pick([f"{p['n']} is the play to build around here ({f1(proj_wk(p, w))} projected)", f"The headliner is {p['n']}, projected for {f1(proj_wk(p, w))}", f"Everything runs through {p['n']}, who projects for {f1(proj_wk(p, w))}"], key, g['home']) + vs(mw) + '.'
    angle = None
    for p in tops[1:]:
        wr, ur = wk_rank(p, w), usual_rank(p)
        if wr and ur and wr + 8 <= ur: angle = pick([f"The sneaky play is {p['n']}: he ranks {p['p']}{wr} this week, well above his usual {p['p']}{ur}.", f"Keep an eye on {p['n']}, who jumps to {p['p']}{wr} this week from his usual {p['p']}{ur}."], key, p['id']); break
    if not angle:
        x = (sorted(lines_for({g['home'], g['away']}, w, 'td'), key=lambda x: -x['po']) or [None])[0]
        if x: angle = f"Most likely to find the end zone, by BFF's numbers: {PI[x['pid']]['n']}, at {round(x['po'] * 100)}%."
    if angle: s += ' ' + angle
    outs = injured({g['home'], g['away']}, w, ('Out', 'Doubtful'))
    if outs: s += ' ' + dot(f"Out: {andj([p['n'] for p in outs[:3]])}")
    q = injured({g['home'], g['away']}, w, ('Questionable',))
    if q: s += ' ' + dot(f"Questionable: {andj([p['n'] for p in q[:3]])}")
    return s, tops[:3]


def write_sunday_outlook(gs, key):
    """the Saturday-morning look at every Sunday game"""
    fresh()
    w = gs[0]['wk']; body = []; ment = []
    wl = [g for g in gs if g['ou'] is not None]
    hi = max(wl, key=lambda g: g['ou']) if wl else None; lo = min(wl, key=lambda g: g['ou']) if wl else None
    its = sorted([(g['ih'], g['home'], g) for g in gs if g['ih']] + [(g['ia'], g['away'], g) for g in gs if g['ia']], key=lambda x: -x[0])
    byes = sorted({t for t in (D.get('sched') or {}) if not any(x[0] == w and x[1] for x in D['sched'][t])})
    outs = injured({t for g in gs for t in (g['home'], g['away'])}, w, ('Out', 'IR', 'Doubtful'))
    intro = pick([f"Sunday brings {plural(len(gs), 'game')}, from the early window through the night game, and a handful of lineup decisions that will swing matchups.", f"Week {w}'s Sunday slate has {plural(len(gs), 'game')}. Here is where the points should be, and where they probably won't."], key, 'i')
    if hi: intro += f" {tm_name(hi['away'])} at {tm_name(hi['home'])} carries the highest total ({fnum(hi['ou'])})"
    if its: intro += f", and {the(its[0][1])} have the biggest implied team total at {f1(its[0][0])} points." if hi else f" {The(its[0][1])} have the biggest implied team total at {f1(its[0][0])} points."
    elif hi: intro += '.'
    if byes: intro += f" On bye: {andj([tm_name(t) for t in byes])}."
    body.append(P_(intro))
    things = []
    if outs: things.append(f"Key absences: {andj([p['n'] + ' (' + p['t'] + ')' for p in outs[:5]])}. Every projection below already accounts for them.")
    if lo and hi and lo is not hi: things.append(f"Lowest total: {tm_name(lo['away'])} at {tm_name(lo['home'])} ({fnum(lo['ou'])}). Vegas expects a slog, so lower your expectations for everyone in that one.")
    if its and len(its) > 1: things.append(f"Best offensive environments: {andj([f'{tm_name(t)} ({f1(v)})' for v, t, _ in its[:3]])}.")
    st, sit = start_sit(gs, w)
    if things: body.append(H_('Things to know')); body.append(UL(things))
    if st or sit:
        body.append(H_("Start 'em, sit 'em"))
        body.append(UL([f"Start {p['n']} ({p['p']}, {p['t']}): {p['p']}{wr} this week, well above his usual {p['p']}{ur}." for _, p, wr, ur in st]
                       + [f"Sit {p['n']} ({p['p']}, {p['t']}{', ' + inj_word(p) if p.get('inj') else ''}): only {p['p']}{wr} this week after ranking {p['p']}{ur} most weeks." for _, p, wr, ur in sit]))
        ment += [x[1] for x in st + sit]
    body.append(H_('Game by game'))
    for g in gs:
        body.append(GH(g)); s, tp = capsule(g, key); body.append(P_(s)); ment += tp
    bl = props_lines(gs, w, 4)
    if bl: body.append(H_('Props to know')); body.append(UL(bl + ['Lines are BFF\'s predictions of where books will post them, not picks. For entertainment, 21+ where legal.']))
    title = pick([f"Week {w} Sunday outlook: {hi['away']}-{hi['home']} headlines {an_n(len(gs))} {len(gs)}-game slate" if hi else f"Week {w} Sunday outlook",
                  f"Week {w} Sunday outlook: every game's fantasy angle", f"Sunday, week {w}: who to start, who to sit, what Vegas expects"], key, 't')
    dek = f"Things to know, start/sit calls, every game's fantasy outlook and props to know for all {len(gs)} Sunday games. Updates until kickoff."
    return dict(kind='slate', src=SRC_PRE, title=title, dek=dek, body=body, players=uniq(ment), teams=sorted({t for g in gs for t in (g['home'], g['away'])}), wk=w,
                img={'k': 'game', 'away': hi['away'], 'home': hi['home'], 'gid': hi.get('gid')} if hi else None), facts_digest([PI[i] for i in uniq(ment)], gs)


# ---------------------------------------------------------------- the week: Friday injury report, Tuesday landscape
def benefactors(p, n=2):
    L = [q for q in P if q['t'] == p['t'] and q['id'] != p['id'] and q['p'] == p['p'] and proj_wk(q, p.get('nw') or 0) > 0]
    return sorted(L, key=lambda q: -proj_wk(q, p.get('nw') or 0))[:n]
def write_injury_report(w, gs, key):
    fresh()
    teams = {t for g in gs for t in (g['home'], g['away'])}
    outs = injured(teams, w, ('Out', 'Doubtful')); irs = [p for p in injured(teams, w, ('IR',)) if (p.get('rl') or 0) >= 10]
    qs = injured(teams, w, ('Questionable',))
    if not outs and not qs and not irs: return None, None
    body = []; ment = []
    late = [g for g in gs if ghour(g) >= 16 or DOW[gday(g).weekday()] != 'Sunday']
    body.append(P_(f"Friday's reports are in for week {w}: {plural(len(outs), 'notable player')} {'is' if len(outs) == 1 else 'are'} out or doubtful and {len(qs)} more {'is' if len(qs) == 1 else 'are'} questionable."
                   + " Here is who is affected, who benefits, and how to plan around the game-time decisions."))
    if outs:
        body.append(H_('Ruled out or doubtful'))
        L = []
        for p in outs[:10]:
            b = benefactors(p); ment += [p] + b
            L.append(f"{p['n']} ({p['p']}, {p['t']}, {inj_word(p)}{', ' + p['injd'].lower() if p.get('injd') else ''})" + (f": {andj([f'{q[chr(110)]} ({f1(proj_wk(q, w))} projected)' if i == 0 else q['n'] for i, q in enumerate(b)])} {'move' if len(b) > 1 else 'moves'} up" if b else '') + '.')
        body.append(UL(L))
    if irs: body.append(P_(dot(f"Still on injured reserve: {andj([p['n'] + ' (' + p['t'] + ')' for p in irs[:8]])}")))
    if qs:
        body.append(H_('Questionable: the game-time decisions'))
        L = []
        for p in qs[:10]:
            g = next((g for g in gs if p['t'] in (g['home'], g['away'])), None); ment.append(p)
            L.append(f"{p['n']} ({p['p']}, {p['t']}{', ' + p['injd'].lower() if p.get('injd') else ''})" + (f", {gdaytime(g)}" if g else '') + (f". {p['injn']}" if p.get('injn') else '') + '.')
        body.append(UL(L))
        body.append(P_("Questionable players played 61% of the time in 2021-2025. For the 4 PM and night games you cannot wait for the news and still pick a replacement from the early games, so keep a pivot from the same window or later on your bench, and check the inactive list 90 minutes before kickoff."
                       if late else "Questionable players played 61% of the time in 2021-2025. Check the inactive list 90 minutes before kickoff."))
    qbx = [(t, qb_of(t)) for t in sorted(teams)]
    qbx = [(t, q) for t, q in qbx if q and q.get('role') not in (None, 'QB1')]
    if qbx:
        body.append(H_('Quarterback situations'))
        body.append(UL([f"{tm_name(t)}: {q['n']} is expected to start ({f1(proj_wk(q, w))} projected)." for t, q in qbx])); ment += [q for _, q in qbx]
    top = (outs or qs or irs)[0]
    title = pick([f"Week {w} injury report: {top['n']} {'out' if top in outs else 'questionable'}, and everything else that matters", f"Week {w} injury report: who's out, who's a game-time decision"], key, 't')
    dek = "Every fantasy-relevant player ruled out, doubtful or questionable this week, who benefits, and the quarterback situations. Updates until Sunday."
    return dict(kind='injuries', src=SRC_PRE, title=title, dek=dek, body=body, players=uniq(ment), teams=sorted(teams), wk=w, img={'k': 'player', 'pid': top['id']}), facts_digest(ment, gs)


def usage_change(p, w):
    """expected points (usage) in his last 2 games vs his season before them"""
    L = [x for x in season_games(p, w + 1) if x[2] is not None]
    if len(L) < 4: return None
    last2 = sum(x[2] for x in L[-2:]) / 2; before = sum(x[2] for x in L[:-2]) / len(L[:-2])
    return last2 - before, last2, before
def write_landscape(w, key):
    """Tuesday: the fantasy landscape after the week"""
    fresh()
    rows = [(p, x) for p in P for x in (p.get('wk') or []) if x[0] == w and x[1] is not None]
    if len(rows) < 40: return None, None
    body = []; ment = []
    byp = {q: sorted([(p, x) for p, x in rows if p['p'] == q], key=lambda y: -y[1][1]) for q in ('QB', 'RB', 'WR', 'TE')}
    top_all = sorted(rows, key=lambda y: -y[1][1])
    intro = pick([f"Week {w} is in the books.", f"Another week down: here is where the fantasy landscape stands after week {w}."], key, 'i')
    if top_all: intro += f" {top_all[0][0]['n']} led everyone with {f1(top_all[0][1][1])} PPR points."
    body.append(P_(intro))
    body.append(H_(f"Week {w} MVPs"))
    body.append(UL([f"{q}: {byp[q][0][0]['n']} ({byp[q][0][0]['t']}), {f1(byp[q][0][1][1])} points" + (f" on {byp[q][0][1][4]} targets" if q in ('WR', 'TE') and byp[q][0][1][4] else f" on {byp[q][0][1][5]} carries" if q == 'RB' and byp[q][0][1][5] else '') + '.' for q in ('QB', 'RB', 'WR', 'TE') if byp[q]]))
    ment += [byp[q][0][0] for q in byp if byp[q]]
    ch = [(usage_change(p, w), p) for p in P if p['p'] != 'QB']
    ch = [(c, p) for c, p in ch if c]
    ris = sorted([x for x in ch if x[0][0] >= 3 and x[0][1] >= 8], key=lambda x: -x[0][0])[:5]
    # fallers are role changes: a player who just missed time hurt (or is out) is injury news, not a usage drop
    fal = sorted([x for x in ch if x[0][0] <= -3 and x[0][2] >= 8 and x[1].get('inj') not in ('IR', 'Out', 'Doubtful') and x[1].get('injs') != 'expected'], key=lambda x: x[0][0])[:5]
    if ris:
        body.append(H_('Risers'))
        body.append(UL([f"{p['n']} ({p['p']}, {p['t']}): " + pick([f"his usage was worth {f1(c[1])} expected points a game over the last two weeks, up from {f1(c[2])} before.",
                                                                       f"{f1(c[1])} expected points a game of usage the last two weeks, more than his {f1(c[2])} before that.",
                                                                       f"the opportunity jumped to {f1(c[1])} expected points a game, from {f1(c[2])}."], key, p['id'])
                        + ' ' + pick(['Usage like that tends to stick.', 'Volume is the stickiest stat in fantasy.', 'That is a role change, not a fluke.', 'Act before the rest of your league does.'], key, p['id'], 'b') for c, p in ris]))
        ment += [p for _, p in ris]
    if fal:
        body.append(H_('Fallers'))
        def fal_note(p):
            if p.get('inj') and p.get('injs') == 'report': return f" He is listed {p['inj'].lower()}."
            if 'for the season' in (p.get('injn') or ''): return ' He has since been ruled out for the season.'
            sn = low_snap(p, w)   # a starter who barely played his last game usually got hurt in it: say so, don't call it a role change
            if sn is not None:
                return f" He played just {round(sn * 100)}% of the snaps in week {w}, which often points to an injury, so check Wednesday's injury report before reading it as a role change."
            return ' Watch his snap share this week.'
        body.append(UL([f"{p['n']} ({p['p']}, {p['t']}): down to {f1(c[1])} expected points a game over the last two weeks from {f1(c[2])}." + fal_note(p) for c, p in fal]))
        ment += [p for _, p in fal]
    inj = [p for p in P if p.get('inj') in ('Out', 'IR', 'Doubtful') and ((p.get('rl') or 0) >= 10 or ovr_rank(p) <= 100)]
    if inj:
        body.append(H_('Injury fallout'))
        body.append(UL([f"{p['n']} ({p['p']}, {p['t']}, {inj_word(p)}{', ' + p['injd'].lower() if p.get('injd') else ''})" + (f": {andj([q['n'] for q in benefactors(p)])} {'stands' if len(benefactors(p)) == 1 else 'stand'} to gain." if benefactors(p) else '.') for p in sorted(inj, key=lambda p: -(p.get('rl') or 0))[:6]]))
        ment += inj[:6]
    nw = w + 1
    pjn = lambda p: proj_wk(p, nw) or (float(p.get('rl') or 0) if not any(r[0] == nw for r in p.get('ros') or []) and p.get('nw') != nw else 0.0)
    wav = [p for p in P if likely_free(p) and p['p'] != 'QB' and pjn(p) >= 7 and p.get('inj') not in ('Out', 'IR')]
    wav = sorted(wav, key=lambda p: -(pjn(p) + 2 * ((usage_change(p, w) or (0,))[0])))[:6]
    if wav:
        body.append(H_('Waiver wire priorities'))
        body.append(UL([f"{p['n']} ({p['p']}, {p['t']}, {p['p']}{pos_rank(p)} for the rest of the season by BFF, so likely on waivers in 12-team leagues): projects for {f1(pjn(p))} a game going forward" + (", and his usage is climbing" if (usage_change(p, w) or (0,))[0] >= 2 else '') + '.' for p in wav]))
        ment += wav
    bl = [p for p in P if p['p'] != 'QB' and (p.get('g') or 0) >= 3 and p.get('xfpg') and p.get('fpg') is not None and p['xfpg'] >= 9 and p['xfpg'] - p['fpg'] >= 2.5 and p.get('inj') not in ('Out', 'IR')]
    sh = [p for p in P if p['p'] != 'QB' and (p.get('g') or 0) >= 3 and p.get('xfpg') and p.get('fpg') is not None and p['fpg'] >= 11 and p['fpg'] - p['xfpg'] >= 3]
    if bl or sh:
        body.append(H_('Buy low, sell high'))
        body.append(UL([f"Buy low: {p['n']} ({p['t']}) is scoring {f1(p['fpg'])} a game on usage worth {f1(p['xfpg'])}." for p in sorted(bl, key=lambda p: -(p['xfpg'] - p['fpg']))[:3]]
                       + [f"Sell high: {p['n']} ({p['t']}) is scoring {f1(p['fpg'])} a game on usage worth only {f1(p['xfpg'])}." for p in sorted(sh, key=lambda p: -(p['fpg'] - p['xfpg']))[:3]]))
        ment += bl[:3] + sh[:3]
    nx = [g for g in GAMES if g['wk'] == nw]
    if nx:
        byes = sorted({t for t in (D.get('sched') or {}) if not any(x[0] == nw and x[1] for x in D['sched'][t])})
        its = sorted([(g['ih'], g['home']) for g in nx if g['ih']] + [(g['ia'], g['away']) for g in nx if g['ia']], key=lambda x: -x[0])
        s = f"Week {nw} has {plural(len(nx), 'game')}."
        if byes: s += f" On bye: {andj([tm_name(t) for t in byes])}, so plan around those players now."
        if its: s += f" The best offensive environments by Vegas: {andj([f'{tm_name(t)} ({f1(v)})' for v, t in its[:3]])}."
        body.append(H_(f"Looking ahead to week {nw}")); body.append(P_(s))
    C = ((D.get('calls') or {}).get('weeks') or {}).get(str(w)) or {}
    gr = lambda k: [e for e in C.get(k) or [] if e.get('res') in ('hit', 'miss')]
    if gr('start') or gr('sit'):
        a, b = gr('start'), gr('sit')
        body.append(H_("BFF's calls scorecard"))
        body.append(P_(f"Our week {w} must starts finished as starters {sum(e['res'] == 'hit' for e in a)} of {len(a)} times" + (f", and our must sits finished outside the starter spots {sum(e['res'] == 'hit' for e in b)} of {len(b)} times." if b else '.')
                       + " Every call is graded with official stats in Fantasy Help, Weekly calls."))
    lead = (ris[0][1] if ris else top_all[0][0] if top_all else None)
    title = pick([f"Week {w} fantasy landscape: {poss(lead['n'])} rise, waiver priorities and what changed" if lead else f"Week {w} fantasy landscape",
                  f"After week {w}: risers, fallers and the waiver wire", f"The fantasy landscape after week {w}: who's up, who's down, who to add"], key, 't')
    dek = f"Week {w}'s MVPs, the risers and fallers by usage, injury fallout, waiver priorities, buy-low and sell-high targets and a look at week {nw}."
    return dict(kind='landscape', src=[{'s': 'Official stats and usage (nflverse)', 'u': 'https://github.com/nflverse/nflverse-data'}, {'s': 'BFF projections and weekly calls', 'u': ''}],
                title=title, dek=dek, body=body, players=uniq(ment), teams=[], wk=w, img={'k': 'player', 'pid': lead['id']} if lead else None), None


# ---------------------------------------------------------------- breaking news
BV = 2   # version of the breaking-news keys (2: injury news keyed by week, activations apart from placements)
POSN = {'QB': 'quarterbacks', 'RB': 'running backs', 'WR': 'wide receivers', 'TE': 'tight ends'}
def depth(q):
    """'No. 2 running back on the depth chart' from 'RB2' (the label alone reads like a fantasy tier)"""
    m = re.match(r'^(QB|RB|WR|TE)(\d)$', q.get('role') or '')
    return f"No. {m.group(2)} {POSN[m.group(1)][:-1]} on the depth chart" if m else f"{POSN[q['p']][:-1]} depth"
def teammates(p, n=3):
    L = [q for q in P if q['t'] == p['t'] and q['id'] != p['id'] and q['p'] == p['p'] and (q.get('rl') or 0) > 0]
    return sorted(L, key=lambda q: -(q.get('rl') or 0))[:n]
def write_breaking(p, ev, key):
    fresh()
    w = p.get('nw') or D['asof']['next_week']; kind = ev['kind']; n = p['n']; ln = last(n)
    if kind == 'out' and 'for the season' in (p.get('injn') or ''): kind = 'season'   # BFF already has him out for the season
    if kind in ('reinstate', 'reinstated'): return write_reinstate(p, ev, key, kind)
    what = {'season': f"{n} is out for the rest of the season", 'ir': f"{n} has been placed on injured reserve", 'out': f"{n} has been ruled out for week {w}", 'doubtful': f"{n} is doubtful for week {w}",
            'traded': f"{n} has been traded", 'released': f"{n} has been released", 'activated': f"{n} has been activated from injured reserve"}[kind]
    title = pick({'season': [f"{n} out for the season: the fantasy fallout", f"Season over for {n}: who steps up", f"Fantasy fallout: {n} is done for the season"],
                  'ir': [f"{n} to injured reserve: what it means for fantasy", f"{n} lands on IR. Here is the fantasy fallout", f"Fantasy fallout: {n} heads to injured reserve"],
                  'out': [f"{n} ruled out for week {w}: who to start instead", f"Fantasy fallout: {n} is out this week", f"{n} out for week {w}. Here is what to do"],
                  'doubtful': [f"{n} doubtful for week {w}: pivot now", f"{n} is doubtful. Here is your backup plan"],
                  'traded': [f"{n} traded: what it means for fantasy", f"Fantasy fallout from the {n} trade"],
                  'released': [f"{n} released: the fantasy fallout", f"{n} cut: who benefits"],
                  'activated': [f"{n} back from injured reserve: the fantasy outlook", f"{n} activated off IR: start him or wait?"]}[kind], key)
    body = [P_(f"{what}{(' (' + ev['why'] + ')') if ev.get('why') else ''}" + (f", according to {ev['src']}." if ev.get('src') else '.')
               + ' ' + pick({'season': ["It's a gut punch for his fantasy managers, and it reshapes the depth chart for the rest of the year.", "That changes the outlook for the whole offense the rest of the way."],
                              'ir': ["That means at least four games on the shelf, so plan for life without him for a while.", "Fantasy managers need a plan for the next month at least."],
                              'out': ["Managers with him in their lineup need to pivot now.", "If he is in your lineup, it's time to make a change."],
                              'doubtful': ["Doubtful players rarely suit up, so treat this as an absence and set your lineup accordingly.", "Plan as if he will sit."],
                              'traded': ["A new team means a new role, and the ripple effects reach both depth charts.", "Here is how the move shakes out for fantasy."],
                              'released': ["His fantasy value now depends on where he lands, and his old team's depth chart shifts today.", "Here is who picks up the slack."],
                              'activated': ["Good news for his managers, though first games back often come with a pitch count.", "He is back, but ease him in if you can."]}[kind], key, 'bl'))]
    ur = usual_rank(p); g_ = p.get('g') or 0
    s = f"{ln} has averaged {f1(p.get('fpg') or 0)} PPR points over {cnt(g_, 'game')} this season" if g_ else f"{ln} has not played this season"
    # "ranks 2nd among running backs", not "an RB2" (which reads as a tier, the 13th to 24th back)
    if ur and ur <= 60: s += f" and ranks {ordn(ur)} among {POSN[p['p']]} in BFF's per-game rest-of-season projection when healthy"
    s += '.'
    if kind == 'ir' and p.get('ret'):
        rep = f"; he was {p['injn'][0].lower() + p['injn'][1:]}" if p.get('injs') == 'news' and p.get('injn') else ''
        s += (f" Players on injured reserve must miss at least four games{rep}. BFF expects him back around week {p['ret']} at the earliest, and those returns often slip."
              if p['ret'] <= 18 else f" Players on injured reserve must miss at least four games{rep}, and BFF doesn't expect him back this season.")
    body.append(P_(s))
    tm = teammates(p)
    if kind == 'activated':
        pw_ = proj_wk(p, w)
        body.append(H_('His outlook'))
        body.append(P_(f"BFF projects {ln} for {f1(pw_)} PPR points in week {w}" + (f", which makes him {'an' if p['p'] == 'RB' else 'a'} {p['p']}{wk_rank(p, w)} for the week" if pw_ > 0 and wk_rank(p, w) else '') + ". First games back from injured reserve can come with a snap count, so the projection leans conservative." if pw_ > 0 else f"BFF does not project {ln} to play in week {w} yet; his projection returns once he is expected to suit up."))
        if tm:
            body.append(H_('Whose role shrinks'))
            body.append(UL([f"{q['n']} ({depth(q)}) projects for {f1(proj_wk(q, w))} in week {w}." for q in tm if proj_wk(q, w) > 0] or [f"No {tm_name(p['t'])} {p['p']} projects for meaningful points behind {ln}."]))
        body.append(H_('What to do'))
        body.append(UL([f"Move {ln} out of your IR slot and back into your lineup plans" + (f"; at {f1(pw_)} projected points he is worth starting over most bench options." if pw_ >= 10 else "; give him a week to show his workload if you have a steadier option."),
                        "BFF's projections, rankings and trade values already reflect this, or will after the next data update (every 3 hours)."]))
        dek = f"{what}. His outlook for week {w}, whose role shrinks on the {tm_name(p['t'])}, and what to do with your lineup."
        return dict(kind='breaking', title=title, dek=dek, body=body, players=uniq([p] + tm), teams=[p['t']], wk=w, img={'k': 'player', 'pid': p['id']}, src=[{'s': 'BFF projections and depth charts (nflverse)', 'u': ''}]), None
    if p['p'] == 'QB': tm = [q for q in tm if proj_wk(q, w) > 0 or q.get('qbs')][:1] or tm[:1]
    body.append(H_('Who benefits'))
    # BFF's numbers still have him playing when the news comes in between data updates (the update shifts his work to the
    # others): those projections are from before the news, so they are labeled that way and the waiver call uses the
    # depth chart instead
    stale = kind in ('out', 'doubtful', 'ir', 'season') and proj_wk(p, w) > 0
    if any(proj_wk(q, w) > 0 for q in tm): tm = [q for q in tm if proj_wk(q, w) > 0 or not likely_free(q)]   # (a backup BFF has at zero is hurt or inactive himself)
    if tm:
        L = []
        for q in tm:
            cl = ([f"projected for {f1(proj_wk(q, w))} in week {w} before the news" if stale else f"projects for {f1(proj_wk(q, w))} in week {w}"] if proj_wk(q, w) > 0 else []) + ([f"ranks outside BFF's top {ROST[q['p']]} at {q['p']}, so he is likely on waivers"] if likely_free(q) else [])
            L.append(f"{q['n']} ({depth(q)})" + (' ' + andj(cl) if cl else '') + '.')
        if p['p'] == 'QB' and tm: L[0] = L[0].rstrip('.') + '; he is the expected starter.'
        body.append(UL(L))
        # an add only when he projects like a fantasy starter this week (RB/WR 8+, TE 6+, QB 14+ PPR points); otherwise
        # the work spreads out and nobody behind him is worth a waiver claim
        BAR = {'QB': 14, 'RB': 8, 'WR': 8, 'TE': 6}
        free = sorted([q for q in tm if likely_free(q) and proj_wk(q, w) >= BAR.get(q['p'], 8)], key=lambda q: -proj_wk(q, w))
        nxt = next((q for q in tm if q.get('role') == p['p'] + '2'), None) if p.get('role') == p['p'] + '1' else None
        if stale and p['p'] == 'RB' and nxt:
            body.append(P_(f"Waiver priority: {nxt['n']} is next in line for {poss(n if last(nxt['n']) == ln else ln)} carries" + (", and he is the add if he is on your wire." if likely_free(nxt) else ", though he is likely rostered already.")
                           + f" BFF's projections give him the extra work with the next data update (within 3 hours)."))
        elif stale and p['p'] == 'QB' and nxt:
            body.append(P_(f"{nxt['n']} is next in line to start. He is worth a waiver claim mainly in two-quarterback and superflex leagues; BFF's projections move the starts to him with the next data update (within 3 hours)."))
        elif stale:
            body.append(P_(f"{poss(ln)} targets usually spread across several players, so there is no must-add yet; BFF's projections shift them to the other {tm_name(p['t'])} receivers with the next data update (within 3 hours)."))
        elif free: body.append(P_(f"Waiver priority: {free[0]['n']} is the add if he is on your wire; at {f1(proj_wk(free[0], w))} projected points he is a real option in week {w}."))
        elif any(likely_free(q) for q in tm): body.append(P_(f"Nobody behind {ln} projects as a must-add: the work likely spreads out, so check BFF's waiver list for the week's best options instead."))
        else: body.append(P_(f"The {tm_name(p['t'])} depth behind {ln} is mostly rostered, so look for help elsewhere on waivers."))
    else:
        body.append(P_(f"The {tm_name(p['t'])} have no clear replacement at {p['p']} in BFF's data, so expect a committee."))
    if p['p'] in ('WR', 'TE'):
        qb = qb_of(p['t'])
        # his season points per game, not the rest-of-season projection, which drops to zero once he is ruled out
        ts = p.get('ts') or 0; top = max((q.get('fpg') or 0 for q in P if q['t'] == p['t'] and q['p'] in ('WR', 'TE') and q['id'] != p['id'] and (q.get('g') or 0) >= 3), default=0)
        best = (p.get('g') or 0) >= 3 and (p.get('fpg') or 0) > top
        if qb and (ts >= .18 or best):   # only when he really is a top target
            body.append(P_(f"For {qb['n']}, losing " + (f"a receiver who draws {round(ts * 100)}% of the targets" if ts >= .18 else "his best receiver") + " lowers the ceiling"
                           + ("." if stale else "; BFF's projections already shift those targets to the receivers still active.")))
    body.append(H_('What to do'))
    body.append(UL([{'season': f"In redraft leagues {ln} can go to an IR slot if your league has one, or be dropped for a player who can help this year; in dynasty leagues, hold him for next season.",
                     'ir': f"Move {ln} to an IR slot if your league has one; do not drop him unless you need the roster spot for a starter.",
                     'out': f"Start someone else in week {w}; {ln} keeps his rest-of-season value.", 'doubtful': f"Plan to start someone else in week {w} and check the inactive list 90 minutes before kickoff.",
                     'traded': "Wait for his new role before moving him; trade values update after the next data run.", 'released': "He is droppable in most leagues until he signs somewhere."}[kind],
                    "BFF's projections, rankings and trade values already reflect this, or will after the next data update (every 3 hours)."]))
    dek = f"{what}. Who benefits on the {tm_name(p['t'])}, waiver moves and what to do with your lineup."
    src = ([{'s': ev['src'], 'u': ev['url']}] if ev.get('url') else []) + [{'s': 'BFF projections and depth charts (nflverse)', 'u': ''}]
    art = dict(kind='breaking', title=title, dek=dek, body=body, players=uniq([p] + tm), teams=[p['t']], wk=w, img={'k': 'player', 'pid': p['id']}, src=src)
    if ev.get('nh'): art['nh'] = ev['nh']   # the report it came from, so a later check can still read it after it leaves the news feed
    return art, None


def write_reinstate(p, ev, key, kind):
    """a player away from his team on a reserve list who applies for (or gets) reinstatement: BFF's data only (his last
    game, his last season as a regular), what has to happen before he can play, and what to do"""
    n = p['n']; ln = last(n); a = p.get('away') or {}; tm = tm_name(p['t']); src = ev.get('src') or 'news reports'
    title = pick([f"{n} applies for reinstatement: what it means for fantasy", f"{n} seeks a return: the fantasy outlook"] if kind == 'reinstate'
                 else [f"{n} reinstated: what it means for fantasy", f"{n} is back: the fantasy outlook"], key)
    body = [P_((f"{n} has applied for reinstatement, according to {src}. He is on a reserve list, away from the {tm}, so he can't play until the league reinstates him and a team has him on its roster."
                if kind == 'reinstate' else f"{n} has been reinstated, according to {src}. He still has to be on a team's active roster to play; the {tm} hold his rights and can keep, trade or release him."))]
    L = ([f"{ln} last played in week {a['last'][1]} of the {a['last'][0]} season."] if a.get('last') else []) + \
        ([f"In {a['y']}, his last season as a fantasy regular, he averaged {f1(a['ppg'])} PPR points over {cnt(a['g'], 'game')}."] if a.get('y') else [])
    if L: body.append(P_(' '.join(L)))
    body.append(H_('What it means for fantasy'))
    body.append(UL([("BFF projects him for 0 until a team has him on its active roster; then his projection, ranking and trade value come back with the next data update (every 3 hours)."
                     if kind == 'reinstate' else "Once he is on a team's active roster, BFF projects him again with the next data update (every 3 hours)."),
                    "Redraft leagues: he is a stash only if you have an open bench spot" + (f"; he has not played since {a['last'][0]} and has no role on a team yet." if a.get('last') else "; he has no role on a team yet."),
                    "Dynasty leagues: hold him if you have him; his value depends on where he plays next."]))
    dek = f"{n} {'has applied for reinstatement' if kind == 'reinstate' else 'has been reinstated'}. What has to happen before he can play, and what to do with him in your league."
    src_ = ([{'s': ev['src'], 'u': ev['url']}] if ev.get('url') else []) + [{'s': 'BFF data (nflverse)', 'u': ''}]
    art = dict(kind='breaking', title=title, dek=dek, body=body, players=[p['id']], teams=[p['t']], wk=p.get('nw') or D['asof']['next_week'], img={'k': 'player', 'pid': p['id']}, src=src_)
    if ev.get('nh'): art['nh'] = ev['nh']
    return art, None


SEASON_RE = re.compile(r"\b(out for (the )?((rest|remainder) of (the )?)?(season|year)|season[- ]ending|(miss|misses|missing|sit out) (the )?((rest|remainder) of (the )?)?(season|year)(?!\s*(opener|finale|debut))|done for the (season|year))\b", re.I)
DIAG_RE = re.compile(r"\b(with|after|due to|suffers|suffered|has) (an? )?((torn|broken|fractured|ruptured|dislocated|separated|sprained|high[- ]ankle|lisfranc|acl|mcl|achilles)[^,.;:!?]{0,40})", re.I)
def breaking_events():
    """fresh, fantasy-relevant news: official injury report and transactions (data run), and headlines (every 30 minutes)"""
    E = []
    # fantasy-relevant: a top-150 player by BFF's rest-of-season numbers, or a real role; a backup quarterback is news only as the starter
    rel = lambda p: p and (ovr_rank(p) <= 150 or (p['p'] == 'QB' and (p.get('role') == 'QB1' or p.get('qbs')))
                           or (p['p'] != 'QB' and ((p.get('rl') or 0) >= 9 or p.get('role') in ('RB1', 'WR1', 'WR2', 'TE1'))))
    def kicked(p):   # his next game has started: "ruled out" for it is no longer news
        x = next((y for y in (D.get('sched') or {}).get(p['t']) or [] if y[0] == p.get('nw') and len(y) > 5 and y[5]), None)
        return bool(x and pdt(x[5]) and pdt(x[5]) <= NOW)
    def stale(p, at):   # a "ruled out" from during one of his games (or the 8 hours after its kickoff), or from before a game
        # that has since kicked off, was about that game ("ruled out with a foot injury against the Dolphins")
        if not at: return False
        for y in (D.get('sched') or {}).get(p['t']) or []:
            k_ = pdt(y[5]) if len(y) > 5 and y[5] else None
            if k_ and at - datetime.timedelta(hours=8) <= k_ <= NOW: return True
        return False
    built = min(NOW, pdt(D['asof'].get('built') + 'T12:00:00+00:00')) if D['asof'].get('built') else NOW
    nw = D['asof'].get('next_week')
    for d in D.get('news') or []:
        p = PI.get(d.get('id'))
        if not rel(p): continue
        x = d.get('x') or ''; m_ = re.search(r'week (\d+)', f"{d.get('d') or ''} {x}")
        # an injury report is about one game: only the report for the player's next game is news (a week 6 "Out" is
        # history once his week 6 game is over); roster moves count from the current week on
        if d['k'] == 'inj' and (not m_ or int(m_.group(1)) != p.get('nw') or kicked(p)): continue
        if m_ and int(m_.group(1)) not in (nw, p.get('nw')): continue   # last week's report is not news
        if d['k'] == 'ir': E.append(dict(p=p, kind='activated' if re.search(r'activat', x, re.I) else 'ir', why=None, src='official roster data (nflverse)', at=pdt(d.get('d')) or built))
        elif d['k'] == 'inj' and d.get('st') in ('Out', 'Doubtful'):
            m = re.search(r'\(([^)]+)\)', x); E.append(dict(p=p, kind=d['st'].lower(), why=m.group(1) if m else None, src='the official injury report', at=pdt(d.get('d')) or built))
        elif d['k'] == 'move' and re.search(r'\btrade', x, re.I): E.append(dict(p=p, kind='traded', why=None, src='official roster data (nflverse)', at=pdt(d.get('d')) or built))
        elif d['k'] == 'move' and re.search(r'releas|waiv|cut', x, re.I): E.append(dict(p=p, kind='released', why=None, src='official roster data (nflverse)', at=pdt(d.get('d')) or built))
    for h in NEWS.get('items') or []:
        if h.get('st') not in ('out', 'doubtful'): continue
        hl = h.get('h', '')
        if INGAME_RE.search(hl) and not re.search(r'season', hl, re.I): continue   # hurt during a game: not a status for the next one
        if SPEC_RE.search(hl) or NOTOUT_RE.search(hl): continue   # "could miss the season": wait for the confirmation
        nh = {k: h[k] for k in ('h', 'd', 's', 'u', 'p', 'so', 'sd', 'sk') if k in h}   # the report, kept with the story
        # only the player the "out" is about ("Saquon Barkley set to play, DeVonta Smith ruled out": Smith); "doubtful" is
        # its own status ("Emeka Egbuka considered doubtful": not ruled out)
        if 'so' in h: who = [(pid, 'out') for pid in h.get('so') or []] + [(pid, 'doubtful') for pid in h.get('sd') or []]
        else: who = [(h['p'][0], 'out')] if len(h.get('p') or []) == 1 and h.get('st') == 'out' else []
        for pid, st_ in who:
            p = PI.get(pid)
            if rel(p) and not kicked(p):
                k = 'doubtful' if st_ == 'doubtful' else 'season' if SEASON_RE.search(hl) else 'ir' if re.search(r'\b(ir|injured reserve)\b', hl, re.I) else 'out'
                if k in ('out', 'doubtful'):
                    if stale(p, pdt(h.get('d'))): continue   # about a game already played (or in progress), not his next one
                    mw = re.search(r'\bweek (\d+)', hl, re.I)
                    if mw and int(mw.group(1)) != p.get('nw'): continue   # "ruled out against the Dolphins in week 7": not his next game
                dx = DIAG_RE.search(hl)
                E.append(dict(p=p, kind=k, why=dx.group(3).strip() if dx else None, src=h.get('s') or 'news reports', url=h.get('u') or '', at=pdt(h.get('d')) or NOW, nh=nh))
    # a player away from his team on a reserve list (no roster, projected 0) who applies for or gets reinstatement (Nov
    # 2026: Brandon Aiyuk); matched by his full name, since the headline tags only know players with a projection
    for p in [q for q in P if q.get('rsv') == 'away']:
        rx = re.compile(r'(?<![\w])' + re.escape(p['n']) + r'(?![\w])', re.I)
        for h in NEWS.get('items') or []:
            hl = h.get('h', '')
            if not rx.search(hl) or NOTREIN_RE.search(hl): continue
            k = 'reinstated' if REINSTATED_RE.search(hl) else 'reinstate' if REINAPP_RE.search(hl) else None
            if k: E.append(dict(p=p, kind=k, why=None, src=h.get('s') or 'news reports', url=h.get('u') or '', at=pdt(h.get('d')) or NOW, nh={x: h[x] for x in ('h', 'd', 's', 'u') if x in h}))
    E = [e for e in E if e['at'] and NOW - e['at'] < datetime.timedelta(hours=48)]
    rank = {'season': -1, 'ir': 0, 'reinstated': 0, 'reinstate': 1, 'traded': 1, 'released': 2, 'out': 3, 'doubtful': 4, 'activated': 5}; best = {}
    for e in E:
        pid = e['p']['id']
        if pid not in best or rank[e['kind']] < rank[best[pid]['kind']]: best[pid] = e
    return sorted(best.values(), key=lambda e: -(e['p'].get('rl') or 0))


# ---------------------------------------------------------------- deciding what to publish
# writer version: raise it when a fix to a writer should correct the article still in its window (Tuesday landscape).
# 2: injury statuses are named by their source; a player who just missed time is injury news, not a usage faller;
#    a starter who barely played his last game is flagged as a possible injury (landscape fallers, recap stock down)
#    5: season-ending news is its own kind of breaking story (not "ruled out for week N"), with the diagnosis; recaps
#       note a player since ruled out for the season or placed on injured reserve
#    7: the analyst voice (verdict-first player notes, scoring plays told as sentences, the line explained in words)
WV = 8   # 8: BFF's own data only; verdicts that match the numbers (a low projection beaten is not "paid off"), the second
#          half and the go-ahead score told in words, late-week ranks against the whole week, injuries in BFF's words
def publish(aid, key, made, once=False):
    art, digest = made
    if not art: return False
    old = ARTS.get(aid); now = iso(NOW)
    sig = hashlib.md5(json.dumps([art['title'], art['body']], sort_keys=True).encode()).hexdigest()
    if old and old.get('sig') == sig: return False
    if old and (once or old.get('kind') in ('recap', 'breaking', 'landscape')) and old.get('wv', 1) >= WV: return False   # written once (a writer fix rewrites it in its window)
    notes = list((old or {}).get('notes') or [])
    if old and digest:
        ch = change_notes(old.get('digest'), digest)
        if ch: notes = [[now, 'Updated: ' + '; '.join(ch) + '.']] + notes[:4]
    ARTS[aid] = dict(art, id=aid, key=key, sig=sig, digest=digest, notes=notes, pub=(old or {}).get('pub') or now, upd=now, by='BFF Data Desk', season=SEASON, wv=WV)
    print(('updated' if old else 'published'), aid, '|', ARTS[aid]['title']); return True


def boxed(gs):
    """every game has a box score (live, or the official stats the morning after)"""
    return all(box_rows(g) for g in gs)
SPEC_RE = re.compile(r"\b(could|may|might|if|would|possibly|potentially|considering|weighing|fears?|feared)\b", re.I)   # not confirmed yet
REINAPP_RE = re.compile(r"\b(appl(y|ies|ied)|fil(e|es|ed|ing)|seek(s|ing)?|looking to get|request(s|ed)?|petition(s|ed)?)\b[^.;:]{0,40}\breinstat", re.I)   # applied for reinstatement
REINSTATED_RE = re.compile(r"\b((has been|was|is|gets|got|officially|been)\s+reinstated|reinstated by|(nfl|league) reinstates)\b", re.I)
NOTREIN_RE = re.compile(r"\b(not|n't|never)( yet)?( been)? reinstat|\bwon't (apply|seek)|\bnot (apply|seek)", re.I)   # "NFL has not yet reinstated"
NOTOUT_RE = re.compile(r"\b(not|n't|never)( yet)?( been)? ruled out|\bnot expected to miss", re.I)   # "not ruled out yet" is not ruled out
INGAME_RE = re.compile(r"\b(remainder|rest of (the )?(game|day|contest|half)|won't return|will not return|(questionable|doubtful|unlikely) to return|ruled out (of|for) (the |today's |sunday's |monday's |thursday's )?game)", re.I)   # hurt during a game


def correct_breaking():
    """a breaking story that turned out wrong becomes a correction under the same link: a player "ruled out" for a week he
    then played, "done for the season" before he played again, or (November 2026 checks) a "ruled out" that was about
    another player in the headline, about a game already under way or played, about another week, a "doubtful" told as
    "ruled out", or "out for the season" from a report that only said he could be. The report is read from the news feed,
    or from the copy kept with the story (nh) once it has left the feed."""
    byu = {h.get('u'): h for h in NEWS.get('items') or [] if h.get('u')}; n_ = 0
    for a in ARTS.values():
        if a.get('kind') != 'breaking' or a.get('fix'): continue
        m = re.search(r'brk-(\d{2}-\d{7})-(out|doubtful|season)\b', a.get('key') or '') or re.search(r'brk-(\d{2}-\d{7})-(out|doubtful|season)\b', a.get('id') or '')
        p = PI.get(m.group(1)) if m else None
        if not p: continue
        kind, w, pub = m.group(2), a.get('wk'), pdt(a.get('pub'))
        played = {r[0] for r in p.get('gl') or [] if any(v for v in r[1:])}   # weeks he took the field with a stat
        u = next((x.get('u') for x in a.get('src') or [] if x.get('u')), None)
        h = byu.get(u) or (a.get('nh') if (a.get('nh') or {}).get('u') == u else None)
        hl = (h or {}).get('h') or ''; at = pdt(h.get('d')) if h else None; src = (h or {}).get('s') or 'news'
        why = None; verdict = 'That was wrong'
        said_at = max([t for t in (pub, at) if t], default=None)   # a story rewritten in place for the season news: from its report
        if kind == 'out' and w in played: why = f"{p['n']} played in week {w}"
        elif kind == 'season' and said_at:
            later = [y[0] for y in (D.get('sched') or {}).get(p['t']) or [] if len(y) > 5 and y[5] and pdt(y[5]) and pdt(y[5]) > said_at and y[0] in played]
            if later: why = f"{p['n']} played again in week {later[0]}"
        if not why and kind == 'season' and h and SPEC_RE.search(hl) and 'for the season' not in (p.get('injn') or ''):
            ir = any(b.get('kind') == 'breaking' and str(b.get('key', '')).startswith(f"brk-{p['id']}-ir") for b in ARTS.values())
            why = f"the report it was based on ({src}) said the injury could end his season, which is not a confirmation" + ("; he is headed to injured reserve, which means at least four games" if ir else '')
            verdict = 'That was premature'
        if not why and kind == 'out' and h:
            mw = re.search(r'\bweek (\d+)', hl, re.I)
            g_ = next((y for y in (D.get('sched') or {}).get(p['t']) or [] if at and pub and len(y) > 5 and y[5] and pdt(y[5]) and at - datetime.timedelta(hours=8) <= pdt(y[5]) <= max(pub, at)), None)
            if NOTOUT_RE.search(hl): why = f"the report it was based on ({src}) said {p['n']} had not been ruled out"
            elif 'so' in h and p['id'] not in (h.get('so') or []):
                why = f"the report it was based on ({src}) said {p['n']} was doubtful, not ruled out" if p['id'] in (h.get('sd') or []) else f"the report it was based on ({src}) did not say {p['n']} was out"
            elif mw and int(mw.group(1)) != w: why = f"the report it was based on ({src}) was about week {mw.group(1)}, not week {w}"
            elif g_ and g_[0] != w: why = f"the report it was based on ({src}) was about his week {g_[0]} game against the {tm_name(g_[1])}, not week {w}"
            elif g_ and pdt(g_[5]) <= at or INGAME_RE.search(hl): why = f"the report it was based on ({src}) was about an injury during his week {g_[0] if g_ else w} game, which was already under way"
        if not why: continue
        said = f"had been ruled out for week {w}" if kind == 'out' else f"was doubtful for week {w}" if kind == 'doubtful' else 'was out for the season'
        a.update(title=f"Correction: {poss(p['n'])} {'status' if kind == 'season' else f'week {w} status'}", dek=f"An earlier version of this story said {p['n']} {said}. {verdict}.",
                 body=[['p', f"An earlier version of this story said {p['n']} {said}. {verdict}: {why}."],
                       ['p', f"For {poss(p['n'])} current status, see his player card, which follows the official injury report. BFF's breaking-news check now ties a status to the player the headline names and to the game it is about, and waits for confirmation when a report only says what could happen."]],
                 fix=1, upd=iso(NOW), notes=[[iso(NOW), 'Corrected: the original story was wrong (see above).' if verdict == 'That was wrong' else 'Corrected: the original story went further than its source (see above).']] + list(a.get('notes') or [])[:4])
        print('corrected', a['id'], '|', why); n_ += 1
    return n_


def run():
    made = correct_breaking()
    # games around now, grouped by day (Eastern)
    near = [g for g in GAMES if -datetime.timedelta(days=4) < g['kick'] - NOW < datetime.timedelta(days=8)]
    by_day = {}
    for g in near: by_day.setdefault(gday(g), []).append(g)
    for day, gs in sorted(by_day.items()):
        w = gs[0]['wk']; wd = day.weekday(); dname = DOW[wd].lower()[:3]; first = min(g['kick'] for g in gs); pre = [g for g in gs if g['state'] == 'pre' or g['kick'] > NOW]   # (a game cannot be over before its kickoff: keeps time-travel runs honest)
        if wd == 6:   # Sunday: Saturday-morning outlook; afternoon recap before the night game; night recap
            opens = at_et(day - datetime.timedelta(days=1), 8)
            if opens <= NOW < first and pre: aid = f"{SEASON}-w{w}-sun-outlook"; made += publish(aid, aid, write_sunday_outlook(gs, aid))
            aft = [g for g in gs if ghour(g) < 19]; night = [g for g in gs if ghour(g) >= 19]
            if aft and all(g['state'] == 'post' for g in aft) and NOW > max(g['kick'] for g in aft) + datetime.timedelta(hours=3):
                aid = f"{SEASON}-w{w}-sun-recap"; late_ok = NOW >= at_et(day + datetime.timedelta(days=1), 10)
                if aid not in ARTS and (boxed(aft) or late_ok) and NOW - max(g['kick'] for g in aft) < datetime.timedelta(days=3):
                    made += publish(aid, aid, write_window_recap(aft, aid, f"Week {w} Sunday", [g for g in night if g['state'] != 'post' or g['kick'] > NOW]), once=True)
            if night and all(g['state'] == 'post' for g in night) and NOW > max(g['kick'] for g in night) + datetime.timedelta(hours=3):
                aid = f"{SEASON}-w{w}-snf-recap"
                if aid not in ARTS and (boxed(night) or NOW >= at_et(day + datetime.timedelta(days=1), 10)) and NOW - max(g['kick'] for g in night) < datetime.timedelta(days=3):
                    made += publish(aid, aid, write_recap(night, aid, 'Sunday night'), once=True)
            continue
        # Thursday, Monday and other days: an outlook that morning (8 AM, or 10 hours before an early kickoff)
        opens = min(at_et(day, 8), first - datetime.timedelta(hours=10))
        label = {'thu': 'Thursday', 'mon': 'Monday', 'fri': 'Friday', 'sat': 'Saturday', 'tue': 'Tuesday', 'wed': 'Wednesday'}[dname]
        if day.month == 12 and day.day == 25: label = 'Christmas'
        if opens <= NOW < first and pre: aid = f"{SEASON}-w{w}-{dname}-outlook"; made += publish(aid, aid, write_outlook(gs, aid, label))
        # recap: right after the final for Monday (and the night it ends), the next morning at 7 for Thursday and other days
        if all(g['state'] == 'post' for g in gs) and datetime.timedelta(hours=3) < NOW - max(g['kick'] for g in gs) < datetime.timedelta(days=3):
            aid = f"{SEASON}-w{w}-{dname}-recap"; ready = NOW >= at_et(day + datetime.timedelta(days=1), 7) if wd != 0 else True
            if (aid not in ARTS or ARTS[aid].get('wv', 1) < WV) and ready and (boxed(gs) or NOW >= at_et(day + datetime.timedelta(days=1), 10)):
                made += publish(aid, aid, write_recap(gs, aid, label), once=True)
    # Friday 5 PM injury report for the coming Sunday (updated until Sunday's first kickoff)
    for day, gs in sorted(by_day.items()):
        if day.weekday() != 6: continue
        w = gs[0]['wk']; opens = at_et(day - datetime.timedelta(days=2), 17); first = min(g['kick'] for g in gs)
        if opens <= NOW < first: aid = f"{SEASON}-w{w}-injuries"; made += publish(aid, aid, write_injury_report(w, [g for g in near if g['wk'] == w and g['state'] == 'pre'], aid))
    # Tuesday 10 AM landscape once every game of the week is final (written once)
    for w in sorted({g['wk'] for g in near}):
        wg = [g for g in GAMES if g['wk'] == w]
        if not wg or not all(g['state'] == 'post' for g in wg) or NOW < max(g['kick'] for g in wg): continue
        endday = max(gday(g) for g in wg); tue = endday + datetime.timedelta(days=(1 - endday.weekday()) % 7 or 7)
        if at_et(tue, 10) <= NOW < at_et(tue, 10) + datetime.timedelta(days=2):
            aid = f"{SEASON}-w{w}-landscape"
            if aid not in ARTS or ARTS[aid].get('wv', 1) < WV: made += publish(aid, aid, write_landscape(w, aid), once=True)
    # breaking news
    today = [a for a in ARTS.values() if a.get('kind') == 'breaking' and pdt(a.get('pub')) and NOW - pdt(a['pub']) < datetime.timedelta(hours=24)]
    room = min(MAX_BRK_RUN, MAX_BRK_DAY - len(today)); done = set(); cur = set()
    first_run = 'seen' not in OLD or OLD.get('bv') != BV   # a new file, or news keys from an older version: learn what is known, publish nothing
    for e in breaking_events():
        k = f"brk-{e['p']['id']}-{e['kind']}" + (f"-w{e['p'].get('nw')}" if e['kind'] in ('out', 'doubtful') else ''); cur.add(k)   # ruled out again next week is new news
        if k not in SEEN: SEEN[k] = iso(NOW - datetime.timedelta(days=1) if first_run else NOW)   # learned on a first run = already known
        # only news first seen in the last 6 hours becomes an article (the first run just learns what is already known)
        if first_run or room <= 0 or NOW - pdt(SEEN[k]) > datetime.timedelta(hours=6): continue
        recent = [a for a in ARTS.values() if a.get('key') == k and pdt(a.get('pub')) and NOW - pdt(a['pub']) < datetime.timedelta(days=6)]
        if recent or k in done: continue
        done.add(k); aid = f"{SEASON}-{k}-{NOW.strftime('%m%d')}"
        if e['kind'] == 'season':
            prior = [a for a in ARTS.values() if a.get('kind') == 'breaking' and str(a.get('key', '')).startswith(f"brk-{e['p']['id']}-out") and pdt(a.get('pub')) and NOW - pdt(a['pub']) < datetime.timedelta(days=6)]
            if prior: aid = prior[0]['id']; ARTS[aid]['wv'] = 0; ARTS[aid]['key'] = k   # replace it in place (same link, corrected story)
        if publish(aid, k, write_breaking(e['p'], e, aid)): room -= 1; made += 1
    # keep three weeks
    keep = {i: a for i, a in ARTS.items() if pdt(a.get('upd')) and NOW - pdt(a['upd']) < datetime.timedelta(days=KEEP_DAYS)}
    items = sorted(keep.values(), key=lambda a: a['upd'], reverse=True)
    seen = {k: v for k, v in SEEN.items() if k in cur or (pdt(v) and NOW - pdt(v) < datetime.timedelta(days=14))}
    new = {'season': SEASON, 'at': iso(NOW) if made else OLD.get('at', iso(NOW)), 'bv': BV, 'items': items, 'seen': seen}
    if made or len(items) != len(OLD.get('items') or []) or seen != OLD.get('seen') or OLD.get('ai_log') or OLD.get('bv') != BV or not os.path.exists(OUT):
        json.dump(new, open(OUT, 'w'), separators=(',', ':')); print(f'articles: {made} new or updated, {len(items)} kept')
    else: print('articles: nothing new')


if __name__ == '__main__':
    try: run()
    except Exception:   # never break the live job
        import traceback; traceback.print_exc(); print('articles: skipped this run'); sys.exit(0)
