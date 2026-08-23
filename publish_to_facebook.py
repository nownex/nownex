import json
import os
import requests

TOKEN = os.environ["FACEBOOK_PAGE_TOKEN"]

GRAPH_URL = "https://graph.facebook.com/v26.0/me/photos"


# هاشتاقات حسب القسم
HASHTAGS = {
    "AI": "#NOWNEX #الذكاء_الاصطناعي #AI #تقنية #أخبار_التقنية",
    "Technology": "#NOWNEX #تقنية #تكنولوجيا #أخبار_التقنية",
    "Cars": "#NOWNEX #سيارات #سيارات_ذكية #أخبار_السيارات",
    "Entertainment": "#NOWNEX #ترفيه #أخبار_الترفيه",
    "Facts": "#NOWNEX #هل_تعلم #معلومات #حقائق",
    "Products": "#NOWNEX #منتجات #تقنية #مراجعات",
}


# قراءة الأخبار
with open("news.json", "r", encoding="utf-8") as f:
    data = json.load(f)


news = data.get("news", [])

if not news:
    raise SystemExit("No news found")


# الحصول على أحدث خبر من كل قسم
latest_by_category = {}

for article in news:
    category = article.get("category", "Other")

    if category not in latest_by_category:
        latest_by_category[category] = article


print("Categories found:", list(latest_by_category.keys()))


# نشر خبر واحد من كل قسم
for category, article in latest_by_category.items():

    title = (
        article.get("title_ar")
        or article.get("title")
        or ""
    )

    summary = (
        article.get("summary_ar")
        or article.get("summary")
        or article.get("description")
        or ""
    )

    link = article.get("link", "")
    image = article.get("image", "")

    hashtags = HASHTAGS.get(
        category,
        "#NOWNEX #أخبار #أخبار_اليوم"
    )

    message = (
        f"📰 {title}\n\n"
        f"{summary}\n\n"
        f"{hashtags}\n\n"
        f"🔗 اقرأ المزيد:\n{link}"
    )


    # نشر الصورة إذا كان الخبر يحتوي على صورة
    if image:

        # إذا كانت الصورة محلية مثل cars.png
        if not image.startswith("http"):
            image = (
                "https://nownex.github.io/nownex/"
                + image
            )

        response = requests.post(
            GRAPH_URL,
            data={
                "url": image,
                "caption": message,
                "access_token": TOKEN,
            },
            timeout=60,
        )

    else:

        # في حالة عدم وجود صورة
        feed_url = "https://graph.facebook.com/v26.0/me/feed"

        response = requests.post(
            feed_url,
            data={
                "message": message,
                "access_token": TOKEN,
            },
            timeout=60,
        )


    if not response.ok:
        raise SystemExit(
            f"Facebook error for {category}: "
            f"{response.text}"
        )


    print(
        f"Published successfully: "
        f"{category} - {response.json()}"
    )
