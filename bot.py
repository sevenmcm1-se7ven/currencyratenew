import os
import io
import csv
import datetime
import requests
from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

BOT_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
CSV_URL = (os.environ.get("CSV_URL") or "").strip()
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FONT_CANDIDATES = [
    os.path.join(BASE_DIR, "font.ttf"),
    os.path.join(BASE_DIR, "NotoSansMyanmar-Regular.ttf"),
    os.path.join(BASE_DIR, "Pyidaungsu.ttf"),
]

LOGO_CANDIDATES = [
    os.path.join(BASE_DIR, "logo.png"),
    os.path.join(BASE_DIR, "logo.jpg"),
    os.path.join(BASE_DIR, "logo.jpeg"),
]


def fetch_rates():
    if not CSV_URL:
        raise ValueError("CSV_URL is not set in Environment Variables")

    resp = requests.get(CSV_URL, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    reader = csv.reader(io.StringIO(resp.text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]

    updated_note = ""
    if rows and len(rows[0]) >= 4 and rows[0][3].strip():
        updated_note = rows[0][3].strip()

    data_rows = rows[1:] if len(rows) > 1 else []
    return data_rows, updated_note


def load_font(size):
    for fp in FONT_CANDIDATES:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


def find_usd_row(rows):
    for r in rows:
        if len(r) >= 3 and "USD" in r[0].upper():
            return r[0].strip(), r[1].strip(), r[2].strip()
    return "USD (ဒေါ်လာ)", "-", "-"


def draw_logo(img, draw, font_badge):
    for lp in LOGO_CANDIDATES:
        if os.path.exists(lp):
            try:
                logo = Image.open(lp).convert("RGBA")
                logo.thumbnail((130, 130))
                lx = img.width - logo.width - 42
                ly = 28
                img.paste(logo, (lx, ly), logo)
                return
            except Exception:
                pass

    draw.rounded_rectangle(
        [(img.width - 230, 32), (img.width - 42, 114)],
        radius=16,
        fill=(32, 32, 38),
        outline=(250, 195, 25),
        width=2,
    )
    draw.text((img.width - 205, 58), "BINANCE P2P", fill=(250, 195, 25), font=font_badge)


def generate_rate_image(rows, updated_note):
    width, height = 1080, 940
    bg_color = (15, 15, 17)
    card_bg = (28, 28, 34)
    row_alt = (23, 23, 28)
    gold_color = (250, 195, 25)
    green_color = (75, 225, 135)
    white = (252, 252, 252)
    gray = (185, 185, 195)
    line_color = (62, 62, 72)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    font_title = load_font(56)
    font_sub = load_font(26)
    font_badge = load_font(23)
    font_usd_lbl = load_font(28)
    font_usd_val = load_font(38)
    font_th = load_font(28)
    font_row = load_font(33)
    font_foot = load_font(23)

    now_mm = (
        datetime.datetime.utcnow() + datetime.timedelta(hours=6, minutes=30)
    ).strftime("%d %b %Y · %I:%M %p")
    time_str = updated_note if updated_note else now_mm

    draw.text((42, 28), "Exchange Rates", fill=gold_color, font=font_title)
    draw.text((42, 96), f"MMK · {time_str}", fill=gray, font=font_sub)
    draw_logo(img, draw, font_badge)

    _, usd_buy, usd_sell = find_usd_row(rows)
    draw.rounded_rectangle(
        [(42, 148), (1038, 260)],
        radius=18,
        fill=card_bg,
        outline=gold_color,
        width=2,
    )
    draw.text((68, 162), "Dollar to MMK (1 USD)", fill=gold_color, font=font_usd_lbl)
    draw.text((68, 202), f"Buy: {usd_buy} MMK", fill=white, font=font_usd_val)
    draw.text((555, 202), f"Sell: {usd_sell} MMK", fill=green_color, font=font_usd_val)

    th_y = 286
    draw.text((48, th_y), "Currency", fill=gold_color, font=font_th)
    draw.text((560, th_y), "Buy", fill=gold_color, font=font_th)
    draw.text((810, th_y), "Sell", fill=gold_color, font=font_th)
    draw.line([(42, th_y + 44), (1038, th_y + 44)], fill=line_color, width=2)

    y = th_y + 60
    for idx, row in enumerate(rows):
        if len(row) < 3 or not row[0].strip():
            continue
        currency = row[0].strip()
        buy = row[1].strip()
        sell = row[2].strip()

        if idx % 2 == 1:
            draw.rounded_rectangle([(38, y - 8), (1042, y + 50)], radius=10, fill=row_alt)

        draw.text((52, y), currency, fill=white, font=font_row)
        if buy and buy != "-":
            draw.text((535, y), buy, fill=white, font=font_row)
        else:
            draw.text((575, y), "-", fill=gray, font=font_row)

        if sell and sell != "-":
            draw.text(
                (785, y),
                sell,
                fill=green_color if "USD" in currency.upper() else white,
                font=font_row,
            )

        y += 66
        if y > height - 90:
            break

    draw.line([(42, height - 66), (1038, height - 66)], fill=line_color, width=1)
    draw.text((42, height - 50), "Auto-updated Rates · Type /rates", fill=gray, font=font_foot)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200


def handle_update(data):
    if not BOT_TOKEN:
        return
    msg = (data or {}).get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    if text.startswith(("/rates", "/currencyrates")):
        try:
            rows, updated_note = fetch_rates()
            photo = generate_rate_image(rows, updated_note)
            requests.post(
                f"{TELEGRAM_API}/sendPhoto",
                data={"chat_id": chat_id},
                files={"photo": ("rates.png", photo, "image/png")},
                timeout=20,
            )
        except Exception as e:
            requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": f"Error: {str(e)}"},
                timeout=10,
            )


@app.route("/webhook", methods=["POST"])
def webhook_static():
    handle_update(request.get_json(silent=True) or {})
    return "ok", 200


@app.route("/<path:token_path>", methods=["POST"])
def webhook_dynamic(token_path):
    if BOT_TOKEN and token_path == BOT_TOKEN:
        handle_update(request.get_json(silent=True) or {})
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
