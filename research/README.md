# BFF research: the accuracy tests

These scripts reproduce every accuracy number BFF publishes about itself. They are not part of the site and the
workflows never run them. Run them from the repository folder. The first run downloads what it needs: the nflverse
data files for 2012-2026 (about 350 MB) into this folder.

**Since November 2026 the site uses BFF's own numbers only.** Several tests below compare BFF with ESPN, Sleeper and the
FantasyPros expert consensus, or test the blends BFF used until then; those comparison sources (other sites' past
projections in `hist/`, the FantasyPros archive `db_fpecr.parquet`, and real posted prop lines in `props/`) are kept
out of the public repository, so those scripts reproduce only where you have them. The numbers they produced stay
below as the record (and on the site's Learn page as comparisons). The scripts that set what the site runs now are
`bt_weekly_v5.py` and `bt_value_v5.py` (BFF's model and value alone), `bt_lines_bff.py` and `bt_props_bff.py` (prop
lines from BFF's own numbers), `bt_fillin.py`, `bt_commonsense.py` and `bt_kdst.py`.

Every test is out of sample: each season is predicted by models trained only on earlier seasons, using only what was
known before each game. The version 5 scripts use the site's own code (`ff_feat.py` builds the inputs, `ff_model.py`
the model), so what is tested is what the site runs.

| Script | What it tests | Time |
| --- | --- | --- |
| `bt_weekly_v5.py` | Weekly projections (version 5) vs the FantasyPros weekly expert consensus, 2021-2026, on the same player-games (about 24,000); the expert weight; the must-start calls. With `BT_FROM=2020 BT_SAVE=1` it also saves `h_weekly_v5.parquet` for the next script | about 40 minutes |
| `bt_sites.py` | The weekly stack BFF publishes (its model + the experts + ESPN + Sleeper) head to head with ESPN, Sleeper and the experts on the same player-games, 2020-2026; the stack weights (chosen on 2020-22); by position; hindsight bounds on how much room any projection has (`--ceiling` adds the perfect-usage bound) | about 5 minutes (10 with `--ceiling`) |
| `bt_lines.py` | Predicted prop lines against real posted week-7 2026 lines (before and after setting them from ESPN's and Sleeper's stat projections), over rates in 2025, and the picks against lines built that way. Data in `props/` | seconds |
| `bt_props_more.py` | The newer props: pass attempts, completions, interceptions, rush attempts, targets, anytime and 1st-half TD. Rules fit to real week-7 lines, over rates in 2025 and 2026, and the interception and touchdown models fit on 2025 and checked on 2026. Data in `props/` | seconds |
| `bt_fillin.py` | Fill-ins (backups who took a hurt starter's snaps) and returning starters: BFF's model vs what happened once the starter was back, 2020-25; the scaling the site uses | seconds |
| `bt_commonsense.py` | Buy-low and sell-high calls with and without the common-sense checks (fill-ins, two games, falling snaps, top-6 usage), 2020-25 | seconds |
| `bt_lines_bff.py` | Since Nov 2026: BFF's own model lines against both samples of real week-7 lines; the passing- and receiving-yard steps the site uses (adopted only where they beat the model line on both samples, players left out). Writes `results_lines_bff.json`. Data in `props/` | seconds |
| `bt_props_bff.py` | Since Nov 2026: the newer props from BFF's own expected volume (count-line rules fit to real week-7 lines, over rates 2025-2026, interception and touchdown scales, outcome spreads). `BT_DATA=<folder>` points it at fresh nflverse files. Writes `results_props_bff.json` | about 2 minutes |
| `bt_value_build.py` then `bt_value_eval.py` | The rest-of-season value formula (spread, expert weight, waiver-wire share) at 15 checkpoints (weeks 4, 6, 8, 10, 12 of 2023-2025), scored against 10 simulated 12-team leagues per checkpoint | about 20 minutes |
| `bt_value_v5.py` | The same checkpoints and truth with the version 5 projections | about 40 minutes (`--reuse` re-scores in a few) |
| `bt_weekly.py` | The previous model (version 4), kept for comparison | about 10 minutes |
| `brain/` | How Ask BFF's own model (BFF Brain) is trained: `corpus.py` (training questions), `train.py` (the classifier, writes brain.json), `voice.py` (how it talks: Ben's voice, shipped inside brain.json), `kb.py` and `kb_export.py` (the football knowledge base, writes kb.json) | about 2 minutes |

```
python research/bt_weekly_v5.py       # writes research/results_weekly_v5.json
BT_FROM=2020 BT_SAVE=1 python research/bt_weekly_v5.py && python research/bt_sites.py --ceiling   # writes research/results_sites.json
python research/bt_value_build.py     # writes research/value_checkpoints.pkl
python research/bt_value_eval.py      # writes research/results_value.json and value_truth.pkl
python research/bt_value_v5.py        # writes research/results_value_v5.json
```

## Results (October 2026)

### Weekly projections

Rank accuracy = mean weekly Spearman correlation between the projection and the points scored, by position (1 =
perfect order). Pairs = among start/sit-relevant players (consensus top 24 QB, 40 RB, 50 WR, 20 TE), how often the
higher-ranked of two really scored more. Average miss = mean absolute error in PPR points.

**What BFF publishes now: a stack of four forecasts** (`bt_sites.py`, the same rule as `ff_produce.py`). Within each
position and week, every forecast becomes a z-score among the players the experts ranked: BFF's model 30%, the
FantasyPros weekly expert rank 10%, Sleeper 30%, ESPN 30%, re-weighted over the forecasts a player has. The k-th
strongest player gets the k-th highest of the players' average projected points (BFF, Sleeper, ESPN). The weights are
the best of every 10% split on 2020-22 (0.563; next best 0.563 and 0.563, so the choice is flat near the top); 2023
onward is a clean test.

Head to head, on the player-games every source projected (ESPN re-scored to full PPR from its projected stats):

| 2023-2025 (11,636 player-games) | Rank accuracy | Pairs | Average miss (PPR) |
| --- | --- | --- | --- |
| FantasyPros experts | 0.565 | 62.1% | 4.80 (on BFF's scale) |
| ESPN | 0.565 | 62.3% | 4.75 |
| Sleeper | 0.561 | 62.1% | 4.86 |
| BFF model alone | 0.556 | 61.6% | 4.82 |
| BFF previous mix (40% model, 60% experts) | 0.570 | 62.3% | 4.79 |
| **BFF stack** | **0.577** | **62.7%** | **4.71** |

2026 weeks 1-6 (1,631 player-games): experts 0.552 / 63.8%, ESPN 0.554 / 63.4% / 4.81, Sleeper 0.560 / 63.6% / 4.81,
BFF model 0.550 / 63.8% / 4.86, **BFF stack 0.574 / 64.1% / 4.76**. 2020-22 (where the weights were chosen): stack
0.563, best other (Sleeper) 0.551. By position, 2023-25, stack vs the best other source: QB 0.381 vs 0.369 (experts),
RB 0.684 vs 0.680 (Sleeper), WR 0.643 vs 0.638 (ESPN), TE 0.601 vs 0.594 (experts); 2026: QB 0.390 vs 0.366, RB 0.698
vs 0.691, WR 0.650 vs 0.644, TE 0.556 vs 0.554. With one site missing (2023-26, all ranked players) the stack still
beats the previous mix: without ESPN 0.638, without Sleeper 0.639, previous mix 0.635.

Every player the experts ranked who played (some lack an ESPN or Sleeper projection; the stack uses what he has):

| 2023-2025 (13,119 player-games) | Rank accuracy | Pairs | Average miss (PPR) |
| --- | --- | --- | --- |
| Season average, shrunk (baseline) | 0.569 | 59.8% | 4.79 |
| BFF model alone | 0.622 | 61.6% | 4.58 |
| FantasyPros experts alone | 0.631 | 62.1% | 4.55 (on BFF's scale) |
| BFF previous mix | 0.635 | 62.2% | 4.53 |
| **BFF stack** | **0.641** | **62.7%** | **4.46** |

| Season | Experts | BFF stack | BFF previous mix | BFF model alone |
| --- | --- | --- | --- | --- |
| 2021 (weights chosen on 2020-22) | 0.581 | 0.597 | 0.589 | 0.575 |
| 2022 (weights chosen on 2020-22) | 0.614 | 0.622 | 0.619 | 0.605 |
| 2023 | 0.629 | 0.634 | 0.630 | 0.614 |
| 2024 | 0.615 | 0.638 | 0.623 | 0.611 |
| 2025 | 0.647 | 0.651 | 0.651 | 0.638 |
| 2026 (weeks 1-6) | 0.631 | 0.648 | 0.636 | 0.631 |

Must-start calls, 2023-2025 (each week's top 10 at each position; a hit finishes as a starter: top 12 QB, 24 RB, 30
WR, 12 TE): BFF stack 66.2%, previous mix 66.5%, FantasyPros experts 66.4%, BFF model alone 64.8%, season average
63.6%. These differ by less than their noise (about 1,840 calls, so about 1.1 points either way).

**Can any projection be 10% more accurate than the best site? No, and here is the evidence** (2023-25, the same
player-games):

- Re-weighting is used up: weights picked on the 2023-25 answers themselves reach 0.578; the stack (weights from
  2020-22) has 0.577. Ridge regression, gradient-boosted trees (with expert disagreement, roster share, games played)
  and per-position weights as the stacker all did the same or worse (0.549-0.577).
- The sources agree with each other at 0.90-0.94 rank correlation (ESPN~Sleeper 0.921, model~ESPN 0.905, experts~model
  0.935), so most of their misses are the same misses.
- Hindsight: ranking each player by his real average in all his other games that season, future games included,
  scores 0.531 with a 4.92-point miss; ESPN's pre-game projection scores 0.561 and 4.75 on the same games. Knowing the
  future season average does not beat the sites.
- Only knowing each player's usage in that very game (expected points from his real targets and carries and where
  they came) reaches 0.718 (pairs 75.3%). A 10% lead over the best site (0.565) would need 0.622: more than a third of
  the way from today's best sites to that clairvoyant mark, with nothing more than pre-game information.

The version 5 model alone (`bt_weekly_v5.py`) has closed most of its gap to the experts (0.030 behind with version 4,
0.010 behind with version 5, level in 2026).

### Prop lines (`bt_lines.py`)

Two samples of real week-7 2026 lines: A, a public props page (Oct 21-23; passing, receiving, rushing yards; one number
per player) and B, scoresandodds.com on Sunday Oct 25 before kickoff (each player's lowest and highest line across books
for passing, receiving and rushing yards and receptions, and the main passing-TD line with its odds;
`props/real_lines_2026_w7_sun.json`, with the projections at that moment in `props/site_2026_w7_sun.json`). Each line
is the average of ESPN's and Sleeper's projection through a rule fit to both samples; average gap to the real line, every
rule scored on players it never saw (sample B; the old rule on the same players in brackets):

| Stat | Rule | Gap (B) | Books' own spread | Inside the books' range |
| --- | --- | --- | --- | --- |
| Passing yards | 0.404 x + 0.250 x season average + 0.218 x market x (Vegas total / 22 - 1) + 75.5 | 7.8 (11.1) | 7.2 | 12 of 28 (9) |
| Receiving yards | 0.916 x | 3.3 (3.3) | 3.3 | 32 of 81 |
| Rushing yards | 0.843 x + 0.112 x season average - 3.5 | 3.8 (4.6) | 2.8 | 28 of 84 (21) |
| Receptions | 0.975 x + 0.15 | 0.25 (0.29) | 0.38 | 76 of 81 (73) |
| Passing TDs | 0.5 below 0.95, 2.5 from 2.3 | 26 of 28 match (24 left out one at a time) | | was 21 of 25 |

The second refit (Oct 25 evening): the player's season average (his mean for the stat in his games before the line's
week) brings rushing and passing lines closer, and the Vegas implied team total helps passing lines; on the earlier
sample (Oct 21-23 lines), each player scored by a fit that left him out, passing yards sit 5.6 from the real lines
(was 8.6) and rushing 4.3 (was 4.9). For receiving yards and receptions nothing tried closed the gap on players left
out (season or last-3 averages, BFF's own stat model, the defense, the Vegas total): what is left is the books' own
information. The books' expected passing TDs, read from the odds, are 0.578 + 0.676 x the projection (they lift low
projections: every 0.5 line came with about one expected TD). In 2025, at lines built this way, overs hit 48.6%
(passing), 43.5% (receiving), 48.5% (rushing), 41.4% (receptions), 46.3% (passing TDs). Picks, unders when BFF's own
model is at least 10% below ESPN and Sleeper: receiving 57.2% of 719 (the only pick); passing 52.6% of 249 (a pick at
the first refit's lines, 58.0%, but not at these lines, which sit closer to the books'), rushing 52.8%, receptions 60.8%
and passing TDs 59.6% (not picks: real books price those unders at -150 to -200); every yardage under 54.2%; overs
where BFF was higher 46.1%. A receiving-yard under pick still hits 55% down to 4.5% below our line. These used lines
built from ESPN and Sleeper, not real book lines.

### More props (`bt_props_more.py`)

`python research/bt_props_more.py` (writes `results_props_more.json`). Real lines: scoresandodds.com's week-7 prop pages
read by hand Sunday Oct 25 (each player's lowest and highest line across books: 25 pass-attempt, 29 completion, 86
rush-attempt and 27 interception lines with odds; `props/real_lines_2026_w7_more.json`). The touchdown page showed one
price per player and no under, some apparently taken during or after the games, so it was not used; the pass+rush and
rush+rec pages had no week-7 rows, so those combos wait. Every rule scored on players it never saw (a fitted rule had to
beat the simpler one by more than 0.02):

| Prop | Rule (x = ESPN and Sleeper's average) | Gap to the books' middle | Books' own spread | Overs 2025 / 2026 |
| --- | --- | --- | --- | --- |
| Pass attempts | x, whole number + .5 | 1.08 (24 passers) | 1.25 | 41.6% / 47.4% |
| Completions | projected attempts x completion rate (this season + half of last, shrunk 100 attempts to 64.5%) | 0.84 (28) | 0.61 | 42.8% / 53.2% |
| Rush attempts | 1.003 x - 0.259 | 0.95 (82) | 0.48 | 45.6% / 41.1% |
| Targets | 1.025 x (no real lines; set so 2025's overs hit like receptions', 41.4%) | | | 41.3% / 45.7% |

Picks would need one side to hit 55% in both seasons for a gap bin (BFF's model 10%+ below, level, 10%+ above the sites);
none does at the real-line rules (target unders below the sites did, 61.5% and 58.8%, but no books post targets to test
against), so these props get no picks. Interceptions: projected attempts x the passer's rate (this season, last season
at 0.66, shrunk 2,489 attempts toward the league's 2.17%) x 0.963, Poisson; fit on 2025 (expected 48.7% to throw
one, 49.1% did; Brier 0.2463 vs 0.2499 for a flat rate) and checked on 2026 (48.5% vs 49.4%; 0.2494 vs 0.2500):
barely better than the league rate, and against the books' week-7 prices with the fee removed, 3 points apart on average
(26 passers; BFF 49.1%, books 49.7%). Anytime touchdowns: projected carries and targets at each position's rate (carry:
QB 4.5%, RB 3.4%; target: RB 2.1%, WR 4.9%, TE 6.1%; WR and TE carries fit to zero) x (implied team total / 22)^1.11 x his
own touchdowns per opportunity (this season and last, shrunk by 52 expected touchdowns' worth), Poisson, fit on 2025:
2025 predicted 23.4% score, 23.4% did (Brier 0.1623 vs 0.1774 for a rate by position); 2026, never seen, 23.9% vs 22.4%
(0.1571 vs 0.1719), and each fifth of the chances lands within 4 points of what happened. First-half touchdowns: that
rate x the share of the position's touchdowns scored in the first half (2024-2025 play-by-play: QB 48.4%, RB 47.2%, WR
50.5%, TE 45.5%): 2025 12.5% vs 12.8%, 2026 12.7% vs 11.9%. Quarterbacks' projected targets are left out (both sites
projected none in all 651 tested games). `spread` holds actual / projection at 5% to 95% for each count prop, which the
page uses for the chance at a line other than BFF's.

### Kickers and team defenses (`bt_kdst.py`)

`python research/bt_kdst.py` (writes `results_kdst.json`, about a minute). Points with Yahoo's default scoring from
nflverse play-by-play (D/ST) and weekly stats (kickers). The D/ST counts against nflverse's own team stats, 2023-25: interceptions,
safeties and blocked kicks match exactly; sacks run about 0.7% higher (play-by-play counts team sacks no player gets);
return and fumble touchdowns within one or two a season. Projections fit on 2015-22, scored on 2023-25:

| | Rule | Average miss | Correlation | Week-by-week rank correlation |
| --- | --- | --- | --- | --- |
| D/ST | opponent's Vegas implied points, sacks and takeaways so far (both sides), home | 4.40 | 0.33 | 0.33 |
| D/ST | Vegas alone | 4.42 | 0.32 | 0.32 |
| D/ST | season so far | 4.57 | 0.10 | 0.10 |
| D/ST | league average | 4.53 | 0.08 | |
| Kicker | team's Vegas implied points, his points so far, indoors | 3.60 | 0.16 | 0.16 |
| Kicker | league average | 3.67 | 0.04 | |

Kickers are mostly luck week to week (no rule tried does much better), and a defense's week is mostly its opponent.

### Common sense: fill-ins, buy low and sell high (`bt_fillin.py`, `bt_commonsense.py`)

`python research/bt_fillin.py` (writes `results_fillin.json`, a few seconds). A **fill-in** took a starter's snaps (40%+,
and 15+ points more than beside the starter) while the starter (.55+ snap share for RBs, .70+ for WRs/TEs in his best 2 of his last 3
games) missed 1-6 games, and ranks below him (fewer targets + carries together, or, never together, fewer in the games he
filled than the starter's best 2). For the starter's return week and the 3 after (2020-25 regular seasons), BFF's weekly
model against what happened:

| | Fit 2020-22 | Check 2023-25 |
|---|---|---|
| Fill-ins: actual / projected (RB, WR, TE) | 0.74, 0.83, 0.84 | 0.85, 0.76, 0.58 |
| Fill-ins over-projected | 72% (521 games) | 74% (379 games) |
| Returning starters: actual / projected | 1.00 (558) | 1.04 (386) |

Scaling fill-ins by the 2020-22 ratios on 2023-25: average miss 3.82 -> 3.44 points, bias +1.37 -> +0.13. The site uses
the ratios pooled over all six seasons (RB 0.786, WR 0.803, TE 0.754), weighted by the chance the starter plays each week.

`python research/bt_commonsense.py` (writes `results_commonsense.json`). Buy-low calls (usage 8+ a game, scoring 2.5+
below it) and sell-high calls (10+ a game, 3+ above usage) in weeks 4-13, judged on the rest of the season against the
player's average so far:

| | Calls | Right | Points a game after vs before |
|---|---|---|---|
| Buy low, every call | 496 | 60% | +1.12 |
| Buy low, fill-in whose starter is back | 11 | 27% | -1.49 |
| Buy low, two games played | 34 | 56% | +0.98 |
| Buy low, snaps falling (last 2 under 75% of season) | 19 | 37% | -0.59 |
| Buy low, usage already top 6 at his position | 114 | 40% | -1.11 |
| Buy low, after all four checks | 327 | 69% | +1.96 |
| Buy low, returning starter | 50 | 72% | +2.73 |
| Fill-in scoring 8+ once his starter is back (a sell) | 148 | 68% | -1.67 |
| Sell high, every call | 1,240 | 75% | -3.08 |
| Sell high, top-6 usage (stud) | 312 | 80% | -4.17 (still 17.9 a game after) |

### Rest-of-season value (BFF value)

15 checkpoints; every source is put on the same value curve so only the order of players differs. Truth = what each
player added to his team over the rest of the season in simulated leagues, with lineups set by the previous
projections (so the test does not favor the new model).

| | Rank accuracy | Lopsided trades called right | R² |
| --- | --- | --- | --- |
| BFF model alone (no experts) | 0.432 | 72.0% | 0.225 |
| BFF value with the previous projections | 0.446 | 73.2% | 0.241 |
| FantasyPros experts alone (same value curve) | 0.448 | 73.4% | 0.257 |
| **BFF value** | **0.454** | **73.5%** | **0.259** |

By season, BFF value vs the experts (rank accuracy): 2023 0.468 vs 0.460, 2024 0.518 vs 0.504, 2025 0.376 vs 0.380.
Lopsided trades are random pairs of players (4,000 draws per checkpoint) whose values are at least 2x apart. With
lineups set by the new projections instead: BFF value 0.448 / 72.5% / 0.293, experts 0.440 / 72.5% / 0.290. In short,
BFF value orders players a little better than the experts in two of three seasons and overall, and calls lopsided
trades as well as they do.

**Correction (October 2026).** An earlier version of this page compared BFF value (0.446, 73.2%) with the experts
mapped onto the old value curve (0.429, 69.8%). On the same curve the experts score 0.448 and 73.4%, so the old formula
was level with the experts, not ahead. The numbers above are the fair comparison.

Small differences in the last digit are expected if the data files have been updated since (nflverse corrects stats
now and then).
