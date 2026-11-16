"""'Is something special happening?' - pure pandas, no LLM."""
def is_special_happening(snap) -> bool:
    vol = snap["volume"] if "volume" in snap else snap["close"] * 0 + 1
    v_today = vol.iloc[-1]
    v_avg = vol.iloc[:-1].mean()
    chg = (snap["close"].iloc[-1] - snap["close"].iloc[-2]) / snap["close"].iloc[-2] * 100
    return bool(v_today > 3 * max(v_avg, 1e-9) or abs(chg) > 8)
