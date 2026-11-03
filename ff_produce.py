import os,json,io,urllib.request,datetime,sys
import pandas as pd, numpy as np
from scipy.stats import spearmanr
# data, features and the season (rolls forward on its own; see ff_build2.py)
from ff_build2 import (POS, SEASON, PHASE, EW_H, r, st, ids, SC, gm, prev, dvp_table, dvp_factor)
B='https://github.com/nflverse/nflverse-data/releases/download/'
def get(rel):
    with urllib.request.urlopen(B+rel,timeout=180) as r_: return pd.read_parquet(io.BytesIO(r_.read()))
def local_or(name,rel=None):
    """a data file fetch_data.py saved, else a download, else None (some files do not exist before the season starts)"""
    try:
        if os.path.exists(name): return pd.read_parquet(name)
        return get(rel) if rel else None
    except Exception as e: print('not available:',name,e); return None
# ---------------- the model (version 5; ff_feat.py builds the features, ff_model.py the trees). It learns from the 13
# completed seasons before this one; the latest of them is first predicted by models trained only on the seasons before it,
# which gives the accuracy, ranges and boom/bust spreads shown on the site. Completed seasons' features are cached.
import ff_feat as FX, ff_model as FM
NHIST=13; FIRST=SEASON-NHIST; XFPY=[FIRST-1,FIRST]; TEST=SEASON-1; TRAIN=list(range(FIRST,TEST)); HIST5=list(range(FIRST,SEASON))
CACHE='.cache'; FV='f5'; os.makedirs(CACHE,exist_ok=True)
_cf=lambda s_:f'{CACHE}/{FV}_{SEASON}_{s_}.parquet'; _rf=f'{CACHE}/{FV}_{SEASON}_xfp.json'
SCOL=['passing_yards','passing_tds','passing_interceptions','rushing_yards','rushing_tds','receptions','receiving_yards','receiving_tds']
WARM=all(os.path.exists(_cf(s_)) for s_ in HIST5) and os.path.exists(_rf)
if WARM:
    C5=FX.Ctx(sorted({SEASON-2,SEASON-1,SEASON}),XFPY,rates=json.load(open(_rf))); DH=pd.concat([pd.read_parquet(_cf(s_)) for s_ in HIST5],ignore_index=True)
else:
    C5=FX.Ctx(list(range(FIRST-1,SEASON+1)),XFPY); json.dump(C5.rates,open(_rf,'w')); parts_=[]
    for s_ in HIST5:
        d_=C5.season_rows(s_).merge(C5.st[['player_id','season','week']+SCOL].drop_duplicates(['player_id','season','week']),on=['player_id','season','week'],how='left')
        d_[SCOL]=d_[SCOL].fillna(0); d_.to_parquet(_cf(s_)); parts_.append(d_)
    DH=pd.concat(parts_,ignore_index=True)
FCOLS=[c for c in DH.columns if c not in SCOL]
print('training rows',{int(k):int(v) for k,v in DH.groupby('season').size().items()},'| features cached' if WARM else '| features built',flush=True)
res={}; RNG={}; QS={}
EV=FM.Model(DH[DH.season.isin(TRAIN)],FCOLS,seeds=1,ros=False); DTE=DH[DH.season==TEST]
for pos in POS:
    t=DTE[DTE.pos==pos]; pp=EV.next(pos,t); base_=FM.prep(t,EV.pr).b.values
    def sp(pred): return float(np.nanmean([spearmanr(x.pp,x.y).correlation for w,x in t.assign(pp=pred).groupby('week') if len(x)>8]))
    res[pos]={'n':int(len(t)),'mae_base':r(float(np.mean(np.abs(base_-t.y)))),'rank_base':r(sp(base_),3),'mae':r(float(np.mean(np.abs(pp-t.y)))),'rank':r(sp(pp),3),'model':'v5'}
    q=t.assign(pp=pp); q=q[q.pp>=5]; ratio=q.y/q.pp; RNG[pos]=[r(ratio.quantile(.1)),r(ratio.quantile(.9))]
    QS.setdefault(pos,{})
    for lo,hi in ((5,10),(10,15),(15,99)):
        qq=t.assign(pp=pp); qq=qq[(qq.pp>=lo)&(qq.pp<hi)]; rt=qq.y/qq.pp
        QS[pos][str(lo)]=[r(rt.quantile(k/20),3) for k in range(1,20)] if len(rt)>=60 else None
    print(pos,'test',TEST,res[pos],flush=True)
MODEL=FM.Model(DH,FCOLS,seeds=3,ros=False); POSAVG={p:float(v) for p,v in MODEL.pr.pavg.items()}
# a sample for the spreadsheet's 'BFF Formula' (a straight-line stand-in for the trees, fit to their projections):
# last completed season's rows, the model's projection and the inputs the spreadsheet can compute
try:
    _fr=[]
    for pos in POS:
        t=FM.prep(DTE[DTE.pos==pos],MODEL.pr); _fr.append(t.assign(model=MODEL.next(pos,DTE[DTE.pos==pos]))[['player_id','season','week','pos','y','model','g','b','be','bx','bxe','l1_fp','it','spread','total','dvp','home','e_snap','e_ts','e_cs','bump','qbm','q','prac','dc','pv','p_fp','p_g','m_fp','e_fp','m_xfp','e_xfp','ew']])
    pd.concat(_fr).to_parquet(f'{CACHE}/formula_rows.parquet')
except Exception as e_: print('formula sample skipped:',e_)
print('model trained on',min(HIST5),'-',max(HIST5),flush=True)
# ---------------- this season's state (falls back to last season's rosters and depth charts before the first game)
S26=st[st.season==SEASON]; LAST=int(S26.week.max()) if len(S26) else 0
wr=local_or(f'roster_weekly_{SEASON}.parquet',f'weekly_rosters/roster_weekly_{SEASON}.parquet')
if wr is None or not len(wr):
    wr=local_or(f'roster_{SEASON}.parquet')   # season roster (offseason moves, rookies) before weekly rosters exist
    if wr is not None and 'week' not in wr.columns: wr=wr.assign(week=0)
if wr is None or not len(wr): wr=local_or(f'roster_weekly_{SEASON-1}.parquet',f'weekly_rosters/roster_weekly_{SEASON-1}.parquet')
for _c in ('status_description_abbr','jersey_number','full_name','position','status','team'):
    if _c not in wr.columns: wr[_c]=None
wr=wr.dropna(subset=['gsis_id']).sort_values('week'); cur=wr.groupby('gsis_id').tail(1).set_index('gsis_id')
dc=local_or(f'depth_charts_{SEASON}.parquet',f'depth_charts/depth_charts_{SEASON}.parquet')
if dc is None or not len(dc) or 'dt' not in dc.columns: dc=local_or(f'depth_charts_{SEASON-1}.parquet',f'depth_charts/depth_charts_{SEASON-1}.parquet')
if dc is None or 'dt' not in getattr(dc,'columns',[]): dc=pd.DataFrame(columns=['dt','gsis_id','team','pos_abb','pos_rank','player_name'])
dc=dc[dc.dt==dc.dt.max()]
_INJC=['gsis_id','team','week','report_status','practice_status']
injall=local_or(f'injuries_{SEASON}.parquet',f'injuries/injuries_{SEASON}.parquet')
if injall is None or not len(injall): injall=pd.DataFrame(columns=_INJC)
for _c in ('report_primary_injury','full_name'):
    if _c not in injall.columns: injall[_c]=None
injfull=injall.copy()
injall=injall[injall.week==injall.groupby('team').week.transform('max')] if len(injall) else injall
inj=injall[injall.report_status.isin(['Out','Doubtful','Questionable'])]
injs=inj.drop_duplicates('gsis_id',keep='last').set_index('gsis_id')
def short_prac(v):
    v=str(v or ''); return 'DNP' if 'Did Not' in v else 'Limited' if 'Limited' in v else 'Full' if 'Full' in v else None
PRAC={r_.gsis_id:short_prac(r_.practice_status) for r_ in injall.itertuples() if short_prac(r_.practice_status)}
_pf=f'pbp_{SEASON}.parquet' if os.path.exists(f'pbp_{SEASON}.parquet') else f'pbp_{SEASON-1}.parquet'   # team pace: last season's until this one starts
P26=pd.read_parquet(_pf,columns=['week','posteam','play_type','qb_kneel','qb_spike','epa']); P26=P26[P26.play_type.isin(['pass','run'])&(P26.qb_kneel!=1)&(P26.qb_spike!=1)]
TV=P26.groupby(['posteam','week']).agg(pl=('epa','size'),pr=('play_type',lambda x:(x=='pass').mean())).groupby('posteam').mean()
RMAP={'QB':'QB','RB':'RB','HB':'RB','WR':'WR','LWR':'WR','RWR':'WR','SWR':'WR','TE':'TE'}   # fullbacks (FB) are not ranked as running backs
dc2=dc[dc.pos_abb.isin(RMAP)].copy(); dc2['pg']=dc2.pos_abb.map(RMAP); role=dc2.sort_values('pos_rank').drop_duplicates('gsis_id').set_index('gsis_id')
# pool: anyone with fantasy activity this season at QB/RB/WR/TE, plus depth-chart starters/backups (and, below, injured stars, this year's early-round rookies and returning starters)
pool={x for x in set(S26.player_id)|set(dc2[dc2.pos_rank<=(3)].gsis_id) if isinstance(x,str) and x}
info=st.sort_values(['season','week']).groupby('player_id').tail(1).set_index('player_id')
idx=ids.dropna(subset=['gsis_id']).drop_duplicates('gsis_id').set_index('gsis_id')
# ---- bio for the player card: height, weight, birth date, college, draft, experience (season roster, else last season's, else the ID table)
BIO={}
for _y in (SEASON-1,SEASON):
    _r=local_or(f'roster_{_y}.parquet',f'rosters/roster_{_y}.parquet')
    if _r is None or not len(_r): continue
    for _x in _r.dropna(subset=['gsis_id']).drop_duplicates('gsis_id',keep='last').itertuples():
        _b={}
        if pd.notna(getattr(_x,'height',None)): _b['ht']=int(float(_x.height))
        if pd.notna(getattr(_x,'weight',None)): _b['wt']=int(float(_x.weight))
        if isinstance(getattr(_x,'birth_date',None),str) and len(_x.birth_date)>=10: _b['bd']=_x.birth_date[:10]
        if isinstance(getattr(_x,'college',None),str) and _x.college.strip(): _b['col']=_x.college.split(';')[0].strip()
        if pd.notna(getattr(_x,'years_exp',None)): _b['exp']=int(_x.years_exp)+(SEASON-_y)
        if pd.notna(getattr(_x,'entry_year',None)): _b['ey']=int(_x.entry_year)
        if pd.notna(getattr(_x,'draft_number',None)): _b['dp']=int(_x.draft_number)
        if isinstance(getattr(_x,'draft_club',None),str) and _x.draft_club: _b['dc']=_x.draft_club
        if _b: BIO[_x.gsis_id]=_b
def bio_of(pid):
    b=dict(BIO.get(pid,{}))
    if pid in idx.index:
        x_=idx.loc[pid]
        if 'ht' not in b and pd.notna(x_.get('height')): b['ht']=int(float(x_['height']))
        if 'wt' not in b and pd.notna(x_.get('weight')): b['wt']=int(float(x_['weight']))
        if 'col' not in b and isinstance(x_.get('college'),str): b['col']=x_['college']
        if 'bd' not in b and isinstance(x_.get('birthdate'),str): b['bd']=x_['birthdate'][:10]
        if pd.notna(x_.get('draft_year')): b['dy']=int(x_['draft_year'])
        if pd.notna(x_.get('draft_round')): b['dr']=int(x_['draft_round'])
        if 'dp' not in b and pd.notna(x_.get('draft_ovr')): b['dp']=int(x_['draft_ovr'])
    return b or None
TODAY=datetime.date.fromisoformat(os.environ['BFF_AS_OF']) if os.environ.get('BFF_AS_OF') else datetime.date.today()
# also keep injured and reserve players who still matter (real production), e.g. on IR or PUP with no snaps this season
_pp1=st[st.season==SEASON-1].groupby('player_id').fantasy_points_ppr.agg(['mean','size']); _pp2=st[st.season==SEASON-2].groupby('player_id').fantasy_points_ppr.agg(['mean','size'])
def _relevant(pid):
    if pid in _pp1.index and _pp1.loc[pid,'size']>=4 and _pp1.loc[pid,'mean']>=7: return True
    return bool(pid in _pp2.index and _pp2.loc[pid,'size']>=6 and _pp2.loc[pid,'mean']>=9)
_extra={pid for pid,r_ in cur.iterrows() if r_.get('position') in POS and r_.get('status') in ('RES','ACT','INA') and pid not in pool and _relevant(pid)}
pool|=_extra
# this year's rookies drafted in the first 100 picks (in the offseason, before depth charts list them) and last season's
# fantasy starters on this season's roster (players who changed teams)
_rosp=set()
_R0=local_or(f'roster_{SEASON}.parquet')
if _R0 is not None and len(_R0) and 'gsis_id' in _R0.columns:
    for _x in _R0.dropna(subset=['gsis_id']).drop_duplicates('gsis_id',keep='last').itertuples():
        if getattr(_x,'position',None) not in POS: continue
        _dn=getattr(_x,'draft_number',None); _ey=getattr(_x,'entry_year',None)
        if (_ey==SEASON and _dn==_dn and _dn is not None and float(_dn)<=100) or _relevant(_x.gsis_id): _rosp.add(_x.gsis_id)
_rosp-=pool; pool|=_rosp
# players on no NFL roster now (released, retired, never signed) have no games to project: in season, a player counts
# only if the latest weekly roster has him with a team (active, reserve, inactive, practice squad or exempt list), or, when
# that week does not list him, the season roster does; the depth chart decides only for players neither roster has.
ONTEAM=('ACT','RES','INA','DEV','EXE')
FREE=set()
if PHASE=='season' and 'week' in wr.columns and len(wr) and int(wr.week.max())>0:
    _MW=int(wr.week.max()); _R26=local_or(f'roster_{SEASON}.parquet',f'rosters/roster_{SEASON}.parquet')
    _R26=_R26.dropna(subset=['gsis_id']).sort_values('week' if 'week' in _R26.columns else 'gsis_id').groupby('gsis_id').tail(1).set_index('gsis_id') if _R26 is not None and len(_R26) and 'gsis_id' in _R26.columns else None
    for pid_ in list(pool):
        if pid_ in cur.index and int(cur.at[pid_,'week'])==_MW: ok_=cur.at[pid_,'status'] in ONTEAM
        elif _R26 is not None and pid_ in _R26.index: ok_=_R26.at[pid_,'status'] in ONTEAM
        else: ok_=pid_ in set(dc2.gsis_id)
        if not ok_: FREE.add(pid_)
    pool-=FREE
print(f'player pool: {len(pool)} ({len(_extra)} injured or reserve players added back, {len(_rosp)} rookies or returning starters from the season roster, {len(FREE)} on no NFL roster left out)')
SC26=SC[SC.season==SEASON]; SCHED_KNOWN=len(SC26)>0
if not SCHED_KNOWN:   # offseason before the schedule is out: 17 games against opponents still to be announced
    _tm=sorted(SC[SC.season==SEASON-1].team.unique())
    SC26=pd.DataFrame([(SEASON,w_,t_,'TBD',np.nan,np.nan,np.nan) for t_ in _tm for w_ in range(1,18)],columns=SC.columns)
if SC26.pts.isna().sum()==0: print('Regular season complete: no unplayed games, keeping the current page.'); sys.exit(0)
NEXT=int(SC26[SC26.pts.isna()].week.min()); byes={}   # current NFL week = earliest week with an unplayed game
for t in SC26.team.unique():
    wk=set(SC26[SC26.team==t].week); byes[t]=[w for w in range(1,19) if w not in wk] if SCHED_KNOWN else []
RET={}; AIR=[.12,.24,.30,.35,.42,.47,.50,.52]
for pid_,G_ in wr[wr.gsis_id.isin(set(cur[cur.status=='RES'].index))].groupby('gsis_id'):
    G_=G_.sort_values('week'); st_=list(G_.status); wk_=list(G_.week); i_=len(st_)-1
    while i_>0 and st_[i_-1]=='RES': i_-=1
    RET[pid_]=max(NEXT+1,int(wk_[i_])+4)   # still on the list now, so next week at the earliest
RSV={pid_:('PUP' if str(x).startswith('P') else 'NFI' if str(x).startswith('N') else 'Suspended' if str(x).startswith('S') else 'IR') for pid_,x in cur[cur.status=='RES'].get('status_description_abbr',pd.Series(dtype=str)).items()}
IDT={'GBP':'GB','JAC':'JAX','KCC':'KC','LVR':'LV','NEP':'NE','NOS':'NO','SFO':'SF','TBB':'TB','LAR':'LA','RAM':'LA','WSH':'WAS'}
def team_of(pid):
    if pid in cur.index and cur.loc[pid,'status'] in ('ACT','RES','INA','DEV','EXE'): return cur.loc[pid,'team'],cur.loc[pid,'status']
    if pid in role.index: return role.loc[pid,'team'],'ACT'
    if pid in info.index and (info.loc[pid,'season']==SEASON or pid not in idx.index): return info.loc[pid,'team'],None
    if pid in idx.index and isinstance(idx.loc[pid,'team'],str) and idx.loc[pid,'status'] in ('ACT','RES','INA','DEV','EXE','PUP','RSR','RSN','SUS'): return IDT.get(idx.loc[pid,'team'],idx.loc[pid,'team']),None
    return (info.loc[pid,'team'] if pid in info.index else None),None
players=[]; prev_pg=prev; GDAY=dict(zip(gm.game_id,gm.gameday)); AVL={}; NOUSE={'RB':1.2,'WR':1.1,'TE':0.6}; NOU={}
# per-game stat mix for custom scoring: this season's games plus three games' worth of last season (or of his position's
# typical mix when he has no last season). Order: pass yd, pass TD, INT, pass 2pt, carries, rush yd, rush TD, receptions,
# rec yd, rec TD, rush/rec 2pt, passing first downs, rushing + receiving first downs, fumbles lost.
MXC=[('passing_yards',),('passing_tds',),('passing_interceptions',),('passing_2pt_conversions',),('carries',),('rushing_yards',),('rushing_tds',),
     ('receptions',),('receiving_yards',),('receiving_tds',),('rushing_2pt_conversions','receiving_2pt_conversions'),('passing_first_downs',),
     ('rushing_first_downs','receiving_first_downs'),('rushing_fumbles_lost','receiving_fumbles_lost','sack_fumbles_lost')]
def _comp(d):
    return pd.DataFrame({k:sum((d[c].fillna(0).astype(float) if c in d.columns else 0.0) for c in grp) for k,grp in enumerate(MXC)},index=d.index)
_c26=_comp(S26).assign(player_id=S26.player_id.values); _S25=st[st.season==SEASON-1]; _c25=_comp(_S25).assign(player_id=_S25.player_id.values,position=_S25.position.values,fp=_S25.fp.values)
MX_SUM=_c26.groupby('player_id').sum(); MX_G=_c26.groupby('player_id').size()
_g25=_c25.groupby('player_id'); MX_PREV=_g25[list(range(len(MXC)))].mean()[_g25.size()>=3]
MX_POS=_c25[_c25.fp>=5].groupby('position')[list(range(len(MXC)))].mean()
def mix_of(pid,pos):
    base=MX_PREV.loc[pid].values if pid in MX_PREV.index else (MX_POS.loc[pos].values if pos in MX_POS.index else np.zeros(len(MXC)))
    g_=int(MX_G.get(pid,0)); s_=MX_SUM.loc[pid].values if pid in MX_SUM.index else np.zeros(len(MXC))
    return [round(float(x),2) for x in (s_+3*base)/(g_+3)]
_GLC=['completions','attempts','passing_yards','passing_tds','passing_interceptions','carries','rushing_yards','rushing_tds','receptions','targets','receiving_yards','receiving_tds']
_g=S26.copy()
for _c in _GLC+['sack_fumbles_lost','rushing_fumbles_lost','receiving_fumbles_lost']:
    if _c not in _g.columns: _g[_c]=0
_g['_fl']=_g[['sack_fumbles_lost','rushing_fumbles_lost','receiving_fumbles_lost']].fillna(0).sum(axis=1)
GL={pid:[[int(x['week'])]+[int(round(float(x[c] or 0))) for c in _GLC]+[int(x['_fl'])] for _,x in grp.sort_values('week').iterrows()] for pid,grp in _g.fillna(0).groupby('player_id')}
# ---- injury status for each player's next game. 2021-25 reports vs who really played (QB/RB/WR/TE who played 3+ games):
# Doubtful played 0.4% of the time, Questionable 61%; out last week and not practicing this week (before game statuses
# are set) 1.3%, limited 40%, full 74%. After an Out (not injured reserve), availability relative to healthy players was
# 39% the next week, 69% after two weeks, 85% after three and about 90% later (OUTA).
OUTA=[.39,.69,.85,.9]
# Questionable and then inactive (2021-25, n=558): 52.5% played the team's next game and 62.5% the one after, against 29%
# and 46% after an Out, so relative to healthy players about 0.7 and 0.9 (QINA)
QINA=[.7,.9,.9,.9]
NXW={t_:int(G_[G_.pts.isna()].week.min()) for t_,G_ in SC26.groupby('team') if G_.pts.isna().any()}
KD={}
for _g in gm[gm.season==SEASON].itertuples():
    for _t in (_g.home_team,_g.away_team): KD[(_t,int(_g.week))]=str(_g.gameday)
def _ret_week(tm_,d_):
    if not d_: return None
    W_=[w_ for (t_,w_),gd in KD.items() if t_==tm_ and gd>=str(d_)[:10]]
    return min(W_) if W_ else 99
STATUS={}
# 1. the official injury report (and what it implies before Friday's game statuses)
for tm_,G_ in (injfull.groupby('team') if len(injfull) else []):
    tm_=IDT.get(tm_,tm_)
    if tm_ not in NXW: continue
    wr_=int(G_.week.max()); nx_=NXW[tm_]; cw_=G_[G_.week==wr_]
    _pv=G_[(G_.week==wr_-1)&G_.report_status.isin(['Out','Doubtful'])]; prevO={a_:(b_ if isinstance(b_,str) else None) for a_,b_ in zip(_pv.gsis_id,_pv.report_primary_injury)}
    if wr_==nx_:
        for x_ in cw_.itertuples():
            s_=x_.report_status if x_.report_status in ('Out','Doubtful','Questionable') else None; d_=x_.report_primary_injury if isinstance(x_.report_primary_injury,str) else prevO.get(x_.gsis_id)
            if s_: STATUS[x_.gsis_id]={'s':s_,'src':'report','d':d_}
            elif x_.gsis_id in prevO:
                pr_=short_prac(x_.practice_status)
                if pr_=='DNP': STATUS[x_.gsis_id]={'s':'Out','src':'expected','d':d_,'n':f'Expected out: missed week {wr_-1} and not practicing'}
                elif pr_=='Limited': STATUS[x_.gsis_id]={'s':'Questionable','src':'expected','d':d_,'n':f'Missed week {wr_-1}; limited in practice'}
    elif wr_<nx_:
        # missed the reported game: listed Out or Doubtful, or Questionable and then inactive for it (weekly roster)
        _ina=set(wr[(wr.week==wr_)&(wr.status=='INA')].gsis_id)
        _miss=cw_.report_status.isin(['Out','Doubtful'])|((cw_.report_status=='Questionable')&cw_.gsis_id.isin(_ina))
        for x_ in cw_[_miss].itertuples():
            q_=x_.report_status=='Questionable'
            STATUS[x_.gsis_id]={'s':'Questionable','src':'expected','k':nx_-wr_,'cv':'q' if q_ else None,'d':x_.report_primary_injury if isinstance(x_.report_primary_injury,str) else None,'n':(f'Questionable for week {wr_} and did not play' if q_ else f'Missed week {wr_}')+f'; no injury report for week {nx_} yet'}
# 2. the commissioner's exempt list (not allowed to play, like a suspension): out until the roster or the news says otherwise
EXEMPT={pid_ for pid_,x_ in cur.iterrows() if x_.get('status')=='EXE' and x_.get('position') in POS}
for pid_ in EXEMPT: STATUS[pid_]={'s':'Out','src':'roster','d':None,'n':"On the commissioner's exempt list (not allowed to play)"}
# 3. timelines reported in the news ("out at least three weeks", "out for the season") for a player whose next game has
#    no official status yet: out until his team's week (next game after the story) + N weeks
import re as _re
_NUMW={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
_TLW=_re.compile(r"\b(?:out|miss|sidelined|shelved)\b(?:\s+(?:for|at least|a minimum of|minimum of|roughly|about|approximately|around|another|an additional)){0,2}\s+(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)(?:\s*(?:-|–|to|or)\s*(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten))?\s+(?:more\s+)?weeks?\b",_re.I)
_TLS=_re.compile(r"\b(out for (the )?((rest|remainder) of (the )?)?(season|year)|season[- ]ending|(miss|misses|missing|sit out) (the )?((rest|remainder) of (the )?)?(season|year)(?!\s*(opener|finale|debut|'s first))|done for the (season|year))\b",_re.I)
_TLX=_re.compile(r"\b(return|returns|returning|back|activated|cleared|after missing|after being|designated to return)\b",_re.I)
_REIN=_re.compile(r"\b(reinstat\w*|removed? from (the )?(commissioner'?s )?exempt list|off (the )?(commissioner'?s )?exempt list|can play again|eligible to (play|return)|cleared to play|on track (to play|for (his |a |sunday'?s? |monday'?s? |thursday'?s? |week \d+ )?(debut|return))|(?<!not )(?<!n't )(?<!unlikely )(expected|set|slated|poised|going|ready) to (play|suit up|debut|make (his|a) debut)|will (play|suit up|debut|make his debut))\b",_re.I)
# a reinstatement stays known after its story leaves the news feed (news_state.json), until the roster drops the exempt
# status itself (October 2026: Josh Jacobs was reinstated on Oct 16, but a week later the story had aged out of the feed
# while the roster still said exempt, so he showed as out)
try: _NST=json.load(open('news_state.json')) if os.path.exists('news_state.json') else {}
except Exception: _NST={}
_RI={pid_:(pd.Timestamp(v_['d']),v_['s']) for pid_,v_ in (_NST.get('reinstated') or {}).items() if pid_ in EXEMPT}
# November 2026: a report of injured reserve ("to be placed on IR", "will land on IR") is at least 4 games, the league's
# minimum; "out indefinitely" / "expected to miss an extended period" is out for his next game (then the measured return
# curve); "could be out for the season" is not a confirmation: noted as questionable, and never replaces a confirmed
# report. The timelines are kept in news_state.json, because a story leaves the news feed within a day or two (Nov 3:
# Lamar Jackson's "to be placed on IR" had no timeline BFF could read, the report before it had left the feed, and he
# showed with no status)
_SPEC=_re.compile(r"\b(could|may|might|if|would|possibly|potentially|considering|weighing|fears?|feared)\b",_re.I)
_TLIR=_re.compile(r"\b(placed on|land(?:s|ing)? on|go(?:es|ing)? on|head(?:s|ed|ing)? to|to) (?:the )?(?:ir|injured reserve)\b",_re.I)
_TLIND=_re.compile(r"\b(out indefinitely|(?:miss|misses|missing) (?:an? )?(?:extended|significant|extensive|lengthy) (?:period|time|stretch|amount)|extended absence)\b",_re.I)
NEWS_TL=0
_now=pd.Timestamp.now(tz='UTC'); _TL={}
for pid_,v_ in (_NST.get('tl') or {}).items():
    try:
        d_=pd.Timestamp(v_['d'])
        if (_now-d_).days<=(200 if v_['n']>=99 else 35): _TL[pid_]=(int(v_['n']),d_,v_['s'],v_.get('hi'),v_.get('k','weeks'),bool(v_.get('spec')))
    except Exception: pass
try:
    _nj=json.load(open('news.json')) if os.path.exists('news.json') else {}
    for it_ in sorted(_nj.get('items') or [],key=lambda x:str(x.get('d') or '')):
        h_=str(it_.get('h') or ''); d_=pd.to_datetime(it_.get('d'),utc=True,errors='coerce'); P_=it_.get('p') or []
        if len(P_)!=1 or pd.isna(d_) or (_now-d_).days>35: continue
        if P_[0] in EXEMPT and _REIN.search(h_): _RI[P_[0]]=(d_,it_.get('s') or 'news'); continue
        old_=_TL.get(P_[0])
        if old_ and d_<=old_[1]: continue   # already known (kept from an earlier run), or older than what is known
        if it_.get('st')=='ok' or P_[0] in (it_.get('sk') or []):   # the headline says he is playing: a reported absence is over
            _TL.pop(P_[0],None); continue
        if _TLX.search(h_): continue
        m_=_TLW.search(h_); se_=_TLS.search(h_); ir_=_TLIR.search(h_); ind_=_TLIND.search(h_)
        _wn=lambda g_: (int(g_) if g_.isdigit() else _NUMW[g_.lower()]) if g_ else None
        if se_: v_=(99,None,'season')
        elif m_: v_=(_wn(m_.group(1)),_wn(m_.group(2)),'weeks')
        elif ir_: v_=(4,None,'ir')
        elif ind_: v_=(1,None,'ind')
        else: continue
        sp_=bool(_SPEC.search(h_))
        if sp_ and old_ and not old_[5]: continue   # a guess never replaces a confirmed report
        _TL[P_[0]]=(v_[0],d_,it_.get('s') or 'news',v_[1],v_[2],sp_)
    for pid_,(n_,d_,s_,hi_,kd_,sp_) in _TL.items():
        if pid_ not in cur.index or (STATUS.get(pid_) or {}).get('src')=='report': continue
        tm_=IDT.get(cur.at[pid_,'team'],cur.at[pid_,'team'])
        if tm_ not in NXW: continue
        w0_=_ret_week(tm_,(d_+pd.Timedelta(days=1)).strftime('%Y-%m-%d')); rw_=99 if n_>=99 else (w0_ or 99)+n_
        if sp_ or kd_=='ind': rw_=min(rw_,(w0_ or 99)+1)   # a guess, or no timeline: about his next game only
        if rw_<=NXW[tm_]: continue
        _when=f"{s_}, {d_.strftime('%b')} {d_.day}"; _span=f'{n_}-{hi_} weeks' if hi_ and hi_>n_ else f'{n_} week'+('s' if n_>1 else '')
        if sp_:
            STATUS[pid_]={'s':'Questionable','src':'news','d':(STATUS.get(pid_) or {}).get('d'),'n':f"Reported he could miss {'the rest of the season' if n_>=99 else 'time (' + _span + ')' if kd_=='weeks' else 'time'}; not confirmed ({_when})"}; NEWS_TL+=1; continue
        if kd_=='ind':
            STATUS[pid_]={'s':'Out','src':'news','d':(STATUS.get(pid_) or {}).get('d'),'n':f"Reported out indefinitely ({_when})"}; NEWS_TL+=1; continue
        # injured reserve: a reported timeline later than the 4-game minimum moves his estimated return (example: the Rams
        # said Davante Adams would miss 6-10 weeks, so not before week 13 instead of the minimum's week 11)
        if pid_ in RET: RET[pid_]=max(RET[pid_],rw_)
        _what='for the season' if n_>=99 else 'to injured reserve (at least 4 games)' if kd_=='ir' else _span
        STATUS[pid_]={'s':'Out','src':'news','d':(STATUS.get(pid_) or {}).get('d'),'rw':rw_,'n':f"Reported {'headed' if kd_=='ir' else 'out'} {_what} ({_when})"}; NEWS_TL+=1
    for pid_,(d_,s_) in _RI.items():   # reinstated: available again (tagged until the roster catches up)
        STATUS[pid_]={'s':'Questionable','src':'news','d':None,'n':f"Reinstated from the exempt list (reported by {s_}, {d_.strftime('%b')} {d_.day})"}; NEWS_TL+=1
    if NEWS_TL: print('injuries: timelines from the news for',NEWS_TL,'players')
except Exception as _e: print('news timelines unavailable:',_e)
try:
    json.dump({'reinstated':{pid_:{'d':d_.isoformat(),'s':s_} for pid_,(d_,s_) in sorted(_RI.items())},
               'tl':{pid_:{'n':n_,'d':d_.isoformat(),'s':s_,'hi':hi_,'k':kd_,'spec':int(sp_)} for pid_,(n_,d_,s_,hi_,kd_,sp_) in sorted(_TL.items())}},open('news_state.json','w'),indent=1)
    if _RI: print('reinstated from the exempt list (kept until the roster catches up):',', '.join(sorted(str(cur.at[p_,'full_name']) if p_ in cur.index and 'full_name' in cur.columns else p_ for p_ in _RI)))
except Exception as _e: print('news state not saved:',_e)
print('injury status:',sum(v['s']=='Out' for v in STATUS.values()),'out,',sum(v['s']=='Doubtful' for v in STATUS.values()),'doubtful,',sum(v['s']=='Questionable' for v in STATUS.values()),'questionable,',sum(v['src']=='expected' for v in STATUS.values()),'of them expected from the report')
# ---- teammates expected to miss games: Out/Doubtful for the next game; injured reserve for every remaining week
OUTN={pid_ for pid_,v in STATUS.items() if v['s'] in ('Out','Doubtful')}
IRS=set(cur[cur.status=='RES'].index)
SIT={}
for tm_,G_ in S26.groupby('team'):
    wks_=sorted(G_.week.unique())[-3:]; rec_=G_[G_.week.isin(wks_)].groupby('player_id').agg(xpg=('xfp','mean'),gp=('week','nunique'),pos=('position','first'),att=('attempts','sum'),name=('player_display_name','first'))
    rec_=rec_[rec_.gp>=min(2,len(wks_))]
    def _sit(outset,rec=rec_):
        miss=rec[rec.index.isin(outset)]; pres=rec[~rec.index.isin(outset)]; qb=rec[rec.pos=='QB'].sort_values('att',ascending=False)
        qbm=int(len(qb)>0 and qb.index[0] in outset and qb.att.iloc[0]>=40)
        return dict(pres=pres,vr=float(miss[(miss.pos=='RB')&(miss.xpg>=4)].xpg.sum()),vw=float(miss[miss.pos.isin(['WR','TE'])&(miss.xpg>=4)].xpg.sum()),qbm=qbm,
                    names=[n for n,x in zip(miss.name,miss.xpg) if x>=4],qbname=(qb.name.iloc[0] if qbm else None))
    SIT[tm_]={'next':_sit(OUTN|IRS),'later':_sit(IRS)}
def sit_feats(pid,pos,tm,which):
    s_=(SIT.get(tm) or {}).get(which)
    if not s_: return 0.0,0,0.0
    pres=s_['pres']
    if pid not in pres.index: return 0.0,s_['qbm'],s_['vr']+s_['vw']
    grp=['RB'] if pos=='RB' else ['WR','TE'] if pos in ('WR','TE') else []
    vac=s_['vr'] if pos=='RB' else s_['vw'] if pos in ('WR','TE') else 0.0
    tot=float(pres[pres.pos.isin(grp)].xpg.sum()) if grp else 0.0
    return (vac*float(pres.loc[pid,'xpg'])/tot if tot>0 else 0.0),s_['qbm'],s_['vr']+s_['vw']
def _ident(pid):
    """team, roster status, position and name, or None when he cannot be projected"""
    tm,status=team_of(pid)
    if tm is None: return None
    pos=(info.loc[pid,'position'] if pid in info.index else (role.loc[pid,'pg'] if pid in role.index else (cur.loc[pid,'position'] if pid in cur.index else (idx.loc[pid,'position'] if pid in idx.index else None))))
    if pos not in POS: return None
    name=(info.loc[pid,'player_display_name'] if pid in info.index else role.loc[pid,'player_name'] if pid in role.index else None)
    if (not isinstance(name,str) or not name.strip()) and pid in cur.index: name=cur.loc[pid,'full_name']
    if (not isinstance(name,str) or not name.strip()) and pid in idx.index: name=idx.loc[pid,'name']
    if not isinstance(name,str) or not name.strip(): return None
    return tm,status,pos,name
# ---- every unplayed game of every player, projected at once. Betting lines where they are out; for weeks further ahead
# each team's points scored and allowed so far stand in for them (the same rule the value backtest used).
_TTN=C5.TT[(C5.TT.season==SEASON)&(C5.TT.week==NEXT)].set_index('team') if len(C5.TT) else pd.DataFrame()
_SCX={(int(x.week),x.team):x for x in C5.SC[C5.SC.season==SEASON].itertuples()}
def _proxy(tm,op):
    if tm in _TTN.index and op in _TTN.index:
        it_=(_TTN.loc[tm,'pts_t']+_TTN.loc[op,'pa_t'])/2; io_=(_TTN.loc[op,'pts_t']+_TTN.loc[tm,'pa_t'])/2; return float(it_),float(it_-io_),float(it_+io_)
    return 22.0,0.0,44.0
def _games(tm,sched):
    out=[]
    for g in sched.itertuples():
        x=_SCX.get((int(g.week),tm)); op=g.opp; hm=float(g.home) if g.home==g.home else 0.5
        it_,sp_,tt_=(x.it,x.spread,x.total) if x is not None else (np.nan,np.nan,np.nan)
        if not (it_==it_ and sp_==sp_ and tt_==tt_): it_,sp_,tt_=_proxy(tm,op)
        out.append((int(g.week),tm,op,hm,float(it_),float(sp_),float(tt_),float(x.dome) if x is not None and x.dome==x.dome else 0.0,float(x.rest) if x is not None and x.rest==x.rest else 0.0,float(x.div) if x is not None and x.div==x.div else 0.0))
    return out
_PRC={'DNP':0.0,'Limited':1.0,'Full':2.0}
_ID={}; _PL={}; _GM={}
for pid in pool:
    _i=_ident(pid)
    if _i is None: continue
    tm,status,pos,name=_i; sched=SC26[(SC26.team==tm)&SC26.pts.isna()].sort_values('week')   # this team's unplayed games
    if not len(sched): continue
    _ID[pid]=_i; _PL[pid]=pos; _GM[pid]=_games(tm,sched)
U5=C5.upcoming(SEASON,NEXT,_PL,_GM)
if not len(U5): U5=pd.DataFrame(columns=['player_id','pos','team','opp','week','gi','q','prac','bump','qbm','vac_all','dvp','e_fp'])
U5['gi']=U5.groupby('player_id').cumcount()
_sit=[sit_feats(pid_,pos_,tm_,'next' if gi_==0 else 'later') for pid_,pos_,tm_,gi_ in zip(U5.player_id,U5.pos,U5.team,U5.gi)]
U5['bump']=[x[0] for x in _sit]; U5['qbm']=[x[1] for x in _sit]; U5['vac_all']=[x[2] for x in _sit]
_first=U5.gi==0   # his next game: this week's injury report and practice
U5.loc[_first,'q']=[1.0 if (STATUS.get(pid_) or {}).get('s')=='Questionable' else 0.0 for pid_ in U5[_first].player_id]
U5.loc[_first,'prac']=[_PRC.get(PRAC.get(pid_),np.nan) for pid_ in U5[_first].player_id]
U5.loc[~_first,'q']=0.0; U5.loc[~_first,'prac']=np.nan
_LG={c:float(_TTN[c].mean()) for c in _TTN.columns if c.endswith('_t')} if len(_TTN) else {}
PRED={}
for pos in POS:
    u=U5[U5.pos==pos]
    if not len(u): continue
    P_=MODEL.next(pos,u); F1=u[u.gi==0]
    Pm_=MODEL.next(pos,F1.assign(dvp=1.0,**{'o_'+k:v for k,v in _LG.items()}))   # an average defense
    _px=[_proxy(t_,o_) for t_,o_ in zip(F1.team,F1.opp)]
    Pv_=MODEL.next(pos,F1.assign(it=[x[0] for x in _px],spread=[x[1] for x in _px],total=[x[2] for x in _px]))   # no betting line
    Pt_=MODEL.next(pos,F1.assign(bump=0.0,qbm=0,vac_all=0.0))   # no teammates out
    XL_=MODEL.parts(pos,F1)
    for pid_,ix in u.groupby('player_id',sort=False).indices.items():
        PRED[pid_]={'P':P_[ix],'wk':u.week.values[ix],'dvp':u.dvp.values[ix],'bump':u.bump.values[ix],'efp':float(u.e_fp.values[ix[0]]) if u.e_fp.values[ix[0]]==u.e_fp.values[ix[0]] else None}
    for j,pid_ in enumerate(F1.player_id.values):
        PRED[pid_].update(Pm=float(Pm_[j]),Pv=float(Pv_[j]),Pt=float(Pt_[j]),xl={c:round(float(v[j]),1) for c,v in XL_.items()})
# rest-of-season level = the average of his remaining game projections, each with its own opponent and team totals
# (2023-25 value backtest: better than adding a separate rest-of-season model, which the old version used)
for pid_,X in PRED.items():
    m_=X['wk']<=17; X['L']=float(np.mean(X['P'][m_])) if m_.any() else float(np.mean(X['P'])); X['PR']=X['P']
print('projected',len(PRED),'players,',len(U5),'games',flush=True)
for pid in pool:
    if pid not in PRED: continue
    tm,status,pos,name=_ID[pid]; X=PRED[pid]
    rows=S26[S26.player_id==pid].sort_values('week')
    pv=prev_pg.get((pid,SEASON),np.nan)
    if (pv is None or pv!=pv) and pid in _pp2.index and _pp2.loc[pid,'size']>=6: pv=0.9*float(_pp2.loc[pid,'mean'])   # missed last season: use the season before
    G_=_GM[pid]; wk_rows=[(g_[0],g_[2],g_[3],g_[4],{'dvp':float(X['dvp'][i_]) if X['dvp'][i_]==X['dvp'][i_] else None,'bump':float(X['bump'][i_])}) for i_,g_ in enumerate(G_)]
    P=X['P']; PR=X['PR']; Pr=np.array([X['L']]); Pm,Pv,Pt=X['Pm'],X['Pv'],X['Pt']; base={'efp':X['efp']}
    S_=STATUS.get(pid,{}); out=S_.get('s'); ir=status=='RES'
    nxt=wk_rows[0]; proj_next=float(P[0]); nw_=int(nxt[0])
    def _avail(w_):
        # chance he plays week w_: out now -> the measured return curve (or a reported return week); missed his last game
        # with no new report -> the same curve from that game
        if out in ('Out','Doubtful'):
            k_=w_-nw_; rw_=S_.get('rw')
            if k_<=0: return 0.0
            if rw_: return 0.0 if w_<rw_ else OUTA[min(3,1+w_-rw_)]
            return OUTA[min(3,k_-1)]
        if S_.get('k'): return (QINA if S_.get('cv')=='q' else OUTA)[min(3,S_['k']-1+w_-nw_)]
        return 1.0
    if out in ('Out','Doubtful') or ir: proj_next=0.0
    elif S_.get('k'): proj_next*=_avail(nw_)
    rec_pg=float(rows.receptions.mean()) if len(rows) else float(st[(st.player_id==pid)&(st.season==SEASON-1)].receptions.mean() or 0)
    ret_=RET.get(pid) if ir else None
    # injured reserve: nothing before his estimated return, then the share of games such players really played after it
    # (2023-25: 11% the first week, 34% by the fourth, about half later; 53% did not play again that season)
    _av=[(0.0 if ret_ and w[0]<ret_ else (AIR[min(len(AIR)-1,int(w[0])-ret_)] if ret_ else 1.0)) if ir else _avail(int(w[0])) for w in wk_rows if w[0]<=17]
    _raw=[float(P[i] if i==0 else PR[i]) for i,w in enumerate(wk_rows) if w[0]<=17]
    ros=[[int(w[0]),w[1],r(_av[i]*_raw[i],1)] for i,w in enumerate(wk_rows) if w[0]<=17]
    AVL[pid]=(_av,_raw)
    rl=role.loc[pid] if pid in role.index else None
    # no usage: on this team for 3+ weeks this season (active, inactive or practice squad, never on a reserve list) and
    # not one fantasy stat. Measured on 2021-25 (n=1,160 RB/WR/TE), such players scored about 1 PPR point the next week
    # (RB 1.23, WR 1.08, TE 0.58; 8% scored 5+), so the projection is capped there until he gets touches. Depth-chart
    # starters keep the model's number; quarterbacks follow the starter rule below.
    if pos in NOUSE and not len(rows) and not ir and status!='EXE' and not (rl is not None and rl['team']==tm and int(rl['pos_rank'])<=(3 if pos=='WR' else 1)):
        _h=wr[(wr.gsis_id==pid)&(wr.week>=1)]
        # (a practice-squad player with no stats this season counts at once: he plays only if elevated, e.g. a former starter
        # signed to the practice squad two weeks ago)
        if not (_h.status=='RES').any() and (((_h.team==tm)&_h.status.isin(['ACT','INA','DEV'])).sum()>=3 or status=='DEV'): NOU[pid]=NOUSE[pos]
    players.append({'id':pid,'n':name,'p':pos,'t':tm,'bio':bio_of(pid),'age':r(idx.loc[pid,'age'],1) if pid in idx.index and 'age' in idx.columns else None,
      'role':f"{rl['pg']}{int(rl['pos_rank'])}" if rl is not None and rl['team']==tm else None,'inj':('IR' if ir else out),'ret':ret_,'bmp':[[int(w[0]),r(w[4]['bump'],2)] for w in wk_rows[:2]],'rsv':(RSV.get(pid,'IR') if ir else None),
      'num':int(cur.loc[pid,'jersey_number']) if pid in cur.index and pd.notna(cur.loc[pid,'jersey_number']) else None,'g':int(len(rows)),'fp':r(rows.fp.sum(),1),'fpg':r(rows.fp.mean(),1) if len(rows) else None,'xfpg':r(rows.xfp.mean(),1) if len(rows) else None,
      'snap':r(rows.offense_pct.mean(),3) if len(rows) and rows.offense_pct.notna().any() else None,'ts':r(rows.target_share.mean(),3) if len(rows) else None,
      'ays':r(rows.air_yards_share.mean(),3) if len(rows) else None,'wopr':r(rows.wopr.mean(),3) if len(rows) else None,'tpg':r(rows.targets.mean(),1) if len(rows) else None,
      'cpg':r(rows.carries.mean(),1) if len(rows) else None,'cs':r(rows.car_share.mean(),3) if len(rows) else None,'rz':r(rows.rzo.mean(),1) if len(rows) else None,
      'rpg':r(rec_pg,2),'mx':mix_of(pid,pos),'prev':r(pv,1),'dy':int(idx.loc[pid,'draft_year']) if pid in idx.index and pd.notna(idx.loc[pid,'draft_year']) else None,
      'gl':GL.get(pid,[]),
      'wk':[[int(x.week),r(x.fp,1),r(x.xfp,1),r(x.offense_pct,2),int(x.targets),int(x.carries),x.opponent_team] for x in rows.itertuples()],
      'proj':r(proj_next,1),'nw':int(nxt[0]),'opp':nxt[1],'home':int(nxt[2]) if nxt[2]==nxt[2] else 0,'it':r(nxt[3],1),'rl':r(Pr[0],1),'frm':r(base.get('efp'),1),
      'dvp':r(nxt[4]['dvp'],3) if nxt[4]['dvp'] is not None else None,'xl':X.get('xl'),'adjm':r(P[0]-Pm,1),'adjv':r(P[0]-Pv,1),'adjt':(0.0 if (out in ('Out','Doubtful') or ir) else r(P[0]-Pt,1)),'injd':S_.get('d'),'injn':None if ir and S_.get('src')=='expected' else S_.get('n'),'injs':None if ir and S_.get('src')=='expected' else S_.get('src'),'pj0':r(float(P[0]),1) if (out in ('Out','Doubtful') or S_.get('k')) and not ir else None,'tmo':[n for n in (SIT.get(tm,{}).get('next',{}).get('names') or []) if n!=name][:4],'qbo':(lambda q:q if q and q!=name else None)(SIT.get(tm,{}).get('next',{}).get('qbname')),'prac':PRAC.get(pid),'tpl':r(TV.pl.get(tm,np.nan),1),'tpr':r(TV.pr.get(tm,np.nan),3),'ros':ros,'bye':(byes.get(tm) or [None])[0],
      'pfr':idx.loc[pid,'pfr_id'] if pid in idx.index and isinstance(idx.loc[pid,'pfr_id'],str) else None})
# ---- quarterbacks: only the expected starter is projected (a backup rarely takes a snap). Starter of record = the best
# quarterback on the depth chart who is not on injured reserve; expected starter = the best one not Out/Doubtful/IR. A
# fill-in keeps next week and, later, the chance the starter is still out; every other quarterback is projected for 0.
import re as _re
def _qrk(p):
    m_=_re.match(r'QB(\d+)$',p.get('role') or ''); return int(m_.group(1)) if m_ else 9
for tm_ in sorted({p['t'] for p in players if p['p']=='QB'}):
    Q_=sorted([p for p in players if p['t']==tm_ and p['p']=='QB'],key=lambda p:(_qrk(p),-sum(g_[2] for g_ in p.get('gl') or [])))
    sor=next((p for p in Q_ if p.get('inj')!='IR'),None); ns=next((p for p in Q_ if p.get('inj') not in ('Out','Doubtful','IR')),None)
    for p in Q_:
        if p is sor or p is ns: continue
        if (p.get('proj') or 0)>0 and p.get('pj0') is None: p['pj0']=p['proj']   # kept so the page can promote him if the starter is ruled out later
        p['proj']=0.0; p['adjt']=0.0; p['qbb']=1
        for row in p['ros']: row[2]=0.0
    if ns is not None:
        ns['qbs']=1
        if sor is not None and ns is not sor:
            a_,_=AVL.get(sor['id'],([1.0]*len(ns['ros']),None)); _,raw_=AVL.get(ns['id'],(None,[row[2] for row in ns['ros']]))
            for j_,row in enumerate(ns['ros']):
                if row[0]!=ns['nw'] and j_<len(a_) and j_<len(raw_): row[2]=r(raw_[j_]*(1-a_[j_]),1)
        # the starter missed his last game and his team has no injury report for the next one yet: he plays with the
        # measured chance (see _avail) and the next quarterback gets the rest, so the team's QB total stays whole
        # (e.g. Baker Mayfield after missing week 6: about 39% his projection, Jalon Daniels about 61% of his)
        if (STATUS.get(ns['id']) or {}).get('k') and ns.get('inj')!='IR':
            a_s,_=AVL.get(ns["id"],(None,None)); bq_=next((p for p in Q_ if p is not ns and p.get('inj') not in ('Out','Doubtful','IR')),None)
            raw_b=AVL.get(bq_['id'],(None,None))[1] if bq_ is not None else None
            if a_s and raw_b:
                for j_,row in enumerate(bq_['ros']):
                    if j_<len(a_s) and j_<len(raw_b): row[2]=r(raw_b[j_]*(1-a_s[j_]),1)
                bq_['proj']=bq_['ros'][0][2] if bq_['ros'] and bq_['ros'][0][0]==bq_['nw'] else 0.0
                bq_['qbb']=0; bq_['qbf']=1; bq_['pj0']=r(raw_b[0],1)
print('quarterbacks: expected starters', sum(1 for p in players if p.get('qbs')), '| backups set to 0:', sum(1 for p in players if p.get('qbb')))
# ---- common sense: fill-ins and returning starters (research/bt_fillin.py, research/bt_commonsense.py). A fill-in is a
# back or receiver who took a starter's snaps (40%+ of them, 15+ points more than beside the starter) while that starter (a
# .55+ snap share for RBs, .70+ for WRs/TEs in his best 2 of his last 3 games, or first on the depth chart) missed 1-6
# games, and who ranks below the starter (lower on the depth chart; without that, fewer targets + carries in their games
# together, or, never together, fewer in the games he filled than the starter's best 2). When the starter is back the model still reads
# the fill-in's starter-sized role: in 2020-25 it over-projected such fill-ins 73% of the time, and they scored 79% (RB),
# 80% (WR) and 75% (TE) of what it said (2023-25 check: average miss 3.82 -> 3.44 points, bias +1.37 -> +0.13). So each
# week of his is scaled by that share, in proportion to the chance the starter plays that week (no change while the starter
# is out). The starter's own projection needed no change (he scored 100-104% of it). The flags feed the buy-low and
# sell-high lists: as buy lows, fill-ins whose starter was back were right 27% of the time (60% for all calls).
FILLF={'RB':.786,'WR':.803,'TE':.754}; FSH={'RB':.55,'WR':.70,'TE':.70}
_PB={p['id']:p for p in players}; NFILL=[]
def _rk(p):
    m_=_re.match(r'[A-Z]+(\d+)$',p.get('role') or ''); return int(m_.group(1)) if m_ else 9
if PHASE=='season' and len(S26):
    _S=S26[S26.position.isin(list(FSH))&(S26.offense_pct.fillna(0)>0)]
    _TW={t_:sorted(int(w_) for w_ in g_.week.unique()) for t_,g_ in S26.groupby('team')}
    _U={(x_.player_id,x_.team,int(x_.week)):float(x_.offense_pct) for x_ in _S.itertuples()}
    _O={(x_.player_id,int(x_.week)):float((x_.targets or 0)+(x_.carries or 0)) for x_ in S26.itertuples()}   # targets + carries
    for (tm_,pos_),G_ in _S.groupby(['team','position']):
        W_=_TW.get(tm_) or []; n_=len(W_)
        for L_ in G_.player_id.unique():
            pL=_PB.get(L_)
            if pL is None or pL['t']!=tm_ or pL['p']!=pos_ or n_<2: continue
            pl_=[(L_,tm_,w_) in _U for w_ in W_]
            if not pl_[-1]:                                   # still missing games
                j_=n_-1
                while j_>=0 and not pl_[j_]: j_-=1
                if j_<0: continue
                miss_=W_[j_+1:]; back_=0
            else:                                             # back, within the team's last 2 games
                hit_=None
                for back_ in (1,2):
                    i_=n_-back_
                    if i_<1 or not pl_[i_] or pl_[i_-1]: continue
                    j_=i_-1
                    while j_>=0 and not pl_[j_]: j_-=1
                    if j_>=0: hit_=(W_[j_+1:i_],back_,j_)
                    break
                if hit_ is None: continue
                miss_,back_,j_=hit_
            if not 1<=len(miss_)<=6: continue
            bef_=[W_[k_] for k_ in range(j_,-1,-1) if pl_[k_]][:3]; sb_=sorted([_U[(L_,tm_,b_)] for b_ in bef_],reverse=True)
            if len(sb_)<2: continue
            if not (np.mean(sb_[:2])>=FSH[pos_] or (_rk(pL)<=(2 if pos_=='WR' else 1) and sb_[0]>=FSH[pos_])): continue
            aL_={int(row[0]):a_ for row,a_ in zip(pL['ros'],AVL.get(L_,([1.0]*len(pL['ros']),None))[0])}
            nxt_=[int(row[0]) for row in pL['ros']][:2]
            due_=next((w_ for w_ in sorted(aL_) if aL_[w_]>=.5),None)
            for X_ in G_.player_id.unique():
                pX=_PB.get(X_)
                if X_==L_ or pX is None or pX['t']!=tm_ or pX['p']!=pos_: continue
                sm_=[_U.get((X_,tm_,m_),0.0) for m_ in miss_]
                if np.mean(sm_)<.40: continue
                wi_=[_U[(X_,tm_,b_)] for b_ in bef_ if (X_,tm_,b_) in _U]
                if wi_ and np.mean(wi_)>np.mean(sm_)-.15: continue    # he had this role already (his snaps must have risen 15+ points)
                # he ranks below the starter: the depth chart settles it when both are on it at different spots; otherwise
                # their targets + carries (together, or the games he filled vs the starter's best 2), as in the research
                if _rk(pX)<9 and _rk(pL)<9 and _rk(pX)!=_rk(pL):
                    if _rk(pX)<_rk(pL): continue
                else:
                    bes_=[b_ for b_ in bef_ if (X_,tm_,b_) in _U]
                    if bes_ and np.mean([_O.get((X_,b_),0) for b_ in bes_])>=np.mean([_O.get((L_,b_),0) for b_ in bes_]): continue
                    if not bes_ and np.mean([_O.get((X_,m_),0) for m_ in miss_])>=np.mean(sorted([_O.get((L_,b_),0) for b_ in bef_],reverse=True)[:2]): continue
                f_=FILLF[pos_]; mult_=[]
                for row in pX['ros']:
                    m_=1-aL_.get(int(row[0]),0.0)*(1-f_); mult_.append(m_); row[2]=r(row[2]*m_,1)
                if pX['ros'] and pX['ros'][0][0]==pX['nw']: pX['proj']=r((pX['proj'] or 0)*mult_[0],1)
                if mult_ and pX.get('rl') is not None: pX['rl']=r(pX['rl']*float(np.mean(mult_)),1)
                st_='back' if back_ else ('q' if pL.get('inj')=='Questionable' else 'act' if not pL.get('inj') else 'out')
                soon_=int(bool(due_) and due_ in nxt_)
                old_=pX.get('fill')
                if old_ is None or soon_>old_.get('soon',0):
                    pX['fill']={'by':pL['n'],'id':L_,'st':st_,'w':due_,'soon':soon_,'f':f_,'m':r(float(np.mean(sm_)),2),'wi':r(float(np.mean(wi_)),2) if wi_ else None}
                pL.setdefault('rtn',[]).append(pX['n']); NFILL.append(f"{pX['n']} ({tm_}, for {pL['n']}{', due back week '+str(due_) if due_ and not back_ else ', back' if back_ else ''})")
# a starter who has not played yet this season (suspension, exempt list, an injury since camp) and is active now: the backs
# or receivers who took his snaps are fill-ins too. With no games of his to measure, the depth chart decides (he must rank
# above them) and he must have been a starter last season (8+ PPR points a game); they must have played 40%+ of the snaps
# over the team's last 2 games (e.g. Josh Jacobs back from the exempt list, Pierre Strong).
if PHASE=='season' and len(S26):
    for pL in players:
        if pL['p'] not in FSH or (pL.get('g') or 0)>0 or pL.get('inj') in ('Out','Doubtful','IR') or _rk(pL)>(2 if pL['p']=='WR' else 1) or (pL.get('prev') or 0)<8: continue
        tm_,pos_=pL['t'],pL['p']; W_=(_TW.get(tm_) or [])[-2:]
        if not W_: continue
        aL_={int(row[0]):a_ for row,a_ in zip(pL['ros'],AVL.get(pL['id'],([1.0]*len(pL['ros']),None))[0])}
        nxt_=[int(row[0]) for row in pL['ros']][:2]; due_=next((w_ for w_ in sorted(aL_) if aL_[w_]>=.5),None)
        for pX in players:
            if pX is pL or pX['t']!=tm_ or pX['p']!=pos_ or not (pL and _rk(pL)<_rk(pX)<9) or pX.get('fill'): continue
            sm_=[_U.get((pX['id'],tm_,w_),0.0) for w_ in W_]
            if np.mean(sm_)<.40: continue
            f_=FILLF[pos_]; mult_=[]
            for row in pX['ros']:
                m_=1-aL_.get(int(row[0]),0.0)*(1-f_); mult_.append(m_); row[2]=r(row[2]*m_,1)
            if pX['ros'] and pX['ros'][0][0]==pX['nw']: pX['proj']=r((pX['proj'] or 0)*mult_[0],1)
            if mult_ and pX.get('rl') is not None: pX['rl']=r(pX['rl']*float(np.mean(mult_)),1)
            pX['fill']={'by':pL['n'],'id':pL['id'],'st':'q' if pL.get('inj')=='Questionable' else 'act','w':due_,'soon':int(bool(due_) and due_ in nxt_),'f':f_,'m':r(float(np.mean(sm_)),2),'wi':None,'new':1}
            pL.setdefault('rtn',[]).append(pX['n']); NFILL.append(f"{pX['n']} ({tm_}, for {pL['n']}, first game of the season)")
# role going down: snap share over his last 2 games under 75% of his season share (3+ games). In 2020-25 buy-low calls on
# such players were right 37% of the time (61% for the rest).
for p in players:
    if p['p'] in FSH and (p.get('g') or 0)>=3 and p.get('snap'):
        _l2=S26[(S26.player_id==p['id'])].sort_values('week').offense_pct.dropna().tail(2)
        if len(_l2)==2 and float(_l2.mean())<.75*p['snap']: p['rdn']=r(float(_l2.mean()),3)
print('fill-ins (projection scaled for the weeks their starter plays):',', '.join(NFILL) if NFILL else 'none','| snaps falling:',sum(1 for p in players if p.get('rdn')))
# next week's projection is BFF's own model (no other site's projections or rankings are used; see research/README.md)
for p in players:   # the no-usage cap (above)
    c_=NOU.get(p['id'])
    if c_ is None: continue
    p['nou']=1; p['proj']=min(p['proj'] or 0,c_); p['rl']=min(p.get('rl') or 0,c_)
    for row in p['ros']: row[2]=min(row[2],c_)
if NOU: print('no usage this season (projection capped at about 1 point):',', '.join(sorted(p['n'] for p in players if p.get('nou'))))
players.sort(key=lambda p:-(p['proj'] or 0))
# defense vs position, this season to date (PPR points allowed per game) with ranks (1 = allows the fewest)
a26,lg26=dvp_table(SEASON,99); DVP={}
for t in sorted(SC26.team.unique()):
    DVP[t]={}
    for pos in POS:
        if (t,pos) in a26.index: sm,c=a26.loc[(t,pos)]; DVP[t][pos]=[r(sm/c,1),int(c),r(dvp_factor(SEASON,99,t,pos),3)]
for pos in POS:
    order=sorted([t for t in DVP if pos in DVP[t]],key=lambda t:DVP[t][pos][0])
    for k,t in enumerate(order): DVP[t][pos].append(k+1)
from zoneinfo import ZoneInfo
def _i(v):
    try: return 0 if v is None or (isinstance(v,float) and np.isnan(v)) else int(v)
    except Exception: return 0
from live_update import box_from_stats   # the same box score the score job writes (kicking and D/ST numbers included)
GW=gm[(gm.season==SEASON)&(gm.week==NEXT)].sort_values(['gameday','gametime']); LGAMES=[]; LBOX={}
for g in GW.itertuples():
    kick=datetime.datetime.strptime(f"{g.gameday} {g.gametime}","%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo('America/New_York')).isoformat() if isinstance(g.gametime,str) else None
    done=not pd.isna(g.home_score)
    fav=None if pd.isna(g.spread_line) else (f"{g.home_team} -{abs(g.spread_line):g}" if g.spread_line>0 else f"{g.away_team} -{abs(g.spread_line):g}" if g.spread_line<0 else 'Pick em')
    LGAMES.append({'id':g.game_id,'away':g.away_team,'home':g.home_team,'as':None if not done else int(g.away_score),'hs':None if not done else int(g.home_score),
                   'state':'post' if done else 'pre','detail':'Final' if done else None,'kick':kick,'venue':g.stadium if isinstance(g.stadium,str) else None,'odds':fav,'ou':None if pd.isna(g.total_line) else float(g.total_line)})
    if done:
        rows=S26[S26.game_id==g.game_id]; LBOX[g.game_id]=box_from_stats(rows)
from ff_news import build_news
REL={p['id'] for p in players if (p.get('prev') or 0)>=6 or (p.get('fpg') or 0)>=6 or (p.get('role') or 'X9')[-1] in '12'}
NEWS=build_news(SEASON,REL)
try:
    from news_update import build_news as collect_news
    HEAD=collect_news()[0]
except Exception as e:
    print('headlines unavailable:',e); HEAD=None
# ---- projection history: each player's projection is refreshed every run until his game kicks off, then it stays frozen
PI_POS={p['id']:p['p'] for p in players}
HP='proj_history.json'
try: H=json.load(open(HP)) if os.path.exists(HP) else {}
except Exception: H={}
HS=H.setdefault(str(SEASON),{})
for p in players:
    if p['nw']==NEXT and p.get('proj') is not None: HS.setdefault(str(NEXT),{})[p['id']]=[p['proj'],p.get('rpg') or 0]
json.dump(H,open(HP,'w'),separators=(',',':'))
# ---- accuracy of the frozen projections against what actually happened, week by week
ACC=[]
for wk,pr in sorted(HS.items(),key=lambda x:int(x[0])):
    act=S26[S26.week==int(wk)].set_index('player_id').fp
    rows=[(v[0],float(act[pid]),PI_POS.get(pid)) for pid,v in pr.items() if pid in act.index and v[0] is not None and v[0]>0]
    if len(rows)<30: continue
    dfa=pd.DataFrame(rows,columns=['p','a','pos']); rk=[spearmanr(x.p,x.a).correlation for _,x in dfa.groupby('pos') if len(x)>=10]
    ACC.append({'wk':int(wk),'n':len(dfa),'mae':r(float((dfa.p-dfa.a).abs().mean()),2),'rank':r(float(np.nanmean(rk)),3) if rk else None})
# the page's scores: the score job's live.json (scores, box scores and scoring plays, every 30 minutes), else built here
LIVE=None
try:
    _lj=json.load(open('live.json')) if os.path.exists('live.json') else None
    if isinstance(_lj,dict) and _lj.get('season')==SEASON and _lj.get('games'): LIVE=_lj
except Exception as e: print('live.json unreadable, building the scores here:',e)
if LIVE is None: LIVE={'week':NEXT,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='minutes'),'src':'nflverse schedule and official stats','season':SEASON,'games':LGAMES,'box':LBOX}
_KX={}
for _x in gm[gm.season==SEASON].itertuples():
    _k=datetime.datetime.strptime(f"{_x.gameday} {_x.gametime}","%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo('America/New_York')).isoformat() if isinstance(_x.gametime,str) else (str(_x.gameday) if isinstance(_x.gameday,str) else None)
    _sp=None if pd.isna(_x.spread_line) else float(_x.spread_line); _to=None if pd.isna(_x.total_line) else float(_x.total_line)
    _KX[(int(_x.week),_x.home_team)]=(_k,None if _sp is None else -_sp,_to); _KX[(int(_x.week),_x.away_team)]=(_k,_sp,_to)
SCHED={t:[[int(g.week),g.opp,int(g.home) if g.home==g.home else 0,r(g.it,1),None if pd.isna(g.pts) else int(g.pts)]+list(_KX.get((int(g.week),t),(None,None,None))) for g in SC26[SC26.team==t].sort_values('week').itertuples()] for t in SC26.team.unique()}
OUT={'asof':{'season':SEASON,'phase':PHASE,'sched':bool(SCHED_KNOWN),'last_week':LAST,'next_week':NEXT,'built':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d'),'depth':str(dc.dt.max())[:10]},
     'players':players,'live':LIVE,'news':NEWS,'headlines':HEAD,'ph':HS.get(str(NEXT),{}),'acc':ACC,'trendsval':json.load(open('trends_val.json')) if os.path.exists('trends_val.json') else None,'dvp':DVP,'lgpos':{p:r(lg26.get(p,np.nan),1) for p in POS},'sched':SCHED,'byes':byes,'model':{'test':res,'range':RNG,'qs':QS,'posavg':{k:r(v,1) for k,v in POSAVG.items()},'train':[min(TRAIN),max(TRAIN)],'test_season':TEST,'hist':[min(HIST5),max(HIST5)],'ew_h':EW_H,'v':5,'rows':int(len(DH))}}
def clean(o):
    if isinstance(o,float) and (o!=o or abs(o)==float('inf')): return None
    if isinstance(o,(np.floating,)): return clean(float(o))
    if isinstance(o,(np.integer,)): return int(o)
    if isinstance(o,dict): return {str(k):clean(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)): return [clean(v) for v in o]
    return o
json.dump(clean(OUT),open('ff_data.json','w'),separators=(',',':'),allow_nan=False)
print('players',len(players),'| next week',NEXT,'| json KB',os.path.getsize('ff_data.json')//1024,flush=True)
for p in players[:12]: print(f"{p['n']:24s} {p['p']} {p['t']} wk{p['nw']} vs {p['opp']} proj {p['proj']} (fpg {p['fpg']}, xfpg {p['xfpg']}, it {p['it']}, dvp {p['dvp']}) role {p['role']} inj {p['inj']}")
