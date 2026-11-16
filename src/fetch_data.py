"""Stage 1 - Data Pipeline v3.
Primary source: Binance public klines API (NO key needed, full daily history
since 2024, generous limits). Fallback: CoinGecko OHLC (1 year, needs key).
Run ONCE:  python src/fetch_data.py
"""
import os, time, json, requests, datetime
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("COINGECKO_KEY")
HEADERS = {"x-cg-demo-api-key": KEY} if KEY else {}
CG = "https://api.coingecko.com/api/v3"
BIN = "https://api.binance.com/api/v3"

with open("config/watchlist.json") as f:
    CFG = json.load(f)
VS = CFG["vs_currency"]
BINMAP = CFG.get("binance", {})
os.makedirs("data", exist_ok=True)

def get(url, params, headers=None):
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers=headers or {}, timeout=30)
        except Exception as e:
            print(f"  network error: {e}")
            time.sleep(5)
            continue
        if r.status_code == 200:
            return r
        if r.status_code == 429:
            w = 20 * (attempt + 1)
            print(f"  rate limited, waiting {w}s ...")
            time.sleep(w)
            continue
        print(f"  HTTP {r.status_code}: {r.text[:100]}")
        return None
    return None

def fetch_binance(symbol):
    """Full daily candles from 2024-01-01 to today. No API key needed."""
    start = int(datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    rows = []
    while True:
        r = get(f"{BIN}/klines", {"symbol": symbol, "interval": "1d",
                                  "startTime": start, "limit": 1000})
        if r is None:
            return None
        data = r.json()
        if not data:
            break
        rows += data
        start = data[-1][0] + 86400000
        if len(data) < 1000:
            break
        time.sleep(1)
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["open_time","open","high","low","close",
                                     "volume","close_time","qav","trades","tbb","tbq","ig"])
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    return df[["timestamp","open","high","low","close","volume"]]

def fetch_coingecko(coin_id):
    """Fallback: last 365 days via OHLC endpoint."""
    r = get(f"{CG}/coins/{coin_id}/ohlc", {"vs_currency": VS, "days": 365}, headers=HEADERS)
    if r is None:
        return None
    df = pd.DataFrame(r.json(), columns=["timestamp","open","high","low","close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

if __name__ == "__main__":
    for coin in CFG["coins"]:
        path = f"data/{coin}.csv"
        if os.path.exists(path):
            print(f"skip {coin} (already downloaded)")
            continue
        print(f"fetching {coin} ...")
        df = None
        if coin in BINMAP:
            df = fetch_binance(BINMAP[coin])
            time.sleep(2)
        if df is None:
            print("  -> trying CoinGecko fallback (1 year only)")
            df = fetch_coingecko(coin)
        if df is not None and len(df):
            df.to_csv(path, index=False)
            print(f"  saved {len(df)} rows -> {path}")
        else:
            print(f"  FAILED {coin} (check id at coingecko.com)")
        time.sleep(3)
    print("done.")
