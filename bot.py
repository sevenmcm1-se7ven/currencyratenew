import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""


@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200


@app.route("/webhook", methods=["POST"])
def webhook_static():
    data = request.get_json(silent=True) or {}
    msg = data.get("message")
    if msg and BOT_TOKEN:
        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or "").strip()
        if text.startswith("/rates"):
            requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": "Bot is online!"},
                timeout=10,
            )
    return "ok", 200


@app.route("/<path:token_path>", methods=["POST"])
def webhook_dynamic(token_path):
    if BOT_TOKEN and token_path == BOT_TOKEN:
        return webhook_static()
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
