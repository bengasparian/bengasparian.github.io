"""BFF research (Nov 2026): the "recent form" formula a user asked for, tested on rest-of-season order.
Recent form = this season's games with the latest weighted most (half-life 2 or 3 games), optionally each game capped at
max(1.6 x his median, median + 8) so one blow-up game counts less (consistency), weighted n/(n+4) against his track
record (0.7 x last season + 0.3 x the season before, 4+ games each). Scored like the value backtest: at weeks 4, 6, 8, 10,
12 of 2023-2025, Spearman rank correlation of each source with the points a game he really scored the rest of the season
(players projected 6+), by position, and mean absolute error. Inputs: value_checkpoints_v5.pkl (the model's rest-of-season
level, experts' ranks, the games that followed) and h_weekly_v5.parquet (every game's points).
Result: the formula alone is much worse than BFF's model at every position; a 15% blend helps quarterbacks in every
season (0.625 -> 0.638) and is mixed or worse for RB, WR and TE, so the site uses it for quarterbacks only.
    python research/bt_recency.py   -> research/results_recency.json"""
import pickle, numpy as np, pandas as pd
from scipy.stats import spearmanr
C=pickle.load(open('value_checkpoints_v5.pkl','rb'))
h=pd.read_parquet('h_weekly_v5.parquet').sort_values(['player_id','season','week'])
h=h[h.y.notna()]
seas=h.groupby(['player_id','season']).y.agg(['mean','size','median'])
def feats(S,N):
    hh=h[(h.season==S)&(h.week<N)]
    out={}
    for pid,g in hh.groupby('player_id'):
        y=g.y.values.astype(float); n=len(y)
        med=np.median(y)
        cap=np.minimum(y, max(med*1.6, med+8))            # consistency: a blow-up game counts only up to ~1.6x his usual
        out[pid]=dict(n=n,mean=y.mean(),med=med,
                      ew2=np.average(y,weights=0.5**((n-1-np.arange(n))/2)),
                      ew3=np.average(y,weights=0.5**((n-1-np.arange(n))/3)),
                      ew2c=np.average(cap,weights=0.5**((n-1-np.arange(n))/2)),
                      ew3c=np.average(cap,weights=0.5**((n-1-np.arange(n))/3)),
                      sd=y.std())
    return out
rows=[]
for (S,N),cut in C.items():
    F=feats(S,N)
    for pid,m in cut.items():
        play=np.array(m['play']); y=np.array(m['y'])
        if play.sum()<3: continue
        f=F.get(pid,{}); p1=seas.loc[(pid,S-1)] if (pid,S-1) in seas.index else None; p2=seas.loc[(pid,S-2)] if (pid,S-2) in seas.index else None
        prev=p1['mean'] if p1 is not None and p1['size']>=4 else np.nan
        prev2=p2['mean'] if p2 is not None and p2['size']>=4 else np.nan
        rows.append(dict(S=S,N=N,pos=m['pos'],mu=m['mu'],ecr=m.get('ecr_p'),fut=y[play].mean(),prev=prev,prev2=prev2,**{k:f.get(k,np.nan) for k in ('n','mean','med','ew2','ew3','ew2c','ew3c','sd')}))
R=pd.DataFrame(rows); OUT = {}
def rk(d,col,sgn=1): return np.nanmean([spearmanr(sgn*x[col],x.fut,nan_policy='omit').correlation for _,x in d.groupby(['S','N']) if len(x)>10])
def mae(d,col): return float(np.nanmean(np.abs(d[col]-d.fut)))
for pos in ('RB','WR','TE','QB'):
    d=R[(R.pos==pos)&(R.mu>=6)].copy()
    # track record: last season, then two seasons ago, shrunk toward this season when missing
    tr=np.where(d.prev.notna(), np.where(d.prev2.notna(), .7*d.prev+.3*d.prev2, d.prev), np.nan)
    d['track']=tr
    for name,cur in (('ew2',d.ew2),('ew3',d.ew3),('ew2c',d.ew2c),('ew3c',d.ew3c)):
        cur=cur.fillna(d.mu)
        # the user's formula: recent form (consistency-capped) weighted with the track record by games played
        k=d.n.fillna(0)/(d.n.fillna(0)+4)
        d['F_'+name]=np.where(d.track.notna(), k*cur+(1-k)*d.track, cur)
    res=[f"{pos} n={len(d)}  model {rk(d,'mu'):.4f}/{mae(d,'mu'):.2f}  experts {rk(d[d.ecr.notna()],'ecr',-1):.4f}"]
    for c in ('F_ew2','F_ew3','F_ew2c','F_ew3c'): res.append(f"{c} {rk(d,c):.4f}/{mae(d,c):.2f}")
    for a in (.15,.3,.5):
        d['B']=(1-a)*d.mu+a*d.F_ew3c; res.append(f"model+{a}*F_ew3c {rk(d,'B'):.4f}/{mae(d,'B'):.2f}")
    print(' | '.join(res)); OUT[pos] = res
import json; json.dump(OUT, open('results_recency.json', 'w'), indent=1)
