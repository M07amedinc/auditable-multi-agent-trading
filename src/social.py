"""Eye 3 - SOCIAL VELOCITY: Telegram + Twitter (Reddit REMOVED by user request).

SETUP (all free):
  TELEGRAM: https://my.telegram.org -> API development tools
      .env: TG_API_ID=123456, TG_API_HASH=...
      Then run ONCE:  python tg_login.py   (saves tg_session.session)
      Optional groups: TG_GROUPS=Name1,Name2  (public channel usernames)

  TWITTER/X: official portal now requires payment -> use any third-party
  free tier: .env TWITTER_API_URL=... + TWITTER_API_KEY=...
  (skip = logs show twitter: -1, everything else works)

Test:  python -m src.social sol bonk
"""
import os, re, time
from difflib import SequenceMatcher
from dotenv import load_dotenv
load_dotenv()

TG_GROUPS = [g.strip() for g in os.getenv("TG_GROUPS", "").split(",") if g.strip()]

# ---------------- Telegram (Telethon) ----------------
_tg = None
def _telegram():
    global _tg
    if _tg is not None:
        return _tg if _tg else None
    api_id, api_hash = os.getenv("TG_API_ID", ""), os.getenv("TG_API_HASH", "")
    if not api_id or not api_hash or not os.path.exists("tg_session.session"):
        _tg = False
        return None
    from telethon import TelegramClient
    _tg = TelegramClient("tg_session", int(api_id), api_hash)
    _tg.start()
    return _tg

def tg_mentions(keyword: str, hours: int = 3) -> int:
    c = _telegram()
    if c is None:
        return -1
    import datetime
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
    n, pat = 0, re.compile(re.escape(keyword.lower()))
    try:
        for g in TG_GROUPS:
            try:
                for m in c.iter_messages(g, limit=200):
                    if m.date and m.date.replace(tzinfo=datetime.timezone.utc) < since:
                        break
                    if m.message and pat.search(m.message.lower()):
                        n += 1
            except Exception:
                continue
    finally:
        c.disconnect()
    return n

def tg_shill(keyword: str, hours: int = 6) -> float:
    c = _telegram()
    if c is None:
        return 0.0
    import datetime
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
    pat = re.compile(re.escape(keyword.lower()))
    texts = []
    try:
        for g in TG_GROUPS:
            try:
                for m in c.iter_messages(g, limit=100):
                    if m.date and m.date.replace(tzinfo=datetime.timezone.utc) < since:
                        break
                    if m.message and pat.search(m.message.lower()):
                        t = re.sub(r"\s+", " ", m.message.lower()).strip()
                        if t:
                            texts.append(t)
            except Exception:
                continue
    finally:
        c.disconnect()
    return _dup_ratio(texts)

# ---------------- Twitter/X ----------------
def twitter_mentions(keyword: str, hours: int = 3) -> int:
    """Official API needs payment -> use a free third-party tier via env:
    TWITTER_API_URL + TWITTER_API_KEY. Returns -1 if not configured."""
    url, key = os.getenv("TWITTER_API_URL", "").strip(), os.getenv("TWITTER_API_KEY", "").strip()
    tok = os.getenv("TWITTER_BEARER_TOKEN", "").strip()
    try:
        import requests
        if tok:
            start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - hours * 3600))
            r = requests.get("https://api.twitter.com/2/tweets/counts/recent",
                params={"query": keyword, "start_time": start, "granularity": "day"},
                headers={"Authorization": f"Bearer {tok}"}, timeout=20)
            if r.status_code == 200:
                return sum(int(b.get("tweet_count", 0)) for b in r.json().get("data", []))
        if url and key:
            r = requests.get(url, params={"q": keyword, "hours": hours},
                headers={"Authorization": f"Bearer {key}"}, timeout=20)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, dict) and "mentions" in j:
                    return int(j["mentions"])
                if isinstance(j, list):
                    return len(j)
    except Exception:
        pass
    return -1

# ---------------- combined ----------------
def _dup_ratio(texts) -> float:
    if len(texts) < 4:
        return 0.0
    dup, total = 0, 0
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            total += 1
            if SequenceMatcher(None, texts[i], texts[j]).ratio() > 0.8:
                dup += 1
    return round(dup / max(total, 1), 2)

def social_boost(symbol: str) -> dict:
    key = symbol.lower().replace("$", "")
    t, x = tg_mentions(key), twitter_mentions(key)
    parts = [v for v in (t, x) if v >= 0]
    mentions = sum(parts) if parts else -1
    return {"mentions_3h": mentions, "shill_score": tg_shill(key),
            "breakdown": {"telegram": t, "twitter": x}}

if __name__ == "__main__":
    import sys
    for k in (sys.argv[1:] or ["sol", "bonk"]):
        print(k, "->", social_boost(k))
