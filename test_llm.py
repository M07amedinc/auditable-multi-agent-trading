import requests
import os
from dotenv import load_dotenv
load_dotenv()

BASE = os.getenv("LLM_BASE_URL")
KEY = os.getenv("LLM_API_KEY")
MODEL = os.getenv("LLM_MODEL")
print("using model:", MODEL)

# test 1: is the key valid? (lists your available models)
r = requests.get(f"{BASE}/models",
                 headers={"Authorization": f"Bearer {KEY}"}, timeout=30)
print("key test:", r.status_code)
if r.status_code == 200:
    ids = [m["id"] for m in r.json().get("data", [])]
    print("available models:", ids[:10])

# test 2: does a chat call work?
r = requests.post(f"{BASE}/chat/completions",
                  headers={"Authorization": f"Bearer {KEY}"},
                  json={"model": MODEL, "messages": [
                      {"role": "user", "content": "say OK"}]},
                  timeout=60)
print("chat test:", r.status_code, "-", r.text[:200])
