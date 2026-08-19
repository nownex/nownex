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
# NOWNEX — Arabic AI News Engine
# Stable Version
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

# لا نريد إرسال عدد كبير من الطلبات إلى Gemini.
MAX_NEWS = 8

REQUEST_TIMEOUT = 25

# وقت الانتظار بين الأخبار.
REQUEST_DELAY = 8


# ============================================================
# NEWS SOURCES
# ============================================================

RSS_FEEDS = [

    # =========================
    # TECHNOLOGY
    # =========================

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


    # =========================
    # AI
    # =========================

    (
        "TechCrunch AI",
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "AI"
    ),


    # =========================
    # CARS
    # =========================

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


    # =========================
    # WORLD
    # =========================

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
        "Google News",
        "https://news.google.com/rss?"
        "hl=ar&gl=DZ&ceid=DZ:ar",
        "World"
    )

]


# ============================================================
# VALID CATEGORIES
# ============================================================

VALID_CATEGORIES = {
    "World",
    "Technology",
    "Entertainment",
    "AI",
    "Cars",
    "Science",
    "Sports",
    "Facts"
}


# ============================================================
# HTTP SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({

    "User-Agent":
        "NOWNEX/1.0 NewsBot",

    "Accept":
        "application/rss+xml, application/xml, text/xml, text/html"

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

    # media_content

    media_content = entry.get(
        "media_content",
        []
    )

    for media in media_content:

        url = (
            media.get("url")
            or
            media.get("href")
        )

        if url:
            return str(url).strip()


    # media_thumbnail

    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    for media in media_thumbnail:

        url = (
            media.get("url")
            or
            media.get("href")
        )

        if url:
            return str(url).strip()


    # enclosure

    enclosures = entry.get(
        "enclosures",
        []
    )

    for enclosure in enclosures:

        url = (
            enclosure.get("href")
            or
            enclosure.get("url")
        )

        if url:
            return str(url).strip()


    # image inside HTML

    sources = [

        entry.get(
            "summary",
            ""
        ),

        entry.get(
            "description",
            ""
        )

    ]


    for source in sources:

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

                if (
                    image.startswith("http://")
                    or
                    image.startswith("https://")
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


        seen.add(key)

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


            entries = feed.entries[:12]


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


    if len(summary) < 120:
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
            "اعتمد على العنوان فقط."
        )


    prompt = f"""
أنت محرر الأخبار في منصة NOWNEX العربية.

اكتب نسخة عربية أصلية ومختصرة للخبر التالي.

المصدر:
{source}

التصنيف:
{category}

العنوان الأصلي:
{title}

المعلومات المتاحة:
{description}

أرسل JSON فقط:

{{
  "title": "عنوان عربي احترافي",
  "summary": "ملخص عربي من 3 إلى 5 جمل"
}}

القواعد:

- العربية الفصحى.
- لا تكرر العنوان داخل الملخص.
- الملخص من 3 إلى 5 جمل.
- لا تخترع أي معلومة.
- لا تخترع أسماء أو أرقامًا أو تصريحات.
- لا تضف رأيًا.
- اعتمد فقط على المعلومات المتاحة.
- أرسل JSON صالحًا فقط.
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

            "temperature": 0.2,

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


    # ========================================================
    # IMPORTANT:
    # We use only ONE request normally.
    # If 429 occurs, wait before trying again.
    # ========================================================

    for attempt in range(1, 4):

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


            # ------------------------------------------------
            # RATE LIMIT
            # ------------------------------------------------

            if response.status_code == 429:

                print(
                    "Gemini rate limit (429)."
                )


                if attempt == 1:

                    wait_time = 30

                elif attempt == 2:

                    wait_time = 60

                else:

                    wait_time = 90


                print(
                    f"Waiting {wait_time} seconds..."
                )


                time.sleep(
                    wait_time
                )

                continue


            # ------------------------------------------------
            # OTHER ERROR
            # ------------------------------------------------

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


            new_title = clean_text(
                result.get(
                    "title",
                    ""
                )
            )


            new_summary = clean_text(
                result.get(
                    "summary",
                    ""
                )
            )


            if not new_title:

                print(
                    "Empty Gemini title."
                )

                return None


            if not summary_is_valid(
                title,
                new_summary
            ):

                print(
                    "Invalid Gemini summary."
                )

                return None


            return {

                "title":
                    new_title,

                "summary":
                    new_summary

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
# SELECT NEWS
# ============================================================

def select_news(
    articles
):

    technology = [
        x for x in articles
        if x["category"] == "Technology"
    ]


    cars = [
        x for x in articles
        if x["category"] == "Cars"
    ]


    ai_news = [
        x for x in articles
        if x["category"] == "AI"
    ]


    other = [
        x for x in articles
        if x["category"]
        not in {
            "Technology",
            "Cars",
            "AI"
        }
    ]


    selected = []


    # ---------------------------------------------
    # TECHNOLOGY
    # ---------------------------------------------

    selected.extend(
        technology[:2]
    )


    # ---------------------------------------------
    # CARS
    # ---------------------------------------------

    selected.extend(
        cars[:2]
    )


    # ---------------------------------------------
    # AI
    # ---------------------------------------------

    selected.extend(
        ai_news[:1]
    )


    # ---------------------------------------------
    # OTHER
    # ---------------------------------------------

    selected.extend(
        other[:3]
    )


    # ---------------------------------------------
    # Fill if necessary
    # ---------------------------------------------

    selected_keys = {
        normalize_title(
            x["title"]
        )
        for x in selected
    }


    for article in articles:

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


        if len(selected) >= MAX_NEWS:
            break


    return selected[:MAX_NEWS]


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("==============================")
    print(" NOWNEX AI NEWS ENGINE")
    print("==============================")
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


    selected = select_news(
        articles
    )


    print(
        "Selected:",
        len(selected)
    )


    final_news = []


    # ========================================================
    # PROCESS ARTICLES
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
            "Original:",
            article["title"]
        )


        ai = ask_gemini(

            article["title"],

            article["description"],

            article["source"],

            article["category"]

        )


        # ----------------------------------------------------
        # If Gemini refuses / rate limited,
        # skip this article instead of crashing everything.
        # ----------------------------------------------------

        if not ai:

            print(
                "✗ Article skipped."
            )

            continue


        item = {

            "title":
                ai["title"],

            "summary":
                ai["summary"],

            "description":
                ai["summary"],

            # IMPORTANT:
            # Keep the original category.
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
            "✓ Article created"
        )


        if item["image"]:

            print(
                "✓ Image available"
            )

        else:

            print(
                "⚠ No image"
            )


        # Important delay between API requests.

        time.sleep(
            REQUEST_DELAY
        )


    # ========================================================
    # NO ARTICLES
    # ========================================================

    if not final_news:

        print("")
        print(
            "================================"
        )

        print(
            "Gemini did not return any articles."
        )

        print(
            "Keeping existing news.json unchanged."
        )

        print(
            "================================"
        )

        # IMPORTANT:
        # Do NOT overwrite news.json.
        # Do NOT crash the entire website.
        return


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


    print("")
    print("==============================")
    print(" NOWNEX NEWS UPDATED")
    print(
        "Articles:",
        len(final_news)
    )
    print("==============================")
    print("")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
