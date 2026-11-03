#!/usr/bin/env python3
"""Kickers and team defenses (D/ST) for BFF: their fantasy points every week, a projection for each game left, and ranks.
They are here for tracking and for leagues that start them; they stay out of BFF's trade values, buy/sell calls, waiver
targets and prop lines, so nothing about the skill-player rankings changes.

SCORING (the most common default league settings, as Yahoo's help pages list them: help.yahoo.com/kb/SLN6489):
  kicker:  field goal 0-39 yards 3, 40-49 yards 4, 50+ yards 5; extra point 1 (no points off for misses)
  D/ST:    sack 1, interception 2, fumble recovery 2, touchdown 6 (interception, fumble, blocked kick, kickoff and punt
           returns), safety 2, blocked kick 2; points allowed 0: 10, 1-6: 7, 7-13: 4, 14-20: 1, 21-27: 0, 28-34: -1, 35+: -4.
  Points allowed (Yahoo's rule, help.yahoo.com/kb/SLN6442): every point the opponent scored except touchdowns its defense
  returned on an interception, a fumble (not on a kickoff or punt) or a blocked field goal, safeties, and defensive
  two-point returns. Everything is counted from nflverse's play-by-play and final scores.

PROJECTIONS (research/bt_kdst.py: fit on 2015-2022, tested on 2023-2025 games it never saw; D/ST: average miss 4.4
points, correlation 0.33 with what happened, against 4.5 and 0.08 for the league average; kickers: 3.6 and 0.16, against
3.7 and 0.04: a kicker's week is mostly luck, and the projection says so):
  D/ST:   a + b x the opponent's implied points (Vegas) + c x the defense's sacks and takeaways per game so far + d x the
          opponent offense's sacks and giveaways per game so far (both shrunk toward the league average) + e x home.
  kicker: a + b x his team's implied points + c x his points per game so far (shrunk) + d x indoors.
  Vegas lines where they are out; for weeks further ahead each team's points scored and allowed so far stand in for them
  (the same rule the skill-player projections use).

python ff_kdst.py   (after ff_produce.py: reads ff_data.json, writes its 'kd' block back; a few seconds)"""
import json, math, os, sys, datetime
import numpy as np, pandas as pd

KPTS = {'fg0_39': 3, 'fg40_49': 4, 'fg50': 5, 'pat': 1}
DPTS = {'sack': 1, 'int': 2, 'fr': 2, 'td': 6, 'sfty': 2, 'blk': 2}
PA_TIERS = ((0, 10), (6, 7), (13, 4), (20, 1), (27, 0), (34, -1))   # (points allowed up to and including, fantasy points); 35+: -4
TFIX = {'LAR': 'LA', 'JAC': 'JAX', 'WSH': 'WAS', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
TNAME = {'ARI': 'Arizona Cardinals', 'ATL': 'Atlanta Falcons', 'BAL': 'Baltimore Ravens', 'BUF': 'Buffalo Bills', 'CAR': 'Carolina Panthers',
         'CHI': 'Chicago Bears', 'CIN': 'Cincinnati Bengals', 'CLE': 'Cleveland Browns', 'DAL': 'Dallas Cowboys', 'DEN': 'Denver Broncos',
         'DET': 'Detroit Lions', 'GB': 'Green Bay Packers', 'HOU': 'Houston Texans', 'IND': 'Indianapolis Colts', 'JAX': 'Jacksonville Jaguars',
         'KC': 'Kansas City Chiefs', 'LA': 'Los Angeles Rams', 'LAC': 'Los Angeles Chargers', 'LV': 'Las Vegas Raiders', 'MIA': 'Miami Dolphins',
         'MIN': 'Minnesota Vikings', 'NE': 'New England Patriots', 'NO': 'New Orleans Saints', 'NYG': 'New York Giants', 'NYJ': 'New York Jets',
         'PHI': 'Philadelphia Eagles', 'PIT': 'Pittsburgh Steelers', 'SEA': 'Seattle Seahawks', 'SF': 'San Francisco 49ers', 'TB': 'Tampa Bay Buccaneers',
         'TEN': 'Tennessee Titans', 'WAS': 'Washington Commanders'}
# projection constants: research/bt_kdst.py (results_kdst.json 'model'); checked by tests/kdsttest.py
DST_M = {'a': 12.8535, 'opp_it': -0.3933, 'rate': 0.2855, 'give': 0.3334, 'home': -0.2736}
K_M = {'a': 2.6143, 'it': 0.1446, 'kavg': 0.2461, 'dome': 0.448}
SHRINK = {'rate': 4, 'give': 4, 'kavg': 4}   # games of the league average mixed into each to-date rate
fix = lambda t: TFIX.get(t, t)


def pa_points(pa):
    for hi, pts in PA_TIERS:
        if pa <= hi: return pts
    return -4


def games_table(path='games.csv'):
    """regular-season games, one row per team: season, week, team, opp, home, points for/against, implied points, indoors"""
    g = pd.read_csv(path, low_memory=False); g = g[g.game_type == 'REG'].copy()
    for c in ('home_team', 'away_team'): g[c] = g[c].map(fix)
    sp = pd.to_numeric(g.spread_line, errors='coerce'); tt = pd.to_numeric(g.total_line, errors='coerce')   # spread_line > 0: home favored
    dome = g.roof.isin(['dome', 'closed']).astype(float)
    H = pd.DataFrame({'season': g.season, 'week': g.week, 'game_id': g.game_id, 'team': g.home_team, 'opp': g.away_team, 'home': 1.0,
                      'pf': pd.to_numeric(g.home_score, errors='coerce'), 'pa_raw': pd.to_numeric(g.away_score, errors='coerce'),
                      'it': (tt + sp) / 2, 'oit': (tt - sp) / 2, 'dome': dome, 'gameday': g.gameday, 'gametime': g.gametime})
    A = pd.DataFrame({'season': g.season, 'week': g.week, 'game_id': g.game_id, 'team': g.away_team, 'opp': g.home_team, 'home': 0.0,
                      'pf': pd.to_numeric(g.away_score, errors='coerce'), 'pa_raw': pd.to_numeric(g.home_score, errors='coerce'),
                      'it': (tt - sp) / 2, 'oit': (tt + sp) / 2, 'dome': dome, 'gameday': g.gameday, 'gametime': g.gametime})
    return pd.concat([H, A], ignore_index=True)


PBP_COLS = ['game_id', 'season', 'week', 'season_type', 'posteam', 'defteam', 'play_type', 'sack', 'interception', 'fumble_lost',
            'fumble_recovery_1_team', 'td_team', 'return_touchdown', 'safety', 'punt_blocked', 'field_goal_result', 'extra_point_result',
            'defensive_two_point_conv', 'defensive_extra_point_conv']


def dst_games(season, G):
    """every team's D/ST stat line and fantasy points in each regular-season game of `season` (needs pbp_<season>.parquet)"""
    f = f'pbp_{season}.parquet'
    if not os.path.exists(f): return pd.DataFrame()
    p = pd.read_parquet(f, columns=PBP_COLS); p = p[p.season_type == 'REG']
    for c in ('posteam', 'defteam', 'fumble_recovery_1_team', 'td_team'): p[c] = p[c].map(lambda t: fix(t) if isinstance(t, str) else t)
    for c in ('sack', 'interception', 'fumble_lost', 'return_touchdown', 'safety', 'punt_blocked', 'defensive_two_point_conv', 'defensive_extra_point_conv'):
        p[c] = pd.to_numeric(p[c], errors='coerce').fillna(0)
    rows = []
    g_ = G[G.season == season].set_index(['game_id', 'team'])
    for (gid, ), P_ in p.groupby(['game_id']):
        teams = [t for t in set(P_.posteam.dropna()) | set(P_.defteam.dropna())]
        for D in teams:
            if (gid, D) not in g_.index: continue
            gr = g_.loc[(gid, D)]; O = gr.opp
            dd = P_[P_.defteam == D]
            sacks = int((dd.sack == 1).sum()); ints = int((dd.interception == 1).sum())
            fr = int(((P_.fumble_lost == 1) & (P_.fumble_recovery_1_team == D)).sum())
            td = int(((P_.td_team == D) & ((P_.posteam != D) | (P_.return_touchdown == 1))).sum())
            sfty = int(((P_.safety == 1) & (P_.defteam == D)).sum())
            blk = int(((dd.punt_blocked == 1) | (dd.field_goal_result == 'blocked') | (dd.extra_point_result == 'blocked')).sum())
            # opponent points that do not count against this defense: its defense's returns off our offense (not kicks), safeties, defensive 2-point returns
            o_def_td = int(((P_.td_team == O) & (P_.posteam == D) & ~P_.play_type.isin(['kickoff', 'punt'])).sum())
            o_sfty = int(((P_.safety == 1) & (P_.defteam == O)).sum())
            o_d2 = int((((P_.defensive_two_point_conv == 1) | (P_.defensive_extra_point_conv == 1)) & (P_.defteam == O)).sum())
            pa_raw = gr.pa_raw
            if pa_raw != pa_raw: continue
            pa = max(0, int(pa_raw) - 6 * o_def_td - 2 * o_sfty - 2 * o_d2)
            pts = sacks * DPTS['sack'] + ints * DPTS['int'] + fr * DPTS['fr'] + td * DPTS['td'] + sfty * DPTS['sfty'] + blk * DPTS['blk'] + pa_points(pa)
            rows.append((season, int(gr.week), D, O, gr.home, sacks, ints, fr, td, sfty, blk, int(pa_raw), pa, pts))
    return pd.DataFrame(rows, columns=['season', 'week', 'team', 'opp', 'home', 'sack', 'int', 'fr', 'td', 'sfty', 'blk', 'pa_raw', 'pa', 'pts'])


def k_games(season):
    """every kicker's line and fantasy points in each regular-season game of `season` (stats_player_week_<season>.parquet)"""
    f = f'stats_player_week_{season}.parquet'
    if not os.path.exists(f): return pd.DataFrame()
    s = pd.read_parquet(f); s = s[(s.season_type == 'REG') & (s.position == 'K')].copy()
    n = lambda c: pd.to_numeric(s[c], errors='coerce').fillna(0) if c in s.columns else 0
    s['fg0_39'] = n('fg_made_0_19') + n('fg_made_20_29') + n('fg_made_30_39'); s['fg40_49'] = n('fg_made_40_49'); s['fg50'] = n('fg_made_50_59') + n('fg_made_60_')
    s['pat'] = n('pat_made'); s['fga'] = n('fg_att'); s['fgm'] = n('fg_made'); s['pata'] = n('pat_att')
    s['pts'] = s.fg0_39 * KPTS['fg0_39'] + s.fg40_49 * KPTS['fg40_49'] + s.fg50 * KPTS['fg50'] + s.pat * KPTS['pat']
    tcol = 'team' if 'team' in s.columns else 'recent_team'
    out = s[['season', 'week', 'player_id', 'player_display_name' if 'player_display_name' in s.columns else 'player_name', tcol, 'opponent_team', 'fg0_39', 'fg40_49', 'fg50', 'pat', 'fga', 'fgm', 'pata', 'pts']].copy()
    out.columns = ['season', 'week', 'pid', 'name', 'team', 'opp', 'fg0_39', 'fg40_49', 'fg50', 'pat', 'fga', 'fgm', 'pata', 'pts']
    out['team'] = out.team.map(fix); out['opp'] = out.opp.map(fix)
    return out[(out.fga + out.pata) > 0]


def to_date(df, key, cols, wk_col='week'):
    """for each row, the sum of `cols` and the number of games for the same key in earlier weeks of the same season"""
    df = df.sort_values(['season', key, wk_col]).copy()
    g = df.groupby(['season', key])
    for c in cols: df[c + '_sum'] = g[c].cumsum() - df[c]
    df['n_prev'] = g.cumcount()
    return df


def features(DST, KG, G):
    """pre-game features for every D/ST and kicker game (what was known before kickoff)"""
    D = DST.copy(); D['tk'] = D['sack'] + 2 * (D['int'] + D['fr'])   # sacks and takeaways (a takeaway counts double, as in scoring)
    D = to_date(D, 'team', ['tk', 'pts'])
    LA = D.groupby('season')['tk'].mean().to_dict()   # league average per game (each season)
    lg = D.season.map(LA)
    D['rate'] = (D.tk_sum + SHRINK['rate'] * lg) / (D.n_prev + SHRINK['rate'])
    # the opponent offense's giveaways so far: what defenses did against it in earlier weeks
    O = D[['season', 'week', 'opp', 'tk']].rename(columns={'opp': 'off', 'tk': 'gv'})
    O = to_date(O, 'off', ['gv']); O['give'] = (O.gv_sum + SHRINK['give'] * O.season.map(LA)) / (O.n_prev + SHRINK['give'])
    D = D.merge(O[['season', 'week', 'off', 'give']].rename(columns={'off': 'opp'}), on=['season', 'week', 'opp'], how='left')
    D = D.merge(G[['season', 'week', 'team', 'oit', 'it']], on=['season', 'week', 'team'], how='left')
    K = to_date(KG.copy(), 'pid', ['pts'])
    KA = K.groupby('season')['pts'].mean().to_dict()
    K['kavg'] = (K.pts_sum + SHRINK['kavg'] * K.season.map(KA)) / (K.n_prev + SHRINK['kavg'])
    K = K.merge(G[['season', 'week', 'team', 'it', 'dome']], on=['season', 'week', 'team'], how='left')
    return D, K


def dst_proj(oit, rate, give, home):
    return DST_M['a'] + DST_M['opp_it'] * oit + DST_M['rate'] * rate + DST_M['give'] * give + DST_M['home'] * home


def k_proj(it, kavg, dome):
    return K_M['a'] + K_M['it'] * it + K_M['kavg'] * kavg + K_M['dome'] * dome


# ------------------------------------------------------------------ this season, for the page
def build(D):
    """the 'kd' block: every D/ST and kicker with this season's points, the next game's projection, the rest of the season and ranks"""
    A = D['asof']; SEASON = int(A['season']); NW = int(A['next_week'])
    G = games_table(); g26 = G[G.season == SEASON].copy()
    played = g26[g26.pf.notna()]
    DS = dst_games(SEASON, G); KG = k_games(SEASON)
    prev = dst_games(SEASON - 1, G) if not len(DS) else pd.DataFrame()
    base = DS if len(DS) else prev
    LA_tk = float((base['sack'] + 2 * (base['int'] + base['fr'])).mean()) if len(base) else 4.0
    KB = KG if len(KG) else k_games(SEASON - 1)
    LA_k = float(KB.pts.mean()) if len(KB) else 8.5
    # implied points for games without a Vegas line yet: each team's points scored and allowed so far (the skill-player rule)
    pf = played.groupby('team').pf.mean(); pa = played.groupby('team').pa_raw.mean(); lgp = float(played.pf.mean()) if len(played) else 22.0
    def proxy(tm, op):
        a = pf.get(tm, lgp); b = pa.get(op, lgp); return float((a + b) / 2)
    tk = (DS['sack'] + 2 * (DS['int'] + DS['fr'])) if len(DS) else pd.Series(dtype=float)
    rate_of = {t: (float(tk[DS.team == t].sum()) + SHRINK['rate'] * LA_tk) / ((DS.team == t).sum() + SHRINK['rate']) for t in TNAME}
    give_of = {t: (float(tk[DS.opp == t].sum()) + SHRINK['give'] * LA_tk) / ((DS.opp == t).sum() + SHRINK['give']) for t in TNAME}
    fut = g26[g26.pf.isna()].sort_values('week')
    def it_of(r):
        return (float(r.it), float(r.oit)) if r.it == r.it and r.oit == r.oit else (proxy(r.team, r.opp), proxy(r.opp, r.team))
    byes = {t: [w for w in range(1, 19) if w not in set(g26[g26.team == t].week)] for t in TNAME}
    out = []
    # ---- D/ST
    for t in sorted(TNAME):
        mine = DS[DS.team == t].sort_values('week') if len(DS) else DS
        ros = []
        for r in fut[fut.team == t].itertuples():
            it, oit = it_of(r); ros.append([int(r.week), r.opp, round(float(dst_proj(oit, rate_of[t], give_of[r.opp], r.home)), 2), int(r.home)])
        nx = next((x for x in ros if x[0] == NW), None)
        out.append({'id': 'DST_' + t, 'n': TNAME[t] + ' D/ST', 'p': 'DST', 't': t,
                    'g': int(len(mine)), 'tot': int(mine.pts.sum()) if len(mine) else 0, 'fpg': round(float(mine.pts.mean()), 2) if len(mine) else None,
                    'wk': [[int(x.week), x.opp, int(x.pts), int(x.sack), int(x.int), int(x.fr), int(x.td), int(x.sfty), int(x.blk), int(x.pa)] for x in mine.itertuples()],
                    'ros': ros, 'nw': NW, 'opp': nx[1] if nx else None, 'home': nx[3] if nx else None, 'proj': nx[2] if nx else 0.0, 'bye': byes[t]})
    # ---- kickers: each team's kicker now (latest depth chart), plus anyone who kicked this season
    cur = {}
    try:
        dc = pd.read_parquet(f'depth_charts_{SEASON}.parquet'); dc = dc[dc.pos_abb == 'K']
        if len(dc):
            last = dc[dc.dt == dc.dt.max()]; last = last.sort_values('pos_rank').drop_duplicates('team')
            cur = {fix(r.team): (r.gsis_id, r.player_name) for r in last.itertuples() if isinstance(r.gsis_id, str)}
    except Exception as e:
        print('no depth chart for kickers:', e)
    for t in TNAME:   # a team the depth chart misses: its latest kicker this season
        if t not in cur and len(KG) and (KG.team == t).any():
            r = KG[KG.team == t].sort_values('week').iloc[-1]; cur[t] = (r.pid, r['name'])
    team_now = {v[0]: t for t, v in cur.items()}
    pids = list(dict.fromkeys(list(team_now) + (list(KG.pid.unique()) if len(KG) else [])))
    for pid in pids:
        mine = KG[KG.pid == pid].sort_values('week') if len(KG) else KG
        t = team_now.get(pid) or (mine.team.iloc[-1] if len(mine) else None)
        if not t: continue
        name = next((v[1] for v in cur.values() if v[0] == pid), None) or (mine['name'].iloc[-1] if len(mine) else pid)
        kavg = (float(mine.pts.sum()) + SHRINK['kavg'] * LA_k) / (len(mine) + SHRINK['kavg'])
        ros = []
        if pid in team_now:
            for r in fut[fut.team == t].itertuples():
                it, oit = it_of(r); ros.append([int(r.week), r.opp, round(float(k_proj(it, kavg, r.dome)), 2), int(r.home)])
        nx = next((x for x in ros if x[0] == NW), None)
        out.append({'id': 'K_' + pid, 'n': name, 'p': 'K', 't': t,
                    'cur': pid in team_now, 'g': int(len(mine)), 'tot': int(mine.pts.sum()) if len(mine) else 0, 'fpg': round(float(mine.pts.mean()), 2) if len(mine) else None,
                    'wk': [[int(x.week), x.opp, int(x.pts), int(x.fgm), int(x.fga), int(x.pat), int(x.pata), int(x.fg50), int(x.fg40_49)] for x in mine.itertuples()],
                    'ros': ros, 'nw': NW, 'opp': nx[1] if nx else None, 'home': nx[3] if nx else None, 'proj': nx[2] if nx else 0.0, 'bye': byes.get(t, [])})
    # ---- ranks: this week (by projection, players with a game), rest of season, season points
    for q in ('K', 'DST'):
        L = [x for x in out if x['p'] == q]
        for i, x in enumerate(sorted([x for x in L if x['opp']], key=lambda x: -x['proj'])): x['rk'] = i + 1
        for i, x in enumerate(sorted([x for x in L if x['ros']], key=lambda x: -sum(r[2] for r in x['ros']))): x['rrk'] = i + 1
        for i, x in enumerate(sorted([x for x in L if x['g']], key=lambda x: (-x['tot'], -(x['fpg'] or 0)))): x['srk'] = i + 1
    R = json.load(open('research/results_kdst.json')) if os.path.exists('research/results_kdst.json') else {}
    test = {q: (R.get(q.lower() if q == 'K' else 'dst') or {}).get('test_2023_25', {}).get('proj') for q in ('K', 'DST')}
    return {'season': SEASON, 'nw': NW, 'list': out, 'test': test,
            'sc': {'K': 'FG 0-39 yds 3 · 40-49 yds 4 · 50+ yds 5 · extra point 1', 'DST': 'sack 1 · INT 2 · fumble recovery 2 · TD 6 · safety 2 · blocked kick 2 · points allowed 0: 10, 1-6: 7, 7-13: 4, 14-20: 1, 21-27: 0, 28-34: -1, 35+: -4'}}


if __name__ == '__main__':
    if not os.path.exists('ff_data.json'): print('ff_data.json not found: run ff_produce.py first'); sys.exit(0)
    D = json.load(open('ff_data.json'))
    try:
        D['kd'] = build(D)
    except Exception as ex:   # never break the data job: the page simply shows no kickers or defenses
        import traceback; traceback.print_exc(); print('kickers and defenses skipped:', ex); sys.exit(0)
    json.dump(D, open('ff_data.json', 'w'), separators=(',', ':'))
    L = D['kd']['list']
    top = lambda q: ', '.join(f"{x['n']} {x['proj']}" for x in sorted([x for x in L if x['p'] == q and x['opp']], key=lambda x: -x['proj'])[:3])
    print(f"kickers and defenses: {sum(x['p'] == 'K' for x in L)} kickers ({sum(1 for x in L if x['p'] == 'K' and x.get('cur'))} current), "
          f"{sum(x['p'] == 'DST' for x in L)} defenses; week {D['kd']['nw']} top K: {top('K')}; top D/ST: {top('DST')}")
