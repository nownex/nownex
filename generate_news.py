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
# NOWNEX — FRESH NEWS ENGINE v5
#
# الهدف:
# - جلب أخبار حديثة فعلية
# - ترتيب حسب وقت النشر الحقيقي
# - منع الأخبار القديمة
# - 3 أخبار على الأقل لكل قسم عند توفرها
# - جمع عدد كبير من الأخبار قبل الاختيار
# - Gemini فقط للترجمة/التحرير
# - الصور بعد اختيار الأخبار فقط
# ============================================================


# ============================================================
# GEMINI API
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


# Gemini 3.7 Flash
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.7-flash"
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

# لا نأخذ أول 15 فقط.
# نريد مخزونًا أكبر حتى نستطيع اختيار الأحدث.
ENTRIES_PER_FEED = 50

REQUEST_TIMEOUT = 15

GEMINI_TIMEOUT = 60

REQUEST_DELAY = 1


# ============================================================
# FRESHNESS
# ============================================================

# الأخبار التي تعتبر حديثة جدًا.
FRESH_HOURS = 48

# أقصى عمر مسموح به في حالة الحاجة.
# لن نذهب إلى أسبوع أو شهر مثل النظام القديم.
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
#
# مهم:
# Google News queries تستخدم when:1d
# للحصول على أخبار اليوم/آخر 24 ساعة.
# ============================================================

RSS_FEEDS = [

    # ========================================================
    # AI
    # ========================================================

    (
        "Google News AI Latest",
        "https://news.google.com/rss/search?"
        "q=artificial%20intelligence%20AI%20when%3A1d"
        "&hl=en&gl=US&ceid=US:en",
        "AI"
    ),

    (
        "Google News AI Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1%20%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A%20when%3A1d"
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
        "q=technology%20smartphones%20gadgets%20when%3A1d"
        "&hl=en&gl=US&ceid=US:en",
        "Technology"
    ),

    (
        "Google News Technology Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%AA%D9%83%D9%86%D9%88%D9%84%D9%88%D8%AC%D9%8A%D8%A7%20%D9%87%D9%88%D8%A7%D8%AA%D9%81%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9%20when%3A1d"
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
        "q=cars%20automotive%20electric%20vehicles%20when%3A1d"
        "&hl=en&gl=US&ceid=US:en",
        "Cars"
    ),

    (
        "Google News Cars Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%B3%D9%8A%D8%A7%D8%B1%D8%A7%D8%AA%20%D8%B3%D9%8A%D8%A7%D8%B1%D8%A7%D8%AA%20%D9%83%D9%87%D8%B1%D8%A8%D8%A7%D8%A6%D9%8A%D8%A9%20when%3A1d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Cars"
    ),

    (
        "Car and Driver",
        "https://www.caranddriver.com/rss/all.xml",
        "Cars"
    ),

    (
        "MotorTrend",
        "https://www.motortrend.com/feed/",
        "Cars"
    ),


    # ========================================================
    # ENTERTAINMENT
    # ========================================================

    (
        "Google News Entertainment Latest",
        "https://news.google.com/rss/search?"
        "q=entertainment%20movies%20music%20games%20when%3A1d"
        "&hl=en&gl=US&ceid=US:en",
        "Entertainment"
    ),

    (
        "Google News Entertainment Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%AA%D8%B1%D9%81%D9%8A%D9%87%20%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D9%85%D9%88%D8%B3%D9%8A%D9%82%D9%89%20%D8%A3%D9%84%D8%B9%D8%A7%D8%A8%20when%3A1d"
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
        "q=world%20news%20when%3A1d"
        "&hl=en&gl=US&ceid=US:en",
        "World"
    ),

    (
        "Google News World Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1%20%D8%A7%D9%84%D8%B9%D8%A7%D9%84%D9%85%20when%3A1d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "World"
    ),

    (
        "BBC Arabic",
        "https://feeds.bbci.co.uk/arabic/rss.xml",
        "World"
    ),

    (
        "Google News Middle East Latest",
        "https://news.google.com/rss/search?"
        "q=Middle%20East%20news%20when%3A1d"
        "&hl=en&gl=US&ceid=US:en",
        "World"
    ),


    # ========================================================
    # FACTS / SCIENCE
    # ========================================================

    (
        "Google News Science Latest",
        "https://news.google.com/rss/search?"
        "q=science%20discovery%20space%20when%3A1d"
        "&hl=en&gl=US&ceid=US:en",
        "Facts"
    ),

    (
        "Google News Science Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D8%B9%D9%84%D9%85%20%D8%A7%D9%83%D8%AA%D8%B4%D8%A7%D9%81%D8%A7%D8%AA%20%D9%81%D8%B6%D8%A7%D8%A1%20when%3A1d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Facts"
    ),

    (
        "ScienceDaily",
        "https://www.sciencedaily.com/rss/top/science.xml",
        "Facts"
    ),

    (
        "Google News Space Latest",
        "https://news.google.com/rss/search?"
        "q=space%20NASA%20astronomy%20when%3A1d"
        "&hl=en&gl=US&ceid=US:en",
        "Facts"
    ),


    # ========================================================
    # PRODUCTS
    # ========================================================

    (
        "Google News Products Latest",
        "https://news.google.com/rss/search?"
        "q=new%20products%20gadgets%20devices%20when%3A1d"
        "&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Products Arabic Latest",
        "https://news.google.com/rss/search?"
        "q=%D9%85%D9%86%D8%AA%D8%AC%D8%A7%D8%AA%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9%20%D9%87%D9%88%D8%A7%D8%AA%D9%81%20when%3A1d"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Products"
    ),

    (
        "Google News Smartphones Latest",
        "https://news.google.com/rss/search?"
        "q=new%20smartphones%20devices%20when%3A1d"
        "&hl=en&gl=US&ceid=US:en",
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

    # media_content
    media_content = entry.get(
        "media_content",
        []
    )

    if isinstance(media_content, list):

        for media in media_content:

            if not isinstance(media, dict):
                continue

            image = (
                media.get("url")
                or media.get("href")
                or media.get("src")
            )

            image = valid_image_url(image)

            if image:
                return image


    # media_thumbnail
    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    if isinstance(media_thumbnail, list):

        for media in media_thumbnail:

            if not isinstance(media, dict):
                continue

            image = (
                media.get("url")
                or media.get("href")
                or media.get("src")
            )

            image = valid_image_url(image)

            if image:
                return image


    # enclosures
    enclosures = entry.get(
        "enclosures",
        []
    )

    if isinstance(enclosures, list):

        for enclosure in enclosures:

            if not isinstance(enclosure, dict):
                continue

            image = (
                enclosure.get("href")
                or enclosure.get("url")
            )

            image = valid_image_url(image)

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


    # HTML داخل RSS
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

    if isinstance(content, list):

        for content_item in content:

            if isinstance(content_item, dict):

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

            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

            r'<img[^>]+src=["\']([^"\']+)["\']',

            r'<img[^>]+data-src=["\']([^"\']+)["\']',

            r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']'

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

            image = valid_image_url(image)

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


        page = response.text[:500000]


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
            "OG IMAGE ERROR:",
            str(error)[:150]
        )


    return ""


# ============================================================
# GET PUBLISHED TIMESTAMP
#
# نستخدم calendar.timegm بدل time.mktime
# حتى لا يتأثر الترتيب بالـ timezone الخاص بـ GitHub.
# ============================================================

def get_published_timestamp(entry):

    parsed = entry.get(
        "published_parsed"
    )


    if not parsed:

        parsed = entry.get(
            "updated_parsed"
        )


    if not parsed:
        return 0


    try:

        return calendar.timegm(
            parsed
        )

    except Exception:

        return 0


# ============================================================
# FORMAT AGE
# ============================================================

def format_age(timestamp):

    if not timestamp:
        return "UNKNOWN"


    now = datetime.now(
        timezone.utc
    ).timestamp()


    seconds = max(
        0,
        now - timestamp
    )


    minutes = int(
        seconds / 60
    )


    if minutes < 60:

        return f"{minutes}m ago"


    hours = int(
        minutes / 60
    )


    if hours < 24:

        return f"{hours}h ago"


    days = int(
        hours / 24
    )


    return f"{days}d ago"


# ============================================================
# IS FRESH
# ============================================================

def is_fresh(
    timestamp,
    max_age_hours=MAX_AGE_HOURS
):

    if not timestamp:
        return False


    now = datetime.now(
        timezone.utc
    ).timestamp()


    age = (
        now - timestamp
    )


    return (
        age >= 0
        and
        age <= max_age_hours * 3600
    )


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


    for (
        source_name,
        feed_url,
        category
    ) in RSS_FEEDS:

        print("")
        print(
            "------------------------------------------"
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
                ).strip()


                if not link:
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
                        and
                        content
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


                published = clean_text(

                    entry.get(
                        "published",
                        entry.get(
                            "updated",
                            ""
                        )
                    )

                )


                timestamp = (
                    get_published_timestamp(
                        entry
                    )
                )


                # ------------------------------------------------
                # الأخبار بدون تاريخ لا ندخلها.
                # ------------------------------------------------

                if not timestamp:

                    print(
                        "SKIP — no publication date:",
                        title[:100]
                    )

                    continue


                # ------------------------------------------------
                # رفض الأخبار الأقدم من MAX_AGE_HOURS
                # ------------------------------------------------

                if not is_fresh(
                    timestamp,
                    MAX_AGE_HOURS
                ):

                    print(
                        "SKIP OLD:",
                        format_age(timestamp),
                        "|",
                        title[:100]
                    )

                    continue


                image = extract_rss_image(
                    entry
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
                        timestamp

                })


        except Exception as error:

            print(
                "RSS ERROR:",
                source_name,
                str(error)[:250]
            )


    # إزالة التكرار
    articles = remove_duplicates(
        articles
    )


    # الأحدث أولًا
    articles.sort(

        key=lambda item:
            item.get(
                "_published_timestamp",
                0
            ),

        reverse=True

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


    if len(summary) < 80:
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
# EXTRACT GEMINI JSON
#
# يحاول استخراج JSON حتى لو Gemini وضع نصًا حوله.
# ============================================================

def extract_json_object(text):

    text = str(
        text or ""
    ).strip()


    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )


    text = re.sub(
        r"^```\s*",
        "",
        text
    )


    text = re.sub(
        r"\s*```$",
        "",
        text
    )


    try:

        return json.loads(
            text
        )

    except Exception:
        pass


    # البحث عن أول JSON object
    start = text.find("{")
    end = text.rfind("}")


    if start >= 0 and end > start:

        candidate = text[
            start:end + 1
        ]


        try:

            return json.loads(
                candidate
            )

        except Exception:
            return None


    return None


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
            "اعتمد على العنوان فقط، "
            "ولا تضف معلومات غير مؤكدة."
        )


    # لا نرسل وصفًا ضخمًا إلى Gemini
    description = description[
        :5000
    ]


    prompt = f"""
أنت محرر الأخبار الرئيسي في NOWNEX.

حوّل الخبر التالي إلى صياغة عربية فصحى احترافية.

المصدر:
{source}

القسم:
{category}

العنوان الأصلي:
{title}

النص/الوصف:
{description}

أعد JSON فقط بالشكل التالي:

{{
  "title_ar": "عنوان عربي واضح",
  "summary_ar": "ملخص عربي من 3 إلى 5 جمل"
}}

القواعد المهمة:

- استخدم العربية الفصحى الحديثة.
- لا تخترع أي معلومة.
- لا تخترع أسماء.
- لا تخترع أرقامًا.
- لا تخترع تصريحات.
- لا تضف رأيًا.
- لا تضف أحداثًا غير موجودة في النص.
- لا تقل إن الخبر حدث اليوم إلا إذا كان ذلك واضحًا من المعلومات.
- الملخص من 3 إلى 5 جمل.
- العنوان مختصر وواضح.
- أعد JSON صالحًا فقط.
- لا تستخدم Markdown.
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


            # ----------------------------------------------------
            # Rate limit
            # ----------------------------------------------------

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


            # ----------------------------------------------------
            # أي خطأ API
            # ----------------------------------------------------

            if response.status_code != 200:

                print(
                    "Gemini API ERROR:"
                )

                print(
                    response.text[:1500]
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

                return None


            result = extract_json_object(
                text
            )


            if not isinstance(
                result,
                dict
            ):

                print(
                    "Invalid Gemini JSON."
                )

                return None


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

                print(
                    "Missing Arabic title."
                )

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
                str(error)[:500]
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
#
# المرحلة الأولى:
# أحدث 3 أخبار فعلية من كل قسم.
#
# المرحلة الثانية:
# الأخبار الإضافية الأحدث حتى 30.
# ============================================================

def select_news(
    articles
):

    selected = []

    selected_keys = set()


    # --------------------------------------------------------
    # أولاً: أحدث 3 لكل قسم
    # --------------------------------------------------------

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
                f"{format_age(article.get('_published_timestamp', 0))} | "
                f"{article.get('title', '')}"
            )


            if count >= MIN_PER_CATEGORY:
                break


    # --------------------------------------------------------
    # الأخبار الإضافية
    # --------------------------------------------------------

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
#
# الصور فقط بعد اختيار الأخبار.
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
        "Gemini:",
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
        "Fresh window:",
        FRESH_HOURS,
        "hours"
    )

    print(
        "Maximum age:",
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
        "=========================================="
    )

    print(
        "TOTAL FRESH COLLECTED:",
        len(articles)
    )

    print(
        "=========================================="
    )


    # ========================================================
    # 2. AVAILABLE BY CATEGORY
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


    # ========================================================
    # 4. SELECTION REPORT
    # ========================================================

    print("")
    print(
        "SELECTED BY CATEGORY:"
    )


    for category in MAIN_CATEGORIES:

        category_items = [

            item

            for item in selected

            if item.get(
                "category"
            ) == category

        ]


        print(
            f"  {category}: "
            f"{len(category_items)}/{MIN_PER_CATEGORY}"
        )


        for item in category_items:

            print(
                "     -",
                format_age(
                    item.get(
                        "_published_timestamp",
                        0
                    )
                ),
                "|",
                item.get(
                    "title",
                    ""
                )[:120]
            )


    # ========================================================
    # 5. FETCH IMAGES
    # ========================================================

    selected = complete_images(
        selected
    )


    # ========================================================
    # 6. GENERATE ARABIC
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
            "Age:",
            format_age(
                article.get(
                    "_published_timestamp",
                    0
                )
            )
        )

        print(
            "Title:",
            article["title"]
        )

        print(
            "Published:",
            article.get(
                "published",
                ""
            )
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


        # ----------------------------------------------------
        # مهم جدًا:
        # إذا فشل Gemini لهذا الخبر،
        # لا نفشل الـ workflow كله.
        # فقط نتخطى الخبر.
        # ----------------------------------------------------

        if not ai:

            print(
                "SKIPPED — Gemini failed"
            )

            continue


        # ----------------------------------------------------
        # نحتفظ بتاريخ النشر الحقيقي
        # وليس وقت تشغيل GitHub.
        # ----------------------------------------------------

        published_at = article.get(
            "_published_timestamp",
            0
        )


        if published_at:

            published_iso = (

                datetime.fromtimestamp(
                    published_at,
                    tz=timezone.utc
                ).isoformat()

            )

        else:

            published_iso = ""


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

            "published":
                article.get(
                    "published",
                    ""
                ),

            "publishedAt":
                published_iso

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
    # 7. FINAL CATEGORY CHECK
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
    # مهم:
    #
    # إذا Gemini فشل في بعض الأخبار،
    # لا نستبدل news.json القديم بملف ناقص.
    #
    # لكننا لا نرمي RuntimeError مباشرة.
    # ========================================================

    if missing_categories:

        print("")
        print(
            "WARNING — NOT ENOUGH VALID NEWS"
        )


        for category in missing_categories:

            print(
                f" - {category}: "
                f"{category_counts.get(category, 0)}/"
                f"{MIN_PER_CATEGORY}"
            )


        # إذا لدينا عدد قليل جدًا من الأخبار،
        # لا نكتب ملفًا ناقصًا.
        if len(final_news) < 10:

            print("")
            print(
                "Too few valid articles."
            )

            print(
                "Existing news.json was NOT modified."
            )

            raise RuntimeError(
                "Not enough fresh valid articles."
            )


        # إذا لدينا عدد معقول،
        # نسمح بالحفظ حتى لو قسم واحد ناقص.
        print("")
        print(
            "Enough fresh articles available."
        )

        print(
            "Continuing without forcing "
            "3 articles in every category."
        )


    # ========================================================
    # 8. SORT FINAL NEWS
    # ========================================================

    final_news.sort(

        key=lambda item:
            item.get(
                "publishedAt",
                ""
            ),

        reverse=True

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
    # 12. FINAL REPORT
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


    print("")
    print(
        "FINAL CATEGORY COUNTS:"
    )


    for category in MAIN_CATEGORIES:

        print(
            f"  {category}: "
            f"{category_counts.get(category, 0)}"
        )


    print("")
    print(
        "FINAL NEWS AGES:"
    )


    for item in final_news[:30]:

        print(
            " -",
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
            )[:100]
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
