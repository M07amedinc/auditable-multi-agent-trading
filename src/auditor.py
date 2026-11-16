"""THE AUDITOR - records every decision, tags outcomes, writes lessons.
"""
import json, os
from datetime import datetime, timezone

OUTCOME_TAGS = ["good_reasoning", "bad_data", "bad_timing", "mandate_block", "market_move"]

class Auditor:
    def __init__(self, path: str = "logs/audit.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def log_decision(self, record: dict):
        record["logged_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def post_mortem(self, record: dict, outcome: dict) -> str:
        """Return the one-sentence lesson for a closed trade."""
        pnl = outcome.get("pnl_pct", 0)
        if pnl > 0:
            return f"win ({pnl:+.1f}%): reasoning held under {outcome.get('regime', 'unknown')} regime"
        return (f"loss ({pnl:+.1f}%): tagged {outcome.get('tag', 'market_move')} - "
                f"{outcome.get('note', 'no note')}")
