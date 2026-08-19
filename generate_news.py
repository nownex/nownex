import os
import json
import re
import html
import time
from datetime import datetime, timezone

import requests
import feedparser


# ============================================================
# NOWNEX — Arabic AI News Engine
# Version: 2.0
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


# ============================================================
# GEMINI
# ============================================================

# IMPORTANT:
# Gemini 2.5 Flash was retired for new users.
# Use the current model configured for this project.

GEMINI_MODEL = "gemini-3.6-flash"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{GEMINI_MODEL}:generateContent"
)


# ============================================================
# SETTINGS
# ============================================================

MAX_NEWS = 16

REQUEST_TIMEOUT = 25


# ============================================================
# NEWS SOURCES
#
# We deliberately separate technology and cars.
# This prevents the website from becoming mostly political/world
# news.
# ============================================================

RSS_FEEDS = [

    # --------------------------------------------------------
    # TECHNOLOGY
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    (
        "TechCrunch AI",
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "AI"
    ),

    # --------------------------------------------------------
    # CARS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # WORLD / GENERAL
    # --------------------------------------------------------

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
    ),

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
# SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/131.0 Safari/537.36"
    )
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

    title = clean_text(title).lower()

    title = re.sub(
        r"[^\w\u0600-\u06FF]+",
        "",
        title
    )

    return title


# ============================================================
# IMAGE EXTRACTION FROM RSS
# ============================================================

def extract_rss_image(entry):

    # --------------------------------------------------------
    # media_content
    # --------------------------------------------------------

    media_content = entry.get(
        "media_content",
        []
    )

    if media_content:

        for media in media_content:

            url = (
                media.get("url")
                or media.get("href")
            )

            if url:
                return str(url).strip()


    # --------------------------------------------------------
    # media_thumbnail
    # --------------------------------------------------------

    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    if media_thumbnail:

        for media in media_thumbnail:

            url = (
                media.get("url")
                or media.get("href")
            )

            if url:
                return str(url).strip()


    # --------------------------------------------------------
    # enclosure
    # --------------------------------------------------------

    enclosures = entry.get(
        "enclosures",
        []
    )

    for enclosure in enclosures:

        url = enclosure.get(
            "href"
        ) or enclosure.get(
            "url"
        )

        mime = str(
            enclosure.get(
                "type",
                ""
            )
        ).lower()

        if url and (
            "image" in mime
            or not mime
        ):

            return str(url).strip()


    # --------------------------------------------------------
    # image inside HTML
    # --------------------------------------------------------

    html_sources = [

        entry.get(
            "summary",
            ""
        ),

        entry.get(
            "description",
            ""
        ),

        str(
            entry.get(
                "content",
                ""
            )
        )

    ]


    for source in html_sources:

        match = re.search(
            r'<img[^>]+src=["\']([^"\']+)["\']',
            str(source),
            flags=re.IGNORECASE
        )

        if match:

            return html.unescape(
                match.group(1).strip()
            )


    return ""


# ============================================================
# GET OG IMAGE FROM ORIGINAL ARTICLE
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

        content_type = response.headers.get(
            "content-type",
            ""
        ).lower()

        if "text/html" not in content_type:
            return ""

        page = response.text[:1000000]


        # ----------------------------------------------------
        # og:image
        # ----------------------------------------------------

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
                flags=re.IGNORECASE
            )

            if match:

                image_url = html.unescape(
                    match.group(1).strip()
                )

                if image_url.startswith("//"):

                    image_url = (
                        "https:"
                        + image_url
                    )

                elif image_url.startswith("/"):

                    from urllib.parse import urljoin

                    image_url = urljoin(
                        response.url,
                        image_url
                    )

                if (
                    image_url.startswith(
                        "http://"
                    )
                    or
                    image_url.startswith(
                        "https://"
                    )
                ):

                    return image_url


    except Exception as error:

        print(
            "Image extraction error:",
            error
        )


    return ""


# ============================================================
# VALIDATE IMAGE URL
# ============================================================

def valid_image_url(url):

    if not url:
        return False

    url = str(url).strip()

    return (
        url.startswith("http://")
        or
        url.startswith("https://")
    )


# ============================================================
# GET BEST IMAGE
# ============================================================

def get_best_image(entry, article_url):

    # First try RSS image.

    rss_image = extract_rss_image(
        entry
    )

    if valid_image_url(
        rss_image
    ):

        return rss_image


    # If RSS does not contain a useful image,
    # try the original article.

    og_image = get_og_image(
        article_url
    )

    if valid_image_url(
        og_image
    ):

        return og_image


    return ""


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

        result.append(item)

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


            if getattr(
                feed,
                "bozo",
                False
            ):

                print(
                    "RSS warning:",
                    getattr(
                        feed,
                        "bozo_exception",
                        ""
                    )
                )


            entries = feed.entries[:15]


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


                if not title:
                    continue

                if not link:
                    continue


                # Get the best available image.

                image = get_best_image(
                    entry,
                    link
                )


                published = (
                    entry.get(
                        "published",
                        ""
                    )
                    or
                    entry.get(
                        "updated",
                        ""
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
                        clean_text(
                            published
                        )

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

    title_clean = clean_text(
        title
    )

    summary_clean = clean_text(
        summary
    )


    if not summary_clean:
        return False


    if len(summary_clean) < 120:
        return False


    if summary_clean.lower() == title_clean.lower():
        return False


    sentence_count = len(
        re.findall(
            r"[.!؟。]",
            summary_clean
        )
    )


    if sentence_count < 2:
        return False


    return True


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(
    title,
    description,
    source,
    source_category
):

    if not description:

        description = (
            "لا يوجد وصف إضافي متاح من مصدر RSS. "
            "اعتمد على العنوان فقط ولا تخترع تفاصيل."
        )


    prompt = f"""
أنت محرر الأخبار الرئيسي في منصة NOWNEX العربية.

مهمتك هي إعادة صياغة الخبر الموجود في البيانات
أدناه باللغة العربية الفصحى بطريقة واضحة ومختصرة.

المصدر:
{source}

التصنيف المحدد من نظام NOWNEX:
{source_category}

العنوان الأصلي:
{title}

النص أو الوصف المتاح:
{description}

أرسل JSON فقط بهذا الشكل:

{{
  "title": "عنوان عربي احترافي",
  "summary": "ملخص عربي واضح من 3 إلى 5 جمل",
  "category": "{source_category}"
}}

الفئات المسموح بها فقط:

World
Technology
Entertainment
AI
Cars
Science
Sports
Facts

القواعد:

- استخدم العربية الفصحى.
- لا تكرر العنوان داخل الملخص.
- الملخص مختلف عن العنوان.
- الملخص من 3 إلى 5 جمل.
- لا تخترع أي معلومات.
- لا تضف أرقامًا أو أسماء أو تصريحات غير موجودة في المادة.
- إذا كانت المعلومات ناقصة، اذكر فقط المعلومات المؤكدة.
- لا تضف رأيًا شخصيًا.
- لا تستخدم Markdown.
- أرسل JSON صالحًا فقط.
- التصنيف الأساسي يجب أن يبقى "{source_category}".
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


    last_error = None


    for attempt in range(1, 4):

        try:

            print(
                f"Gemini attempt {attempt}/3"
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


            if response.status_code != 200:

                print(
                    response.text[:2000]
                )

                raise RuntimeError(
                    f"Gemini HTTP {response.status_code}"
                )


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


            # IMPORTANT:
            # Keep the source category.
            # Gemini must not randomly classify a car article
            # as World.

            new_category = source_category


            if not new_title:

                raise RuntimeError(
                    "Gemini returned an empty title."
                )


            if not summary_is_valid(
                title,
                new_summary
            ):

                raise RuntimeError(
                    "Gemini returned an invalid summary."
                )


            return {

                "title":
                    new_title,

                "summary":
                    new_summary,

                "category":
                    new_category

            }


        except Exception as error:

            last_error = error

            print(
                "Gemini error:",
                error
            )


            if attempt < 3:

                time.sleep(4)


    raise RuntimeError(
        "Gemini failed after 3 attempts: "
        + str(last_error)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("==============================")
    print(" NOWNEX AI NEWS ENGINE 2.0")
    print("==============================")
    print("")


    articles = get_news()


    if not articles:

        raise RuntimeError(
            "No news articles found."
        )


    print("")
    print(
        "Total articles collected:",
        len(articles)
    )


    # --------------------------------------------------------
    # BALANCED SELECTION
    #
    # Technology and Cars receive guaranteed places.
    # --------------------------------------------------------

    technology = [
        a for a in articles
        if a["category"] == "Technology"
    ]

    ai_news = [
        a for a in articles
        if a["category"] == "AI"
    ]

    cars = [
        a for a in articles
        if a["category"] == "Cars"
    ]

    other = [
        a for a in articles
        if a["category"] not in {
            "Technology",
            "AI",
            "Cars"
        }
    ]


    selected = []


    # Minimum technology news.

    selected.extend(
        technology[:4]
    )


    # Minimum AI news.

    selected.extend(
        ai_news[:2]
    )


    # Minimum car news.

    selected.extend(
        cars[:4]
    )


    # Fill the remaining positions
    # with general news.

    remaining_slots = (
        MAX_NEWS - len(selected)
    )


    if remaining_slots > 0:

        selected.extend(
            other[:remaining_slots]
        )


    # If still not enough articles,
    # fill from anything not selected.

    if len(selected) < MAX_NEWS:

        selected_keys = {
            normalize_title(
                item["title"]
            )
            for item in selected
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


    selected = remove_duplicates(
        selected
    )[:MAX_NEWS]


    print("")
    print(
        "Selected:",
        len(selected),
        "articles"
    )


    final_news = []


    for index, article in enumerate(
        selected,
        start=1
    ):

        print("")
        print(
            f"Processing {index}/{len(selected)}"
        )


        print(
            "Original:",
            article["title"]
        )


        print(
            "Category:",
            article["category"]
        )


        try:

            ai = ask_gemini(

                article["title"],

                article["description"],

                article["source"],

                article["category"]

            )


            published_at = (
                article["published"]
                or
                datetime.now(
                    timezone.utc
                ).isoformat()
            )


            item = {

                "title":
                    ai["title"],

                "summary":
                    ai["summary"],

                "description":
                    ai["summary"],

                "category":
                    ai["category"],

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
                    published_at

            }


            final_news.append(
                item
            )


            print(
                "✓ Arabic summary created"
            )


            if item["image"]:

                print(
                    "✓ Image found"
                )

            else:

                print(
                    "⚠ No image found"
                )


        except Exception as error:

            print(
                "✗ Article rejected:",
                error
            )


        # Small pause to avoid hammering the API.

        time.sleep(2)


    if not final_news:

        raise RuntimeError(
            "Gemini did not successfully create "
            "any Arabic articles."
        )


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
        f" Articles: {len(final_news)}"
    )
    print("==============================")
    print("")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
