"""Builds DPO preference pairs from decision records.
chosen = winning side's argument, rejected = losing side's (same situation).
Output: logs/dpo_pairs.jsonl
"""
import json

def build(records_path="logs/decisions.jsonl", out="logs/dpo_pairs.jsonl",
          min_abs_pnl: float = 1.0):
    n = skipped = 0
    with open(out, "w") as fo:
        for line in open(records_path):
            r = json.loads(line)
            if r["decision"] not in ("BUY", "SELL"):
                continue
            bull, bear = r["why"]["bull_claims"], r["why"]["bear_claims"]
            if bull == ["agent_error"] or bear == ["agent_error"]:
                skipped += 1
                continue
            pnl = r["outcome"]["pnl_pct"]
            if abs(pnl) < min_abs_pnl:
                skipped += 1
                continue
            situation = (f"Coin {r['coin']} on {r['date']}. "
                         f"DATA-DRIVEN DEBATE. Bull claims: {bull}. Bear claims: {bear}.")
            winner = bull if r["decision"] == "BUY" else bear
            loser = bear if r["decision"] == "BUY" else bull
            fo.write(json.dumps({
                "prompt": situation,
                "chosen": f"Decision: {r['decision']}. Reasoning: {winner}",
                "rejected": f"Decision: {'SELL' if r['decision']=='BUY' else 'BUY'}. Reasoning: {loser}",
                "margin": abs(pnl)
            }) + "\n")
            n += 1
    print(f"DPO pairs: {n} (skipped {skipped}) -> {out}")

if __name__ == "__main__":
    build()