import os
import json
import re
import html
import time
import calendar
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
import feedparser


# ============================================================
# NOWNEX — NEWS ENGINE v5
# ============================================================
#
# الهدف:
# - أخبار حديثة فقط
# - آخر 72 ساعة
# - ترتيب حسب تاريخ النشر الحقيقي
# - 3 أخبار على الأقل لكل قسم
# - 30 خبرًا كحد أقصى
# - العربية عبر Gemini
# - الصور بعد اختيار الأخبار
# - منع الأخبار القديمة من الدخول
# ============================================================


# ============================================================
# GEMINI API
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


# إذا لم يتم تحديد المتغير في GitHub
# سيستخدم هذا النموذج
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
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

ENTRIES_PER_FEED = 15

REQUEST_TIMEOUT = 15

GEMINI_TIMEOUT = 60

REQUEST_DELAY = 0.5


# ============================================================
# IMPORTANT:
# الخبر يجب ألا يكون أقدم من هذا العدد من الساعات.
#
# 72 ساعة = آخر 3 أيام
# ============================================================

MAX_AGE_HOURS = 72


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
        "TechCrunch AI",
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "AI"
    ),

    (
        "Google News AI",
        "https://news.google.com/rss/search?"
        "q=artificial%20intelligence%20AI%20when%3A3d"
        "&hl=en&gl=US&ceid=US:en",
        "AI"
    ),

    (
        "Google News AI Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1%20%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A%20when%3A3d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
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
        "Google News Technology",
        "https://news.google.com/rss/search?"
        "q=technology%20smartphones%20gadgets%20when%3A3d"
        "&hl=en&gl=US&ceid=US:en",
        "Technology"
    ),

    (
        "Google News Technology Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%AA%D9%83%D9%86%D9%88%D9%84%D9%88%D8%AC%D9%8A%D8%A7%20%D9%87%D9%88%D8%A7%D8%AA%D9%81%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9%20when%3A3d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Technology"
    ),


    # ========================================================
    # CARS
    # ========================================================

    (
        "Motor1",
        "https://www.motor1.com/rss/news/",
        "Cars"
    ),

    (
        "Motor1 Technology",
        "https://www.motor1.com/rss/technology/",
        "Cars"
    ),

    (
        "Car and Driver",
        "https://www.caranddriver.com/rss/all.xml",
        "Cars"
    ),

    (
        "Google News Cars",
        "https://news.google.com/rss/search?"
        "q=cars%20automotive%20electric%20vehicles%20when%3A3d"
        "&hl=en&gl=US&ceid=US:en",
        "Cars"
    ),

    (
        "Google News Cars Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%B3%D9%8A%D8%A7%D8%B1%D8%A7%D8%AA%20%D9%83%D9%87%D8%B1%D8%A8%D8%A7%D8%A6%D9%8A%D8%A9%20when%3A3d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Cars"
    ),


    # ========================================================
    # ENTERTAINMENT
    # ========================================================

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
        "Google News Entertainment",
        "https://news.google.com/rss/search?"
        "q=entertainment%20movies%20music%20games%20when%3A3d"
        "&hl=en&gl=US&ceid=US:en",
        "Entertainment"
    ),

    (
        "Google News Entertainment Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%AA%D8%B1%D9%81%D9%8A%D9%87%20%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D9%85%D9%88%D8%B3%D9%8A%D9%82%D9%89%20%D8%A3%D9%84%D8%B9%D8%A7%D8%A8%20when%3A3d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Entertainment"
    ),


    # ========================================================
    # WORLD
    # ========================================================

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

    (
        "Google News World Arabic",
        "https://news.google.com/rss/search?"
        "q=world%20news%20%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1%20%D8%A7%D9%84%D8%B9%D8%A7%D9%84%D9%85%20when%3A3d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "World"
    ),

    (
        "Google News World",
        "https://news.google.com/rss/search?"
        "q=world%20news%20when%3A3d"
        "&hl=en&gl=US&ceid=US:en",
        "World"
    ),


    # ========================================================
    # FACTS / SCIENCE
    # ========================================================

    (
        "ScienceDaily",
        "https://www.sciencedaily.com/rss/top/science.xml",
        "Facts"
    ),

    (
        "Google News Science",
        "https://news.google.com/rss/search?"
        "q=science%20discovery%20space%20when%3A3d"
        "&hl=en&gl=US&ceid=US:en",
        "Facts"
    ),

    (
        "Google News Science Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%B9%D9%84%D9%85%20%D8%A7%D9%83%D8%AA%D8%B4%D8%A7%D9%81%D8%A7%D8%AA%20%D9%81%D8%B6%D8%A7%D8%A1%20when%3A3d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Facts"
    ),


    # ========================================================
    # PRODUCTS
    # ========================================================

    (
        "Google News Products",
        "https://news.google.com/rss/search?"
        "q=new%20products%20gadgets%20when%3A3d"
        "&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Gadgets",
        "https://news.google.com/rss/search?"
        "q=new%20gadgets%20smartphones%20devices%20when%3A3d"
        "&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Products Arabic",
        "https://news.google.com/rss/search?"
        "q=%D9%85%D9%86%D8%AA%D8%AC%D8%A7%D8%AA%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9%20%D9%87%D9%88%D8%A7%D8%AA%D9%81%20when%3A3d"
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
# CURRENT UTC TIME
# ============================================================

def now_utc():

    return datetime.now(
        timezone.utc
    )


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
# VALID IMAGE URL
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

            image = (
                media.get("url")
                or
                media.get("href")
                or
                media.get("src")
            )

            image = valid_image_url(
                image
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

            image = (
                media.get("url")
                or
                media.get("href")
                or
                media.get("src")
            )

            image = valid_image_url(
                image
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

            image = (
                enclosure.get("href")
                or
                enclosure.get("url")
            )

            image = valid_image_url(
                image
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

        for content_item in content:

            if isinstance(
                content_item,
                dict
            ):

                html_sources.append(
                    content_item.get(
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
# GET OG IMAGE
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
# GET PUBLISHED DATETIME
#
# هذه أهم دالة في النسخة الجديدة.
# ============================================================

def get_published_datetime(entry):

    parsed = entry.get(
        "published_parsed"
    )


    if not parsed:

        parsed = entry.get(
            "updated_parsed"
        )


    if parsed:

        try:

            timestamp = calendar.timegm(
                parsed
            )

            return datetime.fromtimestamp(
                timestamp,
                timezone.utc
            )

        except Exception:

            pass


    # محاولة ثانية من النص
    raw_date = (
        entry.get("published")
        or
        entry.get("updated")
        or
        ""
    )


    raw_date = str(
        raw_date
    ).strip()


    if raw_date:

        try:

            parsed_date = feedparser._parse_date(
                raw_date
            )

            if parsed_date:

                timestamp = calendar.timegm(
                    parsed_date
                )

                return datetime.fromtimestamp(
                    timestamp,
                    timezone.utc
                )

        except Exception:

            pass


    return None


# ============================================================
# CHECK IF NEWS IS FRESH
# ============================================================

def is_fresh_article(
    published_dt
):

    if not published_dt:
        return False


    current = now_utc()


    age = (
        current - published_dt
    ).total_seconds()


    # لا نقبل أخبارًا مستقبلية بشكل كبير
    if age < -3600:
        return False


    max_age = (
        MAX_AGE_HOURS * 3600
    )


    return age <= max_age


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


    current = now_utc()

    oldest_allowed = (
        current
        -
        timedelta(
            hours=MAX_AGE_HOURS
        )
    )


    print("")
    print(
        "=========================================="
    )

    print(
        "NEWS FRESHNESS FILTER"
    )

    print(
        "Current UTC:",
        current.isoformat()
    )

    print(
        "Oldest allowed:",
        oldest_allowed.isoformat()
    )

    print(
        f"Maximum age: {MAX_AGE_HOURS} hours"
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
                "RSS entries:",
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


                # ==========================================
                # REAL PUBLICATION DATE
                # ==========================================

                published_dt = (
                    get_published_datetime(
                        entry
                    )
                )


                # ==========================================
                # IMPORTANT:
                # تجاهل أي خبر بدون تاريخ حقيقي
                # ==========================================

                if not published_dt:

                    print(
                        "SKIP — no publication date:",
                        title[:100]
                    )

                    continue


                # ==========================================
                # IMPORTANT:
                # تجاهل الأخبار القديمة
                # ==========================================

                if published_dt < oldest_allowed:

                    print(
                        "SKIP — OLD:",
                        published_dt.isoformat(),
                        "|",
                        title[:100]
                    )

                    continue


                # ==========================================
                # DESCRIPTION
                # ==========================================

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


                # ==========================================
                # RSS IMAGE
                # ==========================================

                image = extract_rss_image(
                    entry
                )


                published_text = clean_text(

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
                        published_text,

                    # تاريخ حقيقي وليس وقت التشغيل
                    "_published_datetime":
                        published_dt,

                    "_published_timestamp":
                        published_dt.timestamp()

                })


                fresh_count += 1


            print(
                "Fresh:",
                fresh_count
            )


        except Exception as error:

            print(
                "RSS ERROR:",
                source_name,
                str(error)[:250]
            )


    # ========================================================
    # إزالة التكرار
    # ========================================================

    articles = remove_duplicates(
        articles
    )


    # ========================================================
    # ترتيب حقيقي:
    # الأحدث أولًا
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


    for article in articles[:10]:

        print(
            article["category"],
            "|",
            article["_published_datetime"].isoformat(),
            "|",
            article["title"][:100]
        )


    return articles


# ============================================================
# SUMMARY VALIDATION
# ============================================================

def summary_is_valid(
    title,
    summary
):

    summary = clean_text(
        summary
    )


    if not summary:
        return False


    if len(summary) < 100:
        return False


    if summary.lower() == clean_text(
        title
    ).lower():

        return False


    sentences = len(

        re.findall(
            r"[.!؟。]",
            summary
        )

    )


    if sentences < 2:
        return False


    return True


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(
    title,
    description,
    source,
    category
):

    if not description:

        description = (
            "لا يوجد وصف إضافي متاح. "
            "استخدم المعلومات الموجودة في العنوان "
            "فقط ولا تضف أي معلومات غير مؤكدة."
        )


    prompt = f"""
أنت محرر الأخبار الرئيسي في NOWNEX.

حوّل الخبر التالي إلى خبر عربي احترافي.

المصدر:
{source}

القسم:
{category}

العنوان الأصلي:
{title}

المعلومات المتاحة:
{description}

أعد JSON فقط بهذا الشكل:

{{
  "title_ar": "عنوان عربي احترافي",
  "summary_ar": "ملخص عربي من 3 إلى 5 جمل"
}}

القواعد:

1. استخدم العربية الفصحى الحديثة.
2. لا تخترع أي معلومة.
3. لا تخترع أسماء.
4. لا تخترع أرقاماً.
5. لا تخترع تصريحات.
6. لا تضف رأياً شخصياً.
7. استخدم المعلومات الموجودة فقط.
8. الملخص من 3 إلى 5 جمل.
9. العنوان واضح ومهني.
10. أعد JSON صالحاً فقط.
11. لا تستخدم Markdown.
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
        4
    ):

        try:

            print(
                f"Gemini request {attempt}/3"
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

                wait_time = (

                    15
                    if attempt == 1

                    else

                    30
                    if attempt == 2

                    else

                    45

                )


                print(
                    "Rate limit. Waiting:",
                    wait_time
                )


                time.sleep(
                    wait_time
                )

                continue


            if response.status_code != 200:

                print(
                    response.text[:1000]
                )

                return None


            data = response.json()


            candidates = data.get(
                "candidates",
                []
            )


            if not candidates:

                print(
                    "Gemini returned no candidates."
                )

                return None


            text = (

                candidates[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")

            )


            if not text:

                print(
                    "Gemini returned empty text."
                )

                return None


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


            title_ar = clean_text(

                result.get(
                    "title_ar",
                    ""
                )

            )


            summary_ar = clean_text(

                result.get(
                    "summary_ar",
                    ""
                )

            )


            if not title_ar:

                return None


            if not summary_is_valid(

                title_ar,
                summary_ar

            ):

                print(
                    "Invalid Arabic summary."
                )

                return None


            return {

                "title_ar":
                    title_ar,

                "summary_ar":
                    summary_ar

            }


        except Exception as error:

            print(
                "Gemini error:",
                str(error)[:400]
            )


            if attempt < 3:

                time.sleep(
                    5
                )


    return None


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
# ============================================================

def select_news(
    articles
):

    selected = []

    selected_keys = set()


    # ========================================================
    # أولاً:
    # أحدث 3 أخبار لكل قسم
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
                "SELECTED",
                category,
                "|",
                article.get(
                    "_published_datetime"
                ).isoformat(),
                "|",
                article.get(
                    "title",
                    ""
                )
            )


            if count >= MIN_PER_CATEGORY:
                break


    # ========================================================
    # الأخبار الإضافية
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


    # ========================================================
    # إعادة ترتيب المختارات حسب التاريخ الحقيقي
    # ========================================================

    selected.sort(

        key=lambda item:
            item.get(
                "_published_timestamp",
                0
            ),

        reverse=True

    )


    return selected[
        :MAX_NEWS
    ]


# ============================================================
# CREATE TRENDING
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
        "FETCHING IMAGES FOR SELECTED NEWS ONLY"
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
                "Image already available from RSS."
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

            article["image"] = image

            print(
                "    Image: FOUND"
            )

        else:

            print(
                "    Image: NONE"
            )


    return selected


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
        " FRESH + ARABIC + LATEST NEWS"
    )

    print(
        "=========================================="
    )

    print(
        "Gemini model:",
        GEMINI_MODEL
    )

    print(
        "Target:",
        MAX_NEWS
    )

    print(
        "Minimum per category:",
        MIN_PER_CATEGORY
    )

    print(
        "Maximum news age:",
        MAX_AGE_HOURS,
        "hours"
    )

    print("")


    # ========================================================
    # 1. READ RSS
    # ========================================================

    articles = get_news()


    if not articles:

        raise RuntimeError(
            "No fresh RSS articles found."
        )


    print("")
    print(
        "TOTAL FRESH COLLECTED:",
        len(articles)
    )


    # ========================================================
    # 2. REPORT AVAILABLE NEWS
    # ========================================================

    print("")
    print(
        "AVAILABLE FRESH NEWS BY CATEGORY:"
    )


    for category in MAIN_CATEGORIES:

        count = len(

            get_category_articles(
                articles,
                category
            )

        )


        print(
            f"  {category}: {count}"
        )


    # ========================================================
    # 3. CHECK BEFORE AI
    # ========================================================

    for category in MAIN_CATEGORIES:

        count = len(

            get_category_articles(
                articles,
                category
            )

        )


        if count < MIN_PER_CATEGORY:

            raise RuntimeError(

                f"Not enough FRESH news for "
                f"{category}: "
                f"{count}/{MIN_PER_CATEGORY}. "
                f"news.json was NOT modified."

            )


    # ========================================================
    # 4. SELECT NEWS
    # ========================================================

    selected = select_news(
        articles
    )


    print("")
    print(
        "SELECTED:",
        len(selected)
    )


    if len(selected) < MAX_NEWS:

        print(
            "WARNING: Only",
            len(selected),
            "fresh articles available."
        )


    # ========================================================
    # 5. VERIFY SELECTION
    # ========================================================

    print("")
    print(
        "SELECTED BY CATEGORY:"
    )


    for category in MAIN_CATEGORIES:

        count = len([

            item

            for item in selected

            if item.get(
                "category"
            ) == category

        ])


        print(
            f"  {category}: {count}"
        )


    # ========================================================
    # 6. FETCH IMAGES
    # ========================================================

    selected = complete_images(
        selected
    )


    # ========================================================
    # 7. GENERATE ARABIC
    # ========================================================

    final_news = []


    for index, article in enumerate(

        selected,

        start=1

    ):

        print("")
        print(
            "=========================================="
        )

        print(
            f"PROCESSING {index}/{len(selected)}"
        )

        print(
            "Category:",
            article["category"]
        )

        print(
            "Source:",
            article["source"]
        )

        print(
            "Published:",
            article.get(
                "published",
                ""
            )
        )

        print(
            "Published UTC:",
            article.get(
                "_published_datetime"
            ).isoformat()
        )

        print(
            "Title:",
            article["title"]
        )

        print(
            "Image:",
            "YES"
            if article.get("image")
            else
            "NO"
        )


        ai = ask_gemini(

            article["title"],

            article["description"],

            article["source"],

            article["category"]

        )


        if not ai:

            print(
                "SKIPPED — Gemini failed"
            )

            continue


        # ====================================================
        # REAL PUBLICATION DATE
        # ====================================================

        published_dt = article.get(
            "_published_datetime"
        )


        published_iso = (

            published_dt.isoformat()

            if published_dt

            else
            ""

        )


        item = {

            "title_ar":
                ai["title_ar"],

            "summary_ar":
                ai["summary_ar"],

            "title":
                ai["title_ar"],

            "summary":
                ai["summary_ar"],

            "description":
                ai["summary_ar"],

            "category":
                article["category"],

            "source":
                article["source"],

            "link":
                article["link"],

            "image":
                article.get(
                    "image",
                    ""
                ),

            # ================================================
            # التاريخ الحقيقي للخبر
            # ================================================

            "published":
                article.get(
                    "published",
                    ""
                ),

            "publishedAt":
                published_iso,

            # ================================================
            # وقت جلب الخبر
            # ================================================

            "fetchedAt":
                now_utc().isoformat()

        }


        final_news.append(
            item
        )


        print(
            "CREATED ✓"
        )


        time.sleep(
            REQUEST_DELAY
        )


    # ========================================================
    # 8. FINAL CATEGORY CHECK
    # ========================================================

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


    category_counts = {}


    for category in MAIN_CATEGORIES:

        count = len([

            item

            for item in final_news

            if item.get(
                "category"
            ) == category

        ])


        category_counts[
            category
        ] = count


        print(
            f"{category}: "
            f"{count}/{MIN_PER_CATEGORY}"
        )


    missing_categories = [

        category

        for category in MAIN_CATEGORIES

        if category_counts.get(
            category,
            0
        ) < MIN_PER_CATEGORY

    ]


    # ========================================================
    # إذا فشل قسم:
    # لا نستبدل الأخبار القديمة
    # ========================================================

    if missing_categories:

        print("")
        print(
            "=========================================="
        )

        print(
            "ERROR — FRESH NEWS VALIDATION FAILED"
        )

        print(
            "=========================================="
        )


        for category in missing_categories:

            print(

                f"{category}: "
                f"{category_counts.get(category, 0)}/"
                f"{MIN_PER_CATEGORY}"

            )


        print("")
        print(
            "Existing news.json was NOT modified."
        )


        raise RuntimeError(
            "Not enough fresh valid articles."
        )


    # ========================================================
    # 9. TRENDING
    # ========================================================

    trending_news = create_trending(
        final_news
    )


    # ========================================================
    # 10. SORT FINAL NEWS AGAIN
    #
    # مهم جدًا للواجهة.
    # ========================================================

    final_news.sort(

        key=lambda item:
            item.get(
                "publishedAt",
                ""
            ),

        reverse=True

    )


    trending_news.sort(

        key=lambda item:
            item.get(
                "publishedAt",
                ""
            ),

        reverse=True

    )


    # ========================================================
    # 11. OUTPUT
    # ========================================================

    output = {

        "updatedAt":
            now_utc().isoformat(),

        "count":
            len(final_news),

        "trendingCount":
            len(trending_news),

        "maxAgeHours":
            MAX_AGE_HOURS,

        "news":
            final_news,

        "trending":
            trending_news

    }


    # ========================================================
    # 12. SAVE news.json
    # ========================================================

    temp_file = "news.json.tmp"


    with open(

        temp_file,

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(

            output,

            file,

            ensure_ascii=False,

            indent=2

        )


    # استبدال الملف فقط بعد نجاح الكتابة
    os.replace(
        temp_file,
        "news.json"
    )


    # ========================================================
    # 13. FINAL REPORT
    # ========================================================

    print("")
    print(
        "=========================================="
    )

    print(
        " NOWNEX NEWS UPDATED SUCCESSFULLY"
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


    images_count = len([

        item

        for item in final_news

        if item.get(
            "image"
        )

    ])


    print(
        "Images:",
        f"{images_count}/{len(final_news)}"
    )


    print(
        "Maximum article age:",
        MAX_AGE_HOURS,
        "hours"
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
        "LATEST 10 ARTICLES:"
    )


    for item in final_news[:10]:

        print(
            item.get(
                "publishedAt",
                ""
            ),
            "|",
            item.get(
                "category",
                ""
            ),
            "|",
            item.get(
                "title_ar",
                ""
            )
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
