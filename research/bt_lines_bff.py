"""BFF research (November 2026): BFF's own prop lines, from BFF's numbers only, against real posted lines.

Since November 2026 BFF uses no ESPN or Sleeper projections, so every line is a model line (ff_lines.py: expected volume x
efficiency x this game, times a fixed factor, rounded down to .5). This measures how far those lines sit from the lines
books really posted for week 7 of 2026, and tests whether a second step fit to the real lines brings them closer:
passing yards a x model line + c x his season average + d x model line x (implied team total / 22 - 1) + b; rushing yards
a x model line + c x season average + b; receptions a x model line + b; receiving yards k x model line. Every step is
scored on players it never saw (leave one out) and adopted only when it beats the plain model line on BOTH samples.

Samples: A = one book's lines read Oct 21-23 (research/props/real_lines_2026_w7.json); B = Sunday Oct 25, each player's
lowest and highest line across books (real_lines_2026_w7_sun.json; scored against the middle, and how many fall inside).
BFF's lines: research/props/bff_lines_2026_w7_before.json, the model lines BFF published on Oct 24 (01:15 UTC), before
any line used another site's projection; ff_lines.py builds its model lines the same way today (rebuilt from the Oct 25
data: receptions identical, receiving and rushing yards within a yard on average). Both samples are scored against these.
A correction: the first version of this study (Nov 2) scored sample B against the lines BFF had published that Sunday,
which were the market lines built from ESPN's and Sleeper's projections, not BFF's own, and fit the passing-yard step on
them; this version uses BFF's own model lines on both samples.
For comparison it reads the market rule's leave-one-out gaps from research/results_lines.json (what BFF used until
November 2026). Names are matched through nflverse's player table (player_ids.csv).
python research/bt_lines_bff.py   (writes research/results_lines_bff.json; seconds)"""
import os, sys, json, math, re, unicodedata, numpy as np, pandas as pd
BT = os.path.dirname(os.path.abspath(__file__)); RUN = os.path.dirname(BT); os.chdir(os.environ.get('BT_DATA') or RUN)
PR = os.path.join(BT, 'props')
MK = ('py', 'ty', 'ry', 'rec')
COLS = {'py': 'passing_yards', 'ty': 'receiving_yards', 'ry': 'rushing_yards', 'rec': 'receptions'}
FEAT = {'py': ['mk', 'sa', 'mkit'], 'ry': ['mk', 'sa'], 'rec': ['mk'], 'ty': None}
fl = lambda v: max(.5, math.floor(v) + .5)
norm = lambda s: re.sub(r'[^a-z]', '', re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', unicodedata.normalize('NFKD', str(s)).lower().replace('.', '')))


def feats(mk, sa, it):
    sa = mk if sa is None or (isinstance(sa, float) and math.isnan(sa)) else sa; it = 22.0 if it is None else it
    return {'mk': mk, 'sa': sa, 'mkit': mk * (it / 22 - 1)}


def fit(rows, k):
    y = np.array([r[1] for r in rows], float)
    if FEAT[k] is None: m = np.array([r[0]['mk'] for r in rows], float); return {'k': round(float(np.median(y / m)), 4)}
    X = np.array([[r[0][f] for f in FEAT[k]] + [1.0] for r in rows], float); w, *_ = np.linalg.lstsq(X, y, rcond=None)
    out = {'a': round(float(w[0]), 4)}
    if 'sa' in FEAT[k]: out['c'] = round(float(w[FEAT[k].index('sa')]), 4)
    if 'mkit' in FEAT[k]: out['d'] = round(float(w[FEAT[k].index('mkit')]), 4)
    out['b'] = round(float(w[-1]), 3); return out


def line(rule, f):
    if 'k' in rule: return fl(rule['k'] * f['mk'])
    return fl(rule['a'] * f['mk'] + rule.get('c', 0) * f['sa'] + rule.get('d', 0) * f['mkit'] + rule['b'])


if __name__ == '__main__':
    A = json.load(open(os.path.join(PR, 'real_lines_2026_w7.json'))); B = json.load(open(os.path.join(PR, 'real_lines_2026_w7_sun.json')))
    OWN = json.load(open(os.path.join(PR, 'bff_lines_2026_w7_before.json')))
    BL = {(l['pid'], l['k']): l for l in OWN['lines']}
    ids = pd.read_csv('player_ids.csv', low_memory=False)
    BYNAME = {}
    for g, n in zip(ids.gsis_id, ids.name):
        if isinstance(g, str) and isinstance(n, str): BYNAME.setdefault(norm(n), []).append(g)
    have = {pid for pid, _ in BL}
    find = lambda n: next((g for g in BYNAME.get(norm(n), []) if g in have), None)
    S26 = pd.read_parquet('stats_player_week_2026.parquet'); S26 = S26[(S26.season_type == 'REG') & (S26.week < 7)]
    SA26 = S26.groupby('player_id')[list(COLS.values())].mean()
    rows = []
    for smp, real in (('A', A), ('B', B)):
        for k in MK:
            for n, v in (real.get(k) or {}).items():
                g = find(n); b = BL.get((g, k)) if g else None
                if not b: continue
                lo, hi = (v if isinstance(v, list) else (None, None))
                mid = (lo + hi) / 2 if lo is not None else float(v)
                model = float(b['line'])   # the model line (no second step existed on Oct 24)
                sa = float(SA26.loc[g, COLS[k]]) if g in SA26.index else None
                rows.append((smp, k, g, feats(model, sa, b.get('it')), mid, lo, hi, fl(model), b['line']))
    X = pd.DataFrame(rows, columns=['smp', 'k', 'g', 'f', 'real', 'lo', 'hi', 'model', 'posted'])
    MR = json.load(open(os.path.join(BT, 'results_lines.json')))['week7']
    R = {'note': __doc__.split('\n\n')[0], 'rule': {}, 'week7': {}, 'lines_at': OWN.get('at')}
    for k in MK:
        z = X[X.k == k].reset_index(drop=True)
        if not len(z): continue
        rule = fit(list(zip(z.f, z.real)), k)
        z['after'] = [line(fit(list(zip(z.f.drop(i), z.real.drop(i))), k), z.f[i]) for i in z.index]
        out = {'rule': rule, 'n': int(len(z))}
        for s_ in ('A', 'B'):
            q = z[z.smp == s_]
            if not len(q): continue
            d = {'n': int(len(q)), 'gap_model_line': round(float((q.model - q.real).abs().mean()), 2), 'bias_model_line': round(float((q.model - q.real).mean()), 2),
                 'gap_rule_leave_one_out': round(float((q.after - q.real).abs().mean()), 2),
                 'gap_market_rule_leave_one_out': (MR.get(k) or {}).get(s_, {}).get('gap_after_leave_one_out')}
            if s_ == 'B':
                d['inside_books_range'] = {'rule': int(((q.after >= q.lo) & (q.after <= q.hi)).sum()), 'model_line': int(((q.model >= q.lo) & (q.model <= q.hi)).sum())}
                d['books_range_width'] = round(float((q.hi - q.lo).mean()), 2)
            out[s_] = d
        out['adopted'] = all(out[s_]['gap_rule_leave_one_out'] < out[s_]['gap_model_line'] for s_ in ('A', 'B') if s_ in out) and 'A' in out and 'B' in out
        if out['adopted']: R['rule'][k] = rule
        R['week7'][k] = out
        print(k, json.dumps(out))
    # passing touchdowns: BFF's 0.5 / 1.5 / 2.5 lines against Sunday's main lines
    T = [(n, BL[(find(n), 'ptd')]['line'], v[0]) for n, v in (B.get('ptd') or {}).items() if find(n) and (find(n), 'ptd') in BL]
    R['week7']['ptd'] = {'n': len(T), 'match': sum(a == b for _, a, b in T), 'misses': [[n, a, b] for n, a, b in T if a != b],
                         'market_rule_match_leave_one_out': (MR.get('ptd') or {}).get('match_leave_one_out')}
    print('ptd', json.dumps(R['week7']['ptd']))
    json.dump(R, open(os.path.join(BT, 'results_lines_bff.json'), 'w'), indent=1)
