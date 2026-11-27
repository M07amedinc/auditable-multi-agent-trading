"""Run ONCE: python tg_login.py
Logs into Telegram with your phone, saves tg_session.session."""
import os
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient

api_id = os.getenv("TG_API_ID", "").strip()
api_hash = os.getenv("TG_API_HASH", "").strip()
if not api_id or not api_hash:
    raise SystemExit("Set TG_API_ID and TG_API_HASH in .env first (my.telegram.org)")
TelegramClient("tg_session", int(api_id), api_hash).start()
print("saved tg_session.session - you never need to log in again")
