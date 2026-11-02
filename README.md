# BFF · Ben's Fantasy Football: auto-updating version

This folder turns BFF (Ben's Fantasy Football) into a free website that keeps itself up to date all year, with nothing
to edit from one season to the next. Two GitHub workflows do the work, no API keys needed:

| Workflow | File | When | What it does |
|---|---|---|---|
| **Update Gridiron Fantasy** | `update.yml` | every 3 hours (23 minutes past) | downloads the latest NFL data, rebuilds every projection, ranking, trend and prop line, saves and grades the weekly calls, collects news, writes and updates BFF Originals, optionally syncs your Sleeper league, checks the page, saves it |
| **Live scores, news and lines** | `scores.yml` | every 10 minutes | live scores and box scores, news from every source, prop lines moved by ESPN's and Sleeper's latest projections, the odds and news, parlay picks, BFF Originals (breaking news, previews, recaps); only saves when something changed |

Both share one queue, so they never save at the same moment, and each run starts from the newest saved data (not the version that was current when it was queued). Before anything is saved, `check_page.py` checks the
page (data readable, enough players, no script errors) and the live files; anything broken is put back to the
last good version, so the published site never breaks.

## What's on the site
- **Home:** the player rankings screen, with the week built in: the week header (dates, live games), the week's games
  strip, and **Quick hits** (your team or a link-your-league card, the latest BFF Originals, what changed since your last
  visit, this week's calls, injury watch, trending adds, buy and sell, best picks). Its sections: **This week**
  (rankings), **Trade values** (the rest-of-season BFF value chart, tiered, for your league settings), **Start/sit**
  (cheat sheet) and **Favorites**. Every player has a card with projections, usage, game logs, schedule, VORP, news
  and this week's prop lines. Old links to the Week and Players tabs open Home.
- **New on BFF:** on wide screens the home page's left side spotlights what the site does that others don't (Spin
  Draft, kickers and defenses, prop lines that track the books, Ask BFF, linking any league, the graded weekly calls),
  one card at a time in the spotlight; on narrower screens and phones it is a strip under the top story. The numbers on
  the cards come from the data (the prop-line accuracy, this week's top defense), so they stay true as things change.
- **Kickers and team defenses (`ff_kdst.py`):** Players has **K** and **D/ST** buttons with this week's ranks, the season's
  points, the last three games and the rest-of-season projection; each has its own card (game log, road ahead, how it
  is scored and projected). Leagues keep them: ESPN (kicker ids, D/ST ids), Sleeper (DEF team codes, kicker ids),
  typed or copied rosters ("Bills D/ST", a kicker's name) and screenshots. Your lineup fills the league's K and D/ST
  spots, and power rankings count them when the league starts them. Live points come from ESPN's box score (field
  goals by distance from the scoring plays; sacks, takeaways, return touchdowns, safeties and points allowed), with the
  official numbers once the data job posts them. Ask BFF answers "best kickers this week", "should I start the
  Texans defense" or a kicker by name. They stay out of BFF's trade values, buy/sell calls, waiver targets and prop
  lines, so nothing in the skill-player rankings changes. **Scoring** (Yahoo's default settings, which Sleeper's
  follow): field goals 0-39 yards 3, 40-49 yards 4, 50+ yards 5, extra points 1; D/ST sack 1, interception 2, fumble
  recovery 2, touchdown 6, safety 2, blocked kick 2, points allowed 0: 10, 1-6: 7, 7-13: 4, 14-20: 1, 21-27: 0,
  28-34: -1, 35+: -4, where points allowed leave out touchdowns the other defense scores off this team's offense
  (interception and fumble returns, blocked field goals), safeties and defensive two-point returns, as Yahoo counts
  them. **Projections** (research/bt_kdst.py, fit on 2015-22 and tested on 2023-25 games they never saw): D/ST from the
  opponent's Vegas implied points, the defense's sacks and takeaways so far, the opponent offense's sacks and giveaways
  so far and home field (average miss 4.4 points, correlation 0.33 with what happened; the league average missed by 4.5
  with 0.08); kickers from the team's implied points, his points per game so far and indoor games (3.6 and 0.16 against
  3.7 and 0.04: a kicker's week is mostly luck, and the page says so). The D/ST counts match nflverse's own team stats
  for 2023-25 (interceptions, safeties and blocked kicks exactly; sacks within 1%, since play-by-play also counts the
  team sacks no player is credited with).
- **Spin Draft (`game_build.py`, Draft > Spin Draft game):** spin a slot machine for a random NFL team and season since
  1999, draft one of that team's real fantasy scorers into an open spot (QB, RB, RB, WR, WR, TE, FLEX), and build the
  highest-scoring lineup in seven spins, with two re-spins. The end screen shows your total, how close you came to the
  best lineup your spins allowed (every order tried), your best score, and a result to copy and share. **Daily
  challenge** gives everyone the same spins that day; PPR, half PPR or standard. Points are each player's
  regular-season total for that team that season from nflverse's weekly stats (a player traded midseason counts for
  each team with the points he scored there), with the franchise named as it was then (St. Louis Rams to 2015, San
  Diego Chargers to 2016, Oakland Raiders to 2019). Checked: every weekly row of every season re-adds to its points with
  the stated rules, and famous seasons match their published totals (Cooper Kupp 2021: 439.5 PPR; Christian McCaffrey
  2023: 391.3). `game.json` is built once and rebuilt only when a season finishes.
- **Live:** the games and scores in the middle (each with its photo: the featured game on top, then every game of the
  week, with your lineup live above them), the week's **top performers** on the left and **leaders by position** on the
  right (under the games on phones and narrower screens). Before kickoff both lists show projections. Tap a game
  for its full-screen game center (outlook, win chances, injuries with the injury and its source, the expected starting
  quarterbacks, top performers, box score). Past and future weeks too. Scores, injuries and projections update on
  their own (see **Injuries** under Projections).
- **Live game tracker:** while a game is on, its card shows the down and distance, where the ball is on a mini field,
  ESPN's win probability and the last play; a pop-up names any new touchdown or field goal. Its game center opens on
  **Live**: score by quarter, each team's timeouts and who has the ball, the field with the current drive shaded from
  where it started, the current drive play by play (the drive's plays, yards and time), the previous drives with how
  each ended, every scoring play, ESPN's win-probability chart for the whole game, and fantasy points for everyone in
  the game. Then the box score, top performers, overview and matchups. A finished game keeps all of this under **Game
  flow**. Everything comes straight from ESPN's own game feed (the same one ESPN's GameCast uses), read every 30
  seconds in the browser and every 10 minutes by `live_update.py` into `live.json` (key `pbp`), so the page shows it
  even where ESPN can't be reached directly. A part ESPN hasn't sent yet is left out rather than guessed.
- **News:** a sports-site layout with a top story, lead stories with pictures, a trending list (players covered by
  the most outlets in the last day), most-added players on Sleeper and the official injury report. Stories come from
  ESPN, CBS Sports, Yahoo Sports, Pro Football Talk, RotoWire, RotoBaller, PFF and Sharp Football Analysis. Headlines
  stay exactly as each publisher wrote them and link to the original; the labels (Breaking, Injury alert, Waiver
  wire...), outlet counts and "fantasy impact" notes are BFF's. Pictures load from each publisher's own feed image.
  **BFF Originals** (below) are mixed into the feed with a gold "BFF Original" label, lead it while fresh, and have
  their own panel.
- **My League:** link your league for your best lineup, waiver targets, trade ideas and a matchup simulator.
  **ESPN:** paste the league's link (or ID) and the page reads every team, roster, record, lineup spot and the scoring
  straight from ESPN's league service, then refreshes the rosters on its own (at most every 3 hours, paused after you
  edit rosters by hand; "Update now" any time). A My Team link (it has `teamId=`) also picks your team. ESPN's service
  answers this site for public leagues. A private league needs your ESPN sign-in, which browsers keep to ESPN's own
  pages, so ESPN answers other sites as if you were signed out (a reader's private league failed this way in October
  2026, although he was signed in). For those, **Private league?** under ESPN has three steps: open your league's data
  on ESPN (BFF builds the link from your league ID), copy everything, paste it and Import. On a computer there is also a
  one-click bookmark: drag "BFF: import from ESPN" to the bookmarks bar, open your league on ESPN and click it; it reads
  the league on ESPN's page and opens BFF with it after the `#` in the address (that part never leaves the browser), and
  finds your team from your ESPN sign-in. BFF asks before a bookmark replaces a different saved league. A private league
  doesn't refresh on its own: bring it in again after trades (the power rankings say so and link to the steps).
  **Sleeper:** type your username (pick a league if you have several; your team is found for you) or the league ID.
  **Yahoo, NFL.com, CBS and the rest:** Yahoo's data needs an approved app login and does not answer websites (checked),
  so these are read from what you copy: select all on a team's roster page (or a page with every roster), copy, paste,
  "Read page", repeat per team, Import. The page finds every player (also "J. Allen" style names with a team or
  position nearby, and names glued to team codes), splits a page with every roster into teams, and guesses each team's
  name (the line above its record); every name can be fixed and missing players added before the import. **Screenshots**
  work on phones: each one is cleaned up (enlarged, turned into black text on white) and read in the browser with the
  open-source Tesseract.js (version 6.0.1, loaded from jsDelivr only when used, about 6 MB the first time); a test with
  14-player rosters (light and dark mode, full and "J. Allen" names) found every player and the team name. The typed
  format still works: one line per team, "Team name: Player, Player, ..."
- **Draft:** everything for draft day: **Mock draft** against AI teams with different strategies (graded at the end),
  the pick-by-pick **Draft guide** for your league settings, and draft tips.
- **Fantasy Help:** the in-season toolkit: **Weekly calls** (below), Trends (best bets, buy & sell, usage, proof),
  Matchups (this week, defenses, schedules), waivers & trades, the trade analyzer with **Find trades**, betting, and tips.
- **Weekly calls:** every week's must starts, must sits, buy lows and sell highs, saved by `calls_update.py`. Start and
  sit calls keep updating until that player's game kicks off, then lock; buy and sell calls lock at the week's first
  kickoff. After the games each call is graded with official stats: a must start hits when he finishes as a starter
  (top 12 QB, 24 RB, 30 WR, 12 TE in PPR), a must sit hits when he finishes outside those spots, and buy lows and sell
  highs are graded on the player's next 3 games. Buy and sell calls get the same **common-sense checks** as the
  Trends page (see **Common sense** below). A season scorecard shows the hit rates next to honest yardsticks
  (starting the best season averages; all usual starters). Weeks 2-5 of 2026 were rebuilt
  (one time) from the model of the day using only pre-game information and are labeled "rebuilt"; everything from week 6
  on is saved live.
- **Favorites:** star any player to track him in Home → Favorites (this week's outlook, live points, status, props,
  news). Saved in each visitor's own browser (and in their account, if they have one).
- **Scoring:** PPR, half PPR, standard, or **Custom** (the Scoring menu): TE premium (extra points per tight-end
  catch), 6-point passing touchdowns, points per carry or first down, interception and fumble penalties, and the
  rest. Every projection, ranking, BFF value, trade value, draft pick and waiver target re-scores for it. A linked
  Sleeper league's scoring is read automatically.
- **Live points by every name:** during games, the home page's This week list and the start/sit cheat sheet show each
  player's fantasy points so far in a bright badge by his name, with the quarter and clock (and the row gets a green
  edge), then "Final" with his points; scored with your scoring, updated on every live poll (every 30 seconds on your
  own site during games) without redrawing the list.
- **BFF's AI (Ask BFF):** Ask BFF talks like a person: any wording, follow-ups ("what about him next week?"),
  comparisons, "why", small talk, all from BFF's numbers. The AI runs **entirely on the visitor's device**: an open
  model (Qwen3.5, Apache 2.0) that the browser downloads once and runs with WebGPU through WebLLM, sized to the device
  (Standard 4B, 2.4 GB, on computers; Lite 2B, 1.1 GB, on phones; Max 9B, 5.1 GB, for strong computers; Mini 0.8B as a
  fallback). Nothing typed into Ask BFF leaves the device, and there is nothing for the site owner to set up or pay.
  The page hands the model the facts for the question (the players and teams asked about, with this week's projection
  and range, matchup, injuries, stats, rest of season, trade value, prop lines, news and where they sit in your league;
  teams' schedules, results and injuries; rankings, waiver targets, scores, your roster and best lineup; BFF's own call
  on the question; and the closest entries of BFF's knowledge base, which now includes an analyst's playbook for
  start/sit, trades, waivers, injuries, Vegas, weather, usage, streaming, byes, playoffs, aging, DFS, odds and keepers),
  and **every number in a reply is checked against those facts** before it shows (a made-up number gets one retry, then
  the quick answer); on start/sit questions the verdict must also match BFF's call. On fast devices the model thinks
  hard questions through first (trades, close start/sit calls). Until a visitor downloads it, on devices that can't run
  it (no WebGPU, the claude.ai copy), or with "Quick answers only" in AI settings, the classic Ask BFF answers.
- **Classic Ask BFF, powered by BFF Brain, in Ben's voice:** BFF Brain is BFF's own question model, trained here and
  running inside the page (no outside AI and no key): a logistic-regression intent model over words, word pairs and letter groups (so typos still work),
  trained on about 16,200 football questions (`research/brain/`), that sorts a question into 28 kinds (start/sit,
  outlook, trade, trade value, keep or drop, waivers, rankings, league leaders, stats, injury status, news, team,
  defense matchups, game predictions, props, parlays, touchdown scorers, lineup, roster help, weekly calls, how BFF
  works, football rules and terms, greetings, thanks, small talk, venting, complaints, off-topic). On 94 hand-written
  questions it never trained on it picked the right kind 96% of the time. **The voice** (`research/brain/voice.py`,
  shipped inside `brain.json`) makes it talk like Ben: a short human opener that fits the answer (an easy start/sit
  call, a coin flip, a trade that tilts your way or one to avoid, bad injury news), a follow-up on about half the
  answers, never the same opener twice in a row, small talk ("how's it going?", a football joke), sympathy plus real
  help when someone vents about their team, and owning a miss when someone says a projection was wrong (with the
  accuracy record). The numbers, verdicts and reasons always come from BFF's own functions. Asked whether it is a
  person, it says plainly that it is a bot Ben built. Names, teams, positions and numbers are recognized before it reads the question, so it learns how
  people ask, not who. A **football knowledge base** (61 topics: scoring, overtime, the dynamic kickoff, penalties,
  positions and coverages, the playoff format, the draft, rosters, injured reserve, the injury report, fantasy terms,
  analytics terms like EPA and CPOE, betting terms, special teams, eligible receivers, fantasy scoring, records and 2026 dates) is searched by meaning. It **remembers the
  conversation** ("what about Gibbs?", "is he playing?", "why?", "rest of season?"), and **asks instead of guessing**:
  "Allen" gets "Which Allen do you mean?" with buttons, and an unclear question about one player gets the two most
  likely readings as buttons. Answers use the site's own numbers: start/sit, trades, trade ideas for a team you type
  in, lineup and waivers, stats and game logs, injury status, news and BFF Originals, rankings, league leaders, team
  info and depth charts (team nicknames or cities: "the backup running back in Detroit"), standings and division races,
  schedules and strength of schedule (next 4 weeks, rest of season, fantasy playoffs), defenses ranked against each position,
  defenses to stream, handcuffs, trade targets by position, game predictions, parlays and props (21+), bios (height,
  weight, college, draft), every Super Bowl back to Super Bowl I (by number, Roman numeral, year or team), and how BFF
  works. It says plainly what it does not track (weather forecasts, award odds, coaching staffs) and recognizes when a
  name is not a current player ("Jerry Rice" is not Jerry Jeudy).
- **Player cards** show height, weight, birthday, college, draft slot and NFL season (nflverse rosters) next to the
  number, depth chart role, age and bye.
- **Learn:** how everything works, accuracy, and **Sources & citations** for every number and story.
- **Updates bar:** on wider screens, a broadcast-style bar at the bottom of every page cycles through updates that fit the page
  (Home: everything; Live: scores and top performers; News: news; Fantasy Help: fantasy and betting updates;
  My League: your players). Pause, step through, or hide it.
- **Accounts:** visitors can create an account (they must agree to the Terms of Use and Privacy Policy) to save their
  linked leagues, team, favorite players and settings and get them back on any device. See **Accounts** below.
- **Phones:** an app-style layout: a compact header (search, Ask BFF, account), each tab's sections pinned under it,
  one compact top story under the sections, a bottom tab bar (Home, Live, News, Help, More; the More sheet holds your
  account, My League, Draft and Learn), full-screen article reader, compact type and pictures sized for a phone, two
  games per row on Live, news as thumbnail rows under the top story, and tighter player rows. On computers the cover
  story's height follows the window height, so the week's games show on the first screen. The floating
  updates bar and chat button are left to bigger screens. Add it to your home screen for an app icon (on iPhone it then
  opens full screen).
- **Steady while you use it:** live refreshes (every 30 seconds during games) keep your place: sideways rows, tables in
  the game center and the story or game you were reading stay where they were. Closing a game, an article or a player
  card returns you to the same spot; the browser's Back button and Escape close what is open, and Back never reopens
  an article you closed. Switching tabs starts the new tab at the top. On phones, wide tables (betting picks, draft
  guide, game box scores) turn into cards instead of running off the screen, text boxes don't zoom the page on
  iPhone, long names are trimmed instead of wrapping, and nothing hides behind the bottom tab bar. Checked
  automatically at nine screen sizes, from a 360-pixel phone to a 1920-pixel monitor, for overlapping, cut-off or
  off-screen elements.

## Projections
- **BFF's own model (version 5, `ff_feat.py` + `ff_model.py`)**: gradient-boosted decision trees trained on every QB, RB,
  WR and TE game of the 13 completed seasons before this one (2013-2025 in 2026: about 72,000 player-games), retrained
  every run. Two kinds of trees are averaged: one predicts total PPR points, the other predicts each scoring stat
  (passing yards and touchdowns, interceptions, rushing yards and touchdowns, catches, receiving yards and touchdowns),
  which are then added up with the scoring rules. Each is averaged over 3 random seeds, and each stops training when a
  held-out slice stops improving, so it does not memorize noise.
- **What it reads** (all known before kickoff): usage (expected points from targets and carries by depth and field
  position, snap, target, carry and air-yard shares, red-zone and goal-line chances), production (season to date,
  recent form fading by half every 2.5 games, the last two games, last season and the one before; rookies start from
  what players drafted in their range scored), quarterback stats (attempts, yards, touchdowns, EPA, completion % over
  expected, sacks, rushing), the team's pace, pass rate over expected, efficiency and scoring, the opponent's efficiency
  against the pass and run and the fantasy points it allows to the position, the Vegas spread, total and implied team
  total, home, dome, rest, division game, the depth chart, his own injury report and practice participation, and
  teammates ruled out. Weeks ahead without betting lines use each team's points scored and allowed so far instead.
- **Tested out of sample:** every season from 2021 to 2026 was predicted by models trained only on earlier seasons
  (`research/bt_weekly_v5.py`). On the players the FantasyPros experts ranked who played, the model **alone** ranked
  players 0.622 in 2023-25 (experts 0.631) and **0.631 in 2026, tying the experts (0.631)**; the old model alone was
  0.601. In the season it is tested on each run (2025 in 2026), against a season average shrunk toward last season:
  ranking accuracy QB 0.548 (baseline 0.423), RB 0.754 (0.694), WR 0.674 (0.625), TE 0.647 (0.598).
- **The weekly stack of four forecasts** (new): next week's projection stacks BFF's model with the FantasyPros weekly
  expert consensus and ESPN's and Sleeper's public projections. Within each position, every forecast becomes a z-score
  (spreads above that week's average) among the players the experts ranked: model 30%, experts 10%, Sleeper 30%,
  ESPN 30%, re-weighted over the forecasts a player has. The k-th strongest player gets the k-th highest of the players'
  average projected points (BFF, Sleeper, ESPN). The rule is in `ff_stack.py`. `ff_produce.py` fetches ESPN and Sleeper every run and falls back to
  the numbers `proj_compare.py` saved; a site must project at least half of a position group to be used, and with
  neither site the old tested mix (40% model, 60% experts) is used. The weights were chosen on 2020-22 only
  (`research/bt_sites.py`), so 2023-2026 are a clean test.
- **Head to head on the same players** (every player-game ESPN, Sleeper, the experts and BFF all projected; ESPN's and
  Sleeper's past projections fetched from their public APIs, ESPN re-scored to full PPR):

  | 2023-25 (11,636 player-games) | Ranking accuracy | Better of two starters | Avg. miss (PPR) |
  | --- | --- | --- | --- |
  | FantasyPros experts | 0.565 | 62.1% | (ranks only) |
  | ESPN | 0.565 | 62.3% | 4.75 |
  | Sleeper | 0.561 | 62.1% | 4.86 |
  | BFF model alone | 0.556 | 61.6% | 4.82 |
  | **BFF projection (stack)** | **0.577** | **62.7%** | **4.71** |

  2026 weeks 1-6 (1,631): experts 0.552, ESPN 0.554 / 4.81, Sleeper 0.560 / 4.81, **BFF 0.574 / 4.76**. The stack beat
  every other source on all three measures in both periods and ranked better than each of them at every position;
  quarterbacks gained most (0.381 vs 0.369 in 2023-25, 0.390 vs 0.366 in 2026). Over every player the experts ranked
  (13,119 player-games in 2023-25): stack 0.641, previous 40/60 mix 0.635, experts 0.631, model alone 0.622; average
  miss 4.46 vs 4.53; 2026: 0.648 vs 0.636 vs 0.631. Better than the experts in all six seasons 2021-2026.
- **Why 10% better is out of reach** (asked for, tested, not possible): the lead over the best other source is about
  2% in ranking accuracy and under 1% in average miss. Weekly scoring is mostly noise no forecast can see. Hindsight
  check on 2023-25: ranking each player by his real average in all his *other* games that season, future games
  included, scores 0.531 with a 4.92-point miss, worse than ESPN's pre-game projection (0.561, 4.75). The sources agree
  with each other at 0.90-0.94, so their misses are mostly the same misses; weights picked on the test answers
  themselves reach only 0.578 (the stack: 0.577); ridge, gradient-boosted and per-position stacks did no better. Only
  perfect knowledge of each player's usage in that very game reaches 0.718. A 10% lead would need 0.622.
- **Live head-to-head with ESPN and Sleeper** (`proj_compare.py`, every 10 minutes): before each game BFF saves ESPN's
  and Sleeper's public projections next to its own, freezes them at kickoff, and after the games grades every source on
  the same players with official stats (ESPN's projected stats are re-scored to PPR so the scoring matches). The Learn
  page shows the running results; this replaces the old limitation that their past projections cannot be tested.
- **Later weeks and the rest of the season:** each remaining game is projected with its own opponent and team totals;
  a player's rest-of-season level is their average (2023-25 trade-value backtest: better than the separate
  rest-of-season model the old version added). The page's **Why?** breakdown shows the matchup, Vegas, teammates and
  expert-mix effects as their own bars, and each card shows the expected stat line behind the projection.
- **Injuries:** each player's status for his next game comes from ESPN's injury list for that game (`live_update.py`
  saves it every 10 minutes until kickoff), else the official injury report, else what the practice reports imply
  before Friday's game statuses. Measured on every 2021-2025 report against who really played (QB/RB/WR/TE with 3+
  games): Out played 0.1% of the time, Doubtful 0.4% (both projected 0), Questionable 61% (full projection, tagged Q);
  missed last week and not practicing 1.3% (projected 0, tagged as expected out), limited 40% (tagged Q). A report from
  a game already played never tags anyone. Later weeks for a player out now use the measured return curve (39% the
  next week, 69% after two, 85% after three, about 90% later, compared with healthy players) or ESPN's estimated
  return date. When neither ESPN nor the official report lists a player for his next game yet, a timeline reported in
  the news ("out at least three weeks", "out for the season", "to miss the remainder of the season") keeps him out until his team's game that many weeks after
  the story (labeled "expected from news reports"); a headline about a return is never read as a new absence. The page
  also lays ESPN's newest list over the data between runs.
- **Who is in the player pool:** only players on an NFL team. Each run checks the newest weekly team rosters
  (then the season roster, then the depth charts): a player who is not on a team's roster as active, reserve,
  inactive, practice squad or exempt is a free agent and left out (October 2026: Tyreek Hill, who has no team, and four
  others). A player on the **commissioner's exempt list** is projected 0 and shown as "not allowed to play", until a
  news report says he has been reinstated or is on track to play (then he is listed Questionable for his return; the
  reinstatement is kept in `news_state.json` after the story leaves the news feed, until the roster catches up; this
  fixed Josh Jacobs showing as out a week after his Oct 16 reinstatement). Fullbacks are no longer
  ranked as running backs.
- **No usage this season:** a running back, receiver or tight end who has been on his team at least 3 weeks, never on a
  reserve list, without one fantasy stat and not a depth-chart starter is capped near what such players really score
  (measured on 2021-2025, 1,160 players: RB 1.23, WR 1.08, TE 0.58 PPR points the next week), until he gets touches.
- **Questionable and then inactive:** a player listed Questionable who then did not play is treated as having missed
  the game. With no injury report for his next game yet, his chance of playing follows what really happened to such
  players (2021-2025, 558 cases: 52.5% played the next game and 62.5% the one after, against 29% and 46% after an Out).
- **Starting quarterbacks:** only a team's expected starter is projected (the best quarterback on the depth chart who
  is not out). Backups are projected 0; when the starter is out, the fill-in gets that game and, later, the chance the
  starter is still out. When the starter missed his last game and his team has no injury report for the next one yet
  (Monday to Wednesday), he is projected for the measured chance he plays and the next quarterback for the rest (week
  7 of 2026: Baker Mayfield about 39% of his projection, Jalon Daniels about 61% of his), so the team's quarterback
  total stays whole; once ESPN or the official report sets a status, the normal rule takes over on the page right away.
- **Games a player left hurt** still count toward his rates: we tested leaving them out (2025 test season) and next-game
  and rest-of-season errors got slightly worse, because players coming back from those injuries really did score less.
- **Half PPR and standard:** a player's catches are removed in proportion to how much the projection regressed his
  scoring (tested on 2023-2025: lower error than removing his full catches per game).
- **Custom scoring:** each player carries his own stat mix per game (passing yards, touchdowns and two-pointers,
  interceptions, carries, rushing and receiving yards and touchdowns, catches, first downs, fumbles lost): this
  season's games, shrunk toward last season's mix (or his position's average) as if he had 3 more games of it. His PPR
  projection is converted by the ratio of his points under your rules to his PPR points on that mix (limited to
  0.3x-3x). Example, week 6 of 2026: with TE premium (1.5 points per tight-end catch) Brock Bowers rose from 11th to 5th
  by BFF value; with 6-point passing touchdowns quarterback projections rose about 11%. In custom leagues the expert
  consensus (which is scored in PPR) counts 10 points less.

## Common sense: fill-ins, buy low and sell high

Numbers alone can be silly: a backup running back who piled up usage while the starter was hurt looks like a buy low
right when the starter comes back. BFF checks for that and a few other things, and every check was tested on 2020-25.

- **Fill-ins** (`ff_produce.py`, research `research/bt_fillin.py`): a back or receiver who took a starter's snaps (40%+
  of them, and 15+ points more than he played beside the starter) while that starter (a .55+ snap share for RBs, .70+ for WRs and TEs
  in his best 2 of his last 3 games, or first on the depth chart) missed 1-6 games, and who ranks below the starter
  (on the depth chart; without one, by targets plus carries). Once the starter was back, BFF's model over-projected such
  fill-ins 73% of the time: they scored 79% (RB), 80% (WR) and 75% (TE) of their projection. So each of a fill-in's
  weeks is scaled by that share, in proportion to the chance the starter plays that week (2023-25 check, fit on
  2020-22 only: average miss 3.82 -> 3.44 points, bias +1.37 -> +0.13). The starter's own projection needed no change
  (100-104% of it). A starter who has not played yet this season (suspension, exempt list) counts too: Josh Jacobs
  coming back makes Pierre Strong a fill-in. Example, week 7 of 2026: Dameon Pierce while Saquon Barkley returns.
- **Buy low / sell high** (`research/bt_commonsense.py`): no buy low on a fill-in whose starter is back or due back
  within two games, on two games played, on a player whose snaps are falling (last two games under 75% of his season
  share), or on a player whose usage is already top 6 at his position (that usage tends to come back down). With the
  checks, buy-low calls were right 69% of the time (60% without; the calls they drop: 44%). A fill-in still scoring 8+
  a game when his starter returns is a sell (68% of them scored less from then on, 1.7 fewer a game). Studs (top-6
  usage) running hot stay off the sell list: they cooled off by 4.2 a game but still averaged 17.9. The Trends page shows
  who was left off and why, and the player card, the dashboard, Ask BFF and the weekly calls use the same rules.

## BFF value: trade values and rankings
- For every week from now through week 17, BFF value adds up the starting-lineup points a player should give you over
  the best player at his position who would **not** start in your league (your lineup slots times your league size,
  with flex and superflex filled by projection). Each week counts `0.98 x 0.985^weeks-away` (the chance he is still
  active) times the expected points above that level, allowing for weekly ups and downs (a bell curve with a spread of
  half the replacement level), so fringe players keep some upside value. Byes, injured reserve and "out" this week come from the weekly projections.
- It is blended with the **FantasyPros rest-of-season expert consensus** (60% in PPR, 50% half PPR, 40% standard;
  a little more for running backs and for players with two games or fewer this season, where the consensus proved more
  reliable), mapped onto the same curve, then scaled 0-100 (the top players sit near 100).
- **Games since the consensus count right away.** The consensus file updates on Fridays, so Sunday's and Monday's games
  are not in it yet. BFF adds half of the change in its own value from the games played since the consensus was taken
  (2023-2025: value accuracy R² 0.297 -> 0.305, lopsided trades called for the side that really added more 68.5% ->
  70.2%, points above replacement about the same). Example, week 6 of 2026: Jaylen Warren, slow start then 20.6, 15.6
  and 36.8 points, rose from RB16 to RB12 by BFF value while the week-old consensus still had him RB19.
- **Injured reserve:** nothing before his estimated return, then (chance he plays) x (value if he plays), using what
  really happened to such players in 2023-2025: about 1 in 10 played the first week after the estimated return, 1 in 3
  by the fourth week, about half later, and 53% never played again that season. (The old rule counted 75% of every week.)
- Packages: the best player counts fully, then 80%, 60%, 45% (measured: adding two players to a team added
  best + 0.82 x second). A trade is **fair** only when BFF value is within 10%, the consensus within 30% and our
  projections alone within 50%; labels run Even / Slightly favors / Favors / Heavily favors.
- **Backtest, 2023-2025** (15 checkpoints: weeks 4, 6, 8, 10 and 12; only what was known at the time; truth = the real
  starting-lineup points each player added over the best free agent in 10 simulated 12-team leagues per checkpoint;
  every source put on the same value scale): rank accuracy experts alone 0.448, BFF value with the previous model
  0.446, **BFF value now 0.454**; lopsided trades (values 2x apart) called for the side that really added more 73.4%,
  73.2%, 73.5%; R² 0.257, 0.241, **0.259** (lineups in the simulation set by the previous projections, so the test does
  not favor the new model; with lineups set by the new ones: experts 0.440 / 72.5% / 0.290, BFF 0.448 / 72.5% / 0.293).
  BFF value is ahead of the experts in 2023 and 2024 and slightly behind in 2025. Reproduce with
  `research/bt_value_v5.py`.
- **A correction (October 2026):** an earlier version of this README and the site said BFF value beat the experts
  (0.446 vs 0.429, 73.2% vs 69.8%). That comparison put the experts on the old value scale (spread 0.2 x R), which
  understated them; on the same scale the experts score 0.448 / 73.4% / 0.257 and the previous BFF value 0.446 /
  73.2% / 0.241, so it was even with them, not ahead. The numbers
  above use the same scale for everyone.
- **The spread (October 2026):** the bell curve's spread is half the replacement level (real weekly misses are 6.5-8
  points, about 50-75% of it); the old 20% was a guess and too narrow.
- **Value over replacement (VORP):** like basketball's VORP, the points a player should score from now to week 17 over
  the best player at his position likely to be on waivers in your league (in a 12-team league with one QB, two RB, two
  WR, one TE and a flex: about the 20th quarterback, the 61st running back and wide receiver, and the 20th tight end,
  by projected points a game; it moves with your settings). It is on every player card, the Trade values chart and the trade analyzer, and BFF value takes
  15% of its weight from it (the rest stays on points over the best non-starter, the most accurate single measure).
  Tested on 2023-2025 (10 simulated 12-team leagues at each of 14 checkpoints, four roster setups, truth = real lineup
  points each player added over the best free agent): lopsided trades called for the side that really added more
  69.2% -> 70.2%, rank accuracy 0.422 -> 0.427, running backs overvalued by 8.9% -> 5.4% of a top-50 player's worth,
  overall fit R² 0.230 -> 0.226 (about the same). Pure VORP alone was less accurate (R² 0.15).
- **Lineup fit:** quarterbacks were not overvalued in general; a backup quarterback is just worth little to a team
  that already starts one. So trade suggestions count a player only if he would crack the lineup of the team that gets
  him: with your league linked, its best lineup in at least 35% of his remaining games; without a league, better than
  three quarters of starters at QB or TE, or the middle team's last starter at RB or WR. That ends offers padded with
  backup quarterbacks (such as Joe Burrow or Trevor Lawrence as filler). **Looking for: a QB** (or RB, WR, TE) in the
  trade analyzer lifts that rule for the position you need.
- The same value drives the Trade values chart, BFF rank on player cards, Find trades, the trade analyzer, the mock
  draft board (AI teams also follow the consensus), the draft guide, waiver targets and Ask BFF.

## BFF Originals: our own articles (`articles.py`)
Data-driven fantasy articles written for BFF and published on their own, mixed into the News tab (gold "BFF Original"
label, lead story while fresh, their own panel, a Home card, and on each mentioned player's card). Each opens in a
full-screen reader with linked players, a byline, the time, update notes and sources, and has its own link
(`#news/a/<id>`).

Written like an analyst, not a stat sheet: each player's game opens with the verdict ("stole the show", "was a
letdown", "did his job"), then the line in plain words ("caught all four of his targets for 130 yards and a
touchdown"), then what it means (the points against BFF's projection, a season high, a bell-cow workload or a
committee, a true number-one target share). Scoring plays read as sentences ("a 43-yard field goal by Cairo Santos",
"Caleb Williams' 24-yard touchdown pass to Luther Burden III"), and previews explain the Vegas line in words (a
double-digit favorite, a low total that points to a grind, a shootout-level total) instead of listing it. Every number
is still the data's own. A writer change rewrites the articles still in their window (writer version 7).

| Article (Eastern time) | When it publishes |
|---|---|
| **Thursday outlook** (records and form, Vegas line, each team's fantasy outlook, injuries, start 'em / sit 'em, best bets, BFF's pick) | Thursday 8 AM, updated until kickoff |
| **Thursday recap** (scoreboard, how it happened, a fantasy breakdown for each team, stock up and down, waiver wire, looking ahead) | Friday 7 AM |
| **Injury report** (ruled out or doubtful and who moves up, still on injured reserve, questionables with kickoff times, quarterback situations) | Friday 5 PM, until the first Sunday kickoff |
| **Sunday outlook** (things to know, start 'em / sit 'em, game-by-game capsules, best bets of the day) | Saturday 8 AM, updated until kickoff |
| **Sunday recap** (every score, the top performances, game by game, stock, injuries to watch, early waiver look, what is still to come) | once the afternoon games are final, before the night game |
| **Sunday night recap** | after the night game is final |
| **Monday outlook** and **Monday recap** | Monday 8 AM (updated until kickoff), and after the Monday game is final |
| **Fantasy landscape** (the week's MVPs, risers, fallers, injury fallout, waiver priorities, buy low / sell high, byes and best matchups ahead, BFF's calls scorecard) | Tuesday 10 AM, once the week is complete |
| **Other game days** (Saturday games late in the season, holidays, international games) | outlook by 8 AM that day (or 10 hours before the first kickoff, if that is earlier), recap 7 AM the next day |
| **Breaking news** (a relevant player ruled out or doubtful for his next game, out for the season (with the diagnosis when the headline names it), placed on or activated from injured reserve, traded or released) | on the next run after the news reaches BFF (every 10 minutes for headlines, every 3 hours for the official data) |

- **Publishes itself, and says so when it can't:** both workflows run `articles.py` and save `articles.json` with the
  page, so new articles appear on the live site within 10 minutes of their time with nothing for you to do. If the
  writer ever fails, the rest of the run still saves, the 3-hour run is marked failed at the end (GitHub emails you)
  and `status.json` shows `"articles": "failure"`. (October 2026 fix: a game not started yet, which has no score in
  `live.json`, crashed the writer, so no new article reached the live site for a day; the Thursday recap and the
  stories behind it publish on the first run with the fix, and a test now covers it.)
- **Updated as news breaks:** outlooks and the injury report are rewritten when their facts change (injuries, lines,
  projections) until kickoff, with an "Updated:" note saying what changed. Recaps and breaking stories are written once.
  When BFF's writer is fixed (the version number `WV` in `articles.py`), a recap or Tuesday landscape still in its
  window is rewritten once with the fix (same link and publish time), and a "ruled out" story whose player is then
  reported out for the season becomes that season-ending story in place instead of a second article.
- **Injuries are named by their source:** an official or ESPN listing by its name ("questionable"); BFF's own estimate
  between reports by what really happened ("missed week 6, status not set yet"), so it never reads like an official
  listing. A player who just missed time or is out is injury news, not a "faller"; a starter who played under 40% of
  the snaps in his last game is flagged as a possible injury instead of a role change, and a recap notes a player
  since ruled out for the season or placed on injured reserve.
- **Rules:** news counts only if it is under 48 hours old and first seen in the last 6 hours (a first run, or the
  first run after this update, only learns what is already known); an injury report counts only for the player's next
  game and not once that game has started; "ruled out for the rest of the game" headlines wait for the next official
  status; at most 3 breaking stories per run and 12 a day; each story once; articles older than 21 days are cleared. A
  failure here never stops scores, news or the page from saving.
- **Who writes them:** without any key, BFF writes them from its own data (credited "BFF Data Desk"); every number
  comes from the site's projections, lines, injury reports and box scores. **Optional, written by Claude:** add a
  repository **secret** named `ANTHROPIC_API_KEY` (an API key from [console.anthropic.com](https://console.anthropic.com),
  billed to your Anthropic account) and Claude rewrites each draft into a polished article (credited "BFF AI Desk
  (Claude)"). Claude gets only the draft and a fact sheet; if its version contains any number that is not in them, it
  is thrown out and BFF's own text is published instead. Optional variables: `BFF_AI_MODEL` (default
  `claude-sonnet-5-5`) and `BFF_AI_MAX_DAY` (the most Claude calls in 24 hours, default 30; after that BFF's own text is
  used). A typical week needs about 40 calls; a Sunday preview sends about 12,000 characters (roughly 3,000 tokens)
  and gets up to 4,000 tokens back, a breaking story about 2,500 characters (under 1,000 tokens). See current prices at
  [claude.com/pricing](https://claude.com/pricing#api).

## Trade analyzer and waivers
- **Trade analyzer** (Fantasy Help, and "Analyze in depth" on every offer in My League): a photo card for each player
  (BFF value, points a game, next 4 weeks, playoff weeks 15-17, bye, injury, usage signal, boom/bust, VORP and whether
  he would start for you), **Looking for** (lineup fit, or a QB, RB, WR or TE), the package math,
  the three fairness checks, your starting lineup's change week by week with next-4, rest-of-season and playoff totals,
  the other team's change, the roster spots each side must open or can fill (drops and best free agents), startable
  depth by position, and the single additions that would make an unfair offer fair.
- **Waivers:** every target shows its BFF value, the value of the player you would drop, and a FAAB guide based on the
  lineup points he adds the rest of the season (30+ points: 25-40% of your budget; 15-30: 12-25%; 8-15: 5-12%;
  3-8: 1-5%; less: a minimum bid). Targets need a real role, and without a linked league "free" means rostered in under
  half of ESPN and Yahoo leagues.

## Look and pictures
- **Street art at night:** night mode is the default (the theme button still offers day mode or your device's
  setting): a brick wall behind the page, two club spotlights sweeping slowly across it, a big faded BFF tag sprayed
  on the wall, spray-paint underlines on section titles that paint in when a tab opens, neon glow on buttons, the
  active tab and cards under the pointer, a light sweeping across the top story, the home title flickering on like a
  neon sign, and marker-style tags ("New", "Updated") on the feature cards. All of it stops for anyone who asks their
  device for less motion, and the heavy parts stay off on phones and low-power devices.
- **The whole screen, calmer rails:** on big monitors the pages widen to 1840 pixels (Home gets a left rail for New on
  BFF), the side rails are narrower (268 pixels) with smaller thumbnails, three-line headlines and at most six
  headlines, and Live's side lists sit beside a wider games grid with names on one line.
- Every tab reads like the News tab: a cover story on the tab's own artwork with picture headlines beside it, a headline
  rail on wide screens (headlines under the page on smaller ones).
- **News that fits the tab:** every headline gets a relevance score for each tab (your players on My League; top
  players on Home; start/sit, waivers and betting on Fantasy Help; rookies and drafts on Draft; analytics on Learn;
  this week's games on Live), less a point for each day of age. Covers, side stories and rails use it, and each real
  story photo leads one tab only.
- **Readable text on every picture:** text on a photo sits on a dark scrim sized to the text block. When the picture
  can be measured, its brightness behind the text sets the scrim (strong on a white photo, light on a dark one);
  otherwise BFF assumes the brightest possible photo, so white text keeps at least 4.5:1 contrast either way. Text on
  team colors switches to dark ink where white would be hard to read (Steelers gold, Raiders silver, Seahawks green).
- **Real pictures** on your own site: story photos, ESPN headshots everywhere a player is listed, team logos, photo
  cards on the Trade values chart and in the trade analyzer, and the player-card News tab with each story's picture.
  A player without an ESPN photo gets his jersey in team colors. Pages on claude.ai cannot load outside pictures, so
  that copy shows the tab artwork, jerseys and team colors.
- **Game photos:** every Live game card opens with a photo band and both team logos: the home stadium before kickoff,
  during the game a photo from ESPN's coverage of that game only (stories tagged with the game, and highlights posted
  after kickoff that name one of its teams; ESPN's league-wide top story and talk-show clips, which ESPN attaches to
  every game, are never used), the recap photo after the final. A picture that turns up for two games (in any size)
  is used for neither, so one headline photo can never fill every game. The game center puts that photo behind
  the score (no separate photo section). `live_update.py` saves each game's photo links and stadium ids in `live.json`
  (links only), so the photos show even when the page can't reach ESPN directly. The camera button turns outside
  pictures off.

## Accounts (optional; about 10 minutes, free)
Without this the site works exactly as before: everything a visitor links or stars is saved in their own browser.
With it, the account button (top right) lets visitors create an account and get their leagues, team, favorites and
settings back on any device. Creating one requires ticking a box agreeing to the **Terms of Use** and **Privacy Policy**
(both open from the account panel and the footer). Accounts are stored in a free Google Firebase project that you own:
1. Go to [console.firebase.google.com](https://console.firebase.google.com), **Create a project** (any name; Google
   Analytics is not needed).
2. **Security > Authentication > Get started > Sign-in method:** enable **Email/password**, then **Save**.
3. **Databases & Storage > Firestore > Create database:** pick a location, choose **production mode**, create it. Open
   its **Rules** tab, replace everything with the contents of `firestore.rules` from this kit, and **Publish**. (These
   rules let each signed-in person read, save and delete only their own data.)
4. **Project settings** (gear icon) **> General > Your apps > Web app (</>)**: register an app (any nickname, no
   hosting needed) and copy the `firebaseConfig` snippet it shows.
5. In GitHub: **Settings > Secrets and variables > Actions > Variables > New repository variable**, name it
   `BFF_FIREBASE` and paste the snippet. Optional variables: `BFF_TERMS_STATE` (the state whose law governs the terms;
   California if not set) and `BFF_CONTACT` (an email address or link where people can reach you about their data).
6. Run **Update Gridiron Fantasy** once. The account button now offers **Create account** and **Sign in**.

The Firebase web config is not a secret (it is meant to be in web pages); the Firestore rules are what protect the
data. The free plan allows 50,000 reads and 20,000 writes a day, far more than a personal site needs. People can delete
their account and its data from the account panel. On the claude.ai copy, the visitor's Claude sign-in is the account
and the data is saved with the page itself, private to each person. The Terms of Use and Privacy Policy are a
plain-language starting point, not legal advice: have a lawyer review them if the site grows, and note that no terms
can stop every lawsuit; they limit liability, require individual arbitration and rule out class actions where the law
allows.

## Runs by itself all year
- **Seasons roll over on their own.** `fetch_data.py` reads the NFL schedule to decide the season: in progress, about
  to start, or (after the last regular-season game) the next one. The model always learns from the 13 latest completed
  seasons and tests on the most recent, so each finished season joins on its own; nothing is tied to a year.
- **Offseason:** once a regular season ends, the site switches to the next season: rankings, trade values and the mock
  draft are built from last season's data, rookies and players who changed teams come in through the rosters and the
  consensus top 300, and Live says when the schedule usually arrives (May). When the schedule is published, week 1
  projections, opponents, byes and prop lines appear automatically, and live scores start with the first game.
- **New players** join from rosters, depth charts, the consensus top 300 and weekly stats; nobody keeps a list.
- **Health report:** after every data run `health.py` writes `status.json` (which steps worked, the season, the last
  good build, and which forecasts the weekly stack used at each position: `m+r+s+e` = BFF's model, the experts, Sleeper
  and ESPN; `fallback` = neither site answered, so the tested 40/60 mix ran). It changes at least once a day, which also keeps GitHub from pausing the scheduled jobs (GitHub pauses
  them after 60 days without activity in a public repository).
- **Safe by default:** tested library versions are pinned in `requirements.txt` (the newest versions install if those
  ever stop installing); each run checks the page before saving and keeps the last good version if anything fails;
  missing or late data files are skipped and picked up on the next run; GitHub emails you if a run fails.
- **Efficient runs:** the model's features for the 13 completed seasons are built once a season (about 6 minutes,
  with about 350 MB of downloads) and cached between runs (`.cache`); after that each run downloads only the last five
  seasons, and those completed-season files are kept for a week in a GitHub cache. Every player's games are projected in
  one batch (about 4 minutes a run). The Python libraries come from pip's cache.
- **A lighter page:** the big artwork (tab covers, backgrounds) is saved as separate files in `art/` (written by
  `assemble.py` from `app.css`), so the page is about 600 KB smaller and the pictures stay in the browser's cache. The 10-minute job reads ESPN's game pages only when they can
  have changed: live games every run, games not yet started every run in the last 4 hours before kickoff (inactives),
  every half hour within two days (practice reports) and every 2 hours before that.
- **A smoother page:** each tab is drawn the first time it is opened (and again only after new data), not all at
  start-up; ranking rows that are off screen are skipped by the browser until they scroll near
  (`content-visibility`); the "Around BFF" stories beside each tab are reused for 20 seconds instead of rebuilt on
  every tab switch; and phones, tablets and devices with 4 or fewer processor cores get a lighter mode (no page-turn animation or frosted-glass
  bars). Measured on a desktop: start-up long tasks 962 → 571 ms, switching back to Home about 80 → 30 ms.
- **Prop lines close at kickoff:** a game's lines leave the picks, parlays and Ask BFF the moment it kicks off, even
  if the live feed is a few minutes behind; a week's late games (Monday night) keep their lines until then.

## Predicted prop lines (`ff_lines.py`)
- **Set where the market sets them (refit October 25, 2026).** Books' prop lines track the public projections, so every
  line comes from the average of ESPN's and Sleeper's projection for that stat (`site_stats.py`), put through a rule fit
  to real posted lines: receiving yards 0.916 x, receptions 0.975 x + 0.15, rushing yards 0.843 x + 0.112 x the player's
  season average - 3.5, passing yards 0.404 x + 0.250 x his season average + 0.218 x the market x (Vegas implied team
  total / 22 - 1) + 75.5 (rounded down to .5), and passing touchdowns 0.5 below a projection of 0.95, 2.5 from 2.3, else
  1.5. Books post 0.5 passing TDs for low-scoring passers (Cam Ward, Daniel Jones, Malik Willis, J.J. McCarthy in week 7);
  the old model-based TD lines said 1.5 for them. BFF's own model stays out of the line so the picks can test it.
- **How close (research/bt_lines.py):** two samples of real week-7 lines: a public props page (Oct 21-23) and
  scoresandodds.com on Sunday morning (every player's lowest and highest line across books: 28 passing, 84 receiving,
  86 rushing, 85 receptions, 28 passing-TD lines with odds). Each rule scored on players it never saw, against Sunday's
  lines: 3.3 receiving yards from the books' line on average (the books themselves sit 3.3 apart), 3.8 rushing (books
  2.8; was 4.6), 0.25 receptions (books 0.38; was 0.29), 7.8 passing yards (books 7.2; was 11.1), and passing-TD lines
  match 26 of 28 (was 21 of 25). The season average (rushing, passing) and the Vegas total (passing) came in on a second
  refit that evening; on the earlier sample, each player scored by a fit that left him out: passing 5.6 (was 8.6),
  rushing 4.3 (was 4.9). For
  receiving yards and receptions nothing else tried closed the gap: what is left is the books' own information.
- **Picks:** an under on receiving yards when BFF's own model projects the player at least 10% below ESPN and Sleeper:
  57.2% of 719 in 2025 at lines built this way (every yardage under 54.2%). Passing-yard unders were picks at the first
  refit's lines but hit only 52.6% at these closer-to-the-books lines, rushing unders 52.8%, and overs where BFF was
  higher 46.1%, so none of those is a pick. Receptions and passing-TD unders hit often, but books charge -150 to -200
  for those, so a high chance there is not an edge: they get no picks and stay out of Ask BFF's leans and parlays. Each
  pick says how far down it holds (2025: still 55%+ down to 4.5% below our line), because a real book's line can sit
  lower than ours; Ask BFF's "best bets" lists only these picks. "Chance" on each line is how often the over hit in
  2025 for that stat and gap; passing TDs use the books' expected touchdowns read from real odds (0.578 + 0.676 x the
  projection), scaled to 2025 for the gap, as a Poisson count. "Our projection" = the sites' average scaled by BFF's
  model against theirs. A line you type in (your book's) gets its chance by shifting ours by the usual spread of
  outcomes between the two lines. The test used lines built from ESPN and Sleeper, not real book lines, and real prices
  carry a fee, so expect real results to run lower.
- **More props (October 26, 2026, `research/bt_props_more.py`):** pass attempts, completions, interceptions, rush
  attempts, targets, anytime TD and 1st-half TD, from the same ESPN and Sleeper projections (`site_stats.py` now also
  saves their pass attempts, carries and targets). Pass attempts sit at the projection (its whole number + .5);
  completions are projected attempts times the passer's completion rate (this season, last season at half weight, pulled
  toward the league's 64.5%); rush attempts 1.003 x - 0.259; targets 1.025 x (few books post targets, so the line sits
  where 2025's overs hit as often as receptions'). Against week 7's real lines, each rule scored on players it never saw:
  pass attempts 1.08 from the books' (the books 1.25 apart), completions 0.84 (0.61), rush attempts 0.95 (0.48).
  Interceptions and touchdowns are chances of 1 or more with fair odds: interceptions from projected attempts times the
  passer's rate pulled toward the league's 2.17% (3 points from the books' no-vig price on average, 26 passers);
  touchdowns from projected carries and targets at each position's touchdown rate, the Vegas team total and the player's
  own scoring history, fit on 2025 and checked on 2026 games it never saw (expected 23.9% of players to score, 22.4%
  did); 1st-half TD takes the share of each position's touchdowns scored before halftime (about half). None get picks:
  at the count lines no side hit 55% in both 2025 and 2026, and touchdown and interception prices are for comparing with
  your book. The bets page filters by prop type and lists the week's top touchdown chances; player cards, the prop
  checker and Ask BFF show them too; parlay leans stay on the tested yardage stats.
- **Players neither site projects** keep the opportunity model (expected targets, carries or pass attempts times
  efficiency, adjusted for the Vegas team total and the defense; tuned on 2024, tested on 2025), with a chance but no
  pick.
- **Updates every 10 minutes:** the scores workflow re-reads ESPN's and Sleeper's projections, the current ESPN odds and
  the news; a line moves when the sites' projections, the Vegas total or a role changes, and is pulled when a player is
  reported out. Each line keeps its opening number and the reason for every move. `site_stats.json` is saved only when
  a number changed.
- **To follow real sportsbook lines directly**, a licensed odds feed is needed (for example The Odds API or PropLine,
  both with free tiers and an API key); BFF does not scrape sportsbooks.
- `parlay_update.py` builds the best 2-, 3- and 5-pick parlays from tested picks only (one leg per game, no
  questionable players), locks them at the week's first kickoff, and grades them from official box scores.
- For entertainment, 21+ where legal. Gambling problem? Call or text 1-800-MY-RESET (1-800-697-3738), the National Problem Gambling Helpline.

## BFF's AI (nothing to set up)
Ask BFF's AI runs on each visitor's own device, so there is no server, account, key or bill. In Ask BFF a visitor taps
**Download BFF's AI**; the browser downloads WebLLM (from jsDelivr), the model's engine (GitHub) and its files (Hugging
Face) once, keeps them in the browser's storage, and from then on loads it from the device when Ask BFF opens (it never
downloads on its own). It needs WebGPU: recent Chrome or Edge on a computer, Chrome on Android, or Safari 26 and later.
- **Sizes** (Qwen3.5, WebLLM 0.2.86's prebuilt models): Max 9B (5.1 GB; needs 16 GB of memory or an 8 GB graphics
  card), Standard 4B (2.4 GB, the pick for computers), Lite 2B (1.1 GB, the pick for phones and devices reporting under
  8 GB of memory) and Mini 0.8B (0.45 GB, if Lite can't run). Artificial Analysis rates Qwen3.5 4B and 9B well above the
  Qwen3 models of the same size. A start that never finished (the page closed, or the device ran out of memory) waits for
  a tap and offers a smaller size; switching size frees the old one's files; "Remove BFF's AI from this device" frees
  them all.
- **How it answers:** BFF's rules and playbook (how to make start/sit, trade, waiver and prop calls), the facts for the
  question (see **BFF's AI** above), up to two recent exchanges, then the reply, streamed. "Think first" (AI settings):
  Auto lets the 4B and 9B think through trades and close calls once the device has shown it is fast enough, Always is
  slower and sharper, Never is fastest. Every number is checked against the facts and a start/sit verdict against BFF's
  call (one retry each, then the quick answer).
- Tested: `tests/aitest.py` (the page with a stand-in engine: the device check and sizes, the download with progress,
  loading from the device next time, the crash guard, the facts and knowledge base it gets, thinking, the number and
  verdict checks, lookups, follow-ups, the league, escaping, removing it, phones). The real model can't run on the test
  machine (no GPU, no network to Hugging Face): it answers only in a visitor's browser.

## Updating an existing site to this version
If Claude has access to your repository it pushes updates itself. To do it by hand, upload (replace) these files:
`template.html`, `app.css`, `index.html`, the `art/` folder, `brain.json`, `kb.json`, `articles.py`, `ff_build2.py`,
`ff_feat.py`, `ff_model.py`, `ff_produce.py`, `fetch_data.py`, `assemble.py`, `check_page.py`, `ff_lines.py`,
`parlay_update.py`, `calls_update.py`, `ff_news.py`, `news_update.py`, `live_update.py`, `proj_compare.py`, `ff_stack.py`, `site_stats.py`,
`ff_kdst.py`, `game_build.py`, `game.json`, `sync_sleeper.py`, `health.py`, `requirements.txt`, `firestore.rules`, `.gitignore`, `.nojekyll`, `README.md`, the
`research/` folder (the accuracy tests and Ask BFF's training; optional, never run by the workflows), and the two workflow
files in `.github/workflows/` (`update.yml`, `scores.yml`). `calls_backfill.py`, the `ai/` folder and
`.github/workflows/ai.yml` are retired and can be deleted. Leave
your `*_history.json`, `lines.json`, `parlays.json`, `bet_inputs.json`, `articles.json`, `news.json`, `news_state.json`,
`live.json`, `site_stats.json` and `proj_compare.json` alone; your workflows keep those up to date. Then run **Update Gridiron Fantasy** once (the first
run builds the model's 13-season feature tables, about 6 extra minutes).
Optional: add the `ANTHROPIC_API_KEY` secret for Claude-written articles (see **BFF Originals**).

## One-time setup (about 10 minutes)
1. Create a free account at github.com and sign in.
2. Click **New repository**, name it `gridiron-fantasy`, choose **Public**, and create it.
3. Click **uploading an existing file** and drag in everything from this folder **except** the hidden `.github`
   folder and `.nojekyll` file. Click **Commit changes**. Then **Add file > Create new file**, name it `.nojekyll`,
   leave it empty, and commit (it tells GitHub to publish the files as they are).
4. Add the two workflow files: **Add file > Create new file**, name it `.github/workflows/update.yml`, paste in the
   contents of `update.yml` from this kit, and commit. Repeat for `.github/workflows/scores.yml`.
   (Already set up? Replace both files with these new versions.)
5. **Settings > Actions > General > Workflow permissions:** choose **Read and write permissions**, then **Save**.
6. **Settings > Pages:** set the branch to `main` and `/ (root)`, then **Save**. Your site will be at
   `https://YOUR-USERNAME.github.io/gridiron-fantasy/`.
7. Test it: **Actions** tab > **Update Gridiron Fantasy** > **Run workflow**. A run takes about 5 to 10 minutes
   because it downloads several seasons of play-by-play data. Then run **Live scores, news and lines** once.
8. Optional: switch on **Accounts** (above) and **Sleeper sync** (below).

## Sync your Sleeper league automatically (optional)
1. Find your league ID: the long number in your league's web address on sleeper.com.
2. **Settings > Secrets and variables > Actions > Variables tab > New repository variable**. Name it
   `SLEEPER_LEAGUE_ID` and paste the number.
3. Run the data workflow again. Sleeper league data is public and needs no password. (Visitors don't need this: the
   page links Sleeper and ESPN leagues itself, and reads Yahoo and other leagues from a copied page or screenshots.)

## Good to know
- GitHub Pages has a soft limit of 10 site builds per hour, which is why the live workflow runs every 10 minutes
  and saves only when something changed. GitHub can also delay scheduled runs at busy times.
- On your own site, scores also load straight from ESPN in your browser every 30 seconds during games, and news,
  lines and parlays refresh every few minutes without reloading the page.
- Player photos, team logos and news pictures load from ESPN's and the publishers' servers on your own site (the
  camera button turns them off). They belong to the NFL, ESPN, the teams and the publishers. The claude.ai copy shows
  team-color graphics instead.
- A free GitHub Pages site is public. A synced Sleeper league's team names and rosters are visible to anyone with
  the link. Leagues you import by hand are saved only in your own browser.
- GitHub pauses scheduled workflows in a public repository after 60 days with no activity; the daily health report
  keeps the repository active. If updates ever stop, open **Actions** and re-enable the workflows.
- If a run fails, open it in the **Actions** tab to see the error. The usual cause is a data file that has not been
  published yet. The site keeps the last good version until the next run succeeds.

## Sources
- [nflverse](https://github.com/nflverse/nflverse-data): play-by-play, weekly stats, snap counts, rosters, depth
  charts, injury reports; [nfldata](https://github.com/nflverse/nfldata) schedules with Vegas spreads and totals.
- [FantasyPros](https://www.fantasypros.com) expert consensus rankings (weekly and rest of season, PPR) and roster
  percentages, mirrored by [DynastyProcess](https://github.com/dynastyprocess/data), which also supplies the player ID
  crosswalk. If they cannot be downloaded, the site uses its own projections alone.
- ESPN public scoreboard, game and news data; Sleeper trending adds and league scoring settings; the news publishers
  listed above.
- BFF Originals are written from the data above; when the optional key is set, Claude rewrites them through the
  [Claude API (Messages)](https://docs.claude.com/en/api/messages).
- Kicker and D/ST scoring: [Yahoo default league settings](https://help.yahoo.com/kb/SLN6489.html) and
  [scoring categories](https://help.yahoo.com/kb/SLN6442.html) (what counts as points allowed). Spin Draft and kicker/D/ST
  history: nflverse weekly player stats, team stats and play-by-play. Real prop lines used to fit and check BFF's lines
  (read by hand, Oct 2026): a public props page and [scoresandodds.com](https://www.scoresandodds.com/nfl/props).
- BFF's AI: [WebLLM](https://github.com/mlc-ai/web-llm) 0.2.86 running [Qwen3.5](https://huggingface.co/mlc-ai) (9B, 4B, 2B
  or 0.8B; Apache 2.0) in the browser; model comparison from [Artificial Analysis](https://artificialanalysis.ai/articles/qwen3-5-small-models).
- Gambling help: the National Problem Gambling Helpline, [1-800-MY-RESET](https://ncpgambling.org/help-treatment/national-helpline-1-800-522-4700/).
- BFF is not affiliated with the NFL, its teams, or any source listed here.
