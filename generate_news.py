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
# NEWS SOURCES
# ============================================================

RSS_FEEDS = [

    (
        "BBC عربي",
        "https://feeds.bbci.co.uk/arabic/rss.xml"
    ),

    (
        "الجزيرة",
        "https://www.aljazeera.net/aljazeera.rss"
    ),

    (
        "Google News",
        "https://news.google.com/rss?"
        "hl=ar&gl=DZ&ceid=DZ:ar"
    ),

]


MAX_NEWS = 8


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
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/131.0 Safari/537.36"

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
# CHECK IMAGE URL
# ============================================================

def valid_image_url(url):

    if not url:
        return ""

    url = str(url).strip()

    if not url:
        return ""

    if not (
        url.startswith("http://")
        or
        url.startswith("https://")
    ):
        return ""

    # Reject obvious tracking / non-image URLs

    lowered = url.lower()

    blocked = [

        "favicon",
        "logo.svg",
        "sprite",
        "avatar",
        "icon.png"

    ]

    for word in blocked:

        if word in lowered:

            return ""

    return url


# ============================================================
# EXTRACT IMAGE FROM RSS ENTRY
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

            if not isinstance(
                media,
                dict
            ):
                continue

            url = (
                media.get("url")
                or
                media.get("href")
            )

            image = valid_image_url(
                url
            )

            if image:
                return image


    # --------------------------------------------------------
    # media_thumbnail
    # --------------------------------------------------------

    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    if media_thumbnail:

        for media in media_thumbnail:

            if not isinstance(
                media,
                dict
            ):
                continue

            url = (
                media.get("url")
                or
                media.get("href")
            )

            image = valid_image_url(
                url
            )

            if image:
                return image


    # --------------------------------------------------------
    # enclosure
    # --------------------------------------------------------

    enclosures = entry.get(
        "enclosures",
        []
    )

    if enclosures:

        for enclosure in enclosures:

            if not isinstance(
                enclosure,
                dict
            ):
                continue

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

            if (
                "image" in mime
                or
                not mime
            ):

                image = valid_image_url(
                    url
                )

                if image:
                    return image


    # --------------------------------------------------------
    # entry.links
    # --------------------------------------------------------

    links = entry.get(
        "links",
        []
    )

    for item in links:

        if not isinstance(
            item,
            dict
        ):
            continue

        rel = str(
            item.get(
                "rel",
                ""
            )
        ).lower()

        mime = str(
            item.get(
                "type",
                ""
            )
        ).lower()

        href = item.get(
            "href"
        )

        if (
            rel == "enclosure"
            and
            "image" in mime
        ):

            image = valid_image_url(
                href
            )

            if image:
                return image


    # --------------------------------------------------------
    # entry.image
    # --------------------------------------------------------

    image_data = entry.get(
        "image"
    )

    if isinstance(
        image_data,
        dict
    ):

        image = valid_image_url(

            image_data.get(
                "href"
            )
            or
            image_data.get(
                "url"
            )

        )

        if image:
            return image


    return ""


# ============================================================
# EXTRACT OG IMAGE FROM ARTICLE PAGE
# ============================================================

def extract_page_image(link):

    if not link:
        return ""

    try:

        response = SESSION.get(

            link,

            timeout=15,

            allow_redirects=True

        )

        if response.status_code != 200:

            return ""

        content_type = str(
            response.headers.get(
                "content-type",
                ""
            )
        ).lower()

        if (
            "text/html"
            not in content_type
        ):

            return ""

        page = response.text

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

                image = html.unescape(
                    match.group(1)
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
            "Image page error:",
            error
        )


    return ""


# ============================================================
# GET BEST AVAILABLE IMAGE
# ============================================================

def get_article_image(
    entry,
    link
):

    # First try RSS.

    image = extract_rss_image(
        entry
    )

    if image:

        print(
            "Image found in RSS:"
        )

        print(
            image
        )

        return image


    # If RSS has no image,
    # try the original article.

    print(
        "No RSS image. Checking article page..."
    )

    image = extract_page_image(
        link
    )

    if image:

        print(
            "Image found on article page:"
        )

        print(
            image
        )

        return image


    print(
        "No image found."
    )

    return ""


# ============================================================
# READ RSS
# ============================================================

def get_news():

    articles = []


    for source_name, feed_url in RSS_FEEDS:

        print("")
        print(
            "Reading:",
            source_name
        )


        try:

            feed = feedparser.parse(
                feed_url
            )


            for entry in feed.entries[:20]:

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


                # Some RSS feeds use content.

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


                # ------------------------------------------------
                # IMAGE
                # ------------------------------------------------

                image = get_article_image(
                    entry,
                    link
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

                    "image":
                        image

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


    if (
        summary_clean.lower()
        ==
        title_clean.lower()
    ):

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
    source
):

    if not description:

        description = (

            "لا يوجد وصف إضافي متاح "
            "من مصدر RSS. "
            "اعتمد على العنوان فقط "
            "ولا تخترع تفاصيل."

        )


    prompt = f"""

أنت محرر الأخبار الرئيسي في منصة NOWNEX العربية.

مهمتك هي كتابة نسخة عربية أصلية ومختصرة من الخبر
الموجود في البيانات أدناه.

المصدر:
{source}

العنوان الأصلي:
{title}

النص أو الوصف المتاح:
{description}

أعد النتيجة بصيغة JSON فقط:

{{
  "title": "عنوان عربي احترافي",
  "summary": "ملخص عربي من 3 إلى 5 جمل",
  "importance": "شرح مختصر جداً من جملتين يوضح لماذا الخبر مهم",
  "category": "World"
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

قواعد صارمة:

- استخدم العربية الفصحى.
- لا تكرر العنوان داخل الملخص.
- الملخص يجب أن يكون مختلفاً عن العنوان.
- الملخص من 3 إلى 5 جمل.
- importance من جملتين فقط.
- اشرح ما حدث بناءً على المعلومات المتاحة فقط.
- لا تخترع أسماء.
- لا تخترع أرقاماً.
- لا تخترع تصريحات.
- لا تخترع أحداثاً.
- لا تضف رأياً شخصياً.
- إذا كانت المعلومات ناقصة، استخدم المعلومات المؤكدة فقط.
- لا تستخدم Markdown.
- أرسل JSON صالحاً فقط.
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
                0.3,

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
                    response.text[:3000]
                )

                raise RuntimeError(
                    f"Gemini HTTP "
                    f"{response.status_code}"
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


            # Remove accidental markdown.

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


            new_importance = clean_text(

                result.get(
                    "importance",
                    ""
                )

            )


            new_category = result.get(

                "category",

                "World"

            )


            if not new_title:

                raise RuntimeError(
                    "Gemini returned "
                    "an empty title."
                )


            if not summary_is_valid(

                title,

                new_summary

            ):

                raise RuntimeError(

                    "Gemini returned "
                    "an invalid summary."

                )


            if new_category not in VALID_CATEGORIES:

                new_category = "World"


            if not new_importance:

                new_importance = (

                    "يقدم NOWNEX هذا الخبر "
                    "في صورة مختصرة باللغة العربية. "
                    "يمكن الرجوع إلى المصدر الأصلي "
                    "لمزيد من التفاصيل."

                )


            return {

                "title":
                    new_title,

                "summary":
                    new_summary,

                "importance":
                    new_importance,

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
        f"{last_error}"

    )


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

        raise RuntimeError(
            "No news articles found."
        )


    print("")
    print(
        "Found:",
        len(articles),
        "articles"
    )


    articles = articles[:MAX_NEWS]


    final_news = []


    for index, article in enumerate(

        articles,

        start=1

    ):

        print("")
        print(
            f"Processing "
            f"{index}/{len(articles)}"
        )


        print(
            "Original:",
            article["title"]
        )


        try:

            ai = ask_gemini(

                article["title"],

                article["description"],

                article["source"]

            )


            item = {

                "title":
                    ai["title"],

                "summary":
                    ai["summary"],

                "description":
                    ai["summary"],

                "importance":
                    ai["importance"],

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


            print(
                "Image:",
                article.get(
                    "image",
                    "NONE"
                )
            )


        except Exception as error:

            print(
                "✗ Article rejected:",
                error
            )


        time.sleep(2)


    if not final_news:

        raise RuntimeError(

            "Gemini did not successfully "
            "create any Arabic articles."

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
        f" Articles: "
        f"{len(final_news)}"
    )
    print("==============================")
    print("")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
