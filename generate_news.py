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
# NOWNEX — ARABIC NEWS ENGINE
# 7 CATEGORIES × 3 ARTICLES
# الصور تحفظ كرابط فقط ولا يتم تنزيلها
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

MIN_PER_CATEGORY = 3

MAX_NEWS = 24

CANDIDATES_PER_CATEGORY = 18

GEMINI_RETRIES = 3

REQUEST_TIMEOUT = 25

GEMINI_TIMEOUT = 90

REQUEST_DELAY = 2


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
        "Google News World English",
        "https://news.google.com/rss/search?q=world%20news&hl=en&gl=US&ceid=US:en",
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
        "Mozilla/5.0 (compatible; NOWNEX NewsBot/3.0)",

    "Accept":
        "application/rss+xml, application/xml, "
        "text/xml, text/html;q=0.9, */*;q=0.8",

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
# ARABIC VALIDATION
# ============================================================

def arabic_ratio(text):

    text = clean_text(text)

    arabic = len(
        re.findall(
            r"[\u0600-\u06FF]",
            text
        )
    )

    english = len(
        re.findall(
            r"[A-Za-z]",
            text
        )
    )

    total = arabic + english

    if not total:
        return 0

    return arabic / total


def valid_arabic(text):

    text = clean_text(text)

    if len(text) < 8:
        return False

    if len(
        re.findall(
            r"[\u0600-\u06FF]",
            text
        )
    ) < 4:

        return False

    if arabic_ratio(text) < 0.80:
        return False

    return True


def summary_quality(
    title,
    summary
):

    if not title:
        return False

    if not summary:
        return False

    if len(summary) < 100:
        return False

    if title.lower() == summary.lower():
        return False

    sentences = re.findall(
        r"[.!?؟。]",
        summary
    )

    if len(sentences) < 2:
        return False

    return True


# ============================================================
# IMAGE URL
# ============================================================

def normalize_image_url(
    value,
    base_url=""
):

    if not value:
        return ""

    value = html.unescape(
        str(value).strip()
    )

    value = value.replace(
        "\\/",
        "/"
    )

    value = value.strip(
        "\"'"
    )

    if value.startswith("//"):

        value = "https:" + value

    value = urljoin(
        base_url,
        value
    )

    if value.startswith(
        (
            "http://",
            "https://"
        )
    ):

        return value

    return ""


def usable_image(url):

    if not url:
        return False

    lowered = url.lower()

    bad_words = [

        "data:image/",
        ".svg",
        "favicon",
        "logo",
        "avatar",
        "placeholder",
        "sprite",
        "icon",

    ]

    if any(
        word in lowered
        for word in bad_words
    ):

        return False

    return url.startswith(
        (
            "http://",
            "https://"
        )
    )


# ============================================================
# RSS IMAGE
# ============================================================

def extract_rss_image(entry):

    # media_content
    for media in entry.get(
        "media_content",
        []
    ) or []:

        image = normalize_image_url(
            media.get("url")
            or media.get("href")
            or media.get("src")
        )

        if usable_image(image):
            return image


    # media_thumbnail
    for media in entry.get(
        "media_thumbnail",
        []
    ) or []:

        image = normalize_image_url(
            media.get("url")
            or media.get("href")
            or media.get("src")
        )

        if usable_image(image):
            return image


    # enclosures
    for enclosure in entry.get(
        "enclosures",
        []
    ) or []:

        image = normalize_image_url(
            enclosure.get("href")
            or enclosure.get("url")
        )

        if usable_image(image):
            return image


    # links
    for link in entry.get(
        "links",
        []
    ) or []:

        rel = str(
            link.get("rel", "")
        ).lower()

        media_type = str(
            link.get("type", "")
        ).lower()

        if (
            rel == "enclosure"
            or media_type.startswith("image/")
        ):

            image = normalize_image_url(
                link.get("href")
                or link.get("url")
            )

            if usable_image(image):
                return image


    # HTML داخل RSS
    source_text = (
        entry.get("summary", "")
        or entry.get("description", "")
    )

    if not source_text:

        content = entry.get(
            "content",
            []
        )

        if content:

            source_text = content[0].get(
                "value",
                ""
            )


    source_text = str(
        source_text or ""
    )


    patterns = [

        r'<img[^>]+src=["\']([^"\']+)["\']',

        r'<img[^>]+data-src=["\']([^"\']+)["\']',

        r'<img[^>]+data-original=["\']([^"\']+)["\']',

    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            source_text,
            re.IGNORECASE
        )

        if match:

            image = normalize_image_url(
                match.group(1)
            )

            if usable_image(image):
                return image


    return ""


# ============================================================
# IMAGE FROM ARTICLE PAGE
# ============================================================

def extract_page_image(
    page,
    base_url
):

    # --------------------------------------------------------
    # OpenGraph
    # --------------------------------------------------------

    patterns = [

        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        r'<meta[^>]+property=["\']og:image:secure_url["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image:secure_url["\']',

        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',

        r'<meta[^>]+name=["\']twitter:image:src["\'][^>]+content=["\']([^"\']+)["\']',

        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',

        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']image_src["\']',

    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            page,
            re.IGNORECASE
        )

        if match:

            image = normalize_image_url(
                match.group(1),
                base_url
            )

            if usable_image(image):
                return image


    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    jsonld_blocks = re.findall(

        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>'
        r'(.*?)'
        r'</script>',

        page,

        re.IGNORECASE |
        re.DOTALL

    )


    for block in jsonld_blocks:

        matches = re.findall(

            r'"image"\s*:\s*"([^"]+)"',

            block,

            re.IGNORECASE

        )


        for value in matches:

            image = normalize_image_url(
                value,
                base_url
            )

            if usable_image(image):
                return image


    # --------------------------------------------------------
    # Lazy images
    # --------------------------------------------------------

    lazy_patterns = [

        r'data-src=["\']([^"\']+)["\']',

        r'data-original=["\']([^"\']+)["\']',

        r'data-lazy-src=["\']([^"\']+)["\']',

        r'data-image=["\']([^"\']+)["\']',

        r'data-image-url=["\']([^"\']+)["\']',

    ]


    for pattern in lazy_patterns:

        matches = re.findall(
            pattern,
            page,
            re.IGNORECASE
        )

        for value in matches:

            image = normalize_image_url(
                value,
                base_url
            )

            if usable_image(image):
                return image


    # --------------------------------------------------------
    # SRCSET
    # --------------------------------------------------------

    srcsets = re.findall(

        r'(?:srcset|data-srcset)=["\']([^"\']+)["\']',

        page,

        re.IGNORECASE

    )


    for srcset in srcsets:

        best_url = ""

        best_width = 0


        for part in srcset.split(","):

            pieces = part.strip().split()

            if not pieces:
                continue

            image = normalize_image_url(
                pieces[0],
                base_url
            )

            if not usable_image(image):
                continue

            width = 0

            if len(pieces) > 1:

                match = re.search(
                    r"(\d+)w",
                    pieces[1]
                )

                if match:
                    width = int(
                        match.group(1)
                    )


            if width >= best_width:

                best_width = width
                best_url = image


        if best_url:
            return best_url


    return ""


def get_page_image(url):

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


        if (
            "html" not in content_type
            and "xhtml" not in content_type
        ):

            return ""


        # نقرأ HTML فقط في الذاكرة.
        # لا يتم حفظ الصفحة أو الصورة.

        page = response.text[
            :1500000
        ]


        return extract_page_image(
            page,
            response.url
        )


    except Exception as error:

        print(
            "PAGE IMAGE ERROR:",
            error
        )

        return ""


def get_best_image(
    entry,
    link
):

    # أولاً RSS
    image = extract_rss_image(
        entry
    )

    if usable_image(image):

        return image


    # ثانياً صفحة الخبر
    image = get_page_image(
        link
    )

    if usable_image(image):

        return image


    return ""


# ============================================================
# COLLECT RSS
# ============================================================

def get_news():

    articles = []


    for source_name, feed_url, category in RSS_FEEDS:

        print(
            "\n================================"
        )

        print(
            "SOURCE:",
            source_name
        )

        print(
            "CATEGORY:",
            category
        )


        try:

            feed = feedparser.parse(
                feed_url
            )


            entries = feed.entries[
                :30
            ]


            print(
                "ENTRIES:",
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

                        description = clean_text(
                            content[0].get(
                                "value",
                                ""
                            )
                        )


                link = str(
                    entry.get(
                        "link",
                        ""
                    )
                ).strip()


                if not link:
                    continue


                print(
                    "ARTICLE:",
                    title[:100]
                )


                image = get_best_image(
                    entry,
                    link
                )


                if image:

                    print(
                        "IMAGE FOUND:",
                        image[:180]
                    )

                else:

                    print(
                        "IMAGE NOT FOUND"
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
        "\nTOTAL RSS:",
        len(articles)
    )


    return articles


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
                "OLD NEWS:",
                len(news)
            )

            return news


    except Exception as error:

        print(
            "OLD NEWS ERROR:",
            error
        )


    return []


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(
    article
):

    prompt = f"""

أنت المحرر الرئيسي لمنصة NOWNEX العربية.

حوّل الخبر التالي إلى خبر عربي احترافي.

المصدر:
{article["source"]}

القسم:
{article["category"]}

العنوان الأصلي:
{article["title"]}

معلومات المصدر:
{article["description"]}


============================================================
الإخراج
============================================================

أعد JSON فقط يحتوي على:

title_ar
summary_ar


============================================================
الشروط
============================================================

اكتب باللغة العربية الفصحى الحديثة.

العنوان يجب أن يكون صحفياً واضحاً وجذاباً.

الملخص يجب أن يكون من 3 إلى 5 جمل.

لا تخترع أي معلومة.

لا تضف أرقاماً غير موجودة.

لا تضف أسماء غير موجودة.

لا تضف تواريخ غير موجودة.

لا تضف تصريحات غير موجودة.

لا تضف رأياً شخصياً.

لا تستخدم معلومات من خارج المصدر.

يمكن استخدام أسماء الشركات والمنتجات العالمية
باللغة الأصلية عند الضرورة مثل:

OpenAI
Google
Tesla
Samsung
ChatGPT
NASA

لكن ممنوع كتابة جمل إنجليزية كاملة.

العربية يجب أن تكون اللغة الأساسية بالكامل.


============================================================
JSON ONLY
============================================================

{{
    "title_ar": "عنوان عربي احترافي",
    "summary_ar": "ملخص عربي احترافي من ثلاث إلى خمس جمل."
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

            response = requests.post(

                GEMINI_URL,

                headers=headers,

                json=payload,

                timeout=GEMINI_TIMEOUT

            )


            print(
                "GEMINI STATUS:",
                response.status_code
            )


            if response.status_code == 429:

                wait = 30 * attempt

                print(
                    f"RATE LIMIT — WAIT {wait}s"
                )

                time.sleep(
                    wait
                )

                continue


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


            if not valid_arabic(
                title_ar
            ):

                print(
                    "INVALID ARABIC TITLE"
                )

                continue


            if not valid_arabic(
                summary_ar
            ):

                print(
                    "INVALID ARABIC SUMMARY"
                )

                continue


            if not summary_quality(
                title_ar,
                summary_ar
            ):

                print(
                    "INVALID SUMMARY QUALITY"
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
                "GEMINI ERROR:",
                error
            )


        if attempt < GEMINI_RETRIES:

            time.sleep(
                10
            )


    return None


# ============================================================
# CATEGORY
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
# BUILD ITEM
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
        " NOWNEX ARABIC NEWS ENGINE"
    )

    print(
        " 7 CATEGORIES × 3 ARTICLES"
    )

    print(
        " IMAGE EXTRACTION ENABLED"
    )

    print(
        "=========================================="
    )


    # --------------------------------------------------------
    # OLD NEWS
    # --------------------------------------------------------

    old_news = load_existing_news()


    # --------------------------------------------------------
    # RSS
    # --------------------------------------------------------

    articles = get_news()


    if not articles:

        print(
            "NO RSS DATA."
        )

        print(
            "KEEPING OLD news.json."
        )

        return


    # --------------------------------------------------------
    # POOLS
    # --------------------------------------------------------

    pools = {

        category:
            get_category_articles(
                articles,
                category
            )[
                :CANDIDATES_PER_CATEGORY
            ]

        for category in MAIN_CATEGORIES

    }


    # --------------------------------------------------------
    # GENERATE
    # --------------------------------------------------------

    generated = {

        category: []

        for category in MAIN_CATEGORIES

    }


    used_titles = set()


    for category in MAIN_CATEGORIES:

        print(
            "\n=========================================="
        )

        print(
            "PROCESSING:",
            category
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


            if original_key in used_titles:

                continue


            used_titles.add(
                original_key
            )


            print(
                "\nTRY:",
                article["title"]
            )


            ai = ask_gemini(
                article
            )


            if not ai:

                print(
                    "REJECTED"
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
                "ACCEPTED"
            )


            print(
                "IMAGE:",
                "YES"
                if item.get("image")
                else "NO"
            )


            time.sleep(
                REQUEST_DELAY
            )


        print(
            category,
            "NEW:",
            len(
                generated[category]
            )
        )


    # --------------------------------------------------------
    # ASSEMBLE
    # --------------------------------------------------------

    final_news = []

    final_keys = set()


    for category in MAIN_CATEGORIES:

        print(
            "\nFINALIZING:",
            category
        )


        # الأخبار الجديدة
        for item in generated[category]:

            key = normalize_title(
                item.get(
                    "title_ar",
                    ""
                )
            )


            if not key:
                continue


            if key in final_keys:
                continue


            final_keys.add(
                key
            )


            final_news.append(
                item
            )


            current_count = len(
                get_category_articles(
                    final_news,
                    category
                )
            )


            if current_count >= MIN_PER_CATEGORY:

                break


        # الأخبار القديمة كاحتياط
        current_count = len(
            get_category_articles(
                final_news,
                category
            )
        )


        if current_count < MIN_PER_CATEGORY:

            print(
                "Using old news as fallback."
            )


            for old in get_category_articles(
                old_news,
                category
            ):

                title_ar = (
                    old.get(
                        "title_ar"
                    )
                    or
                    old.get(
                        "title"
                    )
                    or
                    ""
                )


                summary_ar = (
                    old.get(
                        "summary_ar"
                    )
                    or
                    old.get(
                        "summary"
                    )
                    or
                    old.get(
                        "description"
                    )
                    or
                    ""
                )


                key = normalize_title(
                    title_ar
                )


                if not key:
                    continue


                if key in final_keys:
                    continue


                old["title_ar"] = (
                    title_ar
                )

                old["summary_ar"] = (
                    summary_ar
                )

                old["title"] = (
                    old.get(
                        "title"
                    )
                    or
                    title_ar
                )

                old["summary"] = (
                    old.get(
                        "summary"
                    )
                    or
                    summary_ar
                )

                old["description"] = (
                    old.get(
                        "description"
                    )
                    or
                    summary_ar
                )


                final_keys.add(
                    key
                )


                final_news.append(
                    old
                )


                current_count += 1


                if current_count >= MIN_PER_CATEGORY:

                    break


        print(
            category,
            "FINAL:",
            current_count
        )


    # --------------------------------------------------------
    # SAFETY
    # --------------------------------------------------------

    missing = []


    for category in MAIN_CATEGORIES:

        count = len(
            get_category_articles(
                final_news,
                category
            )
        )


        if count < MIN_PER_CATEGORY:

            missing.append(
                category
            )


    if missing:

        print(
            "\nUPDATE CANCELLED."
        )

        print(
            "Missing categories:",
            missing
        )

        print(
            "Previous news.json was NOT replaced."
        )

        return


    # --------------------------------------------------------
    # LIMIT
    # --------------------------------------------------------

    final_news = final_news[
        :MAX_NEWS
    ]


    # --------------------------------------------------------
    # TRENDING
    # --------------------------------------------------------

    trending = final_news[
        :3
    ]


    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    output = {

        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "count":
            len(final_news),

        "trending":
            trending,

        "news":
            final_news

    }


    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    image_count = sum(

        1

        for item in final_news

        if item.get(
            "image"
        )

    )


    print(
        "\n"
        "=========================================="
    )

    print(
        " NOWNEX UPDATED SUCCESSFULLY"
    )

    print(
        "=========================================="
    )


    print(
        "TOTAL:",
        len(final_news)
    )


    print(
        "WITH IMAGE:",
        image_count
    )


    for category in MAIN_CATEGORIES:

        print(

            category,
            ":",
            len(
                get_category_articles(
                    final_news,
                    category
                )
            )

        )


    print(
        "\nDONE."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
