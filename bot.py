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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}


def ensure_font_downloaded():
    for fp in FONT_CANDIDATES[:-1]:
        if os.path.exists(fp) and os.path.getsize(fp) > 10000:
            return fp

    if not os.path.exists(TMP_FONT_PATH):
        for url in STATIC_FONT_URLS:
            try:
                r = requests.get(url, timeout=8)
                if r.status_code == 200 and len(r.content) > 10000:
                    with open(TMP_FONT_PATH, "wb") as f:
                        f.write(r.content)
                    return TMP_FONT_PATH
            except Exception:
                pass
    return None


def avg_valid_price(raw_prices):
    vals = []
    for p in raw_prices[:3]:
        try:
            num = float(str(p).replace(",", "").strip())
            if num > 2000:
                vals.append(num)
        except Exception:
            pass
    if vals:
        return sum(vals) / len(vals)
    return None


def fetch_bybit_p2p():
    url = "https://api2.bybit.com/fiat/otc/item/online"
    for side in ("0", "1"):
        payload = {
            "userId": "",
            "tokenId": "USDT",
            "currencyId": "MMK",
            "payment": [],
            "side": side,
            "size": "10",
            "page": "1",
            "amount": "",
            "vaMaker": False,
            "bulkProd": False,
            "canTrade": False,
            "sortType": "OVERALL",
        }
        r = requests.post(url, json=payload, headers=HEADERS, timeout=2.5)
        if r.status_code == 200:
            items = ((r.json() or {}).get("result") or {}).get("items") or []
            price = avg_valid_price([x.get("price") for x in items])
            if price:
                return price, "Bybit P2P"
    return None, None


def fetch_okx_p2p():
    url = (
        "https://www.okx.com/v3/c2c/tradingOrders/books"
        "?quoteCurrency=MMK&baseCurrency=USDT&side=sell"
        "&paymentMethod=all&userType=all&showTrade=false"
        "&showFollow=false&showAlreadyTraded=false&isAbleFilter=false"
    )
    r = requests.get(url, headers=HEADERS, timeout=2.5)
    if r.status_code == 200:
        sell_list = ((r.json() or {}).get("data") or {}).get("sell") or []
        price = avg_valid_price([x.get("price") for x in sell_list])
        if price:
            return price, "OKX P2P"
    return None, None


def fetch_bitget_p2p():
    url = "https://www.bitget.com/v1/p2p/pub/adv/queryAdvList"
    payload = {
        "coinCode": "USDT",
        "fiatCode": "MMK",
        "side": 1,
        "pageNo": 1,
        "pageSize": 10,
    }
    r = requests.post(url, json=payload, headers=HEADERS, timeout=2.5)
    if r.status_code == 200:
        adv_list = ((r.json() or {}).get("data") or {}).get("dataList") or []
        price = avg_valid_price([x.get("price") for x in adv_list])
        if price:
            return price, "Bitget P2P"
    return None, None


def get_p2p_usd_sell():
    for fn in (fetch_bybit_p2p, fetch_okx_p2p, fetch_bitget_p2p):
        try:
            rate, src = fn()
            if rate:
                return rate, src
        except Exception:
            pass
    return None, None


def fetch_rates_fast():
    usd_sell, source_name = get_p2p_usd_sell()

    if not usd_sell and CSV_URL:
        try:
            resp = requests.get(CSV_URL, timeout=4)
            resp.encoding = "utf-8"
            reader = csv.reader(io.StringIO(resp.text))
            rows = [r for r in reader if any(c.strip() for c in r)]
            if len(rows) > 1 and len(rows[1]) >= 3:
                raw_val = rows[1][2].replace(",", "").strip()
                parsed = float(raw_val)
                if parsed > 2000:
                    usd_sell = parsed
                    source_name = "Sheet P2P"
        except Exception:
            pass

    if not usd_sell:
        usd_sell = 5585.0
        source_name = "Fallback"

    usd_buy = usd_sell * 0.985

    fx_rates = {}
    try:
        fx_res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=3)
        if fx_res.status_code == 200:
            fx_rates = (fx_res.json() or {}).get("rates") or {}
    except Exception:
        pass

    def calc(code, mult):
        u = fx_rates.get(code)
        if not u:
            return "-"
        return f"{(usd_sell / float(u)) * mult:,.2f}"

    rows = [
        ["USD (ဒေါ်လာ)", f"{usd_buy:,.2f}", f"{usd_sell:,.2f}"],
        ["THB (ထိုင်းဘတ်)", calc("THB", 0.985), calc("THB", 1.0)],
        ["JPY (ဂျပန်ယန်း)", calc("JPY", 0.985), calc("JPY", 1.0)],
        ["CNY (တရုတ်ယွမ်)", calc("CNY", 0.985), calc("CNY", 1.0)],
        ["MYR (မလေးရှားရင်းဂစ်)", calc("MYR", 0.985), calc("MYR", 1.0)],
        ["SGD (စင်ကာပူဒေါ်လာ)", calc("SGD", 0.985), calc("SGD", 1.0)],
    ]

    now_mm = (
        datetime.datetime.utcnow() + datetime.timedelta(hours=6, minutes=30)
    ).strftime("%d %b %Y · %I:%M %p")
    return rows, f"Updated · {now_mm}", source_name


def load_font(size, resolved_font):
    if resolved_font and os.path.exists(resolved_font):
        try:
            return ImageFont.truetype(resolved_font, size)
        except Exception:
            pass
    return ImageFont.load_default()


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


def generate_rate_image(rows, time_str, source_name):
    width, height = 1140, 960
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

    draw.text((44, 24), "Exchange Rates", fill=gold_color, font=font_title)
    draw.text((44, 106), f"MMK · {time_str}", fill=gray, font=font_sub)
    draw_logo(img, draw, font_badge)

    usd_buy = rows[0][1]
    usd_sell = rows[0][2]
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
        currency, buy, sell = row[0], row[1], row[2]
        if idx % 2 == 1:
            draw.rounded_rectangle([(40, y - 12), (1100, y + 62)], radius=12, fill=row_alt)

        draw.text((52, y), currency, fill=white, font=font_row)
        draw.text((560, y), buy, fill=white, font=font_row)
        draw.text(
            (835, y),
            sell,
            fill=green_color if "USD" in currency.upper() else white,
            font=font_row,
        )
        y += 82

    draw.line([(44, height - 70), (1096, height - 70)], fill=line_color, width=1)
    draw.text(
        (44, height - 52),
        f"Source: {source_name} · Type /rates for latest update",
        fill=gray,
        font=font_foot,
    )

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
            rows, time_str, source_name = fetch_rates_fast()
            photo = generate_rate_image(rows, time_str, source_name)
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
