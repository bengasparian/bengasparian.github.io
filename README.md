# BFF · Ben's Fantasy Football: auto-updating version

This folder turns BFF (Ben's Fantasy Football) into a free website that keeps itself up to date all year, with nothing
to edit from one season to the next. Since November 2026 it is built for **commercial use**: every number, story and
picture on it is BFF's own or comes from a source whose license allows commercial use (see **Free for commercial use**),
and it is ready for ads and tips (see **Making money**). Three GitHub workflows do the work, no API keys needed:

| Workflow | File | When | What it does |
|---|---|---|---|
| **Update Gridiron Fantasy** | `update.yml` | every 3 hours (23 minutes past) | downloads the latest NFL data, rebuilds every projection, ranking, trend and prop line, kickers and defenses, saves and grades the weekly calls, writes and updates BFF Originals, checks the page, saves it |
| **Scores, news and lines** | `scores.yml` | every 30 minutes (4 and 34 past) | final scores, box scores and scoring plays after each game, headline links, pulls prop lines for players reported out, BFF Originals (breaking news, previews, recaps); only saves when something changed |
| **Player photos** | `photos.yml` | Tuesdays 09:41 UTC (and on demand) | finds freely licensed player photos on Wikimedia Commons and saves small copies with each photographer's credit and license |

All three share one queue, so they never save at the same moment, and each run starts from the newest saved data (not
the version that was current when it was queued). Before anything is saved, `check_page.py` checks the page (data
readable, enough players, no script errors), the live files and the photo credits; anything broken is put back to the
last good version, so the published site never breaks.

## Free for commercial use
What the site is built from, and on what terms. This is a plain-language summary, not legal advice; have a lawyer look
it over if the site starts earning real money.

| What | Used for | Terms |
|---|---|---|
| [nflverse data](https://github.com/nflverse/nflverse-data) | play-by-play, weekly player stats, snap counts, rosters (height, weight, college, draft), depth charts, injury reports, the player table, and the schedule with final scores and the Vegas spread and total (the `schedules` release) | [CC BY 4.0](https://github.com/nflverse/nflverse-data/blob/master/LICENSE.md): commercial use allowed with credit, which the Sources page gives |
| BFF's own models and writing | every projection, ranking, BFF value, trade and waiver call, prop line, kicker and defense number, and every BFF Original | yours |
| [Wikidata](https://www.wikidata.org) + [Wikimedia Commons](https://commons.wikimedia.org) | player photos | Wikidata is CC0; each photo is used only under a free license (public domain, CC0, CC BY or CC BY-SA), with its author and license on the player's card and under Sources → Photo credits |
| BFF's team badges | team marks everywhere a logo would go | drawn by BFF from each team's abbreviation and colors; no NFL or team logos are used |
| Headline links (CBS Sports, Pro Football Talk, RotoBaller, PFF, Sharp Football Analysis) | the News tab | the headline and a link to the publisher's own page, nothing else (no teaser text, no pictures); `BFF_NEWS_LINKS` turns them off |
| [Tesseract.js](https://github.com/naptha/tesseract.js) 6.0.1 | reading league screenshots in the browser | Apache 2.0 |
| [WebLLM](https://github.com/mlc-ai/web-llm) 0.2.86 + [Qwen3.5](https://huggingface.co/mlc-ai) | BFF's AI, on the visitor's own device | Apache 2.0 |
| [Google Fonts](https://fonts.google.com) | the page's typefaces | open font licenses |
| Firebase (optional) | accounts | Google's terms; your own free project |

Removed in November 2026 because their terms do not allow a commercial site to reuse them: ESPN's and Sleeper's APIs
(projections, league import, live scores, injuries, headshots, logos, game photos, trending adds), FantasyPros expert
rankings and roster rates (via DynastyProcess), Yahoo Sports and RotoWire feeds, outside story pictures and teasers, and
the optional Claude-written articles. What that changed: projections and BFF value are BFF's model alone (a little less
accurate than the old blend; see **Projections** and **BFF value**), leagues come in by copy and paste or screenshots,
scores arrive after each game instead of live, and photos come from Commons (players without a free photo get their
jersey). The Learn page still compares BFF with ESPN, Sleeper and the FantasyPros experts, with numbers from BFF's own
research; naming them to compare is fine, and BFF says it is not affiliated with anyone it names.

Things to know before you earn from it:
- **Player photos** show real people. BFF uses them the way a news site does, beside each player's stats and news, never
  to endorse anything. If you would rather not, set the repository variable `BFF_PLAYER_PHOTOS` to `off`; the next photo
  run removes them and every player gets his jersey.
- **Headline links**: each publisher's own terms apply to its feed; some say "personal, non-commercial use". BFF shows
  only the headline as a link to the publisher (no text or pictures), which is how news aggregators commonly work, but if
  a publisher objects, set `BFF_NEWS_LINKS` to `off` (the News tab then shows BFF Originals and the official reports).
- **Team names** are used only to say which team is which. "NFL" and team names are trademarks of their owners.
- **Your repository's history** still holds the data files from before November 2026 (other sites' past projections
  and real posted prop lines in `research/hist` and `research/props`, removed from the current files). They are not on
  the site, but anyone can see a public repository's history. Claude can rewrite the history to remove them if you
  want (it changes every commit's ID, so do it only when nobody else has a copy).

## Making money: ads and tips (optional, free)
Both stay off until you set them. Nothing to pay.
1. **Apply to Google AdSense** at [adsense.google.com](https://adsense.google.com) (free; approval takes days to weeks
   and is not guaranteed: Google reviews the content and its [program policies](https://support.google.com/adsense/answer/48182)).
   Your site is the GitHub Pages address, for example `https://YOUR-USERNAME.github.io/REPOSITORY/`. AdSense adds sites
   by domain; `github.io` is on the [Public Suffix List](https://publicsuffix.org), which AdSense accepts for
   subdomains ([AdSense help](https://support.google.com/adsense/answer/12170421)), so the site to add is
   `YOUR-USERNAME.github.io`.
2. **Your publisher ID:** AdSense shows it as `pub-` and 16 digits (Account > Settings > Account information). In
   GitHub: **Settings > Secrets and variables > Actions > Variables > New repository variable**, name `BFF_ADS_CLIENT`,
   value `ca-pub-` and the 16 digits. The next data run puts Google's ad code and the site-verification tag on the page
   and writes `ads.txt`.
3. **ads.txt at the root of your domain:** AdSense reads it only at the root (`YOUR-USERNAME.github.io/ads.txt`;
   [AdSense help](https://support.google.com/adsense/answer/12171612)), and a project site lives one folder down. So create
   one more free public repository named exactly `YOUR-USERNAME.github.io`, add a file `ads.txt` with the single line
   `google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0` (your own 16 digits), and turn on Pages for it
   (Settings > Pages > branch `main`, `/ (root)`). With a custom domain pointed at this repository instead, BFF's own
   `ads.txt` is already at the root and this step is not needed.
4. **Consent in Europe:** Google requires a certified consent message for visitors in the EEA, the UK and Switzerland
   ([Google's requirements](https://support.google.com/admanager/answer/13554116)). In AdSense: **Privacy & messaging >
   European regulations > Create message**, pick your site, and give the privacy policy link
   `https://YOUR-USERNAME.github.io/REPOSITORY/#privacy` (it opens BFF's Privacy Policy, which has the advertising
   disclosures AdSense asks for). BFF shows no consent banner of its own.
5. **Where ads go:** with only `BFF_ADS_CLIENT`, ads show where Google's Auto ads put them once you turn Auto ads on in
   AdSense. To use BFF's own ad spaces instead (on Home
   and Learn, never next to the betting page), create a display ad unit in AdSense (**Ads > By ad unit > Display ads**),
   copy its `data-ad-slot` number into a repository variable `BFF_ADS_SLOT`, and leave Auto ads off in AdSense. Ad
   spaces stay empty (and take no room) until then.
6. **Tips:** set `BFF_TIP_URL` to a `https://` link to your tip page (Ko-fi, Buy Me a Coffee, GitHub Sponsors, PayPal.me
   or similar) and a **Support BFF** button appears in the footer.
7. Run **Update Gridiron Fantasy** once (Actions tab > Run workflow) after setting any of these.

The Terms of Use (section 5a) and Privacy Policy (Advertising) already describe ads and tips. A custom domain (about $10-15
a year) is optional; AdSense works with the `github.io` address as above.

## What's on the site
- **Home:** the player rankings screen with the week built in: the week header (dates, games), the week's games strip,
  and **Quick hits** (your team or a link-your-league card, the latest BFF Originals, injury watch, buy low and sell
  high, and the week's top touchdown chances). Its sections: **This week** (rankings),
  **Trade values** (the rest-of-season BFF value chart, tiered, for your league settings), **Start/sit** (cheat sheet)
  and **Favorites**. Every player has a card with projections, usage, game logs, schedule, VORP, news and this week's
  prop lines.
- **New on BFF:** on wide screens the home page's left side spotlights what the site does that others don't (Spin
  Draft, kickers and defenses, BFF's prop lines, Ask BFF, linking any league, the graded weekly calls), one card at a
  time; on narrower screens it is a strip under the top story. The numbers on the cards come from the data, so they
  stay true as things change.
- **Kickers and team defenses (`ff_kdst.py`):** Players has **K** and **D/ST** buttons with this week's ranks, the season's
  points, the last three games and the rest-of-season projection; each has its own card (game log, road ahead, how it
  is scored and projected). Leagues keep them (typed or copied rosters: "Bills D/ST", a kicker's name; screenshots).
  Your lineup fills the league's K and D/ST spots, and power rankings count them when the league starts them. After a
  game, points come from the official box score (`live.json`: field goals by distance, extra points, sacks, takeaways,
  touchdowns, safeties, blocked kicks and points allowed; checked on 2026 weeks 1-6: kickers 186 of 186 exact, D/ST 184
  of 186), and the official numbers from `ff_kdst.py` replace them on the next data run; until a game's stats are out,
  lineups use the projection. They stay out of BFF's trade values, buy/sell calls, waiver targets and prop lines.
  **Scoring** (the most common default league settings): field goals 0-39 yards 3, 40-49 yards 4, 50+ yards 5, extra
  points 1; D/ST sack 1, interception 2, fumble recovery 2, touchdown 6, safety 2, blocked kick 2, points allowed 0:
  10, 1-6: 7, 7-13: 4, 14-20: 1, 21-27: 0, 28-34: -1, 35+: -4, where points allowed leave out touchdowns the other
  defense scores off this team's offense, safeties and defensive two-point returns. **Projections** (research/bt_kdst.py,
  fit on 2015-22 and tested on 2023-25 games they never saw): D/ST from the opponent's Vegas implied points, the
  defense's sacks and takeaways so far, the opponent offense's sacks and giveaways so far and home field (average miss
  4.4 points, correlation 0.33 with what happened; the league average missed by 4.5 with 0.08); kickers from the team's
  implied points, his points per game so far and indoor games (3.6 and 0.16 against 3.7 and 0.04: a kicker's week is
  mostly luck, and the page says so).
- **Spin Draft (`game_build.py`, Draft > Spin Draft game):** spin a slot machine for a random NFL team and season since
  1999, draft one of that team's real fantasy scorers into an open spot (QB, RB, RB, WR, WR, TE, FLEX), and build the
  highest-scoring lineup in seven spins, with two re-spins. The end screen shows your total, how close you came to the
  best lineup your spins allowed, your best score, and a result to copy and share. **Daily challenge** gives everyone the
  same spins that day; PPR, half PPR or standard. Points are each player's regular-season total for that team that
  season from nflverse's weekly stats, with the franchise named as it was then. Checked: every weekly row of every
  season re-adds to its points with the stated rules, and famous seasons match their published totals (Cooper Kupp
  2021: 439.5 PPR; Christian McCaffrey 2023: 391.3). `game.json` is rebuilt only when a season finishes.
- **Scores** (the tab is still `#live` in links): every game of the week in the middle, the week's **top performers**
  on the left and **leaders by position** on the right (projections before the games). Before kickoff a game shows its
  time, venue and Vegas line; after it, the final score, the box score (passing, rushing, receiving, kicking, team
  totals), the scoring plays and everyone's fantasy points. These come from nflverse's official stats and play-by-play
  (`live_update.py` into `live.json`, every 30 minutes), usually a few hours after the game, with the full play-by-play
  by the next morning. **There is no live in-game feed** (the free, licensed sources publish after the game), and the
  page says so. Tap a game for its game center (outlook, win chances from the spread, injuries, expected starting
  quarterbacks, top performers, box score). Past and future weeks too.
- **News:** a sports-site layout with a top story, lead stories and rails. Outside stories are **headline links only**
  (CBS Sports, Pro Football Talk, RotoBaller, PFF, Sharp Football Analysis): the publisher's headline, linked to its own
  page; the labels (Breaking, Injury alert, Waiver wire...) and "fantasy impact" notes are BFF's. **BFF Originals**
  (below) lead the feed while fresh, with their own panel, and the official injury report and roster moves (nflverse)
  are in the feed too. A headline's status is tied to the player it names: "Saquon Barkley set to play, DeVonta Smith
  ruled out" marks only Smith as out.
- **My League:** link your league for your best lineup, waiver targets, trade ideas and a matchup simulator. It works
  with any site or app and never connects to it: on your league's website select all on a team's roster page (or a page
  with every roster), copy, paste, **Read page**, repeat per team, **Import**. The page finds every player (also "J.
  Allen" style names with a team or position nearby, and names glued to team codes), splits a page with every roster
  into teams, and guesses each team's name; every name can be fixed and missing players added before the import.
  **Screenshots** work on phones: each one is cleaned up and read in the browser with the open-source Tesseract.js
  (loaded from jsDelivr only when used, about 6 MB the first time). The typed format still works: one line per team,
  "Team name: Player, Player, ..."
- **Draft:** **Mock draft** against AI teams with different strategies (graded at the end), the pick-by-pick **Draft
  guide** for your league settings, and draft tips. BFF uses no outside draft-position data: the board is BFF value, and
  the AI teams draft from it with their own needs and some randomness.
- **Fantasy Help:** the in-season toolkit: **Weekly calls** (below), Trends (buy & sell, usage, proof), Matchups (this
  week, defenses, schedules), waivers & trades, the trade analyzer with **Find trades**, BFF's prop lines, and tips.
- **Weekly calls:** every week's must starts, must sits, buy lows and sell highs, saved by `calls_update.py`. Start and
  sit calls keep updating until that player's game kicks off, then lock; buy and sell calls lock at the week's first
  kickoff. After the games each call is graded with official stats: a must start hits when he finishes as a starter
  (top 12 QB, 24 RB, 30 WR, 12 TE in PPR), a must sit hits when he finishes outside those spots, and buy lows and sell
  highs are graded on the player's next 3 games. A season scorecard shows the hit rates next to honest yardsticks.
  Weeks 2-5 of 2026 were rebuilt (one time) from the model of the day using only pre-game information and are labeled
  "rebuilt"; everything from week 6 on is saved live.
- **Favorites:** star any player to track him in Home → Favorites (this week's outlook, his points once his game is
  final, status, props, news). Saved in each visitor's own browser (and in their account, if they have one).
- **Scoring:** PPR, half PPR, standard, or **Custom** (the Scoring menu): TE premium, 6-point passing touchdowns, points
  per carry or first down, interception and fumble penalties, and the rest. Every projection, ranking, BFF value, trade
  value, draft pick and waiver target re-scores for it.
- **Points by every name:** once a game's official stats are out, the home page's This week list and the start/sit
  cheat sheet show each player's fantasy points for it in a badge by his name ("Final"), scored with your scoring.
- **BFF's AI (Ask BFF):** Ask BFF talks like a person: any wording, follow-ups ("what about him next week?"),
  comparisons, "why", small talk, all from BFF's numbers. The AI runs **entirely on the visitor's device**: an open
  model (Qwen3.5, Apache 2.0) that the browser downloads once and runs with WebGPU through WebLLM, sized to the device
  (Standard 4B, 2.4 GB, on computers; Lite 2B, 1.1 GB, on phones; Max 9B, 5.1 GB, for strong computers; Mini 0.8B as a
  fallback). Nothing typed into Ask BFF leaves the device, and there is nothing for the site owner to set up or pay.
  The page hands the model the facts for the question, and **every number in a reply is checked against those facts**
  before it shows (a made-up number gets one retry, then the quick answer); on start/sit questions the verdict must
  also match BFF's call. Until a visitor downloads it, on devices that can't run it, or with "Quick answers only", the
  classic Ask BFF answers.
- **Classic Ask BFF, powered by BFF Brain, in Ben's voice:** BFF's own question model, trained here and running inside
  the page (no outside AI and no key): a logistic-regression intent model over words, word pairs and letter groups (so
  typos still work), trained on about 16,200 football questions (`research/brain/`), that sorts a question into 28
  kinds. On 94 hand-written questions it never trained on it picked the right kind 96% of the time. The numbers,
  verdicts and reasons always come from BFF's own functions; asked whether it is a person, it says plainly that it is a
  bot Ben built. A **football knowledge base** (61 topics) is searched by meaning, it **remembers the conversation**,
  and it **asks instead of guessing** ("Which Allen do you mean?").
- **Player cards** show height, weight, birthday, college, draft slot and NFL season (nflverse) next to the number, depth
  chart role, age and bye, and the player's photo with its credit when a free one exists.
- **Learn:** how everything works, accuracy (including how BFF compares with the big sites), and **Sources & citations**
  for every number, story and photo.
- **Updates bar:** on wider screens, a broadcast-style bar at the bottom cycles through updates that fit the page
  (Home: everything; Scores: results and top performers; News: news; Fantasy Help: fantasy and betting updates; My
  League: your players). Pause, step through, or hide it.
- **Accounts:** visitors can create an account (they must agree to the Terms of Use and Privacy Policy) to save their
  leagues, team, favorites and settings and get them back on any device. See **Accounts** below.
- **Phones:** an app-style layout: a compact header, each tab's sections pinned under it, a bottom tab bar (Home,
  Scores, News, Help, More), full-screen article reader, compact type, and tighter rows. Add it to your home screen for
  an app icon.
- **Steady while you use it:** refreshes keep your place, closing a game, an article or a player card returns you to the
  same spot, the browser's Back button and Escape close what is open, and wide tables turn into cards on phones.
  Checked automatically at nine screen sizes, from a 360-pixel phone to a 1920-pixel monitor.

## Projections
- **BFF's own model (version 5, `ff_feat.py` + `ff_model.py`)**: gradient-boosted decision trees trained on every QB, RB,
  WR and TE game of the 13 completed seasons before this one (2013-2025 in 2026: about 72,000 player-games), retrained
  every run. Two kinds of trees are averaged: one predicts total PPR points, the other predicts each scoring stat, which
  are then added up with the scoring rules. Each is averaged over 3 random seeds and stops training when a held-out
  slice stops improving.
- **What it reads** (all known before kickoff): usage (expected points from targets and carries by depth and field
  position, snap, target, carry and air-yard shares, red-zone and goal-line chances), production (season to date,
  recent form, the last two games, last season and the one before; rookies start from what players drafted in their
  range scored), quarterback stats, the team's pace, pass rate over expected, efficiency and scoring, the opponent's
  efficiency against the pass and run and the fantasy points it allows to the position, the Vegas spread, total and
  implied team total, home, dome, rest, division game, the depth chart, his own injury report and practice
  participation, and teammates ruled out. Weeks ahead without betting lines use each team's points scored and allowed.
- **Since November 2026 the projection is BFF's model alone.** Until then, next week's projection stacked the model with
  ESPN's and Sleeper's projections and the FantasyPros expert consensus; their terms do not allow a commercial site to
  reuse them, so they are gone.
- **How it compares (honest numbers).** Every player-game that ESPN, Sleeper, the FantasyPros experts and BFF all
  projected, graded on the real PPR points (research; ESPN's and Sleeper's past projections read from their public APIs,
  ESPN re-scored to full PPR; every season predicted by models trained only on earlier seasons):

  | 2023-25 (11,636 player-games) | Ranking accuracy | Better of two starters | Avg. miss (PPR) |
  | --- | --- | --- | --- |
  | FantasyPros experts | 0.565 | 62.1% | (ranks only) |
  | ESPN | 0.565 | 62.3% | 4.75 |
  | Sleeper | 0.561 | 62.1% | 4.86 |
  | **BFF projection (BFF's model, since Nov 2026)** | **0.556** | **61.6%** | **4.82** |
  | All four combined (BFF's projection until Nov 2026) | 0.577 | 62.7% | 4.71 |

  2026 weeks 1-6 (1,631): experts 0.552, ESPN 0.554 / 4.81, Sleeper 0.560 / 4.81, BFF's model 0.550 / 4.86. So BFF's
  own projection is within about 1-2% of the big sites, a little behind on ranking, between ESPN and Sleeper on the
  average miss. Combining all four was the only thing that beat every site, and that needs their data.
- **Why no one can be 10% more accurate:** weekly scoring is mostly noise no forecast can see. Ranking each player by his
  real average in all his *other* games that season, future games included, scores 0.531 with a 4.92-point miss (worse
  than the sites' pre-game projections). The sources agree with each other at 0.90-0.94, so their misses are mostly the
  same misses. Only perfect knowledge of each player's usage in that very game reaches 0.718.
- **Later weeks and the rest of the season:** each remaining game is projected with its own opponent and team totals;
  a player's rest-of-season level is their average. The page's **Why?** breakdown shows the matchup, Vegas and teammate
  effects as their own bars, and each card shows the expected stat line behind the projection.
- **Injuries:** each player's status for his next game comes from the official injury report (nflverse), else what the
  practice reports imply before Friday's game statuses. Measured on every 2021-2025 report against who really played
  (QB/RB/WR/TE with 3+ games): Out played 0.1% of the time, Doubtful 0.4% (both projected 0), Questionable 61% (full
  projection, tagged Q); missed last week and not practicing 1.3% (projected 0, tagged as expected out), limited 40%
  (tagged Q). A report from a game already played never tags anyone. Later weeks for a player out now use the measured
  return curve (39% the next week, 69% after two, 85% after three, about 90% later) or the injured-reserve minimum. When
  the official report does not list a player for his next game yet, a timeline reported in the news ("out at least
  three weeks", "out for the season") keeps him out until his team's game that many weeks after the story (labeled
  "expected from news reports"); a report that he is headed to injured reserve counts as the league's 4-game minimum,
  and "out indefinitely" or "expected to miss an extended period" as out for his next game (then the return curve). A
  report that only says what could happen ("could miss the rest of the season") is shown as questionable, "not
  confirmed", and does not change his projection. These timelines are kept in `news_state.json`, because a story
  leaves the news feed within a day or two; a later report that he is playing ends one. A headline that says he is
  playing is never read as an absence.
- **Who is in the player pool:** players on an NFL team (active, reserve, inactive, practice squad or exempt on the
  newest weekly roster, then the season roster, then the depth charts), plus this year's rookies picked in the top 100.
  A player on the **commissioner's exempt list** is projected 0 and shown as "not allowed to play", until a news report
  says he has been reinstated (kept in `news_state.json` until the roster catches up).
- **No usage this season:** a running back, receiver or tight end who has been on his team at least 3 weeks, never on a
  reserve list, without one fantasy stat and not a depth-chart starter is capped near what such players really score
  (measured on 2021-2025, 1,160 players: RB 1.23, WR 1.08, TE 0.58 PPR points the next week), until he gets touches.
- **Questionable and then inactive:** with no injury report for his next game yet, his chance of playing follows what
  really happened to such players (2021-2025, 558 cases: 52.5% played the next game and 62.5% the one after).
- **Starting quarterbacks:** only a team's expected starter is projected (the best quarterback on the depth chart who
  is not out). When the starter missed his last game and his team has no injury report for the next one yet (Monday to
  Wednesday), he is projected for the measured chance he plays and the next quarterback for the rest, so the team's
  quarterback total stays whole; once the official report sets a status, the normal rule takes over.
- **Half PPR and standard:** a player's catches are removed in proportion to how much the projection regressed his
  scoring (tested on 2023-2025: lower error than removing his full catches per game).
- **Custom scoring:** each player carries his own stat mix per game (this season, shrunk toward last season's or his
  position's average as if he had 3 more games of it); his PPR projection is converted by the ratio of his points under
  your rules to his PPR points on that mix (limited to 0.3x-3x).

## Common sense: fill-ins, buy low and sell high
Numbers alone can be silly: a backup running back who piled up usage while the starter was hurt looks like a buy low
right when the starter comes back. BFF checks for that and a few other things, and every check was tested on 2020-25.
- **Fill-ins** (`ff_produce.py`, research `research/bt_fillin.py`): a back or receiver who took a starter's snaps while
  that starter missed 1-6 games, and who ranks below him. Once the starter was back, BFF's model over-projected such
  fill-ins 73% of the time: they scored 79% (RB), 80% (WR) and 75% (TE) of their projection. So each of a fill-in's
  weeks is scaled by that share, in proportion to the chance the starter plays that week (2023-25 check, fit on
  2020-22 only: average miss 3.82 -> 3.44 points, bias +1.37 -> +0.13).
- **Buy low / sell high** (`research/bt_commonsense.py`): no buy low on a fill-in whose starter is back or due back
  within two games, on two games played, on a player whose snaps are falling, or on a player whose usage is already top
  6 at his position. With the checks, buy-low calls were right 69% of the time (60% without). A fill-in still scoring 8+
  a game when his starter returns is a sell (68% of them scored less from then on). The Trends page shows who was left
  off and why, and the player card, the dashboard, Ask BFF and the weekly calls use the same rules.

## BFF value: trade values and rankings
- For every week from now through week 17, BFF value adds up the starting-lineup points a player should give you over
  the best player at his position who would **not** start in your league (your lineup slots times your league size,
  with flex and superflex filled by projection). Each week counts `0.98 x 0.985^weeks-away` times the expected points
  above that level, allowing for weekly ups and downs (a bell curve with a spread of half the replacement level), and
  15% of its weight comes from VORP (below). Scaled 0-100 (the top players sit near 100).
- **Since November 2026 it is BFF's own projections alone** (it used to be blended with the FantasyPros rest-of-season
  consensus). Backtest, 2023-2025 (15 checkpoints; only what was known at the time; truth = the real starting-lineup
  points each player added over the best free agent in 10 simulated 12-team leagues per checkpoint):

  | Measure | FantasyPros experts | BFF value until Nov 2026 (blend) | **BFF value now** |
  | --- | --- | --- | --- |
  | Rank accuracy | 0.448 | 0.454 | **0.432** |
  | Lopsided trades called right | 73.4% | 73.5% | **72.0%** |
  | Fit (R²) | 0.257 | 0.259 | **0.225** |

  So BFF's own value orders players a little less accurately than the experts did, and calls lopsided trades right 72
  times in 100 against their 73. With lineups in the simulation set by the newer projections: experts 0.440 / 72.5%,
  BFF's own value 0.430 / 71.3%. Reproduce with `research/bt_value_v5.py`.
- **Injured reserve:** nothing before his estimated return, then (chance he plays) x (value if he plays), using what
  really happened to such players in 2023-2025.
- Packages: the best player counts fully, then 80%, 60%, 45%. A trade is **fair** only when BFF value is within 10% (or
  2 points) and BFF's projections within 50%; labels run Even / Slightly favors / Favors / Heavily favors.
- **Value over replacement (VORP):** the points a player should score from now to week 17 over the best player at his
  position likely to be on waivers in your league (in a 12-team league with one QB, two RB, two WR, one TE and a flex:
  about the 20th quarterback, the 61st running back and wide receiver, and the 20th tight end). On every player card,
  the Trade values chart and the trade analyzer.
- **Lineup fit:** trade suggestions count a player only if he would crack the lineup of the team that gets him (with
  your league linked, its best lineup in at least 35% of his remaining games). **Looking for: a QB** (or RB, WR, TE) in
  the trade analyzer lifts that rule for the position you need.
- The same value drives the Trade values chart, BFF rank on player cards, Find trades, the trade analyzer, the mock
  draft board, the draft guide, waiver targets and Ask BFF.

## BFF Originals: our own articles (`articles.py`)
Data-driven fantasy articles written by BFF's own writer (credited "BFF Data Desk"; no outside service, no key) and
published on their own, mixed into the News tab (gold "BFF Original" label, lead story while fresh, their own panel, a
Home card, and on each mentioned player's card). Each opens in a full-screen reader with linked players, a byline, the
time, update notes and sources, and has its own link (`#news/a/<id>`). Every number comes from BFF's projections and
lines, the official injury reports and the official box scores; no other site's text or pictures are used (an outlet's
report is linked as a source, never quoted).

Written like an analyst, not a stat sheet: each player's game opens with a verdict that matches the numbers ("stole the
show", "delivered", "cleared a low bar", "came up short", "had a modest day"), then the line in plain words ("caught all
four of his targets for 130 yards and a touchdown"), then what it means (the points against BFF's projection, a season
high, a bell-cow workload or a committee, a true number-one target share). Recaps tell the game: who struck first, the
score that put the winner ahead for good, and a second half that broke it open ("After halftime the Commanders
outscored the Eagles 14-0, with Rachaad White's 1-yard touchdown run"). Previews explain the Vegas line in words, and
late-week outlooks rank players against the whole week. Writer version 8 (November 2026); a writer change rewrites the
recaps still in their window.

| Article (Eastern time) | When it publishes |
|---|---|
| **Thursday outlook** (records and form, Vegas line, each team's fantasy outlook, injuries, start 'em / sit 'em, props to know, the score Vegas implies) | Thursday 8 AM, updated until kickoff |
| **Thursday recap** (scoreboard, how it happened, a fantasy breakdown for each team, stock up and down, waiver wire, looking ahead) | Friday 7 AM |
| **Injury report** (ruled out or doubtful and who moves up, still on injured reserve, questionables with kickoff times, quarterback situations) | Friday 5 PM, until the first Sunday kickoff |
| **Sunday outlook** (things to know, start 'em / sit 'em, game-by-game capsules, props to know) | Saturday 8 AM, updated until kickoff |
| **Sunday recap** (every score, the top performances, game by game, stock, injuries to watch, early waiver look, what is still to come) | once the afternoon games are final and their box scores are out |
| **Sunday night recap** | after the night game's box score is out |
| **Monday outlook** and **Monday recap** | Monday 8 AM (updated until kickoff), and after the Monday game |
| **Fantasy landscape** (MVPs, risers, fallers, injury fallout, waiver priorities, buy low / sell high, byes and best matchups ahead, BFF's calls scorecard) | Tuesday 10 AM, once the week is complete |
| **Other game days** (Saturday games late in the season, holidays, international games) | outlook that morning, recap the next |
| **Breaking news** (a relevant player ruled out or doubtful for his next game, out for the season, placed on or activated from injured reserve, traded or released) | on the next run after the news reaches BFF (every 30 minutes for headlines, every 3 hours for the official data) |

- **Publishes itself:** both workflows run `articles.py` and save `articles.json`, so new articles appear on the live site
  within 30 minutes of their time. If the writer ever fails, the rest of the run still saves, the 3-hour run is marked
  failed at the end (GitHub emails you) and `status.json` shows `"articles": "failure"`.
- **Updated as news breaks:** outlooks and the injury report are rewritten when their facts change, with an "Updated:"
  note saying what changed. Recaps and breaking stories are written once.
- **Breaking news is checked before it runs:** a status counts only for the player the headline names ("Saquon Barkley
  set to play, DeVonta Smith ruled out" is about Smith; in "DeVonta Smith, Dontayvion Wicks ruled out" both are out),
  "doubtful" is its own status (never written as "ruled out"), a "ruled out" from during a game is about that game (not
  the next one), a report that names another week is about that week, a report that only says what could happen waits
  for confirmation, news counts only if it is under 48 hours old and first seen in the last 6 hours, at most 3 breaking
  stories a run and 12 a day.
- **Corrections:** a breaking story that turns out wrong (a player "ruled out" for a week he then played, "done for the
  season" before he played again, or a story the checks above would now stop) is replaced by a correction under the
  same link, saying what was wrong. In November 2026 this corrected the stories written before the checks existed (the
  old tagging applied one player's status to everyone in a headline, and read in-game rulings as next week's; in a test
  on the site's own articles it found nine, among them Saquon Barkley and Puka Nacua "ruled out" for weeks they played).
  Each story keeps a copy of the report it came from, so the check still works after the report leaves the news feed.
  A second check on November 3, with the reports recovered from the site's history, corrected eight more: reports about
  week 7 and 8 games written up as the next week (Tyler Huntley, Hunter Henry, Jake Ferguson and Rashid Shaheed, hurt
  during those games, and Breece Hall twice), Emeka Egbuka's "doubtful" written as "ruled out", and Lamar Jackson "done
  for the season" from a report that said the injury could end his season (he went to injured reserve, at least four
  games).
- **Injuries are named by their source:** an official listing by its name ("questionable"); BFF's own estimate between
  reports by what really happened ("missed week 6, status not set yet"), so it never reads like an official listing.
- Articles older than 21 days are cleared. A failure here never stops scores, news or the page from saving.

## Trade analyzer and waivers
- **Trade analyzer** (Fantasy Help, and "Analyze in depth" on every offer in My League): a card for each player (BFF
  value, points a game, next 4 weeks, playoff weeks 15-17, bye, injury, usage signal, boom/bust, VORP and whether he
  would start for you), **Looking for** (lineup fit, or a QB, RB, WR or TE), the package math, the fairness checks, your
  starting lineup's change week by week, the other team's change, the roster spots each side must open or can fill,
  startable depth by position, and the single additions that would make an unfair offer fair.
- **Waivers:** every target shows its BFF value, the value of the player you would drop, and a FAAB guide based on the
  lineup points he adds the rest of the season (30+ points: 25-40% of your budget; 15-30: 12-25%; 8-15: 5-12%;
  3-8: 1-5%; less: a minimum bid). Targets need a real role. With your league linked, "free" means not on a roster in
  it; without one, a player outside BFF's top 20 QB, 50 RB, 60 WR or 20 TE by rest-of-season value counts as likely
  free (BFF uses no outside roster rates).

## Look and pictures
- **Street art at night:** night mode is the default (the theme button offers day mode or your device's setting): a
  brick wall, two club spotlights, a faded BFF tag, spray-paint underlines, neon glow and marker-style tags. All of it
  stops for anyone who asks their device for less motion, and the heavy parts stay off on phones and low-power devices.
- **Player photos** (`photos.py`, weekly): Wikidata links each player's Pro Football Reference ID to a picture on
  Wikimedia Commons; only pictures whose license is public domain, CC0, CC BY or CC BY-SA are used (anything with "no
  derivatives", "non-commercial", fair use or no license is skipped). Each is cropped to a 3:4 portrait, saved small in
  `photos/`, and credited (author, license with its link, "cropped and resized", and CC BY-SA kept as CC BY-SA) on the
  player's card and under Sources → Photo credits. Players without a free photo get their jersey in team colors.
  Photos only show on your own site (the claude.ai copy shows jerseys).
- **Team badges:** BFF draws its own shield for each team from its abbreviation and colors, used wherever a logo would go.
- **Readable text on every picture:** text on artwork sits on a dark scrim sized to the text block, so white text keeps
  at least 4.5:1 contrast, and text on team colors switches to dark ink where white would be hard to read.
- **Game cards** show both teams' badges and colors (no outside game photos).

## Accounts (optional; about 10 minutes, free)
Without this the site works exactly as before: everything a visitor links or stars is saved in their own browser.
With it, the account button (top right) lets visitors create an account and get their leagues, team, favorites and
settings back on any device. Creating one requires ticking a box agreeing to the **Terms of Use** and **Privacy Policy**
(both open from the account panel and the footer, and directly at `…/#terms` and `…/#privacy`). Accounts are stored in a
free Google Firebase project that you own:
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
their account and its data from the account panel. The Terms of Use and Privacy Policy are a plain-language starting
point, not legal advice: have a lawyer review them if the site grows.

## Runs by itself all year
- **Seasons roll over on their own.** `fetch_data.py` reads the NFL schedule to decide the season: in progress, about
  to start, or (after the last regular-season game) the next one. The model always learns from the 13 latest completed
  seasons and tests on the most recent, so each finished season joins on its own; nothing is tied to a year.
- **Offseason:** once a regular season ends, rankings, trade values and the mock draft are built from last season's data,
  rookies and players who changed teams come in through the rosters, and Scores says when the schedule usually arrives
  (May). When the schedule is published, week 1 projections, opponents, byes and prop lines appear automatically.
- **New players** join from rosters, depth charts and weekly stats; nobody keeps a list. **Photos** for new players are
  looked up every Tuesday.
- **Health report:** after every data run `health.py` writes `status.json` (which steps worked, the season, the last good
  build). It changes at least once a day, which also keeps GitHub from pausing the scheduled jobs (GitHub pauses them
  after 60 days without activity in a public repository).
- **Safe by default:** tested library versions are pinned in `requirements.txt` (the newest versions install if those
  ever stop installing); each run checks the page before saving and keeps the last good version if anything fails;
  missing or late data files are skipped and picked up on the next run; GitHub emails you if a run fails.
- **Efficient runs:** the model's features for the 13 completed seasons are built once a season (about 6 minutes) and
  cached between runs; after that each run downloads only the last five seasons. The score job downloads the season's
  stats and play-by-play only when a finished game still lacks its box score or scoring plays.
- **Prop lines close at kickoff:** a game's lines leave the betting page and Ask BFF the moment it kicks off.
- **When GitHub runs the schedule late:** GitHub starts scheduled workflows on a best-effort basis and can delay or
  drop runs when it is busy. From October 31 to November 3, 2026 the 30-minute job ran only every 3½ to 10 hours and
  the 3-hour job every 5 to 13 hours. Nothing breaks (each run catches up on everything since the last), but news, breaking
  stories and scores arrive later. A free fix, if you want runs on time (about 5 minutes, optional):
  1. On GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
     Repository access: only `bff`. Permissions: **Actions: Read and write** (nothing else). Copy the token.
  2. Make a free account at [cron-job.org](https://cron-job.org) and create a job every 30 minutes (at 4 and 34 past)
     that sends **POST** to `https://api.github.com/repos/bengasparian/bff/actions/workflows/scores.yml/dispatches`
     with the headers `Authorization: Bearer <your token>` and `Accept: application/vnd.github+json`, and the body
     `{"ref":"main"}`. Optionally a second job every 3 hours (23 past) for `update.yml`.
  3. GitHub answers **204** when it worked; the run shows under **Actions** as "workflow_dispatch". The workflows share
     one queue, so an extra start never runs twice at once; if the token ever expires, the schedule still runs as before.

## Predicted prop lines (`ff_lines.py`)
BFF predicts where books will post each line, from its own numbers only. These are predictions, not picks: BFF makes
no picks and suggests no parlays (the build-your-own slip stays, with each leg's chance from BFF's model). For
entertainment, 21+ where legal. Gambling problem? Call or text 1-800-MY-RESET (1-800-697-3738), the National Problem
Gambling Helpline.
- **The model line:** expected volume x efficiency x this game (opponent, Vegas implied team total), times a fixed factor,
  rounded down to .5. Two stats take one more step fit to real posted lines (`research/bt_lines_bff.py`): **passing
  yards** 0.1459 x the model line + 0.2713 x his season average + 0.4071 x the model line x (implied team total / 22 -
  1) + 130.705, and **receiving yards** 1.1093 x the model line (books post receiving lines about 11% above BFF's model),
  each rounded down to .5. Each was adopted only because it beat the plain model line on both samples of real lines,
  scored on players it never saw; the same kind of step did not help rushing yards or receptions, so those stay the
  model line. Passing touchdowns: 0.5 below 0.70 expected, 1.5 below 2.55, else 2.5.
- **How close (week 7 of 2026, real lines read by hand):** two samples, one book's lines read Oct 21-23 and each player's
  lowest and highest line across books on Sunday (scoresandodds.com), against BFF's own model lines. BFF's lines sat an
  average of 4.96 and 5.72 receiving yards from the books' (the books themselves sat 3.21 apart), 9.06 and 8.16 rushing
  yards (books 3.58), 0.60 receptions (books 0.40) and 7.43 and 9.20 passing yards (books 6.96); passing-TD lines matched
  21 of 25. Lines built from ESPN's and Sleeper's projections (what BFF used until November 2026) sat closer, by 1.4 to
  4.8 yards and 0.35 receptions: that is the cost of using only BFF's own numbers. **A correction:** the first version
  of this check (Nov 2) compared Sunday's real lines with the market lines BFF had published that day instead of BFF's
  own, which made BFF's own lines look closer than they are (it quoted 3.23 receiving yards); the numbers above are the
  corrected ones, and the passing-yard step was refit on BFF's own lines.
- **More props** (`research/bt_props_bff.py`): pass attempts (0.3856 x BFF's expected attempts + 20.26), completions
  (0.4581 x expected completions + 11.27), rush attempts and targets (BFF's expected volume, targets x 0.975), each
  rounded down to .5. Against week 7's real lines, scored on players they never saw: pass attempts 1.48 from the books'
  (books 1.12 apart), completions 1.02 (0.54), rush attempts 1.57 (0.52). Few books post targets, so those were set so
  overs hit about as often as receptions'. Interceptions and touchdowns are chances of 1 or more with fair odds:
  interceptions from projected attempts times the passer's rate (2026 games: expected 48.9% of passers to throw one,
  50.8% did), touchdowns from projected carries and targets at each position's rate, the Vegas team total and the
  player's own scoring history (2026: expected 22.2% to score, 22.4% did; 2025: 22.2% and 22.0%); 1st-half TD takes the
  share of touchdowns scored before halftime.
- **Chances:** "Over chance" on each passing, rushing and receiving line comes from how real results spread around
  projections like his (`prop_qs.json`), at BFF's expected value and BFF's line, pulled halfway toward 50% and kept within
  38-62% (BFF's projection is not a sure thing); passing TDs use the same with a Poisson count. For pass attempts,
  completions, rush attempts and targets it is how often overs hit at lines built this way in 2025-2026; touchdowns and
  interceptions are Poisson chances of 1 or more. At BFF's model lines (before the passing- and receiving-yard steps),
  2025 overs hit 46.8% for receptions, 44.4% for receiving yards, 49.1% for rushing yards, 50.0% for passing yards and
  47.2% for passing TDs. A line you type in (your book's) gets its chance by shifting ours by the usual spread of
  outcomes between the two lines.
- **Updates:** every 3 hours with the projections; the 30-minute job pulls a player's lines when he is reported out (as
  books do), never for a ruling during his last game. Each line keeps its opening number and the reason for every move.
- **To follow real sportsbook lines directly**, a licensed odds feed is needed (for example The Odds API, with a free
  tier and your own key); BFF does not scrape sportsbooks.

## BFF's AI (nothing to set up)
Ask BFF's AI runs on each visitor's own device, so there is no server, account, key or bill. In Ask BFF a visitor taps
**Download BFF's AI**; the browser downloads WebLLM (from jsDelivr), the model's engine (GitHub) and its files (Hugging
Face) once, keeps them in the browser's storage, and from then on loads it from the device when Ask BFF opens (it never
downloads on its own). It needs WebGPU: recent Chrome or Edge on a computer, Chrome on Android, or Safari 26 and later.
- **Sizes** (Qwen3.5, WebLLM 0.2.86's prebuilt models): Max 9B (5.1 GB; needs 16 GB of memory or an 8 GB graphics
  card), Standard 4B (2.4 GB, the pick for computers), Lite 2B (1.1 GB, the pick for phones and devices reporting under
  8 GB of memory) and Mini 0.8B (0.45 GB, if Lite can't run). "Remove BFF's AI from this device" frees the space.
- **How it answers:** BFF's rules and playbook, the facts for the question, up to two recent exchanges, then the reply,
  streamed. Every number is checked against the facts and a start/sit verdict against BFF's call (one retry each, then
  the quick answer).
- Tested: `tests/aitest.py` (the page with a stand-in engine). The real model answers only in a visitor's browser.

## Updating an existing site to this version
If Claude has access to your repository it pushes updates itself. To do it by hand, upload (replace) these files:
`template.html`, `app.css`, `index.html`, the `art/` folder, the `photos/` folder, `brain.json`, `kb.json`,
`articles.py`, `ff_build2.py`, `ff_feat.py`, `ff_model.py`, `ff_produce.py`, `fetch_data.py`, `assemble.py`,
`check_page.py`, `ff_lines.py`, `prop_qs.json`, `calls_update.py`, `ff_news.py`, `news_update.py`, `live_update.py`,
`photos.py`, `ff_kdst.py`, `game_build.py`, `game.json`, `health.py`, `requirements.txt`, `firestore.rules`,
`.gitignore`, `.nojekyll`, `README.md`, the `research/` folder (the accuracy tests and Ask BFF's training; optional,
never run by the workflows), and the three workflow files in `.github/workflows/` (`update.yml`, `scores.yml`,
`photos.yml`). Delete these retired files: `parlay_update.py`, `proj_compare.py`, `site_stats.py`, `sync_sleeper.py`,
`ff_stack.py`, `parlays.json`, `parlay_history.json`, `proj_compare.json`, `site_stats.json`, `research/hist/`,
`research/props/`, `research/hist_fetch.py` (and `calls_backfill.py`, the `ai/` folder and `.github/workflows/ai.yml`
if you still have them), and the repository variable `SLEEPER_LEAGUE_ID` and secret `ANTHROPIC_API_KEY` if you set
them (no longer used). Leave your `*_history.json`, `lines.json`, `bet_inputs.json`, `articles.json`, `news.json`,
`news_state.json` and `live.json` alone; your workflows keep those up to date. Then run **Update Gridiron Fantasy**
once, and **Player photos** once.

## One-time setup (about 10 minutes)
1. Create a free account at github.com and sign in.
2. Click **New repository**, give it a name (for example `bff`), choose **Public**, and create it.
3. Click **uploading an existing file** and drag in everything from this folder **except** the hidden `.github`
   folder and `.nojekyll` file. Click **Commit changes**. Then **Add file > Create new file**, name it `.nojekyll`,
   leave it empty, and commit (it tells GitHub to publish the files as they are).
4. Add the three workflow files: **Add file > Create new file**, name it `.github/workflows/update.yml`, paste in the
   contents of `update.yml` from this kit, and commit. Repeat for `scores.yml` and `photos.yml`.
5. **Settings > Actions > General > Workflow permissions:** choose **Read and write permissions**, then **Save**.
6. **Settings > Pages:** set the branch to `main` and `/ (root)`, then **Save**. Your site will be at
   `https://YOUR-USERNAME.github.io/REPOSITORY/`.
7. Test it: **Actions** tab > **Update Gridiron Fantasy** > **Run workflow** (about 5 to 10 minutes the first time).
   Then run **Scores, news and lines** and **Player photos** once each.
8. Optional: **Accounts** and **Making money** (above).

## Switches (repository variables)
Settings > Secrets and variables > Actions > Variables. Each takes effect on the next run of the workflow named.

| Variable | Value | Effect |
|---|---|---|
| `BFF_ADS_CLIENT` | `ca-pub-` + 16 digits | AdSense on (ad code, verification tag, `ads.txt`); Update Gridiron Fantasy |
| `BFF_ADS_SLOT` | an ad unit's slot number | fills BFF's own ad spaces (Home, Learn) |
| `BFF_TIP_URL` | a `https://` link | the footer's **Support BFF** button |
| `BFF_FIREBASE` | the `firebaseConfig` snippet | accounts on |
| `BFF_TERMS_STATE`, `BFF_CONTACT` | a state; an email or link | the terms' governing law; how people reach you about their data |
| `BFF_PLAYER_PHOTOS` | `off` | no player photos (the next Player photos run removes them) |
| `BFF_NEWS_LINKS` | `off` | no outside headline links (the next score run empties them) |

## Good to know
- GitHub Pages has a soft limit of 10 site builds per hour; the score job runs every 30 minutes and saves only when
  something changed. GitHub can also delay scheduled runs at busy times.
- Final scores and box scores appear when nflverse publishes them, usually a few hours after a game; play-by-play and
  player stats by the next morning. Kickoff times, Vegas lines and scores update every 30 minutes; projections every
  3 hours. On your own site the page checks for new scores every 15 minutes (5 while games are on) and for news and
  lines every few minutes, without reloading.
- A free GitHub Pages site is public. Leagues people import are saved only in their own browser (and their account).
- GitHub pauses scheduled workflows in a public repository after 60 days with no activity; the daily health report
  keeps the repository active. If updates ever stop, open **Actions** and re-enable the workflows.
- If a run fails, open it in the **Actions** tab to see the error. The usual cause is a data file that has not been
  published yet. The site keeps the last good version until the next run succeeds.

## Sources
- [nflverse](https://github.com/nflverse/nflverse-data) (CC BY 4.0): play-by-play, weekly stats, snap counts, rosters,
  depth charts, injury reports, the player table, and the [schedules](https://github.com/nflverse/nflverse-data/releases/tag/schedules)
  with final scores and Vegas spreads and totals.
- [Wikidata](https://www.wikidata.org) (CC0) and [Wikimedia Commons](https://commons.wikimedia.org) (each photo's own free
  license, credited on the site).
- Headline links: [CBS Sports](https://www.cbssports.com/nfl/), [Pro Football Talk](https://www.nbcsports.com/nfl/profootballtalk),
  [RotoBaller](https://www.rotoballer.com/nfl), [PFF](https://www.pff.com/nfl), [Sharp Football Analysis](https://www.sharpfootballanalysis.com/).
- Research comparisons only (not used on the site's numbers): ESPN's and Sleeper's past public projections and the
  FantasyPros expert consensus (via [DynastyProcess](https://github.com/dynastyprocess/data)), read once for the accuracy
  tests; real prop lines read by hand (Oct 2026) from a public props page and [scoresandodds.com](https://www.scoresandodds.com/nfl/props).
- Kicker and D/ST scoring: the common default league settings, as [Yahoo's help page](https://help.yahoo.com/kb/SLN6489.html)
  lists them.
- Ads: [AdSense sites](https://support.google.com/adsense/answer/12170421), [ads.txt](https://support.google.com/adsense/answer/12171612),
  [consent requirements](https://support.google.com/admanager/answer/13554116), [Public Suffix List](https://github.com/publicsuffix/list).
- BFF's AI: [WebLLM](https://github.com/mlc-ai/web-llm) 0.2.86 running [Qwen3.5](https://huggingface.co/mlc-ai) (Apache 2.0).
- Gambling help: the National Problem Gambling Helpline, [1-800-MY-RESET](https://ncpgambling.org/help-treatment/national-helpline-1-800-522-4700/).
- BFF is not affiliated with the NFL, its teams, or any source listed here.
