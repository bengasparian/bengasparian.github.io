#!/usr/bin/env python3
"""Safety check before anything is saved to the site.

  python check_page.py          check index.html (data job): placeholders filled, data readable, enough players,
                                script free of syntax errors (node --check, preinstalled on GitHub's runners)
  python check_page.py --json   check the small saved files: live.json, news.json, lines.json, calls_history.json, articles.json, photos/credits.json

Anything that fails is put back to the last saved version (git checkout), so the published site never breaks.
The data check exits with an error so the run shows as failed and nothing new is saved; the next run tries again.
"""
import json, os, re, shutil, subprocess, sys, tempfile

def restore(path, why):
    print(f'CHECK FAILED for {path}: {why}')
    r = subprocess.run(['git', 'checkout', '--', path], capture_output=True, text=True)
    print('  restored the last saved version' if r.returncode == 0 else f'  (no saved version to restore: {r.stderr.strip()[:80]})')

def check_json():
    bad = 0
    for f in ('live.json', 'news.json', 'lines.json', 'bet_inputs.json', 'calls_history.json', 'articles.json', 'photos/credits.json'):
        if not os.path.exists(f): continue
        try:
            d = json.load(open(f))
            if f == 'news.json' and not isinstance(d.get('items'), list): raise ValueError('no items list')
            if f == 'lines.json' and not isinstance(d.get('lines'), list): raise ValueError('no lines list')
            if f == 'calls_history.json' and not isinstance(d.get('weeks'), dict): raise ValueError('no weeks')
            if f == 'photos/credits.json' and not all(isinstance(v, dict) and v.get('f') and v.get('lic') and v.get('src') for v in (d.get('p') or {}).values()): raise ValueError('a photo without its license or source')
            if f == 'articles.json' and not (isinstance(d.get('items'), list) and all(isinstance(a, dict) and a.get('id') and a.get('title') and isinstance(a.get('body'), list) for a in d['items'])): raise ValueError('bad articles')
        except Exception as e:
            restore(f, e); bad += 1
    print('live files OK' if not bad else f'{bad} file(s) restored')
    return 0                                       # the score job always continues; restored files simply are not changed

def check_page():
    f = 'index.html'
    if not os.path.exists(f): print('no index.html built this run; nothing to check'); return 0
    h = open(f, encoding='utf-8').read()
    try:
        if '__CSS__' in h or '__DATA__' in h: raise ValueError('template placeholders were not filled')
        if len(h) > 15_000_000: raise ValueError(f'page is unexpectedly large ({len(h) // 1024} KB)')
        m = re.search(r'const D=(\{.*?\});\n', h, re.S)
        if not m: raise ValueError('embedded data not found')
        D = json.loads(m.group(1))
        n = len(D.get('players') or [])
        if n < 300: raise ValueError(f'only {n} players in the data')
        for k in ('asof', 'sched', 'dvp', 'model'):
            if k not in D: raise ValueError(f'data is missing "{k}"')
        a = h.rindex('<script>') + 8; js = h[a:h.index('</script>', a)]   # the page's own script (the Spin Draft data follows it)
        g0 = h.find('<script type="application/json" id="sdgame">')
        if g0 >= 0:
            G = json.loads(h[g0 + 44:h.index('</script>', g0)].replace('<\\/', '</'))
            if not G.get('t') or len(G['t']) < 20: raise ValueError('Spin Draft data looks incomplete')
        node = shutil.which('node')
        if node:
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as t: t.write(js)
            r = subprocess.run([node, '--check', t.name], capture_output=True, text=True); os.unlink(t.name)
            if r.returncode != 0:
                L = r.stderr.strip().splitlines(); msg = next((l for l in L if 'Error' in l), L[-1] if L else '')
                raise ValueError('script syntax error: ' + msg[:200])
        else: print('node not found; skipped the script syntax check')
    except Exception as e:
        restore(f, e); return 1
    print(f'page OK: {n} players, {len(h) // 1024} KB')
    return 0

if __name__ == '__main__':
    sys.exit(check_json() if '--json' in sys.argv else check_page())
