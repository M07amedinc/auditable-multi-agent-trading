"""Quotes + honeypot probe via Jupiter (updated endpoints: api.jup.ag).
NOTE: Jupiter's v1 API is mainnet-only; the old quote-api.jup.ag domain is retired.
Swap execution requires a free API key: https://portal.jup.ag -> JUPITER_API_KEY in .env
(quotes work without a key, verified).
"""
import os, requests

QUOTE = "https://api.jup.ag/swap/v1/quote"
SWAP = "https://api.jup.ag/swap/v1/swap"

SOL = "So11111111111111111111111111111111111111112"

def get_quote(input_mint: str, output_mint: str, amount_lamports: int, devnet: bool = False) -> dict:
    """devnet param kept for backwards compatibility; Jupiter v1 serves mainnet."""
    r = requests.get(QUOTE, params={
        "inputMint": input_mint, "outputMint": output_mint,
        "amount": amount_lamports, "slippageBps": 50}, timeout=30)
    r.raise_for_status()
    return r.json()

def honeypot_probe(token_mint: str, devnet: bool = False):
    """True = sell route exists. False = no route (honeypot or zero liquidity).
    None = network error / API down (UNKNOWN - do not treat as scam)."""
    try:
        q = get_quote(token_mint, SOL, 1_000_000, devnet=devnet)
        return bool(q.get("routePlan"))
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code in (400, 404, 500):
            return False          # API reached us and said: no route for this token
        return None               # something else - unknown
    except Exception:
        return None               # DNS/network failure - unknown, never call it a scam

def get_swap_tx(quote_response: dict, user_public_key: str) -> str:
    """Builds an unsigned swap transaction (base64). Requires JUPITER_API_KEY (free)."""
    key = os.getenv("JUPITER_API_KEY", "").strip()
    headers = {"x-api-key": key} if key else {}
    r = requests.post(SWAP, headers=headers, json={
        "quoteResponse": quote_response, "userPublicKey": user_public_key,
        "wrapAndUnwrapSol": True}, timeout=30)
    r.raise_for_status()
    return r.json()["swapTransaction"]
