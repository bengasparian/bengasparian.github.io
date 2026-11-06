"""BFF research (Nov 2026): does BFF's model under-project players who keep scoring far above it? A user saw Jaxon
Smith-Njigba (27.5 points a game over 8 games, the most of any receiver; 21.2 a game last season) projected 18.4, below
receivers scoring less on every measure. Gradient-boosted trees cannot go past the highest outcomes they were trained
on (each leaf holds 150+ games), so the very top gets squeezed toward the middle.
Tested on the value backtest's checkpoints (weeks 4, 6, 8, 10, 12 of 2023-2025; the model's rest-of-season level `mu`
at that point and the points a game he really scored after it), players projected 6+ with 4+ games:
  up_a     mu + a x max(0, season average - mu) x n/(n+4)       (only players scoring above the model, n = games played)
  sym_a    mu + a x (season average - mu) x n/(n+4)
  upf_a    as up_a with recent form (latest games weighted most, half-life 3, one blow-up game capped) for the average
  both_a   mu + a x max(0, smaller of (season average - mu) and (last season's average - mu)) x n/(n+4): only players
           scoring above the model this season AND last season (a proven producer the trees squeeze toward the middle)
  proven   the rule the site uses (RB, WR, TE): mu + c x w x min(season gap, last season's gap), w = ramp(season gap
           from 3 to 5) x ramp(last season's gap from 0 to 1), c = 1 (below every leave-one-season-out estimate: 1.6,
           1.1, 1.1). Scored season by season on everyone and on the players it changes.
Each a is chosen on two seasons and scored on the third (leave one season out). Scores: rank correlation within each
checkpoint and position (all; and the top 24 by the model), mean absolute error.
    python research/bt_toptail.py   -> research/results_toptail.json"""
import os, json, numpy as np, pandas as pd
from scipy.stats import spearmanr
BT = os.path.dirname(os.path.abspath(__file__)); os.chdir(BT)
src = open('bt_recency.py').read(); ns = {}; exec(src[:src.index("R=pd.DataFrame(rows)")] + "R=pd.DataFrame(rows)\n", ns); R = ns['R']
R = R[(R.mu >= 6) & (R.n >= 4)].copy(); k = R.n / (R.n + 4)
def corr(d, col, top=None):
    out = []
    for _, x in d.groupby(['S', 'N']):
        if top: x = x.nlargest(top, 'mu')
        if len(x) > 8: out.append(spearmanr(x[col], x.fut).correlation)
    return float(np.mean(out))
def variant(d, kind, a):
    kk = d.n / (d.n + 4)
    if kind == 'both': return d.mu + a * np.maximum(0, np.minimum(d['mean'] - d.mu, (d.prev - d.mu).fillna(-99))) * kk
    g = (d['mean'] if kind != 'upf' else d.ew3c.fillna(d['mean'])) - d.mu
    return d.mu + a * (np.maximum(0, g) if kind in ('up', 'upf') else g) * kk
OUT = {}
for pos in ('WR', 'RB', 'TE', 'QB'):
    d = R[R.pos == pos].copy(); res = {'n': int(len(d)), 'model': {'rank': round(corr(d, 'mu'), 4), 'rank_top24': round(corr(d, 'mu', 24), 4), 'mae': round(float(np.mean(np.abs(d.mu - d.fut))), 3)}}
    for kind in ('up', 'sym', 'upf', 'both'):
        grid = [0, .05, .1, .15, .2, .25, .3, .4, .5] + ([.6, .8, 1, 1.2, 1.5, 2] if kind == 'both' else []); folds = []; best_all = None
        for S in (2023, 2024, 2025):
            tr, te = d[d.S != S], d[d.S == S]
            sc = lambda a, x: corr(x.assign(v=variant(x, kind, a)), 'v') - .3 * float(np.mean(np.abs(variant(x, kind, a) - x.fut)))   # rank first, error second
            a = max(grid, key=lambda a: sc(a, tr)); v = variant(te, kind, a); x = te.assign(v=v)
            folds.append({'season': S, 'a': a, 'rank': round(corr(x, 'v'), 4), 'rank_model': round(corr(x, 'mu'), 4), 'rank_top24': round(corr(x, 'v', 24), 4), 'rank_top24_model': round(corr(x, 'mu', 24), 4),
                          'mae': round(float(np.mean(np.abs(v - x.fut))), 3), 'mae_model': round(float(np.mean(np.abs(x.mu - x.fut))), 3)})
        res[kind] = folds
    OUT[pos] = res; print(pos, json.dumps(res['model']))
    for kind in ('up', 'sym', 'upf', 'both'): print('  ', kind, [(f['season'], f['a'], f['rank'] - f['rank_model'], f['rank_top24'] - f['rank_top24_model'], f['mae'] - f['mae_model']) for f in res[kind]])
def proven(d, c=1.0):
    g1 = d['mean'] - d.mu; g2 = (d.prev - d.mu).fillna(-99)
    w = np.clip((g1 - 3) / 2, 0, 1) * np.clip(g2, 0, 1); return d.mu + c * w * np.maximum(0, np.minimum(g1, g2))
OUT['proven'] = {}
for pos in ('WR', 'RB', 'TE', ('RB', 'WR', 'TE')):
    d = R[R.pos.isin([pos] if isinstance(pos, str) else list(pos))].copy(); d['v'] = proven(d); ch = d[d.v > d.mu + .05]; key = pos if isinstance(pos, str) else 'RB+WR+TE'
    OUT['proven'][key] = {str(S): {'rank_all': [round(corr(x, 'mu'), 4), round(corr(x, 'v'), 4)], 'rank_top24': [round(corr(x, 'mu', 24), 4), round(corr(x, 'v', 24), 4)],
                                   'mae_all': [round(float(np.mean(np.abs(x.mu - x.fut))), 3), round(float(np.mean(np.abs(x.v - x.fut))), 3)],
                                   'changed_n': int((x.v > x.mu + .05).sum()), 'changed_mean_error': [round(float((x.fut - x.mu)[x.v > x.mu + .05].mean()), 2) if (x.v > x.mu + .05).any() else None,
                                                                                                      round(float((x.fut - x.v)[x.v > x.mu + .05].mean()), 2) if (x.v > x.mu + .05).any() else None]}
                             for S, x in d.groupby('S')}
    print('proven', key, json.dumps(OUT['proven'][key]))
json.dump(OUT, open('results_toptail.json', 'w'), indent=1)
