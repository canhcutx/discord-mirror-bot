import json
import os
import threading
import discord
from flask import Flask
import requests

# Lấy Token linh hoạt (nhận cả TOKEN lẫn DISCORD_TOKEN)
TOKEN = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Ép kiểu int an toàn cho SOURCE_CHANNEL_ID
RAW_CHANNEL_ID = os.getenv("SOURCE_CHANNEL_ID")
SOURCE_CHANNEL_ID = int(RAW_CHANNEL_ID) if RAW_CHANNEL_ID else None

MAP_FILE = "message_map.json"

# ---------------------------------------------------------
# CẤU HÌNH NỘI DUNG EMBED ĐÍNH KÈM
# ---------------------------------------------------------
IMAGE_URL = "https://i.postimg.cc/m2MSpkf5/akat.png"
EMBED_DESCRIPTION = (
    "**DANH SÁCH TEAM BAY TRẮNG:**\n"
    "1. Hào Milk\n"
    "2. Gen Tổng\n"
    "3. Bệu\n"
    "4. DouJunn\n"
    "5. Copper\n"
    "6. Nam Con\n\n"
    "**DANH SÁCH TEAM AKAT:**\n"
    "Các thành viên mặc đồ Akatsuki mới như ảnh dưới 👇\n"
    "**KHÔNG MẶC ĐỒ AKATSUKI MỚI THÌ VẪN TÍNH HÓA ĐƠN NHƯ BÌNH THƯỜNG**"
)
EMBED_COLOR = 15158332  # Mã màu đỏ 0xE74C3C dạng Decimal integer

# -------------------------
# Load / Save mapping
# -------------------------

def load_map():
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Lỗi đọc file map: {e}")
    return {}

def save_map():
    try:
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(message_map, f, indent=2)
    except Exception as e:
        print(f"Lỗi lưu file map: {e}")

message_map = load_map()

# -------------------------
# Discord setup
# -------------------------

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

def build_merged_embed(user_content):
    """Hàm gộp tin nhắn gốc và danh sách thành 1 Embed duy nhất"""
    text = user_content.strip()
    
    # Nếu tin nhắn gốc có nội dung thì thêm đường gạch ngang phân cách
    if text:
        full_desc = f"{text}\n\n───────────────────\n**{EMBED_TITLE}**\n\n{EMBED_DESCRIPTION}"
    else:
        full_desc = f"**{EMBED_TITLE}**\n\n{EMBED_DESCRIPTION}"

    return {
        "description": full_desc,
        "color": EMBED_COLOR,
        "image": {"url": IMAGE_URL},
    }

# -------------------------
# Ready
# -------------------------

@client.event
async def on_ready():
    print(f"✅ Bot Mirror online: {client.user}")

# -------------------------
# New Message
# -------------------------

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if not SOURCE_CHANNEL_ID or message.channel.id != SOURCE_CHANNEL_ID:
        return

    content = message.content

    if message.attachments:
        for a in message.attachments:
            content += f"\n{a.url}"

    # Gửi hoàn toàn bên trong Embed, không để content bên ngoài
    if WEBHOOK_URL:
        try:
            r = requests.post(
                WEBHOOK_URL + "?wait=true",
                json={
                    "username": message.author.display_name,
                    "avatar_url": str(message.author.display_avatar.url),
                    "embeds": [build_merged_embed(content)],
                },
                timeout=10
            )

            if r.status_code in [200, 204]:
                data = r.json()
                message_map[str(message.id)] = data["id"]
                save_map()
                print(f"Forwarded message ID: {message.id}")
        except Exception as e:
            print(f"❌ Lỗi gửi Webhook: {e}")

# -------------------------
# Edit Message
# -------------------------

@client.event
async def on_message_edit(before, after):
    if before.author.bot:
        return

    if not SOURCE_CHANNEL_ID or before.channel.id != SOURCE_CHANNEL_ID:
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
            requests.patch(
                f"{WEBHOOK_URL}/messages/{webhook_msg_id}",
                json={"embeds": [build_merged_embed(content)]},
                timeout=10
            )
            print(f"Edited message ID: {before.id}")
        except Exception as e:
            print(f"❌ Lỗi sửa Webhook: {e}")

# -------------------------
# Delete Message
# -------------------------

@client.event
async def on_message_delete(message):
    if message.author.bot:
        return

    if not SOURCE_CHANNEL_ID or message.channel.id != SOURCE_CHANNEL_ID:
        return

    source_id = str(message.id)

    if source_id not in message_map:
        return

    webhook_msg_id = message_map[source_id]

    if WEBHOOK_URL:
        try:
            requests.delete(f"{WEBHOOK_URL}/messages/{webhook_msg_id}", timeout=10)
            del message_map[source_id]
            save_map()
            print(f"Deleted message ID: {message.id}")
        except Exception as e:
            print(f"❌ Lỗi xóa Webhook: {e}")

# -------------------------
# Flask Web Server Keep-Alive
# -------------------------

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Mirror is Alive 24/7!"

# -------------------------
# Start Discord Bot
# -------------------------

def run_bot():
    if TOKEN:
        client.run(TOKEN)
    else:
        print("❌ LỖI: Chưa cài đặt TOKEN biến môi trường!")

# -------------------------
# Main
# -------------------------

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
