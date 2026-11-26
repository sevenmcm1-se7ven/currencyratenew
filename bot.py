function updateRatesSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("Sheet1");

  // 1) Bybit P2P ကနေ USDT -> MMK ဈေးနှုန်းဆွဲယူခြင်း
  // side: "1" = Sell USDT (Buy MMK), "0" = Buy USDT (Sell MMK)
  const bybitPayload = {
    userId: "",
    tokenId: "USDT",
    currencyId: "MMK",
    payment: [],
    side: "0",
    size: "10",
    page: "1",
    amount: "",
    vaMaker: false,
    bulkProd: false,
    canTrade: false,
    sortType: "OVERALL"
  };

  const bybitRes = UrlFetchApp.fetch(
    "https://api2.bybit.com/fiat/otc/item/online",
    {
      method: "post",
      contentType: "application/json",
      headers: {
        "User-Agent": "Mozilla/5.0"
      },
      payload: JSON.stringify(bybitPayload),
      muteHttpExceptions: true
    }
  );

  let usdSell = null;
  if (bybitRes.getResponseCode() === 200) {
    const bybitJson = JSON.parse(bybitRes.getContentText());
    const items =
      (bybitJson && bybitJson.result && bybitJson.result.items) || [];

    if (items.length > 0) {
      const topPrices = items
        .slice(0, 3)
        .map((item) => parseFloat(item.price))
        .filter((n) => !isNaN(n) && n > 0);

      if (topPrices.length > 0) {
        usdSell = topPrices.reduce((a, b) => a + b, 0) / topPrices.length;
      }
    }
  }

  // Bybit API ခေတ္တမရပါက Fallback ဈေး
  if (!usdSell) {
    usdSell = 5585.0;
  }

  const usdBuy = usdSell * 0.985;

  // 2) အခြား ငွေကြေးများအတွက် Cross-rate တွက်ချက်ခြင်း
  const fxRes = UrlFetchApp.fetch("https://open.er-api.com/v6/latest/USD", {
    muteHttpExceptions: true
  });
  const fxJson = JSON.parse(fxRes.getContentText());
  const fxRates = (fxJson && fxJson.rates) || {};

  const fmt = (val) =>
    Number(val).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });

  const fmtUsd = (val) =>
    Number(val).toLocaleString("en-US", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2
    });

  const calcMMK = (code, mult) => {
    const unitPerUsd = fxRates[code];
    if (!unitPerUsd) return "-";
    const mmkPerUnit = usdSell / unitPerUsd;
    return fmt(mmkPerUnit * mult);
  };

  const rows = [
    ["USD (ဒေါ်လာ)", fmtUsd(usdBuy), fmtUsd(usdSell)],
    ["THB (ထိုင်းဘတ်)", calcMMK("THB", 0.985), calcMMK("THB", 1.0)],
    ["JPY (ဂျပန်ယန်း)", calcMMK("JPY", 0.985), calcMMK("JPY", 1.0)],
    ["CNY (တရုတ်ယွမ်)", calcMMK("CNY", 0.985), calcMMK("CNY", 1.0)],
    ["MYR (မလေးရှားရင်းဂစ်)", calcMMK("MYR", 0.985), calcMMK("MYR", 1.0)],
    ["SGD (စင်ကာပူဒေါ်လာ)", calcMMK("SGD", 0.985), calcMMK("SGD", 1.0)]
  ];

  sheet.getRange("A2:C7").setValues(rows);

  const nowStr = Utilities.formatDate(
    new Date(),
    "Asia/Yangon",
    "dd MMM yyyy · hh:mm a"
  );
  sheet.getRange("D1").setValue("Updated · " + nowStr);
}
