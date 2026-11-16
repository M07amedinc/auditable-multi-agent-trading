"""Execution via Jupiter (quotes + swap). Devnet first.
Docs: https://dev.jup.ag/docs/
"""
import os, requests
from dotenv import load_dotenv
load_dotenv()

QUOTE = "https://quote-api.jup.ag/v6/quote"
SWAP = "https://quote-api.jup.ag/v6/swap"

SOL = "So11111111111111111111111111111111111111112"

def get_quote(input_mint: str, output_mint: str, amount_lamports: int, devnet: bool = True) -> dict:
    params = {"inputMint": input_mint, "outputMint": output_mint,
              "amount": amount_lamports, "slippageBps": 50}
    url = "https://quote-api.devnet.jup.ag/v6/quote" if devnet else QUOTE
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def honeypot_probe(token_mint: str, devnet: bool = True) -> bool:
    """Scam check #8: can this token actually be SOLD?
    Ask Jupiter for a sell quote (token -> SOL). If it fails -> honeypot."""
    try:
        q = get_quote(token_mint, SOL, 1_000_000, devnet=devnet)
        return bool(q.get("routePlan"))
    except Exception:
        return False
