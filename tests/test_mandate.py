"""Prove the Mandate Layer blocks what it should. Run: python -m pytest tests/
"""
from src.mandate import MandateLayer

m = MandateLayer()
state = {"drawdown_pct": 5, "trades_today": 1, "allowed_tokens": ["SOL", "BONK"]}

def test_oversized_position_blocked():
    d = m.check({"symbol": "SOL", "size_pct": 6, "mode": "trader"}, state)
    assert not d.allowed and any("position" in r for r in d.reasons)

def test_drawdown_stop():
    d = m.check({"symbol": "SOL", "size_pct": 3, "mode": "trader"},
                {**state, "drawdown_pct": 20})
    assert not d.allowed and any("drawdown" in r for r in d.reasons)

def test_disallowed_token():
    d = m.check({"symbol": "SCAM", "size_pct": 1, "mode": "trader"}, state)
    assert not d.allowed and any("allowed list" in r for r in d.reasons)

def test_legal_trade_passes():
    d = m.check({"symbol": "SOL", "size_pct": 4, "mode": "trader"}, state)
    assert d.allowed
