#!/usr/bin/env python3
"""Weekly calls: BFF's must starts, must sits, buy lows and sell highs, saved every week and graded with real results.

Run by the data workflow after the projections are built (needs ff_data.json and this season's weekly stats file).

How calls are made (the same rules the page uses for the cheat sheet and the Trends tab, PPR scoring):
  must start  the 10 highest projected players at each position for the week (players listed doubtful are left out)
  must sit    usual starters (good rest-of-season rank, solid usual scoring, a real role) projected outside the
              starter spots this week, or questionable/doubtful and near the line
  buy low     non-QBs scoring at least 2.5 points a game less than their usage is worth (expected points 8+)
  sell high   non-QBs scoring at least 3 points a game more than their usage is worth (10+ points a game)

When calls lock:
  must start / must sit   recomputed every run until that player's game kicks off; from kickoff on it never changes
  buy low / sell high     recomputed every run until the week's first kickoff, then locked

How calls are graded (official nflverse stats, PPR):
  must start  hit = finished as a starter at his position that week (top 12 QB, 24 RB, 30 WR, 12 TE)
  must sit    hit = finished outside those spots
              a player who did not play is 'void' and counts neither way; one who played with no stat line scored 0
  yardsticks  the 10 best season averages at each position are graded like must starts, and every usual starter
              (the group must sits are picked from) is graded like a must sit, so each list can be compared with
              what simply going by season-long scoring would have done
  buy low     hit = averaged more points over his next 3 games than when we made the call
  sell high   hit = averaged fewer points over his next 3 games

  python calls_update.py           data job: update calls, grade, write calls_history.json and D['calls'] in ff_data.json
"""
import json, math, os, datetime
import pandas as pd

SEASON_FILE = 'stats_player_week_{}.parquet'
HIST = 'calls_history.json'
CUT = {'QB': 12, 'RB': 24, 'WR': 30, 'TE': 12}
MINU = {'QB': 13, 'RB': 6, 'WR': 7.5, 'TE': 5.5}
POS = ['QB', 'RB', 'WR', 'TE']
NOW = datetime.datetime.now(datetime.timezone.utc)
STAMP = NOW.isoformat(timespec='minutes')
r1 = lambda v: None if v is None else round(float(v), 1)

def when(s):
    try: return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except Exception: return None

# ---------------- the page's rules, ported (PPR: no format adjustment)
def out(p): return p.get('inj') in ('Out', 'IR')
def proj(p): return 0.0 if out(p) else float(p.get('proj') or 0)
def wk_proj(p, w):
    if w == p['nw']: return proj(p)
    for r in p.get('ros') or []:
        if r[0] == w: return float(r[2] or 0)
    return 0.0
def avail(p, w): return (not out(p)) if p['nw'] == w else (p.get('inj') != 'IR' and any(r[0] == w for r in p.get('ros') or []))
def ros_val(p, r): return proj(p) if r[0] == p['nw'] else float(r[2] or 0)
def ros_tot(p, a, b=17): return sum(ros_val(p, r) for r in p.get('ros') or [] if a <= r[0] <= b)
def usual(p, w):
    R = [r for r in p.get('ros') or [] if r[0] != w and r[0] <= 17]
    return sum(ros_val(p, r) for r in R) / len(R) if R else wk_proj(p, w)

def kickoff(D, team, w):
    for x in (D.get('sched') or {}).get(team) or []:
        if x[0] == w: return x[5] if len(x) > 5 else None
    return None
def opp_of(D, team, w):
    for x in (D.get('sched') or {}).get(team) or []:
        if x[0] == w: return x[1], x[2]
    return None, None

def call_week(D):
    nw = int(D['asof']['next_week'])
    left = {t for t, L in (D.get('sched') or {}).items() for x in L if x[0] == nw and x[4] is None}
    return nw + 1 if len(left) / 2 <= 2 and nw < 18 else nw, nw

def make_calls(D, w, nw):
    P = D['players']; res = {'start': [], 'sit': [], 'buy': [], 'sell': [], 'base': [], 'pool': []}
    for pos in POS:
        cut = CUT[pos]
        L = sorted([p for p in P if p['p'] == pos and avail(p, w)], key=lambda p: -wk_proj(p, w))
        wr = {p['id']: i + 1 for i, p in enumerate(L)}
        rr = {p['id']: i + 1 for i, p in enumerate(sorted([p for p in P if p['p'] == pos and p.get('inj') != 'IR'], key=lambda p: -ros_tot(p, nw)))}
        must = [p for p in L if p.get('inj') != 'Doubtful'][:10]; ms = {p['id'] for p in must}
        role = lambda p: p['p'] != 'RB' or (p.get('cs') or 0) >= .15 or (p.get('tpg') or 0) >= 3
        injq = lambda p: p['nw'] == w and p.get('inj') in ('Doubtful', 'Questionable')
        regs = [p for p in L if usual(p, w) >= MINU[pos] and role(p) and rr[p['id']] <= round(cut * 1.5) + 6]   # usual starters
        cand = [p for p in regs if p['id'] not in ms and (wr[p['id']] > cut or (injq(p) and wr[p['id']] > round(cut * .8)))]
        prio = lambda p: 2 if rr[p['id']] <= cut and wr[p['id']] > cut else 1 if injq(p) else 0
        dont = sorted(cand, key=lambda p: (-prio(p), wk_proj(p, w) - usual(p, w)))[:10]
        def entry(p):
            o, h = opp_of(D, p['t'], w)
            return {'id': p['id'], 'n': p['n'], 'p': pos, 't': p['t'], 'o': o, 'h': h, 'k': kickoff(D, p['t'], w), 'v': r1(wk_proj(p, w)),
                    'wr': wr[p['id']], 'u': r1(usual(p, w)), 'q': p.get('inj') if p.get('inj') in ('Questionable', 'Doubtful') else None}
        res['start'] += [entry(p) for p in must]; res['sit'] += [entry(p) for p in dont]
        # yardstick: the 10 best season averages (blended with last season, like the model's baseline)
        blend = lambda p: (((p.get('fpg') or 0) * (p.get('g') or 0) + (p.get('prev') or 0) * 3) / ((p.get('g') or 0) + 3))
        res['pool'] += [{'id': p['id'], 'p': pos, 't': p['t'], 'k': kickoff(D, p['t'], w)} for p in regs]
        res['base'] += [{'id': p['id'], 'p': pos, 't': p['t'], 'k': kickoff(D, p['t'], w)} for p in sorted([p for p in L if p.get('inj') != 'Doubtful'], key=lambda p: -blend(p))[:10]]
    sk = [p for p in P if p['p'] != 'QB' and not out(p) and (p.get('g') or 0) >= 2 and p.get('xfpg') is not None and p.get('fpg') is not None]
    # common sense on top of the numbers (the page uses the same checks; research/bt_commonsense.py, 2020-25): no buy low on
    # a fill-in whose starter is back or due back within two games, on two games, on a player losing snaps or on usage that
    # is already top 6 at his position; no sell high on such a stud; a fill-in still scoring 8+ a game once his starter is
    # back is a sell
    fill_soon = lambda p: bool((p.get('fill') or {}).get('soon'))
    xr = {}
    for q in ('RB', 'WR', 'TE'):
        U = [p for p in P if p['p'] == q and (p.get('g') or 0) >= 2 and p.get('xfpg') is not None and p.get('fpg') is not None]
        for i, p in enumerate(sorted(U, key=lambda p: -p['xfpg'])): xr[p['id']] = i + 1
    stud = lambda p: xr.get(p['id'], 99) <= 6           # usage already top 6 at his position
    no_buy = lambda p: fill_soon(p) or (p.get('g') or 0) < 3 or bool(p.get('rdn')) or stud(p)
    sell_nums = lambda p: p['fpg'] >= 10 and p['fpg'] - p['xfpg'] >= 3
    buy = sorted([p for p in sk if p['xfpg'] >= 8 and p['xfpg'] - p['fpg'] >= 2.5 and not no_buy(p)], key=lambda p: -(p['xfpg'] - p['fpg']) * math.sqrt(p['xfpg']))[:10]
    sell = sorted([p for p in sk if (sell_nums(p) and not stud(p)) or (fill_soon(p) and p['fpg'] >= 8)],
                  key=lambda p: -((100 + p['fpg'] * (1 - p['fill'].get('f', .8))) if fill_soon(p) and p['fpg'] >= 8 else p['fpg'] - p['xfpg']))[:10]   # fill-ins first
    bs = lambda p: {'id': p['id'], 'n': p['n'], 'p': p['p'], 't': p['t'], 'fpg': p['fpg'], 'xfpg': p['xfpg'], 'g': p['g'],
                    **({'fb': p['fill']['by']} if fill_soon(p) else {})}
    res['buy'] = [bs(p) for p in buy]; res['sell'] = [bs(p) for p in sell]
    return res

def merge_week(wk, fresh, first_kick):
    """keep calls whose game already kicked off exactly as they were; replace everything else with the fresh calls"""
    started = lambda e: e.get('k') and when(e['k']) and when(e['k']) <= NOW
    for cat in ('start', 'sit', 'base', 'pool'):
        old = wk.get(cat) or []
        frozen = [e for e in old if started(e)]
        fids = {e['id'] for e in frozen}
        new = [e for e in fresh[cat] if e['id'] not in fids and not started(e)]
        wk[cat] = sorted(frozen + new, key=lambda e: (POS.index(e['p']), -(e.get('v') or 0))) if cat not in ('base', 'pool') else frozen + new
    locked = first_kick and when(first_kick) and when(first_kick) <= NOW
    if not locked:
        wk['buy'], wk['sell'] = fresh['buy'], fresh['sell']; wk['lock'] = first_kick
    wk['upd'] = STAMP; wk.setdefault('made', STAMP)

def grade(H, D, season):
    f = SEASON_FILE.format(season)
    if not os.path.exists(f): print('no weekly stats file; grading skipped'); return
    st = pd.read_parquet(f, columns=['player_id', 'week', 'position', 'season_type', 'fantasy_points_ppr'])
    st = st[(st.season_type == 'REG') & st.position.isin(POS)].copy(); st['fp'] = st.fantasy_points_ppr.fillna(0)
    st['rk'] = st.groupby(['week', 'position']).fp.rank(ascending=False, method='min')
    by = {(r.player_id, int(r.week)): (float(r.fp), int(r.rk)) for r in st.itertuples()}
    npos = st.groupby(['week', 'position']).size().to_dict()
    played = set()                                     # on the field but no stat line (for example a receiver with no targets): 0 points
    try:
        ids = pd.read_csv('player_ids.csv', usecols=['pfr_id', 'gsis_id'], low_memory=False).dropna().drop_duplicates('pfr_id').set_index('pfr_id').gsis_id.to_dict()
        sn = pd.read_parquet(f'snap_counts_{season}.parquet', columns=['pfr_player_id', 'week', 'game_type', 'offense_snaps'])
        sn = sn[(sn.game_type == 'REG') & (sn.offense_snaps > 0)]
        played = {(ids.get(a), int(w)) for a, w in zip(sn.pfr_player_id, sn.week) if ids.get(a)}
    except Exception as e: print('snap counts unavailable for grading:', e)
    games = {}
    for r in st.sort_values('week').itertuples(): games.setdefault(r.player_id, []).append((int(r.week), float(r.fp)))
    final = lambda team, w: any(x[0] == w and x[4] is not None for x in (D.get('sched') or {}).get(team) or [])
    weeks_done = set(int(w) for w in st.week.unique())
    cw = max(int(k) for k in H['weeks']) if H['weeks'] else 0
    for ws, wk in H['weeks'].items():
        w = int(ws)
        for cat in ('start', 'sit', 'base', 'pool'):
            for e in wk.get(cat) or []:
                if not (final(e['t'], w) and w in weeks_done): e.pop('res', None); continue
                if (e['id'], w) in by: a, f_ = by[(e['id'], w)]
                elif (e['id'], w) in played: a, f_ = 0.0, npos.get((w, e['p']), 0) + 1
                else: e.update(a=None, f=None, res='void'); continue
                inside = f_ <= CUT[e['p']]
                e.update(a=round(a, 1), f=f_, res=('hit' if inside else 'miss') if cat in ('start', 'base') else ('miss' if inside else 'hit'))   # pool: 'hit' = finished outside the starter spots
        for cat in ('buy', 'sell'):
            for e in wk.get(cat) or []:
                nx = [round(fp, 1) for (gw, fp) in games.get(e['id'], []) if gw >= w][:3]
                e['nx'] = nx
                done = len(nx) == 3 or (cw - w >= 6 and len(nx) >= 1)
                if done:
                    avg = sum(nx) / len(nx); e['avg'] = round(avg, 1)
                    e['res'] = ('hit' if avg > e['fpg'] else 'miss') if cat == 'buy' else ('hit' if avg < e['fpg'] else 'miss')
                elif cw - w >= 6: e['res'] = 'void'
                else: e.pop('res', None); e['avg'] = round(sum(nx) / len(nx), 1) if nx else None

def compact(H):
    """what the page needs: every call, but the yardstick lists only as graded counts by position"""
    C = {k: v for k, v in H.items() if k != 'weeks'}; C['weeks'] = {}
    for ws, wk in H['weeks'].items():
        c = {k: v for k, v in wk.items() if k not in ('base', 'pool')}
        for k in ('base', 'pool'):
            c[k] = {pos: [sum(e.get('res') == 'hit' for e in wk.get(k) or [] if e['p'] == pos), sum(e.get('res') in ('hit', 'miss') for e in wk.get(k) or [] if e['p'] == pos)] for pos in POS}
        for k in ('start', 'sit'):
            c[k] = [{x: y for x, y in e.items() if y is not None} for e in wk.get(k) or []]
        C['weeks'][ws] = c
    return C

def main():
    D = json.load(open('ff_data.json'))
    season = int(D['asof']['season'])
    try: H = json.load(open(HIST))
    except Exception: H = {}
    if H.get('season') != season: H = {'season': season, 'weeks': {}}
    H.update(fmt='PPR', cut=CUT)
    cw, nw = call_week(D)
    if cw <= 18:
        fresh = make_calls(D, cw, nw)
        kicks = [k for t in (D.get('sched') or {}) for k in [kickoff(D, t, cw)] if k]
        wk = H['weeks'].setdefault(str(cw), {'src': 'live'})
        if wk.get('src') != 'live': wk.clear(); wk['src'] = 'live'
        merge_week(wk, fresh, min(kicks) if kicks else None)
    grade(H, D, season)
    H['at'] = STAMP; H['cw'] = cw
    H['weeks'] = dict(sorted(H['weeks'].items(), key=lambda kv: int(kv[0])))
    json.dump(H, open(HIST, 'w'), separators=(',', ':'))
    D['calls'] = compact(H); json.dump(D, open('ff_data.json', 'w'), separators=(',', ':'))
    for ws, wk in H['weeks'].items():
        c = {k: [e.get('res') for e in wk.get(k) or []] for k in ('start', 'base', 'sit', 'pool', 'buy', 'sell')}
        print(f"week {ws} ({wk.get('src')}): " + ' | '.join(f"{k} {sum(x == 'hit' for x in v)}/{sum(x in ('hit', 'miss') for x in v)} of {len(v)}" for k, v in c.items()))

if __name__ == '__main__':
    main()
