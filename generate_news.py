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
# GEMINI
# ============================================================

# النموذج الجديد الذي طلبته Google API في الخطأ السابق
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

                # بعض المصادر تستخدم content بدلاً من summary

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
# VALIDATE SUMMARY
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

    # الملخص يجب أن يكون مفيدًا وليس جملة قصيرة جدًا

    if len(summary_clean) < 120:
        return False

    # لا نريد تكرار العنوان فقط

    if summary_clean.lower() == title_clean.lower():
        return False

    # يجب أن يحتوي على جملتين على الأقل

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
# VALIDATE IMPORTANCE
# ============================================================

def importance_is_valid(
    importance
):

    importance_clean = clean_text(
        importance
    )

    if not importance_clean:
        return False

    # يجب أن يكون شرحًا حقيقيًا وليس كلمة أو جملة قصيرة جدًا

    if len(importance_clean) < 70:
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
            "لا يوجد وصف إضافي متاح من مصدر RSS. "
            "اعتمد على العنوان فقط ولا تخترع أي تفاصيل."
        )


    prompt = f"""
أنت رئيس تحرير منصة NOWNEX العربية.

مهمتك هي تحويل الخبر الموجود في البيانات أدناه
إلى محتوى إخباري عربي احترافي ومختصر.

المصدر:
{source}

العنوان الأصلي:
{title}

النص أو الوصف المتاح:
{description}


أعد النتيجة بصيغة JSON فقط بهذا الشكل:

{{
  "title": "عنوان عربي احترافي",
  "summary": "ملخص عربي من 3 إلى 5 جمل",
  "importance": "شرح عربي من جملتين يوضح لماذا هذا الخبر مهم للقارئ",
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


القواعد الصارمة:

1. استخدم العربية الفصحى الواضحة.

2. لا تترجم العنوان ترجمة حرفية.

3. اجعل العنوان مختصرًا وجذابًا دون مبالغة.

4. الملخص يجب أن يكون من 3 إلى 5 جمل.

5. الملخص يجب أن يشرح:
   ماذا حدث؟
   ومن المعني بالخبر؟
   وما أهم نتيجة أو تطور معروف؟

6. لا تكرر العنوان داخل الملخص.

7. خانة importance يجب أن تكون خاصة بهذا الخبر تحديدًا.

8. في importance اشرح لماذا يمكن أن يكون الخبر مهمًا أو مؤثرًا،
   بناءً فقط على المعلومات الموجودة في النص.

9. لا تستخدم عبارات عامة مثل:
   "هذا الخبر مهم جدًا"
   أو
   "يقدم NOWNEX هذا الخبر..."
   أو
   "يبقى هذا الخبر محط اهتمام..."

10. لا تكتب أي معلومة غير موجودة في البيانات.

11. لا تخترع أسماء أو أرقامًا أو تصريحات أو أحداثًا.

12. لا تضف رأيًا شخصيًا.

13. إذا كانت المعلومات ناقصة، استخدم فقط المعلومات المؤكدة.

14. لا تستخدم Markdown.

15. لا تضع JSON داخل علامات اقتباس إضافية.

16. أرسل JSON صالحًا فقط.

17. لا تكتب أي كلام قبل JSON أو بعده.
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

            "temperature": 0.25,

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


    # ========================================================
    # RETRY
    # ========================================================

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


            # إزالة Markdown إذا أرسله Gemini بالخطأ

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


            # =================================================
            # RESULT
            # =================================================

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


            # =================================================
            # VALIDATION
            # =================================================

            if not new_title:

                raise RuntimeError(
                    "Gemini returned an empty title."
                )


            if not summary_is_valid(
                title,
                new_summary
            ):

                raise RuntimeError(
                    "Gemini returned an invalid summary."
                )


            if not importance_is_valid(
                new_importance
            ):

                raise RuntimeError(
                    "Gemini returned an invalid importance."
                )


            if new_category not in VALID_CATEGORIES:

                new_category = "World"


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


    # ========================================================
    # GET NEWS
    # ========================================================

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


    # ========================================================
    # PROCESS ARTICLES
    # ========================================================

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

                "importance":
                    ai["importance"],

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
                "✓ Arabic article created"
            )


            print(
                "Title:",
                ai["title"]
            )


            print(
                "Summary:",
                ai["summary"]
            )


            print(
                "Importance:",
                ai["importance"]
            )


            print(
                "Category:",
                ai["category"]
            )


        except Exception as error:

            # لا ننشر خبرًا بدون تلخيص صحيح

            print(
                "✗ Article rejected:",
                error
            )


        # تأخير بسيط بين طلبات Gemini

        time.sleep(2)


    # ========================================================
    # MAKE SURE SOMETHING WAS CREATED
    # ========================================================

    if not final_news:

        raise RuntimeError(
            "Gemini did not successfully create "
            "any Arabic articles."
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
    # DONE
    # ========================================================

    print("")

    print("==============================")

    print(
        " NOWNEX NEWS UPDATED"
    )

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
