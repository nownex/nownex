import os
import json
import re
import html
import time
import calendar
from datetime import datetime, timezone
from urllib.parse import urljoin, quote_plus

import requests
import feedparser


# ============================================================
# NOWNEX NEWS ENGINE
# ============================================================
# Arabic-first
# Fresh news only
# Minimum 3 news per category
# No English fallback
# Better summaries
# Better images
# Reduced Gemini requests
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

# 7 categories × 3 news
MAX_NEWS = 21

MIN_PER_CATEGORY = 3

# لا نسمح بخبر أقدم من 48 ساعة
MAX_AGE_HOURS = 48

# عدد الأخبار التي نقرأها من كل RSS
ENTRIES_PER_FEED = 20

REQUEST_TIMEOUT = 12

GEMINI_TIMEOUT = 90

# الأخبار ترسل إلى Gemini على دفعات
GEMINI_BATCH_SIZE = 4

# انتظار بين دفعات Gemini
GEMINI_BATCH_DELAY = 5

# أقصى حجم تقريبي نفحصه للصورة
IMAGE_MAX_BYTES = 2_000_000


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
# GOOGLE NEWS HELPER
# ============================================================

def google_news_url(
    query,
    language="en",
    country="US"
):

    query = f"{query} when:2d"

    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}"
        f"&hl={language}"
        f"&gl={country}"
        f"&ceid={country}:{language}"
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
        "Google News AI Latest",
        google_news_url(
            "artificial intelligence AI",
            "en",
            "US"
        ),
        "AI"
    ),

    (
        "Google News AI Arabic Latest",
        google_news_url(
            "الذكاء الاصطناعي",
            "ar",
            "DZ"
        ),
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
        "Google News Technology Latest",
        google_news_url(
            "technology smartphones gadgets",
            "en",
            "US"
        ),
        "Technology"
    ),

    (
        "Google News Technology Arabic Latest",
        google_news_url(
            "تكنولوجيا هواتف أجهزة",
            "ar",
            "DZ"
        ),
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
        "Car and Driver",
        "https://www.caranddriver.com/rss/all.xml",
        "Cars"
    ),

    (
        "Google News Cars Latest",
        google_news_url(
            "cars automotive electric vehicles",
            "en",
            "US"
        ),
        "Cars"
    ),

    (
        "Google News Cars Arabic Latest",
        google_news_url(
            "سيارات سيارات كهربائية سيارات جديدة",
            "ar",
            "DZ"
        ),
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
        "Google News Entertainment Latest",
        google_news_url(
            "entertainment movies music games",
            "en",
            "US"
        ),
        "Entertainment"
    ),

    (
        "Google News Entertainment Arabic Latest",
        google_news_url(
            "ترفيه أفلام موسيقى ألعاب",
            "ar",
            "DZ"
        ),
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
        "Google News World Arabic Latest",
        google_news_url(
            "العالم أخبار الشرق الأوسط",
            "ar",
            "DZ"
        ),
        "World"
    ),

    (
        "Google News Middle East Arabic Latest",
        google_news_url(
            "الشرق الأوسط أخبار عاجلة",
            "ar",
            "DZ"
        ),
        "World"
    ),

    (
        "Google News World Latest",
        google_news_url(
            "world news",
            "en",
            "US"
        ),
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
        "Google News Science Latest",
        google_news_url(
            "science discovery space",
            "en",
            "US"
        ),
        "Facts"
    ),

    (
        "Google News Science Arabic Latest",
        google_news_url(
            "علم اكتشافات فضاء علوم",
            "ar",
            "DZ"
        ),
        "Facts"
    ),


    # ========================================================
    # PRODUCTS
    # ========================================================

    (
        "Google News Products Latest",
        google_news_url(
            "new products gadgets devices",
            "en",
            "US"
        ),
        "Products"
    ),

    (
        "Google News Gadgets Latest",
        google_news_url(
            "new gadgets smartphones devices",
            "en",
            "US"
        ),
        "Products"
    ),

    (
        "Google News Products Arabic Latest",
        google_news_url(
            "منتجات أجهزة هواتف منتجات جديدة",
            "ar",
            "DZ"
        ),
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
        "application/rss+xml, application/xml, "
        "text/xml, text/html, image/*"

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
# EXTRACT RSS IMAGE
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

            image = (
                media.get("url")
                or media.get("href")
                or media.get("src")
            )

            image = valid_image_url(
                image
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
                or media.get("href")
                or media.get("src")
            )

            image = valid_image_url(
                image
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
                or enclosure.get("url")
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


    # --------------------------------------------------------
    # HTML داخل RSS
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


    patterns = [

        r'<img[^>]+src=["\']([^"\']+)["\']',

        r'<img[^>]+data-src=["\']([^"\']+)["\']',

        r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']'

    ]


    for source in html_sources:

        source = str(
            source or ""
        )


        for pattern in patterns:

            matches = re.findall(
                pattern,
                source,
                re.IGNORECASE
            )


            for image in matches:

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
# EXTRACT IMAGE CANDIDATES FROM ARTICLE PAGE
# ============================================================

def extract_page_images(
    page,
    page_url
):

    candidates = []


    # --------------------------------------------------------
    # OG / Twitter
    # --------------------------------------------------------

    patterns = [

        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        r'<meta[^>]+property=["\']og:image:url["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image:url["\']',

        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',

        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']'

    ]


    for pattern in patterns:

        matches = re.findall(
            pattern,
            page,
            re.IGNORECASE
        )

        for image in matches:

            image = html.unescape(
                image.strip()
            )

            image = urljoin(
                page_url,
                image
            )

            image = valid_image_url(
                image
            )

            if image:
                candidates.append(
                    image
                )


    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    jsonld_matches = re.findall(

        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>'
        r'(.*?)'
        r'</script>',

        page,

        re.IGNORECASE |
        re.DOTALL

    )


    for raw_json in jsonld_matches:

        try:

            data = json.loads(
                raw_json
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


            # أحيانًا يكون داخل @graph
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


            image_data = obj.get(
                "image"
            )


            if isinstance(
                image_data,
                dict
            ):

                image_data = (

                    image_data.get(
                        "url"
                    )

                    or

                    image_data.get(
                        "contentUrl"
                    )

                )


            if isinstance(
                image_data,
                str
            ):

                image_data = [
                    image_data
                ]


            if not isinstance(
                image_data,
                list
            ):

                continue


            for image in image_data:

                if not isinstance(
                    image,
                    str
                ):
                    continue


                image = urljoin(
                    page_url,
                    image
                )


                image = valid_image_url(
                    image
                )


                if image:
                    candidates.append(
                        image
                    )


    # --------------------------------------------------------
    # إزالة التكرار
    # --------------------------------------------------------

    result = []

    seen = set()


    for image in candidates:

        if image in seen:
            continue

        seen.add(
            image
        )

        result.append(
            image
        )


    return result


# ============================================================
# IMAGE DIMENSIONS
# ============================================================

def get_image_dimensions(
    data
):

    # --------------------------------------------------------
    # PNG
    # --------------------------------------------------------

    if len(data) >= 24:

        if data.startswith(
            b"\x89PNG\r\n\x1a\n"
        ):

            width = int.from_bytes(
                data[16:20],
                "big"
            )

            height = int.from_bytes(
                data[20:24],
                "big"
            )

            return width, height


    # --------------------------------------------------------
    # GIF
    # --------------------------------------------------------

    if len(data) >= 10:

        if (
            data[:6] == b"GIF87a"
            or
            data[:6] == b"GIF89a"
        ):

            width = int.from_bytes(
                data[6:8],
                "little"
            )

            height = int.from_bytes(
                data[8:10],
                "little"
            )

            return width, height


    # --------------------------------------------------------
    # JPEG
    # --------------------------------------------------------

    if len(data) > 4:

        if data[0:2] == b"\xff\xd8":

            index = 2

            while index + 9 < len(data):

                if data[index] != 0xFF:

                    index += 1

                    continue


                marker = data[index + 1]

                index += 2


                # تجاهل markers غير المهمة

                if marker in (
                    0xD8,
                    0xD9
                ):

                    continue


                if index + 2 > len(data):
                    break


                segment_length = int.from_bytes(

                    data[index:index + 2],

                    "big"

                )


                if segment_length < 2:
                    break


                # SOF markers

                if (

                    marker >= 0xC0

                    and

                    marker <= 0xC3

                ) or (

                    marker >= 0xC5

                    and

                    marker <= 0xC7

                ) or (

                    marker >= 0xC9

                    and

                    marker <= 0xCB

                ) or (

                    marker >= 0xCD

                    and

                    marker <= 0xCF

                ):

                    if index + 7 > len(data):
                        break


                    height = int.from_bytes(

                        data[index + 3:index + 5],

                        "big"

                    )

                    width = int.from_bytes(

                        data[index + 5:index + 7],

                        "big"

                    )

                    return width, height


                index += segment_length


    # --------------------------------------------------------
    # WEBP
    # --------------------------------------------------------

    if len(data) >= 30:

        if (
            data[:4] == b"RIFF"
            and
            data[8:12] == b"WEBP"
        ):

            # VP8X
            if data[12:16] == b"VP8X":

                width = (

                    1
                    +
                    int.from_bytes(
                        data[24:27],
                        "little"
                    )

                )

                height = (

                    1
                    +
                    int.from_bytes(
                        data[27:30],
                        "little"
                    )

                )

                return width, height


    return None


# ============================================================
# INSPECT IMAGE QUALITY
# ============================================================

def inspect_image(
    image_url
):

    try:

        response = SESSION.get(

            image_url,

            timeout=REQUEST_TIMEOUT,

            stream=True,

            allow_redirects=True

        )


        if response.status_code != 200:

            return None


        content_type = (

            response.headers
            .get(
                "Content-Type",
                ""
            )
            .lower()

        )


        if "image" not in content_type:

            return None


        content_length = response.headers.get(
            "Content-Length"
        )


        try:

            content_length = int(
                content_length
                or 0
            )

        except Exception:

            content_length = 0


        # نقرأ جزءًا من الصورة فقط
        data = b""


        for chunk in response.iter_content(
            chunk_size=65536
        ):

            if not chunk:
                continue


            data += chunk


            if len(data) >= 512_000:
                break


        dimensions = get_image_dimensions(
            data
        )


        width = 0
        height = 0


        if dimensions:

            width, height = dimensions


        # ----------------------------------------------------
        # رفض الصور الصغيرة
        # ----------------------------------------------------

        if width and height:

            if width < 800:
                return None

            if height < 450:
                return None


            ratio = (
                width / height
            )


            # صور غير مناسبة كصورة خبر
            if ratio < 1.15:
                return None

            if ratio > 3.5:
                return None


        else:

            # إذا لم نستطع معرفة الأبعاد
            # نستخدم حجم الملف كفلتر تقريبي

            if content_length:

                if content_length < 30_000:
                    return None

            elif len(data) < 30_000:

                return None


        # ----------------------------------------------------
        # حساب الجودة
        # ----------------------------------------------------

        if width and height:

            score = (
                width * height
            )

            if width >= 1200:
                score *= 2

            if height >= 630:
                score *= 1.5

        else:

            score = (
                max(
                    content_length,
                    len(data)
                )
                / 1000
            )


        return {

            "url":
                image_url,

            "width":
                width,

            "height":
                height,

            "score":
                score

        }


    except Exception as error:

        print(
            "IMAGE INSPECTION ERROR:",
            str(error)[:150]
        )

        return None


# ============================================================
# GET BEST IMAGE
# ============================================================

def get_best_image(
    article_url,
    rss_image=""
):

    if not article_url:
        return rss_image or ""


    candidates = []


    # --------------------------------------------------------
    # RSS image
    # --------------------------------------------------------

    if rss_image:

        candidates.append(
            rss_image
        )


    # --------------------------------------------------------
    # صفحة الخبر
    # --------------------------------------------------------

    try:

        response = SESSION.get(

            article_url,

            timeout=REQUEST_TIMEOUT,

            allow_redirects=True

        )


        if response.status_code == 200:

            page = response.text[
                :800000
            ]


            page_images = extract_page_images(

                page,

                response.url

            )


            candidates.extend(
                page_images
            )


    except Exception as error:

        print(
            "ARTICLE PAGE ERROR:",
            str(error)[:180]
        )


    # --------------------------------------------------------
    # إزالة التكرار
    # --------------------------------------------------------

    unique = []

    seen = set()


    for image in candidates:

        image = valid_image_url(
            image
        )

        if not image:
            continue


        if image in seen:
            continue


        seen.add(
            image
        )

        unique.append(
            image
        )


    if not unique:

        return ""


    print(
        "Image candidates:",
        len(unique)
    )


    # --------------------------------------------------------
    # اختيار أفضل صورة
    # --------------------------------------------------------

    best = None


    for image_url in unique:

        result = inspect_image(
            image_url
        )


        if not result:
            continue


        print(

            "IMAGE:",
            result["width"],
            "x",
            result["height"],
            image_url[:100]

        )


        if (
            best is None
            or
            result["score"] > best["score"]
        ):

            best = result


    if best:

        print(
            "BEST IMAGE:",
            best["width"],
            "x",
            best["height"]
        )

        return best["url"]


    # --------------------------------------------------------
    # إذا لم نستطع فحص الصورة
    # نستخدم RSS فقط كحل أخير
    # --------------------------------------------------------

    if rss_image:

        print(
            "Using RSS image fallback."
        )

        return rss_image


    return ""


# ============================================================
# PUBLISHED TIMESTAMP
# ============================================================

def get_published_timestamp(
    entry
):

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
# ISO DATE
# ============================================================

def timestamp_to_iso(
    timestamp
):

    if not timestamp:
        return ""


    try:

        return datetime.fromtimestamp(

            timestamp,

            timezone.utc

        ).isoformat()

    except Exception:

        return ""


# ============================================================
# ARTICLE AGE
# ============================================================

def article_age_hours(
    timestamp
):

    if not timestamp:
        return 999999


    now = time.time()


    age = (
        now - timestamp
    ) / 3600


    return max(
        0,
        age
    )


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(
    items
):

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


        if (
            link_key
            and
            link_key in seen_links
        ):
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


                # ------------------------------------------------
                # التاريخ
                # ------------------------------------------------

                published_timestamp = (

                    get_published_timestamp(
                        entry
                    )

                )


                if not published_timestamp:

                    print(
                        "SKIP — no publication date:",
                        title[:100]
                    )

                    continue


                age = article_age_hours(
                    published_timestamp
                )


                # ------------------------------------------------
                # فلتر الأخبار القديمة
                # ------------------------------------------------

                if age > MAX_AGE_HOURS:

                    print(
                        f"SKIP OLD — {age:.1f}h:",
                        title[:100]
                    )

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
                        published_timestamp,

                    "_age_hours":
                        age

                })


        except Exception as error:

            print(
                "RSS ERROR:",
                source_name,
                str(error)[:250]
            )


    # ------------------------------------------------------------
    # إزالة التكرار
    # ------------------------------------------------------------

    articles = remove_duplicates(
        articles
    )


    # ------------------------------------------------------------
    # الأحدث أولاً
    # ------------------------------------------------------------

    articles.sort(

        key=lambda item:
            item.get(
                "_published_timestamp",
                0
            ),

        reverse=True

    )


    print("")
    print(
        "FRESH ARTICLES:",
        len(articles)
    )


    return articles


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
    # 3 أخبار حديثة من كل قسم
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
                f"{article.get('title', '')}"
            )


            if count >= MIN_PER_CATEGORY:
                break


    # --------------------------------------------------------
    # لا نضيف أخبارًا من أقسام أخرى إذا وصلنا 21
    # --------------------------------------------------------

    if len(selected) >= MAX_NEWS:

        return selected[
            :MAX_NEWS
        ]


    # --------------------------------------------------------
    # إضافة أخبار إضافية إذا كانت متوفرة
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
# SUMMARY VALIDATION
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


    if not summary:
        return False


    # --------------------------------------------------------
    # الملخص يجب أن يكون أطول من مجرد جملة
    # --------------------------------------------------------

    if len(summary) < 250:

        return False


    # --------------------------------------------------------
    # لا يكون نفس العنوان
    # --------------------------------------------------------

    if summary.lower() == title.lower():

        return False


    # --------------------------------------------------------
    # عدد الجمل
    # --------------------------------------------------------

    sentences = len(

        re.findall(
            r"[.!؟。]",
            summary
        )

    )


    if sentences < 3:

        return False


    # --------------------------------------------------------
    # عدد الكلمات
    # --------------------------------------------------------

    words = re.findall(
        r"\S+",
        summary
    )


    if len(words) < 45:

        return False


    if len(words) > 180:

        return False


    return True


# ============================================================
# GEMINI BATCH
# ============================================================

def ask_gemini_batch(
    articles
):

    if not articles:

        return []


    news_text = []


    for index, article in enumerate(

        articles,

        start=1

    ):

        description = clean_text(

            article.get(
                "description",
                ""
            )

        )


        if not description:

            description = (
                "لا يوجد وصف إضافي. "
                "اعتمد فقط على العنوان "
                "ولا تضف معلومات غير مؤكدة."
            )


        news_text.append(

            f"""
ARTICLE {index}

SOURCE:
{article.get("source", "")}

CATEGORY:
{article.get("category", "")}

ORIGINAL TITLE:
{article.get("title", "")}

AVAILABLE INFORMATION:
{description}
"""

        )


    joined_news = "\n".join(
        news_text
    )


    prompt = f"""
أنت محرر الأخبار الرئيسي في NOWNEX.

حوّل الأخبار التالية إلى أخبار عربية احترافية.

مهم جدًا:
- يجب ترجمة كل خبر إلى العربية.
- لا تترك أي عنوان باللغة الإنجليزية.
- لا تستخدم الإنجليزية في title_ar أو summary_ar إلا إذا كانت اسمًا أو علامة تجارية لا يمكن ترجمتها.
- لا تخترع أي معلومة.
- لا تخترع أسماء.
- لا تخترع أرقامًا.
- لا تخترع تصريحات.
- لا تخترع اقتباسات.
- لا تضف رأيًا شخصيًا.
- استخدم المعلومات الموجودة في الخبر فقط.

لكل خبر:
1. عنوان عربي واضح.
2. ملخص عربي من 3 إلى 5 جمل.
3. الملخص يجب أن يكون تقريبًا 70 إلى 120 كلمة.
4. يجب أن يشرح أهم ما حدث، ومن المعني، وما التفاصيل الموجودة في المادة الأصلية.
5. لا تجعل الملخص مجرد إعادة صياغة للعنوان.
6. لا تستخدم عبارات عامة لملء النص.
7. لا تختصر الخبر إلى جملة أو جملتين.

أعد JSON فقط بالشكل التالي:

[
  {{
    "id": 1,
    "title_ar": "العنوان العربي",
    "summary_ar": "الملخص العربي"
  }}
]

يجب أن تعيد عنصرًا لكل ARTICLE وبنفس رقم ARTICLE.

الأخبار:

{joined_news}
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
                f"Gemini batch request "
                f"{attempt}/3"
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
            # Rate limit
            # ------------------------------------------------

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
                    "Rate limit 429."
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


            # ------------------------------------------------
            # أخطاء أخرى
            # ------------------------------------------------

            if response.status_code != 200:

                print(
                    "Gemini error:",
                    response.text[:1200]
                )

                return []


            data = response.json()


            candidates = data.get(
                "candidates",
                []
            )


            if not candidates:

                print(
                    "Gemini returned no candidates."
                )

                return []


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

                return []


            text = text.strip()


            # ------------------------------------------------
            # تنظيف Markdown إن ظهر
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


            if isinstance(
                result,
                dict
            ):

                result = result.get(
                    "articles",
                    []
                )


            if not isinstance(
                result,
                list
            ):

                print(
                    "Gemini JSON is not a list."
                )

                return []


            return result


        except Exception as error:

            print(
                "Gemini batch error:",
                str(error)[:500]
            )


            if attempt < 3:

                time.sleep(
                    10
                )


    return []


# ============================================================
# PROCESS GEMINI RESULT
# ============================================================

def process_batch(
    articles
):

    results = ask_gemini_batch(
        articles
    )


    final_items = []


    # --------------------------------------------------------
    # تحويل النتائج إلى dictionary حسب id
    # --------------------------------------------------------

    by_id = {}


    for result in results:

        if not isinstance(
            result,
            dict
        ):
            continue


        try:

            article_id = int(
                result.get(
                    "id"
                )
            )

        except Exception:

            continue


        by_id[
            article_id
        ] = result


    # --------------------------------------------------------
    # معالجة كل خبر
    # --------------------------------------------------------

    for index, article in enumerate(

        articles,

        start=1

    ):

        ai = by_id.get(
            index
        )


        if not ai:

            print(
                "SKIPPED — no Gemini result:",
                article.get(
                    "title",
                    ""
                )[:100]
            )

            continue


        title_ar = clean_text(

            ai.get(
                "title_ar",
                ""
            )

        )


        summary_ar = clean_text(

            ai.get(
                "summary_ar",
                ""
            )

        )


        # ----------------------------------------------------
        # لا ننشر الإنجليزية
        # ----------------------------------------------------

        if not title_ar:

            print(
                "SKIPPED — empty Arabic title."
            )

            continue


        # إذا كان العنوان إنجليزيًا بشكل واضح
        arabic_chars = len(

            re.findall(
                r"[\u0600-\u06FF]",
                title_ar
            )

        )


        latin_chars = len(

            re.findall(
                r"[A-Za-z]",
                title_ar
            )

        )


        if (
            latin_chars > arabic_chars * 2
            and
            latin_chars > 15
        ):

            print(
                "SKIPPED — title still appears English:",
                title_ar[:120]
            )

            continue


        # ----------------------------------------------------
        # الملخص
        # ----------------------------------------------------

        if not summary_is_valid(

            title_ar,

            summary_ar

        ):

            print(
                "SKIPPED — summary too short:",
                title_ar[:100]
            )

            continue


        published_timestamp = article.get(
            "_published_timestamp",
            0
        )


        item = {

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
                article.get(
                    "category",
                    ""
                ),

            "source":
                article.get(
                    "source",
                    ""
                ),

            "link":
                article.get(
                    "link",
                    ""
                ),

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

            # مهم:
            # هذا هو تاريخ الخبر الحقيقي
            # وليس وقت تشغيل GitHub
            "publishedAt":
                timestamp_to_iso(
                    published_timestamp
                ),

            "ageHours":
                round(
                    article.get(
                        "_age_hours",
                        0
                    ),
                    1
                )

        }


        final_items.append(
            item
        )


        print(
            "CREATED ✓:",
            title_ar[:120]
        )


    return final_items


# ============================================================
# FETCH BEST IMAGES
# ============================================================

def complete_images(
    selected
):

    print("")
    print(
        "=========================================="
    )

    print(
        "FETCHING BEST QUALITY IMAGES"
    )

    print(
        "=========================================="
    )


    for index, article in enumerate(

        selected,

        start=1

    ):

        print("")
        print(
            f"[{index}/{len(selected)}]"
        )

        print(
            article.get(
                "title",
                ""
            )[:120]
        )


        image = get_best_image(

            article.get(
                "link",
                ""
            ),

            article.get(
                "image",
                ""
            )

        )


        if image:

            article["image"] = image

            print(
                "IMAGE ✓"
            )

        else:

            article["image"] = ""

            print(
                "IMAGE: NONE"
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
# CATEGORY COUNTS
# ============================================================

def get_category_counts(
    news
):

    counts = {}


    for category in MAIN_CATEGORIES:

        counts[category] = len([

            item

            for item in news

            if item.get(
                "category"
            ) == category

        ])


    return counts


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
        " FRESH + ARABIC + QUALITY"
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

    print(
        "Maximum news age:",
        MAX_AGE_HOURS,
        "hours"
    )

    print(
        "Gemini batch size:",
        GEMINI_BATCH_SIZE
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
        "AVAILABLE FRESH NEWS"
    )

    print(
        "=========================================="
    )


    available_counts = get_category_counts(
        articles
    )


    for category in MAIN_CATEGORIES:

        print(
            f"{category}: "
            f"{available_counts.get(category, 0)}"
        )


    # ========================================================
    # 2. SELECT NEWS
    # ========================================================

    selected = select_news(
        articles
    )


    print("")
    print(
        "SELECTED:",
        len(selected)
    )


    selected_counts = get_category_counts(
        selected
    )


    print("")
    print(
        "SELECTED BY CATEGORY:"
    )


    for category in MAIN_CATEGORIES:

        print(
            f"{category}: "
            f"{selected_counts.get(category, 0)}"
        )


    # ========================================================
    # 3. تأكد أن كل قسم لديه 3 أخبار حديثة
    # ========================================================

    missing_before_ai = [

        category

        for category in MAIN_CATEGORIES

        if selected_counts.get(
            category,
            0
        ) < MIN_PER_CATEGORY

    ]


    if missing_before_ai:

        print("")
        print(
            "=========================================="
        )

        print(
            "ERROR — NOT ENOUGH FRESH NEWS"
        )

        print(
            "=========================================="
        )


        for category in MAIN_CATEGORIES:

            print(

                f"{category}: "
                f"{selected_counts.get(category, 0)}/"
                f"{MIN_PER_CATEGORY}"

            )


        print("")
        print(
            "Existing news.json was NOT modified."
        )


        raise RuntimeError(
            "Not enough fresh articles."
        )


    # ========================================================
    # 4. FETCH BEST IMAGES
    # ========================================================

    selected = complete_images(
        selected
    )


    # ========================================================
    # 5. GEMINI TRANSLATION
    # ========================================================

    final_news = []


    print("")
    print(
        "=========================================="
    )

    print(
        "TRANSLATING NEWS WITH GEMINI"
    )

    print(
        "=========================================="
    )


    total_batches = (

        (
            len(selected)
            +
            GEMINI_BATCH_SIZE
            -
            1
        )
        //
        GEMINI_BATCH_SIZE

    )


    for batch_number, start in enumerate(

        range(
            0,
            len(selected),
            GEMINI_BATCH_SIZE
        ),

        start=1

    ):

        batch = selected[

            start:
            start + GEMINI_BATCH_SIZE

        ]


        print("")
        print(
            "------------------------------------------"
        )

        print(
            f"BATCH {batch_number}/{total_batches}"
        )

        print(
            f"Articles: {len(batch)}"
        )


        batch_results = process_batch(
            batch
        )


        final_news.extend(
            batch_results
        )


        print(
            "Batch created:",
            len(batch_results)
        )


        # ----------------------------------------------------
        # لا ننتظر بعد آخر دفعة
        # ----------------------------------------------------

        if batch_number < total_batches:

            print(
                "Waiting:",
                GEMINI_BATCH_DELAY,
                "seconds"
            )

            time.sleep(
                GEMINI_BATCH_DELAY
            )


    # ========================================================
    # 6. FINAL CATEGORY CHECK
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


    category_counts = get_category_counts(
        final_news
    )


    for category in MAIN_CATEGORIES:

        print(

            f"{category}: "
            f"{category_counts.get(category, 0)}/"
            f"{MIN_PER_CATEGORY}"

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
    # لا ننشر نتيجة ناقصة
    # ========================================================

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


        for category in missing_categories:

            print(

                f"- {category}: "
                f"{category_counts.get(category, 0)}/"
                f"{MIN_PER_CATEGORY}"

            )


        print("")
        print(
            "Existing news.json was NOT modified."
        )


        raise RuntimeError(
            "Not enough valid Arabic articles."
        )


    # ========================================================
    # 7. ترتيب النهائي من الأحدث إلى الأقدم
    # ========================================================

    final_news.sort(

        key=lambda item:

            item.get(
                "publishedAt",
                ""
            ),

        reverse=True

    )


    final_news = final_news[
        :MAX_NEWS
    ]


    # ========================================================
    # 8. TRENDING
    # ========================================================

    trending_news = create_trending(
        final_news
    )


    # ========================================================
    # 9. OUTPUT
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
    # 10. SAVE
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
    # 11. FINAL REPORT
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


    for item in final_news[:10]:

        print(

            f"  {item.get('ageHours', '?')}h | "
            f"{item.get('category', '')} | "
            f"{item.get('title_ar', '')[:100]}"

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
