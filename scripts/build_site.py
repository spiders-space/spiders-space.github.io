#!/usr/bin/env python3
"""
build_site.py — ساخت سایت استاتیک (GitHub Pages) از data/posts.json
خروجی در docs/ :
  index.html · page/N/ · post/<id>/ · feed.xml · sitemap.xml · robots.txt
  search.json · data/page-N.json · site.webmanifest · assets/ · media/
"""
import json, os, re, shutil, sys, html as htmllib
from pathlib import Path
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import quote
from xml.sax.saxutils import escape as xesc

from bs4 import BeautifulSoup

ROOT   = Path(__file__).resolve().parent.parent
CFG    = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DOCS   = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

SITE_URL = (os.environ.get("SITE_URL") or CFG.get("site_url") or "").rstrip("/")
TITLE    = CFG.get("site_title", "SPIDERS_W3B")
DESC     = CFG.get("site_description", "")
TG_URL   = CFG.get("telegram_url", f"https://t.me/{CFG.get('channel','')}")
PAGE_SIZE = int(CFG.get("page_size", 25))
LANG     = CFG.get("lang", "en")
DIR      = "rtl" if LANG == "fa" else "ltr"
LOCALE   = "fa_IR" if LANG == "fa" else "en_US"

posts = json.loads((ROOT / "data/posts.json").read_text(encoding="utf-8")) \
    if (ROOT / "data/posts.json").exists() else []
chan = json.loads((ROOT / "data/channel.json").read_text(encoding="utf-8")) \
    if (ROOT / "data/channel.json").exists() else {}
CHAN_TITLE = chan.get("title") or TITLE
NOW = datetime.now(timezone.utc).strftime("%Y.%m.%d / %H:%M UTC")

MONO_JUNK = re.compile(r"<[^>]+>")

# ——— استایل و اسکریپت داخل خود HTML این‌لاین می‌شوند ———
# چرا؟ چون با هر روش آپلود (حتی وب‌آپلود گیت‌هاب) دیگر فایل css/js جدا
# برای ۴۰۴ خوردن وجود ندارد؛ سایت همیشه استایل‌دار بالا می‌آید.
CSS_SRC = (ROOT / "assets/css/style.css").read_text(encoding="utf-8")
APP_JS  = (ROOT / "assets/js/app.js").read_text(encoding="utf-8")
try:
    FAVICON_DATA = "data:image/svg+xml," + \
        quote((ROOT / "assets/img/favicon.svg").read_text(encoding="utf-8"), safe="")
except Exception:
    FAVICON_DATA = ""

def inline_css(rel: str) -> str:
    """مسیر فونت‌ها را نسبت به عمق صفحه اصلاح می‌کند (CSS در assets/css/ '../fonts/' می‌بیند)."""
    return CSS_SRC.replace("../fonts/", f"{rel}assets/fonts/")

def favicon_href(rel: str) -> str:
    return FAVICON_DATA or (rel + "assets/img/favicon.svg")

def log(*a): print("[build]", *a, flush=True)
def esc(s): return htmllib.escape(str(s or ""), quote=True)

def fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
        return dt.strftime("%Y.%m.%d — %H:%M UTC").replace("—", "//")
    except Exception:
        return iso or ""

def rfc822(iso: str) -> str:
    try:
        return format_datetime(datetime.fromisoformat(iso.replace("Z", "+00:00")))
    except Exception:
        return format_datetime(datetime.now(timezone.utc))

# ------------------------------------------------------------------ sanitize متن پست
ALLOWED_TAGS = {"a", "br", "b", "strong", "i", "em", "u", "s", "strike", "del",
                "code", "pre", "blockquote", "span"}

def sanitize_html(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup.find_all(True):
        if tag.name not in ALLOWED_TAGS:
            if tag.name in ("script", "style"):
                tag.decompose()
            else:
                tag.unwrap()
            continue
        if tag.name == "a":
            href = tag.get("href", "")
            tag.attrs = {"href": href}
            if href.startswith("http"):
                tag["target"] = "_blank"
                tag["rel"] = "nofollow noopener"
        elif tag.name == "span":
            if "tg-spoiler" in (tag.get("class") or []):
                tag.attrs = {"class": "spoiler"}
            else:
                tag.unwrap()
        else:
            tag.attrs = {}
    body = soup.body or soup
    return body.decode_contents().strip()

def plain_text(post, limit=0) -> str:
    t = MONO_JUNK.sub(" ", post.get("text_html") or "")
    t = re.sub(r"\s+", " ", t).strip()
    if not t and post.get("poll"):
        t = post["poll"].get("question", "")
    if limit and len(t) > limit:
        t = t[: limit - 1].rstrip() + "…"
    return t

# ------------------------------------------------------------------ رندر مدیا
EYE = ('<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" '
       'stroke-width="1.8" aria-hidden="true"><path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12Z"/>'
       '<circle cx="12" cy="12" r="2.6"/></svg>')
FILE_SVG = ('<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" '
            'stroke-width="1.6" aria-hidden="true"><path d="M14 3H7a1.5 1.5 0 0 0-1.5 1.5v15A1.5 1.5 0 0 0 7 21h10a1.5 1.5 0 0 0 1.5-1.5V8Z"/>'
            '<path d="M14 3v5h4.5"/><path d="M9 13h6M9 16.5h4"/></svg>')

def media_src(item, rel, key, remote_key="url", premium=False):
    return rel + item[key] if item.get(key) else (item.get(remote_key) or "")

def render_media(post, rel="") -> str:
    out = []
    photos = [m for m in post["media"] if m["type"] == "photo"]
    others = [m for m in post["media"] if m["type"] != "photo"]

    if photos:
        out.append(f'<div class="photos n{min(len(photos),4)}">')
        gal = f"g{post['id']}"
        for i, m in enumerate(photos, 1):
            full = media_src(m, rel, "local")
            out.append(
                f'<a class="lb" href="{esc(full)}" data-gal="{gal}" '
                f'title="photo {i}"><img loading="lazy" decoding="async" '
                f'src="{esc(full)}" alt="photo {i} — post #{post["id"]}"></a>')
        out.append("</div>")

    for m in others:
        t = m["type"]
        if t == "video":
            src = media_src(m, rel, "local")
            poster = media_src(m, rel, "thumb", "thumb_remote")
            dur = f'<span class="dur mono">{esc(m["duration"])}</span>' if m.get("duration") else ""
            poster_attr = f' poster="{esc(poster)}"' if poster else ""
            out.append(
                f'<div class="vid{ " round" if m.get("round") else ""}">'
                f'<video controls preload="none" playsinline src="{esc(src)}"{poster_attr}></video>{dur}</div>')
        elif t in ("audio", "voice"):
            src = media_src(m, rel, "local")
            label = "voice message" if t == "voice" else "audio"
            title = m.get("title") or label
            meta = " · ".join(x for x in [m.get("performer"), m.get("duration")] if x)
            out.append(
                f'<div class="audio"><div class="a-row"><span class="a-kind mono">{esc(label)}</span>'
                f'<span class="a-title">{esc(title)}</span></div>'
                f'<audio controls preload="none" src="{esc(src)}"></audio>'
                + (f'<div class="a-meta mono">{esc(meta)}</div>' if meta else "") + "</div>")
        elif t == "document":
            src = media_src(m, rel, "local")
            size = f'<span class="d-size mono">{esc(m["size"])}</span>' if m.get("size") else ""
            out.append(
                f'<a class="doc" href="{esc(src)}" download target="_blank" rel="noopener">'
                f'{FILE_SVG}<span class="d-name">{esc(m.get("title") or "file")}</span>{size}'
                f'<span class="d-dl mono">download ↓</span></a>')
    return "\n".join(out)

def render_poll(poll) -> str:
    if not poll:
        return ""
    ptype = f'<span class="tag mono">{esc(poll["type"])}</span>' if poll.get("type") else ""
    rows = []
    for o in poll.get("options", []):
        pct = o.get("percent", "")
        w = re.sub(r"[^\d.]", "", pct) or "0"
        rows.append(
            f'<div class="opt"><div class="optrow mono"><span>{esc(pct)}</span>'
            f'<span class="opttext">{esc(o.get("text",""))}</span></div>'
            f'<div class="bar"><i style="width:{w}%"></i></div></div>')
    voters = f'<div class="voters mono">{esc(poll["voters"])}</div>' if poll.get("voters") else ""
    return (f'<div class="poll"><div class="pq-row"><span class="pq">{esc(poll.get("question",""))}</span>{ptype}</div>'
            + "".join(rows) + voters + "</div>")

def render_link_preview(lp, rel="") -> str:
    if not lp:
        return ""
    img = ""
    if lp.get("image"):
        img = f'<img loading="lazy" decoding="async" src="{esc(lp["image"])}" alt="">'
    return (f'<a class="lprev" href="{esc(lp.get("url") or "#")}" target="_blank" rel="nofollow noopener">'
            f'{img}<span class="lp-site mono">{esc(lp.get("site") or "")}</span>'
            f'<span class="lp-title">{esc(lp.get("title") or "")}</span>'
            f'<span class="lp-desc">{esc(lp.get("desc") or "")}</span></a>')

FWD_SVG = ('<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2">'
           '<path d="M13 5l7 7-7 7M4 5l7 7-7 7"/></svg>')

# ------------------------------------------------------------------ رندر کارت پست
def render_card(post, rel="", single=False) -> str:
    pid = post["id"]
    text = sanitize_html(post.get("text_html") or "")
    head_tags = f'<span class="ph-id mono">#{pid}</span>'
    if post.get("date"):
        head_tags += (f'<time class="ph-date mono" datetime="{esc(post["date"])}" '
                      f'title="{esc(post["date"])}">{esc(fmt_date(post["date"]))}</time>')
    if post.get("edited"):
        head_tags += '<span class="tag mono">edited</span>'
    if post.get("fwd"):
        f = post["fwd"]
        n = esc(f.get("name") or "")
        head_tags += (f'<a class="tag fwd mono" href="{esc(f["url"])}" target="_blank" '
                      f'rel="nofollow noopener">{FWD_SVG} {n}</a>') if f.get("url") else \
                     (f'<span class="tag fwd mono">{FWD_SVG} {n}</span>')

    reply = ""
    if post.get("reply") and (post["reply"].get("text") or post["reply"].get("author")):
        r = post["reply"]
        inner = (f'<span class="rp-a mono">{esc(r.get("author") or "")}</span>'
                 f'<span class="rp-t">{esc((r.get("text") or "")[:180])}</span>')
        reply = (f'<a class="reply" href="{esc(r["url"])}" target="_blank" rel="nofollow noopener">'
                 f'{inner}</a>') if r.get("url") else f'<blockquote class="reply">{inner}</blockquote>'

    media = render_media(post, rel)
    poll = render_poll(post.get("poll"))
    lp = render_link_preview(post.get("link_preview"), rel)
    views = (f'<span class="views mono" title="views">{EYE} {esc(post["views"])}</span>'
             if post.get("views") else "")
    tg = (f'<a class="foot-a mono" href="{esc(post["url"])}" target="_blank" rel="noopener">telegram ↗</a>')
    plink = f'<a class="foot-a mono" href="{rel}post/{pid}/">link ٭</a>'
    copy = (f'<button class="foot-a copy mono" data-url="{SID}/post/{pid}/" type="button">copy link</button>')

    article_tag = "article"
    parts = [f'<{article_tag} class="post" id="p{pid}" itemscope itemtype="https://schema.org/SocialMediaPosting">',
             f'<meta itemprop="url" content="{SID}/post/{pid}/">',
             f'<meta itemprop="datePublished" content="{esc(post.get("date") or "")}">',
             f'<header class="post-head">{head_tags}</header>',
             reply,
             f'<div class="post-text" dir="auto" itemprop="articleBody">{text}</div>' if text else "",
             media, poll, lp,
             f'<footer class="post-foot">{views}<span class="spacer"></span>{copy}{plink}{tg}</footer>',
             f'</{article_tag}>']
    return "\n".join(p for p in parts if p)

# ------------------------------------------------------------------ SVG ها
SPIDER = '''<svg viewBox="0 0 100 100" width="40" height="40" aria-hidden="true">
<g stroke="#d7d7d7" stroke-width="2" fill="none" stroke-linecap="round">
<path d="M38 42 C25 33 18 22 12 14"/><path d="M36 50 C22 48 12 46 5 43"/>
<path d="M37 58 C24 63 16 71 11 80"/><path d="M43 66 C35 76 31 86 29 95"/>
<path d="M62 42 C75 33 82 22 88 14"/><path d="M64 50 C78 48 88 46 95 43"/>
<path d="M63 58 C76 63 84 71 89 80"/><path d="M57 66 C65 76 69 86 71 95"/>
</g>
<ellipse cx="50" cy="58" rx="12" ry="15" fill="#0d0d0d" stroke="#d7d7d7" stroke-width="2"/>
<circle cx="50" cy="36" r="8" fill="#0d0d0d" stroke="#d7d7d7" stroke-width="2"/>
<path d="M45 55 L55 55 L50 66 Z" fill="#e53137"/><path d="M46 68 L54 68 L50 74 Z" fill="#e53137"/>
</svg>'''

def web_svg(cls="web tl"):
    legs = ""
    import math
    for ang in (0, 15, 30, 45, 60, 75, 90):
        x = 300 * math.cos(math.radians(ang)); y = 300 * math.sin(math.radians(ang))
        legs += f'<path d="M0 0 L{x:.1f} {y:.1f}"/>'
    arcs = ""
    for r in (55, 105, 155, 205, 255):
        arcs += f'<path d="M{r} 0 A{r} {r} 0 0 1 0 {r}"/>'
    return (f'<svg class="{cls}" viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg" '
            f'aria-hidden="true"><g stroke="currentColor" stroke-width="1" fill="none">{legs}{arcs}</g></svg>')

# ------------------------------------------------------------------ قالب اصلی صفحه
# ASCII art هدر — هماهنگ با index.html دستی کاربر
ART = r"""
  _________      .__    .___                     __      _____________.
 /   _____/_____ |__| __| _/___________  ______ /  \    /  \_____  \_ |__
 \_____  \\____ \|  |/ __ |/ __ \_  __ \/  ___/ \   \/\/   / _(__  <| __ \
 /        \  |_> >  / /_/ \  ___/|  | \/\___ \   \        / /       \ \_\ \
/_______  /   __/|__\____ |\___  >__|  /____  >   \__/\  / /______  /___  /
        \/|__|           \/    \/           \/         \/         \/    \/"""

# ASCII art فوتر (mini-web) — هماهنگ با index.html دستی کاربر
MINI_WEB = r"""  
/ _ \
\_\(_)/_/
 _//o\\_ 
/   \
  """

def nav_links(rel=""):
    return (f'<a class="mono" href="{rel}feed.xml">RSS</a><span class="sep">·</span>'
            f'<a class="mono" href="{rel}sitemap.xml">SITEMAP</a><span class="sep">·</span>'
            f'<a class="mono" href="{TG_URL}" target="_blank" rel="noopener">T.ME ↗</a>')

def head(*, title, desc, path, rel="", og_type="website", og_image=None, jsonld=None, extra=""):
    canonical = f'<link rel="canonical" href="{SID}/{path}">' if SID else ""
    og_url = f'<meta property="og:url" content="{SID}/{path}">' if SID else ""
    og_img = og_image or (f"{SID}/assets/og.png" if SID else f"{rel}assets/og.png")
    og_img_abs = og_img if og_img.startswith("http") else (f"{SID}/{og_img}" if SID and not og_img.startswith("..") else og_img)
    jsonld_tag = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    twitter = "summary_large_image" if og_img_abs.startswith("http") else "summary"
    return f"""<!DOCTYPE html>
<html lang="{LANG}" dir="{DIR}">
<head>
<meta name="google-site-verification" content="ZhhXRYlMZplya4MJ1f3li6XBfyM0PZ0BOYCtPOLeBCY" />
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{canonical}
<link rel="icon" type="image/svg+xml" href="{favicon_href(rel)}">
<link rel="alternate" type="application/rss+xml" title="{esc(TITLE)} RSS" href="{rel}feed.xml">
<link rel="manifest" href="{rel}site.webmanifest">
<meta property="og:site_name" content="{esc(TITLE)}">
<meta property="og:locale" content="{LOCALE}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
{og_url}
{f'<meta property="og:image" content="{esc(og_img_abs)}">' if og_img_abs else ''}
<meta name="twitter:card" content="{twitter}">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
{jsonld_tag}
{extra}
<script>try{{if(localStorage.getItem('spiders-nofx')==='1')document.documentElement.classList.add('nofx')}}catch(e){{}}</script>
<style>{inline_css(rel)}</style>
</head>"""

def shell(*, title, desc, path, feed_html, pager="", extra_head="", og_type="website",
          jsonld=None, rel="", feed_js=None):
    subs = chan.get("counters", [])
    subs_html = f'<span class="subs mono">{" · ".join(esc(s) for s in subs)}</span>' if subs else ""
    h = head(title=title, desc=desc, path=path, rel=rel, og_type=og_type, jsonld=jsonld, extra=extra_head)
    nav = nav_links(rel)
    feed_data = f'<script>window.__FEED__={json.dumps(feed_js)}</script>' if feed_js else ""
    return f"""{h}
<body>
{web_svg("web tl")}
{web_svg("web br")}
<a class="skip mono" href="#feed">skip to feed</a>

<header class="mast">
  <pre class="art mono" aria-hidden="true">{ART}
  </pre>
  <p class="tagline mono">live web archive // synced with <a href="{TG_URL}" target="_blank" rel="noopener">t.me/{esc(chan.get('handle') or 'telegram')}</a></p>
  {subs_html}
  <nav class="nav mono"><a href="{rel or './'}index.html" rel="home">home</a><span class="sep">·</span>{nav}<button id="fxtoggle" class="ghost mono" type="button" title="toggle visual effects">fx</button></nav>

  <div class="searchbox" role="search">
    <input id="q" type="search" dir="auto" placeholder="search the web…" autocomplete="off" aria-label="search posts">
    <kbd class="mono">/</kbd>
    <div id="searchres" class="results" hidden></div>
  </div>
</header>

<main id="feed" class="feed">
{feed_html}
<div id="sentinel" aria-hidden="true"></div>
{pager}
</main>

<footer class="foot">
  <pre class="mini-web mono" aria-hidden="true">{MINI_WEB}
  </pre>
  <h2 class="title mono">{esc(CHAN_TITLE)}<span class="caret">▌</span></h2>
  <p class="mono">spiders_w3b // static web // no cookies · no trackers · no js ads</p>
  <p class="mono dim">last update: {NOW} — woven by github actions 🕷</p>
  <nav class="mono">{nav}</nav>
</footer>

<div id="lb" class="lbbox" hidden>
  <button class="lb-x mono" type="button" aria-label="close">✕</button>
  <button class="lb-n lb-prev mono" type="button" aria-label="previous">‹</button>
  <img alt="">
  <button class="lb-n lb-next mono" type="button" aria-label="next">›</button>
  <div class="lb-cap mono"></div>
</div>
<div id="toast" class="toast mono" role="status"></div>
<button id="top" class="totop mono" type="button" title="back to top">↑</button>
{feed_data}
<script>{APP_JS}</script>
</body>
</html>"""

# ------------------------------------------------------------------ صفحه‌بندی
def chunked(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]

SID = SITE_URL  # alias داخلی برای کارت‌ها

EMPTY_STATE = """
<div class="empty mono">
  <div class="term">
    <p><span class="ok">[*]</span> connection established :: <b>t.me/spiders_w3b</b></p>
    <p><span class="ok">[*]</span> listening on the web…</p>
    <p><span class="ok">[*]</span> trap set for incoming signals</p>
    <p><span class="dot">[_]</span> no transmissions yet — the first signal will appear here<span class="caret">▌</span></p>
  </div>
  <a class="cta mono" href="https://t.me/spiders_w3b" target="_blank" rel="noopener">join the channel ↗</a>
</div>"""

def pager_links(page, pages, rel=""):
    links = []
    if page < pages:
        links.append(f'<a class="mono" href="{rel}page/{page+1}/" rel="next">← older signals</a>')
    if page > 1:
        href = f"{rel}index.html" if page == 2 else f"{rel}page/{page-1}/"
        links.append(f'<a class="mono" href="{href}" rel="prev">newer signals →</a>')
    if not links:
        return ""
    return '<nav class="pager" aria-label="صفحه‌بندی">' + '<span class="sep"> · </span>'.join(links) + '</nav>'

def jsonld_index(items):
    parts = []
    for p in items[:10]:
        parts.append({"@type": "SocialMediaPosting",
                      "headline": plain_text(p, 110) or f"post #{p['id']}",
                      "datePublished": p.get("date"),
                      "url": f"{SID}/post/{p['id']}/" if SID else p["url"],
                      "author": {"@type": "Organization", "name": CHAN_TITLE, "sameAs": TG_URL}})
    return {"@context": "https://schema.org", "@type": "CollectionPage",
            "name": TITLE, "description": DESC,
            "url": SID or None, "hasPart": parts}

def jsonld_post(p):
    imgs = [f"{SID}/{m['local']}" for m in p["media"]
            if m["type"] == "photo" and m.get("local") and SID]
    j = {"@context": "https://schema.org", "@type": "SocialMediaPosting",
         "headline": plain_text(p, 110) or f"post #{p['id']}",
         "datePublished": p.get("date"), "url": f"{SID}/post/{p['id']}/" if SID else p["url"],
         "mainEntityOfPage": f"{SID}/post/{p['id']}/" if SID else None,
         "author": {"@type": "Organization", "name": CHAN_TITLE, "sameAs": TG_URL}}
    if imgs:
        j["image"] = imgs
    return {k: v for k, v in j.items() if v}

# ------------------------------------------------------------------ نوشتن فایل‌ها
def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def sync_dir(src: Path, dst: Path, *, prune=False):
    if not src.exists():
        return
    source_files = set()
    for f in src.rglob("*"):
        if f.is_dir() or f.name == ".DS_Store":
            continue
        rel = f.relative_to(src)
        source_files.add(rel)
        to = dst / rel
        to.parent.mkdir(parents=True, exist_ok=True)
        try:
            if to.exists() and to.stat().st_size == f.stat().st_size and \
               int(to.stat().st_mtime) >= int(f.stat().st_mtime):
                continue
        except OSError:
            pass
        shutil.copy2(f, to)

    # media/ آینهٔ آرشیو منبع است؛ مدیایی که از منبع حذف شده نباید در docs بماند.
    if prune and dst.exists():
        for f in dst.rglob("*"):
            if f.is_file() and f.relative_to(dst) not in source_files:
                f.unlink(missing_ok=True)
        for d in sorted((p for p in dst.rglob("*") if p.is_dir()), reverse=True):
            try:
                d.rmdir()
            except OSError:
                pass

def gen_og():
    try:
        from PIL import Image, ImageDraw, ImageFont
        import math
        W, Hh = 1200, 630
        img = Image.new("RGB", (W, Hh), (5, 5, 5))
        d = ImageDraw.Draw(img)
        web = (34, 34, 34); web2 = (24, 24, 24); red = (229, 49, 55)
        cx, cy = 1080, 80
        for ang in range(0, 360, 15):
            x = cx + 520 * math.cos(math.radians(ang)); y = cy + 520 * math.sin(math.radians(ang))
            d.line([(cx, cy), (x, y)], fill=web2, width=1)
        for r in range(90, 521, 86):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=web, width=1)
        for ox, oy in [(0, 0), (0, Hh)]:
            for ang in range(0, 91 if oy == 0 else 360, 10):
                pass
        for ang in range(150, 271, 10):
            x = 60 + 460 * math.cos(math.radians(ang)); y = 700 + 460 * math.sin(math.radians(ang))
            d.line([(60, 700), (x, y)], fill=web2, width=1)
        for r in range(80, 461, 76):
            d.arc([60 - r, 700 - r, 60 + r, 700 + r], 180, 270, fill=web, width=1)
        d.ellipse([1045, 55, 1115, 125], fill=(13, 13, 13), outline=(215, 215, 215), width=3)
        d.ellipse([1058, 118, 1102, 176], fill=(13, 13, 13), outline=(215, 215, 215), width=3)
        for mx, my in [(1071, 138), (1089, 138)]:
            pass
        d.polygon([(1070, 130), (1090, 130), (1080, 146)], fill=red)
        d.polygon([(1072, 149), (1088, 149), (1080, 160)], fill=red)
        try:
            f_big = ImageFont.truetype(str(ROOT / "assets/fonts/Vazirmatn-Bold.ttf"), 110)
            f_small = ImageFont.truetype(str(ROOT / "assets/fonts/Vazirmatn-Bold.ttf"), 42)
        except Exception:
            f_big = ImageFont.load_default(); f_small = ImageFont.load_default()
        d.text((70, 200), "SPIDERS_W3B", font=f_big, fill=(229, 229, 229))
        d.text((70, 340), "t.me/spiders_w3b", font=f_small, fill=red)
        d.text((70, 410), "// live web archive - auto-synced", font=f_small, fill=(120, 120, 120))
        d.line([(70, 500), (520, 500)], fill=(60, 60, 60), width=2)
        d.text((70, 520), "/// _", font=f_small, fill=(215, 215, 215))
        img.save(DOCS / "assets/og.png", optimize=True)
        log("og.png generated")
    except Exception as e:
        log("og.png skipped:", e)

def clean_stale_generated_pages(valid_post_ids, total_pages):
    """حذف خروجی‌های پست/صفحه‌بندی‌ای که دیگر در دیتای فعلی وجود ندارند."""
    post_root = DOCS / "post"
    if post_root.exists():
        for child in post_root.iterdir():
            if child.is_dir() and child.name.isdigit() and child.name not in valid_post_ids:
                shutil.rmtree(child)

    valid_pages = {str(i) for i in range(2, total_pages + 1)}
    page_root = DOCS / "page"
    if page_root.exists():
        for child in page_root.iterdir():
            if child.is_dir() and child.name.isdigit() and child.name not in valid_pages:
                shutil.rmtree(child)

    data_root = DOCS / "data"
    if data_root.exists():
        for path in data_root.glob("page-*.json"):
            match = re.fullmatch(r"page-(\d+)\.json", path.name)
            if match and match.group(1) not in valid_pages:
                path.unlink(missing_ok=True)


def build():
    (DOCS / "assets").mkdir(exist_ok=True)
    sync_dir(ROOT / "assets", DOCS / "assets")
    sync_dir(ROOT / "media", DOCS / "media", prune=True)

    pages = chunked(posts, PAGE_SIZE) or [[]]
    total = len(pages)

    # --- index + page/N ---
    for i, page_posts in enumerate(pages, start=1):
        cards = "\n".join(render_card(p, "" if i == 1 else "../../") for p in page_posts) or EMPTY_STATE
        rel = "" if i == 1 else "../../"
        feed_js = {"page": 1, "pages": total} if (i == 1 and total > 1) else None
        if i == 1:
            path_ = DOCS / "index.html"
            title, ogt, jl = TITLE, "website", jsonld_index(posts)
            out = shell(title=f"{TITLE} — {CHAN_TITLE}", desc=DESC, path="",
                        feed_html=cards, pager=pager_links(1, total),
                        og_type=ogt, jsonld=jl, feed_js=feed_js)
        else:
            path_ = DOCS / f"page/{i}/index.html"
            out = shell(title=f"{TITLE} — page {i}", desc=DESC, path=f"page/{i}/",
                        feed_html=cards, pager=pager_links(i, total, "../../"), rel="../../")
        write(path_, out)

    # data/page-N.json برای اسکرول بی‌پایان
    if total > 1:
        for i, page_posts in enumerate(pages, start=1):
            if i == 1:
                continue
            cards = "\n".join(render_card(p, "") for p in page_posts)
            write(DOCS / f"data/page-{i}.json",
                  json.dumps({"page": i, "pages": total, "html": cards}, ensure_ascii=False))
        (DOCS / "data/page-1.json").unlink(missing_ok=True)

    # --- post/<id>/ ---
    by_id = {p["id"]: p for p in posts}
    ids_sorted = sorted(by_id)
    for p in posts:
        pid = p["id"]
        card = render_card(p, "../../", single=True)
        older = ids_sorted[ids_sorted.index(pid) - 1] if pid in ids_sorted and ids_sorted.index(pid) > 0 else None
        newer = ids_sorted[ids_sorted.index(pid) + 1] if pid in ids_sorted and ids_sorted.index(pid) < len(ids_sorted) - 1 else None
        nav = []
        if older:
            nav.append(f'<a class="mono" href="../{older}/" rel="prev">← #{older}</a>')
        if newer:
            nav.append(f'<a class="mono" href="../{newer}/" rel="next">#{newer} →</a>')
        pnav = '<nav class="pager postnav">' + '<span class="sep mono"> · </span>'.join(nav) + '</nav>' if nav else ""
        ptitle = plain_text(p, 70) or f"post #{pid}"
        og_img = None
        for m in p["media"]:
            if m["type"] == "photo" and m.get("local") and SID:
                og_img = f"{SID}/{m['local']}"; break
        write(DOCS / f"post/{pid}/index.html",
              shell(title=f"{ptitle} · #{pid}", desc=plain_text(p, 200) or DESC,
                    path=f"post/{pid}/", feed_html=card, pager=pnav,
                    og_type="article", jsonld=jsonld_post(p), rel="../../"))

    # --- search.json ---
    sdata = [{"id": p["id"], "d": fmt_date(p.get("date", "")), "t": plain_text(p, 400)}
             for p in posts if plain_text(p)][:1500]
    write(DOCS / "search.json", json.dumps(sdata, ensure_ascii=False))

    # --- RSS ---
    items = []
    for p in posts[:30]:
        txt = plain_text(p, 300)
        title = txt.split("\n")[0][:90] or f"post #{p['id']}"
        encl = ""
        for m in p["media"]:
            if m["type"] == "photo" and m.get("local") and SID:
                f = DOCS / m["local"]
                ln = f.stat().st_size if f.exists() else 0
                encl = (f'<enclosure url="{SID}/{m["local"]}" length="{ln}" type="image/jpeg"/>')
                break
        items.append(f"""<item>
<title>{xesc(title)}</title>
<link>{SID}/post/{p['id']}/</link>
<guid isPermaLink="false">{xesc(p['url'])}</guid>
<pubDate>{rfc822(p.get('date',''))}</pubDate>
<description>{xesc(txt)}</description>
{encl}
</item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>{xesc(TITLE)}</title>
<link>{SID or TG_URL}</link>
<atom:link href="{SID}/feed.xml" rel="self" type="application/rss+xml"/>
<description>{xesc(DESC)}</description>
<language>{LANG}</language>
{''.join(items)}
</channel>
</rss>"""
    write(DOCS / "feed.xml", rss)

    # --- sitemap / robots / manifest / misc ---
    urls = []
    def sm(loc, lastmod=None, freq="hourly", pri="1.0"):
        if not SID:
            return
        lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        urls.append(f"<url><loc>{SID}/{loc}</loc>{lm}<changefreq>{freq}</changefreq><priority>{pri}</priority></url>")
    latest = (posts[0]["date"] or "")[:10] if posts else ""
    sm("", latest, "hourly", "1.0")
    for i in range(2, total + 1):
        sm(f"page/{i}/", freq="daily", pri="0.6")
    for p in posts:
        sm(f"post/{p['id']}/", (p["date"] or "")[:10], "monthly", "0.8")
    write(DOCS / "sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>")
    write(DOCS / "robots.txt",
          "User-agent: *\nAllow: /\nDisallow: /data/\n" +
          (f"\nSitemap: {SID}/sitemap.xml\n" if SID else ""))
    write(DOCS / "site.webmanifest", json.dumps({
        "name": TITLE, "short_name": TITLE, "description": DESC,
        "start_url": "./index.html", "display": "minimal-ui",
        "background_color": "#050505", "theme_color": "#050505", "dir": DIR, "lang": LANG},
        ensure_ascii=False, indent=1))
    write(DOCS / ".nojekyll", "")
    if CFG.get("cname"):
        write(DOCS / "CNAME", CFG["cname"])

    clean_stale_generated_pages({str(pid) for pid in by_id}, total)
    gen_og()
    log(f"DONE: {len(posts)} posts · {total} feed pages · site_url={SID or '(relative)'}")

if __name__ == "__main__":
    build()