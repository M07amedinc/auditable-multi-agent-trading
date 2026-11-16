"""Turns decision records into an SFT training dataset. v2: stricter filtering."""
import json

def build(records_path="logs/decisions.jsonl", out="logs/sft_dataset.jsonl"):
    n = wins = 0
    with open(out, "w") as fo:
        for line in open(records_path):
            r = json.loads(line)
            if r["decision"] not in ("BUY", "SELL"):
                continue
            real_sides = [s for s in ("bull", "bear") if r["why"][f"{s}_claims"] != ["agent_error"]]
            if not real_sides:
                continue
            situation = (f"Coin {r['coin']} on {r['date']}. "
                         f"Bull claims: {r['why']['bull_claims']}. "
                         f"Bear claims: {r['why']['bear_claims']}. "
                         f"Verifier: {r['why']['verifier']}.")
            winner_key = "bull_claims" if r["decision"] == "BUY" else "bear_claims"
            fo.write(json.dumps({
                "instruction": situation,
                "response": f"Decision: {r['decision']}. Reasoning: {r['why'][winner_key]}",
                "label": "win" if r["outcome"]["pnl_pct"] > 0 else "loss"
            }) + "\n")
            n += 1
            if r["outcome"]["pnl_pct"] > 0:
                wins += 1
    print(f"dataset: {n} examples ({wins} wins, {n-wins} losses) -> {out}")

if __name__ == "__main__":
    build()
