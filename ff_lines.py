#!/usr/bin/env python3
"""Predicted prop lines for BFF: what PrizePicks, Underdog and sportsbooks are expected to post this week.

MARKET LINES (refit Oct 25 2026 on 2 samples of real week-7 lines, research/bt_lines.py): books' lines track the public
projections. Every line is set from the average of ESPN's and Sleeper's projection for that stat (site_stats.py,
refreshed every 10 minutes), put through a rule fit to real posted lines:
  receiving yards 0.916 x the market; receptions 0.975 x + 0.15; rushing yards 0.843 x the market + 0.112 x his season
  average - 3.5; passing yards 0.404 x the market + 0.250 x his season average + 0.218 x the market x (Vegas implied
  team total / 22 - 1) + 75.5 (books lean on what a player has done and on the game's total; second refit, Oct 25
  evening); rounded down to .5; passing touchdowns 0.5 below a market projection of 0.95, 2.5 from 2.3, else 1.5 (books
  post 0.5 for low-scoring passers such as Cam Ward, Daniel Jones or Malik Willis).
Scored on players each fit did not use, against the books' lines read Sunday Oct 25 (scoresandodds.com): average gap
3.3 receiving yards (the books themselves spread 3.3 apart), 3.8 rushing yards (books 2.8; was 4.6), 0.25 receptions
(books 0.38; was 0.29), 7.8 passing yards (books 7.2; was 11.1); passing-TD lines match 26 of 28 real lines (was 21 of
25). On the earlier sample (Oct 21-23 lines), each player scored by a fit that left him out: passing 5.6 (was 8.6),
rushing 4.3 (was 4.9).
BFF's own model stays out of the line, so the picks can test it.
PICKS: an under on receiving yards when BFF's own model projects the player at least 10% below ESPN and Sleeper. In
2025, at lines built this way, those unders hit 57.2% (719 picks; every yardage under 54.2%). Passing-yard unders were
picks at the first refit's lines but hit only 52.6% at these closer-to-the-books lines, and rushing-yard unders 52.8%, so
neither is a pick; overs where BFF was higher hit 46.1%. Receptions and passing TDs get no picks: books price those
unders well above even money (often -150 to -200), so a high chance there is not an edge. Each pick says how far below
our line it still holds (2025: 4.5%), because a real book's line can sit lower than ours. "Chance" for every line is how often the over hit in 2025 for
that stat and that gap between BFF and the sites; passing TDs: the books' expected touchdowns read from real odds
(0.578 + 0.676 x the market), scaled to match 2025 for that gap, through a Poisson count. A player neither site projects
gets the model's line (below).

MORE PROPS (Oct 26 2026, research/bt_props_more.py; no picks on any of these):
  pass attempts (quarterbacks): the market projection, its whole number + .5; completions: projected attempts x his
  completion rate (this season and last season at half weight, shrunk 100 attempts toward the league's 64.5%), whole
  number + .5; rush attempts 1.003 x - 0.259; targets 1.025 x (books rarely post targets: set where 2025's overs hit as
  often as receptions'). Against week 7's real lines (scoresandodds.com, Oct 25), every rule scored on players it never
  saw: pass attempts 1.08 from the books' (books 1.25 apart, 24 passers), completions 0.84 (books 0.61, 28), rush
  attempts 0.95 (books 0.48, 82). No side of these hit 55% in both 2025 and 2026, so no picks.
  Interceptions (chance of 1+): projected attempts x his interception rate (this season, last season at 0.66, shrunk
  2,489 attempts toward the league's 2.17%) x 0.963, as a Poisson count; within 3 points of the books' no-vig price on
  average (26 passers, week 7). Anytime TD (rushing, receiving or a return): projected carries and targets at each
  position's touchdown rate x (Vegas implied team total / 22)^1.11 x his own touchdowns per opportunity (this season and
  last, shrunk), fit on 2025 by Poisson likelihood; in 2026 games it never saw it expected 23.9% of players to score and
  22.4% did (2025: 23.4% and 23.4%). First-half TD: the same rate x the share of that position's touchdowns scored
  before halftime (2024-2025: QB 48.4%, RB 47.2%, WR 50.5%, TE 45.5%). This season's touchdowns come from the game logs
  (rushing + receiving; returns are about 1% of skill players' touchdowns), last season's from nflverse (returns too).

MODEL LINES (the fallback when neither site projects a player) are built the way books build them, from OPPORTUNITY:
  expected volume (targets, carries or pass attempts; recent games count more, last season counts like 1-3 games,
  injury-shortened games are left out) x the player's efficiency (catch rate, yards per target / carry / attempt,
  touchdowns per attempt; shrunk toward the position average) x this game (Vegas implied team total, the defense).
Volume freed up by injured teammates is added for receiving yards. A player coming off an injury-shortened game is
marked down (in testing those players hit their overs only 25-33% of the time). Lines end in .5.

Settings were tuned on 2024 and tested on every 2025 game they had never seen: overs hit 44-50% for every stat, and
they stay balanced for players whose role rose or fell, rookies, players returning from partial games, and at every line
height (very high or low projections are pulled back toward typical, as books do).

Model lines carry a chance (our projection against the line, blended 50/50 with the line and kept within 38-62%) but
no picks since Oct 25 2026: they were tested against model lines, not lines like the books', and the few players on them
are the ones the books are least likely to price the same way.

Two ways to run:
  python ff_lines.py            data job: reads ff_data.json + last season's stats, writes bet_inputs.json, lines.json
                                and the lines into ff_data.json
  python ff_lines.py --refresh  score job (every 10 minutes): reads bet_inputs.json + live.json (current ESPN odds)
                                and rewrites lines.json only when a line or pick actually changed
Every line keeps its opening value and each move with its reason (Vegas total, teammate news, injury status).
"""
import json, math, os, re, sys, datetime

REFRESH = '--refresh' in sys.argv
PULLED = {}
NOW = datetime.datetime.fromisoformat(os.environ['BFF_NOW']) if os.environ.get('BFF_NOW') else datetime.datetime.now(datetime.timezone.utc)
STAMP = NOW.isoformat(timespec='minutes')

# ---- settings tuned on 2024, tested on 2025 (see the docstring)
# d: recency decay per game, Wv: last season's weight in games, pw: last season's weight in efficiency, k: shrinkage toward the
# position average, a: Vegas exponent, b: defense exponent, kb: injured-teammate volume, pp: after a partial game, nf: no last season,
# c: sets the line at the typical game (books' lines sit below the average for skewed stats), sh: pulls unusual projections back toward the
# typical player at the position (passing yards: the highest and lowest lines were too extreme without it)
PAR = {'rec': dict(d=.75, Wv=2, pw=.5, k=30, a=0, b=.25, kb=0, pp=.7, nf=1, c=.8989),
       'ty': dict(d=.9, Wv=2, pw=.5, k=10, a=.25, b=0, kb=.5, pp=.7, nf=1, c=0.8410, sh=.9),
       'ry': dict(d=.9, Wv=1, pw=.5, k=80, a=.5, b=.25, kb=0, pp=.7, nf=.9, c=.9178),
       'ryq': dict(d=.9, Wv=2, pw=.5, k=80, a=.5, b=.25, kb=0, pp=1, nf=1, c=.813),
       'py': dict(d=.6, Wv=3, pw=.5, k=30, a=.25, b=0, kb=0, pp=1, nf=1, c=0.9565, sh=.7),
       'ptd': dict(d=.5, Wv=2, pw=.5, k=30, a=.25, b=0, kb=0, pp=1, nf=1, c=1.0345)}
VOL = {'rec': 'tg', 'ty': 'tg', 'ry': 'car', 'ryq': 'car', 'py': 'att', 'ptd': 'att'}
EFF = {'rec': ('rec', 'tg'), 'ty': ('ty', 'tg'), 'ry': ('ry', 'car'), 'ryq': ('ry', 'car'), 'py': ('py', 'att'), 'ptd': ('ptd', 'att')}
GLI = {'att': 2, 'py': 3, 'ptd': 4, 'car': 6, 'ry': 7, 'rec': 9, 'tg': 10, 'ty': 11}       # columns of a game-log row
PICK_MIN = .55   # the pick bar the page quotes (market picks: 2025 hit rates above it)
# market lines (see the docstring; every number below is research/results_lines.json, checked by tests/linetest.py)
MKR = {'py': {'a': .404, 'c': .2502, 'd': .2181, 'b': 75.536}, 'ty': {'k': .9163}, 'ry': {'a': .8433, 'c': .1115, 'b': -3.476}, 'rec': {'a': .9746, 'b': .154}}   # 'rule'
MKR['ryq'] = MKR['ry']
def mkt_line(k, mk, sa=None, it=None):
    """a market line: k x market, or a x market + c x season average + d x market x (implied total / 22 - 1) + b,
    rounded down to .5 (no season average: the market's projection; no total: 22)"""
    R_ = MKR[k]; sa = mk if sa is None else sa; it = 22.0 if it is None else it
    v = R_['k'] * mk if 'k' in R_ else R_['a'] * mk + R_.get('c', 0) * sa + R_.get('d', 0) * mk * (it / 22 - 1) + R_['b']
    return max(.5, math.floor(v) + .5)
PTD = {'t1': .95, 't2': 2.3, 'a': .578, 'b': .676, 'scale': {'below': .873, 'level': 1.094, 'above': 1.094}}   # 'above': no 2025 QBs; level's
MKMIN = {'py': 150, 'ty': 15, 'ry': 7, 'ryq': 10, 'rec': 1.5}   # the smallest market projection that gets a line (books post down to about these)
OVR = {'py': {'below': .474, 'level': .505, 'above': .505}, 'ty': {'below': .428, 'level': .436, 'above': .459},
       'ry': {'below': .472, 'level': .486, 'above': .491}, 'rec': {'below': .392, 'level': .415, 'above': .449}}   # 2025: share of overs that hit ('above' py: none in 2025, level's)
MK_PICKS = {'ty'}                       # unders when BFF is 10%+ below the sites
HOLD = {'ty': .045}                     # an under pick still holds (55%+ in 2025) down to this far below our line
BT_MKT = {'source': "real week-7 2026 lines: a public props page (Oct 21-23) and scoresandodds.com on Sunday Oct 25 (each player's lowest and highest line across books)",
          'gap': {'py': 7.8, 'ty': 3.3, 'ry': 3.8, 'rec': .25}, 'gap_was': {'py': 11.1, 'ty': 3.3, 'ry': 4.6, 'rec': .29}, 'books': {'py': 7.2, 'ty': 3.3, 'ry': 2.8, 'rec': .38},
          'ptd': {'n': 28, 'match': 26, 'was': [21, 25]}, 'over_2025': {'py': 48.6, 'ty': 43.5, 'ry': 48.5, 'rec': 41.4, 'ptd': 46.3},
          'picks': {'n': 719, 'won': .572, 'by': {'ty': .572}, 'py': .526, 'ry': .528, 'every_under': .542, 'overs': .461}, 'hold': HOLD}
BT = {'season': 2025, 'tuned_on': 2024,
      'lines': {'rec': {'n': 2159, 'mae': 1.67, 'over': 46.8}, 'ty': {'n': 2159, 'mae': 21.9, 'over': 44.4}, 'ry': {'n': 658, 'mae': 26.4, 'over': 49.1},
                'ryq': {'n': 293, 'mae': 13.7, 'over': 50.2}, 'py': {'n': 487, 'mae': 64.5, 'over': 50.0}, 'ptd': {'n': 502, 'mae': 1.00, 'over': 47.2}},
      'picks': {'thr': .55, 'n': 1080, 'won': .596, 'by': {'ptd': .582, 'py': .597, 'rec': .603, 'ry': .538}, 'ty': .46}}
# ---- more markets (Oct 25 2026, research/bt_props_more.py; every number below is research/results_props_more.json, checked by
# tests/linetest.py). Count lines from ESPN's and Sleeper's projections through rules fit to real week-7 lines: pass attempts
# and completions at the projection (completions = projected attempts x his completion rate, shrunk 100 attempts toward the
# league's 64.5% with last season at half weight), rush attempts 1.003 x - 0.26; targets 1.025 x (books rarely post them, so
# set where 2025's overs hit like receptions'). Interceptions and touchdowns are yes/no: a rate per game from the models
# below, fit on 2025 and checked on 2026, shown as a chance and fair odds. None of these get picks (not tested for picks).
XR = {'patt': {'k': 1.0}, 'cmp': {'k': 1.0}, 'car': {'a': 1.003, 'b': -.259}, 'tg': {'k': 1.025}}
XMIN = {'patt': 20, 'cmp': 12, 'car': 2, 'tg': 2.5}            # the smallest projection that gets a line (as in the research)
XOVR = {'patt': {'below': .399, 'level': .444, 'above': .43}, 'cmp': {'below': .412, 'level': .486, 'above': .452},
        'car': {'below': .447, 'level': .436, 'above': .471}, 'tg': {'below': .392, 'level': .423, 'above': .475}}   # 2025+2026 overs ('above' with under 50 games: the market's overall rate)
LGR = {'int': .0217, 'cmp': .6452}                               # 2025: league interceptions and completions per attempt
INTM = {'W': 2488.6, 'pw': .66, 'sc': .963}                      # interception rate shrunk W attempts toward the league's; last season at pw; scale
TDP = [-3.0998, -3.37307, -49.94285, -67.02841, 2.23176, -3.88697, -3.01219, -2.80436, 1.10994, 3.94566, 76.04215]   # the touchdown model (research 'par')
TDPOS = {'QB': 0, 'RB': 1, 'WR': 2, 'TE': 3}
H1 = {'QB': .484, 'RB': .472, 'WR': .505, 'TE': .455}             # share of each position's touchdowns scored in the first half (2024-2025)
BT_MORE = {'lg': LGR, 'int_sc': INTM['sc'], 'gap': {'patt': 1.08, 'cmp': .84, 'car': .95}, 'books': {'patt': 1.25, 'cmp': .61, 'car': .48}, 'n': {'patt': 24, 'cmp': 28, 'car': 82},
           'int_books': {'n': 26, 'gap': .03}, 'td': {'2026': {'predicted': .239, 'actual': .224}, '2025': {'predicted': .234, 'actual': .234}}}
def td_rate(pos, car, tg, it, c_car, c_tg, c_td, p_car, p_tg, p_td, parts=False):
    """expected touchdowns (rushing, receiving, returns) this game: projected carries and targets at the position's
    touchdown rates, the Vegas implied team total, and his own touchdowns per opportunity (this season and last), shrunk
    (parts=True also returns the three factors the page shows: volume at league rates, team total, his own rate)"""
    i = TDPOS[pos]; ac, at = math.exp(TDP[i]), math.exp(TDP[4 + i])
    gam, W, pw = TDP[8], math.exp(TDP[9]), 1 / (1 + math.exp(-TDP[10]))
    exp0 = ac * (car or 0) + (0.0 if pos == 'QB' else at * (tg or 0))   # quarterbacks: projected targets left out (both sites projected
    # none in all 651 tested games, and the fitted quarterback target rate only describes his history below; it is no rate for a real target)
    e_c = ac * (c_car + pw * p_car) + at * (c_tg + pw * p_tg)
    own = (c_td + pw * p_td + W) / (e_c + W); vf = ((it or 22.0) / 22) ** gam
    return (exp0 * vf * own, exp0, vf, own) if parts else exp0 * vf * own
def int_rate(c_int, c_att, p_int, p_att):
    return (c_int + INTM['pw'] * p_int + LGR['int'] * INTM['W']) / (c_att + INTM['pw'] * p_att + INTM['W'])
def cmp_rate(c_cmp, c_att, p_cmp, p_att):
    return (c_cmp + .5 * p_cmp + LGR['cmp'] * 100) / (c_att + .5 * p_att + 100)
def x_line(k, mk):
    R_ = XR[k]; return max(.5, math.floor(R_['k'] * mk if 'k' in R_ else R_['a'] * mk + R_['b']) + .5)
TEAMFIX = {'WSH': 'WAS', 'LAR': 'LA', 'JAC': 'JAX'}
LV = 3   # line rules version: lines from an older version reopen instead of counting as moves (2 = the Oct 25 2026 refit, 3 = its evening refit)

def pover(lam, line):
    """chance of more than `line` (a .5 line) when the count arrives at rate lam (Poisson)"""
    lam = max(float(lam), .01); return 1 - sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(int(line) + 1))

def cdf(q, x):
    if x < q[0]: return max(0, .05 * (1 - (q[0] - x) / (max(q[1] - q[0], .05) * 3)))
    if x >= q[18]: return min(1, .95 + .05 * (x - q[18]) / (max(q[18] - q[17], .05) * 3))
    for i in range(18):
        if x < q[i + 1]: d = q[i + 1] - q[i]; return (i + 1 + ((x - q[i]) / d if d > 0 else 0)) / 20
    return .95
QK = lambda pos, k: {'py': 'pass_yds', 'ptd': 'pass_td', 'ry': 'rush_yds_qb' if pos == 'QB' else 'rush_yds', 'ryq': 'rush_yds_qb',
                     'ty': 'rec_yds_rb' if pos == 'RB' else 'rec_yds', 'rec': 'rec_rb' if pos == 'RB' else 'rec'}[k]

# ------------------------------------------------------------------ inputs
def build_inputs():
    """Data job: everything the lines need, in one compact file the 10-minute job can reuse."""
    import pandas as pd
    D = json.load(open('ff_data.json')); P = D['players']; NW = D['asof']['next_week']; SEASON = D['asof'].get('season') or NOW.year
    SCHED = D.get('sched', {})
    left = {tm for tm, L in SCHED.items() for x in L if x[0] == NW and x[4] is None}
    FW = NW + 1 if len(left) / 2 <= 2 and NW < 18 else NW
    pri, mu = {}, {}
    f = f'stats_player_week_{SEASON - 1}.parquet'
    if os.path.exists(f):
        s = pd.read_parquet(f); s = s[(s.season_type == 'REG') & s.position.isin(['QB', 'RB', 'WR', 'TE'])].copy()
        for c in ['attempts', 'passing_yards', 'passing_tds', 'carries', 'rushing_yards', 'receptions', 'targets', 'receiving_yards']: s[c] = s[c].fillna(0)
        s = s[(s.position != 'QB') | (s.attempts >= 15)]                                  # partial quarterback games left out
        g = s.groupby('player_id').agg(n=('week', 'size'), fp=('fantasy_points_ppr', 'mean'), tg=('targets', 'sum'), rec=('receptions', 'sum'), ty=('receiving_yards', 'sum'),
                                       car=('carries', 'sum'), ry=('rushing_yards', 'sum'), att=('attempts', 'sum'), py=('passing_yards', 'sum'), ptd=('passing_tds', 'sum'))
        g = g[g.n >= 3]
        pri = {pid: {k: round(float(v), 2) for k, v in r.items()} for pid, r in g.iterrows()}
        s2 = pd.read_parquet(f); s2 = s2[(s2.season_type == 'REG') & s2.position.isin(['QB', 'RB', 'WR', 'TE'])].copy()   # every game (the new markets' priors)
        for c in ['attempts', 'completions', 'passing_interceptions', 'carries', 'targets', 'rushing_tds', 'receiving_tds', 'special_teams_tds']: s2[c] = s2[c].fillna(0)
        s2['td'] = s2.rushing_tds + s2.receiving_tds + s2.special_teams_tds
        pv_all = {pid: {k: int(v) for k, v in r.items()} for pid, r in s2.groupby('player_id')[['attempts', 'completions', 'passing_interceptions', 'carries', 'targets', 'td']].sum().iterrows()}
        pos_of = s.drop_duplicates('player_id').set_index('player_id').position
        for q in ['QB', 'RB', 'WR', 'TE']:
            X = g[g.index.isin(pos_of[pos_of == q].index)]
            mu[q] = {k: round(float(v), 4) for k, v in {'rec': X.rec.sum() / max(1, X.tg.sum()), 'ty': X.ty.sum() / max(1, X.tg.sum()), 'ry': X.ry.sum() / max(1, X.car.sum()),
                     'py': X.py.sum() / max(1, X.att.sum()), 'ptd': X.ptd.sum() / max(1, X.att.sum())}.items()}
    else:
        print(f'{f} not found: lines use this season only'); pv_all = {}
    if not mu:   # league-typical efficiency if last season's file is missing
        mu = {'QB': {'rec': 1, 'ty': 1.6, 'ry': 4.6, 'py': 6.9, 'ptd': .045}, 'RB': {'rec': .78, 'ty': 5.6, 'ry': 4.3, 'py': 7, 'ptd': .04},
              'WR': {'rec': .64, 'ty': 8.1, 'ry': 6, 'py': 7, 'ptd': .04}, 'TE': {'rec': .72, 'ty': 7.4, 'ry': 4, 'py': 7, 'ptd': .04}}
    keep = ('id', 'n', 'p', 't', 'opp', 'nw', 'proj', 'inj', 'prac', 'fpg', 'g', 'gl', 'wk', 'role', 'bmp', 'home', 'sid', 'eid', 'pe', 'ps')
    players = []
    for p in P:
        if p['p'] not in ('QB', 'RB', 'WR', 'TE'): continue
        q = {k: p.get(k) for k in keep}
        q['ros'] = [x for x in (p.get('ros') or []) if x[0] in (NW, FW)]
        q['pri'] = pri.get(p['id']); q['pv'] = pv_all.get(p['id'])
        if p.get('nw') == NW and p.get('proj') is not None: q['mo'] = round(float(p['proj']) - float(p.get('adjc') or 0), 2)   # BFF's model alone, before the stack
        players.append(q)
    I = {'asof': D['asof'], 'fw': FW, 'nw': NW, 'sched': SCHED, 'dvp': D.get('dvp', {}), 'mu': mu, 'players': players}
    json.dump(I, open('bet_inputs.json', 'w'), separators=(',', ':'))
    return I, D

# ------------------------------------------------------------------ Vegas: ESPN's current odds when posted, else the schedule's
def espn_totals(I, wk=None):
    """Implied team totals from ESPN's current odds (live.json, refreshed every 10 minutes): over/under and spread."""
    out = {}
    try: L = json.load(open('live.json'))
    except Exception: return out
    if int(L.get('week') or 0) != (wk or I['fw']): return out
    for g in L.get('games') or []:
        ou, det = g.get('ou'), g.get('odds') or ''
        if g.get('state') != 'pre' or not ou: continue
        try: ou = float(ou)
        except (TypeError, ValueError): continue
        m = re.match(r'\s*([A-Z]{2,4})\s*([-+]?\d+(?:\.\d+)?)', det)
        fav, sp = (TEAMFIX.get(m.group(1), m.group(1)), abs(float(m.group(2)))) if m else (None, 0.0)
        for tm in (g['home'], g['away']):
            out[tm] = round(ou / 2 + (sp / 2 if tm == fav else -sp / 2 if fav else 0), 2)
    return out

# ------------------------------------------------------------------ lines
def wkproj(p, FW):
    if p.get('inj') in ('Out', 'IR', 'Doubtful'): return 0.0
    if p['nw'] == FW: return float(p.get('proj') or 0)
    r = next((x for x in p.get('ros') or [] if x[0] == FW), None); return float(r[2]) if r else 0.0

def news_status(I):
    """Latest clear news status per player since his last game: 'out' (ruled out, expected to miss time, placed on IR...)
    pulls his lines, as books do; a later 'cleared' / 'will play' report restores them."""
    try: N = json.load(open('news.json')).get('items') or []
    except Exception: return {}
    last = {}
    for p in I['players']:
        G = [r[0] for r in (p.get('gl') or [])]
        k = next((x[5] for x in I['sched'].get(p['t'], []) if G and x[0] == max(G) and len(x) > 5 and x[5]), None)
        last[p['id']] = k
    st = {}
    for it in sorted(N, key=lambda x: x.get('d') or ''):
        if it.get('st') not in ('out', 'ok'): continue
        for pid in it.get('p') or []:
            since = last.get(pid) or (NOW - datetime.timedelta(days=6)).isoformat()
            if (it.get('d') or '') >= since: st[pid] = (it['st'], it['h'], it.get('s'))
    return {pid: v for pid, v in st.items() if v[0] == 'out'}

def site_week(I, wk):
    """ESPN's and Sleeper's stat projections for week wk (site_stats.py): {gsis id: {'e': {...}, 's': {...}}}"""
    try: S = json.load(open('site_stats.json'))
    except Exception: return {}
    if int(S.get('season') or 0) != int((I.get('asof') or {}).get('season') or 0): return {}
    return (S.get('weeks') or {}).get(str(wk)) or {}

def market(site, k):
    """the market's projection for stat k: the average of ESPN's and Sleeper's (either alone if only one projects him)"""
    xs = [d[k] for d in ((site or {}).get('e'), (site or {}).get('s')) if d and (d.get(k) or 0) > 0]
    return sum(xs) / len(xs) if xs else None

def gap_bin(p, site):
    """BFF's own model vs ESPN and Sleeper (fantasy points this week): below (10%+ lower), level or above (10%+ higher)"""
    fp = [d['fp'] for d in ((site or {}).get('e'), (site or {}).get('s')) if d and (d.get('fp') or 0) > 0]
    if not fp: fp = [v for v in (p.get('pe'), p.get('ps')) if v]
    mo = p.get('mo')
    if len(fp) < 2 or not mo: return 'level', None
    r = mo / (sum(fp) / len(fp))
    return ('below' if r < .9 else 'above' if r > 1.1 else 'level'), round(r, 3)

def build_lines(I, wk=None, teams=None):
    """lines for week wk (default: the coming fantasy week); teams limits them to some teams (this week's late games)"""
    FW, SCHED, DVP, MU = wk or I['fw'], I['sched'], I['dvp'], I['mu']
    QS = json.load(open('prop_qs.json')); ESPN = espn_totals(I, FW); global PULLED; PULLED = news_status(I); SITE = site_week(I, FW)
    sch = lambda tm: next((x for x in SCHED.get(tm, []) if x[0] == FW), None)
    rows = []
    for p in I['players']:
        pos = p['p']; e = sch(p['t']); wp = wkproj(p, FW)
        if teams is not None and p['t'] not in teams: continue
        if not e or not e[1] or p['nw'] > FW or wp < (10 if pos == 'QB' else 4): continue   # Monday-night teams still get next week's lines
        if p['id'] in PULLED: continue                                                              # news says he will miss the game
        G = [r for r in (p.get('gl') or []) if r[0] < FW]
        snap = {w[0]: w[3] for w in (p.get('wk') or []) if w[3] is not None}
        med = sorted(snap.values())[len(snap) // 2] if snap else None
        def partial(r):
            if pos == 'QB': return r[2] < 15
            s_ = snap.get(r[0]); return bool(med and s_ is not None and s_ < .5 * med)
        F = [r for r in G if not partial(r)]; pr = p.get('pri')
        if not F and not pr: continue
        last_part = bool(G and partial(G[-1]))
        if pos == 'QB' and not (p.get('role') == 'QB1' or (G and not last_part)): continue          # books post QB lines for starters
        it_sched = e[3] if e[3] is not None else 22.5; it = ESPN.get(p['t'], it_sched); dv = ((DVP.get(e[1]) or {}).get(pos) or [None, None, 1.0])[2] or 1.0
        bmp = next((b for w, b in (p.get('bmp') or []) if w == FW), 0.0) or 0.0
        rows.append(dict(p=p, pos=pos, F=F, G=G, pr=pr, last_part=last_part, it=it, it_src='ESPN' if p['t'] in ESPN else 'schedule', dv=dv, bmp=bmp, opp=e[1],
                         kick=e[5] if len(e) > 5 else None, wp=wp, site=SITE.get(p['id'])))

    def volume(r, v, d, Wv):
        h = [x[GLI[v]] for x in r['F']]; n = len(h)
        ws = sum(x * d ** (n - 1 - i) for i, x in enumerate(h)); wn = sum(d ** (n - 1 - i) for i in range(n))
        pr = r['pr']; pv = pr[v] / pr['n'] if pr else None
        if pv is not None: return (ws + Wv * pv) / (wn + Wv)
        return ws / wn if wn else None
    def mean_for(r, k):
        P_ = PAR[k]; v = VOL[k]; num, den = EFF[k]; pos = r['pos']
        vol = volume(r, v, P_['d'], P_['Wv'])
        if vol is None: return None
        if P_['kb'] and r['bmp']: vol += P_['kb'] * r['bmp'] / (0.75 if v == 'car' else 1.4 if pos == 'RB' else 1.75) * (1 if (pos == 'RB') == (v == 'car') else .5)
        pr = r['pr'] or {}; cs_n = sum(x[GLI[num]] for x in r['F']); cs_d = sum(x[GLI[den]] for x in r['F'])
        eff = (cs_n + P_['pw'] * pr.get(num, 0) + P_['k'] * MU[pos][num]) / (cs_d + P_['pw'] * pr.get(den, 0) + P_['k'])
        ctx = max(.85, min(1.15, (r['it'] / 22.5) ** P_['a'] * r['dv'] ** P_['b']))
        m = vol * eff * ctx
        if r['last_part']: m *= P_['pp']
        if not r['pr']: m *= P_['nf']
        return m, vol, eff

    # our projection relative to a book-style fantasy baseline, centered by position (the pick signal)
    for r in rows:
        n = len(r['F']); fpg = r['p'].get('fpg'); prf = (r['pr'] or {}).get('fp')
        fpb = (fpg * n + prf * 3) / (n + 3) if (fpg is not None and n and prf is not None) else (fpg if (fpg is not None and n) else prf)
        r['s'] = r['wp'] / max(fpb, 4) if fpb else None
    S = {}
    for r in rows:
        if r['s']: S.setdefault(r['pos'], []).append(r['s'])
    MED = {q: sorted(v)[len(v) // 2] for q, v in S.items()}
    allm = {}
    for r in rows:
        for k in ('py', 'ty'):
            res = mean_for(r, k)
            if res: allm.setdefault((k, r['pos']), []).append(res[0])
    CEN = {key: sorted(v)[len(v) // 2] for key, v in allm.items() if len(v) >= 5}
    qb_done = set(); lines = []
    for r in sorted(rows, key=lambda r: -r['wp']):
        pos, p = r['pos'], r['p']
        if pos == 'QB':
            if p['t'] in qb_done: continue                                                       # one starting QB per team
            qb_done.add(p['t'])
        vtg = volume(r, 'tg', .75, 2) or 0; vcar = volume(r, 'car', .75, 2) or 0
        sn = max(.8, min(1.25, r['s'] / MED[pos])) if r['s'] and MED.get(pos) else 1.0
        mk_ = lambda k: market(r['site'], 'ry' if k == 'ryq' else k)
        has = lambda k: (mk_(k) or 0) >= MKMIN[k]
        stats = ['py', 'ptd', 'ryq'] if pos == 'QB' else (['ry'] if pos == 'RB' and (vcar >= 8 or has('ry')) else []) + \
            (['rec', 'ty'] if vtg >= (2.5 if pos == 'RB' else 3.5) or has('ty') else [])
        gb, gr = gap_bin(p, r['site'])
        for k in stats:
            res = mean_for(r, k)
            if not res: continue
            m, vol, eff = res
            mk = mk_(k)
            if k == 'ryq':
                base_ry = (sum(x[7] for x in r['F']) + (r['pr'] or {}).get('ry', 0)) / max(1, len(r['F']) + (r['pr'] or {}).get('n', 0))
                if base_ry < 12 and not has('ryq'): continue
            mm = None; hold = None; sa = None
            if PAR[k].get('sh') and CEN.get((k, pos)) is not None: m = CEN[(k, pos)] + PAR[k]['sh'] * (m - CEN[(k, pos)])
            kk = 'ry' if k == 'ryq' else k
            if mk is not None and mk > 0:   # market line: where books are expected to set it
                if k == 'ptd':
                    line = .5 if mk < PTD['t1'] else 2.5 if mk >= PTD['t2'] else 1.5
                    mm = (PTD['a'] + PTD['b'] * mk) * PTD['scale'][gb]                 # expected touchdowns
                    po = pover(mm, line); pick = False
                else:
                    sa = sum(x[GLI[kk]] for x in r['G']) / len(r['G']) if r['G'] else None   # his season average (every game this season before this week)
                    line = mkt_line(k, mk, sa, r['it'])
                    if k == 'py' and line < 150.5: continue
                    mm = mk * (max(.5, min(1.5, gr)) if gr else 1.0)                 # the sites' projection, scaled by BFF's model vs theirs
                    po = OVR[kk][gb]; pick = bool(k in MK_PICKS and gb == 'below')
                    if pick: hold = math.floor(line * (1 - HOLD[k])) + .5
                src = 'mkt'
            else:                           # model line (neither site projects him): a chance, no pick
                raw = m * PAR[k]['c']
                line = (.5 if m < .70 else 1.5 if m < 2.55 else 2.5) if k == 'ptd' else math.floor(raw) + .5   # passing-TD cutoffs tuned on 2024
                if k == 'py' and line < 150.5: continue
                mm = m * (sn if k == 'ptd' else 1 + (sn - 1) * .7)
                if k == 'ptd': pm = pover(mm, line)
                else: pm = 1 - cdf(QS[QK(pos, k)], (line + 1e-4) / max(mm, .05))
                po = min(.62, max(.38, .5 * pm + .25)); pick = False
                src = 'bff'
            lines.append({'pid': p['id'], 'wk': FW, 't': p['t'], 'opp': r['opp'], 'k': kk, 'line': line, 'mm': round(float(mm), 2), 'po': round(float(po), 3),
                          'pick': pick, 'hold': hold, 'v': LV, 'kick': r['kick'], 'q': bool(p.get('inj') == 'Questionable'), 'src': src, 'mk': round(float(mk), 2 if k == 'ptd' else 1) if src == 'mkt' else None,
                          'gap': gr if src == 'mkt' else None, 'sa': round(float(sa), 1) if src == 'mkt' and k in ('py', 'ry', 'ryq') and sa is not None else None,
                          'vol': round(float(vol), 1), 'eff': round(float(eff), 3), 'it': round(float(r['it']), 2), 'its': r['it_src'], 'bmp': round(float(r['bmp']), 1), 'pp': bool(r['last_part'])})
        lines += more_lines(r, FW, gb, gr)
    return lines

def more_lines(r, FW, gb, gr):
    """the newer markets (pass attempts, completions, interceptions, rush attempts, targets, anytime and first-half TD):
    from ESPN's and Sleeper's projections only, no picks (research/bt_props_more.py)"""
    p, pos, G, pv = r['p'], r['pos'], r['G'], r['p'].get('pv') or {}
    mk = lambda k: market(r['site'], k)
    c = lambda i: sum(x[i] for x in G)                       # this season before this week (every game he played)
    base = {'pid': p['id'], 'wk': FW, 't': p['t'], 'opp': r['opp'], 'v': LV, 'kick': r['kick'], 'q': bool(p.get('inj') == 'Questionable'), 'src': 'mkt',
            'gap': gr, 'it': round(float(r['it']), 2), 'its': r['it_src']}            # no 'pick' (never a pick), kept small: the page carries every line
    out = []
    def add(k, line, mm, po, m_, x):
        yn = k in ('int', 'td', 'td1')                                     # yes/no: expected counts to 3 decimals, so the page's sums check out
        out.append(dict(base, k=k, line=line, mm=round(float(mm), 3 if yn else 2), po=round(float(po), 3), mk=round(float(m_), 3 if yn else 1), x=x))
    pa, car, tg = mk('patt'), mk('car') or 0, mk('tg') or 0
    if pos == 'QB' and pa and pa >= XMIN['patt']:
        add('patt', x_line('patt', pa), pa, XOVR['patt'][gb], pa, None)
        cr = cmp_rate(c(1), c(2), pv.get('completions', 0), pv.get('attempts', 0)); cm = pa * cr
        if cm >= XMIN['cmp']: add('cmp', x_line('cmp', cm), cm, XOVR['cmp'][gb], cm, {'pa': round(pa, 2), 'cr': round(cr, 4)})
        ir = int_rate(c(5), c(2), pv.get('passing_interceptions', 0), pv.get('attempts', 0)); li = INTM['sc'] * pa * ir
        add('int', .5, li, 1 - math.exp(-li), li, {'pa': round(pa, 2), 'ir': round(ir, 5)})
    if car >= XMIN['car']: add('car', x_line('car', car), car, XOVR['car'][gb], car, None)
    if pos != 'QB' and tg >= XMIN['tg']: add('tg', x_line('tg', tg), tg, XOVR['tg'][gb], tg, None)
    if car + (0 if pos == 'QB' else tg) >= 1.5:
        lt, b0, vf, own = td_rate(pos, car, tg, r['it'], c(6), c(10), c(8) + c(12), pv.get('carries', 0), pv.get('targets', 0), pv.get('td', 0), parts=True)
        x = {'car': round(car, 1), 'tg': round(tg, 1) if pos != 'QB' else 0, 'b': round(b0, 4), 'vf': round(vf, 4), 'own': round(own, 4)}
        add('td', .5, lt, 1 - math.exp(-lt), lt, x)
        add('td1', .5, lt * H1[pos], 1 - math.exp(-lt * H1[pos]), lt, dict(x, h1=H1[pos]))
    return out

# ------------------------------------------------------------------ history: opening line and every move, with the reason
def why(old, new):
    R = []
    if old.get('mk') and new.get('mk') and abs(new['mk'] - old['mk']) >= (.1 if new.get('k') == 'ptd' else max(1, .03 * old['mk'])): R.append(f"ESPN and Sleeper projections {old['mk']} → {new['mk']}")
    if old.get('src') != new.get('src') and new.get('src'): R.append('set from ESPN and Sleeper' if new['src'] == 'mkt' else 'set from BFF\'s model (sites not projecting him)')
    if abs((old.get('it') or 0) - (new.get('it') or 0)) >= .5: R.append(f"Vegas team total {old.get('it')} → {new.get('it')}")
    if abs((old.get('bmp') or 0) - (new.get('bmp') or 0)) >= .3: R.append('teammate injury news' if (new.get('bmp') or 0) > (old.get('bmp') or 0) else 'teammate returning')
    if old.get('q') != new.get('q'): R.append('listed questionable' if new.get('q') else 'off the injury report')
    if abs((old.get('vol') or 0) - (new.get('vol') or 0)) >= .3 and not R: R.append('new game data')
    return '; '.join(R) or 'updated projections'

def _dt(s):
    try:
        d = datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')); return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
    except Exception: return None

def merge_history(new_lines, fw):
    old = {}
    try:
        O = json.load(open('lines.json'))
        if O.get('wk') == fw: old = O
    except Exception: pass
    key = lambda l: (l['pid'], l['k'], l.get('wk', fw))
    prev = {key(l): l for l in old.get('lines') or []}
    moves = list(old.get('moves') or [])
    for l in new_lines:
        o = prev.get(key(l))
        if o and o.get('v') != LV: o = None   # a line from older rules (before the Oct 25 2026 refit): it reopens rather than counting as a move
        if not o:
            l['open'] = l['line']; l['opened'] = STAMP; l['mv'] = []
            continue
        l['open'], l['opened'], l['mv'] = o.get('open', o['line']), o.get('opened', old.get('at', STAMP)), list(o.get('mv') or [])
        if l['line'] != o['line']:
            w = why(o, l); l['mv'].append([STAMP, o['line'], l['line'], w])
            moves.append({'pid': l['pid'], 'k': l['k'], 'from': o['line'], 'to': l['line'], 'at': STAMP, 'why': w})
    now_keys = {key(l) for l in new_lines}
    for kk_ in [k_ for k_ in prev if k_ not in now_keys]:
        pid, k, wk_ = kk_; o_ = prev[kk_]
        if o_.get('kick') and _dt(o_['kick']) and _dt(o_['kick']) <= NOW: continue   # the game started: not a pulled line
        if o_.get('v') != LV: continue   # a line from older rules: not a pulled line
        n_ = PULLED.get(pid); w_ = f"pulled: {n_[1]} ({n_[2]})" if n_ else 'line pulled (injury report or role change)'
        moves.append({'pid': pid, 'k': k, 'from': o_['line'], 'to': None, 'at': STAMP, 'why': w_})
    sig = lambda L: sorted((l['pid'], l['k'], l['line'], round(l['po'], 2), l['q'], round(l.get('it') or 0, 2)) for l in L)   # the team total shows with each line
    changed = (not old) or sig(new_lines) != sig(old.get('lines') or [])
    out = {'wk': fw, 'at': STAMP if changed else old.get('at', STAMP), 'odds_from': None, 'bt': BT, 'mkt': BT_MKT, 'more': BT_MORE, 'lines': new_lines, 'moves': moves[-60:],
           'pulled': [{'pid': k, 'h': v[1], 's': v[2]} for k, v in PULLED.items()]}
    return out, changed

if __name__ == '__main__':
    if REFRESH:
        if not os.path.exists('bet_inputs.json'): print('bet_inputs.json not found yet (the data job makes it); skipping'); sys.exit(0)
        I = json.load(open('bet_inputs.json')); D = None
    else:
        I, D = build_inputs()
    a_ = I.get('asof') or {}
    if a_.get('phase') == 'preseason' and a_.get('sched') is False:   # offseason before the schedule: no games to price
        L = []; print('the schedule is not out yet: no prop lines this run')
    else:
        try:
            L = build_lines(I)
            # this week's games still to play (a Monday-night game while next week's lines are already up)
            if I.get('nw') and I['nw'] != I['fw']:
                late = {tm for tm, S in I['sched'].items() for x in S if x[0] == I['nw'] and x[1] and x[4] is None and len(x) > 5 and _dt(x[5]) and _dt(x[5]) > NOW}
                if late: L = build_lines(I, I['nw'], late) + L
        except Exception as ex:   # never break the job: keep the previous lines
            print('could not rebuild lines, keeping the previous ones:', ex); sys.exit(0)
    out, changed = merge_history(L, I['fw'])
    out['odds_from'] = 'ESPN (current odds)' if any(l['its'] == 'ESPN' for l in L) else 'nflverse schedule (opening odds)'
    if changed or not os.path.exists('lines.json'):
        json.dump(out, open('lines.json', 'w'), separators=(',', ':'))
    if D is not None:
        D['lines'] = out; json.dump(D, open('ff_data.json', 'w'), separators=(',', ':'))
    mv = sum(1 for m in out['moves'] if m['at'] == STAMP)
    print(f"lines: {len(L)} for week {I['fw']}{' and this week' + chr(39) + 's late games' if any(l.get('wk') != I['fw'] for l in L) else ''} ({sum(bool(l.get('pick')) for l in L)} picks at {int(PICK_MIN*100)}%+), {mv} moved this run, odds from {out['odds_from']}"
          + ('' if changed else ' (no change)'))
