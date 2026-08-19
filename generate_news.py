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
# NOWNEX — Bilingual Arabic / English News Engine
# 24+ ARTICLES / MULTI CATEGORY
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

# عدد الأخبار المستهدف
MAX_NEWS = 24

# الحد الأدنى المطلوب من كل قسم
MIN_PER_CATEGORY = 3

REQUEST_TIMEOUT = 25

# تأخير بين طلبات Gemini
REQUEST_DELAY = 8


# ============================================================
# MAIN WEBSITE CATEGORIES
# ============================================================

MAIN_CATEGORIES = [
    "Trending",
    "AI",
    "Technology",
    "Cars",
    "Entertainment",
    "World",
    "Facts",
    "Products"
]


# ============================================================
# NEWS SOURCES
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
        "q=artificial%20intelligence"
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
        "q=cars%20automotive"
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
        "q=entertainment%20movies%20music"
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
        "Reuters World",
        "https://feeds.reuters.com/reuters/worldNews",
        "World"
    ),


    # ========================================================
    # FACTS / KNOWLEDGE
    # ========================================================

    (
        "Google News Science Facts",
        "https://news.google.com/rss/search?"
        "q=science%20facts%20discovery"
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

    (
        "ScienceDaily",
        "https://www.sciencedaily.com/rss/top/science.xml",
        "Facts"
    ),


    # ========================================================
    # PRODUCTS
    # ========================================================

    (
        "Google News Products",
        "https://news.google.com/rss/search?"
        "q=best%20new%20products%20gadgets"
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
# VALID CATEGORIES
# ============================================================

VALID_CATEGORIES = {
    "World",
    "Technology",
    "Entertainment",
    "AI",
    "Cars",
    "Facts",
    "Products"
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

def get_best_image(entry, link):

    image = extract_rss_image(entry)

    if image:
        return image

    return get_og_image(link)


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
            "لا يوجد وصف إضافي متاح. "
            "اعتمد على العنوان فقط."
        )


    prompt = f"""
أنت محرر الأخبار الرئيسي في منصة NOWNEX.

المطلوب إنشاء نسخة ثنائية اللغة للخبر التالي.

المصدر:
{source}

التصنيف:
{category}

العنوان الأصلي:
{title}

المعلومات المتاحة:
{description}

أرسل JSON فقط بهذا الشكل:

{{
  "title_ar": "عنوان عربي احترافي",
  "summary_ar": "ملخص عربي من 3 إلى 5 جمل",
  "title_en": "Professional English headline",
  "summary_en": "English summary of 3 to 5 sentences"
}}

القواعد المهمة:

1. اكتب العربية بالفصحى.
2. اكتب الإنجليزية بلغة صحفية طبيعية واحترافية.
3. العربية والإنجليزية يجب أن تنقلا نفس المعلومات.
4. لا تخترع أي معلومة.
5. لا تخترع أسماء أو أرقامًا أو تصريحات.
6. لا تضف رأيًا شخصيًا.
7. اعتمد فقط على المعلومات المتاحة.
8. لا تترجم ترجمة حرفية ركيكة.
9. اجعل العنوان العربي مناسبًا للأخبار.
10. اجعل العنوان الإنجليزي مناسبًا للأخبار.
11. الملخص العربي من 3 إلى 5 جمل.
12. الملخص الإنجليزي من 3 إلى 5 جمل.
13. أرسل JSON صالحًا فقط بدون Markdown.
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
        x for x in articles
        if x.get("category") == category
    ]


# ============================================================
# SELECT NEWS
# ============================================================

def select_news(articles):

    selected = []

    selected_keys = set()


    # ========================================================
    # STEP 1
    # ضمان وجود 3 أخبار لكل قسم قدر الإمكان
    # ========================================================

    for category in MAIN_CATEGORIES:

        category_articles = get_category_articles(
            articles,
            category
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
    # إضافة أي أخبار إضافية حتى الوصول إلى MAX_NEWS
    # ========================================================

    if len(selected) < MAX_NEWS:

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


    # ========================================================
    # STEP 3
    # إذا توفر أكثر من MAX_NEWS
    # لا نريد تجاوز الرقم المحدد
    # ========================================================

    return selected[:MAX_NEWS]


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("==============================")
    print(" NOWNEX BILINGUAL NEWS ENGINE")
    print("==============================")
    print("")
    print(
        "Target:",
        MAX_NEWS,
        "articles"
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
    # PRINT CATEGORY COUNTS
    # ========================================================

    print("")
    print("Available by category:")


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
        "Selected:",
        len(selected)
    )


    final_news = []


    # ========================================================
    # PROCESS WITH GEMINI
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


        if not ai:

            print(
                "✗ Article skipped."
            )

            continue


        item = {

            # =================================================
            # ARABIC
            # =================================================

            "title_ar":
                ai["title_ar"],

            "summary_ar":
                ai["summary_ar"],


            # =================================================
            # ENGLISH
            # =================================================

            "title_en":
                ai["title_en"],

            "summary_en":
                ai["summary_en"],


            # =================================================
            # BACKWARD COMPATIBILITY
            # =================================================

            "title":
                ai["title_ar"],

            "summary":
                ai["summary_ar"],

            "description":
                ai["summary_ar"],


            # =================================================
            # ORIGINAL DATA
            # =================================================

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
            "✓ Arabic article created"
        )

        print(
            "✓ English article created"
        )


        if item["image"]:

            print(
                "✓ Image available"
            )

        else:

            print(
                "⚠ No image"
            )


        # =====================================================
        # DELAY
        # =====================================================

        time.sleep(
            REQUEST_DELAY
        )


    # ========================================================
    # SAFETY
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


    # ========================================================
    # FINAL REPORT
    # ========================================================

    print("")
    print("==============================")
    print(" NOWNEX NEWS UPDATED")
    print(
        "Articles generated:",
        len(final_news)
    )
    print("==============================")


    print("")
    print("Final categories:")


    for category in MAIN_CATEGORIES:

        count = len([

            x for x in final_news

            if x.get("category") ==
            category

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
