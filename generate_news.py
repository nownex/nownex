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
# NOWNEX — NEWS ENGINE
# Arabic-first + Strong Image Extraction
# + Fallback Images
# + Better RSS / OG / JSON-LD extraction
# ============================================================


API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


# ============================================================
# GEMINI
# ============================================================

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

ENTRIES_PER_FEED = 12

REQUEST_TIMEOUT = 25

GEMINI_TIMEOUT = 90

REQUEST_DELAY = 3

IMAGE_TIMEOUT = 20


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
# FALLBACK IMAGES
#
# إذا لم نجد صورة حقيقية للخبر، نستخدم صورة القسم.
# يجب أن تكون هذه الصور موجودة داخل مشروع GitHub.
# ============================================================

FALLBACK_IMAGES = {

    "AI":
        "https://nownex.github.io/nownex/ai.png",

    "Technology":
        "https://nownex.github.io/nownex/technology.png",

    "Cars":
        "https://nownex.github.io/nownex/cars.png",

    "Entertainment":
        "https://nownex.github.io/nownex/entertainment.png",

    "World":
        "https://nownex.github.io/nownex/world.png",

    "Facts":
        "https://nownex.github.io/nownex/facts.png",

    "Products":
        "https://nownex.github.io/nownex/products.png",

    "Other":
        "https://nownex.github.io/nownex/technology.png"
}


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
        "MIT Technology Review AI",
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
    # FACTS
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
        "Mozilla/5.0 (compatible; NOWNEX-NewsBot/4.0)",

    "Accept":
        "application/rss+xml, application/xml, text/xml, "
        "text/html, application/xhtml+xml"

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

    url = url.replace(
        "&amp;",
        "&"
    )

    return url


# ============================================================
# IMAGE URL CHECK
#
# نتأكد أن الرابط يرجع صورة فعلية.
# ============================================================

def image_url_works(url):

    url = valid_image_url(url)

    if not url:
        return False

    try:

        response = SESSION.head(
            url,
            timeout=IMAGE_TIMEOUT,
            allow_redirects=True
        )

        content_type = str(
            response.headers.get(
                "Content-Type",
                ""
            )
        ).lower()

        if response.status_code < 400:

            if (
                "image/" in content_type
                or
                re.search(
                    r"\.(jpg|jpeg|png|webp|gif|avif)(\?|$)",
                    url,
                    re.IGNORECASE
                )
            ):
                return True

    except Exception:
        pass

    # بعض المواقع تمنع HEAD
    try:

        response = SESSION.get(
            url,
            timeout=IMAGE_TIMEOUT,
            allow_redirects=True,
            stream=True
        )

        content_type = str(
            response.headers.get(
                "Content-Type",
                ""
            )
        ).lower()

        response.close()

        if response.status_code < 400 and (
            "image/" in content_type
            or
            re.search(
                r"\.(jpg|jpeg|png|webp|gif|avif)(\?|$)",
                url,
                re.IGNORECASE
            )
        ):
            return True

    except Exception:
        pass

    return False


# ============================================================
# RSS IMAGE
# ============================================================

def extract_rss_image(entry):

    # --------------------------------------------------------
    # media_content
    # --------------------------------------------------------

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

            url = (
                media.get("url")
                or
                media.get("href")
                or
                media.get("src")
            )

            url = valid_image_url(
                url
            )

            if url:
                return url


    # --------------------------------------------------------
    # media_thumbnail
    # --------------------------------------------------------

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

            url = (
                media.get("url")
                or
                media.get("href")
                or
                media.get("src")
            )

            url = valid_image_url(
                url
            )

            if url:
                return url


    # --------------------------------------------------------
    # enclosure
    # --------------------------------------------------------

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

            url = (
                enclosure.get("href")
                or
                enclosure.get("url")
            )

            url = valid_image_url(
                url
            )

            if url:
                return url


    # --------------------------------------------------------
    # image داخل HTML
    # --------------------------------------------------------

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

            r'<img[^>]+data-original=["\']([^"\']+)["\']',

            r'<source[^>]+srcset=["\']([^"\']+)["\']'

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
# EXTRACT META IMAGE
# ============================================================

def extract_meta_image(
    page,
    base_url
):

    patterns = [

        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        r'<meta[^>]+property=["\']og:image:url["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image:url["\']',

        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',

        r'<meta[^>]+name=["\']twitter:image:src["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image:src["\']'

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
            base_url,
            image
        )

        image = valid_image_url(
            image
        )

        if image:
            return image


    return ""


# ============================================================
# JSON-LD IMAGE
# ============================================================

def extract_jsonld_image(
    page,
    base_url
):

    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page,
        re.IGNORECASE | re.DOTALL
    )


    for script in scripts:

        script = html.unescape(
            script.strip()
        )

        try:

            data = json.loads(
                script
            )

        except Exception:
            continue


        objects = []

        if isinstance(
            data,
            dict
        ):

            objects.append(
                data
            )

            graph = data.get(
                "@graph"
            )

            if isinstance(
                graph,
                list
            ):

                objects.extend(
                    graph
                )

        elif isinstance(
            data,
            list
        ):

            objects.extend(
                data
            )


        for obj in objects:

            if not isinstance(
                obj,
                dict
            ):
                continue


            image = obj.get(
                "image"
            )


            if isinstance(
                image,
                str
            ):

                image = valid_image_url(
                    urljoin(
                        base_url,
                        image
                    )
                )

                if image:
                    return image


            if isinstance(
                image,
                dict
            ):

                image_url = (
                    image.get("url")
                    or
                    image.get("contentUrl")
                )

                image_url = valid_image_url(
                    urljoin(
                        base_url,
                        str(
                            image_url or ""
                        )
                    )
                )

                if image_url:
                    return image_url


            if isinstance(
                image,
                list
            ):

                for image_item in image:

                    if isinstance(
                        image_item,
                        str
                    ):

                        image_url = valid_image_url(
                            urljoin(
                                base_url,
                                image_item
                            )
                        )

                        if image_url:
                            return image_url

                    elif isinstance(
                        image_item,
                        dict
                    ):

                        image_url = (
                            image_item.get("url")
                            or
                            image_item.get("contentUrl")
                        )

                        image_url = valid_image_url(
                            urljoin(
                                base_url,
                                str(
                                    image_url or ""
                                )
                            )
                        )

                        if image_url:
                            return image_url


    return ""


# ============================================================
# HTML IMAGE
# ============================================================

def get_html_image(url):

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
            :1500000
        ]


        # ----------------------------------------------------
        # 1. OpenGraph
        # ----------------------------------------------------

        image = extract_meta_image(
            page,
            response.url
        )

        if image:

            print(
                "    Image: OG"
            )

            return image


        # ----------------------------------------------------
        # 2. JSON-LD
        # ----------------------------------------------------

        image = extract_jsonld_image(
            page,
            response.url
        )

        if image:

            print(
                "    Image: JSON-LD"
            )

            return image


        # ----------------------------------------------------
        # 3. Featured / hero / article images
        # ----------------------------------------------------

        patterns = [

            r'<img[^>]+class=["\'][^"\']*(?:featured|hero|article|thumbnail|main-image|post-image)[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',

            r'<img[^>]+src=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*(?:featured|hero|article|thumbnail|main-image|post-image)[^"\']*["\']',

            r'<img[^>]+data-src=["\']([^"\']+)["\']',

            r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']',

            r'<img[^>]+data-original=["\']([^"\']+)["\']',

            r'<img[^>]+src=["\']([^"\']+)["\']'

        ]


        for pattern in patterns:

            match = re.search(
                pattern,
                page,
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
            "HTML image error:",
            str(error)[:300]
        )


    return ""


# ============================================================
# BEST IMAGE
# ============================================================

def get_best_image(
    entry,
    link,
    category
):

    # --------------------------------------------------------
    # 1. RSS
    # --------------------------------------------------------

    image = extract_rss_image(
        entry
    )

    if image:

        print(
            "    Image: RSS"
        )

        return image


    # --------------------------------------------------------
    # 2. HTML / OG / JSON-LD
    # --------------------------------------------------------

    image = get_html_image(
        link
    )

    if image:

        return image


    # --------------------------------------------------------
    # 3. FALLBACK
    # --------------------------------------------------------

    fallback = FALLBACK_IMAGES.get(
        category,
        FALLBACK_IMAGES["Other"]
    )


    print(
        f"    Image: FALLBACK ({category})"
    )


    return fallback


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(
    items
):

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


                # --------------------------------------------
                # IMAGE
                # --------------------------------------------

                image = get_best_image(
                    entry,
                    link,
                    category
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
                "RSS ERROR:",
                source_name,
                str(error)[:300]
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

أنشئ نسخة عربية احترافية من الخبر التالي.

المصدر:
{source}

القسم:
{category}

العنوان الأصلي:
{title}

المعلومات المتاحة:
{description}

أعد JSON فقط:

{{
  "title_ar": "عنوان عربي احترافي",
  "summary_ar": "ملخص عربي من 3 إلى 5 جمل"
}}

القواعد:

1. استخدم العربية الفصحى الحديثة.
2. لا تخترع أي معلومة.
3. لا تخترع أسماء.
4. لا تخترع أرقاماً.
5. لا تخترع تصريحات أو اقتباسات.
6. لا تضف رأياً شخصياً.
7. استخدم المعلومات المتاحة فقط.
8. يجب أن يكون الملخص من 3 إلى 5 جمل.
9. يجب أن يكون العنوان واضحاً ومهنياً.
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
                    20
                    if attempt == 1
                    else
                    40
                    if attempt == 2
                    else
                    60
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
# SELECT NEWS
# ============================================================

def select_news(
    articles
):

    selected = []

    selected_keys = set()


    # --------------------------------------------------------
    # 3 أخبار لكل قسم
    # --------------------------------------------------------

    for category in MAIN_CATEGORIES:

        candidates = get_category_articles(

            articles,
            category

        )


        count = 0


        for article in candidates:

            key = normalize_title(

                article.get(
                    "title",
                    ""
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


            if count >= MIN_PER_CATEGORY:
                break


    # --------------------------------------------------------
    # أخبار إضافية حتى 30
    # --------------------------------------------------------

    for article in articles:

        if len(selected) >= MAX_NEWS:
            break


        key = normalize_title(

            article.get(
                "title",
                ""
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
        "=========================================="
    )

    print(
        " NOWNEX NEWS ENGINE"
    )

    print(
        " Arabic + Strong Images + Fallback"
    )

    print(
        "=========================================="
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


    # ========================================================
    # GET RSS
    # ========================================================

    articles = get_news()


    if not articles:

        raise RuntimeError(
            "No RSS articles found."
        )


    print("")
    print(
        "TOTAL COLLECTED:",
        len(articles)
    )


    # ========================================================
    # REPORT RSS
    # ========================================================

    print("")
    print(
        "AVAILABLE BY CATEGORY:"
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
    # SELECT
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
    # GENERATE
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
            "Title:",
            article["title"]
        )


        print(
            "Image:",
            article.get(
                "image",
                ""
            )
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


        image = article.get(
            "image",
            ""
        )


        # حماية أخيرة:
        # إذا اختفت الصورة لأي سبب،
        # نضع صورة القسم.

        if not image:

            image = FALLBACK_IMAGES.get(

                article["category"],

                FALLBACK_IMAGES["Other"]

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
                image,

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
            "CREATED ✓"
        )


        time.sleep(
            REQUEST_DELAY
        )


    # ========================================================
    # FINAL CATEGORY CHECK
    # ========================================================

    print("")
    print(
        "=========================================="
    )

    print(
        "FINAL CATEGORY CHECK"
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
            f"{category}: {count}/3"
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
    # لا نكتب news.json.
    #
    # هذا يحمي الموقع من التحديث الجزئي.
    # ========================================================

    if missing_categories:

        print("")
        print(
            "WARNING:"
        )


        print(
            "Some categories have fewer than 3 articles."
        )


        for category in missing_categories:

            print(
                f" - {category}: "
                f"{category_counts.get(category, 0)}/3"
            )


        print("")
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


    # ========================================================
    # SAVE
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
    # FINAL REPORT
    # ========================================================

    print("")
    print(
        "=========================================="
    )


    print(
        " NOWNEX NEWS UPDATED SUCCESSFULLY"
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
        "=========================================="
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


    images_count = len([

        item

        for item in final_news

        if item.get(
            "image"
        )

    ])


    print("")
    print(
        "Images:",
        f"{images_count}/{len(final_news)}"
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
