"""Refresh live.json: this week's games, final scores, box scores and scoring plays, from free public data only (the
nflverse schedule and nflverse's official stats and play-by-play, CC BY 4.0). Scores and box scores appear after each game
is over, as soon as nflverse publishes it (usually within hours; play-by-play and player stats by the next morning). There
is no live in-game feed: BFF uses no other site's scores.

  python live_update.py      (the score job runs it every 30 minutes; a few seconds when nothing changed)
"""
import io, json, os, datetime, urllib.request
from zoneinfo import ZoneInfo
import pandas as pd

B = "https://github.com/nflverse/nflverse-data/releases/download/"
GAMES = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
ET = ZoneInfo("America/New_York")
NOW = datetime.datetime.fromisoformat(os.environ["BFF_NOW"]) if os.environ.get("BFF_NOW") else datetime.datetime.now(datetime.timezone.utc)


def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "bff-site"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()


def _i(v):
    try: return 0 if v is None or v != v else int(v)
    except Exception: return 0


def kick_of(g):
    """kickoff as an ISO time (Eastern time in the schedule), or None"""
    try: return datetime.datetime.strptime(f"{g.gameday} {g.gametime}", "%Y-%m-%d %H:%M").replace(tzinfo=ET).isoformat()
    except Exception: return None


def this_week(gm):
    """the season and week the scoreboard shows: the earliest week with a game not yet final (the latest week once all are)"""
    reg = gm[gm.game_type == "REG"]
    S = int(reg.season.max()); G = reg[reg.season == S]
    if not G.home_score.isna().any():
        if G.empty: return S - 1, 18
        return S, int(G.week.max())
    return S, int(G[G.home_score.isna()].week.min())


BOXV = 2   # box-score format; a saved box score in an older format is rebuilt (2: kicking and D/ST numbers added)
OFF = {"QB", "RB", "FB", "WR", "TE", "T", "G", "C", "OL", "OT", "OG", "LS", "K", "P"}   # positions whose fumble-recovery TDs are not the defense's


def _col(R, c):
    """a stats column summed (0 when nflverse does not have it)"""
    return sum(_i(v) for v in R[c]) if c in R.columns else 0


def _made(v):
    """made field goals' distances from nflverse's list ('51;43')"""
    if not isinstance(v, str): return []
    out = []
    for t in v.split(";"):
        try: out.append(int(float(t)))
        except ValueError: pass
    return out


def dst_lines(rows):
    """each team's D/ST numbers from nflverse player stats, scored the way ff_kdst.py scores them from play-by-play
    (checked on 2026 weeks 1-6, 186 team games: sacks, interceptions, fumble recoveries, touchdowns and blocked kicks match
    in all 186, safeties in 184 and the D/ST's points in 184; ff_kdst.py's official numbers replace these on its next run)"""
    out = {}; teams = list(rows.team.dropna().unique())
    for t in teams:
        R = rows[rows.team == t]; O = rows[rows.team != t]
        if not len(O): continue
        frtd = _col(R[~R.position.isin(OFF)], "fumble_recovery_tds") if "position" in R.columns else 0
        out[t] = {"sk": _col(O, "sacks_suffered"), "int": _col(O, "passing_interceptions"), "fr": _col(R, "fumble_recovery_opp"),
                  "td": _col(R, "def_tds") + _col(R, "special_teams_tds") + frtd, "dtd": _col(R, "def_tds") + frtd,
                  "sf": _col(R, "def_safeties"), "blk": _col(R, "def_punt_blocks") + _col(R, "def_fg_blocks") + _col(R, "def_pat_blocks")}
    return out


def box_from_stats(rows):
    """box score for a finished game, from nflverse player stats: fantasy lines, stat tables per team (kicking too), team
    totals, and each team's D/ST numbers (key dst)"""
    players = []; cats = {}; ts = {}
    for t, R in rows.groupby("team"):
        P_ = [x for x in R.itertuples() if (_i(x.attempts) or _i(x.carries) or _i(x.targets))]
        for x in P_:
            players.append({"n": x.player_display_name, "t": t, "p": x.position, "pc": _i(x.completions), "pa": _i(x.attempts), "py": _i(x.passing_yards), "ptd": _i(x.passing_tds),
                            "int": _i(x.passing_interceptions), "ra": _i(x.carries), "ry": _i(x.rushing_yards), "rtd": _i(x.rushing_tds), "rec": _i(x.receptions), "tg": _i(x.targets),
                            "ty": _i(x.receiving_yards), "rectd": _i(x.receiving_tds),
                            "fl": _i(getattr(x, "rushing_fumbles_lost", 0)) + _i(getattr(x, "receiving_fumbles_lost", 0)) + _i(getattr(x, "sack_fumbles_lost", 0))})
        C = []
        pa = [x for x in P_ if _i(x.attempts)]
        if pa: C.append({"n": "passing", "t": f"{t} Passing", "l": ["C/ATT", "YDS", "TD", "INT", "SACKS"], "r": [[x.player_display_name, f"{_i(x.completions)}/{_i(x.attempts)}", str(_i(x.passing_yards)), str(_i(x.passing_tds)), str(_i(x.passing_interceptions)), f"{_i(getattr(x, 'sacks_suffered', 0))}-{_i(getattr(x, 'sack_yards_lost', 0))}"] for x in pa], "tot": []})
        ru = sorted([x for x in P_ if _i(x.carries)], key=lambda x: -_i(x.rushing_yards))
        if ru: C.append({"n": "rushing", "t": f"{t} Rushing", "l": ["CAR", "YDS", "AVG", "TD"], "r": [[x.player_display_name, str(_i(x.carries)), str(_i(x.rushing_yards)), f"{_i(x.rushing_yards) / max(1, _i(x.carries)):.1f}", str(_i(x.rushing_tds))] for x in ru], "tot": []})
        rc = sorted([x for x in P_ if _i(x.targets)], key=lambda x: -_i(x.receiving_yards))
        if rc: C.append({"n": "receiving", "t": f"{t} Receiving", "l": ["REC", "TGTS", "YDS", "AVG", "TD"], "r": [[x.player_display_name, str(_i(x.receptions)), str(_i(x.targets)), str(_i(x.receiving_yards)), f"{_i(x.receiving_yards) / max(1, _i(x.receptions)):.1f}", str(_i(x.receiving_tds))] for x in rc], "tot": []})
        fu = [p for p in players if p["t"] == t and p["fl"]]
        if fu: C.append({"n": "fumbles", "t": f"{t} Fumbles lost", "l": ["LOST"], "r": [[p["n"], str(p["fl"])] for p in fu], "tot": []})
        ki = [x for x in R.itertuples() if _i(getattr(x, "fg_att", 0)) or _i(getattr(x, "pat_att", 0))]
        if ki: C.append({"n": "kicking", "t": f"{t} Kicking", "l": ["FG", "XP", "LONG", "FG YDS"],
                         "r": [[x.player_display_name, f"{_i(getattr(x, 'fg_made', 0))}/{_i(getattr(x, 'fg_att', 0))}", f"{_i(getattr(x, 'pat_made', 0))}/{_i(getattr(x, 'pat_att', 0))}",
                                str(_i(getattr(x, "fg_long", 0)) or "-"), ", ".join(str(d) for d in _made(getattr(x, "fg_made_list", None)))] for x in ki], "tot": []})
        cats[t] = C
        py = sum(_i(x.passing_yards) for x in pa); ry = sum(_i(x.rushing_yards) for x in ru); to = sum(_i(x.passing_interceptions) for x in pa) + sum(p["fl"] for p in players if p["t"] == t)
        ts[t] = [["Passing yards", str(py)], ["Rushing yards", str(ry)], ["Total yards", str(py + ry)], ["Turnovers", str(to)]]
    return {"v": BOXV, "players": players, "cats": cats, "ts": ts, "dst": dst_lines(rows)}


RET = {"interception": "Interception", "fumble": "Fumble", "punt": "Punt", "kickoff": "Kickoff"}


def scoring(G, name):
    """scoring plays of one game from nflverse play-by-play: [quarter, clock, team, type, text, away score, home score], the
    text in the usual box-score style ('Amon-Ra St. Brown 12 Yd pass from Jared Goff (Jake Bates Kick)'), full names"""
    nm = lambda pid, short: name.get(pid) or (short if isinstance(short, str) else "")
    out = []; rows = G.sort_values("play_id").reset_index(drop=True)
    for i, x in rows.iterrows():
        txt = ty = None; tm = None
        if x.get("touchdown") == 1 and isinstance(x.get("td_team"), str):
            tm = x.td_team; yd = _i(x.get("yards_gained"))
            if x.get("pass_attempt") == 1 and x.get("complete_pass") == 1 and tm == x.get("posteam"):
                txt = f"{nm(x.get('receiver_player_id'), x.get('receiver_player_name'))} {yd} Yd pass from {nm(x.get('passer_player_id'), x.get('passer_player_name'))}"
            elif x.get("rush_attempt") == 1 and tm == x.get("posteam"):
                txt = f"{nm(x.get('rusher_player_id'), x.get('rusher_player_name'))} {yd} Yd Rush"
            else:
                kind = ("Interception" if x.get("interception") == 1 else "Punt" if x.get("play_type") == "punt" else "Kickoff" if x.get("play_type") == "kickoff"
                        else "Blocked Field Goal" if x.get("field_goal_result") == "blocked" else "Missed Field Goal" if x.get("play_type") == "field_goal" else "Fumble" if x.get("fumble") == 1 else None)
                ry = _i(x.get("return_yards")) or yd
                who = nm(x.get("td_player_id"), x.get("td_player_name"))
                txt = f"{who} {ry} Yd {kind} Return" if kind else f"{who} touchdown"
            ty = "TD"
            # the try after the touchdown: the next real play (timeouts and other non-plays in between are skipped)
            nx = None
            for j in range(i + 1, min(i + 6, len(rows))):
                y = rows.iloc[j]
                if y.get("extra_point_attempt") == 1 or y.get("two_point_attempt") == 1: nx = y; break
                if isinstance(y.get("play_type"), str) and y.get("play_type") != "no_play": break
            if nx is not None and nx.get("extra_point_attempt") == 1:
                txt += f" ({nm(nx.get('kicker_player_id'), nx.get('kicker_player_name'))} Kick)" if nx.get("extra_point_result") == "good" else f" ({nm(nx.get('kicker_player_id'), nx.get('kicker_player_name'))} PAT failed)"
                after = nx
            elif nx is not None and nx.get("two_point_attempt") == 1:
                txt += " (Two-Point Conversion)" if nx.get("two_point_conv_result") == "success" else " (Two-Point Pass Conversion Failed)" if nx.get("pass_attempt") == 1 else " (Two-Point Run Conversion Failed)"
                after = nx
            else: after = x
            sc = after
        elif x.get("field_goal_result") == "made":
            tm = x.get("posteam"); txt = f"{nm(x.get('kicker_player_id'), x.get('kicker_player_name'))} {_i(x.get('kick_distance'))} Yd Field Goal"; ty = "FG"; sc = x
        elif x.get("safety") == 1:
            tm = x.get("defteam"); txt = "Safety"; ty = "SF"; sc = x
        else: continue
        out.append([_i(x.get("qtr")), str(x.get("time") or ""), tm, ty, txt[:160], _i(sc.get("total_away_score")), _i(sc.get("total_home_score"))])
    return out


def line_scores(G):
    """points by quarter for [away, home] from play-by-play running scores"""
    if not len(G): return None
    a = []; h = []; pa = ph = 0
    for q in sorted(int(v) for v in G.qtr.dropna().unique()):
        Q = G[G.qtr == q]; ea = _i(Q.total_away_score.max()); eh = _i(Q.total_home_score.max())
        a.append(ea - pa); h.append(eh - ph); pa, ph = ea, eh
    return [a, h]


if __name__ == "__main__":
    old = json.load(open("live.json")) if os.path.exists("live.json") else {}
    try:
        gm = pd.read_csv(io.BytesIO(open(os.environ["BFF_GAMES_CSV"], "rb").read() if os.environ.get("BFF_GAMES_CSV") else fetch(GAMES)), low_memory=False)   # (BFF_GAMES_CSV: a local copy, for tests)
    except Exception as e:
        print("schedule unavailable, keeping the previous live.json:", e); raise SystemExit(0)
    SEASON, W = this_week(gm)
    GW = gm[(gm.season == SEASON) & (gm.week == W) & (gm.game_type == "REG")].sort_values(["gameday", "gametime"])
    GP = gm[(gm.season == SEASON) & (gm.week == W - 1) & (gm.game_type == "REG")].sort_values(["gameday", "gametime"])   # last week's (recaps)
    final = {g.game_id for g in pd.concat([GW, GP]).itertuples() if not pd.isna(g.home_score)}
    B_old = {k: v for k, v in (old.get("box") or {}).items() if isinstance(v, dict) and k in final and v.get("v") == BOXV}
    PB_old = {k: v for k, v in (old.get("pbp") or {}).items() if isinstance(v, dict) and k in final}
    LS_old = {g.get("id"): g.get("ls") for g in (old.get("games") or []) + (old.get("prev") or []) if g.get("ls")}
    need = [g for g in final if g not in B_old or g not in PB_old]
    ST = PBP = None
    if need:   # finished games without a box score or scoring plays yet: read nflverse's stats and play-by-play
        try:
            ST = pd.read_parquet(io.BytesIO(fetch(B + f"stats_player/stats_player_week_{SEASON}.parquet")))
            ST = ST[ST.season_type == "REG"] if "season_type" in ST.columns else ST
        except Exception as e: print("player stats unavailable (box scores wait for the next run):", str(e)[:120])
        try:
            PBP = pd.read_parquet(io.BytesIO(fetch(B + f"pbp/play_by_play_{SEASON}.parquet", 300)))
        except Exception as e: print("play-by-play unavailable (scoring plays wait for the next run):", str(e)[:120])
    name = {}
    if ST is not None: name = dict(zip(ST.player_id, ST.player_display_name))
    B_, PB_, LS_ = dict(B_old), dict(PB_old), dict(LS_old)
    for gid in need:
        if ST is not None and "game_id" in ST.columns and gid not in B_:
            R = ST[ST.game_id == gid]
            if len(R): B_[gid] = box_from_stats(R)
        if PBP is not None and gid not in PB_:
            G = PBP[PBP.game_id == gid]
            if len(G):
                sp = scoring(G, name); PB_[gid] = {"sp": [{"q": s[0], "c": s[1], "tm": s[2], "ty": s[3], "t": s[4], "as": s[5], "hs": s[6]} for s in sp]}
                LS_[gid] = line_scores(G)
    def card(g):
        kick = kick_of(g); done = g.game_id in final
        started = bool(kick and datetime.datetime.fromisoformat(kick) <= NOW)
        fav = None if pd.isna(g.spread_line) else (f"{g.home_team} -{abs(g.spread_line):g}" if g.spread_line > 0 else f"{g.away_team} -{abs(g.spread_line):g}" if g.spread_line < 0 else "Pick em")
        ot = (not pd.isna(getattr(g, "overtime", float("nan")))) and _i(getattr(g, "overtime", 0)) == 1
        return {"id": g.game_id, "wk": int(g.week), "home": g.home_team, "away": g.away_team, "hs": _i(g.home_score) if done else None, "as": _i(g.away_score) if done else None,
                "state": "post" if done else "pre", "started": bool(started and not done), "detail": ("Final/OT" if ot else "Final") if done else ("In progress" if started else None),
                "kick": kick, "venue": g.stadium if isinstance(g.stadium, str) else None, "odds": fav, "ou": None if pd.isna(g.total_line) else float(g.total_line),
                "ls": LS_.get(g.game_id) if done else None}
    games = [card(g) for g in GW.itertuples()]; prev = [card(g) for g in GP.itertuples()]
    new = {"src": "nflverse schedule and official stats (after each game)", "season": SEASON, "week": W, "games": games, "prev": prev, "box": B_, "pbp": PB_}
    if {k: old.get(k) for k in ("week", "games", "prev", "box", "pbp")} != {k: new[k] for k in ("week", "games", "prev", "box", "pbp")}:
        new["at"] = NOW.isoformat(timespec="seconds")
        json.dump(new, open("live.json", "w"), separators=(",", ":"))
        print(f"live.json updated: week {W}, {sum(g['state'] == 'post' for g in games)} of {len(games)} games final (and {sum(g['state'] == 'post' for g in prev)} from week {W - 1}), {len(B_)} box scores, {len(PB_)} with scoring plays")
    else: print("no change")
