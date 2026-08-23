import json
import os
import requests

TOKEN = os.environ["FACEBOOK_PAGE_TOKEN"]

GRAPH_VERSION = "v26.0"

PHOTO_URL = (
    f"https://graph.facebook.com/"
    f"{GRAPH_VERSION}/me/photos"
)

FEED_URL = (
    f"https://graph.facebook.com/"
    f"{GRAPH_VERSION}/me/feed"
)

BASE_IMAGE_URL = "https://nownex.github.io/nownex/"


# =========================================================
# هاشتاقات حسب القسم
# =========================================================

HASHTAGS = {
    "AI":
        "#NOWNEX #الذكاء_الاصطناعي #AI #تقنية #أخبار_التقنية",

    "Technology":
        "#NOWNEX #تقنية #تكنولوجيا #أخبار_التقنية",

    "Cars":
        "#NOWNEX #سيارات #أخبار_السيارات #تكنولوجيا",

    "Entertainment":
        "#NOWNEX #ترفيه #أخبار_الترفيه",

    "World":
        "#NOWNEX #العالم #أخبار_العالم #أخبار_اليوم",

    "Facts":
        "#NOWNEX #حقائق #هل_تعلم #معلومات",

    "Products":
        "#NOWNEX #منتجات #تقنية #مراجعات",

    "Other":
        "#NOWNEX #أخبار #أخبار_اليوم",
}


# =========================================================
# قراءة الأخبار
# =========================================================

with open(
    "news.json",
    "r",
    encoding="utf-8"
) as f:

    data = json.load(f)


news = data.get("news", [])

if not news:
    raise SystemExit("No news found")


# =========================================================
# قراءة سجل الأخبار المنشورة
# =========================================================

posted_file = "posted_news.json"

if os.path.exists(posted_file):

    try:

        with open(
            posted_file,
            "r",
            encoding="utf-8"
        ) as f:

            posted_news = json.load(f)

        if not isinstance(posted_news, dict):
            posted_news = {}

    except Exception:

        posted_news = {}

else:

    posted_news = {}


print(
    f"Previously published: "
    f"{len(posted_news)}"
)


# =========================================================
# اختيار أحدث خبر جديد من كل قسم
# =========================================================

latest_by_category = {}


for article in news:

    category = (
        article.get("category")
        or article.get("section")
        or "Other"
    )

    category = str(category).strip()

    link = (
        article.get("link")
        or ""
    ).strip()

    title = (
        article.get("title_ar")
        or article.get("title")
        or ""
    ).strip()

    if not link and not title:
        continue


    # الرابط هو المعرف الأساسي للخبر
    # والعنوان احتياط
    news_id = link or title


    # =============================================
    # منع التكرار
    # =============================================

    if news_id in posted_news:

        print(
            f"SKIP already published: "
            f"{title}"
        )

        continue


    # نأخذ خبرًا واحدًا فقط من كل قسم
    if category not in latest_by_category:

        latest_by_category[category] = article


# =========================================================
# لا توجد أخبار جديدة
# =========================================================

if not latest_by_category:

    print("No new news to publish.")
    raise SystemExit(0)


print(
    "New categories:",
    list(latest_by_category.keys())
)


# =========================================================
# دالة حفظ سجل النشر
#
# نحفظ بعد كل خبر ناجح أيضًا، وليس فقط في النهاية.
# =========================================================

def save_posted_news():

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


# =========================================================
# نشر الأخبار
# =========================================================

success_count = 0
failed_count = 0


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

    link = (
        article.get("link")
        or ""
    ).strip()

    image = (
        article.get("image")
        or article.get("image_url")
        or ""
    ).strip()


    # =============================================
    # معرف الخبر
    # =============================================

    news_id = link or title


    print("")
    print(
        "=========================================="
    )

    print(
        f"Publishing category: {category}"
    )

    print(
        f"Title: {title}"
    )

    print(
        "=========================================="
    )


    # =============================================
    # الهاشتاقات
    # =============================================

    hashtags = HASHTAGS.get(
        category,
        HASHTAGS["Other"]
    )


    # =============================================
    # نص المنشور
    # =============================================

    message = (
        f"📰 {title}\n\n"
        f"{summary}\n\n"
        f"{hashtags}\n\n"
        f"🔗 اقرأ المزيد:\n{link}"
    )


    # =============================================
    # تجهيز الصورة
    # =============================================

    if image:

        if not image.startswith("http"):

            image = (
                BASE_IMAGE_URL
                + image.lstrip("/")
            )


    # =============================================
    # محاولة النشر
    # =============================================

    try:

        if image:

            print(
                f"Publishing image for category: "
                f"{category}"
            )

            response = requests.post(
                PHOTO_URL,
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

            response = requests.post(
                FEED_URL,
                data={
                    "message": message,
                    "access_token": TOKEN,
                },
                timeout=60,
            )


        # =========================================
        # نجاح النشر
        # =========================================

        if response.ok:

            print(
                f"Published successfully: "
                f"{category} - {title}"
            )


            # =====================================
            # تسجيل الخبر فور نجاحه
            # =====================================

            result = {}

            try:
                result = response.json()
            except Exception:
                pass


            posted_news[news_id] = {

                "title": title,

                "category": category,

                "facebook_id":
                    result.get("id", ""),

                "published_at":
                    __import__("datetime")
                    .datetime.now(
                        __import__("datetime")
                        .timezone.utc
                    )
                    .isoformat()

            }


            # حفظ مباشر
            save_posted_news()


            success_count += 1


        else:

            # =====================================
            # فشل النشر
            #
            # لا نضيف الخبر إلى posted_news
            # حتى يمكن إعادة المحاولة لاحقًا.
            # =====================================

            failed_count += 1

            print(
                f"Facebook error for "
                f"{category}: "
                f"{response.text}"
            )

            print(
                "Continuing with the next category..."
            )


    except Exception as error:

        failed_count += 1

        print(
            f"Exception while publishing "
            f"{category}: {error}"
        )

        print(
            "Continuing with the next category..."
        )


# =========================================================
# حفظ نهائي
# =========================================================

save_posted_news()


print("")
print(
    "=========================================="
)

print(
    "NOWNEX publishing finished"
)

print(
    f"Successful: {success_count}"
)

print(
    f"Failed: {failed_count}"
)

print(
    f"Total stored as published: "
    f"{len(posted_news)}"
)

print(
    "=========================================="
)
