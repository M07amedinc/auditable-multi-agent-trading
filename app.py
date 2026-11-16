"""FULL TRADING JOURNAL DASHBOARD. Run:  streamlit run app.py
Shows: every decision, every closed trade with PnL, win/loss totals,
last-30-days performance, and open positions with live unrealized PnL."""
import json, os, time, base64
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
load_dotenv()



def devnet_wallet():
    """Returns (sol_balance, usd_value, address) or (None, None, None)."""
    try:
        from solders.keypair import Keypair
        raw = os.getenv("DEVNET_PRIVATE_KEY", "").strip()
        if not raw:
            return None, None, None
        kp = Keypair.from_bytes(base64.b64decode(raw))
        addr = str(kp.pubkey())
        helius = os.getenv("HELIUS_KEY", "").strip()
        rpc = (f"https://devnet.helius-rpc.com/?api-key={helius}"
               if helius else "https://api.devnet.solana.com")
        r = requests.post(rpc, json={"jsonrpc": "2.0", "id": 1,
            "method": "getBalance", "params": [addr]}, timeout=15)
        sol = r.json()["result"]["value"] / 1e9
        usd = None
        try:
            p = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT",
                             timeout=10).json()
            usd = sol * float(p["price"])
        except Exception:
            pass
        return sol, usd, addr
    except Exception:
        return None, None, None

st.set_page_config(page_title="Agent Trading Journal", layout="wide")
st.title("Auditable Multi-Agent Trading - Live Journal")

# ---------- wallet panel ----------
sol, usd, addr = devnet_wallet()
w1, w2, w3 = st.columns([1, 1, 2])
if sol is not None:
    w1.metric("Devnet wallet balance", f"{sol:.4f} SOL")
    w2.metric("Approx value", f"${usd:.2f}" if usd else "n/a")
    w3.caption(f"address: {addr} | explorer: https://explorer.solana.com/address/{addr}?cluster=devnet")
else:
    w1.warning("Wallet not configured - add DEVNET_PRIVATE_KEY to .env")


def load(path):
    if not os.path.exists(path):
        return []
    try:
        return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    except Exception:
        return []

decisions = load("logs/decisions.jsonl")
hunter = load("logs/hunter_candidates.jsonl")
holdings = {}
if os.path.exists("logs/holdings.json"):
    try: holdings = json.load(open("logs/holdings.json"))
    except Exception: pass

# ---------- closed trades (from the self-audit records) ----------
closed = []
for d in decisions:
    dec = str(d.get("decision", ""))
    if dec.endswith("_CLOSED"):
        o = d.get("outcome", {})
        closed.append({
            "date": str(d.get("date", ""))[:10],
            "coin": d.get("coin", ""),
            "side": dec.replace("_CLOSED", ""),
            "entry": o.get("entry"), "exit": o.get("exit"),
            "pnl_pct": o.get("pnl_pct"),
            "result": "WIN" if (o.get("pnl_pct") or 0) > 0 else "LOSS",
            "tag": o.get("tag", ""),
            "held_days": o.get("held_days"),
        })
closed_df = pd.DataFrame(closed)

# ---------- headline stats ----------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total decisions", len(decisions))
c2.metric("Closed trades", len(closed))
if len(closed_df):
    wins = closed_df[closed_df["pnl_pct"] > 0]
    losses = closed_df[closed_df["pnl_pct"] <= 0]
    c3.metric("Win rate", f"{len(wins)/len(closed_df)*100:.0f}%")
    c4.metric("Total PnL", f"{closed_df['pnl_pct'].sum():+.2f}%")
    c5.metric("Best / Worst", f"{closed_df['pnl_pct'].max():+.1f}% / {closed_df['pnl_pct'].min():+.1f}%")
else:
    c3.metric("Win rate", "-"); c4.metric("Total PnL", "-"); c5.metric("Best / Worst", "-")

# ---------- last 30 days ----------
st.subheader("Last 30 days")
if len(closed_df):
    closed_df["dt"] = pd.to_datetime(closed_df["date"], errors="coerce")
    month = closed_df[closed_df["dt"] >= (pd.Timestamp.utcnow() - pd.Timedelta(days=30))]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Trades closed", len(month))
    if len(month):
        mw = month[month["pnl_pct"] > 0]
        m2.metric("Wins", f"{len(mw)} ({len(mw)/len(month)*100:.0f}%)")
        m3.metric("PnL (30d)", f"{month['pnl_pct'].sum():+.2f}%")
        m4.metric("Avg per trade", f"{month['pnl_pct'].mean():+.2f}%")
    else:
        m2.metric("Wins", "-"); m3.metric("PnL (30d)", "-"); m4.metric("Avg", "-")
else:
    st.info("No closed trades yet - the self-audit closes positions after 7 days, so trades from the first live week will appear here.")

# ---------- open positions with live unrealized PnL ----------
st.subheader("Open positions (live unrealized PnL)")
if holdings:
    try:
        from src.fetch_data import fetch_binance
        CFG = json.load(open("config/watchlist.json"))
        BIN = CFG.get("binance", {})
        rows = []
        for sym, pos in holdings.items():
            cur = None
            if sym in BIN:
                try:
                    df = fetch_binance(BIN[sym])
                    if df is not None and len(df):
                        cur = float(df.iloc[-1]["close"])
                except Exception:
                    pass
            entry = float(pos.get("entry", 0))
            if cur and entry:
                if pos.get("side") == "BUY":
                    upnl = (cur - entry) / entry * 100
                else:
                    upnl = (entry - cur) / entry * 100
            else:
                upnl = None
            rows.append({"coin": sym, "side": pos.get("side"), "entry": entry,
                         "current": cur, "unrealized_pnl_%": round(upnl, 2) if upnl is not None else None,
                         "opened": pos.get("date")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    except Exception as e:
        st.json(holdings)
else:
    st.info("No open positions.")

# ---------- full trade history ----------
st.subheader("All closed trades (full history)")
if len(closed_df):
    st.dataframe(closed_df.drop(columns=["dt"]), use_container_width=True)
    wins = closed_df[closed_df["pnl_pct"] > 0]["pnl_pct"].sum()
    losses = closed_df[closed_df["pnl_pct"] <= 0]["pnl_pct"].sum()
    st.write(f"**Total won:** {wins:+.2f}%    |    **Total lost:** {losses:+.2f}%")
else:
    st.info("Waiting for the first 7-day audit closes.")

# ---------- live decision feed ----------
st.subheader("Latest decisions")
rows = []
for d in decisions[-15:][::-1]:
    v = d.get("why", {}).get("verifier", {})
    rows.append({"date": str(d.get("date", ""))[:16], "coin": d.get("coin", ""),
                 "decision": d.get("decision", ""),
                 "verified": sum(1 for x in v.values() if x == "verified"),
                 "false": sum(1 for x in v.values() if x == "false"),
                 "mandate": str(d.get("why", {}).get("mandate", ""))[:30],
                 "tag": d.get("outcome", {}).get("tag", "")})
st.dataframe(rows, use_container_width=True)

# ---------- hunter ----------
st.subheader("Hunter: scanned vs rejected")
rejects = [h for h in hunter if any("gate" in g for g in h.get("gates", []))]
h1, h2 = st.columns(2)
h1.metric("Candidates scanned", len(hunter))
h2.metric("Rejected by gates", len(rejects))
st.dataframe([{"mint": h.get("mint", "")[:20], "gates": h.get("gates", [])} for h in rejects[-10:][::-1]],
             use_container_width=True)

if st.checkbox("Auto-refresh every 60s"):
    time.sleep(60)
    st.rerun()
