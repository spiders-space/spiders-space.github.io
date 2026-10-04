#!/usr/bin/env python3
"""
fetch_channel.py — همگام‌سازی آرشیو کانال تلگرام عمومی از طریق نسخهٔ وب
                  (t.me/s/<channel>)

خروجی:
  data/posts.json    → همهٔ پست‌ها (جدید→قدیم)
  data/channel.json  → متادیتای کانال (نام، توضیح، آواتار)
  media/             → مدیاهای دانلودشده (عکس، ویدیو، صوت، فایل)

در هر اجرا تاریخچهٔ قابل‌دسترسی کانال کامل پیمایش می‌شود تا پست‌های حذف‌شده هم
تشخیص داده شوند. فقط پس از پیمایش موفق و کامل، رکوردهای ناپدیدشده حذف می‌شوند؛
در صورت خطا یا محدود بودن MAX_PAGES، آرشیو قبلی حفظ می‌شود.
استیکرها و ری‌اکشن‌ها (و پیام‌های سرویسی مثل "Channel created") نادیده گرفته می‌شوند.
"""
import json, os, re, sys, time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT   = Path(__file__).resolve().parent.parent
CFG    = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

CHANNEL    = os.environ.get("TG_CHANNEL", CFG["channel"])
MAX_PAGES  = int(os.environ.get("MAX_PAGES", CFG.get("max_pages", 0)))
MAX_MEDIA  = float(os.environ.get("MAX_MEDIA_MB", CFG.get("max_media_mb", 45))) * 1024 * 1024

BASE       = f"https://t.me/s/{CHANNEL}"
DATA_DIR   = ROOT / "data"
MEDIA_DIR  = ROOT / "media"
POSTS_JSON = DATA_DIR / "posts.json"
CHAN_JSON  = DATA_DIR / "channel.json"
DATA_DIR.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)
MEDIA_INDEX = None

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
})

# پیام‌های سرویسی تلگرام که پست نیستند
SERVICE_RX = re.compile(
    r"(^Channel created$|^Channel photo updated$|^Channel photo removed$|"
    r"^Channel name changed|^Messages in this channel|pinned \"|pinned a )", re.I)

BG_URL_RX = re.compile(r"url\(\s*['\"]?([^'\")]+)")
CLS = lambda pat: re.compile(pat)

def log(*a): print("[fetch]", *a, flush=True)

def bg_url(style: str):
    m = BG_URL_RX.search(style or "")
    return m.group(1) if m else None

def emoji_to_text(el):
    """تبدیل <img class="emoji" alt="😀"> به کاراکتر ایموجی."""
    for img in el.find_all("img", class_="emoji"):
        img.replace_with(img.get("alt", ""))

def inner_html(el) -> str:
    return el.decode_contents().strip() if el else ""

def is_channel_page(soup) -> bool:
    """رد کردن صفحات خطا/محدودیت که ممکن است با status=200 برگردند."""
    return bool(soup.select_one(".tgme_channel_info, .tgme_widget_message"))

# ----------------------------------------------------------------------------- دانلود مدیا
CT_EXT = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
    "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
    "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "audio/opus": ".ogg", "audio/mp4": ".m4a",
    "audio/wav": ".wav", "application/pdf": ".pdf", "application/zip": ".zip",
    "text/plain": ".txt",
}

def download(url: str, stem: str):
    """دانلود به media/ و برگرداندن نام فایل؛ اگر بزرگ‌تر از سقف یا ناموفق → None."""
    global MEDIA_INDEX
    if not url:
        return None
    # اسکن کامل تاریخچه در هر اجرا انجام می‌شود؛ فایل‌های قبلی را قبل از
    # درخواست شبکه پیدا کن تا مدیای قدیمی دوباره دانلود نشود.
    if MEDIA_INDEX is None:
        MEDIA_INDEX = {}
        for candidate in MEDIA_DIR.iterdir():
            if candidate.is_file() and "." in candidate.name:
                MEDIA_INDEX[candidate.name.rsplit(".", 1)[0]] = candidate.name
    cached = MEDIA_INDEX.get(stem)
    if cached:
        cached_path = MEDIA_DIR / cached
        if cached_path.is_file() and cached_path.stat().st_size > 0:
            return cached
        MEDIA_INDEX.pop(stem, None)
    try:
        r = S.get(url, timeout=90, stream=True)
    except Exception as e:
        log("dl-netfail", url[:70], e); return None
    if r.status_code != 200:
        log("dl-http", r.status_code, url[:80]); return None
    cl = r.headers.get("Content-Length")
    if cl and int(cl) > MAX_MEDIA:
        log("dl-skip-too-big", f"{int(cl)/1e6:.1f}MB", url[:60]); return None

    ext = os.path.splitext(url.split("?")[0])[1].lower()
    if not re.fullmatch(r"\.\w{2,5}", ext or ""):
        ext = CT_EXT.get(r.headers.get("Content-Type", "").split(";")[0].strip(), "")
    if not ext:
        ext = ".bin"
    name = f"{stem}{ext}"
    path = MEDIA_DIR / name
    if path.exists() and path.stat().st_size > 0:
        MEDIA_INDEX[stem] = name
        return name  # از قبل داریم
    size = 0
    try:
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                size += len(chunk)
                if size > MAX_MEDIA:
                    f.close(); path.unlink(missing_ok=True)
                    log("dl-abort-too-big", name); return None
                f.write(chunk)
    except Exception as e:
        path.unlink(missing_ok=True); log("dl-fail", name, e); return None
    MEDIA_INDEX[stem] = name
    return name

def media_item(kind, url, stem, thumb_url=None, extra=None):
    item = {"type": kind, "url": url}
    local = download(url, stem)
    if local:
        item["local"] = f"media/{local}"
    if thumb_url:
        t = download(thumb_url, f"{stem}_thumb")
        if t:
            item["thumb"] = f"media/{t}"
        else:
            item["thumb_remote"] = thumb_url
    if extra:
        item.update(extra)
    return item

# ----------------------------------------------------------------------------- پارس هر پیام
def parse_message(el):
    dp = el.get("data-post", "")
    if "/" not in dp:
        return None
    post_id = int(dp.split("/")[-1])
    purl = f"https://t.me/{dp}"

    # --- تاریخ / بازدید / ویرایش ---
    t = el.find("time", attrs={"datetime": True})
    date_iso = t["datetime"] if t else None
    date_txt = t.get_text(strip=True) if t else ""
    views_el = el.find(class_=CLS(r"message_views"))
    views = views_el.get_text(strip=True) if views_el else None
    edited = bool(el.find(class_=CLS(r"edited")))

    # --- متن ---
    txt_el = el.find(class_=CLS(r"message_text"))
    if txt_el:
        emoji_to_text(txt_el)
    text_html = inner_html(txt_el)

    # --- فوروارد ---
    fwd_el = el.find(class_=CLS(r"forwarded_from"))
    fwd = None
    if fwd_el:
        name_el = fwd_el.find(class_=CLS(r"forwarded_from_name"))
        a = fwd_el.find("a", href=True)
        fwd = {"name": name_el.get_text(strip=True) if name_el else fwd_el.get_text(" ", strip=True),
               "url": a["href"] if a else None}

    # --- ریپلای ---
    reply = None
    rep_el = el.find(class_=CLS(r"message_reply"))
    if rep_el:
        a = rep_el.find("a", href=True)
        auth = rep_el.find(class_=CLS(r"reply_author"))
        rtxt = rep_el.find(class_=CLS(r"reply_text"))
        reply = {"url": a["href"] if a else None,
                 "author": auth.get_text(strip=True) if auth else None,
                 "text": rtxt.get_text(" ", strip=True) if rtxt else None}

    # --- مدیاها ---
    media = []

    for ph in el.find_all(class_=CLS(r"photo_wrap")):
        url = bg_url(ph.get("style", ""))
        if url:
            media.append(media_item("photo", url, f"{post_id}_{len(media)+1}"))

    seen_videos = set()

    def add_video(container, vtag, suffix="+vid"):
        src = vtag.get("src")
        if not src or src in seen_videos:
            return
        seen_videos.add(src)
        # تامنیل و مدت معمولاً خواهرِ wrap داخل video_player هستند
        player = container
        pin = container.parent
        for cand in (container, pin, getattr(pin, "parent", None)):
            if cand is not None and hasattr(cand, "get") and \
               "video_player" in " ".join(cand.get("class", [])):
                player = cand
                break
        thumb_el = player.find(class_=CLS(r"video_thumb"))
        thumb = bg_url(thumb_el.get("style", "")) if thumb_el else None
        dur_el = player.find(class_=CLS(r"video_duration"))
        pclasses = " ".join(player.get("class", []))
        extra = {"duration": dur_el.get_text(strip=True) if dur_el else None}
        if "rounded" in pclasses or "round " in pclasses + " ":
            extra["round"] = True
        media.append(media_item("video", src, f"{post_id}_{len(media)+1}{suffix}",
                                thumb_url=thumb, extra=extra))

    for vw in el.find_all(class_=CLS(r"video_wrap")):
        v = vw.find("video", src=True)
        if v:
            add_video(vw, v)
    # ویدیوهایی که بیرون از video_wrap هستند (پیش‌نمایش لینک و…)
    for vtag in el.find_all("video", src=True):
        add_video(vtag, vtag, suffix="+lpv")

    for au in el.find_all("audio", src=True):
        box = au.find_parent(class_=CLS(r"(audio|voice)_player")) or au.parent
        bcls = " ".join(box.get("class", [])) if hasattr(box, "get") else ""
        kind = "voice" if "voice" in bcls else "audio"
        title_el = box.find(class_=CLS(r"(audio|voice)_title"))
        perf_el  = box.find(class_=CLS(r"audio_performer"))
        dur_el   = box.find(class_=CLS(r"duration"))
        media.append(media_item(kind, au["src"], f"{post_id}_{len(media)+1}+au",
                    extra={"title": title_el.get_text(strip=True) if title_el else None,
                           "performer": perf_el.get_text(strip=True) if perf_el else None,
                           "duration": dur_el.get_text(strip=True) if dur_el else None}))

    seen_doc = set()
    for a in el.find_all("a", href=True):
        cls = " ".join(a.get("class", []))
        if "document" not in cls and not a.find_parent(class_=CLS(r"document_wrap")):
            continue
        if a["href"] in seen_doc:
            continue
        seen_doc.add(a["href"])
        title_el = a.find(class_=CLS(r"document_title"))
        extra_el = a.find(class_=CLS(r"document_extra"))
        media.append(media_item("document", a["href"], f"{post_id}_{len(media)+1}+doc",
                    extra={"title": title_el.get_text(strip=True) if title_el else a.get_text(" ", strip=True),
                           "size": extra_el.get_text(strip=True) if extra_el else None}))

    # استیکرها عمداً نادیده گرفته می‌شوند (قول کاربر: بدون محتوای اضافی)
    # ری‌اکشن‌ها هم اصلاً پارس نمی‌شوند.

    # --- نظرسنجی ---
    poll = None
    poll_el = el.find(class_=CLS(r"message_poll\b"))
    if poll_el:
        q = poll_el.find(class_=CLS(r"poll_question"))
        pt = poll_el.find(class_=CLS(r"poll_type"))
        opts = []
        for opt in poll_el.find_all(class_=CLS(r"\bpoll_option\b")):
            ot = opt.find(class_=CLS(r"poll_option_text"))
            op = opt.find(class_=CLS(r"poll_option_percent"))
            opts.append({"text": ot.get_text(strip=True) if ot else "",
                         "percent": op.get_text(strip=True) if op else ""})
        v = poll_el.find(class_=CLS(r"poll_voters"))
        poll = {"question": q.get_text(strip=True) if q else "",
                "type": pt.get_text(strip=True) if pt else "",
                "options": opts,
                "voters": v.get_text(strip=True) if v else ""}

    # --- پیش‌نمایش لینک ---
    lp = None
    lp_el = el.find("a", class_=CLS(r"link_preview"))
    if lp_el:
        site = lp_el.find(class_=CLS(r"link_preview_site_name"))
        tit  = lp_el.find(class_=CLS(r"link_preview_title"))
        des  = lp_el.find(class_=CLS(r"link_preview_description"))
        img  = lp_el.find("i", class_=CLS(r"link_preview_image"))
        vid  = lp_el.find("video", src=True)
        lp = {"url": lp_el.get("href"),
              "site": site.get_text(strip=True) if site else None,
              "title": tit.get_text(strip=True) if tit else None,
              "desc": des.get_text(strip=True) if des else None,
              "image": bg_url(img.get("style", "")) if img else None}

    # پیام سرویسی؟
    if not media and text_html and SERVICE_RX.search(re.sub(r"<[^>]+>", "", text_html).strip()):
        return None
    # پیام خالی (مثلاً فقط استیکر بود)?
    if not media and not text_html.strip() and not poll and not lp:
        return None

    return {"id": post_id, "url": purl, "date": date_iso, "date_txt": date_txt,
            "views": views, "edited": edited, "text_html": text_html,
            "media": media, "poll": poll, "link_preview": lp,
            "reply": reply, "fwd": fwd}

# ----------------------------------------------------------------------------- متادیتای کانال
def fetch_channel_meta():
    r = S.get(BASE, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    if not is_channel_page(soup):
        raise RuntimeError(f"Telegram returned an unexpected channel page for {CHANNEL}")
    title_el = soup.select_one(".tgme_channel_info_header_title")
    desc_el  = soup.select_one(".tgme_channel_info_description")
    counters = [c.get_text(strip=True) for c in soup.select(".tgme_channel_info_counter")]
    avatar = None
    ph = soup.select_one(".tgme_page_photo")
    if ph:
        img = ph.find("img", src=True)
        if img:
            avatar = {"url": img["src"]}
            local = download(img["src"], "avatar")
            if local:
                avatar["local"] = f"media/{local}"
    meta = {"title": title_el.get_text(strip=True) if title_el else CFG.get("site_title", CHANNEL),
            "desc": desc_el.get_text(" ", strip=True) if desc_el else "",
            "counters": counters, "avatar": avatar,
            "handle": CHANNEL, "url": f"https://t.me/{CHANNEL}"}
    CHAN_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta

# ----------------------------------------------------------------------------- دریافت تاریخچهٔ کامل کانال
def scan_channel(existing):
    """برگرداندن (پست‌های دیده‌شده، پیمایش کامل بود یا نه).

    وجود پیام در خود صفحه معیار حضور آن در کانال است؛ اگر parsing یک پیام
    قدیمی موقتاً شکست بخورد یا پیام از نوعی باشد که آرشیو نمی‌کند، نسخهٔ قبلی
    آن نگه داشته می‌شود. این کار مانع حذف اشتباه بر اثر تغییر markup تلگرام است.
    """
    found = {}
    before, pages = None, 0

    while True:
        url = BASE + (f"?before={before}" if before else "")
        try:
            r = S.get(url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            log("page-fail", url, e)
            return found, False

        soup = BeautifulSoup(r.text, "lxml")
        if not is_channel_page(soup):
            log("page-invalid → keep existing archive", url)
            return found, False

        msgs = [m for m in soup.select(".tgme_widget_message") if m.get("data-post")]
        if not msgs:
            log("end of channel history")
            return found, True

        ids = []
        skipped_sticker = 0
        for m in msgs:
            try:
                pid = int(m["data-post"].split("/")[-1])
            except (TypeError, ValueError, IndexError):
                log("invalid data-post → keep existing archive")
                return found, False
            ids.append(pid)

            if m.find(class_=CLS(r"sticker")) and not m.find(class_=CLS(r"message_text")):
                sticker_only = not any([m.find("video", src=True), m.find("audio", src=True),
                                        m.find(class_=CLS(r"photo_wrap"))])
                if sticker_only:
                    skipped_sticker += 1

            try:
                post = parse_message(m)
            except Exception as e:
                log("parse-fail", pid, e)
                post = None

            if post:
                found[pid] = post
            elif pid in existing:
                # پیام هنوز در کانال است؛ حتی اگر نوع آن قابل‌آرشیو نباشد،
                # رکورد قبلی را به‌عنوان محتوای موجود نگه می‌داریم.
                found[pid] = existing[pid]

        pages += 1
        log(f"page {pages}: messages {min(ids)}…{max(ids)}  archived={len(found)}  stickers={skipped_sticker}")

        if MAX_PAGES and pages >= MAX_PAGES:
            log("MAX_PAGES reached → partial scan; existing posts will be preserved")
            return found, False

        next_before = min(ids)
        if before is not None and next_before >= before:
            log("pagination made no progress → keep existing archive")
            return found, False
        before = next_before
        time.sleep(1.0)  # ادب درخواست


def remove_deleted_media(deleted_ids, existing, kept_posts):
    """پاک‌کردن مدیای اختصاصی پست‌های حذف‌شده از آرشیو محلی."""
    if not deleted_ids:
        return

    kept_refs = set()
    for post in kept_posts.values():
        for item in post.get("media", []):
            for key in ("local", "thumb"):
                if item.get(key):
                    kept_refs.add(Path(item[key]).name)

    deleted_refs = set()
    prefixes = tuple(f"{pid}_" for pid in deleted_ids)
    for pid in deleted_ids:
        for item in existing[pid].get("media", []):
            for key in ("local", "thumb"):
                if item.get(key):
                    deleted_refs.add(Path(item[key]).name)

    removed = 0
    for path in MEDIA_DIR.iterdir():
        if not path.is_file() or path.name in kept_refs:
            continue
        if path.name in deleted_refs or (prefixes and path.name.startswith(prefixes)):
            path.unlink(missing_ok=True)
            removed += 1
    if removed:
        log(f"removed {removed} orphaned media file(s) for deleted posts")


# ----------------------------------------------------------------------------- حلقهٔ اصلی
def main():
    existing = {p["id"]: p for p in json.loads(POSTS_JSON.read_text(encoding="utf-8"))} \
        if POSTS_JSON.exists() else {}
    log(f"channel={CHANNEL}  known={len(existing)}  max_pages={MAX_PAGES or '∞'}  max_media={MAX_MEDIA/1e6:.0f}MB")

    meta = fetch_channel_meta()
    log("meta:", meta["title"], "|", ", ".join(meta["counters"]) or "-")

    scanned, complete = scan_channel(existing)
    if complete:
        deleted_ids = set(existing) - set(scanned)
        if deleted_ids:
            log(f"reconciled: {len(deleted_ids)} post(s) removed from Telegram")
            remove_deleted_media(deleted_ids, existing, scanned)
        db = scanned
    else:
        # خطا، pagination نامعتبر یا MAX_PAGES: دادهٔ قبلی را حذف نکن.
        db = dict(existing)
        db.update(scanned)
        log("incomplete scan → existing posts preserved")

    posts = sorted(db.values(), key=lambda p: p["id"], reverse=True)
    POSTS_JSON.write_text(json.dumps(posts, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"DONE: {len(posts)} posts")

if __name__ == "__main__":
    main()
