"""Download the public data the pipeline needs (nflverse: CC BY 4.0) into this folder, and work out which season it is
(season.json), so nothing has to be changed by hand from one season to the next.

  season in progress  -> that season, phase "season"
  schedule out, no game played yet -> that season, phase "preseason"
  last season finished, next schedule not out yet -> next season, phase "preseason" (draft prep on last season's data)

The model learns from the 13 completed seasons before the current one (their features are cached after the first
build, so later runs download only the last five). Files for the current season are optional:
they do not exist until its first game. BFF uses no other site's projections or rankings: every number on the site comes
from this data and BFF's own model.

  python fetch_data.py                 download everything and write season.json
  python fetch_data.py --season-only   only work out the season from the saved schedule (no downloads)
  (testing: BFF_AS_OF=YYYY-MM-DD pretends it is that day; BFF_HIDE_SCHED=2027 pretends a schedule is not out yet)

Files of completed seasons do not change, so a copy younger than a week (BFF_KEEP_DAYS) is kept instead of downloaded
again; the update job keeps them between runs with a weekly cache. The current season, rosters, depth charts and
the player ID table are downloaded every run.
"""
import os, sys, csv, json, time, datetime, urllib.request

B = "https://github.com/nflverse/nflverse-data/releases/download/"
GAMES = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
AS_OF = os.environ.get("BFF_AS_OF")
TODAY = datetime.date.fromisoformat(AS_OF) if AS_OF else datetime.datetime.now(datetime.timezone.utc).date()


def get(name, url, tries=3):
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=300) as r: data = r.read()
            with open(name, "wb") as f: f.write(data)
            print("downloaded", name, flush=True); return True
        except Exception as e:
            last = e
    raise last


# ---- the schedule decides the season
ONLY = "--season-only" in sys.argv
if not ONLY:
    try: get("games.csv", GAMES)
    except Exception as e:
        if not os.path.exists("games.csv"): raise
        print("schedule download failed; using the saved copy:", e)
rows = [g for g in csv.DictReader(open("games.csv", newline="")) if g.get("game_type") == "REG"]
hide = {int(x) for x in os.environ.get("BFF_HIDE_SCHED", "").split(",") if x}          # testing only: pretend a schedule is not out
rows = [g for g in rows if int(g["season"]) not in hide]
if AS_OF:   # testing only: games on or after the pretend date have not been played yet
    for g in rows:
        if g["gameday"] and g["gameday"] >= AS_OF: g["home_score"] = g["away_score"] = ""
played = lambda g: g.get("home_score", "") not in ("", "NA")
L = max(int(g["season"]) for g in rows)
GL = [g for g in rows if int(g["season"]) == L]
if any(not played(g) for g in GL):
    SEASON, PHASE = L, ("season" if any(played(g) for g in GL) else "preseason")
else:
    SEASON, PHASE = L + 1, "preseason"
SCHED = any(int(g["season"]) == SEASON for g in rows)
json.dump({"season": SEASON, "phase": PHASE, "schedule": SCHED, "asof": TODAY.isoformat()}, open("season.json", "w"))
print(f"season {SEASON}, phase {PHASE}, schedule out: {SCHED}", flush=True)
if AS_OF or hide:   # keep the pretend schedule for the rest of the pipeline
    with open("games.csv", newline="") as f: allr = list(csv.DictReader(f))
    flds = list(allr[0].keys()); out = []
    for g in allr:
        if int(g["season"]) in hide: continue
        if AS_OF and g["gameday"] and g["gameday"] >= AS_OF:
            for k in ("home_score", "away_score", "result", "total", "overtime"):
                if k in g: g[k] = ""
        out.append(g)
    with open("games.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=flds); w.writeheader(); w.writerows(out)

if ONLY: sys.exit(0)
# ---- nflverse. The model (ff_feat.py, ff_model.py) learns from the 13 completed seasons before this one; their features are
# built once a season and cached (.cache), so after that only the latest seasons are needed here.
NH = 13; FIRST = SEASON - NH
WARM = all(os.path.exists(f".cache/f5_{SEASON}_{s}.parquet") for s in range(FIRST, SEASON)) and os.path.exists(f".cache/f5_{SEASON}_xfp.json")
LO = SEASON - 5 if WARM else FIRST - 1
print("model features:", "cached (downloading the last 5 seasons)" if WARM else f"building from {FIRST - 1} (downloading {SEASON - FIRST + 2} seasons)", flush=True)
need, opt = {}, {}
for y in range(LO, SEASON + 1):
    d = need if y < SEASON else opt
    d[f"pbp_{y}.parquet"] = B + f"pbp/play_by_play_{y}.parquet"
    d[f"stats_player_week_{y}.parquet"] = B + f"stats_player/stats_player_week_{y}.parquet"
    d[f"snap_counts_{y}.parquet"] = B + f"snap_counts/snap_counts_{y}.parquet"
    opt[f"roster_weekly_{y}.parquet"] = B + f"weekly_rosters/roster_weekly_{y}.parquet"   # teammate-injury signal (optional)
    opt[f"injuries_{y}.parquet"] = B + f"injuries/injuries_{y}.parquet"
for y in (SEASON, SEASON - 1):   # rosters (bios, rookies, moves): this season's, or last season's before it starts
    opt[f"roster_{y}.parquet"] = B + f"rosters/roster_{y}.parquet"
for y in range(SEASON - 2 if WARM else LO, SEASON + 1):   # depth charts (the model reads who starts)
    opt[f"depth_charts_{y}.parquet"] = B + f"depth_charts/depth_charts_{y}.parquet"
need["players.csv"] = B + "players/players.csv"               # nflverse player table: IDs (gsis, Pro Football Reference), bios, draft
skip = {f for f in os.environ.get("BFF_SKIP", "").split(",") if f}   # testing only: files to leave out
KEEP = float(os.environ.get("BFF_KEEP_DAYS", "7")) * 86400
DONE = {f"{k}_{y}.parquet" for y in range(LO, SEASON) for k in ("pbp", "stats_player_week", "snap_counts", "roster_weekly", "injuries", "depth_charts")}
def kept(name):
    """a completed season's file downloaded within the last week"""
    return name in DONE and os.path.exists(name) and os.path.getsize(name) > 1000 and time.time() - os.path.getmtime(name) < KEEP
K = [n for n in list(need) + list(opt) if n not in skip and kept(n)]
if K: print(f"kept {len(K)} completed-season files from the last week (they do not change):", ", ".join(sorted(K)), flush=True)
for name, url in need.items():
    if name not in skip and name not in K: get(name, url)
for name, url in opt.items():
    if name in skip or name in K: continue
    try: get(name, url, tries=2)
    except Exception as e: print(f"not available yet: {name} ({e}); continuing without it")

# ---- the player ID table the pipeline reads (player_ids.csv): nflverse's player table, the columns BFF uses
import pandas as pd
_COLS = {"gsis_id", "pfr_id", "display_name", "position", "latest_team", "height", "weight", "college_name", "birth_date", "draft_year", "rookie_season",
         "draft_round", "draft_pick", "status", "last_season"}
try:
    _P = pd.read_csv("players.csv", low_memory=False)
    if not _COLS <= set(_P.columns) or len(_P) < 1000: raise ValueError(f"players.csv looks wrong ({len(_P)} rows; missing {sorted(_COLS - set(_P.columns))[:4]})")
except Exception as e:   # a bad download: keep the last good player table (the run stops only when there is none)
    if not os.path.exists("player_ids.csv"): raise
    print("player table not updated this run, keeping the last one:", str(e)[:160], flush=True); _P = None
if _P is not None:
    _bd = pd.to_datetime(_P.birth_date, errors="coerce")
    pd.DataFrame({"gsis_id": _P.gsis_id, "pfr_id": _P.pfr_id, "name": _P.display_name, "position": _P.position, "team": _P.latest_team,
                  "height": _P.height, "weight": _P.weight, "college": _P.college_name, "birthdate": _P.birth_date,
                  "age": ((pd.Timestamp(TODAY) - _bd).dt.days / 365.25).round(1), "draft_year": _P.draft_year.fillna(_P.rookie_season), "draft_round": _P.draft_round,
                  "draft_ovr": _P.draft_pick, "status": _P.status, "last_season": _P.last_season}).to_csv("player_ids.csv", index=False)
    print("player_ids.csv:", len(_P), "players", flush=True)
