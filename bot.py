import discord
import requests
import json
import os

TOKEN = os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))

MAP_FILE = "message_map.json"

# -------------------------
# Load / Save mapping
# -------------------------

def load_map():
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_map():
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(message_map, f)

message_map = load_map()

# -------------------------
# Discord setup
# -------------------------

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# -------------------------
# Ready
# -------------------------

@client.event
async def on_ready():
    print(f"Bot online: {client.user}")

# -------------------------
# New Message
# -------------------------

@client.event
async def on_message(message):

    if message.author.bot:
        return

    if message.channel.id != SOURCE_CHANNEL_ID:
        return

    content = message.content

    # thêm link ảnh đính kèm
    if message.attachments:
        for a in message.attachments:
            content += f"\n{a.url}"

    r = requests.post(
        WEBHOOK_URL + "?wait=true",
        json={
            "username": message.author.display_name,
            "avatar_url": str(message.author.display_avatar.url),
            "content": content
        }
    )

    if r.status_code in [200, 204]:
        data = r.json()

        message_map[str(message.id)] = data["id"]
        save_map()

        print(f"Forwarded: {message.id}")

# -------------------------
# Edit Message
# -------------------------

@client.event
async def on_message_edit(before, after):

    if before.author.bot:
        return

    if before.channel.id != SOURCE_CHANNEL_ID:
        return

    source_id = str(before.id)

    if source_id not in message_map:
        return

    webhook_msg_id = message_map[source_id]

    content = after.content

    if after.attachments:
        for a in after.attachments:
            content += f"\n{a.url}"

    r = requests.patch(
        f"{WEBHOOK_URL}/messages/{webhook_msg_id}",
        json={
            "content": content
        }
    )

    print(
        f"Edited: {before.content} -> {after.content}"
    )

# -------------------------
# Delete Message
# -------------------------

@client.event
async def on_message_delete(message):

    if message.author.bot:
        return

    if message.channel.id != SOURCE_CHANNEL_ID:
        return

    source_id = str(message.id)

    if source_id not in message_map:
        return

    webhook_msg_id = message_map[source_id]

    requests.delete(
        f"{WEBHOOK_URL}/messages/{webhook_msg_id}"
    )

    del message_map[source_id]
    save_map()

    print(f"Deleted: {message.id}")

# -------------------------

client.run(TOKEN)