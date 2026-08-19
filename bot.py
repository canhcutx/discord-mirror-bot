import json
import os
import re
import asyncio
import discord
from aiohttp import web
import aiohttp

# -------------------------
# Lấy biến môi trường
# -------------------------
TOKEN = (os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN") or "").strip()
WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or "").strip()

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

# -------------------------
# Load / Save mapping
# -------------------------
def load_map():
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Lỗi đọc map: {e}", flush=True)
    return {}

def save_map():
    try:
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(message_map, f, indent=2)
    except Exception as e:
        print(f"Lỗi lưu map: {e}", flush=True)

message_map = load_map()

# -------------------------
# Discord Bot Setup
# -------------------------
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
    print(f"==================================", flush=True)
    print(f"✅ Bot Mirror ONLINE: {client.user}", flush=True)
    print(f"📌 Kênh nguồn ID: {SOURCE_CHANNEL_ID}", flush=True)
    print(f"==================================", flush=True)

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if not SOURCE_CHANNEL_ID or message.channel.id != SOURCE_CHANNEL_ID:
        return

    print(f"📩 Nhận tin nhắn ID: {message.id} từ {message.author.display_name}", flush=True)

    content = message.content
    if message.attachments:
        for a in message.attachments:
            content += f"\n{a.url}"

    if WEBHOOK_URL:
        # Sử dụng Webhook của discord.py (Bypass mọi Cloudflare IP check)
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
                embed_data = build_merged_embed(content)
                embed = discord.Embed.from_dict(embed_data)

                sent_msg = await webhook.send(
                    embed=embed,
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                    wait=True
                )
                message_map[str(message.id)] = str(sent_msg.id)
                save_map()
                print(f"🚀 Đã forward tin nhắn ID: {message.id} -> Webhook Msg ID: {sent_msg.id}", flush=True)
        except Exception as e:
            print(f"❌ Lỗi gửi Webhook: {e}", flush=True)

@client.event
async def on_message_edit(before, after):
    if before.author.bot or before.channel.id != SOURCE_CHANNEL_ID:
        return

    source_id = str(before.id)
    if source_id not in message_map:
        return

    webhook_msg_id = int(message_map[source_id])
    content = after.content
    if after.attachments:
        for a in after.attachments:
            content += f"\n{a.url}"

    if WEBHOOK_URL:
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
                embed_data = build_merged_embed(content)
                embed = discord.Embed.from_dict(embed_data)

                await webhook.edit_message(webhook_msg_id, embed=embed)
                print(f"✏️ Đã cập nhật tin nhắn sửa ID: {before.id}", flush=True)
        except Exception as e:
            print(f"❌ Lỗi sửa Webhook: {e}", flush=True)

@client.event
async def on_message_delete(message):
    if message.author.bot or message.channel.id != SOURCE_CHANNEL_ID:
        return

    source_id = str(message.id)
    if source_id not in message_map:
        return

    webhook_msg_id = int(message_map[source_id])
    if WEBHOOK_URL:
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
                await webhook.delete_message(webhook_msg_id)
                del message_map[source_id]
                save_map()
                print(f"🗑️ Đã xóa tin nhắn ID: {message.id}", flush=True)
        except Exception as e:
            print(f"❌ Lỗi xóa Webhook: {e}", flush=True)

# -------------------------
# Web Server Giữ Uptime (aiohttp)
# -------------------------
async def handle_ping(request):
    return web.Response(text="Bot Mirror is Alive 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    # Đã xóa dòng add_head ở đây để tránh xung đột
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Web Server đã mở tại port {port}", flush=True)
    
# -------------------------
# Chạy đồng thời cả 2
# -------------------------
async def main():
    await start_web_server()
    if not TOKEN:
        print("❌ LỖI: Chưa có biến môi trường TOKEN!", flush=True)
        return
    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
