"""THE THREE AGENTS - v2: retries, error logging, verifier with real data."""
import os, sys, json
from dataclasses import dataclass, field
from src.llm_router import ROUTER
KEY = "configured"   # router handles keys

@dataclass
class Argument:
    direction: str
    confidence: float
    claims: list = field(default_factory=list)

@dataclass
class Verdict:
    claim: str
    status: str
    evidence: str = ""

def _ask(prompt: str, role: int = 0) -> str:
    try:
        return ROUTER.ask(prompt, prefer=role)
    except Exception as e:
        print(f"[agents] LLM call FAILED: {e}", file=sys.stderr)
        raise

def _parse_json(text: str) -> dict:
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    end = max(text.rfind("}"), text.rfind("]"))
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON in reply: " + text[:120])
    return json.loads(text[start:end+1])

def _data_block(df) -> str:
    """Rich, checkable data summary - the verifier can verify arithmetic."""
    last, prev = df.iloc[-1], df.iloc[-2]
    chg = (last["close"] - prev["close"]) / prev["close"] * 100
    ma20 = df["close"].tail(20).mean()
    hi30, lo30 = df["high"].max(), df["low"].min()
    closes = ", ".join(f"{c:.4f}" for c in df["close"].tail(8))
    return (f"DATA (all checkable):\n"
            f"- last 8 daily closes (oldest to newest): {closes}\n"
            f"- current close: {last['close']:.4f}\n"
            f"- previous close: {prev['close']:.4f}\n"
            f"- daily change: {chg:+.2f}%\n"
            f"- 20-day average close: {ma20:.4f}\n"
            f"- 30-day high: {hi30:.4f}, 30-day low: {lo30:.4f}")

SYS = """You are a crypto trading analyst. Reply with ONLY a JSON object:
{"direction": "buy"|"sell"|"hold", "confidence": 0.0-1.0,
 "claims": ["short factual claim 1", "short factual claim 2", "short factual claim 3"]}
Rules: every claim must be a CHECKABLE FACT about the data (a number, a comparison, a position in a range). No opinions, no predictions as claims.
No markdown, no explanation, JSON only."""

def bull_agent(df, lessons: list = None, use_llm: bool = True) -> Argument:
    if not use_llm or not KEY:
        return Argument("hold", 0.5, ["stub: no LLM key"])
    lessons_txt = "\n".join(f"- {l['lesson']}" for l in (lessons or [])[:5])
    p = f"{SYS}\n\nROLE: argue the STRONGEST possible BUY case.\n{_data_block(df)}\nPast lessons:\n{lessons_txt or 'none'}"
    try:
        d = _parse_json(_ask(p, role=0))
        return Argument(d["direction"], float(d["confidence"]), [str(c) for c in d["claims"][:5]])
    except Exception:
        return Argument("hold", 0.5, ["agent_error"])

def bear_agent(df, lessons: list = None, use_llm: bool = True) -> Argument:
    if not use_llm or not KEY:
        return Argument("hold", 0.5, ["stub: no LLM key"])
    lessons_txt = "\n".join(f"- {l['lesson']}" for l in (lessons or [])[:5])
    p = f"{SYS}\n\nROLE: argue the STRONGEST possible SELL/HOLD case (risks, overextension, reversal signals).\n{_data_block(df)}\nPast lessons:\n{lessons_txt or 'none'}"
    try:
        d = _parse_json(_ask(p, role=1))
        return Argument(d["direction"], float(d["confidence"]), [str(c) for c in d["claims"][:5]])
    except Exception:
        return Argument("hold", 0.5, ["agent_error"])

VSYS = """You are a strict fact-checker. Given DATA and CLAIMS, check EACH claim.
Rules:
- VERIFIED: the data clearly supports the claim (numbers match within small rounding)
- FALSE: the data contradicts the number/direction of the claim
- UNVERIFIABLE: the claim is about something NOT in the data (future, volume, external events)
Reply ONLY with a JSON array: [{"claim": "...", "status": "verified"|"false"|"unverifiable", "evidence": "one line"}]"""

def verifier_agent(bull: Argument, bear: Argument, df, use_llm: bool = True) -> list:
    claims = [c for c in bull.claims + bear.claims if c and c != "agent_error"]
    if not use_llm or not KEY or not claims:
        return [Verdict(c, "unverifiable") for c in claims]
    p = f"{VSYS}\n\n{_data_block(df)}\n\nCLAIMS: {json.dumps(claims)}"
    try:
        arr = _parse_json(_ask(p, role=2))
        out = []
        for x in arr:
            st = x["status"] if x["status"] in ("verified", "false", "unverifiable") else "unverifiable"
            out.append(Verdict(x["claim"], st, str(x.get("evidence", ""))[:120]))
        return out
    except Exception:
        return [Verdict(c, "unverifiable") for c in claims]

def decide(bull: Argument, bear: Argument, verdicts: list,
           threshold: float = 1.2, min_score: float = 0.5) -> str:
    """threshold: how much the winner must dominate (1.2 = 20% stronger).
    min_score: minimum confidence-weighted score to trade at all.
    Lower both = braver buying (use with --aggressive)."""
    vmap = {v.claim: v.status for v in verdicts}
    W = {"verified": 1.0, "false": -1.0, "unverifiable": 0.3}
    def score(a):
        if not a.claims or a.claims == ["agent_error"]:
            return 0.0
        return a.confidence * sum(W.get(vmap.get(c, "unverifiable"), 0.3) for c in a.claims)
    bs, rs = score(bull), score(bear)
    if bs > threshold * max(rs, 1e-9) and bs > min_score: return "BUY"
    if rs > threshold * max(bs, 1e-9) and rs > min_score: return "SELL"
    return "HOLD"
