"""Lists the models YOUR keys can actually use. Run: python list_models.py
Then paste valid IDs into .env (LLM_2_MODEL / LLM_3_MODEL)."""
import os, requests
from dotenv import load_dotenv
load_dotenv()

k2 = os.getenv("LLM_2_KEY")
if k2:
    r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={k2}", timeout=30)
    if r.status_code == 200:
        ids = [m["name"].replace("models/", "") for m in r.json().get("models", [])]
        flash = [i for i in ids if "flash" in i.lower()]
        print("GEMINI flash models (pick one):")
        for i in flash[:8]:
            print("  ", i)
    else:
        print("gemini key invalid or list failed:", r.status_code, r.text[:150])
else:
    print("LLM_2_KEY not set")

k3 = os.getenv("LLM_3_KEY")
if k3:
    r = requests.get("https://openrouter.ai/api/v1/models",
                     headers={"Authorization": f"Bearer {k3}"}, timeout=30)
    if r.status_code == 200:
        free = [m["id"] for m in r.json()["data"] if m["id"].endswith(":free")]
        print("\nOPENROUTER free models (pick one):")
        for i in free[:15]:
            print("  ", i)
    else:
        print("openrouter key invalid or list failed:", r.status_code, r.text[:150])
else:
    print("LLM_3_KEY not set")
