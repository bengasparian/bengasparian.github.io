"""One-off probe: fetch sample responses from candidate free data sources and save them (with headers) for inspection."""
import json, os, sys, urllib.request, time
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
E = "https://site.api.espn.com/apis/site/v2/sports/basketball"
W = "https://site.web.api.espn.com/apis/common/v3/sports/basketball"
C = "https://sports.core.api.espn.com/v2/sports/basketball/leagues"
T = {
 "nba_scoreboard": f"{E}/nba/scoreboard",
 "nba_teams": f"{E}/nba/teams",
 "nba_team": f"{E}/nba/teams/13",
 "nba_roster": f"{E}/nba/teams/13/roster",
 "nba_teamstats": f"{E}/nba/teams/13/statistics",
 "nba_schedule": f"{E}/nba/teams/13/schedule",
 "nba_news_team": f"{E}/nba/news?team=13",
 "nba_news": f"{E}/nba/news",
 "nba_injuries": f"{E}/nba/injuries",
 "nba_standings": "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings",
 "nba_athlete": f"{W}/nba/athletes/1966",
 "nba_athlete_stats": f"{W}/nba/athletes/1966/stats",
 "nba_athlete_overview": f"{W}/nba/athletes/1966/overview",
 "nba_athlete_gamelog": f"{W}/nba/athletes/1966/gamelog",
 "nba_powerindex": f"{C}/nba/seasons/2027/powerindex",
 "nba_draft": "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/draft",
 "cbb_scoreboard": f"{E}/mens-college-basketball/scoreboard",
 "cbb_teams": f"{E}/mens-college-basketball/teams?limit=500",
 "cbb_team": f"{E}/mens-college-basketball/teams/150",
 "cbb_roster": f"{E}/mens-college-basketball/teams/150/roster",
 "cbb_teamstats": f"{E}/mens-college-basketball/teams/150/statistics",
 "cbb_schedule": f"{E}/mens-college-basketball/teams/150/schedule",
 "cbb_rankings": f"{E}/mens-college-basketball/rankings",
 "cbb_standings": "https://site.api.espn.com/apis/v2/sports/basketball/mens-college-basketball/standings?group=2",
 "cbb_news": f"{E}/mens-college-basketball/news",
 "cbb_powerindex": f"{C}/mens-college-basketball/seasons/2027/powerindex",
 "torvik_players_2026": "https://barttorvik.com/getadvstats.php?year=2026&csv=1",
 "torvik_players_2027": "https://barttorvik.com/getadvstats.php?year=2027&csv=1",
 "torvik_teams_2027": "https://barttorvik.com/2027_team_results.json",
 "torvik_trank": "https://barttorvik.com/trank.php?year=2027&json=1",
 "r247_2026": "https://247sports.com/season/2026-basketball/compositerecruitrankings/",
 "r247_2025": "https://247sports.com/season/2025-basketball/compositerecruitrankings/?ViewPath=~%2FViews%2FSkyNet%2FPlayerSportRanking%2F_SimpleSetForSeason.ascx&Page=2",
 "tank_mock": "https://www.tankathon.com/mock_draft",
 "tank_board": "https://www.tankathon.com/big_board",
 "ncaa_net": "https://ncaa-api.henrygd.me/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings",
 "wiki_parse": "https://en.wikipedia.org/w/api.php?action=parse&page=LeBron_James&prop=wikitext&section=0&format=json&origin=*",
 "wiki_summary": "https://en.wikipedia.org/api/rest_v1/page/summary/Duke_Blue_Devils_men%27s_basketball",
 "nbadraftnet": "https://www.nbadraft.net/ranking/bigboard/",
}
summary = {}
for k, u in T.items():
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Origin": "https://bengasparian.github.io", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read(); hdr = dict(r.headers); code = r.status
    except urllib.error.HTTPError as e:
        body = e.read(); hdr = dict(e.headers); code = e.code
    except Exception as e:
        body = repr(e).encode(); hdr = {}; code = -1
    ext = "json" if body[:1] in (b"{", b"[") else "txt"
    with open(f"{OUT}/{k}.{ext}", "wb") as f: f.write(body[:2_500_000])
    summary[k] = {"url": u, "code": code, "bytes": len(body), "acao": hdr.get("Access-Control-Allow-Origin") or hdr.get("access-control-allow-origin"), "ctype": hdr.get("Content-Type")}
    time.sleep(0.5)
json.dump(summary, open(f"{OUT}/_summary.json", "w"), indent=1)
