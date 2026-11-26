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
TMP_FONT_PATH = "/tmp/StaticMyanmarFont.ttf"

FONT_CANDIDATES = [
    os.path.join(BASE_DIR, "font.ttf"),
    os.path.join(BASE_DIR, "NotoSansMyanmar-Regular.ttf"),
    os.path.join(BASE_DIR, "NotoSansMyanmar-Medium.ttf"),
    os.path.join(BASE_DIR, "Pyidaungsu.ttf"),
    TMP_FONT_PATH,
]

LOGO_CANDIDATES = [
    os.path.join(BASE_DIR, "logo.png"),
    os.path.join(BASE_DIR, "logo.jpg"),
    os.path.join(BASE_DIR, "logo.jpeg"),
    os.path.join(BASE_DIR, "LOGO.png"),
    os.path.join(BASE_DIR, "LOGO.jpg"),
]

STATIC_FONT_URLS = [
    "https://github.com/notofonts/myanmar/raw/main/fonts/NotoSansMyanmar/unhinted/ttf/NotoSansMyanmar-Medium.ttf",
    "https://github.com/notofonts/myanmar/raw/main/fonts/NotoSansMyanmar/unhinted/ttf/NotoSansMyanmar-Regular.ttf",
]


def ensure_font_downloaded():
    for fp in FONT_CANDIDATES[:-1]:
        if os.path.exists(fp) and os.path.getsize(fp) > 10000:
            return fp

    if not os.path.exists(TMP_FONT_PATH):
        for url in STATIC_FONT_URLS:
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200 and len(r.content) > 10000:
                    with open(TMP_FONT_PATH, "wb") as f:
                        f.write(r.content)
                    return TMP_FONT_PATH
            except Exception:
                pass
    return None


def clean_label(text):
    t = (text or "").strip()
    if "BINANCE P2P" in t.upper():
        t = (
            t.replace("Binance P2P ·", "")
            .replace("BINANCE P2P ·", "")
            .replace("Binance P2P", "")
            .replace("BINANCE P2P", "")
            .strip(" ·-")
        )
    return t


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
        updated_note = clean_label(rows[0][3].strip())

    data_rows = rows[1:] if len(rows) > 1 else []
    return data_rows, updated_note


def load_font(size, resolved_font):
    if resolved_font and os.path.exists(resolved_font):
        try:
            return ImageFont.truetype(resolved_font, size)
        except Exception:
            pass
    return ImageFont.load_default()


def find_usd_row(rows):
    for r in rows:
        if len(r) >= 3 and "USD" in r[0].upper():
            return r[0].strip(), r[1].strip(), r[2].strip()
    return "USD", "-", "-"


def draw_logo(img, draw, font_badge):
    for lp in LOGO_CANDIDATES:
        if os.path.exists(lp):
            try:
                logo = Image.open(lp).convert("RGBA")
                logo.thumbnail((156, 156))
                lx = img.width - logo.width - 44
                ly = 22
                img.paste(logo, (lx, ly), logo)
                return
            except Exception:
                pass

    draw.rounded_rectangle(
        [(img.width - 196, 32), (img.width - 44, 114)],
        radius=16,
        fill=(32, 32, 38),
        outline=(250, 195, 25),
        width=2,
    )
    draw.text((img.width - 172, 58), "RATE BOARD", fill=(250, 195, 25), font=font_badge)


def generate_rate_image(rows, updated_note):
    width, height = 1140, 1060
    bg_color = (14, 14, 16)
    card_bg = (28, 28, 35)
    row_alt = (22, 22, 27)
    gold_color = (255, 200, 25)
    green_color = (80, 230, 140)
    white = (255, 255, 255)
    gray = (195, 195, 205)
    line_color = (68, 68, 80)

    resolved_font = ensure_font_downloaded()

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    font_title = load_font(68, resolved_font)
    font_sub = load_font(28, resolved_font)
    font_badge = load_font(24, resolved_font)
    font_usd_lbl = load_font(30, resolved_font)
    font_usd_val = load_font(42, resolved_font)
    font_th = load_font(32, resolved_font)
    font_row = load_font(36, resolved_font)
    font_foot = load_font(25, resolved_font)

    now_mm = (
        datetime.datetime.utcnow() + datetime.timedelta(hours=6, minutes=30)
    ).strftime("%d %b %Y · %I:%M %p")
    time_str = updated_note if updated_note else now_mm

    draw.text((44, 24), "Exchange Rates", fill=gold_color, font=font_title)
    draw.text((44, 106), f"MMK · {time_str}", fill=gray, font=font_sub)
    draw_logo(img, draw, font_badge)

    _, usd_buy, usd_sell = find_usd_row(rows)
    draw.rounded_rectangle(
        [(44, 160), (1096, 286)],
        radius=20,
        fill=card_bg,
        outline=gold_color,
        width=2,
    )
    draw.text((70, 172), "Dollar to MMK (1 USD)", fill=gold_color, font=font_usd_lbl)
    draw.text((70, 218), f"Buy: {usd_buy} MMK", fill=white, font=font_usd_val)
    draw.text((585, 218), f"Sell: {usd_sell} MMK", fill=green_color, font=font_usd_val)

    th_y = 316
    draw.text((48, th_y), "Currency", fill=gold_color, font=font_th)
    draw.text((585, th_y), "Buy", fill=gold_color, font=font_th)
    draw.text((865, th_y), "Sell", fill=gold_color, font=font_th)
    draw.line([(44, th_y + 52), (1096, th_y + 52)], fill=line_color, width=2)

    y = th_y + 72
    for idx, row in enumerate(rows):
        if len(row) < 3 or not row[0].strip():
            continue
        currency = clean_label(row[0].strip())
        buy = row[1].strip()
        sell = row[2].strip()

        if idx % 2 == 1:
            draw.rounded_rectangle([(40, y - 12), (1100, y + 62)], radius=12, fill=row_alt)

        draw.text((52, y), currency, fill=white, font=font_row)
        if buy and buy != "-":
            draw.text((560, y), buy, fill=white, font=font_row)
        else:
            draw.text((605, y), "-", fill=gray, font=font_row)

        if sell and sell != "-":
            draw.text(
                (835, y),
                sell,
                fill=green_color if "USD" in currency.upper() else white,
                font=font_row,
            )

        y += 82
        if y > height - 95:
            break

    draw.line([(44, height - 70), (1096, height - 70)], fill=line_color, width=1)
    draw.text((44, height - 52), "Type /rates for latest update", fill=gray, font=font_foot)

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
                timeout=25,
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
