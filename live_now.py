#!/usr/bin/env python3
"""Live scores during NFL games for BFF, from the BALLDONTLIE NFL API (free tier; its terms allow commercial use,
fantasy sports included, without attribution, as long as the data is not presented as official league data).

How it works (run by .github/workflows/live.yml; nothing to do once the key is set):
  1. The repository secret BFF_BDL_KEY holds a free BALLDONTLIE API key (app.balldontlie.io). Without it this script
     does nothing, and the site keeps its after-game scores from nflverse.
  2. The kickoff times come from the published page (index.html, the schedule BFF already shows). GitHub starts
     scheduled jobs late or skips them when it is busy (in Nov 2026 only about 1 in 12 of the every-30-minutes runs ran,
     and Thursday's game was picked up in the 4th quarter), so a run started up to 20 hours before a kickoff stays on
     and waits for it, and every job (data, scores, photos and this one's own timer) starts it when a game is that near.
  3. From 75 minutes before a kickoff, once a minute (the free tier allows 5 requests a minute), it asks BALLDONTLIE for
     the games of the day and writes live_now.json: each game's score, the score by quarter, the quarter it is in and
     its state. When anything changed (or every 10 minutes) the file is pushed to the `live` branch, as a single commit
     (the branch keeps no history), so GitHub Pages does not rebuild the site each minute. The page reads it from
     raw.githubusercontent.com every minute during games and shows the score as "live (unofficial)".
  4. While games are on, and for 3 hours after the last one ends, it starts the scores job every 30 minutes (and as soon
     as a game ends), so the official final score, box score and scoring plays (live_update.py, nflverse) come in as soon
     as nflverse publishes them instead of whenever GitHub gets to the scores job's own timer.
  5. A GitHub job can run for 6 hours: after 5 h 35 min, if a game is on or near, it starts the next run of live.yml and
     ends (the two never overlap: they share a queue).

  python live_now.py --once      one check, prints the games (needs BFF_BDL_KEY)
  python live_now.py --due       exit code 0 if a game is under way or kicks off within 20 hours, the key is set and no
                                 live run is already going (or queued), else 3
  python live_now.py --check     asks BALLDONTLIE for this week's games once: shows the key works (exit 1 if it does not)
  python live_now.py             the loop (what live.yml runs)
"""
import datetime, json, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

KEY = (os.environ.get('BFF_BDL_KEY') or '').strip()
API = 'https://api.balldontlie.io/nfl/v1/games'
OUT = 'live_now.json'
BRANCH = 'live'
ET = ZoneInfo('America/New_York')
ABBR = {'LAR': 'LA', 'WSH': 'WAS', 'JAC': 'JAX', 'LVR': 'LV', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}   # BALLDONTLIE -> nflverse
POLL = 60          # seconds between checks (free tier: 5 requests a minute)
BEAT = 600         # push at least this often while games are on, so the page can tell the feed is alive
AHEAD = 75 * 60    # ask BALLDONTLIE from this long before a kickoff
LEAD = 20 * 3600   # a run started this long before a kickoff waits for it (GitHub's timers run hours late)
LONGEST = 5 * 3600 # a game is over by then (to stop waiting on one BALLDONTLIE never marks final)
AFTER = 3 * 3600   # after the last game ends, keep starting the scores job (official box scores) this long
SCORES_EVERY = 1800
RUN_LIMIT = 5 * 3600 + 35 * 60
DATA_JOBS = ('.github/workflows/scores.yml', '.github/workflows/update.yml', '.github/workflows/photos.yml')
UA = {'User-Agent': 'BFF-fantasy-football/1.0 (https://github.com/bengasparian/bengasparian.github.io)'}


def now():
    v = os.environ.get('BFF_NOW')
    return datetime.datetime.fromisoformat(v.replace('Z', '+00:00')) if v else datetime.datetime.now(datetime.timezone.utc)


def schedule(path='index.html'):
    """[(kickoff, season, week, away, home)] from the page's schedule (each team's rows: week, opponent, home flag,
    team total, points, kickoff, ...)"""
    try:
        h = open(path, encoding='utf-8').read(); i = h.index('const D=') + 8; j = h.index(';\n', i)
        D = json.loads(h[i:j].replace('<\\/', '</'))
    except Exception as e:
        print('schedule unavailable:', e); return []
    season = (D.get('asof') or {}).get('season'); out = []
    for tm, rows in (D.get('sched') or {}).items():
        for r in rows:
            if len(r) > 5 and r[2] == 1 and r[5]:
                try: k = datetime.datetime.fromisoformat(r[5])
                except ValueError: continue
                if k.tzinfo is None: k = k.replace(tzinfo=ET)
                out.append((k.astimezone(datetime.timezone.utc), season, int(r[0]), r[1], tm))
    return sorted(out)


def window(S, t, lead=AHEAD, done=()):
    """games under way (kicked off within LONGEST, and not yet final) or kicking off within `lead` seconds"""
    return [g for g in S if g[0] - datetime.timedelta(seconds=lead) <= t <= g[0] + datetime.timedelta(seconds=LONGEST) and gid_of(g) not in done]


def gid_of(g):
    return nflid(g[1], g[2], g[3], g[4])


def fetch(dates):
    """every BALLDONTLIE game on these dates (YYYY-MM-DD), following the cursor"""
    out, cursor = [], None
    for _ in range(5):
        q = [('dates[]', d) for d in dates] + [('per_page', 100)] + ([('cursor', cursor)] if cursor else [])
        req = urllib.request.Request(API + '?' + urllib.parse.urlencode(q), headers=dict(UA, Authorization=KEY))
        with urllib.request.urlopen(req, timeout=30) as r: d = json.loads(r.read())
        out += d.get('data') or []
        cursor = (d.get('meta') or {}).get('next_cursor')
        if not cursor: break
    return out


def nflid(season, week, away, home):
    return f'{season}_{int(week):02d}_{away}_{home}'


def convert(G, S):
    """BALLDONTLIE games -> BFF's live games (only games on BFF's schedule; matched by season, week and teams)"""
    known = {nflid(s, w, a, h): k for k, s, w, a, h in S}
    out = []
    for g in G:
        try:
            a = ABBR.get(g['visitor_team']['abbreviation'], g['visitor_team']['abbreviation'])
            h = ABBR.get(g['home_team']['abbreviation'], g['home_team']['abbreviation'])
            gid = nflid(g['season'], g['week'], a, h)
        except (KeyError, TypeError, ValueError):
            continue
        if gid not in known: continue
        st = g.get('status_state') or 'unknown'
        qa = [g.get(f'visitor_team_q{i}') for i in range(1, 5)] + [g.get('visitor_team_ot')]
        qh = [g.get(f'home_team_q{i}') for i in range(1, 5)] + [g.get('home_team_ot')]
        played = [i for i in range(5) if qa[i] is not None or qh[i] is not None]   # quarters with a score posted
        q = (max(played) + 1) if played else (1 if st == 'in_progress' else None)
        ls = None
        if played:
            n = max(4, max(played) + 1)
            ls = [[int(qa[i] or 0) for i in range(n)], [int(qh[i] or 0) for i in range(n)]]
        hs, as_ = g.get('home_team_score'), g.get('visitor_team_score')
        if st not in ('in_progress', 'final') or hs is None or as_ is None: hs = as_ = None
        out.append({'id': gid, 'away': a, 'home': h, 'state': st, 'status': str(g.get('status') or '')[:40],
                    'q': q if st == 'in_progress' else None, 'as': as_, 'hs': hs, 'ls': ls, 'upd': g.get('updated_at')})
    return sorted(out, key=lambda x: x['id'])


def snapshot(t, S):
    W = window(S, t)
    if not W: return None
    dates = sorted({k.astimezone(ET).date().isoformat() for k, *_ in W} | {k.date().isoformat() for k, *_ in W})   # (Eastern and UTC dates: a night game is on two)
    return {'at': t.isoformat(timespec='seconds'), 'src': 'BALLDONTLIE NFL API (unofficial live scores)',
            'games': convert(fetch(dates), S)}


def push(doc):
    """live_now.json to the live branch as one commit (force-pushed, so the branch holds only the latest file)"""
    repo = os.environ.get('GITHUB_REPOSITORY'); token = os.environ.get('GITHUB_TOKEN')
    json.dump(doc, open(OUT, 'w'), separators=(',', ':'))
    if not (repo and token): print('saved', OUT, '(not pushed: no GITHUB_REPOSITORY/GITHUB_TOKEN)'); return
    d = tempfile.mkdtemp(prefix='live_')
    sh = lambda *a: subprocess.run(a, cwd=d, check=True, capture_output=True, text=True)
    sh('git', 'init', '-q', '-b', BRANCH)
    sh('git', 'config', 'user.name', 'gridiron-fantasy-bot'); sh('git', 'config', 'user.email', 'github-actions[bot]@users.noreply.github.com')
    json.dump(doc, open(os.path.join(d, OUT), 'w'), separators=(',', ':'))
    sh('git', 'add', OUT); sh('git', 'commit', '-q', '-m', 'Live scores ' + doc['at'])
    sh('git', 'push', '-q', '-f', f'https://x-access-token:{token}@github.com/{repo}.git', f'{BRANCH}:{BRANCH}')


def gh(path, body=None):
    """GitHub's API with the job's own token (None outside GitHub Actions)"""
    repo = os.environ.get('GITHUB_REPOSITORY'); token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not (repo and token): return None
    req = urllib.request.Request(f'https://api.github.com/repos/{repo}/{path}', method='POST' if body is not None else 'GET',
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=dict(UA, Authorization='Bearer ' + token, Accept='application/vnd.github+json'))
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read() or b'{}')


def waiting(paths, states=('queued', 'pending', 'waiting', 'requested', 'in_progress')):
    """is a run of one of these workflows going or waiting its turn? (None: unknown)"""
    try: j = gh('actions/runs?per_page=40')
    except Exception as e: print('could not list runs:', str(e)[:120]); return None
    if j is None: return None
    me = os.environ.get('GITHUB_RUN_ID')
    return any(r.get('path') in paths and r.get('status') in states and str(r.get('id')) != me for r in j.get('workflow_runs') or [])


def dispatch(wf):
    try:
        if gh(f'actions/workflows/{wf}/dispatches', {'ref': os.environ.get('GITHUB_REF_NAME') or 'main'}) is None: return False
        return True
    except Exception as e:
        print('could not start', wf + ':', str(e)[:160]); return False


def next_run():
    if dispatch('live.yml'): print('started the next run of live.yml (games still on or near)')


def scores_job(why):
    """start the scores job, unless a data job is already waiting its turn (a new run would push it out of the queue)"""
    if waiting(DATA_JOBS, ('queued', 'pending', 'waiting', 'requested')): print('scores job: one is already waiting'); return True
    ok = dispatch('scores.yml')
    if ok: print(now().strftime('%H:%M'), 'started the scores job (' + why + ')')
    return ok


def main():
    if not KEY:
        print('BFF_BDL_KEY is not set: live scores are off (the site keeps its after-game scores)')
        if '--due' in sys.argv: sys.exit(3)
        return
    S = schedule()
    if '--check' in sys.argv:   # (after saving the key: one request, nothing pushed)
        t = now(); days = [(t.astimezone(ET).date() + datetime.timedelta(days=k)).isoformat() for k in range(-3, 5)]
        try: G = fetch(days)
        except urllib.error.HTTPError as e: print('BALLDONTLIE refused the request:', e.code, '(401: the key is wrong or not active)'); sys.exit(1)
        mine = convert(G, S)
        print(f'key works: BALLDONTLIE returned {len(G)} NFL games for {days[0]} to {days[-1]}, {len(mine)} of them on BFF\'s schedule:')
        for g in mine: print(' ', g['id'], g['state'], g['as'], '-', g['hs'])
        return
    if '--due' in sys.argv:   # (for the other jobs: is a live run needed now?)
        if not window(S, now(), LEAD): sys.exit(3)
        if waiting(('.github/workflows/live.yml',)): print('a live run is already going'); sys.exit(3)
        sys.exit(0)
    if '--once' in sys.argv:
        print(json.dumps(snapshot(now(), S) or {'games': [], 'note': 'no game under way or within 75 minutes'}, indent=1)); return
    loop(S)


def loop(S, clock=time.time, sleep=time.sleep):
    t0 = clock(); last = None; last_push = 0; fails = 0; done = {}; last_scores = 0
    if not window(S, now(), LEAD): print('no game under way or within 20 hours'); return
    print('waiting for kickoff:', ', '.join(f"{a}@{h} {k.astimezone(ET):%a %H:%M} ET" for k, _, _, a, h in window(S, now(), LEAD)[:16]))
    while True:
        t = now(); left = RUN_LIMIT - (clock() - t0)
        on = window(S, t, AHEAD, done)                                   # under way, or kicking off within 75 minutes
        near = window(S, t, LEAD, done)                                  # ... or within 20 hours
        after = bool(done) and clock() - max(done.values()) < AFTER     # the official box scores are still coming in
        if not on and not near and not after: print(t.strftime('%H:%M'), 'no game under way or within 20 hours: done'); return
        if left <= 0:
            next_run(); return
        if on:
            try:
                doc = snapshot(t, S); fails = 0
                sig = json.dumps(doc['games'], sort_keys=True)
                if sig != last or clock() - last_push > BEAT:
                    push(doc); last = sig; last_push = clock()
                    live = [g for g in doc['games'] if g['state'] == 'in_progress']
                    print(t.strftime('%H:%M'), 'pushed:', ', '.join(f"{g['away']} {g['as']}-{g['hs']} {g['home']} Q{g['q']}" for g in live) or 'no game in progress yet')
                ended = [g['id'] for g in doc['games'] if g['state'] == 'final' and g['id'] not in done and g['id'] in {gid_of(x) for x in on}]
                for x in ended: done[x] = clock(); print(t.strftime('%H:%M'), 'final:', x)
                if ended and scores_job('a game ended'): last_scores = clock()
            except Exception as e:
                fails += 1; print('live check failed:', str(e)[:200])
                if fails >= 15: print('15 failures in a row: stopping (the next run tries again)'); return
            if any(g[0] <= now() for g in on) and clock() - last_scores >= SCORES_EVERY and scores_job('games on'): last_scores = clock()
            w = window(S, now(), AHEAD, done)
            if w and all(g[0] > now() + datetime.timedelta(minutes=10) for g in w):
                sleep(max(1, min(600, left, max(POLL, (min(g[0] for g in w) - now()).total_seconds() - 300))))   # before kickoff: no need to ask every minute
            else:
                sleep(max(1, min(POLL, left)))
            continue
        # no game on: the official box scores of the games that ended, then wait for the next kickoff
        if after and clock() - last_scores >= SCORES_EVERY and scores_job('after the games'): last_scores = clock()
        wake = [(min(g[0] for g in near) - datetime.timedelta(seconds=AHEAD) - now()).total_seconds()] if near else []
        if after: wake.append(max(60, SCORES_EVERY - (clock() - last_scores)))
        sleep(max(1, min(min(wake) if wake else 600, 1800, left)))


if __name__ == '__main__':
    main()
