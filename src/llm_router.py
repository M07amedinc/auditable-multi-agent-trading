"""Multi-provider LLM router v3 - with startup self-test.
Probes every configured provider with a 1-token call; DEAD providers are
removed so the backtest never wastes time on 404s.
Run  python test_providers.py  anytime to see the health report.
"""
import os, sys, time, requests, threading
from dotenv import load_dotenv
load_dotenv()

class Router:
    def __init__(self):
        self.providers = []
        for i in range(1, 5):
            base = os.getenv(f"LLM_{i}_BASE_URL")
            key = os.getenv(f"LLM_{i}_KEY")
            model = os.getenv(f"LLM_{i}_MODEL")
            if base and key and model:
                self.providers.append({"name": f"slot{i}:{model}",
                                       "base_url": base.rstrip("/"),
                                       "key": key, "model": model})
        self.calls = {p["name"]: 0 for p in self.providers}
        # --- Rate limiter: never exceed Groq free tier (~30 req/min) ---
        self.MAX_RPM = int(os.getenv("LLM_MAX_RPM", "27"))
        self._min_interval = 60.0 / self.MAX_RPM
        self._rl_lock = threading.Lock()
        self._last_req = 0.0

    def _throttle(self):
        """Enforce global min-interval so ALL calls together stay under MAX_RPM."""
        with self._rl_lock:
            wait = self._min_interval - (time.monotonic() - self._last_req)
            if wait > 0:
                time.sleep(wait)
            self._last_req = time.monotonic()

    def _raw_call(self, p, prompt):
        r = requests.post(f"{p['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {p['key']}"},
            json={"model": p["model"],
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.2},
            timeout=60)
        if r.status_code == 429:
            return None          # alive but busy
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def self_test(self, verbose=True):
        alive, dead = [], []
        for p in self.providers:
            try:
                out = self._raw_call(p, "Reply with the word OK")
                alive.append(p)
                if verbose:
                    print(f"  [OK]   {p['name']}")
            except Exception as e:
                dead.append((p, str(e)[:90]))
                if verbose:
                    print(f"  [DEAD] {p['name']} -> {str(e)[:90]}")
        self.providers = alive
        return alive, dead

    def ask(self, prompt: str, prefer: int = 0, retries: int = 8) -> str:
        """429 -> WAIT with growing backoff and retry the SAME provider
        (Mistral/Groq free tiers need breathing room). Only after all
        retries fail does it move to the next provider."""
        if not self.providers:
            raise RuntimeError("no working LLM providers - run: python test_providers.py")
        n = len(self.providers)
        order = [(prefer + k) % n for k in range(n)]
        last = None
        for idx in order:
            p = self.providers[idx]
            for attempt in range(retries):
                self._throttle()
                try:
                    out = self._raw_call(p, prompt)
                    if out is None:                      # 429: wait, retry same
                        wait = 8 * (attempt + 1)
                        print(f"  [{p['name']}] busy, waiting {wait}s", file=sys.stderr)
                        time.sleep(wait)
                        continue
                    self.calls[p["name"]] += 1
                    return out
                except Exception as e:
                    last = e
                    time.sleep(3)
            # provider exhausted its retries -> next one
        raise RuntimeError(f"all providers failed: {last}")

ROUTER = Router()
# Auto health-check at startup: dead providers are dropped immediately so
# no backtest time is wasted on them.
if os.getenv("SKIP_LLM_SELFTTEST") != "1":
    _alive, _ = ROUTER.self_test(verbose=True)
    if not _alive:
        print("!!! NO WORKING LLM PROVIDERS - fix .env (run: python list_models.py) !!!", file=sys.stderr)
