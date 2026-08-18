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
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )


# ============================================================
# GEMINI MODEL
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

    for source_name, feed_url in RSS_FEEDS:

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

                # Some feeds provide content
                # instead of summary/description.

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
# CHECK SUMMARY
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

    # Must be meaningfully longer than the title.

    if len(summary_clean) < 120:
        return False

    # If the summary is almost exactly the title,
    # reject it.

    if summary_clean.lower() == title_clean.lower():
        return False

    # Count sentences.

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

    # If RSS has very little information,
    # explicitly tell Gemini not to invent anything.

    if not description:

        description = (
            "لا يوجد وصف إضافي متاح من مصدر RSS. "
            "اعتمد على العنوان فقط ولا تخترع تفاصيل."
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

اكتب النتيجة في JSON فقط بهذا الشكل:

{{
  "title": "عنوان عربي احترافي",
  "summary": "ملخص عربي من 3 إلى 5 جمل يشرح ما حدث وأهميته",
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
- الملخص يجب أن يكون مختلفًا عن العنوان.
- الملخص يجب أن يحتوي على 3 إلى 5 جمل.
- اشرح ما حدث بناءً على المعلومات المتاحة فقط.
- لا تخترع أسماء أو أرقامًا أو تصريحات أو أحداثًا.
- لا تضف رأيًا شخصيًا.
- إذا كانت المعلومات ناقصة، قل فقط ما يمكن تأكيده.
- لا تستخدم Markdown.
- لا تستخدم علامات اقتباس حول JSON.
- أرسل JSON صالحًا فقط.
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

            "temperature": 0.3,

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

    # Retry Gemini up to 3 times.

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

                # Do not repeat requests when the
                # model itself is unavailable.

                if response.status_code == 404:

                    raise RuntimeError(
                        "Gemini model is unavailable: "
                        f"{GEMINI_MODEL}"
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

            # Remove accidental markdown fences.

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

            new_category = result.get(
                "category",
                "World"
            )

            if not new_title:

                raise RuntimeError(
                    "Gemini returned an empty title."
                )

            if not summary_is_valid(
                title,
                new_summary
            ):

                raise RuntimeError(
                    "Gemini returned an invalid or "
                    "too-short summary."
                )

            if new_category not in VALID_CATEGORIES:

                new_category = "World"

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
        f"Gemini failed after 3 attempts: {last_error}"
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

    print(
        "Found:",
        len(articles),
        "articles"
    )

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

                "category":
                    ai["category"],

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
                "✓ Gemini Arabic summary created"
            )

            print(
                "Title:",
                ai["title"]
            )

            print(
                "Summary:",
                ai["summary"]
            )

        except Exception as error:

            # Do NOT publish an unsummarized article.

            print(
                "✗ Article rejected:",
                error
            )

        time.sleep(2)

    # If Gemini failed for every article,
    # stop the workflow.

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
