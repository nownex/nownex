import json
import os
import requests
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


# =========================================================
# NOWNEX — FACEBOOK PUBLISHER v2
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


# =========================================================
# FILES
# =========================================================

NEWS_FILE = "news.json"
POSTED_FILE = "posted_news.json"


# =========================================================
# SETTINGS
# =========================================================

# انشر كل الأخبار الجديدة الموجودة في news.json
# بدل خبر واحد فقط من كل قسم.
MAX_POSTS_PER_RUN = 21

REQUEST_TIMEOUT = 60


# =========================================================
# HASHTAGS
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
# READ NEWS
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
# READ POSTED HISTORY
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
# SAVE HISTORY
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
# NEWS ID
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
# TIMESTAMP
# =========================================================

def get_article_timestamp(article):

    # -----------------------------------------------------
    # publishedAt هو الأفضل لأنه ISO حقيقي من news engine
    # -----------------------------------------------------

    published_at = str(
        article.get(
            "publishedAt",
            ""
        ) or ""
    ).strip()


    if published_at:

        try:

            normalized = published_at.replace(
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


    # -----------------------------------------------------
    # محاولة قراءة published من RSS
    # مثال:
    # Sun, 23 Aug 2026 15:43:53 GMT
    # -----------------------------------------------------

    published = str(
        article.get(
            "published",
            ""
        ) or ""
    ).strip()


    if published:

        try:

            dt = parsedate_to_datetime(
                published
            )


            if dt.tzinfo is None:

                dt = dt.replace(
                    tzinfo=timezone.utc
                )


            return dt.timestamp()


        except Exception:

            pass


    return 0


# =========================================================
# SORT NEWS
# =========================================================

for article in news:

    if isinstance(
        article,
        dict
    ):

        article["_facebook_timestamp"] = (
            get_article_timestamp(
                article
            )
        )


news.sort(

    key=lambda article:
        article.get(
            "_facebook_timestamp",
            0
        ),

    reverse=True

)


# =========================================================
# FIND NEW NEWS
# =========================================================

new_articles = []


for article in news:

    if not isinstance(
        article,
        dict
    ):
        continue


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


    if news_id in posted_news:

        print(
            "SKIP already published:",
            title[:120]
        )

        continue


    new_articles.append(
        article
    )


# =========================================================
# LIMIT
# =========================================================

new_articles = new_articles[
    :MAX_POSTS_PER_RUN
]


print("")
print(
    "=========================================="
)

print(
    "NEW NEWS READY FOR FACEBOOK"
)

print(
    "=========================================="
)

print(
    "New articles:",
    len(new_articles)
)


if not new_articles:

    print(
        "No new news to publish."
    )

    raise SystemExit(0)


for index, article in enumerate(
    new_articles,
    start=1
):

    print(
        f"{index}. "
        f"{article.get('category', 'Other')} | "
        f"{article.get('title_ar', article.get('title', ''))}"
    )


# =========================================================
# PUBLISH
# =========================================================

success_count = 0
failed_count = 0


for index, article in enumerate(
    new_articles,
    start=1
):

    category = str(
        article.get(
            "category",
            "Other"
        ) or "Other"
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
        f"FACEBOOK POST {index}/{len(new_articles)}"
    )

    print(
        "=========================================="
    )

    print(
        "Category:",
        category
    )

    print(
        "Title:",
        title
    )

    print(
        "Link:",
        link
    )

    print(
        "Image:",
        image if image else "NONE"
    )


    # =====================================================
    # HASHTAGS
    # =====================================================

    hashtags = HASHTAGS.get(
        category,
        HASHTAGS["Other"]
    )


    # =====================================================
    # MESSAGE
    # =====================================================

    message = (

        f"📰 {title}\n\n"

        f"{summary}\n\n"

        f"{hashtags}\n\n"

        f"🔗 اقرأ الخبر كاملًا:\n"
        f"{link}"

    )


    # =====================================================
    # PUBLISH
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

                timeout=REQUEST_TIMEOUT

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

                timeout=REQUEST_TIMEOUT

            )


        # =================================================
        # RESPONSE
        # =================================================

        print(
            "Facebook HTTP status:",
            response.status_code
        )


        try:

            result = response.json()

        except Exception:

            result = {}


        # =================================================
        # SUCCESS
        # =================================================

        if response.ok:

            facebook_id = str(
                result.get(
                    "id",
                    ""
                )
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


            save_posted_news()


            success_count += 1


            print(
                "FACEBOOK PUBLISHED ✓"
            )

            print(
                "Facebook ID:",
                facebook_id
            )


        # =================================================
        # ERROR
        # =================================================

        else:

            failed_count += 1


            print("")
            print(
                "FACEBOOK PUBLISH FAILED ✗"
            )

            print(
                "HTTP:",
                response.status_code
            )

            print(
                "Response:"
            )

            print(
                response.text[:4000]
            )


            print(
                "This news will NOT be added "
                "to posted_news.json."
            )


    except Exception as error:

        failed_count += 1


        print("")
        print(
            "FACEBOOK REQUEST EXCEPTION ✗"
        )

        print(
            str(error)
        )


# =========================================================
# FINAL SAVE
# =========================================================

save_posted_news()


# =========================================================
# FINAL REPORT
# =========================================================

print("")
print(
    "=========================================="
)

print(
    "NOWNEX FACEBOOK PUBLISHING FINISHED"
)

print(
    "=========================================="
)

print(
    "Total new:",
    len(new_articles)
)

print(
    "Successful:",
    success_count
)

print(
    "Failed:",
    failed_count
)

print(
    "Stored published news:",
    len(posted_news)
)

print(
    "=========================================="
)


# =========================================================
# FAIL GITHUB ACTION IF FACEBOOK FAILED
# =========================================================

if failed_count > 0:

    raise RuntimeError(
        f"Facebook publishing failed for "
        f"{failed_count} article(s)."
    )
