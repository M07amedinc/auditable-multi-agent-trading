"""LIVE LOOP - the full pipeline, wired end to end.

  python -m src.run_live --paper    # dry run: analyze + log, no transactions (DEFAULT)
  python -m src.run_live            # same as --paper (safety: paper is always default)
  python -m src.run_live --live     # REALLY executes swaps on devnet via Jupiter

Loop interval: LOOP_MINUTES env var (default 60).

Modes:
  WATCHLIST: for each configured coin, fetch last 35 daily candles (Binance/Bybit),
             run filter -> Bull/Bear -> Verifier -> Mandate. Paper: log only.
  HUNTER:    scan DexScreener candidates -> honeypot probe (gate 4) -> log.
             External gates (RugCheck/GoPlus/behaviour) hook in at _external_gates().

Safety notes:
  - Paper mode NEVER signs anything.
  - --live uses Jupiter devnet ONLY (quote-api.devnet.jup.ag). Put your devnet
    wallet key in .env as DEVNET_PRIVATE_KEY when you are ready; never commit it.
"""
import json, os, sys, time, traceback
import pandas as pd
from src.hunter import scan_candidates
from src.agents import bull_agent, bear_agent, verifier_agent, decide
from src.mandate import MandateLayer
from src.auditor import Auditor
from src.memory import LessonsMemory
from src.filter import is_special_happening
from src.fetch_data import fetch_binance
from src.jupiter import get_quote, honeypot_probe

PAPER = "--live" not in sys.argv            # safety: default is ALWAYS paper
LOOP_MIN = int(os.getenv("LOOP_MINUTES", "60"))
CFG = json.load(open("config/watchlist.json"))
PORT = CFG["portfolio"]
STATE = {"cash": PORT["starting_capital_usd"], "holdings": {}, "trades_today": 0,
         "drawdown_pct": 0.0, "allowed_tokens": CFG["coins"]}
HOLDINGS_PATH = "logs/holdings.json"
HOLD_DAYS = 7

def _load_holdings():
    if os.path.exists(HOLDINGS_PATH):
        try:
            return json.load(open(HOLDINGS_PATH))
        except Exception:
            return {}
    return {}

def _save_holdings(h):
    with open(HOLDINGS_PATH, "w") as f:
        json.dump(h, f, indent=1)

HOLDINGS = _load_holdings()
BINMAP = CFG.get("binance", {})
BYBITMAP = CFG.get("bybit", {})
MANDATE = MandateLayer()
AUDIT = Auditor()
MEM = LessonsMemory()

def candles(symbol_id: str) -> pd.DataFrame:
    """Recent daily candles for a watchlist coin (last ~35 days)."""
    df = None
    if symbol_id in BINMAP:
        df = fetch_binance(BINMAP[symbol_id])
    if df is None and symbol_id in BYBITMAP:
        try:
            from src.fetch_data import fetch_bybit
            df = fetch_bybit(BYBITMAP[symbol_id])
        except (ImportError, AttributeError):
            pass
    if df is None:
        return None
    return df.tail(35).reset_index(drop=True)

def audit_open_trades():
    """Close paper positions older than HOLD_DAYS: compute PnL, tag the
    outcome, log the full record, and write a LESSON to memory.
    This is what makes the live system actually self-learning."""
    today = pd.Timestamp.utcnow().normalize()
    for sym, pos in list(HOLDINGS.items()):
        entry_date = pd.Timestamp(pos["date"])
        if (today - entry_date).days < HOLD_DAYS:
            continue
        df = candles(sym)
        if df is None or len(df) == 0:
            continue
        exit_p = float(df.iloc[-1]["close"])
        entry_p = float(pos["entry"])
        if pos["side"] == "BUY":
            pnl = round((exit_p - entry_p) / entry_p * 100, 2)
        else:
            pnl = round((entry_p - exit_p) / entry_p * 100, 2)
        tag = "good_reasoning" if pnl > 0 else "bad_timing"
        rec = {"date": str(today.date()), "coin": sym,
               "decision": pos["side"] + "_CLOSED", "why": pos.get("why", {}),
               "outcome": {"pnl_pct": pnl, "tag": tag,
                           "entry": entry_p, "exit": exit_p,
                           "held_days": (today - entry_date).days}}
        AUDIT.log_decision(rec)
        with open("logs/decisions.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        MEM.add(f"{'win' if pnl>0 else 'loss'} ({pnl:+.1f}%): {tag}",
                {"coin": sym, "mode": "live"}, str(today.date()))
        del HOLDINGS[sym]
        print(f"[audit] {sym} {pos['side']} closed: {pnl:+.2f}% ({tag}) -> lesson written")
    _save_holdings(HOLDINGS)

def _external_gates(mint_or_symbol: str) -> tuple:
    """Hook for RugCheck / GoPlus / on-chain behaviour checks.
    Returns (passed, reasons). Degrades to 'pending' when no API keys are set -
    the honeypot probe (gate 4) always runs because it needs no key."""
    # TODO when you add a RugCheck key to .env (RUGCHECK_KEY):
    #   r = requests.get(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary",
    #                    headers={"x-api-key": os.getenv("RUGCHECK_KEY")}, timeout=30)
    #   parse risk score -> reject on HONEYPOT/RUG_PULL/FAKE_TOKEN or mint/freeze authority
    return True, ["external_gates_pending_keys"]

def gates(symbol_id, mint=None) -> tuple:
    reasons = []
    if mint:
        if not honeypot_probe(mint):                 # Gate 4 (always on)
            return False, ["gate4_honeypot"]
    ok, ext = _external_gates(mint or symbol_id)
    reasons += ext
    return ok, reasons

def record(decision, why, outcome_tag="no_trade", pnl=0.0, coin="-"):
    rec = {"date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "coin": coin, "decision": decision, "why": why,
           "outcome": {"pnl_pct": pnl, "tag": outcome_tag}}
    AUDIT.log_decision(rec)
    with open("logs/decisions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec

def process_coin(coin_id: str):
    df = candles(coin_id)
    if df is None or len(df) < 31:
        return
    snap = df.iloc[:-5] if len(df) > 34 else df       # agents see only closed candles
    if not is_special_happening(snap):
        return
    passed, gate_reasons = gates(coin_id)
    lessons = MEM.relevant({"coin": coin_id, "mode": "trader"})
    bull = bull_agent(snap, lessons, use_llm=True)
    bear = bear_agent(snap, lessons, use_llm=True)
    verdicts = verifier_agent(bull, bear, snap, use_llm=True)
    decision = decide(bull, bear, verdicts)
    why = {"bull_claims": bull.claims, "bear_claims": bear.claims,
           "verifier": {v.claim: v.status for v in verdicts},
           "gates": gate_reasons, "mandate": "pending"}
    if not passed:
        record("BLOCKED", why, "gate_reject", coin=coin_id); return
    if decision == "HOLD":
        record("HOLD", why, "no_trade", coin=coin_id); return
    md = MANDATE.check({"symbol": coin_id, "size_pct": 3.0, "mode": "trader"}, STATE)
    why["mandate"] = "allowed" if md.allowed else f"blocked: {md.reasons}"
    if not md.allowed:
        record("BLOCKED", why, "mandate_block", coin=coin_id); return
    if PAPER:
        record(decision, why, "paper_trade", coin=coin_id)
        HOLDINGS[coin_id] = {"side": decision, "date": str(pd.Timestamp.utcnow().date()),
                             "entry": float(snap.iloc[-1]["close"]), "why": why}
        _save_holdings(HOLDINGS)
        print(f"[paper] {coin_id}: {decision} (would execute on devnet)")
        return
    # --live: REAL execution on devnet (signed transactions via Jupiter)
    from src.execution_devnet import swap_devnet, SOL as SOL_MINT
    mint = CFG.get("mints", {}).get(coin_id)
    if not mint:
        record(decision, why, "live_skipped_no_mint", coin=coin_id)
        print(f"[live-devnet] {coin_id}: skipped (no mint address in config)")
        return
    if decision == "SELL":
        record(decision, why, "live_skipped_sell_needs_token_account", coin=coin_id)
        print(f"[live-devnet] {coin_id}: SELL skipped (token account not wired)")
        return
    sig, info = swap_devnet(SOL_MINT, mint, 50_000_000)   # 0.05 SOL per trade
    if sig:
        why["tx_signature"] = sig
        record(decision, why, "live_executed_devnet", coin=coin_id)
        print(f"[live-devnet] {coin_id}: BUY executed -> {info}")
    else:
        record(decision, why, f"live_failed: {info}", coin=coin_id)
        print(f"[live-devnet] {coin_id}: failed -> {info}")

def process_hunter():
    for c in scan_candidates():
        mint, sym = c["address"], c.get("symbol", "?")
        print(f"[hunter] candidate {sym} ({mint[:8]}...) vol24h={c['vol24h']:.0f}")
        ok, reasons = gates(sym, mint=mint)
        rec = {"coin": sym, "mint": mint, "signals": c.get("signals_fired"), "gates": reasons}
        with open("logs/hunter_candidates.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        if not ok:
            print(f"[hunter] {sym} REJECTED by gates: {reasons}")

def main():
    print(f"LIVE LOOP starting | paper={PAPER} | every {LOOP_MIN} min")
    print("Ctrl+C to stop. Logs: logs/decisions.jsonl, logs/audit.jsonl")
    while True:
        try:
            audit_open_trades()
            for coin in CFG["coins"]:
                process_coin(coin)
            process_hunter()
            STATE["trades_today"] = 0
        except KeyboardInterrupt:
            print("\nstopped by user"); break
        except Exception:
            traceback.print_exc()
            AUDIT.log_decision({"error": traceback.format_exc()[:400],
                                "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        print(f"[loop] sleeping {LOOP_MIN} min ...")
        time.sleep(LOOP_MIN * 60)

if __name__ == "__main__":
    main()
