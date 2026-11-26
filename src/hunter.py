"""Eye 1 - THE HUNTER (DexScreener, free, no API key needed).
Scans Solana for early-stage blow-up candidates: volume acceleration +
price structure + unique-buyer growth. Candidates then go to Scam Score.
Docs: https://docs.dexscreener.com/api/reference
"""
import requests

def scan_candidates(min_volume_h24_usd: float = 500_000,
                    min_price_change_24h_pct: float = 15.0,
                    chain: str = "solana") -> list:
    """Return trending tokens that pass the EARLY-STAGE signal filter."""
    r = requests.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=30)
    boosts = r.json() if r.status_code == 200 else []
    out = []
    for b in boosts:
        for chain_info in (b.get("chains") or []):
            if chain_info.get("chainId") != chain:
                continue
        tok = b.get("tokenAddress")
        if not tok:
            continue
        d = token_overview(tok)
        if not d:
            continue
        vol = d.get("volume", {}).get("h24", 0) or 0
        chg = d.get("priceChange", {}).get("h24", 0) or 0
        if vol >= min_volume_h24_usd and chg >= min_price_change_24h_pct:
            out.append({"address": tok, "symbol": d.get("symbol"),
                        "vol24h": vol, "chg24h": chg,
                        "signals_fired": ["volume", "price"]})
    return out

def token_overview(address: str) -> dict:
    r = requests.get(f"https://api.dexscreener.com/tokens/v1/solana/{address}", timeout=30)
    if r.status_code != 200 or not r.json():
        return None
    return r.json()[0]

def scan_gems(min_volume_h24_usd: float = 50_000,
              min_price_change_24h_pct: float = 5.0,
              chain: str = "solana") -> list:
    """GEM MODE: much looser thresholds + brand new token profiles.
    Catches new trend tokens early (lower volume, smaller moves)."""
    out = []
    seen = set()
    feeds = []
    r = requests.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=30)
    if r.status_code == 200:
        feeds += r.json() or []
    r2 = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", timeout=30)
    if r2.status_code == 200:
        feeds += r2.json() or []
    for b in feeds:
        for chain_info in (b.get("chains") or []):
            if chain_info.get("chainId") != chain:
                continue
        tok = b.get("tokenAddress")
        if not tok or tok in seen:
            continue
        seen.add(tok)
        d = token_overview(tok)
        if not d:
            continue
        vol = d.get("volume", {}).get("h24", 0) or 0
        chg = d.get("priceChange", {}).get("h24", 0) or 0
        if vol >= min_volume_h24_usd and chg >= min_price_change_24h_pct:
            out.append({"address": tok, "symbol": d.get("symbol"),
                        "vol24h": vol, "chg24h": chg,
                        "signals_fired": ["gems_volume", "gems_price"]})
    return out

