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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}


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
        ["JPY (ဂျပန်ယန်း)", calc("JPY",
