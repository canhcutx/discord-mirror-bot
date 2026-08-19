import json
import os
import re
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or "").strip()
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
            print(f"Lỗi đọc map: {e}", flush=True)
    return {}

def save_map():
    try:
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(message_map, f, indent=2)
    except Exception as e:
        print(f"Lỗi lưu map: {e}", flush=True)

message_map = load_map()

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

@app.route("/", methods=["GET", "HEAD"])
def home():
    return "Mirror Webhook Server is Alive!", 200

@app.route("/mirror", methods=["POST"])
def mirror_endpoint():
    data = request.get_json(silent=True) or {}
    action = data.get("action", "create")  # create, edit, delete
    source_id = str(data.get("message_id", ""))
    content = data.get("content", "")
    username = data.get("username", "Mirror Bot")
    avatar_url = data.get("avatar_url", "")

    if not WEBHOOK_URL:
        return jsonify({"error": "Chưa cấu hình WEBHOOK_URL"}), 500

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # 1. Tạo tin nhắn mới
    if action == "create":
        payload = {
            "username": username,
            "avatar_url": avatar_url,
            "embeds": [build_merged_embed(content)]
        }
        res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload, headers=headers, timeout=10)
        if res.status_code in [200, 204]:
            target_id = res.json().get("id")
            if source_id:
                message_map[source_id] = target_id
                save_map()
            return jsonify({"status": "created", "webhook_id": target_id}), 200
        return jsonify({"error": res.text}), res.status_code

    # 2. Sửa tin nhắn
    elif action == "edit":
        if source_id not in message_map:
            return jsonify({"error": "Không tìm thấy ID tin nhắn"}), 404
        webhook_msg_id = message_map[source_id]
        payload = {"embeds": [build_merged_embed(content)]}
        res = requests.patch(f"{WEBHOOK_URL}/messages/{webhook_msg_id}", json=payload, headers=headers, timeout=10)
        return jsonify({"status": "edited"}), res.status_code

    # 3. Xóa tin nhắn
    elif action == "delete":
        if source_id not in message_map:
            return jsonify({"error": "Không tìm thấy ID tin nhắn"}), 404
        webhook_msg_id = message_map[source_id]
        res = requests.delete(f"{WEBHOOK_URL}/messages/{webhook_msg_id}", headers=headers, timeout=10)
        del message_map[source_id]
        save_map()
        return jsonify({"status": "deleted"}), res.status_code

    return jsonify({"error": "Invalid action"}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
