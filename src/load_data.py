"""One function the whole system uses to read market data."""
import pandas as pd

def get_data(coin_id: str) -> pd.DataFrame:
    df = pd.read_csv(f"data/{coin_id}.csv", parse_dates=["timestamp"])
    return df.sort_values("timestamp").reset_index(drop=True)

def snapshot(coin_id: str, as_of: int, lookback: int = 30):
    """Return the last `lookback` rows strictly BEFORE index as_of.
    This prevents look-ahead bias: the system never sees future data."""
    df = get_data(coin_id)
    return df.iloc[max(0, as_of - lookback):as_of]
