import csv
import datetime
import io
import os
import requests
from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

BOT_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
CSV_URL = (os.environ.get("CSV_URL") or "").strip()
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def clean_txt(s):
    return (s or "").replace("Binance P2P", "").replace("BINANCE P2P", "").strip(" ·-")


def avg_rate(vals):
    nums = []
    for x in vals[:3]:
        try:
            v = float(str(x).replace(",", "").strip())
            if v > 2000:
                nums.append(v)
        except Exception:
            pass
    return (sum(nums) / len(nums)) if nums else None


def get_p2p():
    try:
        r = requests.post(
            "https://api2.bybit.com/fiat/otc/item/online",
            json={"tokenId": "USDT", "currencyId": "MMK", "side": "0", "size": "10", "page": "1"},
            headers=HEADERS,
            timeout=2.5,
        )
        if r.status_code == 200:
            items = ((r.json() or {}).get("result") or {}).get("items") or []
            p = avg_rate([i.get("price") for i in items])
            if p:
                return p, "Bybit P2P"
    except Exception:
        pass

    try:
        r = requests.get(
            "https://www.okx.com/v3/c2c/tradingOrders/books?quoteCurrency=MMK&baseCurrency=USDT&side=sell",
            headers=HEADERS,
            timeout=2.5,
        )
        if r.status_code == 200:
            sell = ((r.json() or {}).get("data") or {}).get("sell") or []
            p = avg_rate([i.get("price") for i in sell])
            if p:
                return p, "OKX P2P"
    except Exception:
        pass

    try:
        r = requests.post(
            "https://www.bitget.com/v1/p2p/pub/adv/queryAdvList",
            json={"coinCode": "USDT", "fiatCode": "MMK", "side": 1, "pageNo": 1, "pageSize": 10},
            headers=HEADERS,
            timeout=2.5,
        )
        if r.status_code == 200:
            lst = ((r.json() or {}).get("data") or {}).get("dataList") or []
            p = avg_rate([i.get("price") for i in lst])
            if p:
                return p, "Bitget P2P"
    except Exception:
        pass

    return None, None


def get_rates():
    sell, src = get_p2p()

    if not sell and CSV_URL:
        try:
            resp = requests.get(CSV_URL, timeout=4)
            resp.encoding = "utf-8"
            rows = [r for r in csv.reader(io.StringIO(resp.text)) if any(c.strip() for c in r)]
            if len(rows) > 1 and len(rows[1]) >= 3:
                v = float(rows[1][2].replace(",", "").strip())
                if v > 2000:
                    sell, src = v, "Sheet P2P"
        except Exception:
            pass

    if not sell:
        sell, src = 5585.0, "Fallback"

    buy = sell * 0.985
    fx = {}
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=3)
        if res.status_code == 200:
            fx = (res.json() or {}).get("rates") or {}
    except Exception:
        pass

    def cross(code, mult):
        u = fx.get(code)
        return f"{(sell / float(u)) * mult:,.2f}" if u else "-"

    table = [
        ["USD (ဒေါ်လာ)", f"{buy:,.2f}", f"{sell:,.2f}"],
        ["THB (ထိုင်းဘတ်)", cross("THB", 0.985), cross("THB", 1.0)],
        ["JPY (ဂျပန်ယန်း)", cross("JPY", 0.985), cross("JPY", 1.0)],
        ["CNY (တရုတ်ယွမ်)", cross("CNY", 0.985), cross("CNY", 1.0)],
        ["MYR (မလေးရှားရင်းဂစ်)", cross("MYR", 0.985), cross("MYR", 1.0)],
        ["SGD (စင်ကာပူဒေါ်လာ)", cross("SGD", 0.985), cross("SGD", 1.0)],
    ]
    now_str = (datetime.datetime.utcnow() + datetime.timedelta(hours=6, minutes=30)).strftime(
        "%d %b %Y · %I:%M %p"
    )
    return table, f"Updated · {now_str}", src


def pick_font(size):
    for name in ("font.ttf", "NotoSansMyanmar-Regular.ttf", "NotoSansMyanmar-Medium.ttf", "Pyidaungsu.ttf"):
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p) and os.path.getsize(p) > 10000:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_logo(img, draw, f_badge):
    for name in ("logo.png", "logo.jpg", "logo.jpeg", "LOGO.png", "LOGO.jpg"):
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p):
            try:
                logo = Image.open(p).convert("RGBA")
                logo.thumbnail((156, 156))
                img.paste(logo, (img.width - logo.width - 44, 22), logo)
                return
            except Exception:
                pass
    draw.rounded_rectangle([(img.width - 196, 32), (img.width - 44, 114)], radius=16, fill=(32, 32, 38))
    draw.text((img.width - 172, 58), "RATE BOARD", fill=(250, 195, 25), font=f_badge)


def make_image(table, time_str, src):
    w, h = 1140, 960
    img = Image.new("RGB", (w, h), (14, 14, 16))
    draw = ImageDraw.Draw(img)

    f_title = pick_font(68)
    f_sub = pick_font(28)
    f_badge = pick_font(24)
    f_lbl = pick_font(30)
    f_val = pick_font(42)
    f_th = pick_font(32)
    f_row = pick_font(36)
    f_foot = pick_font(25)

    draw.text((44, 24), "Exchange Rates", fill=(255, 200, 25), font=f_title)
    draw.text((44, 106), f"MMK · {clean_txt(time_str)}", fill=(195, 195, 205), font=f_sub)
    draw_logo(img, draw, f_badge)

    draw.rounded_rectangle([(44, 160), (1096, 286)], radius=20, fill=(28, 28, 35), outline=(255, 200, 25), width=2)
    draw.text((70, 172), "Dollar to MMK (1 USD)", fill=(255, 200, 25), font=f_lbl)
    draw.text((70, 218), f"Buy: {table[0][1]} MMK", fill=(255, 255, 255), font=f_val)
    draw.text((585, 218), f"Sell: {table[0][2]} MMK", fill=(80, 230, 140), font=f_val)

    draw.text((48, 316), "Currency", fill=(255, 200, 25), font=f_th)
    draw.text((585, 316), "Buy", fill=(255, 200, 25), font=f_th)
    draw.text((865, 316), "Sell", fill=(255, 200, 25), font=f_th)
    draw.line([(44, 368), (1096, 368)], fill=(68, 68, 80), width=2)

    y = 388
    for i, r in enumerate(table):
        cur = clean_txt(r[0])
        if i % 2 == 1:
            draw.rounded_rectangle([(40, y - 12), (1100, y + 62)], radius=12, fill=(22, 22, 27))
        draw.text((52, y), cur, fill=(255, 255, 255), font=f_row)
        draw.text((560, y), r[1], fill=(255, 255, 255), font=f_row)
        draw.text((835, y), r[2], fill=(80, 230, 140) if "USD" in cur.upper() else (255, 255, 255), font=f_row)
        y += 82

    draw.line([(44, h - 70), (1096, h - 70)], fill=(68, 68, 80), width=1)
    draw.text((44, h - 52), f"Source: {clean_txt(src)} · Type /rates for latest update", fill=(195, 195, 205), font=f_foot)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def reply_photo(chat_id, thread_id, photo):
    form = {"chat_id": chat_id}
    if thread_id is not None:
        form["message_thread_id"] = thread_id
    requests.post(
        f"{TELEGRAM_API}/sendPhoto",
        data=form,
        files={"photo": ("rates.png", photo, "image/png")},
        timeout=20,
    )


def reply_text(chat_id, thread_id, txt):
    form = {"chat_id": chat_id, "text": txt}
    if thread_id is not None:
        form["message_thread_id"] = thread_id
    requests.post(f"{TELEGRAM_API}/sendMessage", json=form, timeout=10)


@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    msg = data.get("message")
    if msg and BOT_TOKEN:
        chat_id = msg["chat"]["id"]
        thread_id = msg.get("message_thread_id")
        txt = (msg.get("text") or "").strip()
        if txt.startswith(("/rates", "/currencyrates")):
            try:
                table, t_str, src = get_rates()
                photo = make_image(table, t_str, src)
                reply_photo(chat_id, thread_id, photo)
            except Exception as e:
                reply_text(chat_id, thread_id, f"Error: {e}")
    return "ok", 200


@app.route("/<path:token_path>", methods=["POST"])
def webhook_token(token_path):
    if BOT_TOKEN and token_path == BOT_TOKEN:
        return webhook()
    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
