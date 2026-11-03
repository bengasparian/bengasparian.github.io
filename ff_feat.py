"""BFF features (version 5): one row per player-game with everything known before kickoff.

Built for the research backtests and (once tested) the live site. Each row's features come only from
  - the player's earlier games this season (season-to-date averages and recent form, which fades by half every 2.5 games),
  - his previous two seasons (and his draft slot when he has no NFL history),
  - his team's and his opponent's earlier games this season (pace, pass rate over expected, efficiency, points),
  - pre-game facts: Vegas lines, home field, dome, rest, his injury-report status and practice participation, the depth
    chart, and teammates ruled out.
The target y is the PPR points he scored. Week 1 rows are included (they lean on last season and the draft slot).
"""
import os, numpy as np, pandas as pd

POS = ['QB', 'RB', 'WR', 'TE']
EW_H = 2.5


def _read(p, **kw):
    try: return pd.read_parquet(p, **kw) if os.path.exists(p) else None
    except Exception as e: print('could not read', p, e); return None


def ew(x, h=EW_H):
    """weighted mean of the values BEFORE each index (latest weight 1, halving every h games; a missing value still ages
    the older ones). Returns (means, total weight) for indexes 0..n-1."""
    d = 0.5 ** (1 / h); s = w = 0.0; n = len(x); out = np.full(n, np.nan); wt = np.zeros(n)
    for i in range(n):
        out[i] = s / w if w > 0 else np.nan; wt[i] = w
        v = x[i]; s *= d; w *= d
        if v == v: s += v; w += 1.0
    return out, wt


def cmean(x):
    """mean of the values before each index (NaN-aware)"""
    v = np.nan_to_num(x); c = np.isfinite(x).astype(float)
    cs = np.concatenate([[0], np.cumsum(v)])[:-1]; cn = np.concatenate([[0], np.cumsum(c)])[:-1]
    with np.errstate(invalid='ignore', divide='ignore'): return np.where(cn > 0, cs / np.maximum(cn, 1), np.nan)


# columns averaged per game (season to date and recent form)
STATC = {'fp': 'fp', 'xfp': 'xfp', 'snap': 'offense_pct', 'ts': 'target_share', 'cs': 'car_share', 'rz': 'rzo',
         'ays': 'air_yards_share', 'tgt': 'targets', 'rec': 'receptions', 'recy': 'receiving_yards', 'rectd': 'receiving_tds',
         'car': 'carries', 'rush': 'rushing_yards', 'rushtd': 'rushing_tds', 'att': 'attempts', 'pass': 'passing_yards',
         'ptd': 'passing_tds', 'int': 'passing_interceptions', 'pepa': 'passing_epa', 'cpoe': 'passing_cpoe',
         'repa': 'receiving_epa', 'ruepa': 'rushing_epa', 'yac': 'receiving_yards_after_catch', 'aird': 'receiving_air_yards',
         'sk': 'sacks_suffered', 'gl': 'glc', 'xs': 'xshare'}
LASTC = ['fp', 'xfp', 'snap', 'ts', 'cs', 'ays', 'tgt', 'car', 'att', 'rush', 'xs']


def load(years, xfp_years, rates=None):
    """weekly player stats with expected points (xfp), red-zone and goal-line chances, snap/carry shares; play-by-play
    team tables; the schedule with Vegas lines"""
    st = pd.concat([pd.read_parquet(f'stats_player_week_{y}.parquet') for y in years if os.path.exists(f'stats_player_week_{y}.parquet')])
    st = st[(st.season_type == 'REG') & st.position.isin(POS)].copy(); st['fp'] = st.fantasy_points_ppr
    C = ['season', 'week', 'game_id', 'play_type', 'posteam', 'defteam', 'receiver_player_id', 'rusher_player_id', 'air_yards', 'yardline_100',
         'complete_pass', 'yards_gained', 'pass_touchdown', 'rush_touchdown', 'qb_kneel', 'qb_spike', 'sack', 'two_point_attempt', 'epa', 'qb_dropback',
         'pass', 'rush', 'pass_oe', 'season_type']
    pb = pd.concat([pd.read_parquet(f'pbp_{y}.parquet', columns=C) for y in years if os.path.exists(f'pbp_{y}.parquet')])
    pb = pb[(pb.season_type == 'REG') & (pb.two_point_attempt != 1)]
    yb = lambda y: pd.cut(y, [0, 5, 10, 20, 50, 100], labels=['1-5', '6-10', '11-20', '21-50', '51+'])
    tg = pb[(pb.play_type == 'pass') & pb.receiver_player_id.notna() & (pb.sack != 1)].copy()
    tg['ab'] = pd.cut(tg.air_yards.fillna(-99), [-100, -50, 0, 5, 10, 15, 20, 30, 120], labels=['na', '<=0', '1-5', '6-10', '11-15', '16-20', '21-30', '31+']); tg['yb'] = yb(tg.yardline_100)
    tg['out'] = tg.complete_pass.fillna(0) * (1 + 0.1 * tg.yards_gained.fillna(0)) + 6 * tg.pass_touchdown.fillna(0)
    ru = pb[(pb.play_type == 'run') & pb.rusher_player_id.notna() & (pb.qb_kneel != 1)].copy()
    ru['yb'] = pd.cut(ru.yardline_100, [0, 2, 5, 10, 20, 50, 100], labels=['1-2', '3-5', '6-10', '11-20', '21-50', '51+'])
    ru['out'] = 0.1 * ru.yards_gained.fillna(0) + 6 * ru.rush_touchdown.fillna(0)
    if rates:   # saved from an earlier run (the seasons they were learned from need not be downloaded again)
        xt = {tuple(k.split('|')): v for k, v in rates['t'].items()}; xr = rates['r']
    else:
        xt = tg[tg.season.isin(xfp_years)].groupby(['ab', 'yb'], observed=True).out.mean(); xr = ru[ru.season.isin(xfp_years)].groupby('yb', observed=True).out.mean()
        xt = {(str(a), str(b)): float(v) for (a, b), v in xt.items()}; xr = {str(k): float(v) for k, v in xr.items()}
    tg['x'] = [xt.get((str(a), str(b)), np.nan) for a, b in zip(tg.ab, tg.yb)]; ru['x'] = ru.yb.astype(str).map(xr).astype(float)
    tg['rz'] = (tg.yardline_100 <= 20).astype(int); ru['rz'] = (ru.yardline_100 <= 20).astype(int); ru['gl'] = (ru.yardline_100 <= 5).astype(int)
    X = pd.concat([tg.groupby(['season', 'week', 'receiver_player_id']).agg(xr=('x', 'sum'), rzt=('rz', 'sum')).rename_axis(['season', 'week', 'player_id']),
                   ru.groupby(['season', 'week', 'rusher_player_id']).agg(xc=('x', 'sum'), rzc=('rz', 'sum'), glc=('gl', 'sum')).rename_axis(['season', 'week', 'player_id'])], axis=1).fillna(0).reset_index()
    X['xfp'] = X.xr + X.xc; X['rzo'] = X.rzt + X.rzc
    st = st.merge(X[['season', 'week', 'player_id', 'xfp', 'rzo', 'glc']], on=['season', 'week', 'player_id'], how='left'); st[['xfp', 'rzo', 'glc']] = st[['xfp', 'rzo', 'glc']].fillna(0)
    ids = pd.read_csv('player_ids.csv', low_memory=False); pfr2g = ids.dropna(subset=['pfr_id', 'gsis_id']).drop_duplicates('pfr_id').set_index('pfr_id').gsis_id.to_dict()
    sn = pd.concat([pd.read_parquet(f'snap_counts_{y}.parquet') for y in years if os.path.exists(f'snap_counts_{y}.parquet')]); sn = sn[sn.game_type == 'REG']; sn['player_id'] = sn.pfr_player_id.map(pfr2g)
    st = st.merge(sn[['season', 'week', 'player_id', 'offense_pct']].dropna(subset=['player_id']).drop_duplicates(['season', 'week', 'player_id']), on=['season', 'week', 'player_id'], how='left')
    tc = st.groupby(['season', 'week', 'team']).carries.sum().rename('team_car').reset_index(); st = st.merge(tc, on=['season', 'week', 'team'])
    st['car_share'] = np.where(st.team_car > 0, st.carries / st.team_car, np.nan)
    gm = pd.read_csv('games.csv'); gm = gm[gm.season.isin(years) & (gm.game_type == 'REG')]
    rows = []
    for g in gm.itertuples():
        for t, o, home in ((g.home_team, g.away_team, 1), (g.away_team, g.home_team, 0)):
            ok = not (pd.isna(g.total_line) or pd.isna(g.spread_line)); sp = (g.spread_line if home else -g.spread_line) if ok else np.nan
            rows.append((g.season, g.week, t, o, home, (g.total_line / 2 + sp / 2) if ok else np.nan, sp, g.total_line if ok else np.nan,
                         g.home_score if home else g.away_score, g.away_score if home else g.home_score, int(str(g.roof) in ('dome', 'closed')),
                         ((g.home_rest - g.away_rest) if home else (g.away_rest - g.home_rest)), g.div_game, g.gameday))
    SC = pd.DataFrame(rows, columns=['season', 'week', 'team', 'opp', 'home', 'it', 'spread', 'total', 'pts', 'pa', 'dome', 'rest', 'div', 'gameday'])
    st = st.merge(SC[['season', 'week', 'team', 'home', 'it', 'spread', 'total', 'dome', 'rest', 'div']], on=['season', 'week', 'team'], how='left')
    RATES = {'t': {f'{a}|{b}': v for (a, b), v in xt.items()}, 'r': xr}
    return st, pb, SC, ids, RATES


def team_tables(pb, SC):
    """per team and week: offense (plays, pass rate over expected, EPA per play, points) and defense (EPA per dropback and per
    rush allowed, points allowed). Going into week w each is the season-to-date average shrunk toward a prior worth 4 games
    (half last season's full-season figure, half the league average)."""
    p = pb[pb.play_type.isin(['pass', 'run']) & (pb.qb_kneel != 1) & (pb.qb_spike != 1)].copy()
    off = p.groupby(['season', 'posteam', 'week']).agg(plays=('epa', 'size'), proe=('pass_oe', 'mean'), oepa=('epa', 'mean'), prate=('pass', 'mean')).reset_index().rename(columns={'posteam': 'team'})
    dp = p[p.qb_dropback == 1].groupby(['season', 'defteam', 'week']).epa.mean().rename('dpass')
    dr = p[p.rush == 1].groupby(['season', 'defteam', 'week']).epa.mean().rename('drush')
    de = pd.concat([dp, dr], axis=1).reset_index().rename(columns={'defteam': 'team'})
    T = SC[['season', 'week', 'team', 'pts', 'pa']].merge(off, on=['season', 'week', 'team'], how='left').merge(de, on=['season', 'week', 'team'], how='left')
    T = T.sort_values(['team', 'season', 'week']); cols = ['plays', 'proe', 'oepa', 'prate', 'dpass', 'drush', 'pts', 'pa']
    full = T.groupby(['season', 'team'])[cols].mean(); lg = T.groupby('season')[cols].mean()
    out = []
    for (s, tm), G in T.groupby(['season', 'team']):
        G = G.sort_values('week'); prior = {}
        for c in cols:
            l_ = lg.loc[s, c] if s in lg.index else np.nan; lp = lg.loc[s - 1, c] if (s - 1) in lg.index else l_
            last = full.loc[(s - 1, tm), c] if (s - 1, tm) in full.index else lp
            prior[c] = 0.5 * last + 0.5 * lp if last == last else lp
        played = G.pts.notna().values
        for c in cols:
            v = np.where(played, G[c].values.astype(float), np.nan); cm = cmean(v); n = np.concatenate([[0], np.cumsum(np.isfinite(v))])[:-1]
            G[c + '_t'] = np.where(n > 0, (np.nan_to_num(cm) * n + 4 * prior[c]) / (n + 4), prior[c])
        out.append(G)
    T = pd.concat(out)
    return T[['season', 'week', 'team'] + [c + '_t' for c in cols]]


def dvp_all(st, k=4):
    """fantasy points allowed by each defense to each position before each week, as a ratio to the league average (shrunk)"""
    a = st.groupby(['season', 'week', 'opponent_team', 'position']).fp.sum().reset_index()
    out = {}
    for (s, pos), G in a.groupby(['season', 'position']):
        weeks = sorted(G.week.unique())
        for w in range(1, int(max(weeks)) + 2):
            d = G[G.week < w]
            if not len(d): continue
            base = d.fp.mean(); t = d.groupby('opponent_team').fp.agg(['sum', 'count'])
            for tm, r_ in t.iterrows(): out[(s, w, tm, pos)] = float((r_['sum'] + k * base) / (r_['count'] + k) / base)
    return out


def depth_table(years, SC):
    """depth-chart string (1 = starter) for each player and week, offense only. Old files list a week; newer ones are daily
    snapshots, so each week takes the last snapshot before that week's first game."""
    rows = []
    MAP = {'QB': 'QB', 'RB': 'RB', 'HB': 'RB', 'WR': 'WR', 'LWR': 'WR', 'RWR': 'WR', 'SWR': 'WR', 'TE': 'TE'}
    for y in years:
        d = _read(f'depth_charts_{y}.parquet')
        if d is None: continue
        if 'week' in d.columns:
            d = d[(d.formation == 'Offense') & d.depth_position.isin(MAP) & d.week.notna()]
            d = d.assign(pos=d.depth_position.map(MAP), dc=pd.to_numeric(d.depth_team, errors='coerce'))
            rows.append(d.groupby(['season', 'week', 'gsis_id']).dc.min().reset_index())
        else:
            d = d[d.pos_abb.isin(['QB', 'RB', 'WR', 'TE']) & (d.pos_grp != 'Special Teams')].copy(); d['day'] = pd.to_datetime(d.dt.str[:10])
            first = SC[SC.season == y].groupby('week').gameday.min()
            for w, gd in first.items():
                snap = d[d.day < pd.Timestamp(gd)]
                if not len(snap): continue
                last = snap[snap.day == snap.day.max()]
                g_ = last.groupby('gsis_id').pos_rank.min().reset_index().rename(columns={'pos_rank': 'dc'}); g_['season'] = y; g_['week'] = w; rows.append(g_)
    return pd.concat(rows) if rows else pd.DataFrame(columns=['season', 'week', 'gsis_id', 'dc'])


def inj_table(years):
    """that week's injury report for the player himself: questionable (1/0) and the last practice (0 did not practice,
    1 limited, 2 full; NaN = not on the report)"""
    rows = []
    for y in years:
        d = _read(f'injuries_{y}.parquet')
        if d is None: continue
        d = d[d.game_type == 'REG'] if 'game_type' in d.columns else d
        pr = d.practice_status.fillna('').str.lower()
        d = d.assign(q=(d.report_status == 'Questionable').astype(int), prac=np.select([pr.str.contains('did not'), pr.str.contains('limited'), pr.str.contains('full')], [0, 1, 2], np.nan))
        rows.append(d[['season', 'week', 'gsis_id', 'q', 'prac']].drop_duplicates(['season', 'week', 'gsis_id'], keep='last'))
    return pd.concat(rows) if rows else pd.DataFrame(columns=['season', 'week', 'gsis_id', 'q', 'prac'])


def situ(st, SC, s):
    """teammates missing (same rule as the live site): expected points vacated by Out/Doubtful/reserve teammates at the
    player's position group, shared out by his recent expected points; and whether the starting QB is out"""
    wr_s = _read(f'roster_weekly_{s}.parquet', columns=['gsis_id', 'team', 'week', 'status']); inj_s = _read(f'injuries_{s}.parquet')
    out = {}
    if wr_s is None and inj_s is None: return out
    S = st[st.season == s]
    OUTW = inj_s[inj_s.report_status.isin(['Out', 'Doubtful'])].groupby(['team', 'week']).gsis_id.apply(set).to_dict() if inj_s is not None else {}
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
            for pid, pos in G[G.week == w][['player_id', 'position']].values:
                xp = float(pres.loc[pid, 'xpg']) if pid in pres.index else 0.0
                bump = (vr * xp / totR if pos == 'RB' and totR > 0 else vw * xp / totW if pos in ('WR', 'TE') and totW > 0 else 0.0)
                out[(pid, s, int(w))] = (bump, qbm, vr + vw)
    return out


class Ctx:
    """everything the features need besides the player's own games: stats with xFP and shares, team tables, matchup
    ratios, depth charts, injury reports, last-season profiles, draft slots"""
    def __init__(self, years, xfp_years, rates=None):
        st, pb, SC, ids, self.rates = load(years, xfp_years, rates)
        st = st.sort_values(['player_id', 'season', 'week'])
        txf = st.groupby(['season', 'week', 'team']).xfp.sum().rename('team_xfp').reset_index(); st = st.merge(txf, on=['season', 'week', 'team'], how='left')
        st['xshare'] = np.where(st.team_xfp > 0, st.xfp / st.team_xfp, np.nan)
        agg = st.groupby(['player_id', 'season']).agg(p_fp=('fp', 'mean'), p_g=('fp', 'size'), p_xfp=('xfp', 'mean'), p_snap=('offense_pct', 'mean'),
                                                       p_ts=('target_share', 'mean'), p_ays=('air_yards_share', 'mean'), p_cs=('car_share', 'mean'),
                                                       p_team=('team', lambda x: x.mode().iloc[0])).reset_index()
        self.P1 = agg.assign(season=agg.season + 1)
        self.P2 = agg[['player_id', 'season', 'p_fp', 'p_g']].assign(season=agg.season + 2).rename(columns={'p_fp': 'p2_fp', 'p_g': 'p2_g'})
        self.st, self.pb, self.SC, self.ids = st, pb, SC, ids
        self.TT = team_tables(pb, SC); self.DV = dvp_all(st); self.DC = depth_table(years, SC); self.IJ = inj_table(years)
        self.DVW = {}
        for (s_, w_, t_, p_) in self.DV: self.DVW[(s_, t_, p_)] = max(w_, self.DVW.get((s_, t_, p_), 0))
        _i = ids.dropna(subset=['gsis_id']).drop_duplicates('gsis_id').set_index('gsis_id')
        self.DPICK = {g: (float(p) if p == p else (float(r_) * 32 - 16 if r_ == r_ else np.nan)) for g, p, r_ in zip(_i.index, _i.draft_ovr, _i.draft_round)}
        self.DYEAR = _i.draft_year.to_dict()

    def dvp(self, s, w, opp, pos):
        """matchup ratio going into week w (weeks past the latest played week use the latest one)"""
        v = self.DV.get((s, w, opp, pos))
        if v is None:
            lw = self.DVW.get((s, opp, pos))
            if lw and w > lw: v = self.DV.get((s, lw, opp, pos))
        return np.nan if v is None else v

    def block(self, pid, s, grp):
        """history features for each of his n games this season (from the games before it) plus a row n: going into his
        next game"""
        n = len(grp); f = {'player_id': np.repeat(pid, n + 1), 'season': s, 'g': np.arange(n + 1),
                           'y': np.concatenate([grp.fp.values.astype(float), [np.nan]])}
        for k, c in STATC.items():
            x = grp[c].values.astype(float) if c in grp else np.full(n, np.nan)
            f['m_' + k] = cmean1(x); e, wt = ew1(x); f['e_' + k] = e
            if k == 'fp': f['ew'] = wt
            if k in LASTC:
                f['l1_' + k] = np.concatenate([[np.nan], x])[:n + 1]; f['l2_' + k] = np.concatenate([[np.nan, np.nan], x])[:n + 1]
        fpv = grp.fp.values.astype(float); f['l3'] = np.array([fpv[max(0, i - 3):i].mean() if i else np.nan for i in range(n + 1)])
        dy = self.DYEAR.get(pid, np.nan); f['dpick'] = self.DPICK.get(pid, np.nan); f['yrs'] = (s - dy) if dy == dy else np.nan
        f['lastwk'] = np.concatenate([[np.nan], grp.week.values.astype(float)])
        return pd.DataFrame(f)

    def context(self, D, sit=None):
        """D has player_id, season, week, pos, team, opp, home, it, spread, total, dome, rest, div, lastwk: adds last-season
        profiles, team and opponent tables, matchup ratio, depth chart, injury report and teammates out"""
        D = D.merge(self.P1, on=['player_id', 'season'], how='left').merge(self.P2, on=['player_id', 'season'], how='left')
        D['newteam'] = np.where(D.p_team.notna(), (D.p_team != D.team).astype(float), np.nan); D = D.drop(columns=['p_team'])
        D = D.merge(self.TT, on=['season', 'week', 'team'], how='left')
        o = self.TT.rename(columns={c: 'o_' + c for c in self.TT.columns if c.endswith('_t')}).rename(columns={'team': 'opp'})
        D = D.merge(o, on=['season', 'week', 'opp'], how='left')
        D['dvp'] = [self.dvp(s_, w_, o_, p_) for s_, w_, o_, p_ in zip(D.season, D.week, D.opp, D.pos)]
        D = D.merge(self.DC.rename(columns={'gsis_id': 'player_id'}), on=['season', 'week', 'player_id'], how='left')
        D = D.merge(self.IJ.rename(columns={'gsis_id': 'player_id'}), on=['season', 'week', 'player_id'], how='left'); D['q'] = D.q.fillna(0)
        D['gap'] = D.week - D.lastwk; D = D.drop(columns=['lastwk'])
        if sit is not None:
            key = list(zip(D.player_id, D.season, D.week))
            D['bump'] = [sit.get(k, (0.0, 0, 0.0))[0] for k in key]; D['qbm'] = [sit.get(k, (0.0, 0, 0.0))[1] for k in key]; D['vac_all'] = [sit.get(k, (0.0, 0, 0.0))[2] for k in key]
        return D

    def season_rows(self, s):
        """one row per player-game of season s (features from before kickoff, y = the PPR points he scored)"""
        S = self.st[self.st.season == s]; out = []
        GC = ['home', 'it', 'spread', 'total', 'dome', 'rest', 'div']
        for pid, grp in S.groupby('player_id', sort=False):
            B = self.block(pid, s, grp).iloc[:len(grp)].copy()
            B['week'] = grp.week.values.astype(int); B['pos'] = grp.position.iloc[0]; B['team'] = grp.team.values; B['opp'] = grp.opponent_team.values
            for c in GC: B[c] = grp[c].values
            out.append(B)
        D = self.context(pd.concat(out, ignore_index=True), situ(self.st, self.SC, s))
        print(f'features {s}: {len(D)} player-games', flush=True); return D

    def upcoming(self, s, before_week, players, games):
        """rows for games not yet played: players = {pid: pos}; games = {pid: [(week, team, opp, home, it, spread, total,
        dome, rest, div), ...]}. Features come from his games this season before before_week; teammates-out features are
        left at 0 (the caller sets them from the current injury report)."""
        S = self.st[(self.st.season == s) & (self.st.week < before_week)]; G = dict(tuple(S.groupby('player_id', sort=False))); out = []
        for pid, pos in players.items():
            grp = G.get(pid, S.iloc[:0]); B = self.block(pid, s, grp).iloc[[len(grp)]]
            for (w, tm, op, hm, it, sp, tot, dm, rs, dv) in games.get(pid, []):
                r_ = B.copy(); r_['week'] = int(w); r_['pos'] = pos; r_['team'] = tm; r_['opp'] = op
                for c, v in zip(['home', 'it', 'spread', 'total', 'dome', 'rest', 'div'], [hm, it, sp, tot, dm, rs, dv]): r_[c] = v
                out.append(r_)
        if not out: return pd.DataFrame()
        D = self.context(pd.concat(out, ignore_index=True)); D['bump'] = 0.0; D['qbm'] = 0; D['vac_all'] = 0.0; return D


def ew1(x, h=EW_H):
    """like ew, with one more entry: going into the next game"""
    d = 0.5 ** (1 / h); s = w = 0.0; n = len(x); out = np.full(n + 1, np.nan); wt = np.zeros(n + 1)
    for i in range(n + 1):
        out[i] = s / w if w > 0 else np.nan; wt[i] = w
        if i == n: break
        v = x[i]; s *= d; w *= d
        if v == v: s += v; w += 1.0
    return out, wt


def cmean1(x):
    v = np.nan_to_num(x); c = np.isfinite(x).astype(float)
    cs = np.concatenate([[0], np.cumsum(v)]); cn = np.concatenate([[0], np.cumsum(c)])
    with np.errstate(invalid='ignore', divide='ignore'): return np.where(cn > 0, cs / np.maximum(cn, 1), np.nan)


def build(years, xfp_years, first_season=None):
    """the feature table for seasons >= first_season (earlier years only feed 'last season' features)"""
    C = Ctx(years, xfp_years); first_season = first_season or min(years)
    return pd.concat([C.season_rows(s) for s in sorted(set(C.st.season)) if s >= first_season], ignore_index=True), C.SC
