import json
import os
import re
import threading
import discord
from flask import Flask
import cloudscraper

# Khởi tạo scraper giả lập trình duyệt Chrome thật (bypass Cloudflare)
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

TOKEN = (os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN") or "").strip()
WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or "").strip()

# Ép kiểu int an toàn cho SOURCE_CHANNEL_ID
RAW_CHANNEL_ID = (os.getenv("SOURCE_CHANNEL_ID") or "").strip()
SOURCE_CHANNEL_ID = int(RAW_CHANNEL_ID) if RAW_CHANNEL_ID.isdigit() else None

MAP_FILE = "message_map.json"

IMAGE_URL = "https://i.postimg.cc/m2MSpkf5/akat.png"

EMBED_DESCRIPTION = (
    "**DANH SÁCH TEAM BAY TRẮNG:**\n\u200b"
    "1. Gen Tổng\n"
    "2. Nam Con\n\n"
    "**DANH SÁCH TEAM AKAT:**\n\u200b"
    "Các thành viên mặc đồ Akatsuki mới như ảnh dưới 👇\n"
    "**KHÔNG MẶC ĐỒ AKATSUKI MỚI THÌ VẪN TÍNH HÓA ĐƠN NHƯ BÌNH THƯỜNG**"
)
EMBED_COLOR = 15158332

def load_map():
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Lỗi đọc file map: {e}", flush=True)
    return {}

def save_map():
    try:
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(message_map, f, indent=2)
    except Exception as e:
        print(f"Lỗi lưu file map: {e}", flush=True)

message_map = load_map()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

def fix_mobile_markdown(text):
    return re.sub(r'(\n)(\d+\.)', r'\1\u200b\2', text)

def build_merged_embed(user_content):
    text = user_content.strip()
    if text:
        formatted_text = fix_mobile_markdown(text)
        full_desc = f"{formatted_text}\n\n───────────────────\n{EMBED_DESCRIPTION}"
    else:
        full_desc = EMBED_DESCRIPTION

    return {
        "description": full_desc,
        "color": EMBED_COLOR,
        "image": {"url": IMAGE_URL},
    }

@client.event
async def on_ready():
    print(f"✅ Bot Mirror online: {client.user} | Kênh nguồn: {SOURCE_CHANNEL_ID}", flush=True)

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if not SOURCE_CHANNEL_ID or message.channel.id != SOURCE_CHANNEL_ID:
        return

    print(f"📩 Nhận tin nhắn mới ID: {message.id} | Từ: {message.author}", flush=True)

    content = message.content
    if message.attachments:
        for a in message.attachments:
            content += f"\n{a.url}"

    if WEBHOOK_URL:
        try:
            r = scraper.post(
                WEBHOOK_URL + "?wait=true",
                json={
                    "username": message.author.display_name,
                    "avatar_url": str(message.author.display_avatar.url),
                    "embeds": [build_merged_embed(content)],
                },
                timeout=15
            )

            if r.status_code in [200, 204]:
                data = r.json()
                message_map[str(message.id)] = data["id"]
                save_map()
                print(f" Đã forward tin nhắn ID: {message.id}", flush=True)
            else:
                print(f"❌ Webhook lỗi HTTP {r.status_code}: {r.text[:200]}", flush=True)
        except Exception as e:
            print(f"❌ Lỗi gửi Webhook: {e}", flush=True)

@client.event
async def on_message_edit(before, after):
    if before.author.bot or before.channel.id != SOURCE_CHANNEL_ID:
        return

    source_id = str(before.id)
    if source_id not in message_map:
        return

    webhook_msg_id = message_map[source_id]
    content = after.content
    if after.attachments:
        for a in after.attachments:
            content += f"\n{a.url}"

    if WEBHOOK_URL:
        try:
            r = scraper.patch(
                f"{WEBHOOK_URL}/messages/{webhook_msg_id}",
                json={"embeds": [build_merged_embed(content)]},
                timeout=15
            )
            print(f" Đã sửa tin nhắn ID: {before.id} (HTTP {r.status_code})", flush=True)
        except Exception as e:
            print(f"❌ Lỗi sửa Webhook: {e}", flush=True)

@client.event
async def on_message_delete(message):
    if message.author.bot or message.channel.id != SOURCE_CHANNEL_ID:
        return

    source_id = str(message.id)
    if source_id not in message_map:
        return

    webhook_msg_id = message_map[source_id]
    if WEBHOOK_URL:
        try:
            scraper.delete(f"{WEBHOOK_URL}/messages/{webhook_msg_id}", timeout=15)
            del message_map[source_id]
            save_map()
            print(f"🗑️ Đã xóa tin nhắn ID: {message.id}", flush=True)
        except Exception as e:
            print(f"❌ Lỗi xóa Webhook: {e}", flush=True)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Mirror is Alive 24/7!"

def run_bot():
    if TOKEN:
        client.run(TOKEN)
    else:
        print("❌ LỖI: Chưa cài đặt TOKEN biến môi trường!", flush=True)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
