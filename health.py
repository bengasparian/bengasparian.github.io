"""Write status.json after every data run: whether each step worked, the season the site is on, and when the page was
last built successfully. It changes at most once a day when all is well, which also keeps the repository active so GitHub never pauses the scheduled jobs (it
pauses them after 60 days without activity in a public repository).

  python health.py   (the workflow passes each step's result in environment variables named STEP_<NAME>)
"""
import os, json, datetime
today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
try: old = json.load(open('status.json'))
except Exception: old = {}
steps = {k[5:].lower(): v for k, v in os.environ.items() if k.startswith('STEP_')}
ok = bool(steps) and all(v in ('success', 'skipped') for v in steps.values())
try: season = json.load(open('season.json'))
except Exception: season = old.get('season') or {}
st = {'date': today, 'ok': ok, 'steps': steps, 'season': season,
      'last_good': today if ok else old.get('last_good'),
      'failing_since': None if ok else (old.get('failing_since') or today)}
json.dump(st, open('status.json', 'w'), indent=1, sort_keys=True)
print('status:', 'all steps worked' if ok else 'some steps failed: ' + ', '.join(k for k, v in steps.items() if v not in ('success', 'skipped')),
      '| season', season.get('season'), season.get('phase'))
