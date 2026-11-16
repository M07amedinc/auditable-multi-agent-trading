"""THE MANDATE LAYER - pure code, never an LLM. The auditable gate.
"""
import json
from dataclasses import dataclass

@dataclass
class MandateDecision:
    allowed: bool
    reasons: list

class MandateLayer:
    def __init__(self, config_path: str = "config/watchlist.json"):
        with open(config_path) as f:
            self.rules = json.load(f)["portfolio"]

    def check(self, proposed_trade: dict, portfolio_state: dict) -> MandateDecision:
        r, reasons = self.rules, []
        if proposed_trade["size_pct"] > r["max_position_pct"]:
            reasons.append(f"position {proposed_trade['size_pct']}% > max {r['max_position_pct']}%")
        if proposed_trade.get("mode") == "hunter" and proposed_trade["size_pct"] > r["hunter_max_position_pct"]:
            reasons.append("hunter position too large")
        if portfolio_state.get("drawdown_pct", 0) > r["max_drawdown_pct"]:
            reasons.append("drawdown stop hit")
        if portfolio_state.get("trades_today", 0) >= r["max_trades_per_day"]:
            reasons.append("daily trade limit reached")
        if proposed_trade["symbol"] not in portfolio_state.get("allowed_tokens", []):
            reasons.append("token not in allowed list")
        return MandateDecision(allowed=(len(reasons) == 0), reasons=reasons)
