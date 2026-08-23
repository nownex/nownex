import os
import json
import re
import html
import time
import calendar
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
import feedparser


# ============================================================
# NOWNEX NEWS ENGINE v5
#
# FAST RSS
# FRESH NEWS
# ARABIC FIRST
# GEMINI CATEGORY BATCHING
#
# IMPORTANT:
# Instead of sending 30 Gemini requests,
# we send approximately 7 requests:
# one request per category.
# ============================================================


# ============================================================
# GEMINI API
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


# You can override this from GitHub Variables/Secrets.
#
# Recommended:
# gemini-2.5-flash-lite
#
# If your project already uses another model,
# GEMINI_MODEL can override this value.
#
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-2.5-flash-lite"
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

CANDIDATES_PER_CATEGORY = 8

ENTRIES_PER_FEED = 20

REQUEST_TIMEOUT = 15

GEMINI_TIMEOUT = 90

GEMINI_RETRIES = 3

GEMINI_RETRY_WAIT = 30

REQUEST_DELAY = 2

# Only accept news published within this period.
#
# 24 hours gives enough flexibility if a source updates
# slowly, while preventing very old articles.
#
MAX_AGE_HOURS = 24


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
        "q=artificial%20intelligence%20AI"
        "&hl=en&gl=US&ceid=US:en",
        "AI"
    ),

    (
        "Google News AI Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1%20%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A"
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
        "q=technology%20smartphones%20gadgets"
        "&hl=en&gl=US&ceid=US:en",
        "Technology"
    ),

    (
        "Google News Technology Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%AA%D9%83%D9%86%D9%88%D9%84%D9%88%D8%AC%D9%8A%D8%A7%20%D9%87%D9%88%D8%A7%D8%AA%D9%81%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9"
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
        "q=cars%20automotive%20electric%20vehicles"
        "&hl=en&gl=US&ceid=US:en",
        "Cars"
    ),

    (
        "Google News Cars Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%B3%D9%8A%D8%A7%D8%B1%D8%A7%D8%AA%20%D8%B3%D9%8A%D8%A7%D8%B1%D8%A7%D8%AA%20%D9%83%D9%87%D8%B1%D8%A8%D8%A7%D8%A6%D9%8A%D8%A9"
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
        "q=entertainment%20movies%20music%20games"
        "&hl=en&gl=US&ceid=US:en",
        "Entertainment"
    ),

    (
        "Google News Entertainment Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%AA%D8%B1%D9%81%D9%8A%D9%87%20%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D9%85%D9%88%D8%B3%D9%8A%D9%82%D9%89%20%D8%A3%D9%84%D8%B9%D8%A7%D8%A8"
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
        "https://news.google.com/rss?"
        "hl=ar&gl=DZ&ceid=DZ:ar",
        "World"
    ),

    (
        "Google News World",
        "https://news.google.com/rss/search?"
        "q=world%20news"
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
        "q=science%20discovery%20space"
        "&hl=en&gl=US&ceid=US:en",
        "Facts"
    ),

    (
        "Google News Science Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%B9%D9%84%D9%85%20%D8%A7%D9%83%D8%AA%D8%B4%D8%A7%D9%81%D8%A7%D8%AA%20%D9%81%D8%B6%D8%A7%D8%A1"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
        "Facts"
    ),


    # ========================================================
    # PRODUCTS
    # ========================================================

    (
        "Google News Products",
        "https://news.google.com/rss/search?"
        "q=new%20products%20gadgets"
        "&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Gadgets",
        "https://news.google.com/rss/search?"
        "q=new%20gadgets%20smartphones%20devices"
        "&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Products Arabic",
        "https://news.google.com/rss/search?"
        "q=%D9%85%D9%86%D8%AA%D8%AC%D8%A7%D8%AA%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9%20%D9%87%D9%88%D8%A7%D8%AA%D9%81"
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
# EXTRACT RSS IMAGE
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
# RSS parsed dates are normally UTC.
# calendar.timegm() prevents local timezone mistakes.
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
# ARTICLE AGE
# ============================================================

def article_age_hours(article):

    timestamp = article.get(
        "_published_timestamp",
        0
    )


    if not timestamp:

        # If RSS has no date,
        # keep the article but place it later.
        return 999999


    now = time.time()

    age_seconds = max(
        0,
        now - timestamp
    )


    return age_seconds / 3600


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


                published_timestamp = (
                    get_published_timestamp(
                        entry
                    )
                )


                article = {

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
                        published_timestamp

                }


                age = article_age_hours(
                    article
                )


                if age > MAX_AGE_HOURS:

                    print(
                        "OLD — skipped:",
                        round(age, 1),
                        "hours"
                    )

                    continue


                articles.append(
                    article
                )


        except Exception as error:

            print(
                "RSS ERROR:",
                source_name,
                str(error)[:250]
            )


    articles = remove_duplicates(
        articles
    )


    # ========================================================
    # NEWEST FIRST
    # ========================================================

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
# CATEGORY ARTICLES
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
# PREPARE CANDIDATES
#
# We only send a small number of latest articles
# from each category to Gemini.
# ============================================================

def prepare_category_candidates(
    articles,
    category
):

    candidates = get_category_articles(
        articles,
        category
    )


    candidates.sort(

        key=lambda item:
            item.get(
                "_published_timestamp",
                0
            ),

        reverse=True

    )


    return candidates[
        :CANDIDATES_PER_CATEGORY
    ]


# ============================================================
# GEMINI CATEGORY PROMPT
# ============================================================

def build_category_prompt(
    category,
    candidates
):

    news_blocks = []


    for index, article in enumerate(
        candidates,
        start=1
    ):

        block = f"""
NEWS {index}

Source:
{article.get("source", "")}

Original title:
{article.get("title", "")}

Published:
{article.get("published", "")}

Description:
{article.get("description", "")}

Link:
{article.get("link", "")}
"""


        news_blocks.append(
            block
        )


    joined_news = "\n".join(
        news_blocks
    )


    prompt = f"""
أنت محرر الأخبار الرئيسي في NOWNEX.

القسم:
{category}

لديك مجموعة من الأخبار الحقيقية التي تم جلبها
من RSS خلال آخر 24 ساعة.

اختر أفضل 3 أخبار فقط من القائمة.

إذا كانت القائمة تحتوي على أقل من 3 أخبار،
أعد الأخبار الموجودة فقط.

ممنوع اختراع أخبار جديدة.

ممنوع استخدام معلومات من خارج البيانات المقدمة.

لكل خبر اخترته، أنشئ:
- عنواناً عربياً احترافياً
- ملخصاً عربياً من 3 إلى 5 جمل

المعلومات:

{joined_news}

أعد JSON فقط بهذا الشكل:

{{
  "articles": [
    {{
      "source_index": 1,
      "title_ar": "العنوان العربي",
      "summary_ar": "الملخص العربي."
    }}
  ]
}}

القواعد:

1. العربية الفصحى الحديثة.
2. لا تخترع أي معلومة.
3. لا تخترع أسماء.
4. لا تخترع أرقاماً.
5. لا تخترع تصريحات.
6. لا تضف رأياً.
7. لا تكرر نفس الخبر.
8. اختر الأخبار الأحدث والأكثر أهمية.
9. لا تستخدم Markdown.
10. JSON صالح فقط.
11. لا تعِد أكثر من 3 أخبار.
"""


    return prompt


# ============================================================
# VALID SUMMARY
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


    if not title:
        return False


    if not summary:
        return False


    if len(summary) < 80:
        return False


    if summary.lower() == title.lower():
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
# PARSE GEMINI JSON
# ============================================================

def parse_gemini_json(text):

    if not text:
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


    try:

        return json.loads(
            text
        )

    except Exception:

        # Try to extract the JSON object
        # if Gemini added extra text.

        match = re.search(
            r"\{.*\}",
            text,
            re.DOTALL
        )


        if not match:
            return None


        try:

            return json.loads(
                match.group(0)
            )

        except Exception:

            return None


# ============================================================
# GEMINI CATEGORY REQUEST
#
# ONE REQUEST FOR A WHOLE CATEGORY.
# ============================================================

def ask_gemini_category(
    category,
    candidates
):

    if not candidates:

        print(
            "No candidates for:",
            category
        )

        return []


    prompt = build_category_prompt(
        category,
        candidates
    )


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
        GEMINI_RETRIES + 1
    ):

        try:

            print(
                f"Gemini {category} "
                f"request {attempt}/{GEMINI_RETRIES}"
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

                if attempt >= GEMINI_RETRIES:

                    print(
                        "RATE LIMIT — "
                        "category failed."
                    )

                    return []


                wait_time = (
                    GEMINI_RETRY_WAIT
                    * attempt
                )


                print(
                    "Rate limit."
                )

                print(
                    "Waiting:",
                    wait_time,
                    "seconds"
                )


                time.sleep(
                    wait_time
                )


                continue


            # =================================================
            # OTHER API ERROR
            # =================================================

            if response.status_code != 200:

                print(
                    "Gemini API ERROR:",
                    response.text[:1000]
                )

                return []


            data = response.json()


            candidates_response = data.get(
                "candidates",
                []
            )


            if not candidates_response:

                print(
                    "Gemini returned no candidates."
                )

                return []


            text = (

                candidates_response[0]
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

                return []


            result = parse_gemini_json(
                text
            )


            if not isinstance(
                result,
                dict
            ):

                print(
                    "Invalid Gemini JSON."
                )

                return []


            generated = result.get(
                "articles",
                []
            )


            if not isinstance(
                generated,
                list
            ):

                return []


            final = []


            used_indexes = set()


            for item in generated:

                if not isinstance(
                    item,
                    dict
                ):
                    continue


                source_index = item.get(
                    "source_index"
                )


                try:

                    source_index = int(
                        source_index
                    )

                except Exception:

                    continue


                if source_index < 1:
                    continue


                if source_index > len(
                    candidates
                ):
                    continue


                if source_index in used_indexes:
                    continue


                original = candidates[
                    source_index - 1
                ]


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


                if not summary_is_valid(

                    title_ar,
                    summary_ar

                ):

                    print(
                        "Invalid generated article."
                    )

                    continue


                used_indexes.add(
                    source_index
                )


                final.append({

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
                        category,

                    "source":
                        original.get(
                            "source",
                            ""
                        ),

                    "link":
                        original.get(
                            "link",
                            ""
                        ),

                    "image":
                        original.get(
                            "image",
                            ""
                        ),

                    "published":
                        original.get(
                            "published",
                            ""
                        ),

                    "_published_timestamp":
                        original.get(
                            "_published_timestamp",
                            0
                        )

                })


                if len(final) >= MIN_PER_CATEGORY:

                    break


            print(
                f"Gemini created "
                f"{len(final)} articles for {category}"
            )


            return final


        except Exception as error:

            print(
                "Gemini ERROR:",
                str(error)[:400]
            )


            if attempt < GEMINI_RETRIES:

                time.sleep(
                    GEMINI_RETRY_WAIT
                    * attempt
                )


    return []


# ============================================================
# FETCH IMAGES FOR FINAL NEWS
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
                "RSS image: YES"
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
                "Image: FOUND"
            )

        else:

            print(
                "Image: NONE"
            )


        time.sleep(
            0.2
        )


    return selected


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
# CATEGORY REPORT
# ============================================================

def print_category_report(
    news,
    title
):

    print("")
    print(
        "=========================================="
    )

    print(
        title
    )

    print(
        "=========================================="
    )


    for category in MAIN_CATEGORIES:

        count = len([

            item

            for item in news

            if item.get(
                "category"
            ) == category

        ])


        print(
            f"{category}: {count}"
        )


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
        " FRESH + RSS + ARABIC + LOW GEMINI USAGE"
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
        "Candidates per category:",
        CANDIDATES_PER_CATEGORY
    )

    print(
        "Maximum article age:",
        MAX_AGE_HOURS,
        "hours"
    )

    print("")


    # ========================================================
    # 1. GET RSS NEWS
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


    print_category_report(
        articles,
        "FRESH ARTICLES BY CATEGORY"
    )


    # ========================================================
    # 2. GENERATE CATEGORY BY CATEGORY
    #
    # IMPORTANT:
    # This is the main fix for the 429 problem.
    #
    # 7 categories = approximately 7 Gemini requests.
    # NOT 30 requests.
    # ========================================================

    final_news = []


    for category in MAIN_CATEGORIES:

        print("")
        print(
            "##########################################"
        )

        print(
            f"PROCESSING CATEGORY: {category}"
        )

        print(
            "##########################################"
        )


        category_candidates = (
            prepare_category_candidates(
                articles,
                category
            )
        )


        print(
            "Candidates:",
            len(category_candidates)
        )


        for index, article in enumerate(

            category_candidates,

            start=1

        ):

            age = article_age_hours(
                article
            )


            print(
                f"  {index}. "
                f"{article.get('title', '')}"
            )

            print(
                f"     Age: {age:.1f}h"
            )


        if not category_candidates:

            print(
                "No fresh candidates."
            )

            continue


        generated = ask_gemini_category(

            category,

            category_candidates

        )


        final_news.extend(
            generated
        )


        print(
            f"FINAL {category}: "
            f"{len(generated)}"
        )


        # Small delay between category requests.
        #
        # This is intentional.
        # It reduces the chance of hitting RPM limits.
        #

        time.sleep(
            REQUEST_DELAY
        )


    # ========================================================
    # 3. REMOVE DUPLICATES AGAIN
    # ========================================================

    unique_final = []

    seen_links = set()

    seen_titles = set()


    for article in final_news:

        link_key = str(
            article.get(
                "link",
                ""
            )
        ).strip().lower()


        title_key = normalize_title(

            article.get(
                "title_ar",
                ""
            )

        )


        if (
            link_key
            and
            link_key in seen_links
        ):

            continue


        if (
            title_key
            and
            title_key in seen_titles
        ):

            continue


        if link_key:
            seen_links.add(
                link_key
            )


        if title_key:
            seen_titles.add(
                title_key
            )


        unique_final.append(
            article
        )


    final_news = unique_final


    # ========================================================
    # 4. SORT FINAL NEWS BY REAL PUBLISHED DATE
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
    # 5. KEEP MAX 30
    # ========================================================

    final_news = final_news[
        :MAX_NEWS
    ]


    print_category_report(
        final_news,
        "FINAL CATEGORY CHECK"
    )


    # ========================================================
    # 6. VERIFY MINIMUM
    #
    # We still require 3 per category.
    # This protects news.json from incomplete updates.
    # ========================================================

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


    missing_categories = [

        category

        for category in MAIN_CATEGORIES

        if category_counts.get(
            category,
            0
        ) < MIN_PER_CATEGORY

    ]


    if missing_categories:

        print("")
        print(
            "=========================================="
        )

        print(
            "WARNING — NOT ENOUGH VALID NEWS"
        )

        print(
            "=========================================="
        )


        for category in MAIN_CATEGORIES:

            print(
                f"{category}: "
                f"{category_counts.get(category, 0)}/"
                f"{MIN_PER_CATEGORY}"
            )


        print("")
        print(
            "Existing news.json was NOT modified."
        )


        # IMPORTANT:
        # We do NOT raise RuntimeError here.
        #
        # This allows GitHub Actions to continue
        # and makes the workflow easier to debug.
        #
        # If you want a hard failure later,
        # change this to:
        #
        # raise RuntimeError("Not enough fresh valid articles.")
        #

        return


    # ========================================================
    # 7. FETCH IMAGES
    #
    # Only after Gemini selected the final news.
    # ========================================================

    final_news = complete_images(
        final_news
    )


    # ========================================================
    # 8. TRENDING
    # ========================================================

    trending_news = create_trending(
        final_news
    )


    # ========================================================
    # 9. REMOVE INTERNAL FIELDS
    #
    # _published_timestamp is only used internally.
    # ========================================================

    for item in final_news:

        item.pop(
            "_published_timestamp",
            None
        )


    for item in trending_news:

        item.pop(
            "_published_timestamp",
            None
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
            f"{category_counts[category]}"
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
