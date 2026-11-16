"""Single place where LLM calls happen. Swap API here.
Default: local fine-tuned model (Stage B). Set LLM_PROVIDER=local|api in .env
"""
import os
PROVIDER = os.getenv("LLM_PROVIDER", "api")

def ask(prompt: str) -> str:
    if PROVIDER == "local":
        from unsloth import FastLanguageModel
        # load adapters from models/bull_bear_v1 - cached after first load
        raise NotImplementedError("wire local model loading here")
    import requests
    key = os.getenv("LLM_API_KEY")
    r = requests.post("https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "gpt-4o-mini",
              "messages": [{"role": "user", "content": prompt}]}, timeout=60)
    return r.json()["choices"][0]["message"]["content"]
