"""Phase 1 - SCHOOL. v3: parallel Bull/Bear calls (threads), honest tagging, stats."""
import json, os, time
from concurrent.futures import ThreadPoolExecutor
from src.load_data import get_data
from src.mandate import MandateLayer
from src.auditor import Auditor
from src.memory import LessonsMemory
from src.agents import bull_agent, bear_agent, verifier_agent, decide
from src.filter import is_special_happening

CFG = json.load(open("config/watchlist.json"))
CAPITAL0 = CFG["portfolio"]["starting_capital_usd"]

def run_backtest(use_llm: bool = False, out: str = "logs/decisions.jsonl"):
    os.makedirs("logs", exist_ok=True)
    mandate = MandateLayer()
    auditor = Auditor()
    memory = LessonsMemory()
    records = []
    stats = {"total": 0, "agent_error": 0, "verdicts": {"verified": 0, "false": 0, "unverifiable": 0}}

    for coin in CFG["coins"]:
        df = get_data(coin)
        for i in range(35, len(df) - 7):
            snap = df.iloc[i-30:i]
            if not is_special_happening(snap):
                continue
            stats["total"] += 1
            lessons = memory.relevant({"coin": coin, "mode": "trader"})
            # Bull and Bear are independent -> run them in parallel threads
            with ThreadPoolExecutor(max_workers=2) as ex:
                fb = ex.submit(bull_agent, snap, lessons, use_llm)
                fr = ex.submit(bear_agent, snap, lessons, use_llm)
                bull, bear = fb.result(), fr.result()
            time.sleep(1.0)
            # Verifier needs both arguments -> runs after
            verdicts = verifier_agent(bull, bear, snap, use_llm=use_llm); time.sleep(1.0)
            for v in verdicts:
                stats["verdicts"][v.status] = stats["verdicts"].get(v.status, 0) + 1
            if bull.claims == ["agent_error"] and bear.claims == ["agent_error"]:
                stats["agent_error"] += 1
            decision = decide(bull, bear, verdicts)
            size_pct = 3.0
            md = mandate.check({"symbol": coin, "size_pct": size_pct, "mode": "trader"},
                               {"drawdown_pct": 0, "trades_today": 0, "allowed_tokens": CFG["coins"]})
            entry = float(df.iloc[i]["close"])
            future = df.iloc[i+1:i+8]["close"]
            exit_p = float(future.max()) if decision == "BUY" else float(future.min())
            pnl_pct = round((exit_p - entry) / entry * 100 if decision == "BUY"
                            else (entry - exit_p) / entry * 100, 2)
            if not md.allowed:
                final, tag = "BLOCKED", "mandate_block"
            elif decision == "HOLD":
                final, tag = "HOLD", "no_trade"
            else:
                final, tag = decision, ("good_reasoning" if pnl_pct > 0 else "bad_timing")
            record = {
                "date": str(df.iloc[i]["timestamp"])[:10], "coin": coin, "decision": final,
                "why": {
                    "bull_claims": bull.claims, "bear_claims": bear.claims,
                    "verifier": {v.claim: v.status for v in verdicts},
                    "winning_reason": "weighted_verified_claims",
                    "mandate": "allowed" if md.allowed else f"blocked: {md.reasons}",
                },
                "outcome": {"pnl_pct": pnl_pct, "tag": tag}
            }
            records.append(record)
            auditor.log_decision(record)
            if final in ("BUY", "SELL"):
                memory.add(auditor.post_mortem(record, record["outcome"]),
                           {"coin": coin, "mode": "trader"}, record["date"])

    with open(out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    trades = [r for r in records if r["decision"] in ("BUY", "SELL")]
    wins = [r for r in trades if r["outcome"]["pnl_pct"] > 0]
    print(f"backtest done: {len(records)} records -> {out}")
    print(f"  agent failures: {stats['agent_error']}/{stats['total']} days")
    print(f"  verdicts: {stats['verdicts']}")
    print(f"  real trades: {len(trades)} | wins: {len(wins)} ({100*len(wins)/max(len(trades),1):.0f}%)")
    print(f"  mean pnl on trades: {sum(r['outcome']['pnl_pct'] for r in trades)/max(len(trades),1):.2f}%")
    return records

if __name__ == "__main__":
    import sys
    run_backtest(use_llm="--llm" in sys.argv)
