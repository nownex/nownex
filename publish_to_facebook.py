import json
import os
import requests
from datetime import datetime, timezone


# =========================================================
# NOWNEX — FACEBOOK PUBLISHER
# =========================================================

TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "FACEBOOK_PAGE_TOKEN is missing."
    )


GRAPH_VERSION = "v26.0"

PHOTO_URL = (
    f"https://graph.facebook.com/"
    f"{GRAPH_VERSION}/me/photos"
)

FEED_URL = (
    f"https://graph.facebook.com/"
    f"{GRAPH_VERSION}/me/feed"
)

BASE_IMAGE_URL = (
    "https://nownex.github.io/nownex/"
)


# =========================================================
# الإعدادات
# =========================================================

NEWS_FILE = "news.json"

POSTED_FILE = "posted_news.json"


# =========================================================
# الهاشتاقات
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
# قراءة news.json
# =========================================================

if not os.path.exists(NEWS_FILE):

    raise RuntimeError(
        "news.json does not exist."
    )


with open(
    NEWS_FILE,
    "r",
    encoding="utf-8"
) as f:

    data = json.load(f)


news = data.get(
    "news",
    []
)


if not isinstance(news, list):

    raise RuntimeError(
        "news.json has invalid news format."
    )


if not news:

    raise RuntimeError(
        "No news found in news.json."
    )


print(
    f"Total news in news.json: {len(news)}"
)


# =========================================================
# قراءة سجل النشر
# =========================================================

if os.path.exists(POSTED_FILE):

    try:

        with open(
            POSTED_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            posted_news = json.load(f)


        if not isinstance(
            posted_news,
            dict
        ):

            posted_news = {}


    except Exception as error:

        print(
            "WARNING: Could not read posted_news.json:",
            error
        )

        posted_news = {}

else:

    posted_news = {}


print(
    f"Previously published: {len(posted_news)}"
)


# =========================================================
# حفظ سجل النشر
# =========================================================

def save_posted_news():

    with open(
        POSTED_FILE,
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
# معرف الخبر
#
# الرابط هو المعرف الأقوى.
# العنوان يستخدم كاحتياط.
# =========================================================

def get_news_id(article):

    link = str(
        article.get(
            "link",
            ""
        ) or ""
    ).strip()


    title = str(
        article.get(
            "title_ar",
            article.get(
                "title",
                ""
            )
        ) or ""
    ).strip()


    if link:
        return link


    return title


# =========================================================
# تحويل وقت الخبر إلى رقم للمقارنة
#
# نستخدم publishedAt أولاً.
# =========================================================

def get_article_timestamp(article):

    value = (
        article.get("published")
        or
        article.get("publishedAt")
        or
        ""
    )


    if not value:
        return 0


    value = str(value).strip()


    # ISO format
    try:

        normalized = value.replace(
            "Z",
            "+00:00"
        )


        dt = datetime.fromisoformat(
            normalized
        )


        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )


        return dt.timestamp()


    except Exception:
        pass


    # إذا لم نستطع تحويل التاريخ
    return 0


# =========================================================
# البحث عن أحدث خبر غير منشور في كل قسم
# =========================================================

latest_by_category = {}


for article in news:

    if not isinstance(
        article,
        dict
    ):
        continue


    category = str(
        article.get(
            "category",
            article.get(
                "section",
                "Other"
            )
        ) or "Other"
    ).strip()


    news_id = get_news_id(
        article
    )


    if not news_id:
        continue


    title = str(
        article.get(
            "title_ar",
            article.get(
                "title",
                ""
            )
        ) or ""
    ).strip()


    # =====================================================
    # منع التكرار
    # =====================================================

    if news_id in posted_news:

        print(
            "SKIP already published:",
            title
        )

        continue


    timestamp = get_article_timestamp(
        article
    )


    # =====================================================
    # إذا كان هناك خبر أحدث في نفس القسم
    # نحتفظ بالأحدث فقط.
    # =====================================================

    current = latest_by_category.get(
        category
    )


    if current is None:

        latest_by_category[
            category
        ] = article

    else:

        current_timestamp = (
            get_article_timestamp(
                current
            )
        )


        if timestamp > current_timestamp:

            latest_by_category[
                category
            ] = article


# =========================================================
# لا توجد أخبار جديدة
# =========================================================

if not latest_by_category:

    print("")
    print(
        "No new news to publish."
    )
    print(
        "Facebook is already up to date."
    )

    raise SystemExit(0)


print("")
print(
    "NEW CATEGORIES:"
)


for category in latest_by_category:

    article = latest_by_category[
        category
    ]

    print(
        f" - {category}: "
        f"{article.get('title_ar', article.get('title', ''))}"
    )


# =========================================================
# النشر
# =========================================================

success_count = 0

failed_count = 0


for category, article in latest_by_category.items():

    title = str(
        article.get(
            "title_ar",
            article.get(
                "title",
                ""
            )
        ) or ""
    ).strip()


    summary = str(
        article.get(
            "summary_ar",
            article.get(
                "summary",
                article.get(
                    "description",
                    ""
                )
            )
        ) or ""
    ).strip()


    link = str(
        article.get(
            "link",
            ""
        ) or ""
    ).strip()


    image = str(
        article.get(
            "image",
            article.get(
                "image_url",
                ""
            )
        ) or ""
    ).strip()


    news_id = get_news_id(
        article
    )


    print("")
    print(
        "=========================================="
    )

    print(
        "Publishing:",
        category
    )

    print(
        "Title:",
        title
    )

    print(
        "News ID:",
        news_id
    )


    # =====================================================
    # الهاشتاقات
    # =====================================================

    hashtags = HASHTAGS.get(
        category,
        HASHTAGS["Other"]
    )


    # =====================================================
    # نص المنشور
    # =====================================================

    message = (

        f"📰 {title}\n\n"

        f"{summary}\n\n"

        f"{hashtags}\n\n"

        f"🔗 اقرأ المزيد:\n"
        f"{link}"

    )


    # =====================================================
    # تجهيز الصورة
    # =====================================================

    if image:

        if not image.startswith(
            "http://"
        ) and not image.startswith(
            "https://"
        ):

            image = (
                BASE_IMAGE_URL
                + image.lstrip("/")
            )


    print(
        "Image:",
        image if image else "NONE"
    )


    # =====================================================
    # النشر
    # =====================================================

    try:

        if image:

            print(
                "Publishing as PHOTO..."
            )


            response = requests.post(

                PHOTO_URL,

                data={

                    "url":
                        image,

                    "caption":
                        message,

                    "access_token":
                        TOKEN

                },

                timeout=60

            )


        else:

            print(
                "Publishing as TEXT..."
            )


            response = requests.post(

                FEED_URL,

                data={

                    "message":
                        message,

                    "access_token":
                        TOKEN

                },

                timeout=60

            )


        # =================================================
        # النجاح
        # =================================================

        if response.ok:

            try:

                result = response.json()

            except Exception:

                result = {}


            facebook_id = result.get(
                "id",
                ""
            )


            posted_news[news_id] = {

                "title":
                    title,

                "category":
                    category,

                "link":
                    link,

                "facebook_id":
                    facebook_id,

                "published_at":
                    datetime.now(
                        timezone.utc
                    ).isoformat()

            }


            # حفظ مباشرة
            save_posted_news()


            success_count += 1


            print(
                "Published successfully ✓"
            )


        # =================================================
        # فشل
        # =================================================

        else:

            failed_count += 1


            print(
                "Facebook error:"
            )

            print(
                response.text[:2000]
            )


            print(
                "Continuing..."
            )


    except Exception as error:

        failed_count += 1


        print(
            "Publishing exception:",
            str(error)
        )


        print(
            "Continuing with next category..."
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
    "NOWNEX FACEBOOK PUBLISHING FINISHED"
)

print(
    f"Successful: {success_count}"
)

print(
    f"Failed: {failed_count}"
)

print(
    f"Stored published news: "
    f"{len(posted_news)}"
)

print(
    "=========================================="
)
