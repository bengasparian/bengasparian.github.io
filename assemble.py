"""Combine the template, styles, and data into index.html (the published page).

Ads and tips (optional, both off until set): a repository variable BFF_ADS_CLIENT (or "client" in ads.json) holding your Google AdSense publisher ID
(ca-pub- and 16 digits) turns on AdSense (Auto ads: Google places the ads) and writes ads.txt; BFF_ADS_SLOT (an AdSense
display ad unit's slot number) also fills BFF's own ad spaces; BFF_TIP_URL (a https link to your tip page, for example
Ko-fi, Buy Me a Coffee or GitHub Sponsors) shows a "Support BFF" button.

Accounts (optional): paste your Firebase web app config (the whole `const firebaseConfig = {...}` snippet is fine) into
a GitHub repository variable named BFF_FIREBASE, or into a file named accounts.json. Optional variables BFF_TERMS_STATE
(the state whose law governs the Terms of Use, default California) and BFF_CONTACT (how people reach you about their
data, e.g. an email address or a link). Nothing here is secret: Firebase web keys are meant to be public, and the
Firestore rules in firestore.rules are what protect each person's data.
"""
import os, sys, re, json
if not os.path.exists("ff_data.json"):
    print("No new data this run (for example, the regular season is over); keeping the current page."); sys.exit(0)


def accounts():
    raw = os.environ.get("BFF_FIREBASE", "")
    cfg = {}
    if os.path.exists("accounts.json"):
        try: cfg = json.load(open("accounts.json"))
        except Exception as e: print("accounts.json could not be read:", e)
        raw = raw or json.dumps(cfg.get("firebase", cfg))
    key = re.search(r'apiKey["\']?\s*[:=]\s*["\']([A-Za-z0-9_\-]{20,})["\']', raw)
    pid = re.search(r'projectId["\']?\s*[:=]\s*["\']([a-z0-9\-]{4,})["\']', raw)
    out = {}
    if key and pid: out["firebase"] = {"apiKey": key.group(1), "projectId": pid.group(1)}
    elif raw.strip(): print("BFF_FIREBASE is set but apiKey/projectId were not found in it; accounts stay off")
    law = os.environ.get("BFF_TERMS_STATE") or cfg.get("law"); contact = os.environ.get("BFF_CONTACT") or cfg.get("contact")
    if law: out["law"] = str(law)[:40]
    if contact: out["contact"] = str(contact)[:120]
    return out


def ads():
    """ads and tips from repository variables, else from ads.json in the repository ({"client": "ca-pub-...", "slot": "...",
    "tip": "https://..."}; nothing in it is secret: the publisher ID is in every page that shows ads): empty when off"""
    out = {}
    try: F = json.load(open("ads.json")) if os.path.exists("ads.json") else {}
    except Exception as e: F = {}; print("ads.json unreadable:", e)
    for k, v in (("BFF_ADS_CLIENT", "client"), ("BFF_ADS_SLOT", "slot"), ("BFF_TIP_URL", "tip")):
        if not (os.environ.get(k) or "").strip() and str(F.get(v) or "").strip(): os.environ[k] = str(F[v]).strip()
    cl = (os.environ.get("BFF_ADS_CLIENT") or "").strip()
    if cl:
        if re.fullmatch(r"ca-pub-\d{16}", cl): out["client"] = cl
        elif re.fullmatch(r"pub-\d{16}", cl): out["client"] = "ca-" + cl
        else: print("BFF_ADS_CLIENT should look like ca-pub-1234567890123456; ads stay off")
    sl = (os.environ.get("BFF_ADS_SLOT") or "").strip()
    if out.get("client") and re.fullmatch(r"\d{6,12}", sl): out["slot"] = sl
    tip = (os.environ.get("BFF_TIP_URL") or "").strip()
    if tip:
        if re.fullmatch(r"https://[^\s\"'<>]{4,200}", tip): out["tip"] = tip
        else: print("BFF_TIP_URL should be a https:// link; the tip button stays off")
    return out


t = open("template.html").read()
assert t.count("__CSS__") == 1 and t.count("__DATA__") == 1 and t.count("__SDGAME__") == 1 and t.count("<!--__ADS__-->") == 1
D = json.load(open("ff_data.json"))
A = accounts()
if A: D["auth"] = A
AD = ads()
if AD: D["ads"] = AD
# AdSense: the script in the page head (Auto ads and site verification) and ads.txt at the site's root
head = ""
if AD.get("client"):
    head = (f'<meta name="google-adsense-account" content="{AD["client"]}">'
            f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={AD["client"]}" crossorigin="anonymous"></script>')
    open("ads.txt", "w").write(f"google.com, {AD['client'][3:]}, DIRECT, f08c47fec0942fa0\n")
elif os.path.exists("ads.txt"): os.remove("ads.txt")
print("ads:", ("on (" + AD["client"] + (", BFF's ad spaces filled" if AD.get("slot") else ", Auto ads") + ")") if AD.get("client") else "off (set BFF_ADS_CLIENT to turn them on)",
      "| tips:", "on" if AD.get("tip") else "off")
# BFF Originals (articles.py): the latest ones ride along in the page, for copies that cannot load articles.json
if os.path.exists("articles.json"):
    try:
        AR = json.load(open("articles.json")); D["articles"] = {"at": AR.get("at"), "items": [{k: v for k, v in a.items() if k not in ("digest", "sig", "key")} for a in AR.get("items", [])[:30]]}
    except Exception as e: print("articles.json could not be read:", e)
# player photos (photos.py): freely licensed pictures from Wikimedia Commons, each with its author, license and source
if os.path.exists("photos/credits.json"):
    try:
        PC = json.load(open("photos/credits.json")).get("p") or {}
        D["photos"] = {g: {"f": v["f"], "a": v.get("a") or "", "l": v["lic"], "lu": v.get("lu") or "", "s": v["src"], "m": v.get("m") or ""}
                       for g, v in PC.items() if os.path.exists(os.path.join("photos", v["f"]))}
        print("player photos:", len(D["photos"]))
    except Exception as e: print("photos/credits.json could not be read:", e)
# Super Bowl and conference championship results for BFF Coach (from the NFL schedule fetch_data.py downloads)
if os.path.exists("games.csv"):
    try:
        import csv
        D["post"] = [[int(g["season"]), g["game_type"], *((g["home_team"], g["away_team"], int(g["home_score"]), int(g["away_score"])) if int(g["home_score"]) >= int(g["away_score"]) else (g["away_team"], g["home_team"], int(g["away_score"]), int(g["home_score"]))), g.get("stadium") or "", g.get("gameday") or ""]
                     for g in csv.DictReader(open("games.csv", newline="")) if g.get("game_type") in ("SB", "CON") and g.get("home_score") not in ("", "NA", None) and g.get("away_score") not in ("", "NA", None)]
    except Exception as e: print("postseason results skipped:", e)
# BFF Brain (Ask BFF's own question model and football knowledge base; trained by research/brain/train.py and kb_export.py)
for _k, _f in (("brain", "brain.json"), ("kb", "kb.json")):
    if os.path.exists(_f):
        try: D[_k] = json.load(open(_f))
        except Exception as e: print(_f, "could not be read:", e)
print("accounts:", "on (Firebase project " + A["firebase"]["projectId"] + ")" if A.get("firebase") else "off (set BFF_FIREBASE to turn them on)")
data = json.dumps(D, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
css = open("app.css").read()
# big artwork (tab covers, backgrounds) goes out to art/ as separate files: the page itself gets about 600 KB lighter, the
# images load after the page and stay in the browser's cache between visits (BFF_INLINE_ART=1 keeps them inline)
if os.environ.get("BFF_INLINE_ART") != "1":
    import base64, hashlib
    os.makedirs("art", exist_ok=True); keep = set()
    def _ext(m):
        raw = base64.b64decode(m.group(2)); fn = f"art/{hashlib.md5(raw).hexdigest()[:12]}.{'svg' if m.group(1) == 'svg+xml' else m.group(1)}"; keep.add(fn)
        if not os.path.exists(fn): open(fn, "wb").write(raw)
        return f'url("{fn}")'
    css = re.sub(r"""url\(["']?data:image/(webp|png|jpeg|svg\+xml);base64,([A-Za-z0-9+/=]{8000,})["']?\)""", _ext, css)
    for f in os.listdir("art"):
        if f"art/{f}" not in keep: os.remove(f"art/{f}")   # artwork no longer used
# Spin Draft (game_build.py): every team's fantasy scorers since 1999, parsed only when the game opens
sdg = ""
if os.path.exists("game.json"):
    try: sdg = '<script type="application/json" id="sdgame">' + json.dumps(json.load(open("game.json")), separators=(",", ":")).replace("</", "<\\/") + "</script>"
    except Exception as e: print("game.json could not be read:", e)
open("index.html", "w").write(t.replace("<!--__ADS__-->", head).replace("__CSS__", css).replace("__DATA__", data).replace("__SDGAME__", sdg))
print("index.html written")
