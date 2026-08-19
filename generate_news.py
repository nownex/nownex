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
# NOWNEX — Bilingual News Engine
# LARGE NEWS EDITION
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

# العدد المستهدف
MAX_NEWS = 40

# الحد الأدنى لكل قسم
MIN_PER_CATEGORY = 4

# عدد الأخبار التي نقرأها من كل RSS
ENTRIES_PER_FEED = 15

REQUEST_TIMEOUT = 25

# التأخير بين طلبات Gemini
REQUEST_DELAY = 8


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

    (
        "Google News Technology",
        "https://news.google.com/rss/search?"
        "q=technology%20gadgets%20smartphones"
        "&hl=en&gl=US&ceid=US:en",
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
        "q=%D8%AA%D8%B1%D9%81%D9%8A%D9%87%20%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D9%85%D9%88%D8%B3%D9%8A%D9%82%D9%89"
        "&hl=ar&gl=DZ&ceid=DZ:ar",
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
        "https://news.google.com/rss?"
        "hl=ar&gl=DZ&ceid=DZ:ar",
        "World"
    ),

    (
        "Google News World English",
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
        "Google News Facts Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%AD%D9%82%D8%A7%D8%A6%D9%82%20%D8%B9%D9%84%D9%85%20%D8%A7%D9%83%D8%AA%D8%B4%D8%A7%D9%81%D8%A7%D8%AA"
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
# SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({

    "User-Agent":
        "NOWNEX/2.0 NewsBot",

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
# IMAGE FROM RSS
# ============================================================

def extract_rss_image(entry):

    for media in entry.get(
        "media_content",
        []
    ):

        url = (
            media.get("url")
            or
            media.get("href")
        )

        if url:
            return str(url).strip()


    for media in entry.get(
        "media_thumbnail",
        []
    ):

        url = (
            media.get("url")
            or
            media.get("href")
        )

        if url:
            return str(url).strip()


    for enclosure in entry.get(
        "enclosures",
        []
    ):

        url = (
            enclosure.get("href")
            or
            enclosure.get("url")
        )

        if url:
            return str(url).strip()


    for source in [

        entry.get(
            "summary",
            ""
        ),

        entry.get(
            "description",
            ""
        )

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

        page = response.text[:800000]

        patterns = [

            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']'

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
                    "http://"
                ) or image.startswith(
                    "https://"
                ):

                    return image

    except Exception as error:

        print(
            "Image error:",
            error
        )

    return ""


# ============================================================
# BEST IMAGE
# ============================================================

def get_best_image(entry, link):

    image = extract_rss_image(
        entry
    )

    if image:
        return image

    return get_og_image(
        link
    )


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(items):

    result = []

    seen = set()

    for item in items:

        key = normalize_title(
            item["title"]
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(
            key
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
            "Reading:",
            source_name
        )

        try:

            feed = feedparser.parse(
                feed_url
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
                        published

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
# ENGLISH VALIDATION
# ============================================================

def english_is_valid(
    title,
    summary
):

    summary = clean_text(
        summary
    )

    title = clean_text(
        title
    )

    if not title:
        return False

    if not summary:
        return False

    if len(summary) < 100:
        return False

    if summary.lower() == title.lower():
        return False

    sentences = len(
        re.findall(
            r"[.!?]",
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
            "No additional description "
            "is available. Use only the "
            "information in the headline."
        )


    prompt = f"""
You are the senior news editor of NOWNEX.

Create a bilingual Arabic/English version
of the following news story.

SOURCE:
{source}

CATEGORY:
{category}

ORIGINAL HEADLINE:
{title}

AVAILABLE INFORMATION:
{description}

Return ONLY valid JSON:

{{
  "title_ar": "عنوان عربي احترافي",
  "summary_ar": "ملخص عربي من 3 إلى 5 جمل",
  "title_en": "Professional English headline",
  "summary_en": "English summary of 3 to 5 sentences"
}}

IMPORTANT RULES:

1. Arabic must be Modern Standard Arabic.
2. English must be natural professional journalism.
3. Both languages must communicate exactly the same information.
4. Do not invent facts.
5. Do not invent names.
6. Do not invent numbers.
7. Do not invent quotes.
8. Do not add opinions.
9. Use only the supplied information.
10. Do not make unsupported claims.
11. Arabic summary must contain 3 to 5 sentences.
12. English summary must contain 3 to 5 sentences.
13. Return valid JSON only.
14. Do not use Markdown.
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

                timeout=90

            )


            print(
                "Gemini status:",
                response.status_code
            )


            if response.status_code == 429:

                wait_time = (
                    30
                    if attempt == 1
                    else
                    60
                    if attempt == 2
                    else
                    90
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
                    response.text[:1500]
                )

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
            )


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


            if not summary_is_valid(
                title_ar,
                summary_ar
            ):

                print(
                    "Invalid Arabic summary."
                )

                return None


            if not english_is_valid(
                title_en,
                summary_en
            ):

                print(
                    "Invalid English summary."
                )

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


            if attempt < 3:

                time.sleep(
                    20
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
    # STEP 1
    # ضمان الحد الأدنى لكل قسم حقيقي
    # ========================================================

    for category in MAIN_CATEGORIES:

        category_articles = (
            get_category_articles(
                articles,
                category
            )
        )


        count = 0


        for article in category_articles:

            key = normalize_title(
                article["title"]
            )


            if key in selected_keys:
                continue


            selected.append(
                article
            )

            selected_keys.add(
                key
            )

            count += 1


            if count >= MIN_PER_CATEGORY:
                break


    # ========================================================
    # STEP 2
    # إضافة الأخبار المتبقية
    # ========================================================

    for article in articles:

        if len(selected) >= MAX_NEWS:
            break


        key = normalize_title(
            article["title"]
        )


        if key in selected_keys:
            continue


        selected.append(
            article
        )

        selected_keys.add(
            key
        )


    return selected[:MAX_NEWS]


# ============================================================
# CREATE TRENDING
# ============================================================

def create_trending(
    final_news
):

    """
    Trending ليس RSS مستقلًا.

    نأخذ أفضل الأخبار من مختلف الأقسام
    ونضع نسخة منها في قسم Trending.
    """

    if not final_news:
        return []


    trending = []

    seen = set()


    # نأخذ الأخبار بالتناوب من الأقسام
    # حتى يكون Trending متنوعًا.

    for index in range(
        len(final_news)
    ):

        for category in MAIN_CATEGORIES:

            candidates = [

                item

                for item in final_news

                if item.get(
                    "category"
                ) == category

            ]


            if index >= len(
                candidates
            ):
                continue


            item = candidates[
                index
            ]


            key = normalize_title(
                item.get(
                    "title_ar",
                    item.get(
                        "title",
                        ""
                    )
                )
            )


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
# MAIN
# ============================================================

def main():

    print("")
    print(
        "================================"
    )
    print(
        " NOWNEX LARGE NEWS ENGINE"
    )
    print(
        "================================"
    )

    print(
        "Target:",
        MAX_NEWS
    )

    print(
        "Minimum per category:",
        MIN_PER_CATEGORY
    )

    print("")


    articles = get_news()


    if not articles:

        print(
            "No RSS articles found."
        )

        return


    print("")
    print(
        "Collected:",
        len(articles)
    )


    # ========================================================
    # AVAILABLE COUNTS
    # ========================================================

    print("")
    print(
        "Available articles:"
    )


    for category in MAIN_CATEGORIES:

        print(

            f"{category}: "
            f"{len(get_category_articles("
            f"articles,"
            f"category"
            f"))}"

        )


    # ========================================================
    # SELECT
    # ========================================================

    selected = select_news(
        articles
    )


    print("")
    print(
        "Selected:",
        len(selected)
    )


    final_news = []


    # ========================================================
    # GEMINI PROCESSING
    # ========================================================

    for index, article in enumerate(
        selected,
        start=1
    ):

        print("")
        print(
            "================================"
        )

        print(
            f"Processing {index}/{len(selected)}"
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
            "Title:",
            article["title"]
        )


        ai = ask_gemini(

            article["title"],

            article["description"],

            article["source"],

            article["category"]

        )


        if not ai:

            print(
                "✗ Skipped"
            )

            continue


        item = {

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


        final_news.append(
            item
        )


        print(
            "✓ Created"
        )


        if item["image"]:

            print(
                "✓ Image"
            )

        else:

            print(
                "⚠ No image"
            )


        time.sleep(
            REQUEST_DELAY
        )


    # ========================================================
    # SAFETY
    # ========================================================

    if not final_news:

        print(
            "No articles generated."
        )

        print(
            "Existing news.json was NOT modified."
        )

        return


    # ========================================================
    # TRENDING
    # ========================================================

    trending_news = create_trending(
        final_news
    )


    # ========================================================
    # OUTPUT
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
    # REPORT
    # ========================================================

    print("")
    print(
        "================================"
    )

    print(
        " NOWNEX NEWS UPDATED"
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
        "================================"
    )


    print("")
    print(
        "FINAL CATEGORY COUNTS:"
    )


    for category in MAIN_CATEGORIES:

        count = len([

            item

            for item in final_news

            if item.get(
                "category"
            ) == category

        ])


        print(
            f"  {category}: {count}"
        )


    print("")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
