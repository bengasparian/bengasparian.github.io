#!/usr/bin/env python3
"""Player photos for BFF from Wikimedia Commons, only where the photographer released them under a free license.

How it works (run weekly by .github/workflows/photos.yml; nothing to set up):
  1. Wikidata links NFL players to their Pro Football Reference ID, to a picture on Wikimedia Commons and to the
     player's own Commons category (the property that holds Pro Football Reference IDs is looked up by its link pattern,
     so a renumbering cannot break this).
  2. For the players BFF shows, the picture comes from, in order: the player's Wikidata picture; else a photo in his own
     Commons category; else a Commons photo found by his full name. A photo from his category or from a search is used
     only when it is verifiably him and him alone: the file name has his name (and no "and", "with" or "vs"), a search
     result is also filed under his team, his draft team or his college's football team, and exactly one face shows
     clearly in it (OpenCV face detection; a photo it cannot check is not used).
  3. Only public domain, CC0, CC BY and CC BY-SA pictures are used; anything else (no license found, non-free, "no
     derivatives", "non-commercial") is skipped, and that player keeps his jersey icon.
  4. The picture is cropped to a 3:4 portrait around the face (or top-centered when no single face is found) and saved
     small as photos/<player id>.webp. photos/credits.json keeps, for every photo, its author, license, license link,
     the Commons page and how it was found, which the site shows on the player's card and under Sources -> Photo
     credits. CC BY-SA photos stay under CC BY-SA after cropping (the credit says so).
Pictures already saved are kept until their source changes. A player who drops out of BFF keeps his photo for 60 days.

Set the repository variable BFF_PLAYER_PHOTOS to off to stop using player photos (the next run removes them).

  python photos.py              (needs network access to wikidata.org and wikimedia.org; Pillow, opencv-python-headless 4)
  python photos.py --dry-run    (lists what it would do, writes nothing)
"""
import io, json, os, re, sys, time, html, datetime, urllib.parse, urllib.request

UA = {'User-Agent': 'BFF-fantasy-football/1.0 (https://github.com/bengasparian/bff; photo credits kept per file)'}
SPARQL = 'https://query.wikidata.org/sparql'
COMMONS = 'https://commons.wikimedia.org/w/api.php'
OUT = 'photos'; CRED = os.path.join(OUT, 'credits.json')
W, H = 240, 320                     # saved size (3:4)
DRY = '--dry-run' in sys.argv
ON = (os.environ.get('BFF_PLAYER_PHOTOS') or 'on').strip().lower() not in ('off', '0', 'no', 'false')
NOW = datetime.datetime.now(datetime.timezone.utc)
FREE = re.compile(r'^(cc0|public domain|pd\b|pd-|cc[- ]by(-sa)?[- ]\d(\.\d)?)', re.I)   # license short names Commons uses
NOTFREE = re.compile(r'(\bnc\b|non-?commercial|\bnd\b|no ?deriv|fair use|non-?free|copyrighted)', re.I)
MULTI = re.compile(r"(\b(and|with|vs|versus|feat)\b|&|\+)", re.I)   # a file named for more than one person
TEAM_FULL = {'ARI': 'Arizona Cardinals', 'ATL': 'Atlanta Falcons', 'BAL': 'Baltimore Ravens', 'BUF': 'Buffalo Bills', 'CAR': 'Carolina Panthers',
             'CHI': 'Chicago Bears', 'CIN': 'Cincinnati Bengals', 'CLE': 'Cleveland Browns', 'DAL': 'Dallas Cowboys', 'DEN': 'Denver Broncos',
             'DET': 'Detroit Lions', 'GB': 'Green Bay Packers', 'HOU': 'Houston Texans', 'IND': 'Indianapolis Colts', 'JAX': 'Jacksonville Jaguars',
             'KC': 'Kansas City Chiefs', 'LA': 'Los Angeles Rams', 'LAR': 'Los Angeles Rams', 'LAC': 'Los Angeles Chargers', 'LV': 'Las Vegas Raiders',
             'MIA': 'Miami Dolphins', 'MIN': 'Minnesota Vikings', 'NE': 'New England Patriots', 'NO': 'New Orleans Saints', 'NYG': 'New York Giants',
             'NYJ': 'New York Jets', 'PHI': 'Philadelphia Eagles', 'PIT': 'Pittsburgh Steelers', 'SEA': 'Seattle Seahawks', 'SF': 'San Francisco 49ers',
             'TB': 'Tampa Bay Buccaneers', 'TEN': 'Tennessee Titans', 'WAS': 'Washington Commanders'}
MAX_TRIES = 5   # photos downloaded to check, per player
CROPV = 2   # how photos are cropped (2: around a face confirmed by an eye, else top-centered); a new version re-crops every photo once


def get(url, data=None, timeout=60, tries=3):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()
        except Exception as e:
            last = e; time.sleep(2 + 4 * k)
    raise last


def sparql(q):
    return json.loads(get(SPARQL + '?' + urllib.parse.urlencode({'query': q, 'format': 'json'}), timeout=120))['results']['bindings']


def pfr_property():
    """the Wikidata property whose link pattern is Pro Football Reference's player pages"""
    rows = sparql('SELECT ?p ?f WHERE { ?p wdt:P1630 ?f . FILTER(CONTAINS(LCASE(STR(?f)), "pro-football-reference.com/players")) }')
    props = sorted({r['p']['value'].rsplit('/', 1)[-1] for r in rows})
    if not props: raise SystemExit('no Wikidata property for Pro Football Reference player IDs was found; keeping the current photos')
    return props


def filename(url):
    return urllib.parse.unquote(url.rsplit('/', 1)[-1]).replace('_', ' ')


def wikidata_items(props, pfrs):
    """{pfr id: {'img': Commons file or None, 'cat': the player's Commons category or None}} for BFF's players on Wikidata.
    Two whole-list queries (every player with a picture; every player with a Commons category), read the same way the
    ID is written on Wikidata ("GibbJa01" or "G/GibbJa01"), then kept for BFF's players"""
    want = set(pfrs); out = {}
    for p in props:
        for key, prop in (('img', 'P18'), ('cat', 'P373')):
            for r in sparql(f'SELECT ?id ?v WHERE {{ ?item wdt:{p} ?id . ?item wdt:{prop} ?v . }}'):
                pid = r['id']['value'].strip().split('/')[-1].replace('.htm', '')
                if pid not in want: continue
                e = out.setdefault(pid, {'img': None, 'cat': None})
                if not e[key]: e[key] = filename(r['v']['value']) if key == 'img' else r['v']['value'].strip()
    return out


def norm(s):
    """a name for matching: no accents, apostrophes, periods or suffixes ("De'Von Achane" = "DeVon Achane")"""
    import unicodedata
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"['’`.]", '', s); s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', ' ', s).split()


def has_name(title, name, full=True):
    t, n = ' ' + ' '.join(norm(re.sub(r'\.[a-z]{3,4}$', '', title, flags=re.I))) + ' ', norm(name)
    return bool(n) and (' ' + ' '.join(n) + ' ' in t if full else ' ' + n[-1] + ' ' in t)


def commons_category_files(cat, limit=100):
    q = {'action': 'query', 'format': 'json', 'list': 'categorymembers', 'cmtitle': 'Category:' + cat, 'cmtype': 'file', 'cmlimit': limit, 'maxlag': 5}
    d = json.loads(get(COMMONS + '?' + urllib.parse.urlencode(q))); time.sleep(.5)
    return [m['title'].replace('File:', '', 1) for m in (d.get('query') or {}).get('categorymembers') or []]


def commons_search(name, limit=20):
    q = {'action': 'query', 'format': 'json', 'list': 'search', 'srnamespace': 6, 'srlimit': limit, 'srsearch': f'intitle:"{name}" filetype:bitmap', 'maxlag': 5}
    d = json.loads(get(COMMONS + '?' + urllib.parse.urlencode(q))); time.sleep(.5)
    return [m['title'].replace('File:', '', 1) for m in (d.get('query') or {}).get('search') or []]


def file_categories(files):
    """the visible categories of each Commons file (50 per request)"""
    out = {}
    for i in range(0, len(files), 50):
        q = {'action': 'query', 'format': 'json', 'prop': 'categories', 'clshow': '!hidden', 'cllimit': 'max', 'titles': '|'.join('File:' + f for f in files[i:i + 50]), 'maxlag': 5}
        d = json.loads(get(COMMONS + '?' + urllib.parse.urlencode(q)))
        norm_ = {n['to']: n['from'] for n in (d.get('query') or {}).get('normalized') or []}
        for pg in ((d.get('query') or {}).get('pages') or {}).values():
            t = pg.get('title', ''); out[norm_.get(t, t).replace('File:', '', 1)] = [c['title'].replace('Category:', '', 1) for c in pg.get('categories') or []]
        time.sleep(.5)
    return out


def faces(raw):
    """faces (x, y, w, h) that are clearly faces: OpenCV's frontal-face detector, at least 8% of the picture's short side,
    with an eye found in the upper part of the box (Nov 3 2026: without the eye check, a leg, a glove or a patch of grass
    could count as a face). None if the detector cannot run."""
    try:
        import cv2, numpy as np
        from PIL import Image, ImageOps
        im = np.array(ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('L'))
        fc = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml'))
        ec = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, 'haarcascade_eye.xml'))
        if fc.empty() or ec.empty(): return None
        m = max(24, int(min(im.shape) * .08)); out = []
        for (x, y, w, h) in fc.detectMultiScale(im, scaleFactor=1.1, minNeighbors=6, minSize=(m, m)):
            e = max(6, int(w) // 10)
            if len(ec.detectMultiScale(im[y:y + int(h * .6), x:x + w], scaleFactor=1.1, minNeighbors=4, minSize=(e, e))): out.append((int(x), int(y), int(w), int(h)))
        return out
    except Exception:
        return None


SUFFIX = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}
SUBJ = re.compile(r"\b(sgt|sergeant|spc|specialist|pfc|pvt|private|cpl|corporal|lt|lieutenant|capt|captain|maj|major|col|colonel|gen|general|"
                  r"adm|admiral|airman|seaman|petty|officer|chief|tech|staff|soldier|sailor|cadet|president|secretary|governor|senator|mayor|"
                  r"coach|signed|signs|donates|donated|meets|visits|presents|holds|gives|by|of|for|to|at|and|with)\b", re.I)
NOTPHOTO = re.compile(r"(\(\s*\d{4}\s*[-\u2013]\s*\d{4}\s*\)|\b(painting|portrait of|statue|grave|tomb|memorial|signature|autograph|trading card|logo)\b)", re.I)


def words(s):
    """lowercase words of a name or file name, suffixes kept ("Michael Carter II" -> michael carter ii)"""
    import unicodedata
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', re.sub(r"['\u2019`.]", '', s)).split()


def name_in(title, name):
    """(words before, words after) the player's name in a file name, or None. A different suffix is another man
    ("Michael Carter II" is not Michael Carter); "Deebo Samuel" matches Deebo Samuel Sr."""
    t = words(re.sub(r'\.[a-z]{3,4}$', '', title, flags=re.I)); n = words(name)
    base = [w for w in n if w not in SUFFIX]; suf = [w for w in n if w in SUFFIX]
    for i in range(len(t) - len(base) + 1):
        if base and t[i:i + len(base)] == base:
            j = i + len(base); nxt = t[j] if j < len(t) else None
            if nxt in SUFFIX:
                if nxt not in suf: continue
                j += 1
            return t[:i], t[j:]
    return None


def verified(title, name, cats, ctx, own_cat):
    """a Commons file is this player alone. Always: one person in the file name (no "and", "with", "vs"), not a painting,
    grave or card, and nothing before his name that makes someone else the subject ("Sgt. ... donates a football signed
    by ... Aaron Jones", "Tech Sgt Michael Wilson"). From his own Commons category (linked from his Wikidata item): his
    last name in the file name. From a search: his full name (same suffix), and the file is filed under his team, his
    draft team or his college's football team (a category named like him can be a namesake's: a painter, a hockey
    goalie, a basketball player)"""
    stem = re.sub(r'\.[a-z]{3,4}$', '', title, flags=re.I)
    if MULTI.search(stem) or NOTPHOTO.search(stem): return False
    if own_cat:
        if not has_name(title, name, full=False): return False
        last = words(re.sub(r'\s+(jr|sr|ii|iii|iv|v)\.?$', '', name, flags=re.I))[-1:]
        t = words(stem); k = t.index(last[0]) if last and last[0] in t else 0
        return len(t[:k]) <= 9 and not SUBJ.search(' '.join(t[:k]))
    at = name_in(title, name)
    if not at: return False
    before, _ = at
    if len(before) > 8 or SUBJ.search(' '.join(before)): return False
    cl = [c.lower() for c in cats]
    return any(x and x.lower() in c and ('football' in c or x in TEAM_FULL.values()) for x in ctx for c in cl)


def plain(s):
    """an HTML credit as plain text (Commons artist fields are HTML)"""
    s = html.unescape(re.sub(r'<[^>]+>', ' ', str(s or ''))); return re.sub(r'\s+', ' ', s).strip()[:120]


def commons_info(files):
    """license and a 600-px rendition for each Commons file (50 per request)"""
    info = {}
    for i in range(0, len(files), 50):
        chunk = files[i:i + 50]
        q = {'action': 'query', 'format': 'json', 'prop': 'imageinfo', 'iiprop': 'url|extmetadata|mime|size', 'iiurlwidth': 600,
             'titles': '|'.join('File:' + f for f in chunk), 'maxlag': 5}
        d = json.loads(get(COMMONS + '?' + urllib.parse.urlencode(q)))
        norm = {n['to']: n['from'] for n in (d.get('query') or {}).get('normalized') or []}
        for pg in ((d.get('query') or {}).get('pages') or {}).values():
            ii = (pg.get('imageinfo') or [None])[0]
            if not ii: continue
            title = pg.get('title', ''); fn = norm.get(title, title).replace('File:', '', 1)
            em = ii.get('extmetadata') or {}; v = lambda k: (em.get(k) or {}).get('value')
            info[fn] = {'thumb': ii.get('thumburl') or ii.get('url'), 'mime': ii.get('mime'), 'page': ii.get('descriptionurl'),
                        'lic': plain(v('LicenseShortName')), 'lu': (v('LicenseUrl') or '').strip(), 'nonfree': str(v('NonFree') or '').lower() == 'true',
                        'artist': plain(v('Artist')) or plain(v('Credit')), 'ts': ii.get('timestamp') or (v('DateTime') or '')}
        time.sleep(1)
    return info


def free_license(x):
    lic = x.get('lic') or ''
    return bool(lic) and not x.get('nonfree') and bool(FREE.match(lic)) and not NOTFREE.search(lic)


def crop_save(raw, path, face=None):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
    w, h = im.size
    if face:                              # around the face: about 3.6 face-heights tall, the face in the upper third
        fx, fy, fw, fh = face
        ch = min(h, int(fh * 3.6)); cw = int(round(ch * 3 / 4))
        if cw > w: cw = w; ch = int(round(cw * 4 / 3))
        x0 = min(max(0, int(fx + fw / 2 - cw / 2)), w - cw); y0 = min(max(0, int(fy - fh * .9)), h - ch); box = (x0, y0, x0 + cw, y0 + ch)
    elif w / h > 3 / 4:                   # wider than 3:4: keep the middle
        cw = int(round(h * 3 / 4)); x0 = (w - cw) // 2; box = (x0, 0, x0 + cw, h)
    else:                                 # taller: keep the top part (heads are near the top), a little below the edge
        ch = int(round(w * 4 / 3)); y0 = min(int(h * .06), h - ch); box = (0, y0, w, y0 + ch)
    im = im.crop(box).resize((W, H), Image.LANCZOS)
    im.save(path, 'WEBP', quality=80, method=6)


def main():
    os.makedirs(OUT, exist_ok=True)
    old = json.load(open(CRED)) if os.path.exists(CRED) else {'p': {}}
    if not ON:
        for g in list((old.get('p') or {})):
            f = os.path.join(OUT, old['p'][g]['f'])
            if os.path.exists(f) and not DRY: os.remove(f)
        if not DRY: json.dump({'at': NOW.date().isoformat(), 'off': True, 'p': {}}, open(CRED, 'w'), indent=0)
        print('player photos are turned off (BFF_PLAYER_PHOTOS); removed', len(old.get('p') or {})); return
    if os.path.exists('ff_data.json'): D = json.load(open('ff_data.json'))
    else:   # the weekly job reads the players from the published page (ff_data.json is not saved in the repository)
        h = open('index.html', encoding='utf-8').read(); m = re.search(r'const D=(\{.*?\});\n', h, re.S)
        D = json.loads(m.group(1).replace('<\\/', '</'))
    P = [p for p in D['players'] if p.get('id') and p.get('n')]
    want = {p['pfr']: p['id'] for p in P if p.get('pfr')}
    props = pfr_property(); print('Wikidata property for Pro Football Reference IDs:', ', '.join(props))
    items = wikidata_items(props, sorted(want))
    wd = {p['id']: items.get(p.get('pfr')) or {} for p in P}
    print(f"BFF players: {len(P)}; on Wikidata: {sum(1 for e in wd.values() if e)}; with a Wikidata picture: {sum(1 for e in wd.values() if e.get('img'))};"
          f" with a Commons category: {sum(1 for e in wd.values() if e.get('cat'))}")
    if want and not any(wd.values()):   # (Nov 3 2026: a query in the wrong ID format matched nobody)
        raise SystemExit('Wikidata matched none of BFF\'s players; keeping the current photos')
    info = commons_info(sorted({e['img'] for e in wd.values() if e.get('img')}))
    names_ = [' '.join(norm(p['n'])) for p in P]; others = set(names_); dup = {n for n in others if names_.count(n) > 1}
    cred = {}; kept = new = skipped = 0; reasons = {}; via = {}; staged = []   # (new files are written as .new and kept only if the run is sound)
    count = lambda k: reasons.__setitem__(k, reasons.get(k, 0) + 1)
    usable = lambda x: bool(x and x.get('thumb') and free_license(x) and str(x.get('mime') or '').startswith('image/'))

    def save(g, x, how, raw=None, face=None):
        nonlocal kept, new, skipped
        path = os.path.join(OUT, g + '.webp'); o = (old.get('p') or {}).get(g)
        entry = {'f': g + '.webp', 'a': x['artist'] or 'Unknown author', 'lic': x['lic'], 'lu': x['lu'], 'src': x['page'], 'ts': x['ts'],
                 'm': 'cropped and resized' + (', CC BY-SA' if 'sa' in x['lic'].lower() else ''), 'via': how, 'cv': CROPV, 'seen': NOW.date().isoformat()}
        if o and o.get('src') == x['page'] and o.get('ts') == x['ts'] and o.get('cv') == CROPV and os.path.exists(path):
            cred[g] = entry; kept += 1; via[how] = via.get(how, 0) + 1; return True
        if DRY: print('would save', g, how, x['page'], x['lic']); via[how] = via.get(how, 0) + 1; return True
        try:
            raw = raw or get(x['thumb'])
            if face is None:   # (a Wikidata picture: framed around the face when exactly one shows, else top-centered)
                fs = faces(raw); face = fs[0] if fs and len(fs) == 1 else None
            crop_save(raw, path + '.new', face); staged.append(g); cred[g] = entry; new += 1; via[how] = via.get(how, 0) + 1; time.sleep(.5); return True
        except Exception as e:
            skipped += 1; print('could not save', g, x.get('page'), str(e)[:100])
            if o and o.get('src') == x['page'] and os.path.exists(path): cred[g] = o; return True   # a failed download keeps the photo he had
            return False

    for p in sorted(P, key=lambda p: p['id']):
        g = p['id']; e = wd.get(g) or {}
        if e.get('img'):
            x = info.get(e['img'])
            if usable(x): save(g, x, 'wikidata'); continue
            count(f"Wikidata picture not free ({(x or {}).get('lic') or 'no license'})")
        # no free Wikidata picture: a photo of him alone from his own Commons category, else from a search by his name
        try:
            cands = [(f, 'category') for f in (commons_category_files(e['cat']) if e.get('cat') else [])]
            nm = re.sub(r'\s+(jr|sr|ii|iii|iv|v)\.?$', '', p['n'], flags=re.I)
            me = ' '.join(norm(p['n']))
            if me not in dup:   # (two BFF players with one name: a search cannot tell them apart)
                cands += [(f, 'search') for f in commons_search(nm) if f not in {c for c, _ in cands}]
            # the file name first (no lookups): his name, one person
            cands = [(f, how) for f, how in cands if not MULTI.search(re.sub(r'\.[a-z]{3,4}$', '', f, flags=re.I)) and has_name(f, p['n'], full=how != 'category')][:25]
            if not cands: count('no photo on Commons'); continue
            fi = commons_info([f for f, _ in cands]); fc = file_categories([f for f, _ in cands])
        except Exception as ex:
            count('Commons lookup failed'); print('Commons lookup failed for', p['n'], str(ex)[:100]); continue
        bio = p.get('bio') or {}; ctx = [TEAM_FULL.get(p.get('t')), TEAM_FULL.get(bio.get('dc')), bio.get('col')]
        ok_ = [(f, how) for f, how in cands if usable(fi.get(f)) and verified(f, p['n'], fc.get(f) or [], ctx, how == 'category')
               and not any(o_ != me and ' ' + o_ + ' ' in ' ' + ' '.join(norm(f)) + ' ' for o_ in others)]
        if not ok_: count('no photo verifiably of him alone'); continue
        o = (old.get('p') or {}).get(g)
        ok_.sort(key=lambda c: str(fi[c[0]].get('ts') or ''), reverse=True)   # newest first, then: the photo he has now, his own category
        ok_.sort(key=lambda c: (not (o and o.get('src') == fi[c[0]]['page']), c[1] != 'category'))
        if o and o.get('src') == fi[ok_[0][0]]['page'] and o.get('ts') == fi[ok_[0][0]]['ts'] and o.get('cv') == CROPV and os.path.exists(os.path.join(OUT, g + '.webp')):
            save(g, fi[ok_[0][0]], ok_[0][1]); continue   # checked when it was saved; unchanged since
        done = False
        for f, how in ok_[:MAX_TRIES]:
            try: raw = get(fi[f]['thumb'])
            except Exception: continue
            fs = faces(raw)
            if fs is None: count('face check unavailable (opencv-python-headless 4 not installed)'); break
            if len(fs) == 1: done = save(g, fi[f], how, raw, fs[0]); break
            time.sleep(.3)
        if not done: count('no photo verifiably of him alone')
    wanted = {p['id'] for p in P}
    before = sum(1 for g in (old.get('p') or {}) if g in wanted)
    if before >= 50 and sum(1 for g in cred if g in wanted) < .85 * before and not DRY:   # a fault, not 15% of licenses changing in a week
        for g in staged: os.remove(os.path.join(OUT, g + '.webp.new'))
        raise SystemExit(f'photos would drop from {before} to {sum(1 for g in cred if g in wanted)}; keeping the current photos (nothing saved)')
    for g in staged: os.replace(os.path.join(OUT, g + '.webp.new'), os.path.join(OUT, g + '.webp'))
    # players no longer in BFF keep their photo for 60 days
    for g, o in (old.get('p') or {}).items():
        if g in cred or g in wanted: continue
        try: age = (NOW.date() - datetime.date.fromisoformat(o.get('seen') or '2000-01-01')).days
        except ValueError: age = 999
        if age <= 60 and os.path.exists(os.path.join(OUT, o['f'])): cred[g] = o
        elif not DRY and os.path.exists(os.path.join(OUT, o['f'])): os.remove(os.path.join(OUT, o['f']))
    # a player whose picture is no longer free (or gone): his old file goes
    for g, o in (old.get('p') or {}).items():
        if g not in cred and not DRY and os.path.exists(os.path.join(OUT, o['f'])): os.remove(os.path.join(OUT, o['f']))
    if not DRY: json.dump({'at': NOW.date().isoformat(), 'p': dict(sorted(cred.items()))}, open(CRED, 'w'), indent=0)
    print(f'photos: {len(cred)} in use ({new} new, {kept} unchanged, {skipped} failed); found by: '
          + ', '.join(f'{k} {v}' for k, v in sorted(via.items())) + '; no photo: ' + ', '.join(f'{k} {v}' for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:8]))


if __name__ == '__main__':
    main()
