import os
import io
import csv
import datetime
import requests
from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CSV_URL = os.environ.get("CSV_URL")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def fetch_rates():
    resp = requests.get(CSV_URL, timeout=10)
    resp.encoding = "utf-8"
    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    updated_note = ""
    if rows and len(rows[0]) >= 4 and rows[0][3].strip():
        updated_note = rows[0][3].strip()
    return rows[1:], updated_note


def generate_rate_image(rows, updated_note):
    width, height = 840, 650
    bg_color = (18, 18, 18)
    row_alt = (28, 28, 28)
    gold_color = (245, 190, 20)
    white = (245, 245, 245)
    gray = (165, 165, 165)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("font.ttf", 40)
        font_sub = ImageFont.truetype("font.ttf", 20)
        font_row = ImageFont.truetype("font.ttf", 24)
        font_note = ImageFont.truetype("font.ttf", 17)
    except Exception:
        font_title = font_sub = font_row = font_note = ImageFont.load_default()

    now_mm = (datetime.datetime.utcnow() + datetime.timedelta(hours=6, minutes=30)).strftime(
        "%d %b %Y · %I:%M %p"
    )
    sub_text = f"Buy / Sell · MMK · {now_mm}"
    if updated_note:
        sub_text = f"Buy / Sell · MMK · {updated_note}"

    draw.text((40, 32), "Exchange Rates", fill=gold_color, font=font_title)
    draw.text((40, 88), sub_text, fill=gray, font=font_sub)

    draw.text((40, 145), "Currency", fill=gray, font=font_sub)
    draw.text((470, 145), "Buy", fill=gray, font=font_sub)
    draw.text((665, 145), "Sell", fill=gray, font=font_sub)
    draw.line([(40, 178), (800, 178)], fill=(70, 70, 70), width=2)

    y = 192
    for idx, row in enumerate(rows):
        if len(row) < 3 or not row[0].strip():
            continue
        currency, buy, sell = row[0].strip(), row[1].strip(), row[2].strip()
        if idx % 2 == 1:
            draw.rectangle([(35, y - 6), (805, y + 40)], fill=row_alt)

        draw.text((45, y), currency, fill=white, font=font_row)
        if buy and buy != "-":
            draw.text((445, y), buy, fill=white, font=font_row)
        draw.text((635, y), sell, fill=white, font=font_row)
        y += 52

    draw.text(
        (40, y + 25),
        "Auto-updated via Google Sheets & Apps Script",
        fill=gold_color,
        font=font_note,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    msg = data.get("message")
    if not msg:
        return "ok", 200

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if text.startswith("/rates"):
        try:
            rows, updated_note = fetch_rates()
            photo = generate_rate_image(rows, updated_note)
            requests.post(
                f"{TELEGRAM_API}/sendPhoto",
                data={"chat_id": chat_id},
                files={"photo": ("rates.png", photo, "image/png")},
                timeout=15,
            )
        except Exception as e:
            requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": f"Error: {str(e)}"},
                timeout=10,
            )
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
