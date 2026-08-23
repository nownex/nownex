import os
import json
import re
import html
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
import feedparser


# ============================================================
# NOWNEX — NEWS ENGINE
#
# Arabic-first
# Latest 3 per category
# Strong image extraction
# Duplicate protection
# Gemini Arabic rewriting
# Safe news.json replacement
# ============================================================


# ============================================================
# GEMINI API
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


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

ENTRIES_PER_FEED = 15

REQUEST_TIMEOUT = 25

GEMINI_TIMEOUT = 90

REQUEST_DELAY = 2

GEMINI_RETRIES = 3


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
# تستخدم فقط إذا لم نجد صورة حقيقية للمقال.
#
# عدل المسار إذا كانت صورك الاحتياطية موجودة
# في مجلد مختلف داخل GitHub Pages.
# ============================================================

FALLBACK_IMAGES = {

    "AI":
        "ai.png",

    "Technology":
        "technology.png",

    "Cars":
        "cars.png",

    "Entertainment":
        "entertainment.png",

    "World":
        "world.png",

    "Facts":
        "facts.png",

    "Products":
        "products.png"

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
        "Mozilla/5.0 (compatible; NOWNEX-NewsBot/4.0)",

    "Accept":
        "application/rss+xml, application/xml, "
        "text/xml, text/html, */*"

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
# NORMALIZE URL
# ============================================================

def normalize_url(url):

    url = str(
        url or ""
    ).strip()

    if not url:
        return ""

    try:

        parsed = urlparse(
            url
        )

        # إزالة fragment
        clean = parsed._replace(
            fragment=""
        ).geturl()

        return clean.rstrip("/")

    except Exception:

        return url.rstrip("/")


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


    # منع روابط واضحة ليست صوراً
    bad_extensions = (
        ".svg",
        ".ico"
    )

    path = urlparse(
        url
    ).path.lower()


    if path.endswith(
        bad_extensions
    ):

        return ""


    return url


# ============================================================
# IMAGE FROM RSS
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


            mime = str(
                enclosure.get(
                    "type",
                    ""
                )
            ).lower()


            url = (
                enclosure.get("href")
                or
                enclosure.get("url")
            )


            url = valid_image_url(
                url
            )


            if url and (

                "image" in mime
                or
                re.search(
                    r"\.(jpg|jpeg|png|webp|gif)(\?|$)",
                    url,
                    re.IGNORECASE
                )

            ):

                return url


    # --------------------------------------------------------
    # HTML inside RSS description
    # --------------------------------------------------------

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


    content = entry.get(
        "content",
        []
    )


    if isinstance(
        content,
        list
    ):

        for item in content:

            if isinstance(
                item,
                dict
            ):

                sources.append(
                    item.get(
                        "value",
                        ""
                    )
                )


    for source in sources:

        source = str(
            source or ""
        )


        patterns = [

            r'<img[^>]+src=["\']([^"\']+)["\']',

            r'<img[^>]+data-src=["\']([^"\']+)["\']',

            r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']',

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
# META TAG IMAGE
# ============================================================

def get_meta_image(
    page,
    response_url
):

    # نبحث عن كل meta tag ثم نقرأ property/name/content
    # بغض النظر عن ترتيب attributes.
    meta_tags = re.findall(
        r"<meta\b[^>]*>",
        page,
        re.IGNORECASE
    )


    wanted = {

        "og:image",
        "og:image:url",
        "twitter:image",
        "twitter:image:src"

    }


    for tag in meta_tags:

        property_match = re.search(
            r'(?:property|name)\s*=\s*["\']([^"\']+)["\']',
            tag,
            re.IGNORECASE
        )


        content_match = re.search(
            r'content\s*=\s*["\']([^"\']+)["\']',
            tag,
            re.IGNORECASE
        )


        if not property_match:
            continue


        if not content_match:
            continue


        key = property_match.group(
            1
        ).strip().lower()


        if key not in wanted:
            continue


        image = html.unescape(
            content_match.group(
                1
            ).strip()
        )


        image = urljoin(
            response_url,
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
    response_url
):

    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>'
        r'(.*?)'
        r'</script>',
        page,
        re.IGNORECASE | re.DOTALL
    )


    for raw in scripts:

        raw = html.unescape(
            raw.strip()
        )


        # محاولة مباشرة
        try:

            data = json.loads(
                raw
            )

        except Exception:

            continue


        candidates = []


        def collect_images(obj):

            if isinstance(
                obj,
                dict
            ):

                image = obj.get(
                    "image"
                )


                if image:

                    candidates.append(
                        image
                    )


                graph = obj.get(
                    "@graph"
                )


                if graph:

                    collect_images(
                        graph
                    )


                for value in obj.values():

                    if isinstance(
                        value,
                        (dict, list)
                    ):

                        collect_images(
                            value
                        )


            elif isinstance(
                obj,
                list
            ):

                for item in obj:

                    collect_images(
                        item
                    )


        collect_images(
            data
        )


        for candidate in candidates:

            if isinstance(
                candidate,
                str
            ):

                image = candidate


            elif isinstance(
                candidate,
                dict
            ):

                image = (
                    candidate.get("url")
                    or
                    candidate.get("contentUrl")
                )


            elif isinstance(
                candidate,
                list
            ):

                image = (
                    candidate[0]
                    if candidate
                    else ""
                )


            else:

                image = ""


            image = urljoin(
                response_url,
                str(image or "")
            )


            image = valid_image_url(
                image
            )


            if image:

                return image


    return ""


# ============================================================
# HTML IMAGE
# ============================================================

def get_html_image(
    url
):

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
        # JSON-LD
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
        # OpenGraph / Twitter
        # ----------------------------------------------------

        image = get_meta_image(
            page,
            response.url
        )


        if image:

            print(
                "    Image: OG/Twitter"
            )

            return image


        # ----------------------------------------------------
        # Featured / Hero images
        # ----------------------------------------------------

        patterns = [

            r'<img[^>]+class=["\'][^"\']*'
            r'(?:featured|hero|article|thumbnail|'
            r'cover|main-image)[^"\']*["\'][^>]+'
            r'(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']',

            r'<img[^>]+(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']'
            r'[^>]+class=["\'][^"\']*'
            r'(?:featured|hero|article|thumbnail|cover|main-image)'
            r'[^"\']*["\']',

            r'<img[^>]+data-src=["\']([^"\']+)["\']',

            r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']',

            r'<img[^>]+src=["\']([^"\']+)["\']'

        ]


        for pattern in patterns:

            matches = re.findall(
                pattern,
                page,
                re.IGNORECASE
            )


            for image in matches:

                if not image:
                    continue


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


                if not image:
                    continue


                # منع الصور الصغيرة الواضحة
                lower = image.lower()


                if any(
                    x in lower
                    for x in [
                        "avatar",
                        "favicon",
                        "logo",
                        "icon",
                        "sprite"
                    ]
                ):

                    continue


                print(
                    "    Image: HTML"
                )


                return image


    except Exception as error:

        print(
            "    HTML image error:",
            str(error)[:200]
        )


    return ""


# ============================================================
# BEST IMAGE
# ============================================================

def get_best_image(
    entry,
    link
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
    # 2. Page
    # --------------------------------------------------------

    image = get_html_image(
        link
    )


    if image:

        return image


    return ""


# ============================================================
# FALLBACK IMAGE
# ============================================================

def get_fallback_image(
    category
):

    return FALLBACK_IMAGES.get(
        category,
        ""
    )


# ============================================================
# PARSE DATE
# ============================================================

def parse_published_date(
    entry
):

    # --------------------------------------------------------
    # feedparser parsed time
    # --------------------------------------------------------

    for field in [
        "published_parsed",
        "updated_parsed",
        "created_parsed"
    ]:

        value = entry.get(
            field
        )


        if value:

            try:

                return datetime(
                    value.tm_year,
                    value.tm_mon,
                    value.tm_mday,
                    value.tm_hour,
                    value.tm_min,
                    value.tm_sec,
                    tzinfo=timezone.utc
                )

            except Exception:

                pass


    # --------------------------------------------------------
    # Raw date
    # --------------------------------------------------------

    raw = (

        entry.get(
            "published"
        )
        or
        entry.get(
            "updated"
        )
        or
        entry.get(
            "created"
        )
        or
        ""

    )


    raw = str(
        raw
    ).strip()


    if raw:

        try:

            parsed = feedparser._parse_date(
                raw
            )


            if parsed:

                return datetime(
                    parsed.tm_year,
                    parsed.tm_mon,
                    parsed.tm_mday,
                    parsed.tm_hour,
                    parsed.tm_min,
                    parsed.tm_sec,
                    tzinfo=timezone.utc
                )

        except Exception:

            pass


    return datetime(
        1970,
        1,
        1,
        tzinfo=timezone.utc
    )


# ============================================================
# DATE TO ISO
# ============================================================

def date_to_iso(
    value
):

    if not value:

        return ""


    try:

        return value.astimezone(
            timezone.utc
        ).isoformat()

    except Exception:

        return ""


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(
    items
):

    result = []

    seen_urls = set()
    seen_titles = set()


    for item in items:

        url = normalize_url(
            item.get(
                "link",
                ""
            )
        )


        title = normalize_title(
            item.get(
                "title",
                ""
            )
        )


        if not url and not title:

            continue


        if url and url in seen_urls:

            continue


        if title and title in seen_titles:

            continue


        if url:

            seen_urls.add(
                url
            )


        if title:

            seen_titles.add(
                title
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


                published_date = parse_published_date(
                    entry
                )


                published_iso = date_to_iso(
                    published_date
                )


                print(
                    "  News:",
                    title[:100]
                )


                # ------------------------------------------------
                # IMAGE
                # ------------------------------------------------

                image = get_best_image(
                    entry,
                    link
                )


                if not image:

                    image = get_fallback_image(
                        category
                    )


                    if image:

                        print(
                            "    Image: FALLBACK"
                        )

                    else:

                        print(
                            "    Image: NONE"
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
                        published_iso,

                    "_published_date":
                        published_date

                })


        except Exception as error:

            print(
                "RSS ERROR:",
                source_name,
                str(error)[:300]
            )


    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    articles = remove_duplicates(
        articles
    )


    # --------------------------------------------------------
    # SORT BY REAL PUBLICATION DATE
    # الأحدث أولاً
    # --------------------------------------------------------

    articles.sort(

        key=lambda item:
            item.get(
                "_published_date",
                datetime(
                    1970,
                    1,
                    1,
                    tzinfo=timezone.utc
                )
            ),

        reverse=True

    )


    print("")
    print(
        "TOTAL UNIQUE ARTICLES:",
        len(articles)
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
            "استخدم المعلومات الموجودة في العنوان فقط "
            "ولا تضف أي معلومات غير مؤكدة."
        )


    prompt = f"""
أنت محرر الأخبار الرئيسي في NOWNEX.

حوّل الخبر التالي إلى نسخة عربية احترافية.

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

القواعد الصارمة:

1. استخدم العربية الفصحى الحديثة.
2. لا تخترع أي معلومة.
3. لا تخترع أسماء.
4. لا تخترع أرقاماً.
5. لا تخترع تصريحات أو اقتباسات.
6. لا تضف رأياً شخصياً.
7. لا تضف معلومات من خارج النص.
8. يجب أن يكون الملخص من 3 إلى 5 جمل.
9. يجب أن يكون العنوان واضحاً ومهنياً.
10. حافظ على المعنى الأصلي.
11. إذا كان هناك اسم شركة أو منتج أو شخص مهم، لا تغيّره.
12. أعد JSON صالحاً فقط.
13. لا تستخدم Markdown.
"""


    payload = {

        "contents": [

            {

                "role": "user",

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
                f"    Gemini request "
                f"{attempt}/{GEMINI_RETRIES}"
            )


            response = requests.post(

                GEMINI_URL,

                headers=headers,

                json=payload,

                timeout=GEMINI_TIMEOUT

            )


            print(
                "    Gemini status:",
                response.status_code
            )


            # ------------------------------------------------
            # RATE LIMIT
            # ------------------------------------------------

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
                    "    Rate limit. Waiting:",
                    wait_time,
                    "seconds"
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
                    "    Gemini error:",
                    response.text[:1000]
                )


                if attempt < GEMINI_RETRIES:

                    time.sleep(
                        10
                    )


                continue


            data = response.json()


            candidates = data.get(
                "candidates",
                []
            )


            if not candidates:

                print(
                    "    No Gemini candidates."
                )

                continue


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


            text = text.strip()


            # ------------------------------------------------
            # Remove accidental Markdown
            # ------------------------------------------------

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

                print(
                    "    Invalid title."
                )

                continue


            if not summary_is_valid(

                title_ar,
                summary_ar

            ):

                print(
                    "    Invalid Arabic summary."
                )

                continue


            return {

                "title_ar":
                    title_ar,

                "summary_ar":
                    summary_ar

            }


        except Exception as error:

            print(
                "    Gemini exception:",
                str(error)[:500]
            )


            if attempt < GEMINI_RETRIES:

                time.sleep(
                    10
                )


    return None


# ============================================================
# CATEGORY ARTICLES
# ============================================================

def get_category_articles(
    articles,
    category
):

    result = [

        article

        for article in articles

        if article.get(
            "category"
        ) == category

    ]


    result.sort(

        key=lambda item:
            item.get(
                "_published_date",
                datetime(
                    1970,
                    1,
                    1,
                    tzinfo=timezone.utc
                )
            ),

        reverse=True

    )


    return result


# ============================================================
# CREATE NEWS ITEM
# ============================================================

def create_news_item(
    article,
    ai
):

    return {

        "title_ar":
            ai["title_ar"],

        "summary_ar":
            ai["summary_ar"],

        # Compatibility
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
# GENERATE CATEGORY
#
# مهم:
# إذا فشل Gemini في أول خبر، ننتقل للخبر التالي.
# الهدف النهائي 3 أخبار صحيحة لكل قسم.
# ============================================================

def generate_category_news(
    candidates,
    category,
    target=3
):

    result = []

    used = set()


    for article in candidates:

        if len(result) >= target:

            break


        key = (
            normalize_url(
                article.get(
                    "link",
                    ""
                )
            )
            or
            normalize_title(
                article.get(
                    "title",
                    ""
                )
            )
        )


        if key in used:

            continue


        used.add(
            key
        )


        print("")
        print(
            "------------------------------------------"
        )


        print(
            f"Processing {category}:",
            article.get(
                "title",
                ""
            )
        )


        print(
            "Source:",
            article.get(
                "source",
                ""
            )
        )


        print(
            "Published:",
            article.get(
                "published",
                ""
            )
        )


        if article.get(
            "image"
        ):

            print(
                "Image: YES"
            )

        else:

            print(
                "Image: NO"
            )


        ai = ask_gemini(

            article.get(
                "title",
                ""
            ),

            article.get(
                "description",
                ""
            ),

            article.get(
                "source",
                ""
            ),

            category

        )


        if not ai:

            print(
                "SKIPPED — Gemini failed"
            )

            continue


        item = create_news_item(
            article,
            ai
        )


        result.append(
            item
        )


        print(
            "CREATED ✓"
        )


        time.sleep(
            REQUEST_DELAY
        )


    return result


# ============================================================
# TRENDING
# ============================================================

def create_trending(
    final_news
):

    trending = []

    seen = set()


    # نأخذ خبرًا أو خبرين من كل قسم
    # حتى يكون Trending متنوعاً.

    for category in MAIN_CATEGORIES:

        category_news = [

            item

            for item in final_news

            if item.get(
                "category"
            ) == category

        ]


        for item in category_news[:2]:

            key = (

                normalize_url(
                    item.get(
                        "link",
                        ""
                    )
                )

                or

                normalize_title(
                    item.get(
                        "title_ar",
                        ""
                    )
                )

            )


            if not key:

                continue


            if key in seen:

                continue


            copy_item = dict(
                item
            )


            # مهم:
            # نحتفظ بالقسم الأصلي.
            #
            # لا نغير category إلى Trending
            # حتى لا تضيع معلومات القسم.

            copy_item[
                "isTrending"
            ] = True


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
        " NOWNEX NEWS ENGINE v4"
    )

    print(
        " Latest + Arabic + Strong Images"
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


    # ========================================================
    # AVAILABLE
    # ========================================================

    print("")
    print(
        "=========================================="
    )

    print(
        "AVAILABLE BY CATEGORY"
    )

    print(
        "=========================================="
    )


    for category in MAIN_CATEGORIES:

        candidates = get_category_articles(

            articles,
            category

        )


        print(
            f"{category}: "
            f"{len(candidates)}"
        )


    # ========================================================
    # GENERATE
    # ========================================================

    final_news = []


    # --------------------------------------------------------
    # المرحلة الأولى:
    # ضمان 3 أخبار لكل قسم
    # --------------------------------------------------------

    for category in MAIN_CATEGORIES:

        print("")
        print(
            "=========================================="
        )


        print(
            f"GENERATING CATEGORY: {category}"
        )


        candidates = get_category_articles(

            articles,
            category

        )


        category_news = generate_category_news(

            candidates,

            category,

            MIN_PER_CATEGORY

        )


        print("")
        print(
            f"{category} GENERATED:",
            len(category_news),
            "/",
            MIN_PER_CATEGORY
        )


        final_news.extend(
            category_news
        )


    # ========================================================
    # SAFETY CHECK
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
    # NEVER DESTROY EXISTING NEWS
    # ========================================================

    if missing_categories:

        print("")
        print(
            "=========================================="
        )

        print(
            "WARNING — UPDATE CANCELLED"
        )

        print(
            "=========================================="
        )


        print(
            "Some categories have fewer than 3 valid articles:"
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
    # SORT FINAL NEWS
    #
    # ترتيب الأقسام لا يتغير.
    # داخل الناتج نرتب حسب publishedAt الخاص بالمصدر
    # قدر الإمكان.
    # ========================================================

    # لا نستخدم publishedAt هنا لأنه وقت المعالجة.
    # نحافظ على ترتيب 3 أخبار لكل قسم.


    # ========================================================
    # MAX NEWS
    # ========================================================

    final_news = final_news[
        :MAX_NEWS
    ]


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
    # TEMP FILE
    #
    # نكتب أولاً إلى ملف مؤقت.
    # إذا حدث خطأ أثناء الكتابة لا نخرب news.json.
    # ========================================================

    temp_file = "news.json.tmp"

    final_file = "news.json"


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


    # --------------------------------------------------------
    # استبدال آمن
    # --------------------------------------------------------

    os.replace(
        temp_file,
        final_file
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


    print("")
    print(
        "FINAL CATEGORY COUNTS:"
    )


    for category in MAIN_CATEGORIES:

        print(
            f"  {category}: "
            f"{category_counts[category]}"
        )


    # ========================================================
    # IMAGE REPORT
    # ========================================================

    real_images = 0
    fallback_images = 0
    no_images = 0


    for item in final_news:

        image = str(
            item.get(
                "image",
                ""
            )
        )


        if not image:

            no_images += 1

            continue


        filename = image.split(
            "/"
        )[-1].lower()


        fallback_names = [

            value.lower()

            for value in FALLBACK_IMAGES.values()

        ]


        if filename in fallback_names:

            fallback_images += 1

        else:

            real_images += 1


    print("")
    print(
        "IMAGE REPORT"
    )


    print(
        "Real images:",
        real_images
    )


    print(
        "Fallback images:",
        fallback_images
    )


    print(
        "No images:",
        no_images
    )


    print("")
    print(
        "news.json saved successfully."
    )


    print(
        "=========================================="
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
