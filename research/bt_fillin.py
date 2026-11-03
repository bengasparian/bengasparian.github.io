"""BFF research: fill-ins and returning starters (the 'common sense' check behind buy-low, sell-high and rest-of-season).

Question: when a starter comes back from missing games, how does BFF's weekly model do on (a) the player who filled in for
him and (b) the starter himself? The model reads each player's recent usage, so a fill-in carries his starter-sized role
into the week the starter returns.
Definitions (regular season 2020-25, snap counts from Pro Football Reference via nflverse):
  starter  L: same team and position as X; in his best 2 of his last 3 games before the absence he averaged a snap share
              of at least .55 (RB) / .70 (WR, TE); he missed 1-6 straight team games and plays again in week w.
  fill-in  X: played the games L missed with at least .40 snap share and more snaps than in his games beside L (if any),
              and ranks below L: fewer targets + carries than L in their games together (never together: fewer in the
              games he filled than L's best 2 of his last 3).
For X and L in week w (and the 3 weeks after, while L keeps playing): actual PPR points vs the model's out-of-sample
prediction (research/h_weekly_v5.parquet). Fit on 2020-22, checked on 2023-25.
python research/bt_fillin.py   (writes research/results_fillin.json)"""
import os, json, numpy as np, pandas as pd
BT = os.path.dirname(os.path.abspath(__file__)); RUN = os.path.dirname(BT); os.chdir(RUN)
ids = pd.read_csv('player_ids.csv', usecols=['pfr_id', 'gsis_id'], low_memory=False).dropna().drop_duplicates('pfr_id').set_index('pfr_id').gsis_id.to_dict()
H = pd.read_parquet(os.path.join(BT, 'h_weekly_v5.parquet'))
H = H[H.season.between(2020, 2025)].set_index(['player_id', 'season', 'week'])
SH = {'RB': .55, 'WR': .70, 'TE': .70}
rows = []
for S in range(2020, 2026):
    sn = pd.read_parquet(f'snap_counts_{S}.parquet', columns=['season', 'game_type', 'week', 'pfr_player_id', 'position', 'team', 'offense_snaps', 'offense_pct'])
    sn = sn[(sn.game_type == 'REG') & sn.position.isin(SH) & (sn.offense_snaps > 0)].copy()
    sn['pid'] = sn.pfr_player_id.map(ids); sn = sn.dropna(subset=['pid'])
    tw = sn.groupby('team').week.apply(lambda s: sorted(s.unique())).to_dict()      # weeks each team played
    U = {(r.pid, r.team, int(r.week)): float(r.offense_pct) for r in sn.itertuples()}
    POS = sn.groupby('pid').position.agg(lambda s: s.mode().iloc[0]).to_dict()
    sw = pd.read_parquet(f'stats_player_week_{S}.parquet', columns=['player_id', 'week', 'season_type', 'targets', 'carries']); sw = sw[sw.season_type == 'REG']
    O = {(x.player_id, int(x.week)): float((x.targets or 0) + (x.carries or 0)) for x in sw.itertuples()}   # targets + carries
    for (tm, pos), G in sn.groupby(['team', 'position']):
        W = tw[tm]; players = G.pid.unique()
        for L in players:
            if POS.get(L) != pos: continue
            pw = [w for w in W if (L, tm, w) in U]
            for i, w in enumerate(W):
                if i == 0 or (L, tm, w) not in U or (L, tm, W[i - 1]) in U: continue   # L returns in week w after missing the week before
                j = i - 1
                while j >= 0 and (L, tm, W[j]) not in U: j -= 1
                miss = W[j + 1:i]
                if j < 0 or not (1 <= len(miss) <= 6): continue
                before = [W[k] for k in range(j, -1, -1) if (L, tm, W[k]) in U][:3]
                if len(before) < 2 or np.mean(sorted([U[(L, tm, b)] for b in before], reverse=True)[:2]) < SH[pos]: continue   # his best 2 of those 3 (one injury-shortened game does not hide a starter)
                for X in players:
                    if X == L or POS.get(X) != pos: continue
                    sm = [U.get((X, tm, m), 0) for m in miss]
                    if np.mean(sm) < .40: continue
                    with_ = [U[(X, tm, b)] for b in before if (X, tm, b) in U]
                    if with_ and np.mean(with_) > np.mean(sm) - .15: continue          # he had this role already (his snaps must have risen by 15+ points)
                    # he ranks below the starter: fewer targets + carries beside him (or, never beside him, fewer in the
                    # games he filled than the starter's best 2 of his last 3)
                    bes = [b for b in before if (X, tm, b) in U]
                    if bes and np.mean([O.get((X, b), 0) for b in bes]) >= np.mean([O.get((L, b), 0) for b in bes]): continue
                    if not bes and np.mean([O.get((X, m), 0) for m in miss]) >= np.mean(sorted([O.get((L, b), 0) for b in before], reverse=True)[:2]): continue
                    after = [W[k] for k in range(i, min(len(W), i + 4)) if (L, tm, W[k]) in U]
                    for k, wa in enumerate(after):
                        if (L, tm, wa) not in U: break
                        for who, pid in (('fill', X), ('starter', L)):
                            if (pid, S, wa) in H.index:
                                h = H.loc[(pid, S, wa)]
                                if isinstance(h, pd.DataFrame): h = h.iloc[0]
                                rows.append({'season': S, 'week': wa, 'k': k, 'who': who, 'pos': pos, 'pid': pid, 'model': float(h.model), 'y': float(h.y),
                                             'with': float(np.mean(with_)) if with_ else None, 'miss': float(np.mean(sm)), 'nmiss': len(miss), 'pair': (L, X, S, w)})
Z = pd.DataFrame(rows).drop_duplicates(['who', 'pid', 'season', 'week'])
print('cases', Z.groupby(['who', 'pos']).size().to_dict())
R = {'cases': {f'{a}_{b}': int(n) for (a, b), n in Z.groupby(['who', 'pos']).size().items()}}
def summ(d):
    return {'n': len(d), 'model': round(float(d.model.mean()), 2), 'actual': round(float(d.y.mean()), 2), 'ratio': round(float(d.y.sum() / d.model.sum()), 3),
            'over_projected_pct': round(float((d.model > d.y).mean() * 100), 1)}
for part, d in (('fit_2020_22', Z[Z.season <= 2022]), ('check_2023_25', Z[Z.season >= 2023])):
    R[part] = {}
    for who in ('fill', 'starter'):
        for pos in ('RB', 'WR', 'TE'):
            x = d[(d.who == who) & (d.pos == pos)]
            if len(x) >= 15: R[part][f'{who}_{pos}'] = summ(x)
        x = d[d.who == who]; R[part][f'{who}_all'] = summ(x)
        R[part][f'{who}_first_week'] = summ(x[x.k == 0]); R[part][f'{who}_later_weeks'] = summ(x[x.k > 0])
        # fill-ins who never played beside the starter vs those who did
        if who == 'fill':
            R[part]['fill_never_beside'] = summ(x[x['with'].isna()]); R[part]['fill_had_games_beside'] = summ(x[x['with'].notna()])
print(json.dumps(R, indent=1))
# the correction a projection would use: ratio fit on 2020-22, then the 2023-25 error with and without it
F = {who: {pos: R['fit_2020_22'].get(f'{who}_{pos}', R['fit_2020_22'][f'{who}_all'])['ratio'] for pos in ('RB', 'WR', 'TE')} for who in ('fill', 'starter')}
c = Z[Z.season >= 2023].copy(); c['adj'] = c.model * [F[w][p] for w, p in zip(c.who, c.pos)]
R['factor'] = F
R['check_2023_25_error'] = {who: {'mae_model': round(float((c[c.who == who].model - c[c.who == who].y).abs().mean()), 2),
                                  'mae_adjusted': round(float((c[c.who == who].adj - c[c.who == who].y).abs().mean()), 2),
                                  'bias_model': round(float((c[c.who == who].model - c[c.who == who].y).mean()), 2),
                                  'bias_adjusted': round(float((c[c.who == who].adj - c[c.who == who].y).mean()), 2)} for who in ('fill', 'starter')}
# the site uses the ratio pooled over all six seasons (more cases; the 2023-25 check above used only 2020-22)
R['factor_all'] = {pos: round(float(Z[(Z.who == 'fill') & (Z.pos == pos)].y.sum() / Z[(Z.who == 'fill') & (Z.pos == pos)].model.sum()), 3) for pos in ('RB', 'WR', 'TE')}
print('factor', F, 'pooled', R['factor_all']); print('2023-25', R['check_2023_25_error'])
json.dump(R, open(os.path.join(BT, 'results_fillin.json'), 'w'), indent=1)
