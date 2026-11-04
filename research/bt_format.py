"""BFF research: half PPR and standard projections from the PPR projection. Two ways to take the catches out:
  A. the site until Nov 2026: his catches a game so far this season (last season's before his first game), scaled by
     his projection over his points a game so far (kept between 0.5x and 1.5x);
  B. the catches BFF's own stat-by-stat model projects for that game (the same model whose catches are already inside
     the PPR projection, so the two always agree).
Each season 2023-2025 is predicted by models trained only on the seasons before it (the site's ff_model.py, one seed),
from the feature cache ff_produce.py keeps (.cache/f5_<season>_<year>.parquet). Scored against what really happened
(half PPR = PPR points - 0.5 x catches; standard = PPR points - catches): mean absolute error and the rank correlation
within each week and position (players projected 5+ points), for RB, WR and TE.
    python research/bt_format.py      (about 15 minutes) -> research/results_format.json"""
import os, sys, glob, json, time, numpy as np, pandas as pd
from scipy.stats import spearmanr
BT = os.path.dirname(os.path.abspath(__file__)); RUN = os.path.dirname(BT); os.chdir(RUN); sys.path.insert(0, RUN)
import ff_model as FM
t0 = time.time()
files = sorted(glob.glob('.cache/f5_*_*.parquet')); last = max(int(f.split('_')[1]) for f in files)
D = pd.concat([pd.read_parquet(f) for f in files if int(f.split('_')[1]) == last], ignore_index=True)
FC = [c for c in D.columns if c not in ['passing_yards', 'passing_tds', 'passing_interceptions', 'rushing_yards', 'rushing_tds', 'receptions', 'receiving_yards', 'receiving_tds']]
prev_rec = D.groupby(['player_id', 'season']).receptions.mean()   # catches a game, by season (for A before his first game)
OUT = {}; rows = []
for S in (2023, 2024, 2025):
    M = FM.Model(D[D.season < S], FC, seeds=1, ros=False)
    for pos in ('RB', 'WR', 'TE'):
        t = D[(D.season == S) & (D.pos == pos)].copy()
        if not len(t): continue
        t['v'] = M.next(pos, t); t['xrec'] = M.parts(pos, t)['receptions']
        pr = pd.Series([prev_rec.get((p, S - 1), np.nan) for p in t.player_id], index=t.index)
        t['rpg'] = np.where(t.g > 0, t.m_rec, pr); t['rpg'] = t.rpg.fillna(0)
        k = np.where(t.m_fp > 3, np.clip(t.v / t.m_fp.where(t.m_fp > 3, 1), .5, 1.5), 1.0)
        t['catchA'] = t.rpg * np.where(t.g > 0, k, 1.0); t['catchB'] = t.xrec
        rows.append(t[['player_id', 'season', 'week', 'pos', 'y', 'receptions', 'v', 'catchA', 'catchB', 'g']])
    print(S, 'done', round(time.time() - t0), 's', flush=True)
R = pd.concat(rows, ignore_index=True)
def score(d, pred, truth):
    mae = float(np.mean(np.abs(truth - pred)))
    q = d.assign(p_=pred, t_=truth); q = q[q.v >= 5]
    rk = float(np.nanmean([spearmanr(x.p_, x.t_).correlation for _, x in q.groupby(['season', 'week', 'pos']) if len(x) > 8]))
    return round(mae, 4), round(rk, 4)
for fmt, kk in (('half', .5), ('std', 1.0)):
    for pos in ('RB', 'WR', 'TE', 'all'):
        d = R if pos == 'all' else R[R.pos == pos]
        truth = d.y - kk * d.receptions
        a = score(d, np.maximum(0, d.v - kk * d.catchA), truth); b = score(d, np.maximum(0, d.v - kk * d.catchB), truth)
        OUT.setdefault(fmt, {})[pos] = {'n': int(len(d)), 'A_site_until_nov_2026': {'mae': a[0], 'rank': a[1]}, 'B_model_catches': {'mae': b[0], 'rank': b[1]},
                                        'by_season_mae': {str(s): [score(x, np.maximum(0, x.v - kk * x.catchA), x.y - kk * x.receptions)[0], score(x, np.maximum(0, x.v - kk * x.catchB), x.y - kk * x.receptions)[0]] for s, x in d.groupby('season')}}
        print(fmt, pos, OUT[fmt][pos], flush=True)
OUT['catch_error'] = {'A_mae': round(float(np.mean(np.abs(R.receptions - R.catchA))), 4), 'B_mae': round(float(np.mean(np.abs(R.receptions - R.catchB))), 4),
                      'A_bias': round(float(np.mean(R.catchA - R.receptions)), 4), 'B_bias': round(float(np.mean(R.catchB - R.receptions)), 4)}
print('catches:', OUT['catch_error'])
json.dump(OUT, open(os.path.join(BT, 'results_format.json'), 'w'), indent=1)
