import os
import json
import re
import html
import time
import calendar
from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests
import feedparser


# ============================================================
# NOWNEX NEWS ENGINE v6
# ============================================================
# الهدف:
# - أخبار حديثة فقط
# - العربية أولاً
# - لا تسقط العملية كلها بسبب Gemini 429
# - لا يشترط 3 أخبار ناجحة من كل قسم
# - يحفظ الأخبار العربية الصالحة
# - ترجمة أفضل
# - ملخصات أطول
# - صور أفضل
# - يسمح للـWorkflow بالوصول إلى Facebook
# ============================================================


# ============================================================
# GEMINI
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)


GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{GEMINI_MODEL}:generateContent"
)


# ============================================================
# SETTINGS
# ============================================================

MAX_NEWS = 21

MAX_AGE_HOURS = 48

ENTRIES_PER_FEED = 20

REQUEST_TIMEOUT = 15

GEMINI_TIMEOUT = 120

# عدد الأخبار في كل طلب Gemini
GEMINI_BATCH_SIZE = 7

# انتظار بسيط بين الطلبات
GEMINI_BATCH_DELAY = 8

# أقل عدد أخبار عربية مقبول حتى تستمر العملية
MIN_VALID_TOTAL = 7

# الحد الأقصى لمحاولات Gemini
GEMINI_MAX_RETRIES = 3


MAIN_CATEGORIES = [
    "AI",
    "Technology",
    "Cars",
    "Entertainment",
    "World",
    "Facts",
    "Products"
]


# ============================================================
# HTTP
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({

    "User-Agent":
        "Mozilla/5.0 (compatible; NOWNEX-NewsBot/6.0)",

    "Accept":
        "application/rss+xml, application/xml, "
        "text/xml, text/html, image/*"

})


# ============================================================
# GOOGLE NEWS
# ============================================================

def google_news_url(
    query,
    language="en",
    country="US"
):

    query = f"{query} when:2d"

    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}"
        f"&hl={language}"
        f"&gl={country}"
        f"&ceid={country}:{language}"
    )


# ============================================================
# RSS SOURCES
# ============================================================

RSS_FEEDS = [

    # AI

    (
        "TechCrunch AI",
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "AI"
    ),

    (
        "Google News AI Latest",
        google_news_url(
            "artificial intelligence AI",
            "en",
            "US"
        ),
        "AI"
    ),

    (
        "Google News AI Arabic Latest",
        google_news_url(
            "الذكاء الاصطناعي",
            "ar",
            "DZ"
        ),
        "AI"
    ),

    (
        "MIT Technology Review",
        "https://www.technologyreview.com/feed/",
        "AI"
    ),


    # TECHNOLOGY

    (
        "TechCrunch",
        "https://techcrunch.com/feed/",
        "Technology"
    ),

    (
        "The Verge",
        "https://www.theverge.com/rss/index.xml",
        "Technology"
    ),

    (
        "Ars Technica",
        "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "Technology"
    ),

    (
        "Google News Technology Latest",
        google_news_url(
            "technology smartphones gadgets",
            "en",
            "US"
        ),
        "Technology"
    ),

    (
        "Google News Technology Arabic Latest",
        google_news_url(
            "تكنولوجيا هواتف أجهزة",
            "ar",
            "DZ"
        ),
        "Technology"
    ),


    # CARS

    (
        "Motor1",
        "https://www.motor1.com/rss/news/",
        "Cars"
    ),

    (
        "Car and Driver",
        "https://www.caranddriver.com/rss/all.xml",
        "Cars"
    ),

    (
        "Google News Cars Latest",
        google_news_url(
            "cars automotive electric vehicles",
            "en",
            "US"
        ),
        "Cars"
    ),

    (
        "Google News Cars Arabic Latest",
        google_news_url(
            "سيارات سيارات كهربائية سيارات جديدة",
            "ar",
            "DZ"
        ),
        "Cars"
    ),


    # ENTERTAINMENT

    (
        "Variety",
        "https://variety.com/feed/",
        "Entertainment"
    ),

    (
        "Hollywood Reporter",
        "https://www.hollywoodreporter.com/feed/",
        "Entertainment"
    ),

    (
        "Google News Entertainment Latest",
        google_news_url(
            "entertainment movies music games",
            "en",
            "US"
        ),
        "Entertainment"
    ),

    (
        "Google News Entertainment Arabic Latest",
        google_news_url(
            "ترفيه أفلام موسيقى ألعاب",
            "ar",
            "DZ"
        ),
        "Entertainment"
    ),


    # WORLD

    (
        "BBC Arabic",
        "https://feeds.bbci.co.uk/arabic/rss.xml",
        "World"
    ),

    (
        "Google News World Arabic Latest",
        google_news_url(
            "العالم أخبار الشرق الأوسط",
            "ar",
            "DZ"
        ),
        "World"
    ),

    (
        "Google News Middle East Arabic Latest",
        google_news_url(
            "الشرق الأوسط أخبار عاجلة",
            "ar",
            "DZ"
        ),
        "World"
    ),

    (
        "Google News World Latest",
        google_news_url(
            "world news",
            "en",
            "US"
        ),
        "World"
    ),


    # FACTS

    (
        "ScienceDaily",
        "https://www.sciencedaily.com/rss/top/science.xml",
        "Facts"
    ),

    (
        "Google News Science Latest",
        google_news_url(
            "science discovery space",
            "en",
            "US"
        ),
        "Facts"
    ),

    (
        "Google News Science Arabic Latest",
        google_news_url(
            "علم اكتشافات فضاء علوم",
            "ar",
            "DZ"
        ),
        "Facts"
    ),


    # PRODUCTS

    (
        "Google News Products Latest",
        google_news_url(
            "new products gadgets devices",
            "en",
            "US"
        ),
        "Products"
    ),

    (
        "Google News Gadgets Latest",
        google_news_url(
            "new gadgets smartphones devices",
            "en",
            "US"
        ),
        "Products"
    ),

    (
        "Google News Products Arabic Latest",
        google_news_url(
            "منتجات أجهزة هواتف منتجات جديدة",
            "ar",
            "DZ"
        ),
        "Products"
    )

]


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(value):

    value = html.unescape(
        str(value or "")
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# NORMALIZE TITLE
# ============================================================

def normalize_title(title):

    title = clean_text(
        title
    ).lower()

    title = re.sub(
        r"[^\w\u0600-\u06FF]+",
        "",
        title
    )

    return title


# ============================================================
# IMAGE URL
# ============================================================

def valid_image_url(url):

    if not url:
        return ""

    url = html.unescape(
        str(url).strip()
    )

    if url.startswith("//"):
        url = "https:" + url

    if not (
        url.startswith("http://")
        or
        url.startswith("https://")
    ):
        return ""

    return url.replace(
        "&amp;",
        "&"
    )


# ============================================================
# RSS IMAGE
# ============================================================

def extract_rss_image(entry):

    media_content = entry.get(
        "media_content",
        []
    )

    if isinstance(
        media_content,
        list
    ):

        for media in media_content:

            if not isinstance(
                media,
                dict
            ):
                continue

            image = valid_image_url(
                media.get("url")
                or media.get("href")
                or media.get("src")
            )

            if image:
                return image


    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    if isinstance(
        media_thumbnail,
        list
    ):

        for media in media_thumbnail:

            if not isinstance(
                media,
                dict
            ):
                continue

            image = valid_image_url(
                media.get("url")
                or media.get("href")
                or media.get("src")
            )

            if image:
                return image


    enclosures = entry.get(
        "enclosures",
        []
    )

    if isinstance(
        enclosures,
        list
    ):

        for enclosure in enclosures:

            if not isinstance(
                enclosure,
                dict
            ):
                continue

            image = valid_image_url(
                enclosure.get("href")
                or enclosure.get("url")
            )

            if image:
                return image


    html_sources = [

        entry.get(
            "summary",
            ""
        ),

        entry.get(
            "description",
            ""
        )

    ]


    content = entry.get(
        "content",
        []
    )

    if isinstance(
        content,
        list
    ):

        for item in content:

            if isinstance(
                item,
                dict
            ):

                html_sources.append(
                    item.get(
                        "value",
                        ""
                    )
                )


    for source in html_sources:

        source = str(
            source or ""
        )


        matches = re.findall(

            r'<img[^>]+(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']',

            source,

            re.IGNORECASE

        )


        for image in matches:

            image = valid_image_url(
                image
            )

            if image:
                return image


    return ""


# ============================================================
# PUBLISHED TIMESTAMP
# ============================================================

def get_published_timestamp(entry):

    parsed = entry.get(
        "published_parsed"
    )


    if not parsed:

        parsed = entry.get(
            "updated_parsed"
        )


    if parsed:

        try:

            return calendar.timegm(
                parsed
            )

        except Exception:

            pass


    return 0


# ============================================================
# AGE
# ============================================================

def article_age_hours(timestamp):

    if not timestamp:
        return 999999


    age = (
        time.time() - timestamp
    ) / 3600


    return max(
        0,
        age
    )


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(items):

    result = []

    seen_titles = set()

    seen_links = set()


    for item in items:

        title_key = normalize_title(
            item.get(
                "title",
                ""
            )
        )


        link_key = str(
            item.get(
                "link",
                ""
            )
        ).strip().lower()


        if not title_key:
            continue


        if title_key in seen_titles:
            continue


        if (
            link_key
            and
            link_key in seen_links
        ):
            continue


        seen_titles.add(
            title_key
        )


        if link_key:

            seen_links.add(
                link_key
            )


        result.append(
            item
        )


    return result


# ============================================================
# READ RSS
# ============================================================

def get_news():

    articles = []


    for (
        source_name,
        feed_url,
        category
    ) in RSS_FEEDS:

        print("")
        print(
            "=========================================="
        )

        print(
            "Reading:",
            source_name
        )

        try:

            response = SESSION.get(
                feed_url,
                timeout=REQUEST_TIMEOUT
            )


            if response.status_code != 200:

                print(
                    "HTTP:",
                    response.status_code
                )

                continue


            feed = feedparser.parse(
                response.content
            )


            entries = feed.entries[
                :ENTRIES_PER_FEED
            ]


            print(
                "Found:",
                len(entries)
            )


            for entry in entries:

                title = clean_text(
                    entry.get(
                        "title",
                        ""
                    )
                )


                if not title:
                    continue


                link = str(
                    entry.get(
                        "link",
                        ""
                    )
                    or ""
                ).strip()


                if not link:
                    continue


                timestamp = get_published_timestamp(
                    entry
                )


                if not timestamp:

                    print(
                        "SKIP — no date:",
                        title[:100]
                    )

                    continue


                age = article_age_hours(
                    timestamp
                )


                if age > MAX_AGE_HOURS:

                    print(
                        f"SKIP OLD — {age:.1f}h:",
                        title[:100]
                    )

                    continue


                description = clean_text(

                    entry.get(
                        "summary",
                        entry.get(
                            "description",
                            ""
                        )
                    )

                )


                if not description:

                    content = entry.get(
                        "content",
                        []
                    )


                    if isinstance(
                        content,
                        list
                    ) and content:

                        try:

                            description = clean_text(

                                content[0].get(
                                    "value",
                                    ""
                                )

                            )

                        except Exception:
                            pass


                image = extract_rss_image(
                    entry
                )


                published = clean_text(

                    entry.get(
                        "published",
                        entry.get(
                            "updated",
                            ""
                        )
                    )

                )


                articles.append({

                    "title":
                        title,

                    "description":
                        description,

                    "link":
                        link,

                    "source":
                        source_name,

                    "category":
                        category,

                    "image":
                        image,

                    "published":
                        published,

                    "_published_timestamp":
                        timestamp,

                    "_age_hours":
                        age

                })


        except Exception as error:

            print(
                "RSS ERROR:",
                source_name,
                str(error)[:300]
            )


    articles = remove_duplicates(
        articles
    )


    articles.sort(

        key=lambda x:
            x.get(
                "_published_timestamp",
                0
            ),

        reverse=True

    )


    print("")
    print(
        "FRESH ARTICLES:",
        len(articles)
    )


    return articles


# ============================================================
# SELECT NEWS
# ============================================================

def select_news(articles):

    selected = []

    selected_keys = set()


    # أولاً نحاول الحصول على 3 من كل قسم
    for category in MAIN_CATEGORIES:

        candidates = [

            article

            for article in articles

            if article.get(
                "category"
            ) == category

        ]


        count = 0


        for article in candidates:

            key = (

                article.get(
                    "link",
                    ""
                ).strip().lower()

                or

                normalize_title(
                    article.get(
                        "title",
                        ""
                    )
                )

            )


            if not key:
                continue


            if key in selected_keys:
                continue


            selected.append(
                article
            )

            selected_keys.add(
                key
            )

            count += 1


            if count >= 3:
                break


    # ثم نكمل حتى 21
    for article in articles:

        if len(selected) >= MAX_NEWS:
            break


        key = (

            article.get(
                "link",
                ""
            ).strip().lower()

            or

            normalize_title(
                article.get(
                    "title",
                    ""
                )
            )

        )


        if not key:
            continue


        if key in selected_keys:
            continue


        selected.append(
            article
        )

        selected_keys.add(
            key
        )


    return selected[
        :MAX_NEWS
    ]


# ============================================================
# SUMMARY VALIDATION
# ============================================================

def summary_is_valid(
    title,
    summary
):

    title = clean_text(
        title
    )

    summary = clean_text(
        summary
    )


    if not summary:
        return False


    if len(summary) < 250:
        return False


    if summary.lower() == title.lower():
        return False


    sentences = len(

        re.findall(
            r"[.!؟]",
            summary
        )

    )


    if sentences < 3:
        return False


    words = re.findall(
        r"\S+",
        summary
    )


    if len(words) < 45:
        return False


    if len(words) > 220:
        return False


    return True


# ============================================================
# ARABIC VALIDATION
# ============================================================

def is_arabic_title(title):

    arabic = len(

        re.findall(
            r"[\u0600-\u06FF]",
            title
        )

    )


    latin = len(

        re.findall(
            r"[A-Za-z]",
            title
        )

    )


    if arabic == 0:
        return False


    if (
        latin > arabic * 2
        and
        latin > 15
    ):

        return False


    return True


# ============================================================
# GEMINI REQUEST
# ============================================================

def ask_gemini_batch(articles):

    if not articles:
        return []


    blocks = []


    for index, article in enumerate(
        articles,
        start=1
    ):

        description = clean_text(

            article.get(
                "description",
                ""
            )
        )


        if len(description) > 6000:

            description = description[:6000]


        blocks.append(

            f"""
ARTICLE {index}

CATEGORY:
{article.get("category", "")}

SOURCE:
{article.get("source", "")}

ORIGINAL TITLE:
{article.get("title", "")}

ARTICLE INFORMATION:
{description}
"""

        )


    joined = "\n".join(
        blocks
    )


    prompt = f"""
أنت محرر أخبار عربي محترف يعمل في NOWNEX.

مهمتك ترجمة وصياغة الأخبار التالية باللغة العربية.

قواعد صارمة:

1. ترجم كل عنوان إلى العربية.
2. لا تترك العنوان باللغة الإنجليزية.
3. أسماء الشركات والمنتجات والعلامات التجارية يمكن إبقاؤها كما هي عند الحاجة.
4. لا تخترع أي معلومة.
5. لا تضف أرقامًا غير موجودة.
6. لا تضف تصريحات غير موجودة.
7. لا تضف رأيًا شخصيًا.
8. اعتمد فقط على المعلومات الموجودة في ARTICLE INFORMATION.
9. اكتب ملخصًا عربيًا مفيدًا من 70 إلى 120 كلمة تقريبًا.
10. الملخص يجب أن يكون 3 إلى 5 جمل.
11. لا تجعل الملخص مجرد إعادة صياغة للعنوان.
12. اشرح ما حدث ومن المعني وما التفاصيل المهمة الموجودة في المصدر.
13. إذا كانت المعلومات قليلة، اكتب أفضل ملخص ممكن دون اختراع معلومات.
14. لا تكتب اعتذارًا.
15. لا تكتب أي شيء خارج JSON.

أعد JSON فقط:

[
  {{
    "id": 1,
    "title_ar": "عنوان عربي",
    "summary_ar": "ملخص عربي منظم"
  }}
]

يجب أن تعيد نتيجة لكل ARTICLE.

الأخبار:

{joined}
"""


    payload = {

        "contents": [

            {

                "role": "user",

                "parts": [

                    {
                        "text": prompt
                    }

                ]

            }

        ],

        "generationConfig": {

            "temperature":
                0.2,

            "responseMimeType":
                "application/json"

        }

    }


    headers = {

        "Content-Type":
            "application/json",

        "x-goog-api-key":
            API_KEY

    }


    for attempt in range(
        1,
        GEMINI_MAX_RETRIES + 1
    ):

        try:

            print(
                f"Gemini request "
                f"{attempt}/{GEMINI_MAX_RETRIES}"
            )


            response = requests.post(

                GEMINI_URL,

                headers=headers,

                json=payload,

                timeout=GEMINI_TIMEOUT

            )


            print(
                "Gemini status:",
                response.status_code
            )


            # =================================================
            # RATE LIMIT
            # =================================================

            if response.status_code == 429:

                retry_after = (

                    response.headers.get(
                        "Retry-After"
                    )
                )


                try:

                    wait_time = int(
                        retry_after
                    )

                except Exception:

                    wait_time = 30 * attempt


                # لا ننتظر دقائق طويلة جدًا
                wait_time = min(
                    wait_time,
                    60
                )


                print(
                    "Gemini rate limit 429."
                )

                print(
                    "Waiting:",
                    wait_time,
                    "seconds."
                )


                if attempt < GEMINI_MAX_RETRIES:

                    time.sleep(
                        wait_time
                    )

                    continue


                print(
                    "Gemini failed after "
                    "rate-limit retries."
                )

                return []


            # =================================================
            # OTHER ERROR
            # =================================================

            if response.status_code != 200:

                print(
                    "Gemini error:"
                )

                print(
                    response.text[:2000]
                )

                return []


            # =================================================
            # JSON
            # =================================================

            data = response.json()


            candidates = data.get(
                "candidates",
                []
            )


            if not candidates:

                print(
                    "Gemini returned no candidates."
                )

                return []


            content = candidates[0].get(
                "content",
                {}
            )


            parts = content.get(
                "parts",
                []
            )


            if not parts:

                print(
                    "Gemini returned no parts."
                )

                return []


            text = parts[0].get(
                "text",
                ""
            )


            if not text:

                return []


            text = text.strip()


            # إزالة Markdown
            text = re.sub(
                r"^```json\s*",
                "",
                text,
                flags=re.IGNORECASE
            )


            text = re.sub(
                r"\s*```$",
                "",
                text
            )


            result = json.loads(
                text
            )


            if isinstance(
                result,
                dict
            ):

                result = result.get(
                    "articles",
                    []
                )


            if not isinstance(
                result,
                list
            ):

                print(
                    "Gemini result is not a list."
                )

                return []


            return result


        except json.JSONDecodeError as error:

            print(
                "Gemini JSON ERROR:",
                str(error)
            )

            print(
                "Raw response:",
                text[:1500]
                if "text" in locals()
                else "NONE"
            )

            return []


        except requests.Timeout:

            print(
                "Gemini TIMEOUT."
            )

            if attempt < GEMINI_MAX_RETRIES:

                time.sleep(
                    10
                )

                continue


        except Exception as error:

            print(
                "Gemini ERROR:",
                str(error)[:500]
            )

            if attempt < GEMINI_MAX_RETRIES:

                time.sleep(
                    10
                )

                continue


    return []


# ============================================================
# PROCESS GEMINI
# ============================================================

def process_batch(articles):

    results = ask_gemini_batch(
        articles
    )


    if not results:

        print(
            "BATCH FAILED — keeping other batches alive."
        )

        return []


    by_id = {}


    for result in results:

        if not isinstance(
            result,
            dict
        ):
            continue


        try:

            article_id = int(
                result.get(
                    "id"
                )
            )

        except Exception:

            continue


        by_id[
            article_id
        ] = result


    final_items = []


    for index, article in enumerate(
        articles,
        start=1
    ):

        ai = by_id.get(
            index
        )


        if not ai:

            print(
                "SKIP — Gemini did not return:",
                article.get(
                    "title",
                    ""
                )[:100]
            )

            continue


        title_ar = clean_text(

            ai.get(
                "title_ar",
                ""
            )
        )


        summary_ar = clean_text(

            ai.get(
                "summary_ar",
                ""
            )
        )


        if not is_arabic_title(
            title_ar
        ):

            print(
                "SKIP — title not Arabic:",
                title_ar[:120]
            )

            continue


        if not summary_is_valid(
            title_ar,
            summary_ar
        ):

            print(
                "SKIP — summary invalid:",
                title_ar[:120]
            )

            continue


        timestamp = article.get(
            "_published_timestamp",
            0
        )


        final_items.append({

            "title_ar":
                title_ar,

            "summary_ar":
                summary_ar,

            "title":
                title_ar,

            "summary":
                summary_ar,

            "description":
                summary_ar,

            "category":
                article.get(
                    "category",
                    ""
                ),

            "source":
                article.get(
                    "source",
                    ""
                ),

            "link":
                article.get(
                    "link",
                    ""
                ),

            "image":
                article.get(
                    "image",
                    ""
                ),

            "published":
                article.get(
                    "published",
                    ""
                ),

            "publishedAt":
                datetime.fromtimestamp(
                    timestamp,
                    timezone.utc
                ).isoformat()
                if timestamp
                else "",

            "ageHours":
                round(
                    article.get(
                        "_age_hours",
                        0
                    ),
                    1
                )

        })


        print(
            "CREATED ✓:",
            title_ar[:120]
        )


    return final_items


# ============================================================
# SIMPLE IMAGE QUALITY
# ============================================================

def image_is_usable(url):

    if not url:
        return False


    try:

        response = SESSION.head(

            url,

            timeout=10,

            allow_redirects=True

        )


        if response.status_code != 200:
            return False


        content_type = (

            response.headers.get(
                "Content-Type",
                ""
            )
            .lower()

        )


        if "image" not in content_type:
            return False


        return True


    except Exception:

        return False


# ============================================================
# COMPLETE IMAGES
# ============================================================

def complete_images(selected):

    print("")
    print(
        "=========================================="
    )

    print(
        "CHECKING NEWS IMAGES"
    )

    print(
        "=========================================="
    )


    for index, article in enumerate(
        selected,
        start=1
    ):

        image = article.get(
            "image",
            ""
        )


        if image and image_is_usable(
            image
        ):

            print(
                f"[{index}] IMAGE ✓"
            )

        else:

            article["image"] = ""

            print(
                f"[{index}] IMAGE unavailable"
            )


    return selected


# ============================================================
# CATEGORY COUNTS
# ============================================================

def get_category_counts(news):

    counts = {}


    for category in MAIN_CATEGORIES:

        counts[category] = len([

            item

            for item in news

            if item.get(
                "category"
            ) == category

        ])


    return counts


# ============================================================
# TRENDING
# ============================================================

def create_trending(final_news):

    trending = []

    seen = set()


    for item in final_news:

        key = normalize_title(

            item.get(
                "title_ar",
                ""
            )
        )


        if not key:
            continue


        if key in seen:
            continue


        copy_item = dict(
            item
        )


        copy_item[
            "category"
        ] = "Trending"


        trending.append(
            copy_item
        )


        seen.add(
            key
        )


        if len(trending) >= 10:

            break


    return trending


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print(
        "=========================================="
    )

    print(
        " NOWNEX NEWS ENGINE v6"
    )

    print(
        " FRESH + ARABIC + PARTIAL SUCCESS"
    )

    print(
        "=========================================="
    )

    print(
        "Target:",
        MAX_NEWS
    )

    print(
        "Maximum age:",
        MAX_AGE_HOURS,
        "hours"
    )

    print(
        "Gemini batch:",
        GEMINI_BATCH_SIZE
    )

    print(
        "Minimum valid total:",
        MIN_VALID_TOTAL
    )


    # ========================================================
    # 1. RSS
    # ========================================================

    articles = get_news()


    if not articles:

        raise RuntimeError(
            "No fresh RSS articles found."
        )


    # ========================================================
    # 2. SELECT
    # ========================================================

    selected = select_news(
        articles
    )


    print("")
    print(
        "SELECTED:",
        len(selected)
    )


    selected_counts = get_category_counts(
        selected
    )


    print("")
    print(
        "SELECTED BY CATEGORY:"
    )


    for category in MAIN_CATEGORIES:

        print(
            f"{category}: "
            f"{selected_counts.get(category, 0)}"
        )


    # ========================================================
    # 3. IMAGES
    # ========================================================

    selected = complete_images(
        selected
    )


    # ========================================================
    # 4. GEMINI
    # ========================================================

    final_news = []


    total_batches = (

        (
            len(selected)
            +
            GEMINI_BATCH_SIZE
            -
            1
        )
        //
        GEMINI_BATCH_SIZE

    )


    print("")
    print(
        "=========================================="
    )

    print(
        "GEMINI TRANSLATION"
    )

    print(
        "=========================================="
    )


    for batch_number, start in enumerate(

        range(
            0,
            len(selected),
            GEMINI_BATCH_SIZE
        ),

        start=1

    ):

        batch = selected[
            start:
            start + GEMINI_BATCH_SIZE
        ]


        print("")
        print(
            f"BATCH {batch_number}/{total_batches}"
        )


        results = process_batch(
            batch
        )


        final_news.extend(
            results
        )


        print(
            "Valid results:",
            len(results)
        )


        # مهم:
        # حتى إذا فشلت هذه الدفعة،
        # نكمل إلى الدفعة التالية.

        if batch_number < total_batches:

            print(
                "Waiting:",
                GEMINI_BATCH_DELAY,
                "seconds"
            )

            time.sleep(
                GEMINI_BATCH_DELAY
            )


    # ========================================================
    # 5. REMOVE DUPLICATES
    # ========================================================

    unique_news = []

    seen = set()


    for item in final_news:

        key = (

            item.get(
                "link",
                ""
            ).strip().lower()

            or

            normalize_title(
                item.get(
                    "title_ar",
                    ""
                )
            )

        )


        if not key:
            continue


        if key in seen:
            continue


        seen.add(
            key
        )

        unique_news.append(
            item
        )


    final_news = unique_news


    # ========================================================
    # 6. SORT
    # ========================================================

    final_news.sort(

        key=lambda item:
            item.get(
                "publishedAt",
                ""
            ),

        reverse=True

    )


    final_news = final_news[
        :MAX_NEWS
    ]


    # ========================================================
    # 7. REPORT
    # ========================================================

    category_counts = get_category_counts(
        final_news
    )


    print("")
    print(
        "=========================================="
    )

    print(
        "FINAL CATEGORY CHECK"
    )

    print(
        "=========================================="
    )


    for category in MAIN_CATEGORIES:

        print(

            f"{category}: "
            f"{category_counts.get(category, 0)}"

        )


    print("")
    print(
        "TOTAL VALID ARABIC NEWS:",
        len(final_news)
    )


    # ========================================================
    # 8. إذا لم نحصل على عدد كافٍ
    # ========================================================

    if len(final_news) < MIN_VALID_TOTAL:

        print("")
        print(
            "WARNING — TOO FEW VALID ARTICLES"
        )

        print(
            "Existing news.json was NOT modified."
        )


        raise RuntimeError(

            f"Only {len(final_news)} valid "
            f"Arabic articles were generated. "
            f"Minimum required: {MIN_VALID_TOTAL}."

        )


    # ========================================================
    # 9. TRENDING
    # ========================================================

    trending_news = create_trending(
        final_news
    )


    # ========================================================
    # 10. OUTPUT
    # ========================================================

    output = {

        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "count":
            len(final_news),

        "trendingCount":
            len(trending_news),

        "news":
            final_news,

        "trending":
            trending_news

    }


    # ========================================================
    # 11. SAVE
    # ========================================================

    with open(

        "news.json",

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(

            output,

            file,

            ensure_ascii=False,

            indent=2

        )


    # ========================================================
    # 12. FINAL
    # ========================================================

    images_count = len([

        item

        for item in final_news

        if item.get(
            "image"
        )

    ])


    print("")
    print(
        "=========================================="
    )

    print(
        " NOWNEX NEWS UPDATED SUCCESSFULLY ✓"
    )

    print(
        "=========================================="
    )

    print(
        "Articles:",
        len(final_news)
    )

    print(
        "Trending:",
        len(trending_news)
    )

    print(
        "Images:",
        f"{images_count}/{len(final_news)}"
    )


    print("")
    print(
        "FINAL NEWS:"
    )


    for item in final_news:

        print(

            f"{item.get('ageHours', '?')}h | "
            f"{item.get('category', '')} | "
            f"{item.get('title_ar', '')[:100]}"

        )


    print("")
    print(
        "news.json saved successfully."
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
