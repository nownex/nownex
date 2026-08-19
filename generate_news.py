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
# BATCH VERSION
# ============================================================


# ============================================================
# API
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


GEMINI_MODEL = "gemini-3.6-flash"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{GEMINI_MODEL}:generateContent"
)


# ============================================================
# SETTINGS
# ============================================================

MAX_NEWS = 24

MIN_PER_CATEGORY = 3

BATCH_SIZE = 6

REQUEST_TIMEOUT = 30

GEMINI_TIMEOUT = 120

BATCH_DELAY = 5


# ============================================================
# WEBSITE CATEGORIES
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
        "Google News World English",
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
        "q=science%20discovery"
        "&hl=en&gl=US&ceid=US:en",
        "Facts"
    ),

    (
        "Google News Facts",
        "https://news.google.com/rss/search?"
        "q=science%20facts"
        "&hl=en&gl=US&ceid=US:en",
        "Facts"
    ),

    (
        "Google News Facts Arabic",
        "https://news.google.com/rss/search?"
        "q=%D8%AD%D9%82%D8%A7%D8%A6%D9%82%20%D8%B9%D9%84%D9%85%D9%8A%D8%A9"
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
        "q=new%20gadgets%20devices"
        "&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Smartphones",
        "https://news.google.com/rss/search?"
        "q=new%20smartphones"
        "&hl=en&gl=US&ceid=US:en",
        "Products"
    ),

    (
        "Google News Products Arabic",
        "https://news.google.com/rss/search?"
        "q=%D9%85%D9%86%D8%AA%D8%AC%D8%A7%D8%AA%20%D8%AC%D8%AF%D9%8A%D8%AF%D8%A9"
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
        "NOWNEX/2.0 NewsBot",

    "Accept":
        "application/rss+xml, application/xml, "
        "text/xml, text/html"

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

    title = clean_text(title).lower()

    title = re.sub(
        r"[^\w\u0600-\u06FF]+",
        "",
        title
    )

    return title


# ============================================================
# RSS IMAGE
# ============================================================

def extract_rss_image(entry):

    media_content = entry.get(
        "media_content",
        []
    )

    for media in media_content:

        url = (
            media.get("url")
            or media.get("href")
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
            or media.get("href")
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
            or enclosure.get("url")
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
# CATEGORY ARTICLES
# ============================================================

def get_category_articles(
    articles,
    category
):

    return [
        article
        for article in articles
        if article.get("category") == category
    ]


# ============================================================
# SELECT NEWS
# ============================================================

def select_news(articles):

    selected = []

    selected_keys = set()


    # ========================================================
    # FIRST: 3 FROM EACH CATEGORY
    # ========================================================

    print("")
    print("Selecting minimum articles per category...")


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


        print(
            f"{category}: {count}"
        )


    # ========================================================
    # ADD EXTRA ARTICLES
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


    return selected[:MAX_NEWS]


# ============================================================
# GEMINI RESPONSE CLEANING
# ============================================================

def clean_json_text(text):

    text = str(text or "").strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return text.strip()


# ============================================================
# VALID GENERATED ARTICLE
# ============================================================

def generated_article_is_valid(item):

    if not isinstance(
        item,
        dict
    ):
        return False


    title_ar = clean_text(
        item.get(
            "title_ar",
            ""
        )
    )

    summary_ar = clean_text(
        item.get(
            "summary_ar",
            ""
        )
    )

    title_en = clean_text(
        item.get(
            "title_en",
            ""
        )
    )

    summary_en = clean_text(
        item.get(
            "summary_en",
            ""
        )
    )


    if not title_ar:
        return False

    if not title_en:
        return False

    if not summary_ar:
        return False

    if not summary_en:
        return False


    if len(summary_ar) < 60:
        return False

    if len(summary_en) < 60:
        return False


    return True


# ============================================================
# GEMINI BATCH
# ============================================================

def ask_gemini_batch(
    batch
):

    if not batch:
        return []


    articles_text = []


    for index, article in enumerate(
        batch,
        start=1
    ):

        title = article.get(
            "title",
            ""
        )

        description = article.get(
            "description",
            ""
        )

        if not description:

            description = (
                "No additional description "
                "is available."
            )


        # نحد الوصف حتى لا يكبر الطلب بشكل مبالغ
        description = description[:4000]


        articles_text.append(
            f"""
ARTICLE {index}

Source:
{article.get("source", "")}

Category:
{article.get("category", "")}

Original title:
{title}

Available information:
{description}
"""
        )


    joined_articles = "\n".join(
        articles_text
    )


    prompt = f"""
You are the senior news editor of NOWNEX.

Process the following {len(batch)} news articles.

For EVERY article, create:

1. Professional Arabic headline.
2. Arabic summary of 3 to 5 sentences.
3. Professional English headline.
4. English summary of 3 to 5 sentences.

IMPORTANT:

- Return EXACTLY {len(batch)} objects.
- Keep the SAME order as ARTICLE 1, ARTICLE 2, etc.
- Do not merge articles.
- Do not omit any article.
- Do not invent facts.
- Do not invent names.
- Do not invent numbers.
- Do not invent quotes.
- Use only the information provided.
- Arabic must be Modern Standard Arabic.
- English must sound like natural professional journalism.
- The Arabic and English versions must describe the same event.
- Do not add personal opinions.
- Do not write Markdown.

Return ONLY valid JSON in this exact format:

{{
  "articles": [
    {{
      "title_ar": "...",
      "summary_ar": "...",
      "title_en": "...",
      "summary_en": "..."
    }}
  ]
}}

Here are the articles:

{joined_articles}
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
                f"Gemini batch request "
                f"{attempt}/3 "
                f"({len(batch)} articles)"
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


            # =================================================
            # RATE LIMIT
            # =================================================

            if response.status_code == 429:

                if attempt == 1:
                    wait_time = 30

                elif attempt == 2:
                    wait_time = 60

                else:
                    wait_time = 90


                print(
                    "Gemini rate limit."
                )

                print(
                    f"Waiting {wait_time} seconds..."
                )


                time.sleep(
                    wait_time
                )

                continue


            # =================================================
            # OTHER ERROR
            # =================================================

            if response.status_code != 200:

                print(
                    "Gemini error response:"
                )

                print(
                    response.text[:2000]
                )

                if attempt < 3:

                    time.sleep(
                        20
                    )

                    continue

                return []


            # =================================================
            # PARSE RESPONSE
            # =================================================

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


            text = clean_json_text(
                text
            )


            result = json.loads(
                text
            )


            generated = result.get(
                "articles",
                []
            )


            if not isinstance(
                generated,
                list
            ):
                return []


            # =================================================
            # VALIDATE COUNT
            # =================================================

            if len(generated) != len(batch):

                print(
                    "Gemini returned "
                    f"{len(generated)} "
                    "instead of "
                    f"{len(batch)}."
                )

                if attempt < 3:

                    time.sleep(
                        10
                    )

                    continue

                return []


            valid = []


            for item in generated:

                if generated_article_is_valid(
                    item
                ):

                    valid.append({

                        "title_ar":
                            clean_text(
                                item.get(
                                    "title_ar",
                                    ""
                                )
                            ),

                        "summary_ar":
                            clean_text(
                                item.get(
                                    "summary_ar",
                                    ""
                                )
                            ),

                        "title_en":
                            clean_text(
                                item.get(
                                    "title_en",
                                    ""
                                )
                            ),

                        "summary_en":
                            clean_text(
                                item.get(
                                    "summary_en",
                                    ""
                                )
                            )

                    })

                else:

                    valid.append(None)


            return valid


        except Exception as error:

            print(
                "Gemini batch error:",
                error
            )


            if attempt < 3:

                time.sleep(
                    20
                )


    return []


# ============================================================
# PROCESS BATCH
# ============================================================

def process_batch(
    batch
):

    # ========================================================
    # TRY FULL BATCH
    # ========================================================

    result = ask_gemini_batch(
        batch
    )


    if result and len(result) == len(batch):

        return result


    # ========================================================
    # IF FAILED — SPLIT IN HALF
    # ========================================================

    print("")
    print(
        "Batch failed."
    )

    print(
        "Splitting batch into smaller batches..."
    )


    if len(batch) <= 1:

        return [None]


    middle = len(batch) // 2


    first_half = batch[
        :middle
    ]

    second_half = batch[
        middle:
    ]


    first_result = process_batch(
        first_half
    )


    time.sleep(
        BATCH_DELAY
    )


    second_result = process_batch(
        second_half
    )


    return (
        first_result +
        second_result
    )


# ============================================================
# FALLBACK ARTICLE
# ============================================================

def create_fallback_article(
    article
):

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


    if not description:

        description = (
            "NOWNEX was unable to generate "
            "an extended summary for this story."
        )


    # هذا الاحتياط يمنع اختفاء الخبر بالكامل
    # إذا فشل Gemini في خبر معين.

    return {

        "title_ar":
            title,

        "summary_ar":
            description,

        "title_en":
            title,

        "summary_en":
            description

    }


# ============================================================
# BUILD FINAL ARTICLE
# ============================================================

def build_final_article(
    original,
    generated
):

    if generated:

        ai = generated

    else:

        print(
            "⚠ Using fallback for:",
            original.get(
                "title",
                ""
            )
        )

        ai = create_fallback_article(
            original
        )


    return {

        # =====================================================
        # ARABIC
        # =====================================================

        "title_ar":
            ai["title_ar"],

        "summary_ar":
            ai["summary_ar"],


        # =====================================================
        # ENGLISH
        # =====================================================

        "title_en":
            ai["title_en"],

        "summary_en":
            ai["summary_en"],


        # =====================================================
        # BACKWARD COMPATIBILITY
        # =====================================================

        "title":
            ai["title_ar"],

        "summary":
            ai["summary_ar"],

        "description":
            ai["summary_ar"],


        # =====================================================
        # ORIGINAL DATA
        # =====================================================

        "category":
            original.get(
                "category",
                "World"
            ),

        "source":
            original.get(
                "source",
                "NOWNEX"
            ),

        "link":
            original.get(
                "link",
                ""
            ),

        "image":
            original.get(
                "image",
                ""
            ),

        "published":
            original.get(
                "published",
                ""
            ),

        "publishedAt":
            datetime.now(
                timezone.utc
            ).isoformat()

    }


# ============================================================
# SAVE JSON
# ============================================================

def save_news(
    final_news
):

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


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("======================================")
    print(" NOWNEX NEWS ENGINE — BATCH VERSION")
    print("======================================")
    print("")

    print(
        "Target articles:",
        MAX_NEWS
    )

    print(
        "Minimum per category:",
        MIN_PER_CATEGORY
    )

    print(
        "Batch size:",
        BATCH_SIZE
    )

    print("")


    # ========================================================
    # GET RSS
    # ========================================================

    articles = get_news()


    if not articles:

        print(
            "No RSS articles found."
        )

        return


    print("")
    print(
        "Total RSS articles:",
        len(articles)
    )


    # ========================================================
    # CATEGORY REPORT
    # ========================================================

    print("")
    print(
        "RSS articles by category:"
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
        "Selected articles:",
        len(selected)
    )


    if not selected:

        print(
            "Nothing selected."
        )

        return


    # ========================================================
    # SPLIT INTO BATCHES
    # ========================================================

    batches = [

        selected[i:i + BATCH_SIZE]

        for i in range(
            0,
            len(selected),
            BATCH_SIZE
        )

    ]


    print("")
    print(
        "Gemini batches:",
        len(batches)
    )


    # ========================================================
    # PROCESS
    # ========================================================

    generated_results = []


    for batch_index, batch in enumerate(
        batches,
        start=1
    ):

        print("")
        print(
            "======================================"
        )

        print(
            f"Processing batch "
            f"{batch_index}/{len(batches)}"
        )

        print(
            "Articles in batch:",
            len(batch)
        )

        print(
            "======================================"
        )


        result = process_batch(
            batch
        )


        if len(result) != len(batch):

            print(
                "⚠ Unexpected batch result."
            )


            while len(result) < len(batch):

                result.append(
                    None
                )


            result = result[
                :len(batch)
            ]


        generated_results.extend(
            result
        )


        if batch_index < len(batches):

            print(
                f"Waiting {BATCH_DELAY} seconds..."
            )

            time.sleep(
                BATCH_DELAY
            )


    # ========================================================
    # BUILD FINAL NEWS
    # ========================================================

    final_news = []


    for index, article in enumerate(
        selected
    ):

        generated = None


        if index < len(
            generated_results
        ):

            generated = (
                generated_results[index]
            )


        item = build_final_article(
            article,
            generated
        )


        final_news.append(
            item
        )


        print(
            f"✓ Final article "
            f"{len(final_news)}/{len(selected)}"
        )


    # ========================================================
    # SAFETY
    # ========================================================

    if not final_news:

        print("")
        print(
            "No final articles generated."
        )

        print(
            "Keeping existing news.json."
        )

        return


    # ========================================================
    # SAVE
    # ========================================================

    save_news(
        final_news
    )


    # ========================================================
    # FINAL REPORT
    # ========================================================

    print("")
    print("======================================")
    print(" NOWNEX NEWS UPDATED")
    print("======================================")

    print(
        "Articles saved:",
        len(final_news)
    )


    print("")
    print(
        "Final categories:"
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
    print(
        "news.json successfully created."
    )

    print("")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
