"""BFF Brain knowledge base: football rules, fantasy terms, league structure and analytics terms.
Each entry: (id, [ways people ask it], answer[, last season it is current for]). The page skips an entry once the
site's season is past that season (dates and records that change), so nothing goes stale. Answers are short, plain and checked against official sources
(NFL rulebook and NFL.com operations pages; season dates from NFL.com's 2026-27 important dates). Things that change
every season (rosters, stats, injuries, odds) are NOT here: those come from BFF's live data."""

KB = [
 # ---------------- scoring and the basics
 ('score_values', ['how many points is a touchdown', 'what is a field goal worth', 'how many points for a safety', 'what is an extra point worth',
                   'how many points is a two point conversion', 'nfl scoring system', 'how does scoring work in football'],
  'A <b>touchdown</b> is 6 points, the <b>extra point</b> kick after it 1, a <b>two-point conversion</b> 2, a <b>field goal</b> 3 and a <b>safety</b> 2. '
  'If the defense returns a blocked kick or a turnover on a try all the way to the other end zone, it scores 2.'),
 ('game_length', ['how long is an nfl game', 'how many quarters in football', 'how long is a quarter', 'how long does a football game last',
                  'how many minutes in an nfl game'],
  'An NFL game is <b>60 minutes</b> of game clock: four 15-minute quarters, with halftime after the second. Because the clock stops often, a game usually takes a little over 3 hours.'),
 ('downs', ['how do downs work', 'what is a first down', 'how many downs do you get', 'what does 3rd and 5 mean', 'what is a turnover on downs'],
  'The offense gets <b>four downs</b> (plays) to gain <b>10 yards</b>. Make it and you earn a new first down; fail and the ball goes to the other team. "3rd and 5" means it is the third try and 5 yards are still needed. '
  'Teams usually punt or kick a field goal on 4th down; going for it and failing is a <b>turnover on downs</b>.'),
 ('field_size', ['how big is a football field', 'how long is a football field', 'how wide is a football field', 'how deep is the end zone'],
  'The field is <b>100 yards</b> between the goal lines, plus a <b>10-yard end zone</b> at each end (120 yards in all), and <b>53⅓ yards</b> (160 feet) wide.'),
 ('players_on_field', ['how many players are on the field', 'how many players per team on the field', 'how many players play at once', '11 players on the field'],
  'Each team has <b>11 players</b> on the field at a time. Twelve or more is a penalty.'),
 ('overtime', ['how does overtime work', 'nfl overtime rules', 'can an nfl game end in a tie', 'what happens if the game is tied',
               'does each team get the ball in overtime', 'playoff overtime rules'],
  '<b>Regular season</b> (since 2025): one <b>10-minute</b> period, and <b>both teams get a possession</b> even if the first one ends in a touchdown; after that the next score wins, and if it is still tied when time runs out, the game is a <b>tie</b>. '
  '<b>Playoffs</b>: 15-minute periods, both teams get a possession, and they keep playing until someone wins.'),
 ('play_clock', ['what is the play clock', 'how long is the play clock', 'delay of game'],
  'After a play ends the offense has <b>40 seconds</b> to snap the ball (<b>25</b> after stoppages like timeouts and penalties). Running out of time is <b>delay of game</b>, a 5-yard penalty.'),
 ('timeouts', ['how many timeouts does each team get', 'do timeouts carry over', 'how many timeouts in overtime'],
  'Each team gets <b>3 timeouts per half</b>; unused first-half timeouts do not carry over. In regular-season overtime each team gets 2.'),
 ('two_minute', ['what is the two minute warning', 'two-minute warning'],
  'The <b>two-minute warning</b> is an automatic stoppage when 2:00 remain in the 2nd and 4th quarters, almost like a free timeout.'),
 ('challenges', ['how do coach challenges work', 'how many challenges does a coach get', 'what is the red flag', 'what plays are reviewed automatically'],
  'A head coach throws the red flag to <b>challenge</b> a call: 2 per game, plus a 3rd if both are successful, and he needs a timeout left. '
  'Scoring plays, turnovers and every play in the final two minutes of each half and overtime are reviewed by the replay officials instead.'),
 ('kickoff', ['how do kickoffs work', 'what is the dynamic kickoff', 'where is a touchback on a kickoff', 'new kickoff rule', 'what is a touchback'],
  'Since 2024 the NFL uses the <b>dynamic kickoff</b>: the kicker kicks from his 35, the other players line up near midfield and cannot move until the ball lands or is touched. '
  'A kick into the end zone that is not returned is a <b>touchback</b> to the receiving team\'s <b>35-yard line</b> (since 2025); one that lands short of the landing zone (inside the 20) comes out to the 40. A punt touchback comes out to the 20.'),
 ('pat', ['where is the extra point kicked from', 'how long is an extra point', 'where is a two point conversion from'],
  'The <b>extra point</b> is snapped from the 15-yard line (about a 33-yard kick). A <b>two-point try</b> is snapped from the 2-yard line.'),
 ('safety', ['what is a safety', 'how do you get a safety', 'what happens after a safety', 'how much is a safety worth', 'safety points'],
  'A <b>safety</b> happens when the offense is tackled (or fumbles out, or commits certain penalties) in its own end zone. The defense gets <b>2 points and the ball</b>: the team that gave up the safety kicks it away from its own 20.'),
 ('fair_catch', ['what is a fair catch', 'how does a fair catch work'],
  'A returner waves an arm to call a <b>fair catch</b>: he cannot be hit, cannot run with the ball, and his team starts where he caught it.'),
 ('turnovers', ['what is a turnover', 'what is a fumble', 'what is an interception', 'what is a pick six', 'what is a strip sack'],
  'A <b>turnover</b> gives the ball to the other team: an <b>interception</b> (a defender catches a pass), a <b>lost fumble</b> (the ball carrier drops it and the defense recovers) or a turnover on downs. '
  'A <b>pick-six</b> is an interception returned for a touchdown; a <b>strip-sack</b> is a sack where the defender knocks the ball loose.'),
 ('sack', ['what is a sack', 'what counts as a sack'],
  'A <b>sack</b> is when the quarterback is tackled behind the line of scrimmage while trying to pass. It counts as a loss of yards on that down.'),
 ('penalties_common', ['what is holding', 'what is pass interference', 'what is a false start', 'what is offsides', 'what is roughing the passer',
                       'what is intentional grounding', 'common nfl penalties', 'what is encroachment'],
  '<b>False start</b> (offense moves before the snap): 5 yards. <b>Offside / encroachment / neutral zone infraction</b> (defense): 5 yards. '
  '<b>Offensive holding</b>: 10 yards; <b>defensive holding</b>: 5 yards and a first down. <b>Defensive pass interference</b>: ball at the spot of the foul and a first down (at the 1 if it is in the end zone); offensive pass interference: 10 yards. '
  '<b>Roughing the passer</b>: 15 yards and a first down. <b>Intentional grounding</b>: loss of down and 10 yards or the spot of the foul (a safety if it happens in the end zone).'),
 ('red_zone', ['what is the red zone', 'what does red zone mean', 'what is the goal line'],
  'The <b>red zone</b> is inside the opponent\'s 20-yard line, where most touchdowns are scored. Inside the 5 is often called the <b>goal line</b>. BFF counts red-zone targets and carries as part of a player\'s usage.'),
 ('positions', ['what positions are there in football', 'what does each position do', 'what is a tight end', 'what is a running back', 'what is a wide receiver',
                'what is a linebacker', 'what is a cornerback', 'what is a safety position', 'what is a fullback'],
  'Offense: <b>quarterback</b> (throws, runs the offense), <b>running back</b> (runs and catches short passes), <b>fullback</b> (lead blocker), <b>wide receivers</b> (catch passes), <b>tight end</b> (blocks and catches), and five <b>offensive linemen</b> (center, two guards, two tackles). '
  'Defense: <b>defensive linemen</b> (rush the passer, stop the run), <b>linebackers</b>, <b>cornerbacks</b> (cover receivers) and <b>safeties</b> (deep coverage). Special teams: kicker, punter, long snapper and returners.'),
 ('coverage', ['what is cover 2', 'what is cover 3', 'man vs zone coverage', 'what is a blitz', 'what is nickel defense', 'what is dime defense'],
  'In <b>man</b> coverage each defender follows one receiver; in <b>zone</b> each covers an area. <b>Cover 2</b> splits the deep field between two safeties; <b>Cover 3</b> splits it into thirds. '
  'A <b>blitz</b> sends extra rushers (often a linebacker or defensive back). <b>Nickel</b> uses a fifth defensive back, <b>dime</b> a sixth.'),
 ('plays', ['what is play action', 'what is an rpo', 'what is a screen pass', 'what is a draw play', 'what is a hail mary', 'what is an onside kick', 'what is a flea flicker', 'what is a trick play'],
  '<b>Play-action</b>: fake a handoff, then pass. <b>RPO</b> (run-pass option): the QB reads a defender after the snap and hands off or throws. <b>Screen</b>: a short pass behind blockers. <b>Draw</b>: looks like a pass, then a delayed run. '
  '<b>Hail Mary</b>: a long desperation pass to the end zone. <b>Onside kick</b>: a short kickoff the kicking team tries to recover. <b>Flea flicker</b>: a handoff, a pitch back to the QB, then a deep pass.'),
 # ---------------- season and league
 ('season_length', ['how many games in the nfl season', 'how many weeks in the nfl season', 'how long is the nfl season', 'how many regular season games'],
  'The NFL regular season is <b>17 games over 18 weeks</b> (each team has one bye week), 272 games in all. Most fantasy leagues end in week 17.'),
 ('playoffs', ['how do the nfl playoffs work', 'how many teams make the playoffs', 'what is a wild card', 'who gets a bye in the playoffs', 'playoff format'],
  '<b>14 teams</b> make the playoffs, 7 per conference: the 4 division winners (seeds 1-4) and 3 wild cards (5-7). Only the <b>No. 1 seed</b> in each conference gets a bye. '
  'Rounds: Wild Card, Divisional, Conference Championships, then the Super Bowl. Higher seeds host until the Super Bowl, which is at a pre-chosen stadium.'),
 ('teams_count', ['how many nfl teams are there', 'how many teams in the nfl', 'what are the nfl divisions', 'how many divisions in the nfl'],
  'The NFL has <b>32 teams</b> in two conferences (AFC and NFC), each with four divisions of four: '
  'AFC East (Bills, Dolphins, Patriots, Jets), AFC North (Ravens, Bengals, Browns, Steelers), AFC South (Texans, Colts, Jaguars, Titans), AFC West (Broncos, Chiefs, Raiders, Chargers), '
  'NFC East (Cowboys, Giants, Eagles, Commanders), NFC North (Bears, Lions, Packers, Vikings), NFC South (Falcons, Panthers, Saints, Buccaneers), NFC West (Cardinals, Rams, 49ers, Seahawks).'),
 ('dates_2026', ['when is the super bowl', 'where is the super bowl this year', 'when is the trade deadline', 'when do the playoffs start', 'when is super bowl lxi'],
  '2026 season dates (NFL.com): the <b>trade deadline</b> is <b>Nov. 10</b> at 4 p.m. ET; Week 18 is Jan. 9-10; Wild Card Weekend Jan. 16-18; Divisional round Jan. 23-24; Conference Championships Jan. 31; '
  '<b>Super Bowl LXI</b> is <b>Feb. 14, 2027</b> at SoFi Stadium in Inglewood, California.', 2026),
 ('most_sb', ['which team has the most super bowl wins', 'most super bowl titles', 'who has won the most super bowls'],
  'The <b>New England Patriots</b> and <b>Pittsburgh Steelers</b> have the most Super Bowl wins, <b>6 each</b> (through Super Bowl LX).', 2026),
 ('draft', ['how does the nfl draft work', 'how many rounds in the nfl draft', 'who picks first in the draft', 'what are compensatory picks'],
  'The NFL Draft has <b>7 rounds</b>. Teams that missed the playoffs pick first, worst record first; playoff teams follow in order of how far they went, and the Super Bowl champion picks last. '
  'Extra <b>compensatory picks</b> (rounds 3-7) go to teams that lost more free agents than they signed. Picks can be traded.'),
 ('rookie_contracts', ['how long are rookie contracts', 'what is the fifth year option', 'what is a franchise tag'],
  'Drafted rookies sign <b>4-year</b> contracts; first-round picks also carry a <b>fifth-year option</b> the team can pick up. The <b>franchise tag</b> lets a team keep a player about to become a free agent on a one-year deal at a set (high) salary.'),
 ('rosters', ['how many players on an nfl roster', 'how big is a practice squad', 'how many players are on a practice squad', 'practice squad size', 'nfl roster size', '53 man roster', 'how many players dress for a game', 'what is the emergency third quarterback'],
  'An NFL team carries <b>53 players</b>, plus a <b>16-player practice squad</b>. On game day up to 48 can be active (if 8 are offensive linemen), and a team can also name an <b>emergency third quarterback</b> who can only play if the other two are out.'),
 ('ir_rules', ['how does injured reserve work in the nfl', 'how long is ir', 'what does designated to return mean', 'what is pup', 'what is nfi', 'can a player come back from ir'],
  'A player put on <b>injured reserve</b> must miss at least <b>4 games</b>; each team can bring back up to 8 players a season with return designations. <b>PUP</b> (physically unable to perform) is for football injuries that carry over from before the season; <b>NFI</b> is for injuries or illness not from football. '
  'BFF projects 0 points while a player is on any of these lists and starts projecting him again in his expected return week.'),
 ('injury_report', ['what does questionable mean', 'what does doubtful mean', 'what does out mean', 'how does the injury report work', 'what does dnp mean', 'what does limited practice mean'],
  'On the official injury report, <b>Out</b> means he will not play, <b>Doubtful</b> means unlikely, and <b>Questionable</b> means uncertain. Practice reports say <b>DNP</b> (did not practice), <b>Limited</b> or <b>Full</b>. '
  'In 2021-2025 data, Out players played 0.1% of the time, Doubtful 0.4% and Questionable 61%, which is why BFF projects Out and Doubtful players for 0.'),
 ('prime_time', ['what is thursday night football', 'what is monday night football', 'what is sunday night football', 'what is tnf', 'what is snf', 'what is mnf'],
  '<b>Thursday Night Football</b>, <b>Sunday Night Football</b> and <b>Monday Night Football</b> are the stand-alone prime-time games each week. In fantasy, players in the Thursday game lock first, so set those lineups early.'),
 ('hall_of_fame', ['where is the pro football hall of fame', 'what is the hall of fame'],
  'The <b>Pro Football Hall of Fame</b> is in <b>Canton, Ohio</b>. Players become eligible five years after they retire.'),
 ('records_career', ['who has the most career passing yards', 'who has the most rushing yards ever', 'who has the most receiving yards ever', 'nfl career records', 'who has the most touchdowns ever', 'how many touchdowns did jerry rice have', 'jerry rice career stats',
                     'how many rushing yards did emmitt smith have', 'how many passing yards did tom brady have', 'who is the greatest player of all time', 'who is the goat',
                     'best fantasy player of all time', 'best player ever'],
  'Career records: passing yards <b>Tom Brady</b> (89,214), rushing yards <b>Emmitt Smith</b> (18,355), receiving yards and total touchdowns <b>Jerry Rice</b> (22,895 yards, 208 touchdowns).'),
 ('records_season', ['single season receiving record', 'most receiving yards in a season', 'most rushing yards in a season', 'most passing yards in a season', 'nfl single season records'],
  'Single-season records (through 2025): passing yards <b>Peyton Manning</b> 5,477 (2013), rushing yards <b>Eric Dickerson</b> 2,105 (1984), receiving yards <b>Calvin Johnson</b> 1,964 (2012).', 2026),
 # ---------------- fantasy terms
 ('ppr', ['what is ppr', 'what is half ppr', 'what is standard scoring', 'how does fantasy scoring work', 'point per reception'],
  '<b>PPR</b> gives 1 point per catch, <b>half PPR</b> 0.5 and <b>standard</b> 0. Most leagues also give 0.1 per rushing or receiving yard, 6 per rushing or receiving touchdown, 0.04 per passing yard (1 per 25), 4 per passing touchdown and -2 per interception or fumble lost. '
  'Pick your format with the Scoring menu and BFF re-scores everything.'),
 ('flex', ['what is a flex', 'who should i play at flex', 'what is a flex spot'],
  'A <b>flex</b> spot can hold a running back, wide receiver or tight end. Start whoever projects highest among your non-starters.'),
 ('superflex', ['what is superflex', 'what is a superflex league', 'should i start two quarterbacks'],
  '<b>Superflex</b>: a flex spot that can also hold a quarterback. Quarterbacks score the most, so most teams start two and they are worth far more (set SF to 1 in BFF and values adjust).'),
 ('handcuff', ['what is a handcuff', 'should i draft handcuffs'],
  'A <b>handcuff</b> is the backup to a starting running back: if the starter gets hurt, the backup inherits much of his work. Handcuffs matter most for backs who get nearly all of their team\'s carries.'),
 ('faab_waivers', ['what is faab', 'how do waivers work', 'what is waiver priority', 'how much faab should i bid', 'how does the waiver wire work', 'what is the waiver wire', 'how do waiver claims work', 'when do waivers clear', 'what is a free agent in fantasy', 'how does faab work'],
  'On the <b>waiver wire</b>, dropped and unrostered players can be claimed. With rolling priority, the team that claims moves to the back of the line; with <b>FAAB</b> (free agent acquisition budget), each team bids from a season budget and the highest bid wins.'),
 ('bye_week', ['what is a bye week', 'what happens on a bye'],
  'A <b>bye week</b> is the one week each team does not play; its players score 0 that week, so have a replacement ready.'),
 ('dst_kicker', ['how do defenses score in fantasy', 'how do kickers score in fantasy', 'should i draft a kicker', 'what is dst', 'when should i draft a defense'],
  '<b>D/ST</b> scores for sacks, interceptions, fumble recoveries, defensive and return touchdowns, safeties and few points allowed. <b>Kickers</b> usually get 3 for a field goal (more for long ones) and 1 per extra point. '
  'Both swing a lot week to week, so most managers draft them last and <b>stream</b> them by matchup. BFF does not rank them.'),
 ('league_types', ['what is dynasty', 'what is a keeper league', 'what is best ball', 'what is redraft', 'what is a guillotine league'],
  '<b>Redraft</b>: a fresh draft every season (what BFF values are built for). <b>Keeper</b>: each team keeps a few players for next season. <b>Dynasty</b>: you keep your whole roster year to year, so young players are worth more. '
  '<b>Best ball</b>: no lineup setting; your top scorers count automatically.'),
 ('adp', ['what is adp', 'what is average draft position'],
  '<b>ADP</b> (average draft position) is where a player usually goes in drafts. BFF\'s draft guide uses the FantasyPros consensus as its guide to where players go.'),
 ('draft_strategy', ['what is zero rb', 'what is hero rb', 'what is robust rb', 'what is the best draft strategy', 'should i draft a qb early'],
  '<b>Zero RB</b> waits on running backs and loads up on receivers early; <b>Hero RB</b> takes one elite back early then waits; <b>Robust RB</b> takes several backs early. '
  'In one-quarterback leagues, waiting on a quarterback is usually fine because many score similarly; in superflex take two early. Try strategies against AI teams in the Mock draft.'),
 ('stack_stream', ['what is a stack', 'what is streaming', 'should i stack my qb', 'what does streaming a defense mean'],
  'A <b>stack</b> pairs a quarterback with his own receivers, so a big passing day counts twice. <b>Streaming</b> means picking up a different player each week (often a QB, TE, kicker or defense) for the best matchup.'),
 ('boom_bust', ['what is a boom', 'what is a bust', 'what is a floor', 'what is a ceiling', 'what does high floor mean', 'what does upside mean'],
  'A player\'s <b>floor</b> is a bad-but-realistic week (BFF uses the 10th percentile) and his <b>ceiling</b> a great one (90th). <b>Boom</b> and <b>bust</b> are the chances of a big week or a dud. '
  'Favored? Lean on floor. Underdog? Chase ceiling.'),
 ('sleeper_term', ['what is a sleeper', 'what does sleeper mean in fantasy'],
  'A <b>sleeper</b> is a player who usually ranks outside the starter tier but should score like a starter, this week or over the season. BFF\'s cheat sheet lists weekly sleepers.'),
 ('buy_sell_term', ['what is buy low', 'what is sell high', 'what does regression mean in fantasy', 'what is positive regression'],
  '<b>Buy low</b>: a player scoring well below what his usage is usually worth (bad luck tends to even out). <b>Sell high</b>: scoring well above his usage, usually from touchdowns or long plays that rarely repeat. '
  'That evening-out is <b>regression to the mean</b>.'),
 ('usage_terms', ['what is target share', 'what is snap share', 'what is air yards', 'what is adot', 'what is wopr', 'what is yards per route run', 'what is racr',
                  'what is expected fantasy points', 'what is xfp', 'what does usage mean', 'what is a target', 'what does targets mean', 'what are targets', 'what counts as a target'],
  'A <b>target</b> is a pass thrown to a player, caught or not. <b>Target share</b>: his share of the team\'s targets. <b>Snap share</b>: share of offensive plays he is on the field. <b>Air yards</b>: how far past the line of scrimmage his targets travel; <b>aDOT</b> is their average. '
  '<b>WOPR</b> = 1.5 × target share + 0.7 × air-yards share. <b>Yards per route run</b> = receiving yards ÷ routes. <b>Expected fantasy points (xFP)</b>: what his targets and carries usually score given depth and field position.'),
 ('advanced_terms', ['what is epa', 'what is cpoe', 'what is success rate', 'what is pass rate over expected', 'what is proe', 'what is dvoa'],
  '<b>EPA</b> (expected points added): how much a play changed the expected points of the drive, based on down, distance and field position. <b>CPOE</b>: completion % above what the throws\' difficulty predicts. '
  '<b>Success rate</b>: share of plays with positive EPA. <b>PROE</b> (pass rate over expected): how much more a team passes than the situation predicts; BFF uses it for team pace and play calling.'),
 ('vorp_term', ['what is vorp', 'what is value over replacement', 'what is replacement level'],
  '<b>VORP</b> (value over replacement player) is the points a player should score above the best player at his position likely available on waivers. It makes up 15% of BFF value; the rest is points above the best player who would not start in your league.'),
 ('vulture_committee', ['what is a vulture', 'what is a committee backfield', 'what is a rbbc', 'what is garbage time', 'what is game script'],
  'A <b>vulture</b> steals short touchdowns from the main back (often a big back or the QB). A <b>committee</b> splits carries between backs. <b>Garbage time</b> is late in a lopsided game when stats pile up against soft defense. '
  '<b>Game script</b>: teams that lead run more; teams that trail throw more.'),
 ('ir_slot', ['what is an ir slot', 'can i put a questionable player on ir', 'what is the trade deadline in fantasy'],
  'An <b>IR slot</b> in fantasy holds a player your league platform lists as injured (rules vary: some allow Out, some only IR) without using a bench spot. Fantasy trade deadlines are set by each league, often around week 10-12.'),
 ('fantasy_playoffs', ['when are the fantasy playoffs', 'what weeks are fantasy playoffs', 'how many teams make fantasy playoffs'],
  'Most leagues play the <b>fantasy playoffs in weeks 15-17</b>, with 4 or 6 of 10-12 teams making it. BFF\'s schedules show each player\'s matchups for those weeks.'),
 # ---------------- betting terms
 ('betting_terms', ['what is a spread', 'what is a moneyline', 'what is an over under', 'what does -110 mean', 'what is the vig', 'what does cover the spread mean', 'what is an implied total'],
  'The <b>spread</b> is the favorite\'s expected margin: a 3-point favorite (-3) must win by more than 3 to <b>cover</b>. The <b>moneyline</b> is a bet on who wins outright. The <b>over/under</b> (total) is the expected combined score. '
  '<b>-110</b> means you risk 110 to win 100; the extra is the <b>vig</b>. A team\'s <b>implied total</b> = total ÷ 2 + spread ÷ 2 for the favorite (minus for the underdog); BFF uses it in every projection. For entertainment, 21+ where legal.'),
 ('parlay_term', ['what is a parlay', 'what is a same game parlay', 'what is a prop bet', 'what is a player prop', 'what is an anytime touchdown bet'],
  'A <b>parlay</b> combines bets: all legs must win, and the payout multiplies. A <b>same-game parlay</b> takes legs from one game. A <b>player prop</b> is a bet on a player\'s stat, like over 64.5 receiving yards or an anytime touchdown. '
  'BFF predicts the lines and picks only where its projection disagrees enough. For entertainment, 21+ where legal.'),
 ('special_teams', ['what does a long snapper do', 'what does a punter do', 'what is special teams', 'what does a kicker do', 'what is a returner', 'what is a holder'],
  '<b>Special teams</b> are on the field for kicks: the <b>kicker</b> (field goals, extra points, kickoffs), the <b>punter</b>, the <b>long snapper</b> (snaps the ball 7-8 yards back to the holder or about 15 to the punter), the <b>holder</b> (often the punter) and the <b>returners</b>.'),
 ('eligible_receivers', ['can a quarterback catch a pass', 'can an offensive lineman catch a pass', 'who is an eligible receiver', 'what is an eligible receiver', 'can a qb catch a touchdown', 'what is reporting as eligible'],
  'Only <b>eligible receivers</b> may catch a forward pass: the two players on each end of the line and the backs (players at least a yard behind the line). Linemen are ineligible unless they report to the referee as eligible. A quarterback who takes the snap directly from under center is ineligible, but one lined up as a back, such as in the shotgun, can catch a pass: Nick Foles caught a touchdown on the "Philly Special" in Super Bowl LII.'),
 ('win_league', ['how do i win my fantasy league', 'tips to win fantasy football', 'how to get better at fantasy football', 'fantasy football strategy tips', 'how do i make the playoffs in fantasy'],
  'Start your best projected lineup every week, work the waiver wire early in the week for players whose role just grew, trade for players whose usage is better than their points (buy low) and away from the reverse, keep a backup for your most important running back, and check your players\' matchups for the fantasy playoffs (weeks 15-17) before the trade deadline.'),
 ('fantasy_scoring', ['how many points does a passing td count in ppr', 'how many points is a passing touchdown in fantasy', 'how does fantasy scoring work', 'how many points per rushing yard',
                       'how many points is an interception in fantasy', 'how many points for a reception in ppr', 'what are the default fantasy scoring settings', 'how many points is a fumble in fantasy'],
  'Typical fantasy scoring: a <b>passing touchdown is 4 points</b> (6 in some leagues), 1 point per 25 passing yards, an interception -1 or -2 depending on the site; a <b>rushing or receiving touchdown is 6</b>, 1 point per 10 rushing or receiving yards, a lost fumble -2, a two-point conversion 2. Receptions add 1 point in <b>PPR</b>, 0.5 in half PPR and 0 in standard; that is the only difference between the three.'),
 # ---------------- the analyst's playbook (Nov 2026): how to make the calls, for BFF Brain and BFF's AI
 ('start_sit_how', ['how do i decide who to start', 'how to make start sit decisions', 'start sit advice', 'tips for start sit', 'how do you pick between two players',
                    'tiebreakers for start sit', 'should i start the better matchup or the better player'],
  'Start the player BFF projects higher unless something changed after the projection: a new injury report, a role change, or a teammate ruled out. '
  'BFF\'s weekly projection already includes the Vegas implied team total, home field, rest, the opposing defense against his position and his injury-report status, so do not count the matchup twice. '
  'When two players are within a point or two, break the tie by your week: if you expect to win, take the steadier one (lower bust chance); if you expect to lose, take the higher ceiling (boom chance).'),
 ('close_call', ['what counts as a close call', 'is a one point difference a lot', 'how accurate are weekly projections', 'how much do projections miss by', 'how often is the projection right'],
  'Weekly projections miss a lot: BFF\'s miss by about 4.5 PPR points per player on average (tested on 2023-2025 games it never saw), and the higher-ranked of two start/sit options outscores the other only about 63% of the time. '
  'So a gap of a point or two is close to a coin flip; a gap of 5 or more is a clear call.'),
 ('trade_how', ['how do i evaluate a trade', 'how to tell if a trade is fair', 'trade advice fantasy', 'should i accept a 2 for 1 trade', 'what is a 2 for 1 trade',
                'how do i win a trade', 'what makes a good trade'],
  'Judge a trade on the rest of the season, not one week: BFF\'s trade value and rest-of-season points are the starting point. Then check your lineup, because a trade only helps if the player you get would start for you. '
  'In a 2-for-1, the side getting the best player usually wins: lineup spots are limited, the extra player often sits on the bench, and the other team has to drop someone. '
  'Also weigh injuries, bye weeks and the fantasy playoff weeks (15-17 in most leagues).'),
 ('waiver_how', ['waiver wire strategy', 'how do i decide who to pick up', 'who should i add after an injury', 'a starter got hurt who do i pick up', 'who replaces an injured starter on waivers', 'how much faab should i bid', 'faab bidding strategy', 'when should i use my waiver priority', 'who to add after an injury'],
  'Chase role changes, not one big game: a back whose starter just got hurt, a receiver whose snaps and targets jumped. Steady usage keeps scoring; one long touchdown on low usage usually does not repeat. '
  'With FAAB, spend big on players who could start for you the rest of the season and little on one-week fill-ins (kickers, defenses, streaming quarterbacks). Save a high waiver priority for an injury replacement who becomes a starter.'),
 ('injury_timing', ['should i start a questionable player', 'what to do with a questionable player', 'when are inactives announced', 'game time decision fantasy', 'late game injury strategy'],
  'Teams announce their inactive players about <b>90 minutes before kickoff</b>. For a questionable player in a late game, put him in your flex spot if you can, so a player from an even later game can replace him if he sits. '
  'Doubtful players rarely play, and Out means he will not; never start either.'),
 ('vegas_fantasy', ['how do vegas odds affect fantasy', 'what is an implied team total in fantasy', 'does game script matter', 'should i start players in high scoring games',
                    'what does the over under mean for fantasy'],
  'Fantasy points come mostly from yards and touchdowns, so players on teams Vegas expects to score a lot (a high <b>implied team total</b>) get more chances. '
  'Big favorites tend to run more once they lead, which helps their running backs; teams expected to trail tend to throw more, which helps their quarterback and receivers. BFF builds the implied team total into every projection.'),
 ('weather', ['does weather matter in fantasy', 'should i bench players in the snow', 'how does wind affect football', 'does rain affect fantasy football', 'cold weather fantasy'],
  'Strong, steady wind is the weather that matters most: it hurts deep passing and long field goals. Rain and cold usually matter less than people expect, and domed stadiums are not affected. '
  'BFF\'s projections account for domes but not for weather forecasts, so check the forecast for windy outdoor games.'),
 ('usage_vs_points', ['what stats matter most in fantasy', 'are targets more important than touchdowns', 'why does usage matter', 'what predicts fantasy points', 'what is touchdown regression'],
  'Usage predicts future fantasy points better than past points: targets, carries, snaps and red-zone touches repeat from week to week, while touchdowns swing a lot. '
  'A player scoring far above what his usage is worth tends to cool off (sell high); one scoring below it tends to bounce back (buy low). BFF shows this as what his usage is worth a game.'),
 ('usage_benchmarks', ['what is a good target share', 'how many targets is good', 'what is a good snap share', 'how much usage does a running back need'],
  'Rough guide: a receiver earning about a quarter of his team\'s targets is getting elite usage, around 20% makes a solid starter, and under 15% is hard to trust. '
  'For running backs, playing most of the snaps and catching passes matters as much as carries, especially in PPR.'),
 ('rushing_qbs', ['why are rushing quarterbacks good in fantasy', 'do running quarterbacks score more fantasy points', 'are mobile quarterbacks better in fantasy'],
  'Rushing counts more than passing in most scoring: 1 point per 10 rushing yards against 1 per 25 passing yards, and 6 points for a rushing touchdown against 4 for a passing one. '
  'That is why quarterbacks who run are worth so much in fantasy.'),
 ('streaming_k_dst', ['how do i stream defenses', 'which defense should i pick up', 'how to pick a kicker', 'streaming kickers', 'best way to choose a defense each week'],
  'Stream defenses against offenses that allow sacks and turnovers, especially ones starting a backup quarterback, and when the opponent\'s implied team total is low. '
  'For kickers, look for teams with a high implied team total whose drives tend to stall in field-goal range, and indoor or calm-weather games. BFF projects both every week.'),
 ('playoff_prep', ['how to prepare for the fantasy playoffs', 'fantasy playoff schedule strategy', 'should i stash a handcuff for the playoffs', 'strength of schedule for fantasy playoffs'],
  'From mid-season on, look ahead to weeks 15-17: a handcuff for your top running back is cheap insurance, and an easier schedule in those weeks is worth a little in a trade. '
  'Use your league\'s trade deadline to fix your weakest starting spot.'),
 ('bye_plan', ['how to handle bye weeks', 'too many players on bye', 'bye week strategy', 'what do i do when my players are on bye'],
  'Check byes a week or two ahead. If several starters share a bye, add a fill-in early, before other teams do, or trade a bench player for a starter at that position. A player on bye scores 0, so never leave one in your lineup.'),
 ('aging', ['what age do running backs decline', 'how does age affect fantasy value', 'when do wide receivers peak', 'dynasty age strategy', 'how long do quarterbacks last'],
  'Running backs tend to decline earliest, often from their late 20s; receivers usually hold up a few years longer; quarterbacks can stay productive into their mid-30s. '
  'In dynasty, a younger player holds value longer, so two players with the same points this year are not worth the same. BFF\'s values are built for this season (redraft).'),
 ('dfs_basics', ['what is dfs', 'how does daily fantasy work', 'how do cash games work in dfs', 'what are cash games', 'dfs strategy', 'draftkings daily fantasy lineup tips', 'cash game vs gpp', 'what is a gpp', 'how do i build a dfs lineup', 'what is a dfs tournament'],
  '<b>Daily fantasy (DFS)</b>: a new lineup each slate under a salary cap. In <b>cash games</b> (50/50s, head-to-heads) roughly half the field wins, so pick steady, high-floor players. '
  'In <b>tournaments</b> (GPPs) only the top few percent win big, so you need upside: stacks (a quarterback with his receivers) and some players few others pick.'),
 ('odds_math', ['how do american odds work', 'how do betting odds work', 'what do the plus and minus numbers mean in betting', 'what does plus 200 mean in betting', 'what does minus 150 mean', 'what does +150 mean', 'what does -150 mean', 'how do i convert odds to a probability', 'what is implied probability', 'what are fair odds',
                'what is the break even percentage at -110'],
  '<b>Minus odds</b> (-150): risk 150 to win 100; the implied chance is 150 ÷ (150 + 100) = 60%. <b>Plus odds</b> (+150): risk 100 to win 150; the implied chance is 100 ÷ (150 + 100) = 40%. '
  'At -110 on both sides you must win 52.4% just to break even. <b>Fair odds</b> have no fee in them: BFF shows them next to its chances, and a bet has value only when your book pays more. For entertainment, 21+ where legal.'),
 ('responsible_betting', ['is sports betting a good way to make money', 'how much should i bet', 'help with a gambling problem', 'betting bankroll advice', 'how do i stop gambling'],
  'Bet only money you can afford to lose, set a budget before the week starts, and never chase losses: the fee in every price means most bettors lose over time. '
  'If betting stops being fun, the National Problem Gambling Helpline is 1-800-MY-RESET (1-800-697-3738), call or text, any time, or chat at 1800myreset.org. For entertainment, 21+ where legal.'),
 ('te_premium', ['what is te premium', 'tight end premium scoring', 'what is a te premium league'],
  '<b>TE premium</b> gives tight ends extra points per catch (often 0.5 more, so 1.5 per catch in PPR), which makes the top tight ends more valuable compared with receivers.'),
 ('keepers', ['how do keepers work', 'who should i keep', 'keeper league strategy', 'what does it cost to keep a player'],
  'In keeper leagues each team keeps a few players, usually at the cost of a draft pick (often the round he was drafted in). Keep the player whose value beats the pick it costs by the most: '
  'a breakout drafted late usually beats a star who costs a first-round pick.'),
 ('lineup_lock', ['when do lineups lock', 'can i change my lineup after games start', 'when do i need to set my lineup', 'thursday night lineup lock'],
  'On most platforms each player locks when his own game kicks off, so you can still change players in later games. Set Thursday and early Sunday players first, and check inactives about 90 minutes before each kickoff.'),
 ('scoring_strategy', ['how does ppr change strategy', 'ppr vs standard strategy', 'are receivers better in ppr', 'who is better in standard scoring'],
  'PPR adds a point per catch, so receivers and pass-catching running backs gain the most; in standard scoring, yards and touchdowns matter more, which favors goal-line backs. Half PPR sits in between. '
  'BFF switches every projection to the scoring you pick.'),
 ('trade_timing', ['when should i trade', 'trade deadline strategy fantasy', 'when to sell high', 'when to buy low'],
  'Buy before the breakout: rising usage, an easier schedule ahead, or a teammate\'s injury. Sell right after a big game, especially one built on long or lucky touchdowns. '
  'Check your league\'s trade deadline; fantasy deadlines are set by each league, often around weeks 10-12.'),
 ('bff_ai', ['what ai does ask bff use', 'is ask bff chatgpt', 'how does bff ai work', 'does my question leave my device', 'how big is the ai download', 'what model does bff use', 'is the ai private',
             'how do i turn on the ai', 'how do i download bffs ai', 'how do i remove the ai from my device', 'why cant i use the ai on my phone'],
  '<b>BFF\'s AI</b> is an open model (Qwen3.5, Apache 2.0) that runs in your own browser with WebGPU through WebLLM: it downloads once (about 2.4 GB on a computer, 1.1 GB on a phone, 5.1 GB for the largest size) and then answers on your device, so your questions never leave it. '
  'It writes from BFF\'s own numbers and every number in a reply is checked against BFF\'s data. Tap <b>Download BFF\'s AI</b> in Ask BFF to get it; <b>AI settings</b> (under the chat) change its size or remove it. '
  'It needs a browser with WebGPU (Chrome or Edge on a computer, Chrome on Android, Safari 26 and later); where a device cannot run it, Ask BFF gives its quick answers instead.'),
]
