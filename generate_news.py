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
# NOWNEX — ARABIC ONLY NEWS ENGINE
# 7 CATEGORIES × 3 ARTICLES = 21 ARTICLES
# RSS -> IMAGE -> GEMINI ARABIC -> news.json
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing from GitHub Secrets.")

# You can override this from GitHub Secrets/Variables if needed.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{GEMINI_MODEL}:generateContent"
)

# ============================================================
# SETTINGS
# ============================================================

ARTICLES_PER_CATEGORY = 3
MAX_NEWS = 21

RSS_ENTRIES_PER_FEED = 20
CANDIDATES_PER_CATEGORY = 12

REQUEST_TIMEOUT = 25
GEMINI_TIMEOUT = 90

GEMINI_RETRIES = 3
REQUEST_DELAY = 2

MAIN_CATEGORIES = [
    "AI",
    "Technology",
    "Cars",
    "Entertainment",
    "World",
    "Facts",
    "Products",
]

# ============================================================
# RSS SOURCES
# ============================================================

RSS_FEEDS = [

    # AI
    (
        "TechCrunch AI",
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "AI",
    ),
    (
        "Google News AI",
        "https://news.google.com/rss/search?q=artificial%20intelligence&hl=en&gl=US&ceid=US:en",
        "AI",
    ),
    (
        "Google News AI Arabic",
        "https://news.google.com/rss/search?q=%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1%20%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A&hl=ar&gl=DZ&ceid=DZ:ar",
        "AI",
    ),
    (
        "The Verge AI",
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "AI",
    ),

    # Technology
    (
        "TechCrunch",
        "https://techcrunch.com/feed/",
        "Technology",
    ),
    (
        "The Verge",
        "https://www.theverge.com/rss/index.xml",
        "Technology",
    ),
    (
        "Ars Technica",
        "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "Technology",
    ),
    (
        "MIT Technology Review",
        "https://www.technologyreview.com/feed/",
        "Technology",
    ),

    # Cars
    (
        "Motor1",
        "https://www.motor1.com/rss/news/",
        "Cars",
    ),
    (
        "Car and Driver",
        "https://www.caranddriver.com/rss/all.xml",
        "Cars",
    ),
    (
        "Google News Cars",
        "https://news.google.com/rss/search?q=cars%20automotive%20vehicles&hl=en&gl=US&ceid=US:en",
        "Cars",
    ),

    # Entertainment
    (
        "Variety",
        "https://variety.com/feed/",
        "Entertainment",
    ),
    (
        "Hollywood Reporter",
        "https://www.hollywoodreporter.com/feed/",
        "Entertainment",
    ),
    (
        "Google News Entertainment",
        "https://news.google.com/rss/search?q=entertainment%20movies%20music%20games&hl=en&gl=US&ceid=US:en",
        "Entertainment",
    ),
    (
        "Google News Entertainment Arabic",
        "https://news.google.com/rss/search?q=%D8%AA%D8%B1%D9%81%D9%8A%D9%87%20%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D9%85%D9%88%D8%B3%D9%8A%D9%82%D9%89&hl=ar&gl=DZ&ceid=DZ:ar",
        "Entertainment",
    ),

    # World
    (
        "BBC Arabic",
        "https://feeds.bbci.co.uk/arabic/rss.xml",
        "World",
    ),
    (
        "Al Jazeera",
        "https://www.aljazeera.net/aljazeera.rss",
        "World",
    ),
    (
        "Google News World Arabic",
        "https://news.google.com/rss?hl=ar&gl=DZ&ceid=DZ:ar",
        "World",
    ),
    (
        "Google News World English",
        "https://news.google.com/rss/search?q=world%20news&hl=en&gl=US&ceid=US:en",
        "World",
    ),

    # Facts / Science
    (
        "ScienceDaily",
        "https://www.sciencedaily.com/rss/top/science.xml",
        "Facts",
    ),
    (
        "Google News Science",
        "https://news.google.com/rss/search?q=science%20discovery%20research&hl=en&gl=US&ceid=US:en",
        "Facts",
    ),
    (
        "Google News Facts Arabic",
        "https://news.google.com/rss/search?q=%D8%AD%D9%82%D8%A7%D8%A6%D9%82%20%D8%B9%D9%84%D9%85%D9%8A%D8%A9%20%D8%A7%D9%83%D8%AA%D8%B4%D8%A7%D9%81%D8%A7%D8%AA&hl=ar&gl=DZ&ceid=DZ:ar",
        "Facts",
    ),

    # Products
    (
        "Google News Products",
        "https://news.google.com/rss/search?q=new%20products%20gadgets&hl=en&gl=US&ceid=US:en",
        "Products",
    ),
    (
        "Google News Gadgets",
        "https://news.google.com/rss/search?q=new%20gadgets%20smartphones%20devices&hl=en&gl=US&ceid=US:en",
        "Products",
    ),
    (
        "Google News Products Arabic",
        "https://news.google.com/rss/search?q=%D9%85%D9%86%D8%AA%D8%AC%D8%A7%D8%AA%20%D8%AC%D8%AF%D9%8A%D8%AF%D8%A9%20%D9%87%D9%88%D8%A7%D8%AA%D9%81%20%D8%A3%D8%AC%D9%87%D8%B2%D8%A9&hl=ar&gl=DZ&ceid=DZ:ar",
        "Products",
    ),
]


# ============================================================
# HTTP
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "NOWNEX/3.0 NewsBot",
    "Accept": "application/rss+xml, application/xml, text/xml, text/html",
})


# ============================================================
# TEXT
# ============================================================

def clean_text(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_title(title):
    title = clean_text(title).lower()
    return re.sub(r"[^\w\u0600-\u06FF]+", "", title)


def remove_duplicates(items):
    result = []
    seen = set()

    for item in items:
        key = normalize_title(item.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)

    return result


# ============================================================
# ARABIC VALIDATION
# ============================================================

def arabic_count(text):
    return len(re.findall(r"[\u0600-\u06FF]", clean_text(text)))


def latin_count(text):
    return len(re.findall(r"[A-Za-z]", clean_text(text)))


def arabic_ratio(text):
    ar = arabic_count(text)
    en = latin_count(text)

    if ar + en == 0:
        return 0

    return ar / (ar + en)


def english_ratio(text):
    ar = arabic_count(text)
    en = latin_count(text)

    if ar + en == 0:
        return 0

    return en / (ar + en)


# These are proper names/technical names that can legitimately appear
# in an Arabic article.
ALLOWED_LATIN_WORDS = {
    "AI", "OpenAI", "Anthropic", "Google", "Microsoft", "Apple",
    "Samsung", "Tesla", "Meta", "Amazon", "Nvidia", "Intel", "AMD",
    "Sony", "Nintendo", "Netflix", "YouTube", "TikTok", "Instagram",
    "Facebook", "WhatsApp", "ChatGPT", "Gemini", "Claude", "GPT",
    "Android", "iPhone", "iOS", "Windows", "Xbox", "PlayStation",
    "BMW", "Mercedes", "Audi", "Toyota", "Honda", "Ford", "BYD",
    "Hyundai", "Kia", "Reuters", "BBC", "NASA", "SpaceX",
    "TechCrunch", "The Verge", "MIT", "Open", "AI4",
}


def strip_allowed_names(text):
    result = clean_text(text)

    for word in sorted(ALLOWED_LATIN_WORDS, key=len, reverse=True):
        result = re.sub(
            rf"\b{re.escape(word)}\b",
            " ",
            result,
            flags=re.IGNORECASE,
        )

    return clean_text(result)


def is_valid_arabic(text, minimum=8):
    text = clean_text(text)

    if len(text) < minimum:
        return False

    if arabic_count(text) < 5:
        return False

    cleaned = strip_allowed_names(text)

    if arabic_ratio(cleaned) < 0.70:
        return False

    # Reject obvious English sentences remaining in the Arabic field.
    if english_ratio(cleaned) > 0.18:
        return False

    return True


def summary_is_valid(title, summary):
    title = clean_text(title)
    summary = clean_text(summary)

    if not is_valid_arabic(summary, 100):
        return False

    if summary.lower() == title.lower():
        return False

    sentences = re.findall(r"[.!؟。]", summary)

    return len(sentences) >= 2


# ============================================================
# IMAGES
# ============================================================

def extract_rss_image(entry):
    for media in entry.get("media_content", []):
        url = media.get("url") or media.get("href")
        if url:
            return str(url).strip()

    for media in entry.get("media_thumbnail", []):
        url = media.get("url") or media.get("href")
        if url:
            return str(url).strip()

    for enclosure in entry.get("enclosures", []):
        url = enclosure.get("href") or enclosure.get("url")
        if url:
            return str(url).strip()

    source_text = (
        entry.get("summary", "")
        or entry.get("description", "")
    )

    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        str(source_text),
        re.IGNORECASE,
    )

    if match:
        return html.unescape(match.group(1).strip())

    return ""


def get_og_image(url):
    if not url:
        return ""

    try:
        response = SESSION.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        if response.status_code != 200:
            return ""

        page = response.text[:900000]

        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, page, re.IGNORECASE)

            if match:
                image = html.unescape(match.group(1).strip())
                image = urljoin(response.url, image)

                if image.startswith(("http://", "https://")):
                    return image

    except Exception as error:
        print("OG image error:", error)

    return ""


def get_best_image(entry, link):
    image = extract_rss_image(entry)

    if image:
        return image

    return get_og_image(link)


# ============================================================
# RSS
# ============================================================

def get_news():
    articles = []

    for source_name, feed_url, category in RSS_FEEDS:
        print("\n----------------------------------------")
        print("Reading:", source_name)
        print("Category:", category)

        try:
            feed = feedparser.parse(feed_url)
            entries = feed.entries[:RSS_ENTRIES_PER_FEED]

            print("Entries:", len(entries))

            for entry in entries:
                title = clean_text(entry.get("title", ""))

                if not title:
                    continue

                description = clean_text(
                    entry.get(
                        "summary",
                        entry.get("description", ""),
                    )
                )

                if not description:
                    content = entry.get("content", [])

                    if content:
                        try:
                            description = clean_text(
                                content[0].get("value", "")
                            )
                        except Exception:
                            pass

                link = str(entry.get("link", "")).strip()

                if not link:
                    continue

                image = get_best_image(entry, link)

                published = clean_text(
                    entry.get(
                        "published",
                        entry.get("updated", ""),
                    )
                )

                articles.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "source": source_name,
                    "category": category,
                    "image": image,
                    "published": published,
                })

        except Exception as error:
            print("RSS ERROR:", source_name, error)

    articles = remove_duplicates(articles)

    print("\nTOTAL RSS ARTICLES:", len(articles))

    return articles


# ============================================================
# EXISTING NEWS
# ============================================================

def load_existing_news():
    if not os.path.exists("news.json"):
        return []

    try:
        with open("news.json", "r", encoding="utf-8") as file:
            data = json.load(file)

        news = data.get("news", [])

        if isinstance(news, list):
            return news

    except Exception as error:
        print("Existing news error:", error)

    return []


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(article):
    title = article.get("title", "")
    description = article.get("description", "")
    source = article.get("source", "")
    category = article.get("category", "")

    if not description:
        description = (
            "لا يوجد وصف إضافي. "
            "اعتمد فقط على العنوان والمعلومات المتاحة."
        )

    prompt = f"""
أنت محرر الأخبار الرئيسي في منصة NOWNEX العربية.

اكتب نسخة عربية احترافية من الخبر التالي.

المصدر:
{source}

القسم:
{category}

العنوان الأصلي:
{title}

المعلومات المتاحة:
{description}

المطلوب JSON فقط، بحقلين:

title_ar
summary_ar

قواعد صارمة جدًا:

1. title_ar يجب أن يكون بالعربية الفصحى.
2. summary_ar يجب أن يكون بالعربية الفصحى.
3. لا تكتب أي جملة إنجليزية.
4. لا تضع نصًا إنجليزيًا كاملًا داخل الحقول.
5. أسماء الشركات والأشخاص والمنتجات والعلامات التجارية يمكن إبقاؤها
   باللاتينية عند الحاجة فقط، مثل OpenAI وGoogle وTesla وNASA وAI.
6. لا تخترع أي معلومة.
7. لا تخترع أرقامًا أو أسماء أو تواريخ أو تصريحات.
8. لا تضف رأيًا شخصيًا.
9. لا تنسخ النص حرفيًا.
10. أعد صياغة الخبر بالعربية بأسلوب صحفي واضح.
11. summary_ar من 3 إلى 5 جمل.
12. لا تستخدم Markdown.
13. لا تستخدم نقاطًا أو قوائم.
14. لا تستخدم رموزًا تعبيرية.

إذا كان المصدر باللغة الإنجليزية، ترجم المعلومات إلى العربية.
إذا كان المصدر باللغة العربية، أعد صياغتها بالعربية.

أرسل JSON صالحًا فقط:

{{
  "title_ar": "عنوان عربي احترافي",
  "summary_ar": "ملخص عربي من ثلاث إلى خمس جمل."
}}
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.15,
            "responseMimeType": "application/json",
        },
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY,
    }

    for attempt in range(1, GEMINI_RETRIES + 1):
        try:
            print(f"Gemini {attempt}/{GEMINI_RETRIES}")

            response = requests.post(
                GEMINI_URL,
                headers=headers,
                json=payload,
                timeout=GEMINI_TIMEOUT,
            )

            print("Gemini status:", response.status_code)

            if response.status_code == 429:
                wait = 30 * attempt
                print(f"Rate limit. Waiting {wait}s...")
                time.sleep(wait)
                continue

            if response.status_code != 200:
                print(response.text[:1200])

                if attempt < GEMINI_RETRIES:
                    time.sleep(15)
                    continue

                return None

            data = response.json()

            text = (
                data["candidates"][0]
                ["content"]["parts"][0]["text"]
                .strip()
            )

            text = re.sub(
                r"^```json\s*",
                "",
                text,
                flags=re.IGNORECASE,
            )

            text = re.sub(r"\s*```$", "", text)

            result = json.loads(text)

            title_ar = clean_text(result.get("title_ar", ""))
            summary_ar = clean_text(result.get("summary_ar", ""))

            if not is_valid_arabic(title_ar):
                print("Rejected: Arabic title validation failed.")
                if attempt < GEMINI_RETRIES:
                    time.sleep(4)
                    continue
                return None

            if not summary_is_valid(title_ar, summary_ar):
                print("Rejected: Arabic summary validation failed.")
                if attempt < GEMINI_RETRIES:
                    time.sleep(4)
                    continue
                return None

            return {
                "title_ar": title_ar,
                "summary_ar": summary_ar,
            }

        except Exception as error:
            print("Gemini error:", error)

            if attempt < GEMINI_RETRIES:
                time.sleep(10)

    return None


# ============================================================
# BUILD
# ============================================================

def build_news_item(article, ai):
    return {
        "title_ar": ai["title_ar"],
        "summary_ar": ai["summary_ar"],

        # Backward compatibility with the current frontend.
        "title": ai["title_ar"],
        "summary": ai["summary_ar"],
        "description": ai["summary_ar"],

        "category": article["category"],
        "source": article["source"],
        "link": article["link"],
        "image": article.get("image", ""),
        "published": article.get("published", ""),
        "publishedAt": datetime.now(timezone.utc).isoformat(),
    }


def category_articles(items, category):
    return [
        item for item in items
        if item.get("category") == category
    ]


# ============================================================
# MAIN
# ============================================================

def main():
    print("\n==========================================")
    print(" NOWNEX ARABIC NEWS ENGINE")
    print(" 7 CATEGORIES × 3 ARTICLES")
    print("==========================================")

    old_news = load_existing_news()
    rss_articles = get_news()

    if not rss_articles:
        print("No RSS data. Keeping existing news.json.")
        return

    pools = {
        category: []
        for category in MAIN_CATEGORIES
    }

    for category in MAIN_CATEGORIES:
        candidates = category_articles(
            rss_articles,
            category,
        )

        pools[category] = candidates[:CANDIDATES_PER_CATEGORY]

        print(
            f"{category}: "
            f"{len(pools[category])} candidates"
        )

    generated = {
        category: []
        for category in MAIN_CATEGORIES
    }

    used_original_titles = set()

    # ========================================================
    # Generate 3 fresh articles per category.
    # If one fails, try the next candidate.
    # ========================================================

    for category in MAIN_CATEGORIES:
        print("\n==========================================")
        print("PROCESSING:", category)
        print("==========================================")

        for article in pools[category]:

            if len(generated[category]) >= ARTICLES_PER_CATEGORY:
                break

            original_key = normalize_title(article["title"])

            if original_key in used_original_titles:
                continue

            used_original_titles.add(original_key)

            print("\nTrying:", article["title"])

            ai = ask_gemini(article)

            if not ai:
                print("Rejected. Trying next candidate.")
                continue

            item = build_news_item(article, ai)

            generated[category].append(item)

            print("ACCEPTED:", ai["title_ar"])

            if article.get("image"):
                print("Image: YES")
            else:
                print("Image: NO")

            time.sleep(REQUEST_DELAY)

        print(
            f"{category}: "
            f"{len(generated[category])} fresh articles"
        )

    # ========================================================
    # OLD NEWS FALLBACK
    # Only used to prevent a category from becoming empty.
    # ========================================================

    old_by_category = {
        category: []
        for category in MAIN_CATEGORIES
    }

    for item in old_news:
        category = item.get("category")

        if category not in old_by_category:
            continue

        if not item.get("title_ar"):
            continue

        if not item.get("summary_ar"):
            continue

        old_by_category[category].append(item)

    # ========================================================
    # ASSEMBLE
    # ========================================================

    final_news = []
    final_keys = set()

    for category in MAIN_CATEGORIES:

        # Fresh first.
        for item in generated[category]:
            key = normalize_title(item.get("title_ar", ""))

            if key in final_keys:
                continue

            final_keys.add(key)
            final_news.append(item)

            if len(category_articles(final_news, category)) >= ARTICLES_PER_CATEGORY:
                break

        # Old fallback.
        current = len(category_articles(final_news, category))

        if current < ARTICLES_PER_CATEGORY:
            for item in old_by_category[category]:
                key = normalize_title(item.get("title_ar", ""))

                if key in final_keys:
                    continue

                final_keys.add(key)
                final_news.append(item)
                current += 1

                if current >= ARTICLES_PER_CATEGORY:
                    break

        print(
            f"FINAL {category}: "
            f"{len(category_articles(final_news, category))}"
        )

    # ========================================================
    # SAFETY: never replace good news with incomplete data.
    # ========================================================

    missing = []

    for category in MAIN_CATEGORIES:
        count = len(category_articles(final_news, category))

        if count < ARTICLES_PER_CATEGORY:
            missing.append(category)

    if missing:
        print("\nINCOMPLETE UPDATE:")
        print(missing)
        print("Existing news.json will be kept unchanged.")
        return

    # ========================================================
    # SAVE
    # ========================================================

    final_news = final_news[:MAX_NEWS]

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(final_news),
        "news": final_news,
    }

    with open("news.json", "w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("\n==========================================")
    print(" NOWNEX NEWS UPDATED SUCCESSFULLY")
    print("==========================================")
    print("TOTAL:", len(final_news))

    for category in MAIN_CATEGORIES:
        print(
            category,
            ":",
            len(category_articles(final_news, category)),
        )


if __name__ == "__main__":
    main()
