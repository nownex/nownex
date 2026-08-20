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
# 7 CATEGORIES × 3 ARTICLES = 21 ARTICLES
# EXTERNAL IMAGES ONLY
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

MAIN_CATEGORIES = [
    "AI",
    "Technology",
    "Cars",
    "Entertainment",
    "World",
    "Facts",
    "Products",
]

MIN_PER_CATEGORY = 3

MAX_NEWS = 21

CANDIDATES_PER_CATEGORY = 12

GEMINI_RETRIES = 3

REQUEST_TIMEOUT = 25

GEMINI_TIMEOUT = 90

REQUEST_DELAY = 2


# ============================================================
# FALLBACK IMAGES
# ============================================================
# هذه الصور موجودة أصلًا في موقعك.
# تستخدم فقط عندما لا توجد صورة للخبر.
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
        "products.png",

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
        "Mozilla/5.0 (compatible; NOWNEX/3.0; +https://nownex.com)",

    "Accept":
        "application/rss+xml, application/xml, text/xml, text/html,*/*",

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

        seen.add(
            key
        )

        result.append(
            item
        )

    return result


# ============================================================
# LANGUAGE VALIDATION
# ============================================================

def arabic_ratio(text):

    text = clean_text(
        text
    )

    letters = re.findall(
        r"[A-Za-z\u0600-\u06FF]",
        text
    )

    if not letters:
        return 0

    arabic = re.findall(
        r"[\u0600-\u06FF]",
        text
    )

    return len(arabic) / len(letters)


def is_arabic_text(text):

    text = clean_text(
        text
    )

    if len(text) < 8:
        return False

    arabic_count = len(
        re.findall(
            r"[\u0600-\u06FF]",
            text
        )
    )

    if arabic_count < 4:
        return False

    return arabic_ratio(text) >= 0.55


# ============================================================
# IMAGE — RSS
# ============================================================

def extract_rss_image(entry):

    # --------------------------------------------------------
    # media:content
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # media:thumbnail
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # enclosure
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # image داخل الوصف
    # --------------------------------------------------------

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


    matches = re.findall(

        r'<img[^>]+src=["\']([^"\']+)["\']',

        str(
            source_text
        ),

        re.IGNORECASE

    )


    if matches:

        return html.unescape(
            matches[0].strip()
        )


    return ""


# ============================================================
# IMAGE — OG IMAGE
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

            print(
                "OG page status:",
                response.status_code
            )

            return ""


        # نقرأ حجمًا كبيرًا من الصفحة لأن
        # بعض المواقع تضع meta tags بعد بداية الصفحة.

        page = response.text[
            :1500000
        ]


        patterns = [

            # property ثم content
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

            # content ثم property
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

            # twitter image
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

                    match.group(
                        1
                    ).strip()

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

                    print(
                        "✓ OG image found"
                    )

                    return image


    except Exception as error:

        print(
            "OG image error:",
            error
        )


    return ""


# ============================================================
# IMAGE QUALITY HELPERS
# ============================================================

def make_high_quality_image_url(url):

    """
    نحاول الحصول على نسخة أكبر من الصورة عندما يكون
    الرابط يحتوي على معلمات تصغير معروفة.

    لا نغير الرابط عشوائيًا حتى لا نكسر الصور.
    """

    if not url:
        return ""


    result = url


    # TechCrunch:
    # ?resize=1200,800
    result = re.sub(

        r"[?&]resize=\d+,\d+",

        "",

        result,

        flags=re.IGNORECASE

    )


    # بعض CDN تستخدم w= / width=
    result = re.sub(

        r"([?&])(w|width)=\d+",

        r"\1",

        result,

        flags=re.IGNORECASE

    )


    # إزالة & زائدة
    result = result.replace(
        "?&",
        "?"
    )


    result = result.rstrip(
        "?&"
    )


    return result


# ============================================================
# BEST IMAGE
# ============================================================

def get_best_image(
    entry,
    link,
    category
):

    # ========================================================
    # 1 — RSS IMAGE
    # ========================================================

    image = extract_rss_image(
        entry
    )


    if image:

        print(
            "RSS image found:"
        )

        print(
            image
        )

        return make_high_quality_image_url(
            image
        )


    # ========================================================
    # 2 — OG IMAGE
    # ========================================================

    print(
        "Searching original page for OG image..."
    )


    image = get_og_image(
        link
    )


    if image:

        return make_high_quality_image_url(
            image
        )


    # ========================================================
    # 3 — FALLBACK
    # ========================================================

    fallback = FALLBACK_IMAGES.get(
        category,
        ""
    )


    print(
        "No article image."
    )

    print(
        "Using category fallback:",
        fallback
    )


    return fallback


# ============================================================
# RSS COLLECTION
# ============================================================

def get_news():

    articles = []


    for source_name, feed_url, category in RSS_FEEDS:

        print(
            "\n"
            "=========================================="
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


            entries = feed.entries[
                :20
            ]


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
                        published,

                })


        except Exception as error:

            print(
                "RSS ERROR:",
                source_name,
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

        r"[.!؟。]",

        summary

    )


    if len(sentences) < 2:
        return False


    return True


# ============================================================
# ARTICLE VALIDATION
# ============================================================

def article_is_valid(
    title_ar,
    summary_ar
):

    if not is_arabic_text(
        title_ar
    ):

        print(
            "FAILED Arabic title"
        )

        return False


    if not is_arabic_text(
        summary_ar
    ):

        print(
            "FAILED Arabic summary"
        )

        return False


    if not summary_quality(

        title_ar,

        summary_ar

    ):

        print(
            "FAILED summary quality"
        )

        return False


    return True


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(article):

    title = clean_text(

        article.get(
            "title",
            ""
        )

    )


    description = clean_text(

        article.get(
            "description",
            ""
        )

    )


    source = clean_text(

        article.get(
            "source",
            ""
        )

    )


    category = clean_text(

        article.get(
            "category",
            ""
        )

    )


    if not description:

        description = (
            "لا يوجد وصف إضافي للخبر. "
            "اعتمد على العنوان والمعلومات المتاحة فقط."
        )


    prompt = f"""
أنت محرر الأخبار الرئيسي في منصة NOWNEX العربية.

مهمتك إنشاء نسخة عربية احترافية للخبر التالي.

المصدر:
{source}

القسم:
{category}

العنوان الأصلي:
{title}

المعلومات المتاحة:
{description}


============================================================
المطلوب
============================================================

أعد حقلين فقط:

title_ar
summary_ar


============================================================
العنوان العربي
============================================================

اكتب عنوانًا صحفيًا احترافيًا باللغة العربية الفصحى.

لا تنسخ العنوان الأصلي حرفيًا.

لا تكتب العنوان بالإنجليزية.


============================================================
الملخص العربي
============================================================

اكتب ملخصًا باللغة العربية الفصحى من 3 إلى 5 جمل.

يجب أن يكون واضحًا ومناسبًا لموقع أخبار.

أعد صياغة المعلومات بدل ترجمتها حرفيًا.


============================================================
اللغة
============================================================

الخبر عربي فقط.

ممنوع كتابة جمل إنجليزية.

ممنوع كتابة فقرات إنجليزية.

يمكن استخدام أسماء الشركات والأشخاص والمنتجات العالمية
عند الضرورة فقط.

أمثلة مسموحة:

OpenAI
Google
Microsoft
Apple
Tesla
ChatGPT
Gemini
NASA
BMW

لكن لا تستخدم الإنجليزية في جملة كاملة.


============================================================
المصداقية
============================================================

لا تخترع معلومات.

لا تخترع أرقامًا.

لا تخترع أسماء.

لا تخترع تصريحات.

لا تخترع تواريخ.

لا تضف رأيًا شخصيًا.

اعتمد فقط على المعلومات الموجودة في المصدر.


============================================================
التنسيق
============================================================

لا تستخدم Markdown.

لا تستخدم Emojis.

لا تستخدم قوائم.

أرسل JSON صالحًا فقط.


============================================================
JSON
============================================================

{{
  "title_ar": "عنوان عربي احترافي",
  "summary_ar": "ملخص عربي من ثلاث إلى خمس جمل."
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

                "Gemini status:",
                response.status_code

            )


            # ------------------------------------------------
            # RATE LIMIT
            # ------------------------------------------------

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

                    f"Rate limit. "
                    f"Waiting {wait}s."

                )


                time.sleep(
                    wait
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
            # JSON
            # ------------------------------------------------

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


            print(
                "Arabic title:",
                title_ar
            )


            # ------------------------------------------------
            # VALIDATE
            # ------------------------------------------------

            if not article_is_valid(

                title_ar,

                summary_ar

            ):

                print(
                    "Arabic validation failed."
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
                    summary_ar

            }


        except Exception as error:

            print(
                "Gemini ERROR:",
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
# LOAD OLD NEWS
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
# BUILD NEWS ITEM
# ============================================================

def build_news_item(
    article,
    ai
):

    category = article.get(
        "category",
        ""
    )


    image = (

        article.get(
            "image",
            ""
        )

        or

        FALLBACK_IMAGES.get(
            category,
            ""
        )

    )


    return {

        "title_ar":
            ai["title_ar"],

        "summary_ar":
            ai["summary_ar"],


        # توافق مع index.html الحالي
        "title":
            ai["title_ar"],

        "summary":
            ai["summary_ar"],

        "description":
            ai["summary_ar"],


        "category":
            category,

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
        " EXTERNAL IMAGES ONLY"
    )

    print(
        "=========================================="
    )


    # ========================================================
    # OLD DATA
    # ========================================================

    old_news = load_existing_news()


    # ========================================================
    # RSS
    # ========================================================

    articles = get_news()


    if not articles:

        print(
            "No RSS articles found."
        )

        print(
            "Keeping existing news.json."
        )

        return


    # ========================================================
    # CATEGORY POOLS
    # ========================================================

    pools = {

        category: []

        for category in MAIN_CATEGORIES

    }


    for category in MAIN_CATEGORIES:

        category_articles = (

            get_category_articles(

                articles,

                category

            )

        )


        pools[category] = (

            category_articles[
                :CANDIDATES_PER_CATEGORY
            ]

        )


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


            key = normalize_title(

                article.get(
                    "title",
                    ""
                )

            )


            if key in used_original_titles:

                continue


            used_original_titles.add(
                key
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
                    "✗ Rejected."
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
                "✓ Accepted."
            )


            time.sleep(
                REQUEST_DELAY
            )


        print(

            f"{category}: "
            f"{len(generated[category])} generated"

        )


    # ========================================================
    # OLD NEWS BY CATEGORY
    # ========================================================

    old_by_category = {

        category: []

        for category in MAIN_CATEGORIES

    }


    for item in old_news:

        category = item.get(
            "category"
        )


        if category not in MAIN_CATEGORIES:

            continue


        if not item.get(
            "title_ar"
        ):

            continue


        if not item.get(
            "summary_ar"
        ):

            continue


        old_by_category[
            category
        ].append(
            item
        )


    # ========================================================
    # FINAL ASSEMBLY
    # ========================================================

    final_news = []

    final_keys = set()


    for category in MAIN_CATEGORIES:

        print(
            "\nFINALIZING:",
            category
        )


        # ----------------------------------------------------
        # NEW ARTICLES
        # ----------------------------------------------------

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


            current_count = len(

                get_category_articles(

                    final_news,

                    category

                )

            )


            if current_count >= MIN_PER_CATEGORY:

                break


        # ----------------------------------------------------
        # OLD ARTICLES FALLBACK
        # ----------------------------------------------------

        current_count = len(

            get_category_articles(

                final_news,

                category

            )

        )


        if current_count < MIN_PER_CATEGORY:

            print(
                "Using previous valid articles as fallback."
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


                # إذا لم تكن هناك صورة في الخبر القديم
                # نستخدم صورة القسم.
                if not item.get(
                    "image"
                ):

                    item["image"] = (
                        FALLBACK_IMAGES.get(
                            category,
                            ""
                        )
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
    # STRICT CATEGORY CHECK
    # ========================================================

    missing = []


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
    # PROTECT EXISTING DATA
    # ========================================================

    if missing:

        print(
            "\nWARNING!"
        )


        print(
            "Missing categories:",
            missing
        )


        print(
            "The update is incomplete."
        )


        print(
            "Existing news.json will NOT be replaced."
        )


        return


    # ========================================================
    # EXACTLY 3 PER CATEGORY
    # ========================================================

    cleaned_final = []


    for category in MAIN_CATEGORIES:

        category_items = (

            get_category_articles(

                final_news,

                category

            )

        )


        cleaned_final.extend(

            category_items[
                :MIN_PER_CATEGORY
            ]

        )


    final_news = cleaned_final


    # ========================================================
    # FINAL SAFETY
    # ========================================================

    if len(final_news) != 21:

        print(
            "ERROR: Final news count is not 21."
        )


        print(
            "Keeping existing news.json."
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
        " NOWNEX UPDATE SUCCESSFUL"
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
        "\nNo news images were downloaded."
    )

    print(
        "Only image URLs are stored in news.json."
    )

    print(
        "=========================================="
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
