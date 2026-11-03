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

UA = {'User-Agent': 'BFF-fantasy-football/1.0 (https://github.com/bengasparian/bengasparian.github.io; photo credits kept per file)'}
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
MAX_TRIES = 6   # new photos downloaded to check, per player and run (checked photos are remembered in photos/checks.json)
CROPV = 4   # how photos are cropped (4: head and shoulders around a large, central face, from a 1000-px copy; else top-centered); a new version re-crops every photo once
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'face_detection_yunet_2023mar.onnx')   # YuNet (MIT, OpenCV Zoo)
CHECKS = os.path.join(OUT, 'checks.json')


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


def wikidata_by_birth(players):
    """{BFF id: {'img', 'cat'}} for players Wikidata does not link by Pro Football Reference ID: an American football player
    (P106) with his exact birth date (P569) and his name as the English label; a name and birth date two items share is
    skipped"""
    byd = {}
    for p in players:
        bd = str((p.get('bio') or {}).get('bd') or '')
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', bd): byd.setdefault(bd, []).append(p)
    hits = {}
    ds = sorted(byd)
    for i in range(0, len(ds), 60):
        vals = ' '.join(f'"{d}T00:00:00Z"^^xsd:dateTime' for d in ds[i:i + 60])
        try:
            rows = sparql(f'SELECT ?item ?dob ?label ?img ?cat WHERE {{ VALUES ?dob {{ {vals} }} ?item wdt:P569 ?dob ; wdt:P106 wd:Q19204627 ; rdfs:label ?label . '
                          f'FILTER(LANG(?label) = "en") OPTIONAL {{ ?item wdt:P18 ?img . }} OPTIONAL {{ ?item wdt:P373 ?cat . }} }}')
        except Exception as e:
            print('Wikidata birth-date lookup failed:', str(e)[:100]); continue
        for r in rows:
            d = r['dob']['value'][:10]; lab = norm(r['label']['value'])
            for p in byd.get(d, []):
                if norm(p['n']) == lab:
                    e = hits.setdefault(p['id'], {'items': set(), 'img': None, 'cat': None}); e['items'].add(r['item']['value'])
                    if r.get('img') and not e['img']: e['img'] = filename(r['img']['value'])
                    if r.get('cat') and not e['cat']: e['cat'] = r['cat']['value'].strip()
        time.sleep(1)
    return {g: {'img': e['img'], 'cat': e['cat']} for g, e in hits.items() if len(e['items']) == 1 and (e['img'] or e['cat'])}


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
    """the clear faces in a photo, as boxes (x, y, w, h) in fractions of its width and height: YuNet (OpenCV's neural face
    detector, model in models/), score 0.85 or more and at least 4% of the picture's short side; if the model cannot run,
    OpenCV's older detector with an eye found in the face (Nov 3 2026: without that check a leg or a glove could count).
    None if neither can run."""
    try:
        import cv2, numpy as np
        from PIL import Image, ImageOps
        rgb = np.array(ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')); H_, W_ = rgb.shape[:2]
    except Exception:
        return None
    try:
        d = cv2.FaceDetectorYN.create(MODEL, '', (W_, H_), 0.85, 0.3, 5000)
        _, F = d.detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        m = .04 * min(W_, H_)
        return [(float(f[0]) / W_, float(f[1]) / H_, float(f[2]) / W_, float(f[3]) / H_) for f in (F if F is not None else []) if min(f[2], f[3]) >= m]
    except Exception:
        pass
    try:
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        fc = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml'))
        ec = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, 'haarcascade_eye.xml'))
        if fc.empty() or ec.empty(): return None
        m = max(24, int(min(g.shape) * .08)); out = []
        for (x, y, w, h) in fc.detectMultiScale(g, scaleFactor=1.1, minNeighbors=6, minSize=(m, m)):
            e = max(6, int(w) // 10)
            if len(ec.detectMultiScale(g[y:y + int(h * .6), x:x + w], scaleFactor=1.1, minNeighbors=4, minSize=(e, e))): out.append((x / W_, y / H_, w / W_, h / H_))
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


def taken(v):
    """the date a photo was taken, as YYYY-MM-DD (or YYYY-MM, YYYY) from Commons' DateTimeOriginal (often HTML), else ''"""
    m = re.search(r'\b((19|20)\d\d)(?:[-:/](\d\d)(?:[-:/](\d\d))?)?', plain(v))
    return '-'.join(x for x in (m.group(1), m.group(3), m.group(4)) if x) if m else ''


def commons_info(files):
    """license and a 600-px rendition for each Commons file (50 per request)"""
    info = {}
    for i in range(0, len(files), 50):
        chunk = files[i:i + 50]
        q = {'action': 'query', 'format': 'json', 'prop': 'imageinfo', 'iiprop': 'url|extmetadata|mime|size', 'iiurlwidth': 1000,
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
                        'artist': plain(v('Artist')) or plain(v('Credit')), 'ts': ii.get('timestamp') or (v('DateTime') or ''),
                        'taken': taken(v('DateTimeOriginal')), 'w': ii.get('width'), 'h': ii.get('height')}
        time.sleep(1)
    return info


def free_license(x):
    lic = x.get('lic') or ''
    return bool(lic) and not x.get('nonfree') and bool(FREE.match(lic)) and not NOTFREE.search(lic)


def good_face(box):
    """a face big and central enough to be the photo's subject and to show sharply: at least 8% of the picture's width,
    its center in the middle 70% (Nov 3 2026: smaller ones were blurry, or a bystander, like a referee beside a player
    in a helmet)"""
    if not box: return False
    x, y, w, h = box
    return w >= .08 and .15 <= x + w / 2 <= .85


def crop_save(raw, path, face=None):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
    w, h = im.size
    if face:                              # head and shoulders: 2.7 face-heights tall, the face centered a little above the middle
        fx, fy, fw, fh = face[0] * w, face[1] * h, face[2] * w, face[3] * h
        ch = min(h, max(int(fh * 2.7), 60)); cw = int(round(ch * 3 / 4))
        if cw > w: cw = w; ch = min(h, int(round(cw * 4 / 3)))
        x0 = min(max(0, int(fx + fw / 2 - cw / 2)), w - cw); y0 = min(max(0, int(fy + fh / 2 - ch * .42)), h - ch); box = (x0, y0, x0 + cw, y0 + ch)
    elif w / h > 3 / 4:                   # no clear face: wider than 3:4 keeps the middle
        cw = int(round(h * 3 / 4)); x0 = (w - cw) // 2; box = (x0, 0, x0 + cw, h)
    else:                                 # taller: keep the top part (heads are near the top), a little below the edge
        ch = int(round(w * 4 / 3)); y0 = min(int(h * .06), h - ch); box = (0, y0, w, y0 + ch)
    im = im.crop(box).resize((W, H), Image.LANCZOS)
    im.save(path, 'WEBP', quality=82, method=6)


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
    bb = wikidata_by_birth([p for p in P if not wd[p['id']]]); wd.update(bb)
    if bb: print('found on Wikidata by name and birth date:', len(bb))
    print(f"BFF players: {len(P)}; on Wikidata: {sum(1 for e in wd.values() if e)}; with a Wikidata picture: {sum(1 for e in wd.values() if e.get('img'))};"
          f" with a Commons category: {sum(1 for e in wd.values() if e.get('cat'))}")
    if want and not items:   # (Nov 3 2026: a query in the wrong ID format matched nobody)
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
            crop_save(raw, path + '.new', face)   # (face: the one clear face, checked by the caller; None: top-centered)
            staged.append(g); cred[g] = entry; new += 1; via[how] = via.get(how, 0) + 1; time.sleep(.5); return True
        except Exception as e:
            skipped += 1; print('could not save', g, x.get('page'), str(e)[:100])
            if o and o.get('src') == x['page'] and os.path.exists(path): cred[g] = o; return True   # a failed download keeps the photo he had
            return False

    try: chk = json.load(open(CHECKS)) if os.path.exists(CHECKS) else {}
    except Exception: chk = {}
    used = set()

    def check(f, x):
        """(number of clear faces, the face if exactly one, the downloaded picture or None): remembered when the file is unchanged"""
        used.add(f); c = chk.get(f)
        if c and c.get('ts') == x['ts']: return c['n'], c.get('f'), None
        raw = get(x['thumb']); fs = faces(raw); time.sleep(.3)
        if fs is None: return None, None, raw
        chk[f] = {'n': len(fs), 'f': [round(v, 4) for v in fs[0]] if len(fs) == 1 else None, 'ts': x['ts']}
        return chk[f]['n'], chk[f]['f'], raw

    for p in sorted(P, key=lambda p: p['id']):
        g = p['id']; e = wd.get(g) or {}
        nm = re.sub(r'\s+(jr|sr|ii|iii|iv|v)\.?$', '', p['n'], flags=re.I); me = ' '.join(norm(p['n']))
        # every verified photo of him: his Wikidata picture, his own Commons category, a search by his full name
        cands = [(e['img'], 'wikidata')] if e.get('img') else []
        try:
            if e.get('cat'): cands += [(f, 'category') for f in commons_category_files(e['cat']) if f != e.get('img')]
            if me not in dup:   # (two BFF players with one name: a search cannot tell them apart)
                cands += [(f, 'search') for f in commons_search(nm) if f not in {c for c, _ in cands}]
        except Exception as ex:
            count('Commons lookup failed'); print('Commons lookup failed for', p['n'], str(ex)[:100])
        cands = [(f, how) for f, how in cands if how == 'wikidata' or (not MULTI.search(re.sub(r'\.[a-z]{3,4}$', '', f, flags=re.I)) and has_name(f, p['n'], full=how != 'category'))][:40]
        fc = {}
        try:
            extra = [f for f, _ in cands if f not in info]
            if extra: info.update(commons_info(extra))
            srch = [f for f, how in cands if how == 'search']
            if srch: fc = file_categories(srch)
        except Exception as ex:
            count('Commons lookup failed'); print('Commons lookup failed for', p['n'], str(ex)[:100])
        bio = p.get('bio') or {}; ctx = [TEAM_FULL.get(p.get('t')), TEAM_FULL.get(bio.get('dc')), bio.get('col')]
        ok_ = [(f, how) for f, how in cands if usable(info.get(f)) and (how == 'wikidata' or (verified(f, p['n'], fc.get(f) or [], ctx, how == 'category')
               and not any(o_ != me and ' ' + o_ + ' ' in ' ' + ' '.join(norm(f)) + ' ' for o_ in others)))]
        if not ok_:
            x = info.get(e.get('img')) if e.get('img') else None
            count(f"Wikidata picture not free ({(x or {}).get('lic') or 'no license'})" if x else 'no photo on Commons' if not cands else 'no photo verifiably of him alone'); continue
        # the most recent photo (the date it was taken, else uploaded) where his face shows clearly, alone
        when = lambda f: info[f].get('taken') or str(info[f].get('ts') or '')[:10]
        ok_.sort(key=lambda c: (when(c[0]), c[1] == 'wikidata'), reverse=True)
        pick = None; tries = 0; raws = {}
        for f, how in ok_:
            c = chk.get(f)
            if not (c and c.get('ts') == info[f]['ts']):
                if tries >= MAX_TRIES: continue
                tries += 1
            try: n_, box, raw = check(f, info[f])
            except Exception as ex: print('could not check', f, str(ex)[:80]); continue
            if n_ is None: count('face check unavailable (opencv-python-headless 4 not installed)'); break
            if raw: raws[f] = raw
            if n_ == 1 and good_face(box): pick = (f, how, box); break
        if not pick:   # his face shows clearly in none of them: his Wikidata picture as it is (top-centered), else no photo
            wf = next((c for c in ok_ if c[1] == 'wikidata'), None)
            if not wf: count('no photo with his face clearly visible'); continue
            pick = (wf[0], 'wikidata', None)
        f, how, box = pick
        save(g, info[f], how, raws.get(f), box)
    if not DRY:
        try: json.dump({k: v for k, v in sorted(chk.items()) if k in used}, open(CHECKS, 'w'), separators=(',', ':'))
        except Exception as ex: print('face checks not saved:', ex)
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
