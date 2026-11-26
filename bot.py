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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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


def fetch_bybit():
    for side in ("0", "1"):
        try:
            r = requests.post(
                "https://api2.bybit.com/fiat/otc/item/online",
                json={
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
                },
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
    return None, None


def fetch_okx():
    try:
        r = requests.get(
            "https://www.okx.com/v3/c2c/tradingOrders/books?quoteCurrency=MMK&baseCurrency=USDT&side=sell&paymentMethod=all&userType=all&showTrade=false&showFollow=false&showAlreadyTraded=false&isAbleFilter=false",
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
    return None, None


def fetch_bitget():
    try:
        r = requests.post(
            "https://www.bitget.com/v1/p2p/pub/adv/queryAdvList",
            json={
                "coinCode": "USDT",
                "fiatCode": "MMK",
                "side": 1,
                "pageNo": 1,
                "pageSize": 10,
            },
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


def get_p2p():
    for fn in (fetch_bybit, fetch_okx, fetch_bitget):
        p, src = fn()
        if p:
            return p, src
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
    tmp_p = "/tmp/mm_font.ttf"
    if not os.path.exists(tmp_p):
        try:
            r = requests.get(
                "https://github.com/notofonts/myanmar/raw/main/fonts/NotoSansMyanmar/unhinted/ttf/NotoSansMyanmar-Medium.ttf",
                timeout=8,
            )
            if r.status_code == 200 and len(r.content) > 10000:
                with open(tmp_p, "wb") as f:
                    f.write(r.content)
        except Exception:
            pass
    if os.path.exists(tmp_p):
        try:
            return ImageFont.truetype(tmp_p, size)
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

    draw.
