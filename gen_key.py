"""Generates a devnet wallet. Run: python gen_key.py
Copy the PRIVATE line into .env as DEVNET_PRIVATE_KEY=...
Then fund the PUBLIC key at https://faucet.solana.com"""
import base64
from solders.keypair import Keypair

kp = Keypair()
print("=== DEVNET WALLET (safe: fake money, devnet only) ===")
print("PUBLIC KEY :", kp.pubkey())
print("PRIVATE KEY (paste into .env):", base64.b64encode(bytes(kp)).decode())
