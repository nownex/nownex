import json
import os
import requests

TOKEN = os.environ["FACEBOOK_PAGE_TOKEN"]

with open("news.json", "r", encoding="utf-8") as f:
    data = json.load(f)

news = data.get("news", [])
if not news:
    raise SystemExit("No news found")

article = news[0]

title = article.get("title_ar") or article.get("title", "")
summary = article.get("summary_ar") or article.get("summary", "")
link = article.get("link", "")

message = f"📰 {title}\n\n{summary}\n\n🔗 اقرأ المزيد:\n{link}"

url = "https://graph.facebook.com/v26.0/me/feed"

response = requests.post(
    url,
    data={
        "message": message,
        "access_token": TOKEN,
    },
    timeout=30,
)

if not response.ok:
    raise SystemExit(f"Facebook error: {response.text}")

print("Published successfully:", response.json())
