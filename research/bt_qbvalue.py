"""BFF research (Nov 2026): are quarterbacks over-valued in 1-QB leagues? A user saw Josh Allen (the best fantasy QB)
valued near Jaxon Smith-Njigba and the best players at other positions, while trade charts (12-team PPR 1QB) put the
top QB around the 11th-best receiver.
Scored on the same checkpoints and simulated-league truth as bt_value_v5.py (weeks 4-12 of 2023-2025, v5 projections,
lineups 1 QB, 2 RB, 2 WR, 1 TE, 1 flex). Two truths: (a) every team holds 2 QBs, 5 RBs, 6 WRs, 2 TEs (the original);
(b) closer to real 12-team leagues: half the teams hold one QB (they pick one up for byes and injuries), and a team
missing its starter that week starts the best quarterback nobody holds that week (streaming).
Variants (all on BFF's value curve; only quarterback handling changes):
  site     the spread of a week's points around his projection = 0.5 x R (R: the best player at his position who would not start)
  sabs     the spread from the measured weekly misses at each position (starters' standard deviation of points minus projection)
  qbrep_k  quarterbacks' replacement level raised to the k-th best quarterback who would not start (streaming)
Prints the rank correlation and R2 with the truth, the share of 2x-lopsided calls the truth agrees with, each
position's bias (truth minus value-implied truth, % of a top-50 player's truth; negative = valued too high) and the
QB-vs-others coin flip on near-equal values (50% = unbiased; below 50% = the QB is valued too high).
    python research/bt_qbvalue.py   -> research/results_qbvalue.json"""
import os, sys, pickle, random, json, numpy as np
from scipy.stats import spearmanr, norm
BT = os.path.dirname(os.path.abspath(__file__))
C = pickle.load(open(os.path.join(BT, 'value_checkpoints_v5.pkl'), 'rb'))
POS = ['QB', 'RB', 'WR', 'TE']; SLOTS = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1}; NT = 12; NL = 10
def lineup(players, cut, w, stream=None):
    av = [p for p in players if cut[p]['play'][w]]; tot = 0.0; used = set()
    for q, k in SLOTS.items():
        c = sorted([p for p in av if cut[p]['pos'] == q], key=lambda p: -cut[p]['mu'])[:k]
        if q == 'QB' and not c and stream: c = [stream[w]]
        for p in c: tot += cut[p]['y'][w]; used.add(p)
    fl = sorted([p for p in av if p not in used and cut[p]['pos'] != 'QB'], key=lambda p: -cut[p]['mu'])[:1]
    for p in fl: tot += cut[p]['y'][w]
    return tot
def simulate(cut, seed, real):
    rng = random.Random(seed); ids = list(cut)
    ranked = sorted([p for p in ids if cut[p]['ecr_o']], key=lambda p: cut[p]['ecr_o']); rest = sorted([p for p in ids if not cut[p]['ecr_o']], key=lambda p: -cut[p]['mu'])
    if len(ranked) < 150: ranked = sorted(ids, key=lambda p: -cut[p]['mu']); rest = []
    order = ranked + rest; mr = {p: i + 1 for i, p in enumerate(order)}
    noisy = sorted(ids, key=lambda p: mr[p] + rng.gauss(0, .15 * mr[p] + 3))
    comp = [dict(QB=(1 if (real and t % 2) else 2), RB=5, WR=6, TE=2) for t in range(NT)]
    teams = [[] for _ in range(NT)]; cnt = [{q: 0 for q in POS} for _ in range(NT)]; pool = list(noisy)
    for rnd in range(15):
        for t in (range(NT) if rnd % 2 == 0 else range(NT - 1, -1, -1)):
            if sum(cnt[t].values()) >= sum(comp[t].values()): continue
            for k, p in enumerate(pool):
                if cnt[t][cut[p]['pos']] < comp[t][cut[p]['pos']]: teams[t].append(p); cnt[t][cut[p]['pos']] += 1; pool.pop(k); break
    fa = {q: max([p for p in pool if cut[p]['pos'] == q], key=lambda p: cut[p]['mu']) for q in POS}
    W = len(cut[ids[0]]['play'])
    # streaming: the best-projected quarterback nobody holds who plays that week (one per week; projections are the
    # season level, so this is the best free agent on the field, not the luckiest)
    fq = sorted([p for p in pool if cut[p]['pos'] == 'QB'], key=lambda p: -cut[p]['mu'])
    stream = [next((p for p in fq if cut[p]['play'][w]), fq[0]) for w in range(W)] if real else None
    truth = {}
    for T in teams:
        base = sum(lineup(T, cut, w, stream) for w in range(W))
        for p in T:
            T2 = [x for x in T if x != p] + ([] if (real and cut[p]['pos'] == 'QB') else [fa[cut[p]['pos']]])
            truth[p] = base - sum(lineup(T2, cut, w, stream) for w in range(W))
    return truth
def posPart(d, s): z = d / s; return d * norm.cdf(z) + s * norm.pdf(z)
def levels(cut, comp=dict(QB=2, RB=5, WR=6, TE=2)):
    mb = {p: m['mu'] for p, m in cut.items()}; by = {q: sorted([p for p in cut if cut[p]['pos'] == q], key=lambda p: -mb[p]) for q in POS}
    cnt = {q: min(len(by[q]), NT * SLOTS[q]) for q in POS}
    rest = sorted([p for q in ('RB', 'WR', 'TE') for p in by[q][cnt[q]:]], key=lambda p: -mb[p])[:NT]
    for p in rest: cnt[cut[p]['pos']] += 1
    Rs = {q: mb[by[q][min(len(by[q]) - 1, cnt[q])]] for q in POS}
    Rw = {q: mb[by[q][min(len(by[q]) - 1, NT * comp[q])]] for q in POS}
    return Rs, Rw, by, cnt, mb
# measured weekly misses (points minus his projection) of players who would start, by position
MISS = {}
for q in POS:
    e = []
    for key, cut in C.items():
        Rs, *_ = levels(cut)
        for p, m in cut.items():
            if m['pos'] == q and m['mu'] >= Rs[q]: e += [y - m['mu'] for y, pl in zip(m['y'], m['play']) if pl]
    MISS[q] = float(np.std(e))
def val(cut, base, s_mode='rel', qbk=0, pm=None, rbk=0):
    Rs, Rw, by, cnt, mb = levels(cut); R = dict(Rs if base == 's' else Rw); out = {}
    if qbk: R['QB'] = mb[by['QB'][max(0, cnt['QB'] - qbk)]]   # a better quarterback as the replacement (streaming)
    if rbk and base == 's': R['RB'] = mb[by['RB'][min(len(by['RB']) - 1, cnt['RB'] + rbk)]]   # a deeper running back as the replacement (scarcity: injuries, fewer good ones)
    for p, m in cut.items():
        r = R[m['pos']]; s = max(.5, .5 * Rs[m['pos']]) if s_mode == 'rel' else MISS[m['pos']] * s_mode
        out[p] = sum(.98 * .985 ** h * posPart(m['mu'] - r, s) for h, pl in enumerate(m['play']) if pl) * ((pm or {}).get(m['pos'], 1))
    return out
def scale(V):
    top = sorted(V.values(), reverse=True)[:3]; ref = sum(top) / 3 or 1; return {p: 100 * v / ref for p, v in V.items()}
def blend(cut, **kw):
    A = scale(val(cut, 's', **kw)); B = scale(val(cut, 'w', **kw)); return {p: .85 * A[p] + .15 * B[p] for p in cut}
def metrics(Vf, TR):
    R2 = []; SP = []; bias = {q: [] for q in POS}; qb = []; dirs = []; top12 = []
    for key, cut in sorted(C.items()):
        V = scale(Vf(cut)); T = TR[key]; ps = [p for p in T if p in V]
        v = np.array([V[p] for p in ps]); t = np.array([T[p] for p in ps])
        R2.append(np.corrcoef(v, t)[0, 1] ** 2); SP.append(spearmanr(v, t).correlation)
        b = (v @ t) / (v @ v); top = np.sort(t)[-50:].mean()
        for q in POS:
            m_ = np.array([cut[p]['pos'] == q for p in ps])
            if m_.sum(): bias[q].append(float(np.mean(t[m_] - b * v[m_]) / top * 100))
        # the best QB's value relative to the 12th-best non-QB, by value and by truth
        # where the 3 best-valued QBs sit among everyone, by value and by truth (rank 1 = most valuable)
        qi = sorted([i for i, p in enumerate(ps) if cut[p]['pos'] == 'QB'], key=lambda i: -v[i])[:3]
        rv = {i: r + 1 for r, i in enumerate(np.argsort(-v))}; rt = {i: r + 1 for r, i in enumerate(np.argsort(-t))}
        top12.append((np.mean([rv[i] for i in qi]), np.mean([rt[i] for i in qi])))
        rng = random.Random(1); n = len(ps)
        for _ in range(4000):
            i, j = rng.randrange(n), rng.randrange(n)
            if i == j or min(v[i], v[j]) < 3: continue
            qi_, qj_ = cut[ps[i]]['pos'] == 'QB', cut[ps[j]]['pos'] == 'QB'
            if qi_ != qj_ and .9 <= v[i] / v[j] <= 1.1: qb.append((t[i] > t[j]) == qi_)
            if v[i] / v[j] >= 2 or v[j] / v[i] >= 2: dirs.append((v[i] > v[j]) == (t[i] > t[j]))
    return dict(rho=round(float(np.mean(SP)), 4), r2=round(float(np.mean(R2)), 4), dir_pct=round(100 * float(np.mean(dirs)), 1),
                qb_wins=round(float(np.mean(qb)), 3), qb_n=len(qb), bias={q: round(float(np.mean(bias[q])), 1) for q in POS},
                top3QB_rank_by_value=round(float(np.mean([a for a, _ in top12])), 1), top3QB_rank_by_truth=round(float(np.mean([b for _, b in top12])), 1))
if __name__ == '__main__':
    print('measured weekly misses (SD) of starters:', {q: round(v, 2) for q, v in MISS.items()}, flush=True)
    OUT = {'miss_sd': MISS}
    CACHE = os.environ.get('BFF_QBV_CACHE')
    TRS = pickle.load(open(CACHE, 'rb')) if CACHE and os.path.exists(CACHE) else {}
    for real in (False, True):
        TR = TRS.get(real) or {}
        if not TR:
            for key, cut in sorted(C.items()):
                acc = {}
                for L in range(NL):
                    for p, v in simulate(cut, hash((key, L, real)) % 10 ** 6, real).items(): acc.setdefault(p, []).append(v)
                TR[key] = {p: float(np.mean(v)) for p, v in acc.items() if len(v) >= NL // 2}
            TRS[real] = TR
            if CACHE: pickle.dump(TRS, open(CACHE, 'wb'))
        name = 'truth (b): real rosters, streaming' if real else 'truth (a): 2 QBs a team'
        OUT[name] = {}
        VARS = [('site: spread 0.5 x R', lambda c: blend(c)), ('measured spread x0.6', lambda c: blend(c, s_mode=.6))] + \
               [(f'QB replacement {k} better', (lambda k: lambda c: blend(c, qbk=k))(k)) for k in (1, 2, 3, 4, 6)] + \
               [(f'QB x{m}', (lambda m: lambda c: blend(c, pm={'QB': m}))(m)) for m in (.85, .7, .6, .5)] + \
               [(f'QB replacement {k} better, x{m}', (lambda k, m: lambda c: blend(c, qbk=k, pm={'QB': m}))(k, m)) for k, m in ((6, .85), (6, .75), (6, .7), (8, .8), (10, 1), (10, .8))]
        for lab, f in VARS:
            OUT[name][lab] = metrics(f, TR); print(name, '|', lab, OUT[name][lab], flush=True)
    json.dump(OUT, open(os.path.join(BT, 'results_qbvalue.json'), 'w'), indent=1)
