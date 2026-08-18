import os
import json
import re
import html
import time
from datetime import datetime, timezone

import requests
import feedparser


# ============================================================
# NOWNEX — Arabic News Generator
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


# Gemini model
GEMINI_MODEL = "gemini-2.5-flash"

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
# REMOVE DUPLICATES
# ============================================================

def normalize_title(title):

    title = title.lower()

    title = re.sub(
        r"[^\w\u0600-\u06FF]+",
        "",
        title
    )

    return title


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
# READ RSS NEWS
# ============================================================

def get_news():

    articles = []

    for source_name, feed_url in RSS_FEEDS:

        print(
            "Reading news from:",
            source_name
        )

        try:

            feed = feedparser.parse(
                feed_url
            )

            for entry in feed.entries[:15]:

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

                articles.append(
                    {
                        "title": title,
                        "description": description,
                        "link": link,
                        "source": source_name
                    }
                )

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
# GEMINI
# ============================================================

def ask_gemini(
    title,
    description,
    source
):

    prompt = f"""
أنت رئيس تحرير منصة إخبارية عربية احترافية اسمها NOWNEX.

أريد منك تحويل الخبر التالي إلى خبر عربي مختصر
ومفهوم للقارئ العربي.

المصدر:
{source}

العنوان الأصلي:
{title}

المعلومات المتاحة:
{description}

أعد النتيجة بصيغة JSON فقط.

الصيغة:

{{
  "title": "عنوان عربي احترافي",
  "summary": "ملخص عربي واضح من 3 إلى 5 جمل",
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

القواعد المهمة:

1. اكتب بالعربية الفصحى.
2. لا تترجم ترجمة حرفية.
3. اجعل العنوان جذابًا لكن غير مبالغ فيه.
4. لا تضف أي معلومة غير موجودة في النص.
5. لا تخترع أرقامًا أو تصريحات.
6. لا تقدم رأيًا شخصيًا.
7. إذا كان الخبر غير واضح، حافظ على المعلومات المؤكدة فقط.
8. الملخص يجب أن يشرح للقارئ ماذا حدث ولماذا الخبر مهم.
9. لا تضع Markdown.
10. أرسل JSON فقط بدون أي كلام قبله أو بعده.
"""

    payload = {

        "contents": [

            {
                "parts": [

                    {
                        "text": prompt
                    }

                ]
            }

        ],

        "generationConfig": {

            "temperature": 0.2,

            "responseMimeType": "application/json"

        }

    }


    headers = {

        "Content-Type":
            "application/json",

        "x-goog-api-key":
            API_KEY

    }


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
            "Gemini API request failed."
        )


    data = response.json()


    try:

        text = (
            data
            ["candidates"]
            [0]
            ["content"]
            ["parts"]
            [0]
            ["text"]
        )

    except Exception:

        print(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            )
        )

        raise RuntimeError(
            "Invalid Gemini response."
        )


    text = text.strip()


    # Remove accidental Markdown fences

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


    return {

        "title":
            clean_text(
                result.get(
                    "title",
                    title
                )
            ),

        "summary":
            clean_text(
                result.get(
                    "summary",
                    description
                )
            ),

        "category":
            result.get(
                "category",
                "World"
            )

    }


# ============================================================
# CATEGORY VALIDATION
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


def valid_category(category):

    if category in VALID_CATEGORIES:

        return category

    return "World"


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("==============================")
    print(" NOWNEX NEWS ENGINE")
    print("==============================")
    print("")


    articles = get_news()


    if not articles:

        raise RuntimeError(
            "No news articles found."
        )


    print(
        "Found",
        len(articles),
        "articles."
    )


    # Limit the number sent to Gemini

    articles = articles[
        :MAX_NEWS
    ]


    final_news = []


    for index, article in enumerate(
        articles,
        start=1
    ):

        print("")
        print(
            f"Processing {index}/{len(articles)}"
        )

        print(
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

                "category":
                    valid_category(
                        ai["category"]
                    ),

                "source":
                    article["source"],

                "link":
                    article["link"],

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


        except Exception as error:

            print(
                "Gemini failed:",
                error
            )

            # Keep the original article
            # if Gemini temporarily fails.

            final_news.append(

                {

                    "title":
                        article["title"],

                    "summary":
                        article["description"],

                    "description":
                        article["description"],

                    "category":
                        "World",

                    "source":
                        article["source"],

                    "link":
                        article["link"],

                    "publishedAt":
                        datetime.now(
                            timezone.utc
                        ).isoformat()

                }

            )


        # Small delay between requests

        time.sleep(2)


    # ========================================================
    # CREATE news.json
    # ========================================================

    output = {

        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),

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
