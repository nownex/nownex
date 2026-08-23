import os
import json
import re
import html
import time
import calendar
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
from email.utils import parsedate_to_datetime

import requests
import feedparser


# ============================================================
# NOWNEX — NEWS ENGINE v5
# ============================================================
#
# أهم التغييرات:
#
# 1. الأخبار الأقدم من 48 ساعة يتم حذفها.
# 2. Google News يستخدم when:2d لجلب الأخبار الحديثة.
# 3. لا يتم الاحتفاظ بالأخبار القديمة إذا فشل Gemini.
# 4. Gemini يعمل على دفعات Batch بدل طلب لكل خبر.
# 5. إذا فشل Gemini بسبب 429:
#       - لا يفشل التحديث بالكامل.
#       - يتم نشر الأخبار الجديدة الموجودة.
# 6. updatedAt هو وقت إنشاء الملف الحقيقي.
# 7. publishedAt يعتمد على وقت نشر الخبر وليس وقت معالجة Gemini.
# 8. ترتيب الأخبار من الأحدث إلى الأقدم.
# 9. لا يشترط وجود 3 أخبار لكل قسم حتى يتم نشر الملف.
# 10. نستهدف 30 خبرًا حديثًا.
#
# ============================================================


# ============================================================
# GEMINI API
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

MAX_NEWS = 30

MIN_PER_CATEGORY = 3

ENTRIES_PER_FEED = 30

REQUEST_TIMEOUT = 15

GEMINI_TIMEOUT = 90

# ------------------------------------------------------------
# أقصى عمر للخبر
# ------------------------------------------------------------

MAX_AGE_HOURS = 48

# ------------------------------------------------------------
# Gemini batch
#
# بدل:
# 30 خبر × طلب Gemini
#
# سنستخدم:
# 5 دفعات × 6 أخبار
#
# ------------------------------------------------------------

GEMINI_BATCH_SIZE = 6

GEMINI_BATCH_RETRIES = 3

GEMINI_RETRY_WAIT = 20

# ------------------------------------------------------------
# وقت بسيط بين الدفعات
# ------------------------------------------------------------

BATCH_DELAY = 3


# ============================================================
# CATEGORIES
# ============================================================

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
# RSS SOURCES
# ============================================================

RSS_FEEDS = [

    # ========================================================
    # AI
    # ========================================================

    (
        "Google News AI Latest",
        "https://news.google.com/rss/search?"
        "q=AI%20artificial%20intelligence%20when%3A2d"
        "&hl=en&gl=US&ceid=US:en",
        "AI"
    ),

    (
        "Google News AI Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1%20%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A%20when%3A2d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "AI"
    ),

    (
        "TechCrunch AI",
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "AI"
    ),

    (
        "MIT Technology Review",
        "https://www.technologyreview.com/feed/",
        "AI"
    ),


    # ========================================================
    # TECHNOLOGY
    # ========================================================

    (
        "Google News Technology Latest",
        "https://news.google.com/rss/search?"
        "q=technology%20smartphones%20gadgets%20when%3A2d"
        "&hl=en&gl=US&ceid=US:en",
        "Technology"
    ),

    (
        "Google News Technology Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%AA%D9%83%D9%86%D9%88%D9%84%D9%88%D8%AC%D9%8A%D8%A7%20%D9%87%D9%88%D8%A7%D8%AA%D9%81%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9%20when%3A2d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Technology"
    ),

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


    # ========================================================
    # CARS
    # ========================================================

    (
        "Google News Cars Latest",
        "https://news.google.com/rss/search?"
        "q=cars%20automotive%20electric%20vehicles%20when%3A2d"
        "&hl=en&gl=US&ceid=US:en",
        "Cars"
    ),

    (
        "Google News Cars Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%B3%D9%8A%D8%A7%D8%B1%D8%A7%D8%AA%20%D9%83%D9%87%D8%B1%D8%A8%D8%A7%D8%A6%D9%8A%D8%A9%20when%3A2d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Cars"
    ),

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


    # ========================================================
    # ENTERTAINMENT
    # ========================================================

    (
        "Google News Entertainment Latest",
        "https://news.google.com/rss/search?"
        "q=entertainment%20movies%20music%20games%20when%3A2d"
        "&hl=en&gl=US&ceid=US:en",
        "Entertainment"
    ),

    (
        "Google News Entertainment Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%AA%D8%B1%D9%81%D9%8A%D9%87%20%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D9%85%D9%88%D8%B3%D9%8A%D9%82%D9%89%20%D8%A3%D9%84%D8%B9%D8%A7%D8%A8%20when%3A2d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Entertainment"
    ),

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


    # ========================================================
    # WORLD
    # ========================================================

    (
        "Google News World Latest",
        "https://news.google.com/rss/search?"
        "q=world%20news%20when%3A2d"
        "&hl=en&gl=US&ceid=US:en",
        "World"
    ),

    (
        "Google News Middle East Latest",
        "https://news.google.com/rss/search?"
        "q=Middle%20East%20news%20when%3A2d"
        "&hl=en&gl=US&ceid=US:en",
        "World"
    ),

    (
        "Google News World Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1%20%D8%A7%D9%84%D8%B9%D8%A7%D9%84%D9%85%20when%3A2d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "World"
    ),

    (
        "BBC Arabic",
        "https://feeds.bbci.co.uk/arabic/rss.xml",
        "World"
    ),

    (
        "Al Jazeera",
        "https://www.aljazeera.net/aljazeera.rss",
        "World"
    ),


    # ========================================================
    # FACTS / SCIENCE
    # ========================================================

    (
        "Google News Science Latest",
        "https://news.google.com/rss/search?"
        "q=science%20discovery%20space%20when%3A2d"
        "&hl=en&gl=US&ceid=US:en",
        "Facts"
    ),

    (
        "Google News Science Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%B9%D9%84%D9%85%20%D8%A7%D9%83%D8%AA%D8%B4%D8%A7%D9%81%D8%A7%D8%AA%20%D9%81%D8%B6%D8%A7%D8%A1%20when%3A2d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Facts"
    ),

    (
        "ScienceDaily",
        "https://www.sciencedaily.com/rss/top/science.xml",
        "Facts"
    ),


    # ========================================================
    # PRODUCTS
    # ========================================================

    (
        "Google News Products Latest",
        "https://news.google.com/rss/search?"
        "q=new%20products%20gadgets%20devices%20when%3A2d"
        "&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Gadgets Latest",
        "https://news.google.com/rss/search?"
        "q=new%20gadgets%20smartphones%20devices%20when%3A2d"
        "&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Products Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D9%85%D9%86%D8%AA%D8%AC%D8%A7%D8%AA%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9%20%D9%87%D9%88%D8%A7%D8%AA%D9%81%20when%3A2d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Products"
    )

]


# ============================================================
# HTTP SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({

    "User-Agent":
        "Mozilla/5.0 (compatible; NOWNEX-NewsBot/5.0)",

    "Accept":
        "application/rss+xml, application/xml, text/xml, text/html"

})


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
# VALID URL
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

            if not image:
                continue

            mime = str(
                enclosure.get(
                    "type",
                    ""
                )
            ).lower()

            if (
                "image" in mime
                or
                re.search(
                    r"\.(jpg|jpeg|png|webp|gif)(\?|$)",
                    image,
                    re.IGNORECASE
                )
            ):
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

        patterns = [

            r'<img[^>]+src=["\']([^"\']+)["\']',

            r'<img[^>]+data-src=["\']([^"\']+)["\']',

            r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']',

            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'

        ]


        for pattern in patterns:

            match = re.search(
                pattern,
                source,
                re.IGNORECASE
            )

            if not match:
                continue

            image = match.group(1)

            if "," in image:

                image = (
                    image
                    .split(",")[0]
                    .strip()
                    .split(" ")[0]
                )

            image = valid_image_url(
                image
            )

            if image:
                return image


    return ""


# ============================================================
# OG IMAGE
# ============================================================

def get_og_image(url):

    if not url:
        return ""


    try:

        response = SESSION.get(

            url,

            timeout=REQUEST_TIMEOUT,

            allow_redirects=True

        )


        if response.status_code != 200:
            return ""


        page = response.text[
            :500000
        ]


        patterns = [

            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

            r'<meta[^>]+property=["\']og:image:url["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image:url["\']',

            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']'

        ]


        for pattern in patterns:

            match = re.search(
                pattern,
                page,
                re.IGNORECASE
            )

            if not match:
                continue


            image = html.unescape(
                match.group(1).strip()
            )


            image = urljoin(
                response.url,
                image
            )


            image = valid_image_url(
                image
            )


            if image:
                return image


    except Exception as error:

        print(
            "OG image error:",
            str(error)[:150]
        )


    return ""


# ============================================================
# PUBLISHED TIMESTAMP
#
# مهم جدًا:
# لا نستخدم time.mktime لأنه يعتمد على timezone المحلي.
# نستخدم UTC بشكل صحيح.
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

            return float(
                calendar.timegm(
                    parsed
                )
            )

        except Exception:
            pass


    for field in [
        "published",
        "updated",
        "pubDate"
    ]:

        value = entry.get(
            field
        )

        if not value:
            continue


        try:

            dt = parsedate_to_datetime(
                str(value)
            )


            if dt.tzinfo is None:

                dt = dt.replace(
                    tzinfo=timezone.utc
                )


            return dt.timestamp()


        except Exception:
            pass


    return 0.0


# ============================================================
# AGE
# ============================================================

def get_age_hours(timestamp):

    if not timestamp:
        return 999999


    now = datetime.now(
        timezone.utc
    ).timestamp()


    age_seconds = (
        now - timestamp
    )


    return age_seconds / 3600


# ============================================================
# IS FRESH?
# ============================================================

def is_fresh(timestamp):

    if not timestamp:
        return False


    age_hours = get_age_hours(
        timestamp
    )


    # خبر في المستقبل بشكل غير منطقي
    if age_hours < -6:
        return False


    return age_hours <= MAX_AGE_HOURS


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(items):

    result = []

    seen_titles = set()

    seen_links = set()


    for item in items:

        title = item.get(
            "title",
            ""
        )

        link = item.get(
            "link",
            ""
        )


        title_key = normalize_title(
            title
        )

        link_key = str(
            link or ""
        ).strip().lower()


        if not title_key:
            continue


        if title_key in seen_titles:
            continue


        if link_key and link_key in seen_links:
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

    now = datetime.now(
        timezone.utc
    )

    cutoff = (
        now -
        timedelta(
            hours=MAX_AGE_HOURS
        )
    )


    print("")
    print(
        "=========================================="
    )

    print(
        "FETCHING FRESH NEWS"
    )

    print(
        "Current UTC:",
        now.isoformat()
    )

    print(
        "Cutoff UTC:",
        cutoff.isoformat()
    )

    print(
        "Maximum age:",
        MAX_AGE_HOURS,
        "hours"
    )

    print(
        "=========================================="
    )


    for (
        source_name,
        feed_url,
        category
    ) in RSS_FEEDS:

        print("")
        print(
            "--------------------------------"
        )

        print(
            "Reading:",
            source_name
        )

        print(
            "Category:",
            category
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
                "Found RSS:",
                len(entries)
            )


            fresh_count = 0


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
                ).strip()


                if not link:
                    continue


                timestamp = (
                    get_published_timestamp(
                        entry
                    )
                )


                age_hours = get_age_hours(
                    timestamp
                )


                # --------------------------------------------
                # رفض الخبر القديم
                # --------------------------------------------

                if not is_fresh(
                    timestamp
                ):

                    print(
                        "OLD:",
                        round(
                            age_hours,
                            1
                        ),
                        "hours:",
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


                    if (
                        isinstance(
                            content,
                            list
                        )
                        and content
                    ):

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
                        age_hours

                })


                fresh_count += 1


            print(
                "FRESH:",
                fresh_count
            )


        except Exception as error:

            print(
                "RSS ERROR:",
                source_name,
                str(error)[:250]
            )


    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    articles = remove_duplicates(
        articles
    )


    # ========================================================
    # SORT NEWEST FIRST
    # ========================================================

    articles.sort(

        key=lambda item:
            item.get(
                "_published_timestamp",
                0
            ),

        reverse=True

    )


    print("")
    print(
        "=========================================="
    )

    print(
        "FRESH ARTICLES AFTER FILTER:",
        len(articles)
    )

    print(
        "=========================================="
    )


    for item in articles[:30]:

        print(
            f"[{item['category']}] "
            f"{item['source']} | "
            f"{item['_age_hours']:.1f}h | "
            f"{item['title'][:100]}"
        )


    return articles


# ============================================================
# CATEGORY HELPERS
# ============================================================

def get_category_articles(
    articles,
    category
):

    return [

        article

        for article in articles

        if article.get(
            "category"
        ) == category

    ]


# ============================================================
# SELECT NEWS
#
# نأخذ 3 من كل قسم أولًا.
# إذا لم يوجد 3، نأخذ المتوفر.
# ثم نملأ حتى 30.
# ============================================================

def select_news(
    articles
):

    selected = []

    selected_keys = set()


    print("")
    print(
        "=========================================="
    )

    print(
        "SELECTING FRESH NEWS"
    )

    print(
        "=========================================="
    )


    # ========================================================
    # أولًا: 3 من كل قسم
    # ========================================================

    for category in MAIN_CATEGORIES:

        candidates = get_category_articles(

            articles,

            category

        )


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


            print(
                f"SELECTED {category}: "
                f"{article['title'][:100]}"
            )


            if count >= MIN_PER_CATEGORY:
                break


    # ========================================================
    # ملء العدد حتى 30
    # ========================================================

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
# GEMINI BATCH
# ============================================================

def ask_gemini_batch(
    articles
):

    if not articles:
        return []


    articles_text = []


    for index, article in enumerate(
        articles,
        start=1
    ):

        articles_text.append(

            f"""
ARTICLE {index}

ID:
{index}

Category:
{article.get("category", "")}

Source:
{article.get("source", "")}

Original title:
{article.get("title", "")}

Description:
{article.get("description", "")}
"""

        )


    prompt = f"""
أنت محرر الأخبار الرئيسي في NOWNEX.

حوّل الأخبار التالية إلى العربية الفصحى الحديثة.

مهم جدًا:

- لا تخترع أي معلومة.
- لا تخترع أسماء.
- لا تخترع أرقامًا.
- لا تخترع تصريحات.
- لا تضف معلومات من خارج النص.
- حافظ على معنى الخبر الأصلي.
- كل خبر يجب أن يبقى مستقلًا.
- العنوان احترافي وواضح.
- الملخص من 2 إلى 4 جمل.
- أعد JSON فقط.
- لا تستخدم Markdown.

عدد الأخبار:
{len(articles)}

صيغة JSON المطلوبة:

{{
  "articles": [
    {{
      "id": 1,
      "title_ar": "العنوان بالعربية",
      "summary_ar": "الملخص بالعربية"
    }}
  ]
}}

الأخبار:

{"".join(articles_text)}
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
                0.15,

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
        GEMINI_BATCH_RETRIES + 1
    ):

        try:

            print(
                f"Gemini batch "
                f"{attempt}/{GEMINI_BATCH_RETRIES}"
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


            if response.status_code == 429:

                if attempt < GEMINI_BATCH_RETRIES:

                    wait_time = (
                        GEMINI_RETRY_WAIT
                        * attempt
                    )

                    print(
                        "Gemini rate limit."
                    )

                    print(
                        "Waiting:",
                        wait_time
                    )

                    time.sleep(
                        wait_time
                    )

                    continue


                print(
                    "Gemini rate limit "
                    "after all retries."
                )

                return {}


            if response.status_code != 200:

                print(
                    "Gemini error:",
                    response.text[:1000]
                )

                return {}


            data = response.json()


            candidates = data.get(
                "candidates",
                []
            )


            if not candidates:

                print(
                    "Gemini returned no candidates."
                )

                return {}


            text = (

                candidates[0]
                .get(
                    "content",
                    {}
                )
                .get(
                    "parts",
                    [{}]
                )[0]
                .get(
                    "text",
                    ""
                )

            )


            if not text:

                print(
                    "Gemini returned empty text."
                )

                return {}


            text = text.strip()


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


            output = {}


            for item in result.get(
                "articles",
                []
            ):

                try:

                    article_id = int(
                        item.get(
                            "id"
                        )
                    )

                except Exception:
                    continue


                title_ar = clean_text(

                    item.get(
                        "title_ar",
                        ""
                    )

                )


                summary_ar = clean_text(

                    item.get(
                        "summary_ar",
                        ""
                    )

                )


                if not title_ar:
                    continue


                if len(summary_ar) < 40:
                    continue


                output[
                    article_id
                ] = {

                    "title_ar":
                        title_ar,

                    "summary_ar":
                        summary_ar

                }


            print(
                "Gemini generated:",
                len(output),
                "/",
                len(articles)
            )


            return output


        except Exception as error:

            print(
                "Gemini batch error:",
                str(error)[:500]
            )


            if attempt < GEMINI_BATCH_RETRIES:

                time.sleep(
                    10
                )


    return {}


# ============================================================
# PROCESS ARABIC
# ============================================================

def generate_arabic_news(
    selected
):

    final_news = []


    # ========================================================
    # تقسيم الأخبار إلى دفعات
    # ========================================================

    batches = [

        selected[i:i + GEMINI_BATCH_SIZE]

        for i in range(
            0,
            len(selected),
            GEMINI_BATCH_SIZE
        )

    ]


    print("")
    print(
        "=========================================="
    )

    print(
        "GENERATING ARABIC NEWS"
    )

    print(
        "Articles:",
        len(selected)
    )

    print(
        "Batches:",
        len(batches)
    )

    print(
        "Batch size:",
        GEMINI_BATCH_SIZE
    )

    print(
        "=========================================="
    )


    for batch_index, batch in enumerate(
        batches,
        start=1
    ):

        print("")
        print(
            "=========================================="
        )

        print(
            f"BATCH {batch_index}/{len(batches)}"
        )

        print(
            "=========================================="
        )


        translations = ask_gemini_batch(
            batch
        )


        # ====================================================
        # إنشاء النتائج
        # ====================================================

        for index, article in enumerate(
            batch,
            start=1
        ):

            # ------------------------------------------------
            # Gemini نجح
            # ------------------------------------------------

            ai = translations.get(
                index
            )


            if ai:

                title_ar = ai[
                    "title_ar"
                ]

                summary_ar = ai[
                    "summary_ar"
                ]

                ai_status = "GEMINI"


            # ------------------------------------------------
            # Gemini فشل
            #
            # لا نحذف الخبر الجديد.
            # ------------------------------------------------

            else:

                print(
                    "Gemini unavailable for:",
                    article["title"][:100]
                )


                # إذا كان الخبر عربيًا أصلًا،
                # يمكن استخدام عنوانه ووصفه مباشرة.

                original_title = article.get(
                    "title",
                    ""
                )

                original_description = article.get(
                    "description",
                    ""
                )


                title_ar = clean_text(
                    original_title
                )


                summary_ar = clean_text(
                    original_description
                )


                # إذا لم يوجد وصف،
                # نضع صياغة آمنة من العنوان فقط.

                if len(summary_ar) < 40:

                    summary_ar = (
                        title_ar
                    )


                ai_status = "RSS-FALLBACK"


            # ------------------------------------------------
            # إذا بقي العنوان فارغًا
            # ------------------------------------------------

            if not title_ar:

                print(
                    "SKIPPED — empty title"
                )

                continue


            # ------------------------------------------------
            # publishedAt
            #
            # نستخدم تاريخ نشر الخبر الحقيقي.
            # ------------------------------------------------

            timestamp = article.get(
                "_published_timestamp",
                0
            )


            if timestamp:

                published_at = (
                    datetime.fromtimestamp(
                        timestamp,
                        timezone.utc
                    ).isoformat()
                )

            else:

                published_at = (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                )


            item = {

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
                    published_at,

                "_published_timestamp":
                    timestamp,

                "_age_hours":
                    article.get(
                        "_age_hours",
                        999999
                    ),

                "_ai_status":
                    ai_status

            }


            final_news.append(
                item
            )


            print(
                "CREATED:",
                ai_status,
                "|",
                article["category"],
                "|",
                round(
                    article.get(
                        "_age_hours",
                        0
                    ),
                    1
                ),
                "h |",
                title_ar[:100]
            )


        # ====================================================
        # انتظار صغير بين الدفعات
        # ====================================================

        if batch_index < len(batches):

            time.sleep(
                BATCH_DELAY
            )


    # ========================================================
    # ترتيب نهائي
    # ========================================================

    final_news.sort(

        key=lambda item:
            item.get(
                "_published_timestamp",
                0
            ),

        reverse=True

    )


    return final_news[
        :MAX_NEWS
    ]


# ============================================================
# FETCH IMAGES
# ============================================================

def complete_images(
    selected
):

    print("")
    print(
        "=========================================="
    )

    print(
        "FETCHING IMAGES"
    )

    print(
        "=========================================="
    )


    for index, article in enumerate(
        selected,
        start=1
    ):

        if article.get(
            "image"
        ):

            print(
                f"[{index}/{len(selected)}] "
                "RSS image found."
            )

            continue


        link = article.get(
            "link",
            ""
        )


        if not link:
            continue


        print(
            f"[{index}/{len(selected)}] "
            "Trying OG image..."
        )


        image = get_og_image(
            link
        )


        if image:

            article[
                "image"
            ] = image

            print(
                "    Image: FOUND"
            )

        else:

            print(
                "    Image: NONE"
            )


    return selected


# ============================================================
# TRENDING
# ============================================================

def create_trending(
    final_news
):

    trending = []

    seen = set()


    for category in MAIN_CATEGORIES:

        category_news = [

            item

            for item in final_news

            if item.get(
                "category"
            ) == category

        ]


        for item in category_news[:2]:

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

                return trending


    return trending


# ============================================================
# CATEGORY COUNTS
# ============================================================

def get_category_counts(
    news
):

    counts = {}


    for category in MAIN_CATEGORIES:

        counts[
            category
        ] = len([

            item

            for item in news

            if item.get(
                "category"
            ) == category

        ])


    return counts


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print(
        "=========================================="
    )

    print(
        " NOWNEX NEWS ENGINE v5"
    )

    print(
        " FRESH NEWS + ARABIC + NO OLD NEWS"
    )

    print(
        "=========================================="
    )

    print(
        "Current UTC:",
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    print(
        "Maximum age:",
        MAX_AGE_HOURS,
        "hours"
    )

    print(
        "Target:",
        MAX_NEWS
    )

    print(
        "=========================================="
    )


    # ========================================================
    # 1. FETCH FRESH RSS
    # ========================================================

    articles = get_news()


    if not articles:

        raise RuntimeError(
            "No fresh RSS articles found."
        )


    print("")
    print(
        "TOTAL FRESH ARTICLES:",
        len(articles)
    )


    # ========================================================
    # 2. AVAILABLE BY CATEGORY
    # ========================================================

    print("")
    print(
        "AVAILABLE FRESH NEWS:"
    )


    available_counts = get_category_counts(
        articles
    )


    for category in MAIN_CATEGORIES:

        print(
            f"  {category}: "
            f"{available_counts[category]}"
        )


    # ========================================================
    # 3. SELECT
    # ========================================================

    selected = select_news(
        articles
    )


    print("")
    print(
        "SELECTED:",
        len(selected)
    )


    if not selected:

        raise RuntimeError(
            "No fresh news selected."
        )


    # ========================================================
    # 4. IMAGES
    # ========================================================

    selected = complete_images(
        selected
    )


    # ========================================================
    # 5. GEMINI
    # ========================================================

    final_news = generate_arabic_news(
        selected
    )


    # ========================================================
    # 6. SAFETY CHECK
    # ========================================================

    if not final_news:

        raise RuntimeError(
            "No news could be generated."
        )


    # ========================================================
    # مهم:
    #
    # نتأكد أن كل الأخبار المنشورة حديثة.
    # ========================================================

    fresh_final_news = []


    for item in final_news:

        timestamp = item.get(
            "_published_timestamp",
            0
        )


        if not is_fresh(
            timestamp
        ):

            print(
                "FINAL FILTER REMOVED OLD:",
                item.get(
                    "title_ar",
                    ""
                )
            )

            continue


        fresh_final_news.append(
            item
        )


    final_news = fresh_final_news


    if not final_news:

        raise RuntimeError(
            "All generated news became stale."
        )


    # ========================================================
    # 7. FINAL SORT
    # ========================================================

    final_news.sort(

        key=lambda item:
            item.get(
                "_published_timestamp",
                0
            ),

        reverse=True

    )


    # ========================================================
    # 8. CATEGORY COUNTS
    # ========================================================

    category_counts = get_category_counts(
        final_news
    )


    print("")
    print(
        "=========================================="
    )

    print(
        "FINAL CATEGORY COUNTS"
    )

    print(
        "=========================================="
    )


    for category in MAIN_CATEGORIES:

        print(
            f"{category}: "
            f"{category_counts[category]}"
        )


    # ========================================================
    # 9. TRENDING
    # ========================================================

    trending_news = create_trending(
        final_news
    )


    # ========================================================
    # 10. REMOVE INTERNAL FIELDS
    # ========================================================

    clean_final_news = []


    for item in final_news:

        clean_item = {

            "title_ar":
                item.get(
                    "title_ar",
                    ""
                ),

            "summary_ar":
                item.get(
                    "summary_ar",
                    ""
                ),

            "title":
                item.get(
                    "title",
                    ""
                ),

            "summary":
                item.get(
                    "summary",
                    ""
                ),

            "description":
                item.get(
                    "description",
                    ""
                ),

            "category":
                item.get(
                    "category",
                    ""
                ),

            "source":
                item.get(
                    "source",
                    ""
                ),

            "link":
                item.get(
                    "link",
                    ""
                ),

            "image":
                item.get(
                    "image",
                    ""
                ),

            "published":
                item.get(
                    "published",
                    ""
                ),

            "publishedAt":
                item.get(
                    "publishedAt",
                    ""
                )

        }


        clean_final_news.append(
            clean_item
        )


    clean_trending = []


    for item in trending_news:

        clean_trending.append({

            "title_ar":
                item.get(
                    "title_ar",
                    ""
                ),

            "summary_ar":
                item.get(
                    "summary_ar",
                    ""
                ),

            "title":
                item.get(
                    "title",
                    ""
                ),

            "summary":
                item.get(
                    "summary",
                    ""
                ),

            "description":
                item.get(
                    "description",
                    ""
                ),

            "category":
                "Trending",

            "source":
                item.get(
                    "source",
                    ""
                ),

            "link":
                item.get(
                    "link",
                    ""
                ),

            "image":
                item.get(
                    "image",
                    ""
                ),

            "published":
                item.get(
                    "published",
                    ""
                ),

            "publishedAt":
                item.get(
                    "publishedAt",
                    ""
                )

        })


    # ========================================================
    # 11. OUTPUT
    # ========================================================

    updated_at = datetime.now(
        timezone.utc
    ).isoformat()


    output = {

        "updatedAt":
            updated_at,

        "count":
            len(clean_final_news),

        "trendingCount":
            len(clean_trending),

        "news":
            clean_final_news,

        "trending":
            clean_trending

    }


    # ========================================================
    # 12. SAVE
    #
    # هذه المرة نكتب الملف حتى لو Gemini فشل جزئيًا.
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
    # 13. REPORT
    # ========================================================

    images_count = len([

        item

        for item in clean_final_news

        if item.get(
            "image"
        )

    ])


    gemini_count = len([

        item

        for item in final_news

        if item.get(
            "_ai_status"
        ) == "GEMINI"

    ])


    fallback_count = len([

        item

        for item in final_news

        if item.get(
            "_ai_status"
        ) == "RSS-FALLBACK"

    ])


    print("")
    print(
        "=========================================="
    )

    print(
        " NOWNEX UPDATED SUCCESSFULLY"
    )

    print(
        "=========================================="
    )

    print(
        "Updated:",
        updated_at
    )

    print(
        "Articles:",
        len(clean_final_news)
    )

    print(
        "Trending:",
        len(clean_trending)
    )

    print(
        "Images:",
        f"{images_count}/{len(clean_final_news)}"
    )

    print(
        "Gemini:",
        gemini_count
    )

    print(
        "Fallback:",
        fallback_count
    )

    print("")
    print(
        "FINAL CATEGORY COUNTS:"
    )


    for category in MAIN_CATEGORIES:

        print(
            f"  {category}: "
            f"{category_counts[category]}"
        )


    print("")
    print(
        "=========================================="
    )

    print(
        "news.json saved successfully."
    )

    print(
        "OLD NEWS ARE NOT ALLOWED."
    )

    print(
        "=========================================="
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
