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
# NOWNEX NEWS ENGINE
# 7 CATEGORIES × 3 ARTICLES = 21 ARTICLES MINIMUM
# STRICT ARABIC / ENGLISH SEPARATION
# ============================================================


API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


# ============================================================
# GEMINI
# ============================================================

GEMINI_MODEL = "gemini-3.6-flash"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{GEMINI_MODEL}:generateContent"
)


# ============================================================
# SETTINGS
# ============================================================

MIN_PER_CATEGORY = 3

MAX_NEWS = 24

CANDIDATES_PER_CATEGORY = 12

GEMINI_RETRIES = 3

REQUEST_TIMEOUT = 25

GEMINI_TIMEOUT = 90

REQUEST_DELAY = 2


# ============================================================
# MAIN CATEGORIES
# ============================================================

MAIN_CATEGORIES = [

    "AI",

    "Technology",

    "Cars",

    "Entertainment",

    "World",

    "Facts",

    "Products",

]


VALID_CATEGORIES = set(
    MAIN_CATEGORIES
)


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
        "https://news.google.com/rss/search?q=artificial%20intelligence&hl=en&gl=US&ceid=US:en",
        "AI"
    ),

    (
        "Google News AI Arabic",
        "https://news.google.com/rss/search?q=%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1%20%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A&hl=ar&gl=DZ&ceid=DZ:ar",
        "AI"
    ),

    (
        "The Verge AI",
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
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
        "MIT Technology Review",
        "https://www.technologyreview.com/feed/",
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
        "https://news.google.com/rss/search?q=cars%20automotive%20vehicles&hl=en&gl=US&ceid=US:en",
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
        "https://news.google.com/rss/search?q=entertainment%20movies%20music%20games&hl=en&gl=US&ceid=US:en",
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
        "Google News World",
        "https://news.google.com/rss?hl=ar&gl=DZ&ceid=DZ:ar",
        "World"
    ),

    (
        "Reuters World",
        "https://feeds.reuters.com/reuters/worldNews",
        "World"
    ),

    (
        "Google News World English",
        "https://news.google.com/rss/search?q=world%20news&hl=en&gl=US&ceid=US:en",
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
        "https://news.google.com/rss/search?q=science%20discovery%20research&hl=en&gl=US&ceid=US:en",
        "Facts"
    ),

    (
        "Google News Facts Arabic",
        "https://news.google.com/rss/search?q=%D8%AD%D9%82%D8%A7%D8%A6%D9%82%20%D8%B9%D9%84%D9%85%D9%8A%D8%A9%20%D8%A7%D9%83%D8%AA%D8%B4%D8%A7%D9%81%D8%A7%D8%AA&hl=ar&gl=DZ&ceid=DZ:ar",
        "Facts"
    ),


    # ========================================================
    # PRODUCTS
    # ========================================================

    (
        "Google News Products",
        "https://news.google.com/rss/search?q=new%20products%20gadgets&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Gadgets",
        "https://news.google.com/rss/search?q=new%20gadgets%20smartphones%20devices&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Products Arabic",
        "https://news.google.com/rss/search?q=%D9%85%D9%86%D8%AA%D8%AC%D8%A7%D8%AA%20%D8%AC%D8%AF%D9%8A%D8%AF%D8%A9%20%D9%87%D9%88%D8%A7%D8%AA%D9%81%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9&hl=ar&gl=DZ&ceid=DZ:ar",
        "Products"
    ),

]


# ============================================================
# SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({

    "User-Agent":
        "NOWNEX/2.0 NewsBot",

    "Accept":
        "application/rss+xml, application/xml, text/xml, text/html",

})


# ============================================================
# TEXT HELPERS
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

    title = clean_text(
        title
    ).lower()

    return re.sub(
        r"[^\w\u0600-\u06FF]+",
        "",
        title
    )


def remove_duplicates(items):

    result = []

    seen = set()

    for item in items:

        key = normalize_title(
            item.get(
                "title",
                ""
            )
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

def arabic_chars(text):

    return re.findall(
        r"[\u0600-\u06FF]",
        clean_text(text)
    )


def english_chars(text):

    return re.findall(
        r"[A-Za-z]",
        clean_text(text)
    )


def all_letters(text):

    return re.findall(
        r"[A-Za-z\u0600-\u06FF]",
        clean_text(text)
    )


def arabic_ratio(text):

    letters = all_letters(
        text
    )

    if not letters:
        return 0

    return len(
        arabic_chars(text)
    ) / len(letters)


def english_ratio(text):

    letters = all_letters(
        text
    )

    if not letters:
        return 0

    return len(
        english_chars(text)
    ) / len(letters)


# ============================================================
# ALLOWED FOREIGN NAMES
# ============================================================

# أسماء تجارية وتقنية يمكن أن تظهر داخل النص العربي
# بدون اعتبارها خلطًا للغة.

ALLOWED_LATIN_WORDS = {

    "AI",
    "OpenAI",
    "Anthropic",
    "Google",
    "Microsoft",
    "Apple",
    "Samsung",
    "Tesla",
    "Meta",
    "Amazon",
    "Nvidia",
    "Intel",
    "AMD",
    "Sony",
    "Nintendo",
    "Netflix",
    "YouTube",
    "TikTok",
    "Instagram",
    "Facebook",
    "WhatsApp",
    "ChatGPT",
    "Gemini",
    "Claude",
    "GPT",
    "Android",
    "iPhone",
    "iOS",
    "Windows",
    "Xbox",
    "PlayStation",
    "BMW",
    "Mercedes",
    "Audi",
    "Toyota",
    "Honda",
    "Ford",
    "BYD",
    "Hyundai",
    "Kia",
    "Reuters",
    "BBC",
    "TechCrunch",
    "The",
    "Verge",
    "NASA",
    "SpaceX",
    "YouTube",
}


def remove_allowed_names(text):

    result = clean_text(
        text
    )

    for word in ALLOWED_LATIN_WORDS:

        result = re.sub(
            rf"\b{re.escape(word)}\b",
            "",
            result,
            flags=re.IGNORECASE
        )

    return result


def contains_mixed_language_problem(
    text,
    language
):

    cleaned = remove_allowed_names(
        text
    )

    ar = arabic_ratio(
        cleaned
    )

    en = english_ratio(
        cleaned
    )


    if language == "ar":

        # بعد إزالة أسماء الشركات،
        # لا نريد كمية كبيرة من الإنجليزية.

        if en > 0.20:

            return True

        if ar < 0.55:

            return True


    if language == "en":

        if ar > 0.10:

            return True

        if en < 0.65:

            return True


    return False


def is_valid_arabic(text):

    text = clean_text(
        text
    )

    if len(text) < 8:
        return False

    if len(arabic_chars(text)) < 4:
        return False

    if contains_mixed_language_problem(
        text,
        "ar"
    ):

        return False

    return True


def is_valid_english(text):

    text = clean_text(
        text
    )

    if len(text) < 8:
        return False

    if len(english_chars(text)) < 5:
        return False

    if contains_mixed_language_problem(
        text,
        "en"
    ):

        return False

    return True


# ============================================================
# IMAGE
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
            return str(
                url
            ).strip()


    for media in entry.get(
        "media_thumbnail",
        []
    ):

        url = (
            media.get("url")
            or media.get("href")
        )

        if url:
            return str(
                url
            ).strip()


    for enclosure in entry.get(
        "enclosures",
        []
    ):

        url = (
            enclosure.get("href")
            or enclosure.get("url")
        )

        if url:
            return str(
                url
            ).strip()


    source_text = (
        entry.get(
            "summary",
            ""
        )
        or
        entry.get(
            "description",
            ""
        )
    )


    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        str(source_text),
        re.IGNORECASE
    )


    if match:

        return html.unescape(
            match.group(1).strip()
        )


    return ""


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
                    (
                        "http://",
                        "https://"
                    )
                ):

                    return image


    except Exception as error:

        print(
            "Image error:",
            error
        )


    return ""


def get_best_image(
    entry,
    link
):

    image = extract_rss_image(
        entry
    )

    if image:
        return image

    return get_og_image(
        link
    )


# ============================================================
# RSS COLLECTION
# ============================================================

def get_news():

    articles = []


    for source_name, feed_url, category in RSS_FEEDS:

        print(
            "\n--------------------------------"
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

            feed = feedparser.parse(
                feed_url
            )

            entries = feed.entries[:20]


            print(
                "Entries:",
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

                })


        except Exception as error:

            print(
                "RSS ERROR:",
                error
            )


    articles = remove_duplicates(
        articles
    )


    print(
        "\nTOTAL RSS ARTICLES:",
        len(articles)
    )


    return articles


# ============================================================
# QUALITY
# ============================================================

def summary_quality(
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
# FINAL LANGUAGE VALIDATION
# ============================================================

def article_is_valid(
    title_ar,
    summary_ar,
    title_en,
    summary_en
):

    # Arabic title
    if not is_valid_arabic(
        title_ar
    ):

        print(
            "FAILED Arabic title"
        )

        return False


    # Arabic summary
    if not is_valid_arabic(
        summary_ar
    ):

        print(
            "FAILED Arabic summary"
        )

        return False


    # Arabic quality
    if not summary_quality(
        title_ar,
        summary_ar
    ):

        print(
            "FAILED Arabic quality"
        )

        return False


    # English title
    if not is_valid_english(
        title_en
    ):

        print(
            "FAILED English title"
        )

        return False


    # English summary
    if not is_valid_english(
        summary_en
    ):

        print(
            "FAILED English summary"
        )

        return False


    # English quality
    if not summary_quality(
        title_en,
        summary_en
    ):

        print(
            "FAILED English quality"
        )

        return False


    return True


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(
    article
):

    title = article.get(
        "title",
        ""
    )

    description = article.get(
        "description",
        ""
    )

    source = article.get(
        "source",
        ""
    )

    category = article.get(
        "category",
        ""
    )


    if not description:

        description = (
            "No additional description "
            "is available. Use only the "
            "headline and available information."
        )


    prompt = f"""
You are the senior editor of NOWNEX,
a professional bilingual news platform.

Create a news article based ONLY on the
source information provided below.

SOURCE:
{source}

CATEGORY:
{category}

ORIGINAL HEADLINE:
{title}

SOURCE INFORMATION:
{description}


============================================================
RETURN EXACTLY FOUR JSON FIELDS
============================================================

title_ar
summary_ar
title_en
summary_en


============================================================
ARABIC VERSION
============================================================

title_ar MUST be Modern Standard Arabic.

summary_ar MUST be Modern Standard Arabic.

The Arabic version MUST NOT be written in English.

Translate and professionally rewrite the source information.

Do not copy the English headline.

Do not copy English sentences.

English is allowed only for unavoidable proper names,
brands, companies, products, organizations or technical
names that are normally written in Latin characters.

Examples that are allowed:

OpenAI
Google
Tesla
Samsung
ChatGPT
AI
NASA

However, do NOT write complete English sentences
inside the Arabic version.

Arabic must remain the dominant language.


============================================================
ENGLISH VERSION
============================================================

title_en MUST be professional English.

summary_en MUST be professional English.

The English version MUST NOT be written in Arabic.

Do not copy Arabic sentences.

Arabic is allowed only for unavoidable proper names.

English must remain the dominant language.


============================================================
CONTENT
============================================================

Both versions must describe exactly the same event.

Do NOT invent facts.

Do NOT invent numbers.

Do NOT invent people.

Do NOT invent quotes.

Do NOT invent dates.

Do NOT add opinions.

Use ONLY the supplied information.

Arabic summary must contain 3 to 5 sentences.

English summary must contain 3 to 5 sentences.

No Markdown.

No bullet points.

No emojis.


============================================================
VERY IMPORTANT
============================================================

If the original article is English:

Create a REAL Arabic translation/rewrite
for title_ar and summary_ar.

If the original article is Arabic:

Create a REAL English translation/rewrite
for title_en and summary_en.

Never put the source language in the wrong field.


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

                "role":
                    "user",

                "parts": [

                    {

                        "text":
                            prompt

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
        GEMINI_RETRIES + 1
    ):

        try:

            print(
                f"Gemini attempt "
                f"{attempt}/{GEMINI_RETRIES}"
            )


            response = requests.post(

                GEMINI_URL,

                headers=headers,

                json=payload,

                timeout=GEMINI_TIMEOUT

            )


            print(
                "Status:",
                response.status_code
            )


            if response.status_code == 429:

                wait = (
                    30
                    if attempt == 1
                    else
                    60
                    if attempt == 2
                    else
                    90
                )


                print(
                    "Rate limit. "
                    f"Waiting {wait}s."
                )


                time.sleep(
                    wait
                )

                continue


            if response.status_code != 200:

                print(
                    response.text[:1000]
                )


                if attempt < GEMINI_RETRIES:

                    time.sleep(
                        15
                    )

                    continue


                return None


            data = response.json()


            text = (
                data
                ["candidates"]
                [0]
                ["content"]
                ["parts"]
                [0]
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


            # =================================================
            # STRICT CHECK
            # =================================================

            if not article_is_valid(

                title_ar,

                summary_ar,

                title_en,

                summary_en

            ):

                print(
                    "LANGUAGE / QUALITY CHECK FAILED."
                )


                if attempt < GEMINI_RETRIES:

                    time.sleep(
                        4
                    )

                    continue


                return None


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

        item

        for item in articles

        if item.get(
            "category"
        ) == category

    ]


# ============================================================
# EXISTING NEWS
# ============================================================

def load_existing_news():

    if not os.path.exists(
        "news.json"
    ):

        return []


    try:

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


        if isinstance(
            news,
            list
        ):

            print(
                "Existing news:",
                len(news)
            )

            return news


    except Exception as error:

        print(
            "Existing news error:",
            error
        )


    return []


# ============================================================
# BUILD FINAL ITEM
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
        "\n"
        "=========================================="
    )

    print(
        " NOWNEX NEWS ENGINE"
    )

    print(
        " 7 CATEGORIES × 3 ARTICLES"
    )

    print(
        "=========================================="
    )


    # ========================================================
    # LOAD OLD DATA
    # ========================================================

    old_news = load_existing_news()


    # ========================================================
    # RSS
    # ========================================================

    articles = get_news()


    if not articles:

        print(
            "No RSS data."
        )

        print(
            "Keeping existing news.json."
        )

        return


    # ========================================================
    # PREPARE CATEGORY POOLS
    # ========================================================

    pools = {

        category: []

        for category in MAIN_CATEGORIES

    }


    for category in MAIN_CATEGORIES:

        category_articles = get_category_articles(
            articles,
            category
        )


        pools[category] = category_articles[
            :CANDIDATES_PER_CATEGORY
        ]


        print(
            f"{category}: "
            f"{len(pools[category])} candidates"
        )


    # ========================================================
    # GENERATE
    # ========================================================

    generated = {

        category: []

        for category in MAIN_CATEGORIES

    }


    used_original_titles = set()


    for category in MAIN_CATEGORIES:

        print(
            "\n"
            "=========================================="
        )

        print(
            f"PROCESSING CATEGORY: {category}"
        )

        print(
            "=========================================="
        )


        for article in pools[category]:

            if len(
                generated[category]
            ) >= MIN_PER_CATEGORY:

                break


            original_key = normalize_title(
                article["title"]
            )


            if original_key in used_original_titles:

                continue


            used_original_titles.add(
                original_key
            )


            print(
                "\nTrying:",
                article["title"]
            )


            ai = ask_gemini(
                article
            )


            if not ai:

                print(
                    "✗ Rejected. "
                    "Trying next candidate."
                )

                continue


            item = build_news_item(
                article,
                ai
            )


            generated[category].append(
                item
            )


            print(
                "✓ ACCEPTED"
            )


            time.sleep(
                REQUEST_DELAY
            )


        print(
            f"{category}: "
            f"{len(generated[category])} "
            f"new articles"
        )


    # ========================================================
    # FALLBACK FROM OLD NEWS
    # ========================================================

    old_by_category = {

        category: []

        for category in MAIN_CATEGORIES

    }


    for item in old_news:

        category = item.get(
            "category"
        )


        if category not in VALID_CATEGORIES:

            continue


        if not item.get(
            "title_ar"
        ):

            continue


        if not item.get(
            "title_en"
        ):

            continue


        old_by_category[
            category
        ].append(
            item
        )


    # ========================================================
    # ASSEMBLE 3 PER CATEGORY
    # ========================================================

    final_news = []

    final_keys = set()


    for category in MAIN_CATEGORIES:

        print(
            "\nFINALIZING:",
            category
        )


        # New articles first

        for item in generated[category]:

            key = normalize_title(
                item.get(
                    "title_ar",
                    ""
                )
            )


            if key in final_keys:
                continue


            final_keys.add(
                key
            )


            final_news.append(
                item
            )


            if len(
                get_category_articles(
                    final_news,
                    category
                )
            ) >= MIN_PER_CATEGORY:

                break


        # Old articles as fallback

        current_count = len(
            get_category_articles(
                final_news,
                category
            )
        )


        if current_count < MIN_PER_CATEGORY:

            print(
                f"{category}: "
                f"using old valid articles "
                f"as fallback."
            )


            for item in old_by_category[category]:

                key = normalize_title(
                    item.get(
                        "title_ar",
                        ""
                    )
                )


                if key in final_keys:

                    continue


                final_keys.add(
                    key
                )


                final_news.append(
                    item
                )


                current_count += 1


                if current_count >= MIN_PER_CATEGORY:

                    break


        print(
            f"{category}: "
            f"{current_count} final"
        )


    # ========================================================
    # FILL EXTRA ARTICLES
    # ========================================================

    if len(final_news) < MAX_NEWS:

        print(
            "\nAdding extra articles..."
        )


        for category in MAIN_CATEGORIES:

            for item in generated[category]:

                if len(final_news) >= MAX_NEWS:

                    break


                key = normalize_title(
                    item.get(
                        "title_ar",
                        ""
                    )
                )


                if key in final_keys:

                    continue


                final_keys.add(
                    key
                )


                final_news.append(
                    item
                )


            if len(final_news) >= MAX_NEWS:

                break


    final_news = final_news[
        :MAX_NEWS
    ]


    # ========================================================
    # FINAL CATEGORY CHECK
    # ========================================================

    print(
        "\n"
        "=========================================="
    )

    print(
        "FINAL CATEGORY CHECK"
    )

    print(
        "=========================================="
    )


    missing = []


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

            missing.append(
                category
            )


    # ========================================================
    # SAFETY
    # ========================================================

    if missing:

        print(
            "\nWARNING:"
        )

        print(
            "The following categories are incomplete:"
        )

        print(
            missing
        )


        # إذا كان لدينا ملف قديم يحتوي أخبارًا أكثر،
        # لا نسمح بتدميره.

        if len(old_news) >= MIN_PER_CATEGORY:

            print(
                "INCOMPLETE UPDATE."
            )

            print(
                "Keeping previous news.json."
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
    # SUCCESS
    # ========================================================

    print(
        "\n"
        "=========================================="
    )

    print(
        " NOWNEX NEWS UPDATED"
    )

    print(
        "=========================================="
    )


    print(
        "TOTAL:",
        len(final_news)
    )


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


    print(
        "\nNOWNEX update complete."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
