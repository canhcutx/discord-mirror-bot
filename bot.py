import json
import os
import re
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
import requests

sys.stdout.reconfigure(line_buffering=True)

# -------------------------
# Lấy biến môi trường
# -------------------------
TOKEN = (os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN") or "").strip()
WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or "").strip()

RAW_CHANNEL_ID = (os.getenv("SOURCE_CHANNEL_ID") or "").strip()
SOURCE_CHANNEL_ID = int(RAW_CHANNEL_ID) if RAW_CHANNEL_ID.isdigit() else None

MAP_FILE = "message_map.json"
IMAGE_URL = "https://i.postimg.cc/m2MSpkf5/akat.png"

# Dùng trực tiếp ký tự khoảng trắng không độ rộng \u200b
ZWSP = "\u200b"

EMBED_DESCRIPTION = (
    f"**DANH SÁCH TEAM BAY TRẮNG:**\n{ZWSP}"
    "1. Gen Tổng\n"
    "2. Nam Con\n\n"
    f"**DANH SÁCH TEAM AKAT:**\n{ZWSP}"
    "Các thành viên mặc đồ Akatsuki mới như ảnh dưới 👇\n"
    "**KHÔNG MẶC ĐỒ AKATSUKI MỚI THÌ VẪN TÍNH HÓA ĐƠN NHƯ BÌNH THƯỜNG**"
)
EMBED_COLOR = 15158332

# -------------------------
# Load / Save mapping
# -------------------------
def load_map():
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Lỗi đọc file map: {e}")
    return {}

def save_map():
    try:
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(message_map, f, indent=2)
    except Exception as e:
        print(f"⚠️ Lỗi lưu file map: {e}")

message_map = load_map()

# -------------------------
# Discord Bot Setup
# -------------------------
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def fix_mobile_markdown(text):
    # Dùng hàm lambda thay thế để tránh lỗi escape Regex
    return re.sub(r'(\n)(\d+\.)', lambda m: m.group(1) + ZWSP + m.group(2), text)

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
    print("========================================")
    print(f"✅ Bot Mirror ONLINE: {client.user}")
    print(f"📌 Đang theo dõi kênh ID: {SOURCE_CHANNEL_ID}")
    print("========================================")

@client.event
async def on_message(message):
    if message.author.bot or not SOURCE_CHANNEL_ID or message.channel.id != SOURCE_CHANNEL_ID:
        return

    print(f"📩 Nhận tin nhắn ID: {message.id} từ {message.author.display_name}")

    content = message.content
    if message.attachments:
        for a in message.attachments:
            content += f"\n{a.url}"

    if WEBHOOK_URL:
        try:
            payload = {
                "username": message.author.display_name,
                "avatar_url": str(message.author.display_avatar.url),
                "embeds": [build_merged_embed(content)],
            }
            r = requests.post(WEBHOOK_URL + "?wait=true", json=payload, headers=HEADERS, timeout=10)
            if r.status_code in [200, 204]:
                data = r.json()
                message_map[str(message.id)] = data["id"]
                save_map()
                print(f"🚀 Đã forward tin nhắn thành công (Msg ID: {data['id']})")
            else:
                print(f"❌ Webhook lỗi HTTP {r.status_code}: {r.text}")
        except Exception as e:
            print(f"❌ Lỗi gửi Webhook: {e}")

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
            payload = {"embeds": [build_merged_embed(content)]}
            r = requests.patch(f"{WEBHOOK_URL}/messages/{webhook_msg_id}", json=payload, headers=HEADERS, timeout=10)
            print(f"✏️ Đã đồng bộ tin sửa (HTTP {r.status_code})")
        except Exception as e:
            print(f"❌ Lỗi sửa Webhook: {e}")

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
            requests.delete(f"{WEBHOOK_URL}/messages/{webhook_msg_id}", headers=HEADERS, timeout=10)
            del message_map[source_id]
            save_map()
            print(f"🗑️ Đã xóa tin nhắn Webhook")
        except Exception as e:
            print(f"❌ Lỗi xóa Webhook: {e}")

# -------------------------
# Web Server Giữ Sống 24/7 (Thread phụ)
# -------------------------
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot Mirror is Alive 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    server.serve_forever()

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()

    if not TOKEN:
        print("❌ LỖI: Chưa có biến môi trường TOKEN!")
    else:
        client.run(TOKEN)
