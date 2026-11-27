"""Real devnet execution via Jupiter. Signs and sends actual transactions
on Solana devnet (fake SOL, real blockchain). Requires:
  - .env: DEVNET_PRIVATE_KEY (base64) + HELIUS_KEY
  - devnet wallet funded: https://faucet.solana.com
"""
import os, base64, requests
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

SOL = "So11111111111111111111111111111111111111112"
QUOTE = "https://quote-api.devnet.jup.ag/v6/quote"
SWAP = "https://api.jup.ag/swap/v1/swap"

def _keypair() -> Keypair:
    raw = os.getenv("DEVNET_PRIVATE_KEY", "").strip()
    if not raw:
        raise RuntimeError("DEVNET_PRIVATE_KEY missing in .env (run: python gen_key.py)")
    try:
        return Keypair.from_bytes(base64.b64decode(raw))
    except Exception:
        return Keypair.from_bytes(bytes.fromhex(raw))

def public_key() -> str:
    return str(_keypair().pubkey())

def swap_devnet(input_mint: str, output_mint: str, amount_lamports: int,
                slippage_bps: int = 100):
    """Returns (tx_signature, error)."""
    try:
        kp = _keypair()
        q = requests.get(QUOTE, params={"inputMint": input_mint,
            "outputMint": output_mint, "amount": amount_lamports,
            "slippageBps": slippage_bps}, timeout=30)
        q.raise_for_status()
        jkey = os.getenv("JUPITER_API_KEY", "").strip()
        s = requests.post(SWAP, headers={"x-api-key": jkey} if jkey else {},
            json={"quoteResponse": q.json(),
            "userPublicKey": str(kp.pubkey()), "wrapAndUnwrapSol": True}, timeout=30)
        s.raise_for_status()
        tx = VersionedTransaction.from_bytes(base64.b64decode(s.json()["swapTransaction"]))
        signed = VersionedTransaction(tx.message, [kp])
        helius = os.getenv("HELIUS_KEY", "").strip()
        rpc = (f"https://devnet.helius-rpc.com/?api-key={helius}"
               if helius else "https://api.devnet.solana.com")
        r = requests.post(rpc, json={"jsonrpc": "2.0", "id": 1,
            "method": "sendTransaction",
            "params": [base64.b64encode(bytes(signed)).decode()]}, timeout=30)
        r.raise_for_status()
        out = r.json()
        if "error" in out:
            return None, str(out["error"])[:200]
        sig = out.get("result", "")
        explorer = f"https://explorer.solana.com/tx/{sig}?cluster=devnet"
        return sig, explorer
    except Exception as e:
        return None, str(e)[:200]
