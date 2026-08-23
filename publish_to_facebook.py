import json
import os
import requests

TOKEN = os.environ["FACEBOOK_PAGE_TOKEN"]

GRAPH_URL = "https://graph.facebook.com/v26.0/me/photos"

BASE_IMAGE_URL = "https://nownex.github.io/nownex/"


# -----------------------------
# هاشتاقات حسب القسم
# -----------------------------

HASHTAGS = {
    "AI": "#NOWNEX #الذكاء_الاصطناعي #AI #تقنية #أخبار_التقنية",
    "Technology": "#NOWNEX #تقنية #تكنولوجيا #أخبار_التقنية",
    "Cars": "#NOWNEX #سيارات #أخبار_السيارات #تكنولوجيا",
    "Entertainment": "#NOWNEX #ترفيه #أخبار_الترفيه",
    "Facts": "#NOWNEX #حقائق #هل_تعلم #معلومات",
    "Products": "#NOWNEX #منتجات #تقنية #مراجعات",
}


# -----------------------------
# قراءة الأخبار
# -----------------------------

with open("news.json", "r", encoding="utf-8") as f:
    data = json.load(f)

news = data.get("news", [])

if not news:
    raise SystemExit("No news found")


# -----------------------------
# قراءة سجل الأخبار المنشورة
# -----------------------------

posted_file = "posted_news.json"

if os.path.exists(posted_file):
    with open(posted_file, "r", encoding="utf-8") as f:
        posted_news = json.load(f)
else:
    posted_news = {}


# -----------------------------
# اختيار أحدث خبر جديد من كل قسم
# -----------------------------

latest_by_category = {}

for article in news:

    category = (
        article.get("category")
        or article.get("section")
        or "Other"
    )

    link = article.get("link", "").strip()

    title = (
        article.get("title_ar")
        or article.get("title")
        or ""
    ).strip()

    # مفتاح فريد للخبر
    # الرابط هو الأفضل، والعنوان احتياط
    news_id = link or title

    if not news_id:
        continue

    # تجاهل الخبر إذا سبق نشره
    if news_id in posted_news:
        continue

    # نأخذ خبرًا واحدًا جديدًا فقط من كل قسم
    if category not in latest_by_category:
        latest_by_category[category] = article


# -----------------------------
# لا توجد أخبار جديدة
# -----------------------------

if not latest_by_category:
    print("No new news to publish.")
    raise SystemExit(0)


print(
    "New categories:",
    list(latest_by_category.keys())
)


# -----------------------------
# نشر الأخبار
# -----------------------------

for category, article in latest_by_category.items():

    title = (
        article.get("title_ar")
        or article.get("title")
        or ""
    ).strip()

    summary = (
        article.get("summary_ar")
        or article.get("summary")
        or article.get("description")
        or ""
    ).strip()

    link = article.get("link", "").strip()

    image = (
        article.get("image")
        or article.get("image_url")
        or ""
    ).strip()


    # -------------------------
    # تحديد الهاشتاقات
    # -------------------------

    hashtags = HASHTAGS.get(
        category,
        "#NOWNEX #أخبار #أخبار_اليوم"
    )


    # -------------------------
    # نص المنشور
    # -------------------------

    message = (
        f"📰 {title}\n\n"
        f"{summary}\n\n"
        f"{hashtags}\n\n"
        f"🔗 اقرأ المزيد:\n{link}"
    )


    # -------------------------
    # تجهيز رابط الصورة
    # -------------------------

    if image:

        if not image.startswith("http"):

            image = (
                BASE_IMAGE_URL
                + image.lstrip("/")
            )


        print(
            f"Publishing image for category: {category}"
        )

        response = requests.post(
            GRAPH_URL,
            data={
                "url": image,
                "caption": message,
                "access_token": TOKEN,
            },
            timeout=60,
        )

    else:

        print(
            f"No image for {category}, "
            "publishing text instead."
        )

        feed_url = (
            "https://graph.facebook.com/"
            "v26.0/me/feed"
        )

        response = requests.post(
            feed_url,
            data={
                "message": message,
                "access_token": TOKEN,
            },
            timeout=60,
        )


    # -------------------------
    # التحقق من Facebook
    # -------------------------

    if not response.ok:

        raise SystemExit(
            f"Facebook error for "
            f"{category}: {response.text}"
        )


    # -------------------------
    # تسجيل الخبر بعد نجاح النشر
    # -------------------------

    news_id = link or title

    posted_news[news_id] = {
        "title": title,
        "category": category
    }


    print(
        f"Published successfully: "
        f"{category} - {title}"
    )


# -----------------------------
# حفظ سجل الأخبار المنشورة
# -----------------------------

with open(
    posted_file,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        posted_news,
        f,
        ensure_ascii=False,
        indent=2
    )


print(
    f"Saved {len(posted_news)} published news."
)
