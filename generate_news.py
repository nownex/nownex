import os
import json
import re
import html
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
import feedparser


# ============================================================
# NOWNEX — BILINGUAL NEWS ENGINE
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing from GitHub Secrets.")


GEMINI_MODEL = "gemini-3.6-flash"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{GEMINI_MODEL}:generateContent"
)


# ============================================================
# SETTINGS
# ============================================================

MAX_NEWS = 24

# الموقع يحتاج 3 أخبار على الأقل لكل قسم
MIN_PER_CATEGORY = 3

# نأخذ عدة مرشحين لكل قسم حتى يكون لدينا بدائل
CANDIDATES_PER_CATEGORY = 5

REQUEST_TIMEOUT = 25
GEMINI_TIMEOUT = 90

# وقت قصير بين طلبات Gemini
REQUEST_DELAY = 2

# عدد المحاولات لكل خبر
GEMINI_RETRIES = 3


MAIN_CATEGORIES = [
    "AI",
    "Technology",
    "Cars",
    "Entertainment",
    "World",
    "Facts",
    "Products",
]


VALID_CATEGORIES = set(MAIN_CATEGORIES)


# ============================================================
# NEWS SOURCES
# ============================================================

RSS_FEEDS = [

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
        "MIT Technology Review",
        "https://www.technologyreview.com/feed/",
        "Technology"
    ),


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
        "https://news.google.com/rss/search?q=artificial%20intelligence&hl=en&gl=US&ceid=US:en",
        "AI"
    ),

    (
        "Google News AI Arabic",
        "https://news.google.com/rss/search?q=%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1%20%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A&hl=ar&gl=DZ&ceid=DZ:ar",
        "AI"
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
        "https://news.google.com/rss/search?q=cars%20automotive&hl=en&gl=US&ceid=US:en",
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
        "https://news.google.com/rss/search?q=entertainment%20movies%20music&hl=en&gl=US&ceid=US:en",
        "Entertainment"
    ),

    (
        "Google News Entertainment Arabic",
        "https://news.google.com/rss/search?q=%D8%AA%D8%B1%D9%81%D9%8A%D9%87%20%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D9%85%D9%88%D8%B3%D9%8A%D9%82%D9%89&hl=ar&gl=DZ&ceid=DZ:ar",
        "Entertainment"
    ),


    # ========================================================
    # WORLD
    # ========================================================

    (
        "BBC عربي",
        "https://feeds.bbci.co.uk/arabic/rss.xml",
        "World"
    ),

    (
        "الجزيرة",
        "https://www.aljazeera.net/aljazeera.rss",
        "World"
    ),

    (
        "Google News World",
        "https://news.google.com/rss?hl=ar&gl=DZ&ceid=DZ:ar",
        "World"
    ),

    (
        "Reuters World",
        "https://feeds.reuters.com/reuters/worldNews",
        "World"
    ),


    # ========================================================
    # FACTS
    # ========================================================

    (
        "Google News Science Facts",
        "https://news.google.com/rss/search?q=science%20facts%20discovery&hl=en&gl=US&ceid=US:en",
        "Facts"
    ),

    (
        "Google News Facts Arabic",
        "https://news.google.com/rss/search?q=%D8%AD%D9%82%D8%A7%D8%A6%D9%82%20%D8%B9%D9%84%D9%85%20%D8%A7%D9%83%D8%AA%D8%B4%D8%A7%D9%81%D8%A7%D8%AA&hl=ar&gl=DZ&ceid=DZ:ar",
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
        "Google News Products",
        "https://news.google.com/rss/search?q=best%20new%20products%20gadgets&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Gadgets",
        "https://news.google.com/rss/search?q=new%20gadgets%20smartphones%20devices&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Products Arabic",
        "https://news.google.com/rss/search?q=%D9%85%D9%86%D8%AA%D8%AC%D8%A7%D8%AA%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9%20%D9%87%D9%88%D8%A7%D8%AA%D9%81&hl=ar&gl=DZ&ceid=DZ:ar",
        "Products"
    ),
]


# ============================================================
# HTTP SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "NOWNEX/1.0 NewsBot",
    "Accept": "application/rss+xml, application/xml, text/xml, text/html",
})


# ============================================================
# TEXT CLEANING
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


def normalize_title(title):

    title = clean_text(title).lower()

    return re.sub(
        r"[^\w\u0600-\u06FF]+",
        "",
        title
    )


# ============================================================
# DUPLICATES
# ============================================================

def remove_duplicates(items):

    result = []

    seen = set()

    for item in items:

        key = normalize_title(
            item.get("title", "")
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)

        result.append(item)

    return result


# ============================================================
# LANGUAGE ANALYSIS
# ============================================================

def count_arabic(text):

    return len(
        re.findall(
            r"[\u0600-\u06FF]",
            clean_text(text)
        )
    )


def count_english(text):

    return len(
        re.findall(
            r"[A-Za-z]",
            clean_text(text)
        )
    )


def count_letters(text):

    return len(
        re.findall(
            r"[A-Za-z\u0600-\u06FF]",
            clean_text(text)
        )
    )


def arabic_ratio(text):

    total = count_letters(text)

    if total == 0:
        return 0

    return count_arabic(text) / total


def english_ratio(text):

    total = count_letters(text)

    if total == 0:
        return 0

    return count_english(text) / total


def has_arabic(text):

    return count_arabic(text) >= 3


def has_english(text):

    return count_english(text) >= 3


# ============================================================
# STRICT LANGUAGE VALIDATION
# ============================================================

def is_arabic_text(text):

    text = clean_text(text)

    if len(text) < 8:
        return False

    if not has_arabic(text):
        return False

    # العربية يجب أن تكون هي اللغة الغالبة بوضوح
    if arabic_ratio(text) < 0.65:
        return False

    # لا نسمح بكمية كبيرة من الإنجليزية
    if english_ratio(text) > 0.25:
        return False

    return True


def is_english_text(text):

    text = clean_text(text)

    if len(text) < 8:
        return False

    if not has_english(text):
        return False

    # الإنجليزية يجب أن تكون هي اللغة الغالبة بوضوح
    if english_ratio(text) < 0.70:
        return False

    # العربية لا يجب أن تكون موجودة بكثرة
    if arabic_ratio(text) > 0.12:
        return False

    return True


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def extract_rss_image(entry):

    for media in entry.get(
        "media_content",
        []
    ):

        url = (
            media.get("url")
            or media.get("href")
        )

        if url:
            return str(url).strip()


    for media in entry.get(
        "media_thumbnail",
        []
    ):

        url = (
            media.get("url")
            or media.get("href")
        )

        if url:
            return str(url).strip()


    for enclosure in entry.get(
        "enclosures",
        []
    ):

        url = (
            enclosure.get("href")
            or enclosure.get("url")
        )

        if url:
            return str(url).strip()


    for source in [
        entry.get("summary", ""),
        entry.get("description", "")
    ]:

        match = re.search(
            r'<img[^>]+src=["\']([^"\']+)["\']',
            str(source),
            re.IGNORECASE
        )

        if match:

            return html.unescape(
                match.group(1).strip()
            )


    return ""


# ============================================================
# HIGH QUALITY OG IMAGE
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

        page = response.text[:800000]

        patterns = [

            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                page,
                re.IGNORECASE
            )

            if match:

                image = html.unescape(
                    match.group(1).strip()
                )

                image = urljoin(
                    response.url,
                    image
                )

                if image.startswith(
                    ("http://", "https://")
                ):

                    return image

    except Exception as error:

        print(
            "Image error:",
            error
        )

    return ""


def get_best_image(entry, link):

    image = extract_rss_image(entry)

    if image:
        return image

    return get_og_image(link)


# ============================================================
# RSS COLLECTION
# ============================================================

def get_news():

    articles = []

    for source_name, feed_url, category in RSS_FEEDS:

        print(
            "\nReading:",
            source_name
        )

        try:

            feed = feedparser.parse(
                feed_url
            )

            entries = feed.entries[:20]

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

                    if content:

                        try:

                            description = clean_text(
                                content[0].get(
                                    "value",
                                    ""
                                )
                            )

                        except Exception:
                            pass


                link = str(
                    entry.get(
                        "link",
                        ""
                    )
                ).strip()


                if not link:
                    continue


                image = get_best_image(
                    entry,
                    link
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

                    "title": title,

                    "description": description,

                    "link": link,

                    "source": source_name,

                    "category": category,

                    "image": image,

                    "published": published,

                })


        except Exception as error:

            print(
                "RSS error:",
                source_name,
                error
            )


    return remove_duplicates(
        articles
    )


# ============================================================
# SUMMARY QUALITY
# ============================================================

def summary_is_valid(
    title,
    summary
):

    title = clean_text(title)
    summary = clean_text(summary)

    if not title or not summary:
        return False

    if len(summary) < 100:
        return False

    if summary.lower() == title.lower():
        return False

    sentences = re.findall(
        r"[.!?؟。]",
        summary
    )

    if len(sentences) < 2:
        return False

    return True


# ============================================================
# FINAL ARTICLE LANGUAGE VALIDATION
# ============================================================

def generated_article_is_valid(
    title_ar,
    summary_ar,
    title_en,
    summary_en
):

    # --------------------------------------------------------
    # Arabic
    # --------------------------------------------------------

    if not is_arabic_text(title_ar):

        print(
            "INVALID Arabic title:",
            title_ar
        )

        return False


    if not is_arabic_text(summary_ar):

        print(
            "INVALID Arabic summary"
        )

        return False


    if not summary_is_valid(
        title_ar,
        summary_ar
    ):

        print(
            "INVALID Arabic summary quality"
        )

        return False


    # --------------------------------------------------------
    # English
    # --------------------------------------------------------

    if not is_english_text(title_en):

        print(
            "INVALID English title:",
            title_en
        )

        return False


    if not is_english_text(summary_en):

        print(
            "INVALID English summary"
        )

        return False


    if not summary_is_valid(
        title_en,
        summary_en
    ):

        print(
            "INVALID English summary quality"
        )

        return False


    # --------------------------------------------------------
    # Explicit opposite-language protection
    # --------------------------------------------------------

    if arabic_ratio(title_en) > 0.12:

        print(
            "English text contains too much Arabic."
        )

        return False


    if english_ratio(title_ar) > 0.25:

        print(
            "Arabic title contains too much English."
        )

        return False


    if arabic_ratio(summary_en) > 0.12:

        print(
            "English summary contains too much Arabic."
        )

        return False


    if english_ratio(summary_ar) > 0.25:

        print(
            "Arabic summary contains too much English."
        )

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
            "اعتمد فقط على العنوان والمعلومات المتاحة."
        )


    prompt = f"""
You are the senior bilingual news editor for NOWNEX.

Create ONE professional news article in TWO languages.

SOURCE:
{source}

CATEGORY:
{category}

ORIGINAL HEADLINE:
{title}

AVAILABLE INFORMATION:
{description}


============================================================
OUTPUT
============================================================

Return exactly these four JSON fields:

title_ar
summary_ar
title_en
summary_en


============================================================
ARABIC — VERY STRICT
============================================================

title_ar MUST be written primarily in Modern Standard Arabic.

summary_ar MUST be written primarily in Modern Standard Arabic.

Do NOT copy the English headline.

Do NOT copy English sentences.

Translate and professionally rewrite the information.

Arabic text must contain at least 70% Arabic-script letters.

Do not put English sentences inside Arabic text.

English is allowed ONLY when naturally necessary for:
- company names
- product names
- person names
- official organization names
- technical names that are normally written in Latin characters

Do not write an Arabic sentence and then continue it in English.

Do not use English as the main language of the Arabic version.


============================================================
ENGLISH — VERY STRICT
============================================================

title_en MUST be written in natural professional English.

summary_en MUST be written in natural professional English.

Do NOT copy Arabic sentences.

Do NOT place Arabic sentences inside the English version.

English text must contain at least 70% Latin letters.

Arabic is allowed ONLY when absolutely necessary for a proper name.

Do not use Arabic as the main language of the English version.


============================================================
CONTENT RULES
============================================================

Both languages must describe exactly the same news story.

Do not invent facts.

Do not invent numbers.

Do not invent names.

Do not invent quotes.

Do not add opinions.

Use only the information available in the source.

The Arabic and English versions may be independently rewritten,
but they must remain factually equivalent.

Arabic summary: 3 to 5 sentences.

English summary: 3 to 5 sentences.

No Markdown.

No bullet points.

No emojis.


============================================================
IMPORTANT
============================================================

If the original source is English:

You MUST translate the information into Arabic for title_ar
and summary_ar.

If the original source is Arabic:

You MUST translate the information into English for title_en
and summary_en.

NEVER return the original language in the wrong field.


============================================================
JSON ONLY
============================================================

{{
  "title_ar": "عنوان عربي احترافي",
  "summary_ar": "ملخص عربي من ثلاث إلى خمس جمل.",
  "title_en": "Professional English headline",
  "summary_en": "Professional English summary of three to five sentences."
}}
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

            "temperature": 0.15,

            "responseMimeType": "application/json"

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
                f"Gemini request {attempt}/{GEMINI_RETRIES}"
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


            # ------------------------------------------------
            # RATE LIMIT
            # ------------------------------------------------

            if response.status_code == 429:

                wait_time = (
                    30
                    if attempt == 1
                    else 60
                    if attempt == 2
                    else 90
                )

                print(
                    f"Rate limit. Waiting {wait_time}s..."
                )

                time.sleep(
                    wait_time
                )

                continue


            # ------------------------------------------------
            # HTTP ERROR
            # ------------------------------------------------

            if response.status_code != 200:

                print(
                    response.text[:1500]
                )

                if attempt < GEMINI_RETRIES:

                    time.sleep(
                        15
                    )

                    continue

                return None


            # ------------------------------------------------
            # JSON RESPONSE
            # ------------------------------------------------

            data = response.json()

            text = (
                data["candidates"][0]
                ["content"]["parts"][0]
                ["text"]
                .strip()
            )


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


            title_en = clean_text(
                result.get(
                    "title_en",
                    ""
                )
            )


            summary_en = clean_text(
                result.get(
                    "summary_en",
                    ""
                )
            )


            print(
                "AR:",
                title_ar
            )

            print(
                "EN:",
                title_en
            )


            # ------------------------------------------------
            # STRICT VALIDATION
            # ------------------------------------------------

            if not generated_article_is_valid(

                title_ar,

                summary_ar,

                title_en,

                summary_en

            ):

                print(
                    "Language validation FAILED."
                )

                if attempt < GEMINI_RETRIES:

                    print(
                        "Retrying with strict language rules..."
                    )

                    time.sleep(
                        4
                    )

                    continue

                return None


            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            return {

                "title_ar":
                    title_ar,

                "summary_ar":
                    summary_ar,

                "title_en":
                    title_en,

                "summary_en":
                    summary_en

            }


        except Exception as error:

            print(
                "Gemini error:",
                error
            )

            if attempt < GEMINI_RETRIES:

                time.sleep(
                    10
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
# LOAD OLD NEWS
# ============================================================

def load_existing_news():

    try:

        if not os.path.exists(
            "news.json"
        ):

            return []


        with open(
            "news.json",
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(
                file
            )


        news = data.get(
            "news",
            []
        )


        if not isinstance(
            news,
            list
        ):

            return []


        print(
            f"Existing news loaded: {len(news)}"
        )


        return news


    except Exception as error:

        print(
            "Could not load existing news:",
            error
        )

        return []


# ============================================================
# VALIDATE OLD NEWS
# ============================================================

def valid_existing_article(item):

    try:

        category = item.get(
            "category"
        )

        if category not in VALID_CATEGORIES:
            return False


        return generated_article_is_valid(

            item.get(
                "title_ar",
                ""
            ),

            item.get(
                "summary_ar",
                ""
            ),

            item.get(
                "title_en",
                ""
            ),

            item.get(
                "summary_en",
                ""
            )

        )

    except Exception:

        return False


# ============================================================
# SELECT CANDIDATES
# ============================================================

def build_candidates(
    articles
):

    candidates = {}

    for category in MAIN_CATEGORIES:

        candidates[category] = []

        category_articles = get_category_articles(
            articles,
            category
        )


        for article in category_articles:

            if len(
                candidates[category]
            ) >= CANDIDATES_PER_CATEGORY:

                break


            candidates[category].append(
                article
            )


    return candidates


# ============================================================
# BUILD NEWS ITEM
# ============================================================

def build_news_item(
    article,
    ai
):

    return {

        "title_ar":
            ai["title_ar"],

        "summary_ar":
            ai["summary_ar"],

        "title_en":
            ai["title_en"],

        "summary_en":
            ai["summary_en"],


        # Backward compatibility
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
            datetime.now(
                timezone.utc
            ).isoformat()

    }


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n======================================"
    )

    print(
        " NOWNEX BILINGUAL NEWS ENGINE"
    )

    print(
        "======================================\n"
    )


    existing_news = load_existing_news()


    # ========================================================
    # RSS
    # ========================================================

    articles = get_news()


    if not articles:

        print(
            "RSS returned no articles."
        )

        print(
            "Keeping existing news.json."
        )

        return


    print(
        f"\nCollected RSS articles: {len(articles)}"
    )


    # ========================================================
    # AVAILABLE RSS BY CATEGORY
    # ========================================================

    print(
        "\nRSS availability:"
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
    # CANDIDATES
    # ========================================================

    candidates = build_candidates(
        articles
    )


    # ========================================================
    # GENERATE BY CATEGORY
    # ========================================================

    generated_by_category = {

        category: []

        for category in MAIN_CATEGORIES

    }


    for category in MAIN_CATEGORIES:

        print(
            "\n======================================"
        )

        print(
            f" CATEGORY: {category}"
        )

        print(
            "======================================"
        )


        category_candidates = candidates.get(
            category,
            []
        )


        if not category_candidates:

            print(
                "No RSS candidates."
            )

            continue


        for article in category_candidates:

            if len(
                generated_by_category[category]
            ) >= MIN_PER_CATEGORY:

                break


            print(
                "\nTrying:"
            )

            print(
                article["title"]
            )


            ai = ask_gemini(

                article["title"],

                article["description"],

                article["source"],

                category

            )


            if not ai:

                print(
                    "✗ Rejected."
                )

                continue


            item = build_news_item(
                article,
                ai
            )


            generated_by_category[
                category
            ].append(
                item
            )


            print(
                "✓ Valid bilingual article."
            )


            time.sleep(
                REQUEST_DELAY
            )


        print(
            f"{category}: "
            f"{len(generated_by_category[category])} "
            f"new articles"
        )


    # ========================================================
    # VALID OLD NEWS FOR FALLBACK
    # ========================================================

    old_by_category = {

        category: []

        for category in MAIN_CATEGORIES

    }


    for item in existing_news:

        if not valid_existing_article(
            item
        ):

            continue


        category = item.get(
            "category"
        )


        if category in VALID_CATEGORIES:

            old_by_category[
                category
            ].append(
                item
            )


    # ========================================================
    # FINAL ASSEMBLY
    # ========================================================

    final_news = []

    used_titles = set()


    for category in MAIN_CATEGORIES:

        print(
            "\nFinalizing:",
            category
        )


        category_items = []


        # ----------------------------------------------------
        # New articles first
        # ----------------------------------------------------

        for item in generated_by_category.get(
            category,
            []
        ):

            key = normalize_title(
                item.get(
                    "title_ar",
                    ""
                )
            )


            if key in used_titles:
                continue


            used_titles.add(
                key
            )

            category_items.append(
                item
            )


            if len(category_items) >= MIN_PER_CATEGORY:
                break


        # ----------------------------------------------------
        # Old valid articles as fallback
        # ----------------------------------------------------

        if len(category_items) < MIN_PER_CATEGORY:

            print(
                f"{category}: "
                f"new articles insufficient. "
                f"Using valid previous articles."
            )


            for item in old_by_category.get(
                category,
                []
            ):

                key = normalize_title(
                    item.get(
                        "title_ar",
                        item.get(
                            "title",
                            ""
                        )
                    )
                )


                if key in used_titles:
                    continue


                used_titles.add(
                    key
                )

                category_items.append(
                    item
                )


                if len(category_items) >= MIN_PER_CATEGORY:

                    break


        print(
            f"{category}: "
            f"{len(category_items)} final articles"
        )


        final_news.extend(
            category_items
        )


    # ========================================================
    # FILL TO 24
    # ========================================================

    if len(final_news) < MAX_NEWS:

        print(
            "\nFilling remaining slots..."
        )


        all_new = []

        for category in MAIN_CATEGORIES:

            all_new.extend(
                generated_by_category.get(
                    category,
                    []
                )
            )


        all_old = []

        for category in MAIN_CATEGORIES:

            all_old.extend(
                old_by_category.get(
                    category,
                    []
                )
            )


        for item in all_new + all_old:

            if len(final_news) >= MAX_NEWS:

                break


            key = normalize_title(
                item.get(
                    "title_ar",
                    item.get(
                        "title",
                        ""
                    )
                )
            )


            if key in used_titles:

                continue


            used_titles.add(
                key
            )

            final_news.append(
                item
            )


    # ========================================================
    # FINAL SAFETY
    # ========================================================

    final_news = final_news[
        :MAX_NEWS
    ]


    # ========================================================
    # DO NOT DESTROY A GOOD DATABASE
    # ========================================================

    if not final_news:

        print(
            "\nNO VALID NEWS."
        )

        print(
            "Existing news.json will remain unchanged."
        )

        return


    # ========================================================
    # CHECK CATEGORIES
    # ========================================================

    print(
        "\n======================================"
    )

    print(
        " FINAL NEWS REPORT"
    )

    print(
        "======================================"
    )


    missing_categories = []


    for category in MAIN_CATEGORIES:

        count = len(
            get_category_articles(
                final_news,
                category
            )
        )


        print(
            f"{category}: {count}"
        )


        if count < MIN_PER_CATEGORY:

            missing_categories.append(
                category
            )


    # ========================================================
    # IMPORTANT SAFETY
    # ========================================================

    if missing_categories:

        print(
            "\nWARNING:"
        )

        print(
            "Some categories have fewer than "
            f"{MIN_PER_CATEGORY} articles:"
        )

        print(
            missing_categories
        )


        # إذا كانت لدينا أخبار قديمة، لا نستبدل
        # قاعدة البيانات بقاعدة ناقصة.
        if existing_news:

            print(
                "Keeping previous news.json "
                "because the new dataset is incomplete."
            )

            return


    # ========================================================
    # SAVE
    # ========================================================

    output = {

        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "count":
            len(final_news),

        "news":
            final_news

    }


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
    # DONE
    # ========================================================

    print(
        "\n======================================"
    )

    print(
        " NOWNEX NEWS UPDATED SUCCESSFULLY"
    )

    print(
        "======================================"
    )


    print(
        "Total:",
        len(final_news)
    )


    print(
        "\nCategories:"
    )


    for category in MAIN_CATEGORIES:

        count = len(
            get_category_articles(
                final_news,
                category
            )
        )

        print(
            f"  {category}: {count}"
        )


    print(
        "\nTrending = all generated articles."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
