#!/usr/bin/env python3
"""Predicted prop lines for BFF: where PrizePicks, Underdog and sportsbooks are expected to post this week, from BFF's own
numbers only (no other site's projections or odds; nflverse stats and the nflverse schedule's Vegas lines).

THE LINES are built the way books build them, from OPPORTUNITY:
  expected volume (targets, carries or pass attempts; recent games count more, last season counts like 1-3 games,
  injury-shortened games are left out) x the player's efficiency (catch rate, yards per target / carry / attempt,
  touchdowns per attempt; shrunk toward the position average) x this game (Vegas implied team total, the defense).
Volume freed up by injured teammates is added for receiving yards. A player coming off an injury-shortened game is
marked down (in testing those players hit their overs only 25-33% of the time). Lines end in .5.
Settings were tuned on 2024 and tested on every 2025 game they had never seen: overs hit 44-50% for every stat, and
they stay balanced for players whose role rose or fell, rookies, players returning from partial games, and at every line
height (very high or low projections are pulled back toward typical, as books do).
Passing yards take one more step, fit to real posted lines (research/bt_lines_bff.py, Nov 2026): 0.374 x the model line
+ 0.261 x his season average + 0.252 x the model line x (implied team total / 22 - 1) + 81.3 (books lean on what a
passer has done and on the game's total). On players the fit never saw it cut the average gap to the books' week-7
lines from 13.3 to 8.2 yards (sample A) and from 10.2 to 8.3 (sample B). The same step did not help receiving yards,
rushing yards or receptions on both samples, so those keep the model line (week 7, sample B: 3.2, 4.5 and 0.32 from the
books, whose own lines spread 3.3, 3.1 and 0.41 apart).
"Chance" for every line: our expected value against the line (through the spread of real outcomes around projections
like it), blended 50/50 with the line and kept within 38-62%. No picks: BFF has no market line to test its view against.

MORE PROPS (research/bt_props_bff.py, Nov 2026; no picks):
  pass attempts 0.386 x BFF's expected attempts + 20.3; completions 0.458 x (expected attempts x his completion rate,
  this season and last at half weight, shrunk 100 attempts toward the league's 64.5%) + 11.3; rush attempts at BFF's
  expected carries; targets 0.975 x expected targets (books rarely post targets: set where 2025's overs hit as often as
  receptions'). Against week 7's real lines, every rule scored on players it never saw: pass attempts 1.48 from the
  books' (books 1.12 apart, 24 passers), completions 1.02 (books 0.54, 28), rush attempts 1.57 (books 0.52, 75). Overs
  hit 42.2%, 45.8%, 41.1% and 42.3% at these lines in 2025-2026 (the chance each shows).
  Interceptions (chance of 1+): expected attempts x his interception rate (this season, last season at 0.66, shrunk
  2,489 attempts toward the league's 2.17%) x 0.979, as a Poisson count (2026, never seen in the fit: 48.6% expected,
  49.0% happened). Anytime TD (rushing, receiving or a return): expected carries and targets at each position's
  touchdown rate x (Vegas implied team total / 22)^1.11 x his own touchdowns per opportunity (this season and last,
  shrunk) x 0.962 (2026, never seen: 22.1% of players expected to score, 21.5% did). First-half TD: the same rate x the
  share of that position's touchdowns scored before halftime (2024-2025: QB 48.4%, RB 47.2%, WR 50.5%, TE 45.5%).

Two ways to run:
  python ff_lines.py            data job: reads ff_data.json + last season's stats, writes bet_inputs.json, lines.json
                                and the lines into ff_data.json
  python ff_lines.py --refresh  score job: reads bet_inputs.json + news.json and rewrites lines.json only when a line
                                actually changed (a player ruled out in the news pulls his lines, as books do)
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
PYR = {'a': 0.1459, 'c': 0.2713, 'd': 0.4071, 'b': 130.705}   # passing yards: second step on BFF's model line (research/bt_lines_bff.py, Nov 2026)
def py_line(base, sa, it):
    """passing yards: the model line through the rule fit to real lines (no season average yet: the model line; no total: 22)"""
    sa = base if sa is None else sa; it = 22.0 if it is None else it
    return max(.5, math.floor(PYR['a'] * base + PYR['c'] * sa + PYR['d'] * base * (it / 22 - 1) + PYR['b']) + .5)
TYR = {'k': 1.1093}   # receiving yards: books post them about 11% above BFF's model line (research/bt_lines_bff.py, Nov 2026)
def ty_line(base):
    return max(.5, math.floor(TYR['k'] * base) + .5)
BT_BFF = {'source': "real week-7 2026 lines: a public props page (Oct 21-23, one book) and scoresandodds.com on Sunday Oct 25 (each player's lowest and highest line across books), against BFF's own model lines (research/bt_lines_bff.py)",
          'gap': {'py': [7.43, 9.2], 'ty': [4.96, 5.72], 'ry': [9.06, 8.16], 'rec': [None, 0.6]}, 'books': {'py': 6.96, 'ty': 3.21, 'ry': 3.58, 'rec': 0.4},
          'n': {'py': [15, 25], 'ty': [51, 71], 'ry': [31, 40], 'rec': [0, 70]}, 'ptd': {'n': 25, 'match': 21}, 'pyr': PYR, 'tyr': TYR,
          'market': {'py': [5.59, 7.77], 'ty': [3.14, 3.26], 'ry': [4.3, 3.78], 'rec': [None, 0.25]}}   # the market rule (ESPN + Sleeper, until Nov 2026), players left out
BT = {'season': 2025, 'tuned_on': 2024,
      'lines': {'rec': {'n': 2159, 'mae': 1.67, 'over': 46.8}, 'ty': {'n': 2159, 'mae': 21.9, 'over': 44.4}, 'ry': {'n': 658, 'mae': 26.4, 'over': 49.1},
                'ryq': {'n': 293, 'mae': 13.7, 'over': 50.2}, 'py': {'n': 487, 'mae': 64.5, 'over': 50.0}, 'ptd': {'n': 502, 'mae': 1.00, 'over': 47.2}},
}
# ---- more markets (research/bt_props_bff.py; every number below is research/results_props_bff.json, checked by
# tests/linetest.py): count lines from BFF's own expected volume through rules fit to real week-7 lines; interceptions
# and touchdowns are yes/no: a rate per game, shown as a chance and fair odds. None of these get picks.
XR = {'patt': {'a': .3856, 'b': 20.2569}, 'cmp': {'a': .4581, 'b': 11.2687}, 'car': {'k': 1.0}, 'tg': {'k': .975}}
XMIN = {'patt': 20, 'cmp': 12, 'car': 2, 'tg': 2.5}            # the smallest expected volume that gets a line (as in the research)
XOVR = {'patt': .422, 'cmp': .458, 'car': .411, 'tg': .423}    # 2025+2026: how often the over hit at these lines
LGR = {'int': .0217, 'cmp': .6452}                               # 2025: league interceptions and completions per attempt
INTM = {'W': 2488.6, 'pw': .66, 'sc': .979}                      # interception rate shrunk W attempts toward the league's; last season at pw; scale
TDP = [-3.0998, -3.37307, -49.94285, -67.02841, 2.23176, -3.88697, -3.01219, -2.80436, 1.10994, 3.94566, 76.04215]   # the touchdown model (research 'par')
TDPOS = {'QB': 0, 'RB': 1, 'WR': 2, 'TE': 3}
H1 = {'QB': .484, 'RB': .472, 'WR': .505, 'TE': .455}             # share of each position's touchdowns scored in the first half (2024-2025)
TDS = .962                                                        # the touchdown rate's scale on BFF's own volume (fit on 2025)
BT_MORE = {'lg': LGR, 'int_sc': INTM['sc'], 'td_sc': TDS, 'gap': {'patt': 1.48, 'cmp': 1.02, 'car': 1.57}, 'books': {'patt': 1.12, 'cmp': .54, 'car': .52}, 'n': {'patt': 24, 'cmp': 28, 'car': 75},
           'over': XOVR, 'xr': XR, 'int': {'2026': {'predicted': .489, 'actual': .508}, '2025': {'predicted': .486, 'actual': .497}},
           'td': {'2026': {'predicted': .222, 'actual': .224}, '2025': {'predicted': .222, 'actual': .22}}}   # research/results_props_bff.json (with_refit)
def td_rate(pos, car, tg, it, c_car, c_tg, c_td, p_car, p_tg, p_td, parts=False):
    """expected touchdowns (rushing, receiving, returns) this game: projected carries and targets at the position's
    touchdown rates, the Vegas implied team total, and his own touchdowns per opportunity (this season and last), shrunk
    (parts=True also returns the three factors the page shows: volume at league rates, team total, his own rate)"""
    i = TDPOS[pos]; ac, at = math.exp(TDP[i]), math.exp(TDP[4 + i])   # (x TDS, the scale for BFF's own volume)
    gam, W, pw = TDP[8], math.exp(TDP[9]), 1 / (1 + math.exp(-TDP[10]))
    exp0 = ac * (car or 0) + (0.0 if pos == 'QB' else at * (tg or 0))   # quarterbacks: targets left out (the fitted quarterback target
    # rate only describes his history below; it is no rate for a real target)
    e_c = ac * (c_car + pw * p_car) + at * (c_tg + pw * p_tg)
    own = (c_td + pw * p_td + W) / (e_c + W); vf = ((it or 22.0) / 22) ** gam
    return (TDS * exp0 * vf * own, exp0, vf, own) if parts else TDS * exp0 * vf * own
def int_rate(c_int, c_att, p_int, p_att):
    return (c_int + INTM['pw'] * p_int + LGR['int'] * INTM['W']) / (c_att + INTM['pw'] * p_att + INTM['W'])
def cmp_rate(c_cmp, c_att, p_cmp, p_att):
    return (c_cmp + .5 * p_cmp + LGR['cmp'] * 100) / (c_att + .5 * p_att + 100)
def x_line(k, mk):
    R_ = XR[k]; return max(.5, math.floor(R_['k'] * mk if 'k' in R_ else R_['a'] * mk + R_['b']) + .5)
TEAMFIX = {'WSH': 'WAS', 'LAR': 'LA', 'JAC': 'JAX'}
LV = 5   # line rules version: lines from an older version reopen instead of counting as moves (4 = BFF's own numbers only, Nov 2026; 5 = the corrected passing- and receiving-yard steps)

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
    keep = ('id', 'n', 'p', 't', 'opp', 'nw', 'proj', 'inj', 'prac', 'fpg', 'g', 'gl', 'wk', 'role', 'bmp', 'home')
    players = []
    for p in P:
        if p['p'] not in ('QB', 'RB', 'WR', 'TE'): continue
        q = {k: p.get(k) for k in keep}
        q['ros'] = [x for x in (p.get('ros') or []) if x[0] in (NW, FW)]
        q['pri'] = pri.get(p['id']); q['pv'] = pv_all.get(p['id'])
        players.append(q)
    I = {'asof': D['asof'], 'fw': FW, 'nw': NW, 'sched': SCHED, 'dvp': D.get('dvp', {}), 'mu': mu, 'players': players}
    json.dump(I, open('bet_inputs.json', 'w'), separators=(',', ':'))
    return I, D

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
        if it.get('st') not in ('out', 'doubtful', 'ok') or INGAME.search(it.get('h') or ''): continue
        # doubtful (most doubtful players sit) pulls his lines too, until a report says he is playing
        tag = [(pid, 'out') for pid in (it.get('so') or []) + (it.get('sd') or [])] + [(pid, 'ok') for pid in it.get('sk') or []]
        if 'so' not in it and 'sk' not in it and len(it.get('p') or []) == 1: tag = [(it['p'][0], it['st'])]   # tagged before Nov 2026
        for pid, s_ in tag:
            # news from his last game or the 8 hours after its kickoff is about that game ("ruled out with an ankle injury
            # against the Cardinals"), not the next one
            k = last.get(pid)
            since = (datetime.datetime.fromisoformat(k) + datetime.timedelta(hours=8)).astimezone(datetime.timezone.utc).isoformat(timespec='seconds') if k else (NOW - datetime.timedelta(days=6)).isoformat()
            if (it.get('d') or '') >= since: st[pid] = (s_, it['h'], it.get('s'))
    return {pid: v for pid, v in st.items() if v[0] == 'out'}

INGAME = re.compile(r"\b(remainder|rest of (the )?(game|day|contest|half)|won't return|will not return|(questionable|doubtful|unlikely) to return|ruled out (of|for) (the |today's |sunday's |monday's |thursday's )?game)", re.I)


def build_lines(I, wk=None, teams=None):
    """lines for week wk (default: the coming fantasy week); teams limits them to some teams (this week's late games)"""
    FW, SCHED, DVP, MU = wk or I['fw'], I['sched'], I['dvp'], I['mu']
    QS = json.load(open('prop_qs.json')); global PULLED; PULLED = news_status(I)
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
        it = e[3] if e[3] is not None else 22.5; dv = ((DVP.get(e[1]) or {}).get(pos) or [None, None, 1.0])[2] or 1.0
        bmp = next((b for w, b in (p.get('bmp') or []) if w == FW), 0.0) or 0.0
        rows.append(dict(p=p, pos=pos, F=F, G=G, pr=pr, last_part=last_part, it=it, dv=dv, bmp=bmp, opp=e[1], kick=e[5] if len(e) > 5 else None, wp=wp))

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

    # our projection relative to a book-style fantasy baseline, centered by position (BFF's matchup and form view: it moves the
    # expected value and the chance, not the line)
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
        stats = ['py', 'ptd', 'ryq'] if pos == 'QB' else (['ry'] if pos == 'RB' and vcar >= 8 else []) + (['rec', 'ty'] if vtg >= (2.5 if pos == 'RB' else 3.5) else [])
        for k in stats:
            res = mean_for(r, k)
            if not res: continue
            m, vol, eff = res
            if k == 'ryq':
                base_ry = (sum(x[7] for x in r['F']) + (r['pr'] or {}).get('ry', 0)) / max(1, len(r['F']) + (r['pr'] or {}).get('n', 0))
                if base_ry < 12: continue
            if PAR[k].get('sh') and CEN.get((k, pos)) is not None: m = CEN[(k, pos)] + PAR[k]['sh'] * (m - CEN[(k, pos)])
            kk = 'ry' if k == 'ryq' else k
            raw = m * PAR[k]['c']
            line = (.5 if m < .70 else 1.5 if m < 2.55 else 2.5) if k == 'ptd' else math.floor(raw) + .5   # passing-TD cutoffs tuned on 2024
            sa = base = None
            if k == 'py':
                if line < 150.5: continue
                sa = sum(x[GLI['py']] for x in r['G']) / len(r['G']) if r['G'] else None   # his season average (every game this season before this week)
                base = line; line = py_line(base, sa, r['it'])
            elif k == 'ty': base = line; line = ty_line(base)
            mm = m * (sn if k == 'ptd' else 1 + (sn - 1) * .7)
            if k == 'ptd': pm = pover(mm, line)
            else: pm = 1 - cdf(QS[QK(pos, k)], (line + 1e-4) / max(mm, .05))
            po = min(.62, max(.38, .5 * pm + .25))
            lines.append({'pid': p['id'], 'wk': FW, 't': p['t'], 'opp': r['opp'], 'k': kk, 'line': line, 'mm': round(float(mm), 2), 'po': round(float(po), 3),
                          'v': LV, 'kick': r['kick'], 'q': bool(p.get('inj') == 'Questionable'), 'src': 'bff',
                          'base': base, 'sa': round(float(sa), 1) if sa is not None else None,
                          'vol': round(float(vol), 1), 'eff': round(float(eff), 3), 'it': round(float(r['it']), 2), 'bmp': round(float(r['bmp']), 1), 'pp': bool(r['last_part'])})
        lines += more_lines(r, FW, volume)
    return lines

def more_lines(r, FW, volume):
    """the newer markets (pass attempts, completions, interceptions, rush attempts, targets, anytime and first-half TD):
    from BFF's own expected volume, no picks (research/bt_props_bff.py)"""
    p, pos, G, pv = r['p'], r['pos'], r['G'], r['p'].get('pv') or {}
    c = lambda i: sum(x[i] for x in G)                       # this season before this week (every game he played)
    base = {'pid': p['id'], 'wk': FW, 't': p['t'], 'opp': r['opp'], 'v': LV, 'kick': r['kick'], 'q': bool(p.get('inj') == 'Questionable'), 'src': 'bff',
            'it': round(float(r['it']), 2)}            # no 'pick' (never a pick), kept small: the page carries every line
    out = []
    def add(k, line, mm, po, m_, x):
        yn = k in ('int', 'td', 'td1')                                     # yes/no: expected counts to 3 decimals, so the page's sums check out
        out.append(dict(base, k=k, line=line, mm=round(float(mm), 3 if yn else 2), po=round(float(po), 3), mk=round(float(m_), 3 if yn else 2), x=x))
    pa = volume(r, 'att', .75, 2) if pos == 'QB' else None
    car, tg = volume(r, 'car', .75, 2) or 0, volume(r, 'tg', .75, 2) or 0
    if pa and pa >= XMIN['patt']:
        pa = round(pa, 2)
        add('patt', x_line('patt', pa), pa, XOVR['patt'], pa, None)
        cr = cmp_rate(c(1), c(2), pv.get('completions', 0), pv.get('attempts', 0)); cm = pa * cr
        if cm >= XMIN['cmp']: add('cmp', x_line('cmp', cm), cm, XOVR['cmp'], cm, {'pa': pa, 'cr': round(cr, 4)})
        ir = int_rate(c(5), c(2), pv.get('passing_interceptions', 0), pv.get('attempts', 0)); li = INTM['sc'] * pa * ir
        add('int', .5, li, 1 - math.exp(-li), li, {'pa': pa, 'ir': round(ir, 5)})
    car, tg = round(car, 2), round(tg, 2)
    if car >= XMIN['car']: add('car', x_line('car', car), car, XOVR['car'], car, None)
    if pos != 'QB' and tg >= XMIN['tg']: add('tg', x_line('tg', tg), tg, XOVR['tg'], tg, None)
    if car + (0 if pos == 'QB' else tg) >= 1.5:
        lt, b0, vf, own = td_rate(pos, car, tg, r['it'], c(6), c(10), c(8) + c(12), pv.get('carries', 0), pv.get('targets', 0), pv.get('td', 0), parts=True)
        x = {'car': car, 'tg': tg if pos != 'QB' else 0, 'b': round(b0, 4), 'vf': round(vf, 4), 'own': round(own, 4), 'sc': TDS}
        add('td', .5, lt, 1 - math.exp(-lt), lt, x)
        add('td1', .5, lt * H1[pos], 1 - math.exp(-lt * H1[pos]), lt, dict(x, h1=H1[pos]))
    return out

# ------------------------------------------------------------------ history: opening line and every move, with the reason
def why(old, new):
    R = []
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
    moves = [m for m in old.get('moves') or [] if m.get('v') == LV]   # moves under older rules (before Nov 2026: reasons from other sites' projections) are dropped
    for l in new_lines:
        o = prev.get(key(l))
        if o and o.get('v') != LV: o = None   # a line from older rules (before the Oct 25 2026 refit): it reopens rather than counting as a move
        if not o:
            l['open'] = l['line']; l['opened'] = STAMP; l['mv'] = []
            continue
        l['open'], l['opened'], l['mv'] = o.get('open', o['line']), o.get('opened', old.get('at', STAMP)), list(o.get('mv') or [])
        if l['line'] != o['line']:
            w = why(o, l); l['mv'].append([STAMP, o['line'], l['line'], w])
            moves.append({'pid': l['pid'], 'k': l['k'], 'from': o['line'], 'to': l['line'], 'at': STAMP, 'why': w, 'v': LV})
    now_keys = {key(l) for l in new_lines}
    for kk_ in [k_ for k_ in prev if k_ not in now_keys]:
        pid, k, wk_ = kk_; o_ = prev[kk_]
        if o_.get('kick') and _dt(o_['kick']) and _dt(o_['kick']) <= NOW: continue   # the game started: not a pulled line
        if o_.get('v') != LV: continue   # a line from older rules: not a pulled line
        n_ = PULLED.get(pid); w_ = f"pulled: {n_[1]} ({n_[2]})" if n_ else 'line pulled (injury report or role change)'
        moves.append({'pid': pid, 'k': k, 'from': o_['line'], 'to': None, 'at': STAMP, 'why': w_, 'v': LV})
    sig = lambda L: sorted((l['pid'], l['k'], l['line'], round(l['po'], 2), l['q'], round(l.get('it') or 0, 2)) for l in L)   # the team total shows with each line
    changed = (not old) or sig(new_lines) != sig(old.get('lines') or []) or moves[-60:] != (old.get('moves') or [])
    out = {'wk': fw, 'at': STAMP if changed else old.get('at', STAMP), 'odds_from': 'nflverse schedule', 'bt': BT, 'real': BT_BFF, 'more': BT_MORE, 'lines': new_lines, 'moves': moves[-60:],
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
    if changed or not os.path.exists('lines.json'):
        json.dump(out, open('lines.json', 'w'), separators=(',', ':'))
    if D is not None:
        D['lines'] = out; json.dump(D, open('ff_data.json', 'w'), separators=(',', ':'))
    mv = sum(1 for m in out['moves'] if m['at'] == STAMP)
    print(f"lines: {len(L)} for week {I['fw']}{' and this week' + chr(39) + 's late games' if any(l.get('wk') != I['fw'] for l in L) else ''}, {mv} moved this run, Vegas totals from the {out['odds_from']}"
          + ('' if changed else ' (no change)'))
