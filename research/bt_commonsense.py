"""BFF research: do the 'common sense' checks make buy-low and sell-high calls better?

Buy low (as on the site): a non-QB averaging at least 8 expected PPR points a game from his usage (targets and carries,
by where and how deep they come) and scoring at least 2.5 a game less. Sell high: scoring at least 10 a game and at least
3 above his usage. Judged on what happens next: his points per game over the rest of the season (weeks w-17) against
what he had averaged so far (the price in a trade). A good buy-low scores more from here; a good sell-high scores less.
The checks tested (2020-25 regular seasons, weeks 4-13, the trade window):
  fill-in    his usage came while a starter at his position was out (research/bt_fillin.py rule) and that starter is
             back this week or came back within the last two weeks
  two games  only two games played so far
  role down  his snap share over his last two games is under 75% of his season share
  starter    the returning starter's own line (often a buy low after injury-shortened games)
  stud       his usage already ranks in the top 6 at his position (a buy low then leans on usage that tends to fall back;
             a sell high gives up a player who stays elite)
python research/bt_commonsense.py   (writes research/results_commonsense.json)"""
import os, json, numpy as np, pandas as pd
BT = os.path.dirname(os.path.abspath(__file__)); RUN = os.path.dirname(BT); os.chdir(RUN)
ids = pd.read_csv('player_ids.csv', usecols=['pfr_id', 'gsis_id'], low_memory=False).dropna().drop_duplicates('pfr_id').set_index('pfr_id').gsis_id.to_dict()
SH = {'RB': .55, 'WR': .70, 'TE': .70}


def fill_pairs(S):
    """{(fill-in id, week): starter id} for the starter's return week and the two weeks after"""
    sn = pd.read_parquet(f'snap_counts_{S}.parquet', columns=['game_type', 'week', 'pfr_player_id', 'position', 'team', 'offense_snaps', 'offense_pct'])
    sn = sn[(sn.game_type == 'REG') & sn.position.isin(SH) & (sn.offense_snaps > 0)].copy()
    sn['pid'] = sn.pfr_player_id.map(ids); sn = sn.dropna(subset=['pid'])
    tw = sn.groupby('team').week.apply(lambda s: sorted(s.unique())).to_dict()
    U = {(r.pid, r.team, int(r.week)): float(r.offense_pct) for r in sn.itertuples()}
    out, back = {}, {}
    sw = pd.read_parquet(f'stats_player_week_{S}.parquet', columns=['player_id', 'week', 'season_type', 'targets', 'carries']); sw = sw[sw.season_type == 'REG']
    O = {(x.player_id, int(x.week)): float((x.targets or 0) + (x.carries or 0)) for x in sw.itertuples()}
    for (tm, pos), G in sn.groupby(['team', 'position']):
        W = tw[tm]; players = G.pid.unique()
        for L in players:
            for i, w in enumerate(W):
                if i == 0 or (L, tm, w) not in U or (L, tm, W[i - 1]) in U: continue
                j = i - 1
                while j >= 0 and (L, tm, W[j]) not in U: j -= 1
                miss = W[j + 1:i]
                if j < 0 or not (1 <= len(miss) <= 6): continue
                before = sorted([U[(L, tm, W[k])] for k in range(j, -1, -1) if (L, tm, W[k]) in U][:3], reverse=True)[:2]
                if len(before) < 2 or np.mean(before) < SH[pos]: continue
                for k in range(i, min(len(W), i + 3)): back[(L, W[k])] = 1
                for X in players:
                    if X == L: continue
                    sm = [U.get((X, tm, m), 0) for m in miss]
                    if np.mean(sm) < .40: continue
                    bw = [W[k] for k in range(j, -1, -1) if (L, tm, W[k]) in U][:3]
                    with_ = [U[(X, tm, b)] for b in bw if (X, tm, b) in U]
                    if with_ and np.mean(with_) > np.mean(sm) - .15: continue
                    bes = [b for b in bw if (X, tm, b) in U]                                # he ranks below the starter
                    if bes and np.mean([O.get((X, b), 0) for b in bes]) >= np.mean([O.get((L, b), 0) for b in bes]): continue
                    if not bes and np.mean([O.get((X, m), 0) for m in miss]) >= np.mean(sorted([O.get((L, b), 0) for b in bw], reverse=True)[:2]): continue
                    for k in range(i, min(len(W), i + 3)): out[(X, W[k])] = L
    return out, back


rows = []
for S in range(2020, 2026):
    F = pd.read_parquet(f'.cache/f5_2026_{S}.parquet', columns=['player_id', 'season', 'week', 'pos', 'team', 'g', 'y', 'm_fp', 'm_xfp', 'm_snap', 'l1_snap', 'l2_snap'])
    F = F[F.pos.isin(['RB', 'WR', 'TE'])]
    fp_, back = fill_pairs(S)
    tg = F.groupby('team').week.apply(lambda s: set(s.unique())).to_dict()
    Y = {k: g.set_index('week').y for k, g in F.groupby('player_id')}
    F['xrk'] = F[F.g >= 2].groupby(['week', 'pos']).m_xfp.rank(ascending=False, method='min')   # usage rank at his position
    for x in F[(F.week >= 4) & (F.week <= 13) & (F.g >= 2)].itertuples():
        if x.m_xfp != x.m_xfp or x.m_fp != x.m_fp: continue
        buy = x.m_xfp >= 8 and x.m_xfp - x.m_fp >= 2.5; sell = x.m_fp >= 10 and x.m_fp - x.m_xfp >= 3
        fa = (x.player_id, int(x.week)) in fp_ and x.m_fp >= 8      # any fill-in scoring 8+ a game when his starter is back
        if not (buy or sell or fa): continue
        y = Y[x.player_id]; fut = y[(y.index >= x.week) & (y.index <= 17)]
        tgames = len([w for w in tg.get(x.team, ()) if x.week <= w <= 17])
        rd = (x.l1_snap + x.l2_snap) / 2 < .75 * x.m_snap if x.l1_snap == x.l1_snap and x.l2_snap == x.l2_snap and x.m_snap == x.m_snap and x.m_snap > 0 else False
        rows.append({'season': S, 'week': int(x.week), 'pid': x.player_id, 'pos': x.pos, 'buy': buy, 'sell': sell, 'fpg': x.m_fp, 'xfpg': x.m_xfp, 'g': int(x.g),
                     'ros_pg': float(fut.mean()) if len(fut) else np.nan, 'ros_team_pg': float(fut.sum() / tgames) if tgames else np.nan,
                     'stud': bool(x.xrk == x.xrk and x.xrk <= 6), 'fill': (x.player_id, int(x.week)) in fp_, 'fill_any': bool(fa), 'two': int(x.g) == 2, 'role_down': bool(rd), 'starter_back': (x.player_id, int(x.week)) in back})
Z = pd.DataFrame(rows)
Z['bounce'] = Z.ros_pg - Z.fpg
def summ(d, side):
    d = d[d.ros_pg.notna()]
    if not len(d): return {'n': 0}
    good = (d.ros_pg > d.fpg) if side == 'buy' else (d.ros_pg < d.fpg)
    return {'n': len(d), 'players': int(d.pid.nunique()), 'avg_so_far': round(float(d.fpg.mean()), 2), 'avg_usage': round(float(d.xfpg.mean()), 2), 'avg_after': round(float(d.ros_pg.mean()), 2),
            'after_reached_usage_pct': round(float((d.ros_pg >= d.xfpg - 1).mean() * 100), 1),
            'change': round(float((d.ros_pg - d.fpg).mean()), 2), 'call_right_pct': round(float(good.mean() * 100), 1),
            'after_per_team_game': round(float(d.ros_team_pg.mean()), 2)}
R = {}
for side in ('buy', 'sell'):
    d = Z[Z[side]]
    R[side] = {'all': summ(d, side)}
    for f in ('fill', 'two', 'role_down', 'starter_back', 'stud'):
        R[side][f] = summ(d[d[f]], side); R[side]['not_' + f] = summ(d[~d[f]], side)
    keep = d[~d.fill & ~d.two & ~d.role_down & ~d.stud] if side == 'buy' else d[~d.stud]
    R[side]['after_checks'] = summ(keep, side); R[side]['dropped_by_checks'] = summ(d[~d.index.isin(keep.index)], side)
R['fill_in_scoring_8_plus'] = summ(Z[Z.fill_any], 'sell')   # 'right' = he scored less from then on (a sell)
print(json.dumps(R, indent=1))
json.dump(R, open(os.path.join(BT, 'results_commonsense.json'), 'w'), indent=1)
