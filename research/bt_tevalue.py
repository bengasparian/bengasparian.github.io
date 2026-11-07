"""BFF research (Nov 2026): are tight ends under-valued? A user felt Brock Bowers, Trey McBride and George Kittle should be
worth more because good tight ends are scarce, without over-valuing tight ends in general.
Same checkpoints and simulated-league truths as bt_qbvalue.py (weeks 4-12 of 2023-2025; truth (a) 2 QBs a team, truth
(b) real rosters with streaming), starting from the live rule (1-QB quarterbacks x0.85 against a better replacement,
running backs x1.1). Variants: every tight end x m (1.05 to 1.3: all LESS accurate, not used), and the k best tight ends
by value x m with the others x r, scored overall and season by season. Kept: the 3 best x1.1, the others x0.95 (more
accurate overall on both truths and in 2024 and 2025; 2023 about even).
    BFF_QBV_CACHE=<truths.pkl from bt_qbvalue.py> python research/bt_tevalue.py   -> research/results_tevalue.json"""
import sys, pickle, json, numpy as np
import os
BT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BT); sys.argv = ['x']
import bt_qbvalue as Q
TRS = pickle.load(open(os.environ['BFF_QBV_CACHE'], 'rb'))   # the simulated-league truths bt_qbvalue.py saves
LIVE = {'QB': .85, 'RB': 1.1}
def rule(k, m, r=1.0):
    def f(c):
        V = Q.blend(c, qbk=6, pm=dict(LIVE)); tes = sorted([p for p in c if c[p]['pos'] == 'TE'], key=lambda p: -V[p])
        top = set(tes[:k]); rest = set(tes[k:])
        return {p: v * (m if p in top else r if p in rest else 1) for p, v in V.items()}
    return f
ALL = dict(Q.C)
def by_season(f, TR):
    out = {}
    for y in (2023, 2024, 2025):
        Q.C = {k: v for k, v in ALL.items() if k[0] == y}
        m = Q.metrics(f, TR); out[y] = (m['rho'], m['r2'], m['dir_pct'])
    Q.C = dict(ALL); return out
V = [('live', rule(0, 1))] + [(f'every TE x{m}', rule(999, m)) for m in (1.05, 1.1, 1.2, 1.3)] + [(f'top {k} x{m}' + (f', rest x{r}' if r != 1 else ''), rule(k, m, r)) for k, m, r in
     ((3, 1.1, 1), (3, 1.2, 1), (3, 1.3, 1), (2, 1.2, 1), (4, 1.2, 1), (3, 1.2, .95), (3, 1.2, .9), (3, 1.1, .95))]
OUT = {}
for real in (False, True):
    for lab, f in V:
        m = Q.metrics(f, TRS[real]); s = by_season(f, TRS[real]); OUT[('B ' if real else 'A ') + lab] = dict(all=m, seasons=s)
        print('B' if real else 'A', lab, '| all', m['rho'], m['r2'], m['dir_pct'], 'TE bias', m['bias']['TE'], '| by season', s, flush=True)
json.dump({k: {'all': v['all'], 'seasons': {str(y): x for y, x in v['seasons'].items()}} for k, v in OUT.items()}, open(os.path.join(BT, 'results_tevalue.json'), 'w'), indent=1)
