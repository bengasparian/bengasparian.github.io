"""BFF research (November 2026): the newer prop markets from BFF's own numbers only (no ESPN or Sleeper projections).

Volume (pass attempts, carries, targets) = BFF's own expected volume, the same as ff_lines.py's model lines: each game this
season counts 0.75 as much as the one after it, last season's per-game average counts like 2 games, and games he left
early (quarterbacks under 15 attempts; others under half their usual snap share) are left out.

1. Count lines (pass attempts, completions = attempts x his completion rate, rush attempts): rules on that volume fit to
   the real week-7 2026 lines (research/props/real_lines_2026_w7_more.json), every rule scored on players it never saw
   (leave one out); a fitted rule must beat the simpler one by more than 0.02. Targets: books rarely post them, so k is
   set where 2025's overs hit like receptions' do at BFF's receptions lines (41.4%), as before.
2. How often the over hit at those lines, 2025 (weeks 2-18) and 2026 (weeks 2 to the latest), the chance each line shows.
3. Interceptions and anytime / first-half touchdowns (yes/no): the same rate models as before (ff_lines.py), now on BFF's
   volume. Calibration checked on 2025 and 2026; when the expected count is off on 2025 the scale is refit on 2025 alone
   and checked on 2026 (which it never saw).
4. The spread of outcomes around each volume (actual / expected at 5%, 10% ... 95%) for the chance at other lines.
python research/bt_props_bff.py   (writes research/results_props_bff.json; about a minute)"""
import os, sys, json, math, numpy as np, pandas as pd
from scipy.optimize import minimize_scalar
BT = os.path.dirname(os.path.abspath(__file__)); RUN = os.path.dirname(BT); os.chdir(os.environ.get('BT_DATA') or RUN); sys.path.insert(0, RUN)
import ff_lines as FL
PR = os.path.join(BT, 'props')
fl = lambda v: math.floor(v) + .5
POS = ('QB', 'RB', 'WR', 'TE')
GLC = ['completions', 'attempts', 'passing_yards', 'passing_tds', 'passing_interceptions', 'carries', 'rushing_yards', 'rushing_tds', 'receptions', 'targets', 'receiving_yards', 'receiving_tds', 'special_teams_tds']
IDS = pd.read_csv('player_ids.csv', low_memory=False)
PFR2G = IDS.dropna(subset=['pfr_id', 'gsis_id']).drop_duplicates('pfr_id').set_index('pfr_id').gsis_id.to_dict()
NAME = {g: n for g, n in zip(IDS.gsis_id, IDS.name) if isinstance(g, str)}
import re, unicodedata
norm = lambda s: re.sub(r'[^a-z]', '', re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', unicodedata.normalize('NFKD', s).lower().replace('.', '')))
BYNAME = {}
for g, n in NAME.items(): BYNAME.setdefault(norm(n), []).append(g)
GM = pd.read_csv('games.csv', low_memory=False); GM = GM[GM.game_type == 'REG']
PBP = '/home/claude/work/bt3/data' if os.path.isdir('/home/claude/work/bt3/data') else RUN


def stats(season):
    s = pd.read_parquet(f'stats_player_week_{season}.parquet'); s = s[(s.season_type == 'REG') & s.position.isin(POS)].copy()
    for c in GLC: s[c] = s[c].fillna(0) if c in s.columns else 0
    s['td'] = s.rushing_tds + s.receiving_tds + s.special_teams_tds; s['team_'] = s['team'] if 'team' in s.columns else s['recent_team']
    return s


def implied(season):
    o = {}
    for g in GM[GM.season == season].itertuples():
        if pd.isna(g.total_line) or pd.isna(g.spread_line): continue
        o[(g.home_team, g.week)] = g.total_line / 2 + g.spread_line / 2; o[(g.away_team, g.week)] = g.total_line / 2 - g.spread_line / 2
    return o


def snaps(season):
    try:
        sn = pd.read_parquet(f'snap_counts_{season}.parquet'); sn = sn[sn.game_type == 'REG']
    except Exception: return {}
    return {(PFR2G.get(a), int(w)): float(p) for a, w, p in zip(sn.pfr_player_id, sn.week, sn.offense_pct) if PFR2G.get(a) and p == p}


def first_half(season):
    f = os.path.join(PBP, f'pbp_{season}.parquet')
    p = pd.read_parquet(f, columns=['season_type', 'qtr', 'week', 'td_player_id']); p = p[(p.season_type == 'REG') & p.td_player_id.notna()]
    return p[p.qtr <= 2].groupby(['td_player_id', 'week']).size().to_dict()


def build(season):
    """one row per player and week he played (week 2 on): BFF's volumes from the games before, the priors, the actuals"""
    ST = stats(season); PV = stats(season - 1); IT = implied(season); SN = snaps(season); H1 = first_half(season)
    q = PV[(PV.position != 'QB') | (PV.attempts >= 15)]
    pri = q.groupby('player_id').agg(n=('week', 'size'), tg=('targets', 'sum'), car=('carries', 'sum'), att=('attempts', 'sum'), rec=('receptions', 'sum'))
    pri = pri[pri.n >= 3]
    pv = PV.groupby('player_id')[['attempts', 'completions', 'passing_interceptions', 'carries', 'targets', 'td']].sum()
    pos = ST.drop_duplicates('player_id', keep='last').set_index('player_id').position.to_dict()
    rows = []
    for g, G in ST.sort_values('week').groupby('player_id'):
        P_ = pos[g]; G = G.reset_index(drop=True)
        for i in range(len(G)):
            w = int(G.week[i])
            if w < 2: continue
            H = G.iloc[:i]
            sn = [SN.get((g, int(x))) for x in H.week]; med = sorted(v for v in sn if v is not None)
            med = med[len(med) // 2] if med else None
            part = [(a < 15) if P_ == 'QB' else bool(med and s is not None and s < .5 * med) for a, s in zip(H.attempts, sn)]
            F = H.loc[np.array([not x for x in part], dtype=bool)] if len(H) else H
            pr = pri.loc[g].to_dict() if g in pri.index else None
            if not len(F) and not pr: continue
            if P_ == 'QB' and not (len(H) and not part[-1]): continue          # lines for quarterbacks who started their last game
            def vol(col, prc, d=.75, Wv=2):
                h = list(F[col]); n = len(h)
                ws = sum(x * d ** (n - 1 - k) for k, x in enumerate(h)); wn = sum(d ** (n - 1 - k) for k in range(n))
                pvv = pr[prc] / pr['n'] if pr else None
                if pvv is not None: return (ws + Wv * pvv) / (wn + Wv)
                return ws / wn if wn else None
            p_ = pv.loc[g] if g in pv.index else pd.Series(0, index=pv.columns)
            r = G.iloc[i]
            rows.append(dict(season=season, w=w, g=g, pos=P_, it=IT.get((r.team_, w), np.nan),
                             patt=vol('attempts', 'att') if P_ == 'QB' else None, car=vol('carries', 'car') or 0.0, tg=vol('targets', 'tg') or 0.0, recv=vol('receptions', 'rec') or 0.0,
                             c_att=float(H.attempts.sum()), c_cmp=float(H.completions.sum()), c_int=float(H.passing_interceptions.sum()), c_car=float(H.carries.sum()), c_tg=float(H.targets.sum()), c_td=float(H.td.sum()),
                             p_att=float(p_.attempts), p_cmp=float(p_.completions), p_int=float(p_.passing_interceptions), p_car=float(p_.carries), p_tg=float(p_.targets), p_td=float(p_.td),
                             a_att=float(r.attempts), a_cmp=float(r.completions), a_int=float(r.passing_interceptions), a_car=float(r.carries), a_tg=float(r.targets), a_rec=float(r.receptions),
                             a_td=float(r.td), a_td1=float(H1.get((g, w), 0))))
    return pd.DataFrame(rows)


def calib(p, y, n=5):
    o = pd.DataFrame({'p': p, 'y': y}).sort_values('p'); o['b'] = pd.qcut(o.p, n, labels=False, duplicates='drop')
    return [[round(float(g.p.mean()), 3), round(float(g.y.mean()), 3), int(len(g))] for _, g in o.groupby('b')]


if __name__ == '__main__':
    X = pd.concat([build(2025), build(2026)], ignore_index=True)
    X['cmpv'] = [a * FL.cmp_rate(c, ca, p, pa) if a else None for a, c, ca, p, pa in zip(X.patt, X.c_cmp, X.c_att, X.p_cmp, X.p_att)]
    R = {'note': __doc__.split('\n\n')[0], 'n': X.groupby('season').size().astype(int).to_dict(), 'lines': {}, 'rules': {}}
    print('rows', R['n'])
    MKT = {'patt': ('patt', 'a_att', 'QB', 20), 'cmp': ('cmpv', 'a_cmp', 'QB', 12), 'car': ('car', 'a_car', None, 2), 'tg': ('tg', 'a_tg', None, 2.5)}
    # ---- 1. real week-7 lines
    RL = json.load(open(os.path.join(PR, 'real_lines_2026_w7_more.json')))
    X7 = X[(X.season == 2026) & (X.w == 7)]; have = set(X7.g)
    for k, (col, act, ps, mn) in MKT.items():
        out = {}
        rows = []
        for n, v in (RL.get(k) or {}).items():
            g = next((g for g in BYNAME.get(norm(n), []) if g in have), None)
            if not g: continue
            m = X7[X7.g == g][col].iloc[0]
            if m is not None and m == m and m >= mn: rows.append((n, float(m), (v[0] + v[2]) / 2, v[0], v[2]))
        if len(rows) >= 8:
            m = np.array([r[1] for r in rows]); y = np.array([r[2] for r in rows])
            fits = {'flat': lambda mm, yy: {'k': 1.0}, 'k': lambda mm, yy: {'k': round(float(np.median(yy / mm)), 4)},
                    'ab': lambda mm, yy: dict(zip(('a', 'b'), [round(float(z), 4) for z in np.polyfit(mm, yy, 1)]))}
            ln = lambda rule, x: fl(rule['k'] * x) if 'k' in rule else fl(rule['a'] * x + rule['b'])
            best = None
            for nm, f_ in fits.items():
                pred = [ln(f_(np.delete(m, i), np.delete(y, i)), m[i]) for i in range(len(m))]
                gap = float(np.mean(np.abs(np.array(pred) - y))); inr = int(sum(lo <= p <= hi for p, (*_, lo, hi) in zip(pred, rows)))
                out[f'rule_{nm}'] = {'gap_leave_one_out': round(gap, 2), 'inside_books_range': inr, 'n': len(rows)}
                if best is None or gap < best[0] - .02: best = (gap, nm, f_(m, y))
            R['rules'][k] = best[2]; out['rule'] = best[2]; out['books_range_width'] = round(float(np.mean([hi - lo for *_, lo, hi in rows])), 2)
        R['lines'][k] = out
    t25 = X[(X.season == 2025) & (X.tg >= MKT['tg'][3])]; best = None
    for kk in np.arange(.80, 1.21, .005):
        ov = float((t25.a_tg > np.floor(kk * t25.tg) + .5).mean())
        if best is None or abs(ov - .414) < abs(best[1] - .414): best = (round(float(kk), 3), ov)
    R['rules']['tg'] = {'k': best[0]}; R['lines']['tg'] = {'rule': R['rules']['tg'], 'note': "no real lines: books rarely post targets; set so 2025 overs hit like receptions' (41.4%)"}
    # ---- 2. over rates at those lines
    for k, rule in R['rules'].items():
        col, act, ps, mn = MKT[k]; d = X[X[col].notna()]; d = d[d[col] >= mn]
        if ps: d = d[d.pos == ps]
        d = d.assign(line=[max(.5, fl(rule['k'] * x) if 'k' in rule else fl(rule['a'] * x + rule['b'])) for x in d[col]])
        R['lines'][k]['over'] = {str(s): {'n': int((d.season == s).sum()), 'over': round(float((d[d.season == s][act] > d[d.season == s].line).mean()), 3)} for s in (2025, 2026)}
        R['lines'][k]['over_pooled'] = round(float((d[act] > d.line).mean()), 3)
        print(k, json.dumps(R['lines'][k]))
    # ---- 3. interceptions
    QB = X[(X.pos == 'QB') & (X.patt >= 20) & (X.a_att >= 10)].copy()
    QB['ir'] = [FL.int_rate(a, b, c, d) for a, b, c, d in zip(QB.c_int, QB.c_att, QB.p_int, QB.p_att)]
    def int_out(sc):
        o = {}
        for s in (2025, 2026):
            d = QB[QB.season == s]; lam = sc * d.patt * d.ir; p1 = 1 - np.exp(-lam); y = (d.a_int >= 1).astype(float)
            o[str(s)] = {'n': int(len(d)), 'predicted_any': round(float(p1.mean()), 3), 'actual_any': round(float(y.mean()), 3),
                         'brier': round(float(((p1 - y) ** 2).mean()), 4), 'brier_flat': round(float(((y.mean() - y) ** 2).mean()), 4), 'by_fifths': calib(p1, y)}
        return o
    d25 = QB[QB.season == 2025]
    sc = minimize_scalar(lambda s: float((s * d25.patt * d25.ir - d25.a_int * np.log(s * d25.patt * d25.ir)).sum()), bounds=(.5, 1.5), method='bounded').x
    R['int'] = {'scale_before': FL.INTM['sc'], 'with_old_scale': int_out(FL.INTM['sc']), 'scale_refit_2025': round(float(sc), 3), 'with_refit': int_out(sc)}
    print('int', json.dumps({k: v for k, v in R['int'].items()}))
    # ---- touchdowns
    TP = X[(X.car + np.where(X.pos == 'QB', 0, X.tg)) >= 1.5].copy()
    TP['lam'] = [FL.td_rate(p, c, t, (it if it == it else 22.0), cc, ct, ctd, pc, pt, ptd) for p, c, t, it, cc, ct, ctd, pc, pt, ptd in
                 zip(TP.pos, TP.car, TP.tg, TP.it, TP.c_car, TP.c_tg, TP.c_td, TP.p_car, TP.p_tg, TP.p_td)]
    def td_out(sc):
        o = {}
        for s in (2025, 2026):
            d = TP[TP.season == s]; lam = sc * d.lam; p1 = 1 - np.exp(-lam); y = (d.a_td >= 1).astype(float)
            hh = d.pos.map(FL.H1).values; ph = 1 - np.exp(-lam * hh); yh = (d.a_td1 >= 1).astype(float)
            o[str(s)] = {'n': int(len(d)), 'anytime': {'predicted': round(float(p1.mean()), 3), 'actual': round(float(y.mean()), 3), 'brier': round(float(((p1 - y) ** 2).mean()), 4),
                                                      'brier_flat_by_position': round(float(((d.pos.map(y.groupby(d.pos).mean()) - y) ** 2).mean()), 4), 'by_fifths': calib(p1, y)},
                         'first_half': {'predicted': round(float(ph.mean()), 3), 'actual': round(float(yh.mean()), 3), 'brier': round(float(((ph - yh) ** 2).mean()), 4)}}
        return o
    t25 = TP[TP.season == 2025]
    tsc = minimize_scalar(lambda s: float((s * t25.lam - t25.a_td * np.log(np.maximum(s * t25.lam, 1e-6))).sum()), bounds=(.5, 1.5), method='bounded').x
    R['td'] = {'with_old_scale': td_out(1.0), 'scale_refit_2025': round(float(tsc), 3), 'with_refit': td_out(tsc)}
    print('td', json.dumps(R['td']))
    # ---- 4. spread of outcomes around BFF's volume
    R['spread'] = {}
    for k, (col, act, ps, mn) in MKT.items():
        d = X[X[col].notna()]; d = d[d[col] >= mn]
        if ps: d = d[d.pos == ps]
        R['spread'][k] = {'n': int(len(d)), 'q': [round(float(v), 3) for v in np.quantile(d[act] / d[col], np.arange(.05, .951, .05))]}
    json.dump(R, open(os.path.join(BT, 'results_props_bff.json'), 'w'), indent=1)
    print('spread', json.dumps(R['spread']))
