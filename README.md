# 🕷 SPIDERS_W3B — سایت وب کانال تلگرام

[![pages-build-deployment](https://github.com/spiders-space/spiders-space.github.io/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/spiders-space/spiders-space.github.io/actions/workflows/pages/pages-build-deployment)

آرشیو زندهٔ **[t.me/spiders_w3b](https://t.me/spiders_w3b)** روی GitHub Pages.
هر ۳۰ دقیقه GitHub Actions تاریخچهٔ عمومی کانال را کامل بررسی می‌کند، پست‌های جدید و ویرایش‌ها را همگام می‌سازد و پست‌هایی را که از کانال حذف شده‌اند از داده‌ها و خروجی سایت هم پاک می‌کند — شبیه یک تایم‌لاین توییتر، با تم تار عنکبوت/دارک‌وب.
اگر دریافت تاریخچه ناقص شود (مثلاً خطای موقت تلگرام یا فعال بودن `MAX_PAGES`)، داده‌های قبلی پاک نمی‌شوند تا خطای شبکه باعث حذف اشتباهی آرشیو نشود.

**پشتیبانی مدیا:** عکس و آلبوم 🖼 · ویدیو و ویدیومسج 🎬 · صوت/موزیک و ویس 🎧 · فایل/سند با دکمهٔ دانلود 📎 · نظرسنجی 📊 · پیش‌نمایش لینک 🔗 · ریپلای و فوروارد · ایموجی‌های متنی ✅
**حذف‌شده (عمدی):** ری‌اکشن‌ها ❌ · استیکرها ❌ · پیام‌های سرویسی ❌

**امکانات:** SEO کامل (Open Graph · JSON-LD · sitemap.xml · RSS · صفحهٔ مستقل هر پست با canonical) · جستجوی فارسی (دکمهٔ `/`) · اسکرول بی‌پایان + صفحه‌بندی استاتیک · لایت‌باکس گالری · کپی لینک هر پست · اسپویلر کلیک‌شونده · بدون کوکی و ردیاب · افکت CRT با دکمهٔ `fx` برای خاموشی.

> 🧩 **CSS/JS این‌لاین:** استایل و اسکریپت موقع build داخل خودِ HTML قرار می‌گیرند — پس هیچ فایل جدایی برای ۴۰۴ خوردن روی Pages وجود ندارد و حتی با آپلود دستی هم سایت همیشه استایل‌دار بالا می‌آید. (فایل‌های `assets/css` و `assets/js` به‌عنوان ورودی build لازم‌اند و `assets/fonts` برای فونت.)

---

## راه‌اندازی (۱۰ دقیقه)

### ۱) ساخت ریپو
یک ریپوی **public** در GitHub بساز (مثلاً `spiders-w3b`) و همهٔ فایل‌های همین پوشه را داخلش push کن:

```bash
git init && git add -A && git commit -m "🕷 init"
git branch -M main
git remote add origin git@github.com:USERNAME/spiders-w3b.git
git push -u origin main
```

### ۲) فعال‌سازی GitHub Pages
`Settings → Pages → Build and deployment`:
- Source: **Deploy from a branch**
- Branch: **main** و پوشهٔ **/docs** → Save

### ۳) دسترسی نوشتن به Actions
ورک‌فلو خودش با `permissions: contents: write` دسترسی لازم را می‌گیرد، پس **معمولاً نیازی به تغییر تنظیم نیست** — این مرحله را رد کن.

اگر هنگام اجرای اکشن خطای `Resource not accessible by integration` گرفتی (معمولاً وقتی ریپو داخل سازمانی است که GITHUB_TOKEN را قفل کرده):

1. برو به `github.com/settings/personal-access-tokens` → **Generate new token** (Fine-grained)
   - Repository access: فقط ریپوی سایت · Permissions → **Contents: Read and write**
2. در ریپو: `Settings → Secrets and variables → Actions → New repository secret`
   - Name: `GH_PAT` · مقدار: توکن کپی‌شده
3. دوباره اکشن را اجرا کن — ورک‌فلو خودکار از این توکن استفاده می‌کند.

### ۴) اجرای اول
`Actions → 🕷 update web → Run workflow`
اجرای اول کل تاریخچهٔ کانال + مدیا را آرشیو می‌کند (کمی طول می‌کشد). در هر اجرای بعدی هم تاریخچهٔ عمومی دوباره پیمایش می‌شود تا علاوه بر پست‌های تازه و ویرایش‌شده، پست‌های حذف‌شده از کانال نیز از آرشیو و صفحات سایت حذف شوند. اگر اسکن کامل نشود، پست‌های قبلی حفظ می‌شوند.

سایت تو اینجاست: **`https://USERNAME.github.io/spiders-w3b/`**

> نکته: آدرس دقیق و canonical لینک‌ها به‌صورت خودکار از نام ریپو ساخته می‌شود؛ نیازی به تنظیم نیست. اگر دامنهٔ اختصاصی داری، در `config.json` مقدار `cname` و `site_url` را بگذار و دوباره push کن.

---

## تنظیمات (`config.json`)

| کلید | پیش‌فرض | توضیح |
|---|---|---|
| `channel` | `spiders_w3b` | آیدی کانال عمومی (بدون @) |
| `page_size` | `25` | تعداد پست در هر صفحهٔ فید |
| `max_media_mb` | `45` | سقف حجم دانلود هر مدیا (مگابایت). بزرگ‌ترها فقط لینک می‌شوند |
| `max_pages` | `0` | `0` = پیمایش کل تاریخچه و همگام‌سازی حذف‌ها؛ مقدار محدود، اسکن ناقص است و حذف انجام نمی‌شود |
| `site_url` | `""` | در CI خودکار پر می‌شود؛ برای دامنهٔ اختصاصی دستی بگذار |
| `cname` | `""` | دامنهٔ اختصاصی → فایل CNAME ساخته می‌شود |

زمان به‌روزرسانی را هم می‌توانی در `.github/workflows/update.yml` با `cron` عوض کنی (پیش‌فرض: هر ۳۰ دقیقه).

---

## ساختار

```
├── .github/workflows/update.yml   # اکشنِ همگام‌سازی + بازسازی
├── config.json                    # تنظیمات
├── scripts/
│   ├── fetch_channel.py           # همگام‌سازی کامل t.me/s + تشخیص حذف و دانلود مدیا
│   └── build_site.py              # رندر HTML ،RSS ،sitemap ،OG و…
├── assets/ (css · js · img · fonts)
├── data/   (posts.json · channel.json)   ← توسط اکشن آپدیت می‌شود
├── media/  (آرشیو مدیا)                  ← توسط اکشن آپدیت می‌شود
└── docs/   (خروجی سایت ← منبع GitHub Pages)
```

## اجرای محلی

```bash
pip install -r requirements.txt
python scripts/fetch_channel.py      # MAX_PAGES=2 برای تست سریع
python scripts/build_site.py
python -m http.server -d docs 8000   # http://localhost:8000
```

## نکتهٔ حجم مخزن

مدیاها داخل خود ریپو آرشیو می‌شوند (لینک‌های CDN تلگرام موقتی‌اند). GitHub Pages سایت‌های تا ~۱GB را توصیه می‌کند و فایل‌ها نمی‌توانند از ۱۰۰MB بزرگ‌تر باشند. اگر رشد زیاد شد: `max_media_mb` را کم کن یا مدیاهای خیلی قدیمی را از `media/` پاک کن — پست‌ها و متن‌ها می‌مانند.

## حریم خصوصی

فقط کانال‌های **عمومی** پشتیبانی می‌شوند (دقیقاً همان چیزی که در `t.me/s/<channel>` عمومی است). بدون هیچ کوکی/ردیاب/اسکریپت شخص‌ثالث.

— 🕸 با GitHub Actions بافته می‌شود.
