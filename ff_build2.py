"""Shared data and features for the BFF projections (used by ff_produce.py, calls_backfill.py and the backtests).

Everything rolls forward on its own. fetch_data.py writes season.json with the current season (or the upcoming one in
the offseason); the model learns from the five completed seasons before it, testing on the most recent of them, so
each new season of games is picked up without anyone editing a file.

Features for each player-game, from his games before it:
  season averages (points, expected points, snap share, target share, carry share, red-zone chances), the last 3 games,
  recent form (exponentially weighted, so the latest game counts most and older ones fade by half every 2.5 games),
  last season's points per game (or a draft-slot prior for rookies), Vegas implied total, the defense's points allowed,
  and teammates missing (vacated expected points, starting QB out) from that week's injury report and roster status.
"""
import os, json, io, urllib.request, datetime
import pandas as pd, numpy as np

POS = ['QB', 'RB', 'WR', 'TE']


def _season():
    """(season, phase) from season.json; without it, the season that is underway or next."""
    try:
        s = json.load(open('season.json')); return int(s['season']), s.get('phase', 'season')
    except Exception:
        t = datetime.date.today(); return (t.year if t.month >= 3 else t.year - 1), 'season'


SEASON, PHASE = _season()
HIST = [y for y in range(SEASON - 5, SEASON) if os.path.exists(f'stats_player_week_{y}.parquet')]   # completed seasons
CUR_OK = os.path.exists(f'stats_player_week_{SEASON}.parquet')                                       # games played this season
YEARS = HIST + ([SEASON] if CUR_OK else [])
TEST = HIST[-1]; TRAIN = HIST[:-1]           # model choice is tested on the latest completed season, never seen in training
EW_H = 2.5                                   # recent-form half-life in games (2023-25 backtest: 1.5, 2.5 and 4 tried)
FEAT_VER = 'v30'                             # bump when the features change (old caches are then ignored)
CACHE = '.cache'
print(f'season {SEASON} ({PHASE}); history {HIST}; this season played: {CUR_OK}', flush=True)


def r(v, d=2): return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), d)


def read_opt(path, **kw):
    """read a parquet file if it is there (a season's file can be missing before its first game)"""
    try: return pd.read_parquet(path, **kw) if os.path.exists(path) else None
    except Exception as e: print('could not read', path, e); return None


# ---------- weekly stats
st = pd.concat([pd.read_parquet(f'stats_player_week_{y}.parquet') for y in YEARS]); st = st[(st.season_type == 'REG') & st.position.isin(POS)].copy()
st['fp'] = st.fantasy_points_ppr; st['fps'] = st.fantasy_points
_AS_OF = os.environ.get('BFF_AS_OF')   # testing only: pretend it is that day (games.csv from fetch_data.py has later scores removed)
if _AS_OF and os.path.exists('games.csv'):
    _g = pd.read_csv('games.csv'); _g = _g[(_g.season == SEASON) & (_g.game_type == 'REG') & _g.home_score.notna()]
    _LASTW = int(_g.week.max()) if len(_g) else 0
    st = st[(st.season != SEASON) | (st.week <= _LASTW)]
# ---------- expected fantasy points (PPR) from opportunities: average PPR per target by depth and field position, per carry by field position
C = ['season', 'week', 'game_id', 'play_type', 'posteam', 'receiver_player_id', 'rusher_player_id', 'air_yards', 'yardline_100', 'complete_pass', 'yards_gained',
     'touchdown', 'pass_touchdown', 'rush_touchdown', 'qb_kneel', 'sack', 'two_point_attempt']
pb = pd.concat([pd.read_parquet(f'pbp_{y}.parquet', columns=C) for y in YEARS if os.path.exists(f'pbp_{y}.parquet')]); pb = pb[pb.two_point_attempt != 1]
if _AS_OF: pb = pb[(pb.season != SEASON) | (pb.week <= _LASTW)]
yb = lambda y: pd.cut(y, [0, 5, 10, 20, 50, 100], labels=['1-5', '6-10', '11-20', '21-50', '51+'])
tg = pb[(pb.play_type == 'pass') & pb.receiver_player_id.notna() & (pb.sack != 1)].copy()
tg['ab'] = pd.cut(tg.air_yards.fillna(-99), [-100, -50, 0, 5, 10, 15, 20, 30, 120], labels=['na', '<=0', '1-5', '6-10', '11-15', '16-20', '21-30', '31+']); tg['yb'] = yb(tg.yardline_100)
tg['out'] = tg.complete_pass.fillna(0) * (1 + 0.1 * tg.yards_gained.fillna(0)) + 6 * tg.pass_touchdown.fillna(0)
ru = pb[(pb.play_type == 'run') & pb.rusher_player_id.notna() & (pb.qb_kneel != 1)].copy(); ru['yb'] = pd.cut(ru.yardline_100, [0, 2, 5, 10, 20, 50, 100], labels=['1-2', '3-5', '6-10', '11-20', '21-50', '51+'])
ru['out'] = 0.1 * ru.yards_gained.fillna(0) + 6 * ru.rush_touchdown.fillna(0)
tr = lambda d: d[d.season.isin(TRAIN)]   # learned before the test season
xt = tr(tg).groupby(['ab', 'yb'], observed=True).out.mean(); xr = tr(ru).groupby('yb', observed=True).out.mean()
tg['x'] = [xt.get((a, b), np.nan) for a, b in zip(tg.ab, tg.yb)]; ru['x'] = ru.yb.map(xr).astype(float)
tg['rz'] = (tg.yardline_100 <= 20).astype(int); ru['rz'] = (ru.yardline_100 <= 20).astype(int)
X = pd.concat([tg.groupby(['season', 'week', 'receiver_player_id']).agg(xr=('x', 'sum'), rzt=('rz', 'sum')).rename_axis(['season', 'week', 'player_id']),
               ru.groupby(['season', 'week', 'rusher_player_id']).agg(xc=('x', 'sum'), rzc=('rz', 'sum')).rename_axis(['season', 'week', 'player_id'])], axis=1).fillna(0).reset_index()
X['xfp'] = X.xr + X.xc; X['rzo'] = X.rzt + X.rzc
st = st.merge(X[['season', 'week', 'player_id', 'xfp', 'rzo']], on=['season', 'week', 'player_id'], how='left'); st[['xfp', 'rzo']] = st[['xfp', 'rzo']].fillna(0)
print('xFP model: avg PPR per target by depth/field position learned from', len(tr(tg)), 'targets and', len(tr(ru)), 'carries', flush=True)
# ---------- snap share (PFR ids -> gsis)
ids = pd.read_csv('player_ids.csv', low_memory=False); pfr2g = ids.dropna(subset=['pfr_id', 'gsis_id']).drop_duplicates('pfr_id').set_index('pfr_id').gsis_id.to_dict()
sn = pd.concat([pd.read_parquet(f'snap_counts_{y}.parquet') for y in YEARS if os.path.exists(f'snap_counts_{y}.parquet')]); sn = sn[sn.game_type == 'REG']; sn['player_id'] = sn.pfr_player_id.map(pfr2g)
st = st.merge(sn[['season', 'week', 'player_id', 'offense_pct']].dropna(subset=['player_id']).drop_duplicates(['season', 'week', 'player_id']), on=['season', 'week', 'player_id'], how='left')
tc = st.groupby(['season', 'week', 'team']).carries.sum().rename('team_car').reset_index(); st = st.merge(tc, on=['season', 'week', 'team'])
st['car_share'] = np.where(st.team_car > 0, st.carries / st.team_car, np.nan)
# ---------- schedule and Vegas implied team totals (nflverse games file; fetch_data.py saves it as games.csv)
if os.path.exists('games.csv'): gm = pd.read_csv('games.csv')
else: gm = pd.read_csv(io.BytesIO(urllib.request.urlopen('https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv', timeout=120).read()))
gm = gm[gm.season.between(SEASON - 5, SEASON) & (gm.game_type == 'REG')]
rows = []
for g in gm.itertuples():
    for t, o, home in ((g.home_team, g.away_team, 1), (g.away_team, g.home_team, 0)):
        it = np.nan if pd.isna(g.total_line) or pd.isna(g.spread_line) else (g.total_line / 2 + (g.spread_line / 2 if home else -g.spread_line / 2))
        rows.append((g.season, g.week, t, o, home, it, g.home_score if home else g.away_score))
SC = pd.DataFrame(rows, columns=['season', 'week', 'team', 'opp', 'home', 'it', 'pts'])
st = st.merge(SC[['season', 'week', 'team', 'home', 'it']], on=['season', 'week', 'team'], how='left')


# ---------- fantasy points allowed by each defense to each position (shrunk toward the league average)
def dvp_table(s, before):
    d = st[(st.season == s) & (st.week < before)]
    a = d.groupby(['opponent_team', 'position', 'week']).fp.sum().reset_index().groupby(['opponent_team', 'position']).fp.agg(['sum', 'count'])
    lg = d.groupby(['position', 'week', 'opponent_team']).fp.sum().groupby('position').mean()
    return a, lg


def dvp_factor(s, before, team, pos, k=4):
    a, lg = DV.get((s, before)) or DV.setdefault((s, before), dvp_table(s, before))
    base = lg.get(pos, np.nan)
    if (team, pos) not in a.index or not base == base: return np.nan
    sm, c = a.loc[(team, pos)]; return float((sm + k * base) / (c + k) / base)


DV = {}


def ew(x, h=EW_H):
    """recent form: weighted mean of the games BEFORE each index (latest game weight 1, halving every h games); skips missing values.
    Returns (means, total weight) for indexes 0..n, so index n is the form going into the next game."""
    d = 0.5 ** (1 / h); s = w = 0.0; n = len(x); out = np.full(n + 1, np.nan); wt = np.zeros(n + 1)
    for i in range(n + 1):
        out[i] = s / w if w > 0 else np.nan; wt[i] = w
        if i == n: break
        v = x[i]; s *= d; w *= d
        if v == v: s += v; w += 1.0
    return out, wt


_idx = ids.dropna(subset=['gsis_id']).drop_duplicates('gsis_id').set_index('gsis_id')
DPICK = {g: (float(p) if p == p else (float(r_) * 32 - 16 if r_ == r_ else np.nan)) for g, p, r_ in zip(_idx.index, _idx.draft_ovr, _idx.draft_round)}
DYEAR = _idx.draft_year.to_dict()


def draft_feats(pid, s):
    dy = DYEAR.get(pid, np.nan); return DPICK.get(pid, np.nan), ((s - dy) if dy == dy else np.nan)


def _nanmean(a): a = a[np.isfinite(a)]; return float(a.mean()) if len(a) else np.nan


def feats(s, t, p_rows, team_opp=None):
    """features going into a player's next game, from his games so far this season (p_rows, oldest first)"""
    pr = p_rows; g = len(pr); f = {'g': g}
    fp = pr.fp.values.astype(float); xf = pr.xfp.values.astype(float); snp = pr.offense_pct.values.astype(float)
    ts_ = pr.target_share.values.astype(float); cs_ = pr.car_share.values.astype(float)
    f.update(ppg=fp.mean() if g else np.nan, xpg=xf.mean() if g else np.nan, l3=fp[-3:].mean() if g else np.nan, snap=_nanmean(snp) if g else np.nan,
             ts=_nanmean(ts_) if g else np.nan, cs=_nanmean(cs_) if g else np.nan, rz=pr.rzo.values.mean() if g else np.nan)
    for nm, arr in (('efp', fp), ('exf', xf), ('esn', snp), ('ets', ts_), ('ecs', cs_)):
        v, w = ew(arr); f[nm] = v[-1]
        if nm == 'efp': f['ew'] = w[-1]
    return f


st = st.sort_values(['player_id', 'season', 'week'])
prev = st.groupby(['player_id', 'season']).agg(pg=('fp', 'mean'), gg=('fp', 'size')).reset_index(); prev['season'] += 1; prev = prev[prev.gg >= 3].set_index(['player_id', 'season']).pg
F = ['g', 'ppg', 'xpg', 'l3', 'snap', 'ts', 'cs', 'rz', 'prev', 'dvp', 'it', 'home']
EWF = ['efp', 'exf', 'esn', 'ets', 'ecs']


def _season_files(s):
    """that season's weekly rosters and injury reports (downloaded by fetch_data.py; missing files mean no teammate signal)"""
    return read_opt(f'roster_weekly_{s}.parquet', columns=['gsis_id', 'team', 'week', 'status']), read_opt(f'injuries_{s}.parquet')


def situ(D, s):
    """teammates missing for each player-game of season s: expected points vacated by injured or reserve teammates at his
    position group, shared out by his recent expected points, and whether the starting QB was out. Same rule as the live site."""
    wr_s, inj_s = _season_files(s)
    out = {}
    if wr_s is None and inj_s is None: return out
    S = st[st.season == s]
    if inj_s is not None:
        inj_s = inj_s[inj_s.report_status.isin(['Out', 'Doubtful'])]
        OUTW = inj_s.groupby(['team', 'week']).gsis_id.apply(set).to_dict()
    else: OUTW = {}
    RESW = wr_s[wr_s.status == 'RES'].groupby(['team', 'week']).gsis_id.apply(set).to_dict() if wr_s is not None else {}
    for tm, G in S.groupby('team'):
        weeks = sorted(G.week.unique())
        for w in sorted(SC[(SC.season == s) & (SC.team == tm)].week.unique()):
            prior = [x for x in weeks if x < w][-3:]
            if not prior: continue
            rec = G[G.week.isin(prior)].groupby('player_id').agg(xpg=('xfp', 'mean'), gp=('week', 'nunique'), pos=('position', 'first'), att=('attempts', 'sum'))
            rec = rec[rec.gp >= min(2, len(prior))]
            outset = OUTW.get((tm, w), set()) | RESW.get((tm, w), set())
            if not outset: continue
            miss = rec[rec.index.isin(outset)]; pres = rec[~rec.index.isin(outset)]; qb = rec[rec.pos == 'QB'].sort_values('att', ascending=False)
            qbm = int(len(qb) > 0 and qb.index[0] in outset and qb.att.iloc[0] >= 40)
            vr = float(miss[(miss.pos == 'RB') & (miss.xpg >= 4)].xpg.sum()); vw = float(miss[miss.pos.isin(['WR', 'TE']) & (miss.xpg >= 4)].xpg.sum())
            totR = float(pres[pres.pos == 'RB'].xpg.sum()); totW = float(pres[pres.pos.isin(['WR', 'TE'])].xpg.sum())
            for pid in G[G.week == w].player_id:
                pos = G[G.player_id == pid].position.iloc[0]; xp = float(pres.loc[pid, 'xpg']) if pid in pres.index else 0.0
                bump = (vr * xp / totR if pos == 'RB' and totR > 0 else vw * xp / totW if pos in ('WR', 'TE') and totW > 0 else 0.0)
                out[(pid, s, int(w))] = (bump, qbm, vr + vw)
    return out


def build(seasons):
    """one row per player-game (week 2 on) with the features known before kickoff and the points he scored (y)"""
    parts = []
    for s in seasons:
        cf = f'{CACHE}/feat_{FEAT_VER}_{s}.parquet'
        if s < SEASON and os.path.exists(cf):
            parts.append(pd.read_parquet(cf)); continue
        out = []
        for pid, grp in st[st.season == s].groupby('player_id', sort=False):
            n = len(grp); fp = grp.fp.values.astype(float); xf = grp.xfp.values.astype(float); snp = grp.offense_pct.values.astype(float)
            ts_ = grp.target_share.values.astype(float); cs_ = grp.car_share.values.astype(float); rz = grp.rzo.values.astype(float); wk = grp.week.values
            opp = grp.opponent_team.values; pos = grp.position.iloc[0]; itv = grp.it.values; hm = grp.home.values
            cfp = np.concatenate([[0], np.cumsum(fp)]); cxf = np.concatenate([[0], np.cumsum(xf)]); crz = np.concatenate([[0], np.cumsum(rz)])
            E = {nm: ew(arr) for nm, arr in (('efp', fp), ('exf', xf), ('esn', snp), ('ets', ts_), ('ecs', cs_))}
            pv = prev.get((pid, s), np.nan); dp, yrs = draft_feats(pid, s)
            for i in range(n):
                w = int(wk[i])
                if w < 2: continue
                f = {'player_id': pid, 'season': s, 'week': w, 'pos': pos, 'y': fp[i], 'g': i,
                     'ppg': cfp[i] / i if i else np.nan, 'xpg': cxf[i] / i if i else np.nan, 'l3': fp[max(0, i - 3):i].mean() if i else np.nan,
                     'snap': _nanmean(snp[:i]) if i else np.nan, 'ts': _nanmean(ts_[:i]) if i else np.nan, 'cs': _nanmean(cs_[:i]) if i else np.nan,
                     'rz': crz[i] / i if i else np.nan, 'prev': pv, 'dvp': dvp_factor(s, w, opp[i], pos) if w > 2 else np.nan, 'it': itv[i], 'home': hm[i],
                     'dpick': dp, 'yrs': yrs, 'ew': E['efp'][1][i]}
                for nm in EWF: f[nm] = E[nm][0][i]
                out.append(f)
        D = pd.DataFrame(out)
        sit = situ(D, s); key = list(zip(D.player_id, D.season, D.week))
        D['bump'] = [sit.get(k, (0.0, 0, 0.0))[0] for k in key]; D['qbm'] = [sit.get(k, (0.0, 0, 0.0))[1] for k in key]; D['vac_all'] = [sit.get(k, (0.0, 0, 0.0))[2] for k in key]
        if s < SEASON:
            try: os.makedirs(CACHE, exist_ok=True); D.to_parquet(cf)
            except Exception as e: print('feature cache not saved:', e)
        parts.append(D); print(f'features {s}: {len(D)} player-games', flush=True)
    return pd.concat(parts, ignore_index=True)


if __name__ == '__main__':
    D = build(HIST); print(D.groupby('season').size().to_dict()); print(D[['bump', 'qbm', 'vac_all', 'efp', 'ew']].describe().T)
