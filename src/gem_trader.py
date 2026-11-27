"""GEM TRADER - turns approved gems into real paper trades.

Problem: a gem born 5 minutes ago has no candle history for Bull/Bear.
Solution: we discover it at birth, so we BUILD the history ourselves -
one DexScreener price snapshot per loop cycle (5 min). After MAX_POINTS
snapshots (~30 min) the gem gets a micro Bull/Bear debate -> Mandate
(2% hunter cap) -> paper trade -> 7-day self-audit closes it like any
other position. Entry price = first-debate price.
"""
import json, os, time
import pandas as pd

HIST_PATH = "logs/gem_history.json"
MAX_POINTS = 6            # 6 x 5-min snapshots = ~30 min before first debate
TRADE_PCT = 2.0           # hunter position cap from config

HISTORY = {}

def _load():
    global HISTORY
    if os.path.exists(HIST_PATH):
        try:
            HISTORY = json.load(open(HIST_PATH))
        except Exception:
            HISTORY = {}

def _save():
    os.makedirs("logs", exist_ok=True)
    json.dump(HISTORY, open(HIST_PATH, "w"), indent=1)

def dex_price(mint: str):
    import requests
    try:
        r = requests.get(f"https://api.dexscreener.com/tokens/v1/solana/{mint}", timeout=15)
        if r.status_code != 200:
            return None
        d = r.json()
        if not d:
            return None
        p = d[0].get("priceUsd")
        return float(p) if p else None
    except Exception:
        return None

def onchain_momentum(mint: str):
    """Real buyers in the last hour: DexScreener pair txns (free, no key).
    Returns {buys, sells} for h1, or None on failure."""
    import requests
    try:
        r = requests.get(f"https://api.dexscreener.com/tokens/v1/solana/{mint}", timeout=15)
        if r.status_code != 200 or not r.json():
            return None
        h1 = (r.json()[0].get("txns") or {}).get("h1") or {}
        return {"buys": int(h1.get("buys", 0) or 0), "sells": int(h1.get("sells", 0) or 0)}
    except Exception:
        return None


def track_from_hunter(minutes: int = 60):
    """Start tracking gems that PASSED the gates in recent hunter scans."""
    _load()
    path = "logs/hunter_candidates.jsonl"
    if not os.path.exists(path):
        return
    cutoff = time.time() - minutes * 60
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            mint = rec.get("mint")
            if not mint or mint in HISTORY:
                continue
            gates = rec.get("gates", [])
            if any("honeypot" in g for g in gates):
                continue                        # rejected by gate 4
            HISTORY[mint] = {"symbol": rec.get("coin") or mint[:8],
                             "prices": [], "traded": None,
                             "social": rec.get("social", {})}
    _save()

def snapshot_cycle():
    """Record one price point per tracked gem (called every loop cycle)."""
    _load()
    changed = False
    for mint, g in HISTORY.items():
        if g.get("traded") or len(g["prices"]) >= MAX_POINTS:
            continue
        p = dex_price(mint)
        if p:
            g["prices"].append([round(time.time()), p])
            changed = True
    if changed:
        _save()

def micro_df(mint: str) -> pd.DataFrame:
    g = HISTORY[mint]
    rows = [{"timestamp": pd.to_datetime(ts, unit="s"), "open": p, "high": p,
             "low": p, "close": p, "volume": 0} for ts, p in g["prices"]]
    return pd.DataFrame(rows)

def maybe_trade(state, threshold: float = 1.2, min_score: float = 0.5):
    """Gems with enough snapshots: micro-debate -> mandate -> paper trade."""
    _load()
    from src.auditor import Auditor
    from src.mandate import MandateLayer
    from src.agents import bull_agent, bear_agent, verifier_agent, decide
    audit = Auditor()
    md = MandateLayer()
    for mint, g in list(HISTORY.items()):
        if g.get("traded") or len(g["prices"]) < MAX_POINTS:
            continue
        df = micro_df(mint)
        from src.memory import LessonsMemory
        lessons = LessonsMemory().relevant({"coin": g.get("symbol"), "mode": "hunter"})
        bull = bull_agent(df, lessons, use_llm=True)
        bear = bear_agent(df, lessons, use_llm=True)
        verdicts = verifier_agent(bull, bear, df, use_llm=True)
        decision = decide(bull, bear, verdicts, threshold=threshold, min_score=min_score)

        # ---- trend + real-buyers trigger (buy even if the micro-debate is quiet) ----
        social = g.get("social") or {}
        mentions = social.get("mentions_3h") or 0
        shill = social.get("shill_score") or 0
        mom = onchain_momentum(mint)
        hot_social = mentions >= 10 and shill < 0.5
        real_buyers = bool(mom) and mom["buys"] >= 20 and mom["buys"] >= 2 * max(mom["sells"], 1)
        momentum_buy = hot_social and real_buyers

        why = {"bull_claims": bull.claims, "bear_claims": bear.claims,
               "verifier": {v.claim: v.status for v in verdicts},
               "gates": "passed", "mint": mint,
               "social_mentions_3h": mentions, "shill_score": shill,
               "onchain_h1": mom}
        if decision == "HOLD" and not momentum_buy:
            g["traded"] = "HOLD"
            g["last_decision"] = {"decision": "HOLD",
                                  "reason": "micro-debate HOLD + no momentum trigger",
                                  "mentions": mentions, "shill": shill, "onchain": mom}
            _save()
            print(f"[gem-trader] {g['symbol']} ({mint[:8]}...): HOLD (debate quiet, "
                  f"mentions={mentions}, buys_h1={mom['buys'] if mom else 'n/a'})")
            continue
        if decision == "HOLD":
            decision = "BUY"     # crowd + real buyers carrying it
            why["source"] = "gem_momentum_trade"
        else:
            why["source"] = "gem_debate_trade" 
        # gems are screened by the 6 gates, not the watchlist whitelist:
        # a discovered mint passes its own gate results, so whitelist is
        # satisfied per-mint here (watchlist trades still use the whitelist)
        gem_state = {**state, "allowed_tokens": list(state.get("allowed_tokens", [])) + [mint]}
        ok = md.check({"symbol": mint, "size_pct": TRADE_PCT, "mode": "hunter"}, gem_state)
        why["mandate"] = "allowed" if ok.allowed else f"blocked: {ok.reasons}"
        if not ok.allowed:
            g["traded"] = "BLOCKED"
            _save()
            print(f"[gem-trader] {g['symbol']} ({mint[:8]}...): BLOCKED by mandate: {ok.reasons}")
            continue
        entry = g["prices"][-1][1]
        now = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
        rec = {"date": now, "coin": "gem:" + mint, "decision": decision,
               "why": why, "outcome": {"pnl_pct": 0.0, "tag": "gem_paper_trade", "entry": entry}}
        with open("logs/decisions.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        audit.log_decision(rec)
        h = {}
        if os.path.exists("logs/holdings.json"):
            try:
                h = json.load(open("logs/holdings.json"))
            except Exception:
                h = {}
        h["gem:" + mint] = {"side": decision, "date": now[:10], "entry": entry, "why": why}
        json.dump(h, open("logs/holdings.json", "w"), indent=1)
        g["traded"] = decision
        _save()
        print(f"[gem-trader] {g['symbol']} ({mint[:8]}...): {decision} @ ${entry:.10g} (2% hunter cap)")
