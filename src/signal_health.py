"""Signal Health + Scam Score (pure code, deterministic).
A candidate must PASS ALL checks to reach the agents.
"""
from dataclasses import dataclass, field

@dataclass
class ScamReport:
    passed: bool
    flags: list = field(default_factory=list)
    score: int = 0  # 0 = clean, higher = more suspicious

def check_holder_concentration(top10_pct: float, threshold: float = 40.0) -> str:
    return f"top10_holds_{top10_pct:.0f}pct" if top10_pct > threshold else None

def check_self_trade_pct(self_trade_pct: float, threshold: float = 30.0) -> str:
    return f"self_trades_{self_trade_pct:.0f}pct" if self_trade_pct > threshold else None

def check_unique_buyers(trade_count: int, unique_wallets: int, min_ratio: float = 0.3) -> str:
    if unique_wallets / max(trade_count, 1) < min_ratio:
        return "bot_volume_trades_gtgt_wallets"
    return None

def check_trade_uniformity(sizes: list, max_cv: float = 0.5) -> str:
    import statistics
    if len(sizes) < 10:
        return None
    cv = statistics.stdev(sizes) / (statistics.mean(sizes) + 1e-9)
    return "uniform_trade_sizes_bots" if cv < max_cv else None

def check_wallet_ages(ages_days: list, max_new_pct: float = 0.6) -> str:
    if not ages_days:
        return None
    new = sum(1 for a in ages_days if a < 7) / len(ages_days)
    return f"young_wallets_{new:.0%}" if new > max_new_pct else None

def check_funding_pattern(funder_counts: dict, max_from_one: int = 20) -> str:
    """funder_counts: {source_wallet: count_of_wallets_it_funded}."""
    if funder_counts and max(funder_counts.values()) >= max_from_one:
        return "one_wallet_funds_many"
    return None

def honeypot_check(can_sell: bool) -> str:
    return "honeypot_cannot_sell" if not can_sell else None

def full_scam_score(**kwargs) -> ScamReport:
    checks = [
        check_holder_concentration(kwargs.get("top10_pct", 0)),
        check_self_trade_pct(kwargs.get("self_trade_pct", 0)),
        check_unique_buyers(kwargs.get("trade_count", 1), kwargs.get("unique_wallets", 1)),
        check_trade_uniformity(kwargs.get("trade_sizes", [])),
        check_wallet_ages(kwargs.get("wallet_ages_days", [])),
        check_funding_pattern(kwargs.get("funder_counts", {})),
        honeypot_check(kwargs.get("can_sell", True)),
    ]
    flags = [c for c in checks if c]
    return ScamReport(passed=(len(flags) == 0), flags=flags, score=len(flags))
