#!/usr/bin/env python3
"""Player photos for BFF from Wikimedia Commons, only where the photographer released them under a free license.

How it works (run weekly by .github/workflows/photos.yml; nothing to set up):
  1. Wikidata links NFL players to their Pro Football Reference ID, to a picture on Wikimedia Commons and to the
     player's own Commons category (the property that holds Pro Football Reference IDs is looked up by its link pattern,
     so a renumbering cannot break this).
  2. The candidates for a player: his own picture (his Wikidata picture, and the picture his English Wikipedia article's
     infobox shows), the photos in his own Commons category and Commons photos found by his full name. A photo from his
     category or from a search counts only when it is verifiably him and him alone: the file name has his name (and no
     "and", "with" or "vs", nothing like "injury" or "fans" that puts other people in it), a search result is also filed
     under his team, his draft team or his college's football team, and exactly one face shows clearly in it (OpenCV
     face detection; a photo it cannot check is not used), and no other NFL player is named in it (nflverse's player
     table). His own picture is used when his face shows clearly in it (chosen to show him, it is the surest); else
     the most recent category or search photo (the date it was taken, else uploaded) where it does; else his own
     picture as it is.
  3. Only public domain, CC0, CC BY and CC BY-SA pictures are used; anything else (no license found, non-free, "no
     derivatives", "non-commercial") is skipped, and that player keeps his jersey icon.
  4. The picture is cropped to a 3:4 head-and-shoulders portrait around his face (top-centered when no face is clear
     enough) and saved small as photos/<player id>.webp. photos/credits.json keeps, for every photo, its author, license, license link,
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
MAX_TRIES = int(os.environ.get('BFF_PHOTO_TRIES') or 6)   # new photos downloaded to check, per player and run (his Wikidata and Wikipedia pictures are always checked; checked photos are remembered in photos/checks.json)
CROPV = 6   # how photos are cropped (6: head and shoulders around his face, from a 1920-px copy when the face is small; else top-centered); a new version re-crops every photo once
DV = 2      # how faces are found (2: at three sizes, faint ones kept for a closer look); checks of another version are made again
HIGH, LOW = .85, .6   # face detector scores: a clear face; a faint one (a face mask, a shadow) that only counts if a closer look confirms it
OTHERS = re.compile(r"\b(injur(y|ed|ies)|trainers?|carted|medical|fans|crowd|cheerleaders?|mascots?|referees?|umpires?)\b", re.I)   # something else going on in the photo
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
    """{pfr id: {'img': Commons file or None, 'cat': the player's Commons category or None, 'wp': his English Wikipedia
    article or None}} for BFF's players on Wikidata. Whole-list queries (every player with a picture; with a Commons
    category; with an English Wikipedia article), read the same way the
    ID is written on Wikidata ("GibbJa01" or "G/GibbJa01"), then kept for BFF's players"""
    want = set(pfrs); out = {}
    for p in props:
        for key, prop in (('img', 'wdt:P18'), ('cat', 'wdt:P373'), ('wp', None)):
            q = (f'SELECT ?id ?v WHERE {{ ?item wdt:{p} ?id . ?item {prop} ?v . }}' if prop else
                 f'SELECT ?id ?v WHERE {{ ?item wdt:{p} ?id . ?v schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }}')
            try: rows = sparql(q)
            except Exception as ex:
                if key != 'wp': raise
                print('Wikipedia articles from Wikidata unavailable:', str(ex)[:100]); rows = []
            for r in rows:
                pid = r['id']['value'].strip().split('/')[-1].replace('.htm', '')
                if pid not in want: continue
                e = out.setdefault(pid, {'img': None, 'cat': None, 'wp': None})
                if not e.get(key): e[key] = filename(r['v']['value']) if key in ('img', 'wp') else r['v']['value'].strip()
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
            rows = sparql(f'SELECT ?item ?dob ?label ?img ?cat ?wp WHERE {{ VALUES ?dob {{ {vals} }} ?item wdt:P569 ?dob ; wdt:P106 wd:Q19204627 ; rdfs:label ?label . '
                          f'FILTER(LANG(?label) = "en") OPTIONAL {{ ?item wdt:P18 ?img . }} OPTIONAL {{ ?item wdt:P373 ?cat . }} '
                          f'OPTIONAL {{ ?wp schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }} }}')
        except Exception as e:
            print('Wikidata birth-date lookup failed:', str(e)[:100]); continue
        for r in rows:
            d = r['dob']['value'][:10]; lab = norm(r['label']['value'])
            for p in byd.get(d, []):
                if norm(p['n']) == lab:
                    e = hits.setdefault(p['id'], {'items': set(), 'img': None, 'cat': None, 'wp': None}); e['items'].add(r['item']['value'])
                    if r.get('img') and not e['img']: e['img'] = filename(r['img']['value'])
                    if r.get('cat') and not e['cat']: e['cat'] = r['cat']['value'].strip()
                    if r.get('wp') and not e['wp']: e['wp'] = filename(r['wp']['value'])
        time.sleep(1)
    return {g: {'img': e['img'], 'cat': e['cat'], 'wp': e['wp']} for g, e in hits.items() if len(e['items']) == 1 and (e['img'] or e['cat'] or e['wp'])}


WIKI = 'https://en.wikipedia.org/w/api.php'


def fname(v):
    """a Commons file name written the way Commons does ("brock_Purdy&amp;x.jpg" -> "Brock Purdy&x.jpg")"""
    v = re.sub(r'\s+', ' ', html.unescape(urllib.parse.unquote(str(v or ''))).replace('_', ' ')).strip()
    return v[:1].upper() + v[1:]


def infobox_image(text):
    """the picture an article's infobox shows (its image parameter, before the first section heading), or None"""
    lead = re.split(r'\n==[^=]', text or '', maxsplit=1)[0]
    m = re.search(r'^[ \t]*\|[ \t]*image[ \t]*=[ \t]*(.*?)[ \t]*$', lead, re.M | re.I)
    if not m: return None
    v = re.sub(r'<!--.*?-->', '', m.group(1)).strip()
    v = re.sub(r'^\[\[\s*', '', v); v = re.sub(r'^(file|image)\s*:', '', v, flags=re.I).split('|')[0].split(']]')[0].strip()
    return fname(v) if v else None


def article_texts(titles):
    """{article title: its wikitext} (20 per request, following continuation)"""
    out = {}
    for i in range(0, len(titles), 20):
        q = {'action': 'query', 'format': 'json', 'formatversion': 2, 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main', 'titles': '|'.join(titles[i:i + 20]), 'maxlag': 5}
        cont = {}
        for _ in range(20):
            for k in range(4):   # (busy servers answer "maxlag": wait and ask again)
                d = json.loads(get(WIKI + '?' + urllib.parse.urlencode({**q, **cont})))
                if not d.get('error'): break
                time.sleep(5 + 5 * k)
            if d.get('error'): raise RuntimeError(str(d['error'])[:100])
            for pg in (d.get('query') or {}).get('pages') or []:
                r = (pg.get('revisions') or [None])[0]
                if r: out[pg['title']] = (((r.get('slots') or {}).get('main') or {}).get('content') or r.get('content') or '')
            cont = d.get('continue') or {}
            if not cont: break
            time.sleep(.5)
        time.sleep(.5)
    return out


def wikipedia_images(titles):
    """{article title: the free picture its infobox shows (on Commons)} for English Wikipedia articles (50 per request).
    Nov 3 2026: Jahmyr Gibbs's article showed "Gibbs in 2026" while his Wikidata item had no picture yet. Wikipedia's
    picture for an article (its "page image") is used only when it is the one the infobox shows: an article without one
    could otherwise give a picture of a stadium or a teammate."""
    pic, back = {}, {}
    titles = sorted({t for t in titles if t})
    for i in range(0, len(titles), 50):
        q = {'action': 'query', 'format': 'json', 'prop': 'pageimages', 'piprop': 'name', 'pilicense': 'free', 'redirects': 1, 'titles': '|'.join(titles[i:i + 50]), 'maxlag': 5}
        try: d = json.loads(get(WIKI + '?' + urllib.parse.urlencode(q)))
        except Exception as e: print('Wikipedia pictures unavailable:', str(e)[:100]); continue
        bk = {}
        for k in ('normalized', 'redirects'):
            for n in (d.get('query') or {}).get(k) or []: bk[n['to']] = bk.get(n['from'], n['from'])
        for pg in ((d.get('query') or {}).get('pages') or {}).values():
            if pg.get('pageimage'): t = pg.get('title'); pic[t] = fname(pg['pageimage']); back[t] = bk.get(t, t)
        time.sleep(.5)
    try: texts = article_texts(sorted(pic))
    except Exception as e: print('Wikipedia infoboxes unavailable (no Wikipedia pictures this run):', str(e)[:100]); return {}
    out = {back[t]: f for t, f in pic.items() if infobox_image(texts.get(t)) == f}
    if len(out) < len(pic): print('Wikipedia pictures not in the article\'s infobox (not used):', len(pic) - len(out))
    return out


NFLVERSE_PLAYERS = 'https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'
NAMES = os.path.join(OUT, 'nfl_names.json')


def nfl_names():
    """every NFL player's name as norm() writes it (nflverse's player table, 2+ words), saved in photos/nfl_names.json for
    a run when the table cannot be read. A Commons file naming another player is a photo of him too (Nov 4 2026: "Quinn
    meinerz calvin ridley" showed the Broncos guard's face, and he is not in BFF's list)."""
    try:
        import csv
        rows = csv.DictReader(io.StringIO(get(NFLVERSE_PLAYERS, timeout=120).decode('utf-8', 'replace')))
        out = sorted({' '.join(norm(r.get('display_name'))) for r in rows if len(norm(r.get('display_name'))) >= 2})
        if len(out) < 5000: raise ValueError(f'only {len(out)} names')
        if not DRY: json.dump(out, open(NAMES, 'w'), separators=(',', ':'))
        return set(out)
    except Exception as e:
        print("nflverse's player names unavailable, using the saved list:", str(e)[:100])
        try: return set(json.load(open(NAMES)))
        except Exception: return set()


def names_in(title, me, names):
    """other people's names (from names) in a file name, his own taken out; his name with a short first name counts as
    his ("Josh Dobbs" for Joshua Dobbs, "Kenny Gainwell" for Kenneth Gainwell: same last name, first names starting alike)"""
    t = ' ' + ' '.join(norm(re.sub(r'\.[a-z]{3,4}$', '', title, flags=re.I))) + ' '
    w = t.replace(' ' + me + ' ', ' | ').split() if me else t.split()
    mw = me.split() or ['']
    grams = {' '.join(w[i:i + k]) for k in (2, 3, 4) for i in range(len(w) - k + 1)}
    return {g for g in grams if '|' not in g and g in names and g != me
            and not (g.split()[-1] == mw[-1] and g.split()[0][:3] == mw[0][:3])}


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


def iou(a, b):
    """how much two boxes overlap (0: not at all, 1: the same box)"""
    iw = max(0., min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])); ih = max(0., min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    u = a[2] * a[3] + b[2] * b[3] - iw * ih
    return iw * ih / u if u > 0 else 0.


def faces(raw):
    """the faces in a photo, best first, as (x, y, w, h, score): the box in fractions of its width and height and the
    detector's score (.85 or more: a clear face; .6 to .85: a faint one). YuNet (OpenCV's neural face detector, model in
    models/) looks at the picture as it is and at 640 and 320 pixels (Nov 3 2026: at one size it missed the big faces of
    close-up portraits), one box per face, each at least 4% of the picture's short side. If the model cannot run,
    OpenCV's older detector with an eye found in the face (Nov 3 2026: without that check a leg or a glove could count),
    each counted as clear. None if neither can run."""
    try:
        import cv2, numpy as np
        from PIL import Image, ImageOps
        rgb = np.array(ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')); H_, W_ = rgb.shape[:2]
    except Exception:
        return None
    try:
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR); m = .04 * min(W_, H_); found = []
        for side in (None, 640, 320):
            s = 1. if side is None else side / max(W_, H_)
            if side and s >= 1: continue
            img = bgr if side is None else cv2.resize(bgr, (max(1, round(W_ * s)), max(1, round(H_ * s))), interpolation=cv2.INTER_AREA)
            h2, w2 = img.shape[:2]
            _, F = cv2.FaceDetectorYN.create(MODEL, '', (w2, h2), LOW, 0.3, 5000).detect(img)
            for f in (F if F is not None else []):
                b = (float(f[0]) / w2, float(f[1]) / h2, float(f[2]) / w2, float(f[3]) / h2, float(f[14]))
                if min(b[2] * W_, b[3] * H_) >= m: found.append(b)
        out = []
        for b in sorted(found, key=lambda b: -b[4]):
            if all(iou(b, o) < .3 for o in out): out.append(b)
        return out
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
            if len(ec.detectMultiScale(g[y:y + int(h * .6), x:x + w], scaleFactor=1.1, minNeighbors=4, minSize=(e, e))): out.append((x / W_, y / H_, w / W_, h / H_, 1.))
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
    by ... Aaron Jones", "Tech Sgt Michael Wilson"), and nothing else going on that puts another face in it (Nov 3 2026: the
    one clear face in "Brock Purdy injury 49ers Bears 2024" was a 49ers staff member's). From his own Commons category (linked from his Wikidata item): his
    last name in the file name. From a search: his full name (same suffix), and the file is filed under his team, his
    draft team or his college's football team (a category named like him can be a namesake's: a painter, a hockey
    goalie, a basketball player)"""
    stem = re.sub(r'\.[a-z]{3,4}$', '', title, flags=re.I).replace('_', ' ')
    if MULTI.search(stem) or NOTPHOTO.search(stem) or OTHERS.search(stem): return False
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
    """license, a 1000-px rendition and the original's size and address for each Commons file (50 per request)"""
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
                        'taken': taken(v('DateTimeOriginal')), 'w': ii.get('width'), 'h': ii.get('height'), 'orig': ii.get('url'),
                        'tw': ii.get('thumbwidth') or ii.get('width'), 'th': ii.get('thumbheight') or ii.get('height')}
        time.sleep(1)
    return info


def free_license(x):
    lic = x.get('lic') or ''
    return bool(lic) and not x.get('nonfree') and bool(FREE.match(lic)) and not NOTFREE.search(lic)


def good_face(box):
    """a face big and central enough to be the photo's subject and to show sharply: at least 8% of the picture's width,
    its center in the middle 70% across (Nov 3 2026: smaller ones were blurry, or a bystander, like a referee beside a
    player in a helmet) and not at the top edge (Nov 4 2026: a face cut off there was a player in the background, or
    the back of a helmet)"""
    if not box: return False
    x, y, w, h = box[:4]
    return w >= .08 and .15 <= x + w / 2 <= .85 and .08 <= y + h / 2 <= .8


def crop_box(w, h, face=None):
    """the 3:4 part of a w x h picture to keep, in pixels"""
    if face:                              # head and shoulders: 2.7 face-heights tall, the face centered a little above the middle
        fx, fy, fw, fh = face[0] * w, face[1] * h, face[2] * w, face[3] * h
        ch = min(h, max(int(fh * 2.7), 60)); cw = int(round(ch * 3 / 4))
        if cw > w: cw = w; ch = min(h, int(round(cw * 4 / 3)))
        x0 = min(max(0, int(fx + fw / 2 - cw / 2)), w - cw); y0 = min(max(0, int(fy + fh / 2 - ch * .42)), h - ch); return (x0, y0, x0 + cw, y0 + ch)
    if w / h > 3 / 4:                     # no clear face: wider than 3:4 keeps the middle
        cw = int(round(h * 3 / 4)); x0 = (w - cw) // 2; return (x0, 0, x0 + cw, h)
    ch = int(round(w * 4 / 3)); y0 = min(int(h * .06), h - ch); return (0, y0, w, y0 + ch)   # taller: the top part (heads are near the top), a little below the edge


def crop_save(raw, path, face=None):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
    im = im.crop(crop_box(im.size[0], im.size[1], face)).resize((W, H), Image.LANCZOS)
    im.save(path, 'WEBP', quality=82, method=6)


def confirm(raw, fs):
    """when no face in a picture is clear (a face mask, a shadow): the faint face (score .6 or more) that is big, central
    and at least 1.6 times as wide as any other, if a closer look (its head-and-shoulders crop, checked again) finds one
    clear face in the middle; else None"""
    if not fs or any(b[4] >= HIGH for b in fs): return None
    lo = sorted(fs, key=lambda b: -b[2])
    if not good_face(lo[0]) or (len(lo) > 1 and lo[0][2] < 1.6 * lo[1][2]): return None
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
    b = io.BytesIO(); im.crop(crop_box(im.size[0], im.size[1], lo[0])).save(b, 'PNG')
    hit = [f for f in faces(b.getvalue()) or [] if f[4] >= HIGH and f[2] >= .25 and .25 <= f[0] + f[2] / 2 <= .75 and .15 <= f[1] + f[3] / 2 <= .65]
    return [round(v, 4) for v in lo[0]] if len(hit) == 1 else None


def subject(c, own):
    """the face to crop to in a checked photo, or None. Any photo: its only clear face, if big and central (good_face).
    His own picture (his Wikidata picture or his Wikipedia infobox's, chosen to show him): also the clear face at least
    1.6 times as wide as any other (Nov 3 2026: a small face behind him had made Jarrett Stidham's picture "two faces"),
    or, when no face is clear, the faint one a closer look confirmed"""
    if not c: return None
    hi = sorted((b for b in c.get('b') or [] if b[4] >= HIGH), key=lambda b: -b[2])
    if len(hi) == 1: f = hi[0]
    elif hi: f = hi[0] if own and hi[0][2] >= 1.6 * hi[1][2] else None
    else: f = c.get('lo') if own else None
    return tuple(f[:4]) if f and good_face(f) else None


def bigger(x):
    """a 1920-px copy of a Commons picture (the original when it is no wider), or None. Commons serves only its standard
    thumbnail widths (20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840; Nov 4 2026: 2000 px was refused)"""
    if (x.get('w') or 0) <= 1920: u = x.get('orig')
    else: u = re.sub(r'/\d+px-', '/1920px-', x.get('thumb') or '', count=1)
    if not u or u == x.get('thumb'): return None
    try: return get(u, tries=2)
    except Exception as e: print('no bigger copy of', x.get('page'), str(e)[:80]); return None


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
    wpi = wikipedia_images([e.get('wp') for e in wd.values()])
    for e in wd.values():
        if e.get('wp') and wpi.get(e['wp']): e['wpimg'] = wpi[e['wp']]
    print('pictures from English Wikipedia articles:', sum(1 for e in wd.values() if e.get('wpimg')))
    info = commons_info(sorted({e['img'] for e in wd.values() if e.get('img')} | {e['wpimg'] for e in wd.values() if e.get('wpimg')}))
    names_ = [' '.join(norm(p['n'])) for p in P]; others = set(names_) | nfl_names(); dup = {n for n in set(names_) if names_.count(n) > 1}
    cred = {}; kept = new = skipped = noface = 0; reasons = {}; via = {}; staged = []   # (new files are written as .new and kept only if the run is sound)
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
            if face and face[3] * (x.get('th') or 0) * 2.7 < H and (x.get('w') or 0) >= 1.4 * (x.get('tw') or 1e9):   # (its crop would be enlarged: a sharper copy)
                raw = bigger(x) or raw
            crop_save(raw, path + '.new', face)   # (face: the face to crop to, checked by the caller; None: top-centered)
            staged.append(g); cred[g] = entry; new += 1; via[how] = via.get(how, 0) + 1; time.sleep(.5); return True
        except Exception as e:
            skipped += 1; print('could not save', g, x.get('page'), str(e)[:100])
            if o and o.get('src') == x['page'] and os.path.exists(path): cred[g] = o; return True   # a failed download keeps the photo he had
            return False

    try: chk = json.load(open(CHECKS)) if os.path.exists(CHECKS) else {}
    except Exception: chk = {}
    used = set()

    def check(f, x):
        """(the faces found: {'b': every face with its score, 'lo': a faint face a closer look confirmed}, the downloaded
        picture or None): remembered in photos/checks.json while the file and the way faces are found are unchanged"""
        used.add(f); c = chk.get(f)
        if c and c.get('ts') == x['ts'] and c.get('dv') == DV: return c, None
        raw = get(x['thumb']); fs = faces(raw); time.sleep(.3)
        if fs is None: return None, raw
        chk[f] = {'b': [[round(v, 4) for v in b] for b in fs[:12]], 'lo': confirm(raw, fs), 'ts': x['ts'], 'dv': DV}
        return chk[f], raw

    for p in sorted(P, key=lambda p: p['id']):
        g = p['id']; e = wd.get(g) or {}
        nm = re.sub(r'\s+(jr|sr|ii|iii|iv|v)\.?$', '', p['n'], flags=re.I); me = ' '.join(norm(p['n']))
        # every verified photo of him: his Wikidata picture, his own Commons category, a search by his full name
        cands = [(e['img'], 'wikidata')] if e.get('img') else []
        if e.get('wpimg') and e['wpimg'] != e.get('img'): cands.append((e['wpimg'], 'wikipedia'))   # (his article's picture: chosen for him by its editors)
        try:
            if e.get('cat'): cands += [(f, 'category') for f in commons_category_files(e['cat']) if f != e.get('img')]
            if me not in dup:   # (two BFF players with one name: a search cannot tell them apart)
                cands += [(f, 'search') for f in commons_search(nm) if f not in {c for c, _ in cands}]
        except Exception as ex:
            count('Commons lookup failed'); print('Commons lookup failed for', p['n'], str(ex)[:100])
        cands = [(f, how) for f, how in cands if how in ('wikidata', 'wikipedia') or (not MULTI.search(re.sub(r'\.[a-z]{3,4}$', '', f, flags=re.I)) and has_name(f, p['n'], full=how != 'category'))][:40]
        fc = {}
        try:
            extra = [f for f, _ in cands if f not in info]
            if extra: info.update(commons_info(extra))
            srch = [f for f, how in cands if how == 'search']
            if srch: fc = file_categories(srch)
        except Exception as ex:
            count('Commons lookup failed'); print('Commons lookup failed for', p['n'], str(ex)[:100])
        bio = p.get('bio') or {}; ctx = [TEAM_FULL.get(p.get('t')), TEAM_FULL.get(bio.get('dc')), bio.get('col')]
        ok_ = [(f, how) for f, how in cands if usable(info.get(f)) and (how in ('wikidata', 'wikipedia') or (verified(f, p['n'], fc.get(f) or [], ctx, how == 'category')
               and not names_in(f, me, others)))]
        if not ok_:
            x = info.get(e.get('img')) if e.get('img') else None
            count(f"Wikidata picture not free ({(x or {}).get('lic') or 'no license'})" if x else 'no photo on Commons' if not cands else 'no photo verifiably of him alone'); continue
        # his own picture where his face shows clearly (the newest first), else the most recent category or search photo
        # (the date it was taken, else uploaded) where his face shows clearly, alone
        when = lambda f: info[f].get('taken') or str(info[f].get('ts') or '')[:10]
        ok_.sort(key=lambda c: (c[1] in ('wikidata', 'wikipedia'), when(c[0])), reverse=True)   # his own pictures first (Nov 4 2026: two newer category and search photos showed someone else)
        pick = None; tries = 0; raws = {}
        for f, how in ok_:
            own = how in ('wikidata', 'wikipedia'); c = chk.get(f)
            if not (c and c.get('ts') == info[f]['ts'] and c.get('dv') == DV) and not own:
                if tries >= MAX_TRIES: continue
                tries += 1
            try: c, raw = check(f, info[f])
            except Exception as ex: print('could not check', f, str(ex)[:80]); continue
            if c is None: count('face check unavailable (opencv-python-headless 4 not installed)'); break
            if raw: raws[f] = raw
            box = subject(c, own)
            if box: pick = (f, how, box); break
        if not pick:   # his face shows clearly in none of them: his own picture as it is (top-centered), else no photo
            wf = next((c for c in ok_ if c[1] in ('wikidata', 'wikipedia')), None)
            if not wf: count('no photo with his face clearly visible'); continue
            pick = (wf[0], wf[1], None); noface += 1
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
    print(f'photos: {len(cred)} in use ({new} new, {kept} unchanged, {skipped} failed; {noface} of them his own picture with no face clear enough to crop to); found by: '
          + ', '.join(f'{k} {v}' for k, v in sorted(via.items())) + '; no photo: ' + ', '.join(f'{k} {v}' for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:8]))


if __name__ == '__main__':
    main()
