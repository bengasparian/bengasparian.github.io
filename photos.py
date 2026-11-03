#!/usr/bin/env python3
"""Player photos for BFF from Wikimedia Commons, only where the photographer released them under a free license.

How it works (run weekly by .github/workflows/photos.yml; nothing to set up):
  1. Wikidata links NFL players to their Pro Football Reference ID and to a picture on Wikimedia Commons (the property
     that holds Pro Football Reference IDs is looked up by its link pattern, so a renumbering cannot break this).
  2. For the players BFF shows (ff_data.json), each picture's license is read from Commons. Only public domain, CC0,
     CC BY and CC BY-SA pictures are used; anything else (no license found, non-free, "no derivatives", "non-commercial")
     is skipped, and that player keeps his jersey icon.
  3. The picture is cropped to a 3:4 portrait (top-centered, where the head usually is) and saved small as
     photos/<player id>.webp. photos/credits.json keeps, for every photo, its author, license, license link and the
     Commons page, which the site shows on the player's card and under Sources -> Photo credits. CC BY-SA photos stay
     under CC BY-SA after cropping (the credit says so).
Pictures already saved are kept until their source changes. A player who drops out of BFF keeps his photo for 60 days.

Set the repository variable BFF_PLAYER_PHOTOS to off to stop using player photos (the next run removes them).

  python photos.py              (needs network access to wikidata.org and wikimedia.org; Pillow)
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


def wikidata_images(props):
    """{pfr id: Commons file name} for every player item with a Pro Football Reference ID and an image"""
    out = {}
    for p in props:
        rows = sparql(f'SELECT ?id ?img WHERE {{ ?item wdt:{p} ?id . ?item wdt:P18 ?img . }}')
        for r in rows:
            pid = r['id']['value'].strip().split('/')[-1].replace('.htm', '')
            fn = urllib.parse.unquote(r['img']['value'].rsplit('/', 1)[-1]).replace('_', ' ')
            out.setdefault(pid, fn)
    return out


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


def crop_save(raw, path):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
    w, h = im.size
    if w / h > 3 / 4:                     # wider than 3:4: keep the middle
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
    P = [p for p in D['players'] if p.get('pfr')]
    want = {p['pfr']: p['id'] for p in P}
    props = pfr_property(); print('Wikidata property for Pro Football Reference IDs:', ', '.join(props))
    img = wikidata_images(props); print('players on Wikidata with a picture:', len(img))
    hit = {g: img[r] for r, g in want.items() if r in img}
    print(f'BFF players with a Wikidata picture: {len(hit)} of {len(want)}')
    info = commons_info(sorted(set(hit.values())))
    cred = {}; kept = new = skipped = 0; reasons = {}
    for g, fn in sorted(hit.items()):
        x = info.get(fn)
        if not x or not x.get('thumb'): reasons['no file info'] = reasons.get('no file info', 0) + 1; continue
        if not free_license(x): reasons[x.get('lic') or 'no license'] = reasons.get(x.get('lic') or 'no license', 0) + 1; continue
        if not str(x.get('mime') or '').startswith('image/'): continue
        path = os.path.join(OUT, g + '.webp'); o = (old.get('p') or {}).get(g)
        same = o and o.get('src') == x['page'] and o.get('ts') == x['ts'] and os.path.exists(path)
        entry = {'f': g + '.webp', 'a': x['artist'] or 'Unknown author', 'lic': x['lic'], 'lu': x['lu'], 'src': x['page'], 'ts': x['ts'],
                 'm': 'cropped and resized' + (', CC BY-SA' if 'sa' in x['lic'].lower() else ''), 'seen': NOW.date().isoformat()}
        if same: cred[g] = entry; kept += 1; continue
        if DRY: print('would save', g, fn, x['lic']); continue
        try:
            crop_save(get(x['thumb']), path); cred[g] = entry; new += 1; time.sleep(.5)
        except Exception as e:
            skipped += 1; print('could not save', g, fn, str(e)[:100])
    # players no longer in BFF keep their photo for 60 days
    wanted = set(want.values())   # (want maps Pro Football Reference IDs to BFF's player IDs)
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
    print(f'photos: {len(cred)} in use ({new} new, {kept} unchanged, {skipped} failed); skipped for license: '
          + ', '.join(f'{k} {v}' for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:8]))


if __name__ == '__main__':
    main()
