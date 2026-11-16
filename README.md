# Auditable Multi-Agent Trading on Blockchain

**Verified reasoning, signal integrity and mandate enforcement for autonomous cryptocurrency trading on Solana.**

An autonomous AI trading system where every decision is *argued* by competing agents, *fact-checked* by a verifier, *enforced* by a hard rule engine, *executed* on-chain, and *recorded* for audit. The system learns from its own wins and losses via preference-based fine-tuning (DPO), and a live loop runs the whole pipeline continuously with a self-auditing journal.

**Status (Nov 2026): fully operational end-to-end on paper; real signed transactions on Solana devnet; trained model (DPO) available.**

---

## Table of Contents
1. [The Problem](#the-problem)
2. [Architecture Overview](#architecture-overview)
3. [How a Trade Happens](#how-a-trade-happens)
4. [The Four Eyes (detection)](#the-four-eyes)
5. [The Six Gates (scam screening)](#the-six-gates)
6. [The Agents](#the-agents)
7. [The Mandate Layer](#the-mandate-layer)
8. [The Auditor & Learning Loop](#the-auditor--learning-loop)
9. [Self-Training (DPO)](#self-training-dpo)
10. [Live Deployment](#live-deployment)
11. [Trading Journal Dashboard](#trading-journal-dashboard)
12. [Real Devnet Execution](#real-devnet-execution)
13. [Backtest Results](#backtest-results)
14. [Quick Start](#quick-start)
15. [Configuration](#configuration)
16. [Project Structure](#project-structure)
17. [Tech Stack](#tech-stack)
18. [Honest Limitations](#honest-limitations)
19. [Ethics & Safety](#ethics--safety)

---

## The Problem

Autonomous trading systems fail in four predictable ways:

| Failure | Typical cause | Layer that fixes it |
|---|---|---|
| Acting on manipulated data | wash trading, botnets, fake volume | 6 Gates + behaviour checks |
| Hallucinated reasoning | LLM states "facts" that are not true | Verifier Agent (per-claim fact-checking) |
| Ignoring user constraints | no hard limits on size/asset/loss | Mandate Layer (pure code) |
| No accountability | when it loses, nobody can say why | Auditor (decision + WHY + outcome) |

**Design rule: code decides what is ALLOWED. LLMs decide what is ARGUED. Data decides what is TRUE.**

## Architecture Overview

```
FOUR EYES (always watching, all free feeds)
  pump.fun births | DexScreener movers | Reddit/social | self-found smart wallets
        |
        v
FILTER  "is something special happening?"  (volume spike or big move?)
        |
        v
SIX GATES (deterministic, LLM never involved)
  1 RugCheck paperwork   2 insider wallet graph   3 second scanner opinion
  4 live honeypot probe  5 behaviour checks (bots, wash trading)
        |
        v
THE DEBATE  (3 LLM calls per analyzed day)
  Bull argues BUY  +  Bear argues SELL   ->  every claim must be a checkable fact
        |
        v
VERIFIER  checks every claim against the data -> verified / false / unverifiable
        |
        v
DECISION (weighted, code only: verified=+1, unverifiable=+0.3, false=-1)
        |
        v
MANDATE LAYER (pure Python rules: max size 5%, drawdown stop 15%, whitelist)
        |
        v
EXECUTION  (Jupiter on Solana - paper / devnet / mainnet-capped)
        |
        v
AUDITOR logs everything (decision + WHY + outcome)
        |
        v
SELF-AUDIT: positions close after 7 days -> PnL -> tagged -> lesson -> memory
        |
        v
DPO TRAINING: outcome-labelled debates -> preference pairs -> model improves
```

## How a Trade Happens

1. **Snapshot** - the last 30 days of OHLCV (never future data; no look-ahead bias anywhere).
2. **Filter** - boring days skipped; only volume spikes (>3x average) or big moves (+/-8%) trigger analysis.
3. **Debate** - Bull and Bear each get the same data block + past lessons, and must return structured JSON: direction, confidence, and up to five numbered **checkable claims** (opinions are banned - this is what makes verification possible).
4. **Verification** - the Verifier receives the full data block (last 8 closes, 20-day average, 30-day high/low, daily change) and every claim from both sides. Each claim is marked `verified`, `false`, or `unverifiable` with one-line evidence.
5. **Decision** - claims weighted (verified=+1.0, unverifiable=+0.3, false=-1.0) times agent confidence.
6. **Mandate check** - deterministic rules the LLM cannot override: position cap, drawdown stop, daily limit, whitelist.
7. **Execution** - approved trades via Jupiter (paper / devnet / capped mainnet per ethics approval).
8. **Recording** - the Auditor writes a JSON Decision Record: what was decided, *why* (all claims, verdicts, mandate result), and the outcome.
9. **Self-audit (live)** - after 7 real days, the position closes: PnL computed, outcome tagged (`good_reasoning`/`bad_timing`), a **lesson written to memory**, feeding future debates.

## The Four Eyes

| Eye | Source | What it catches |
|---|---|---|
| 1. Newborn | pump.fun websocket (pumpportal / Helius webhook) | coins at birth, hours before aggregators |
| 2. Crowd | DexScreener boosts / new pairs / movers | where the crowd's money is going |
| 3. Social | Reddit (PRAW, free) + pluggable Twitter adapter | mention acceleration; copy-paste shill detection (coordinated bot farms) |
| 4. Smart money | self-discovered wallets: bought early, sold near top, repeatedly (from on-chain history via Helius) | entries of proven wallets (signal, not proof - still gated) |

**Critical rule:** every coin from every eye goes through the same pipeline. No eye can skip ahead.

## The Six Gates

No coin reaches the agents unless it passes ALL gates. Gates are deterministic code + external scanners - never an LLM.

1. **RugCheck** - mint/freeze authority, LP lock, taxes, top holders, honeypot flags
2. **Insider graph** - bundled launches, hidden wallet clusters controlling supply
3. **Second opinion (GoPlus)** - if scanners disagree, the coin is dropped
4. **Live honeypot probe** - a real sell quote from Jupiter; if selling is impossible -> reject (needs no API key, always on)
5. **Behaviour checks** (own code) - self-trade %, trade-count vs unique-wallets ratio, trade-size uniformity (bots), buyer wallets < 7 days old, volume-price mismatch (wash trading)
6. **Verdict** - all five passed = tradeable

Principle: *RugCheck checks the coin's paperwork. Our Layer-5 checks watch the coin's behaviour. A coin needs both.*

## The Agents

Three LLM calls per analyzed day, via a multi-provider router (Groq / OpenRouter / Mistral / Gemini - any OpenAI-compatible API), with global rate limiting (configurable, default 27 req/min) and automatic failover + startup self-test.

- **Bull agent** - strongest possible BUY case; claims must be checkable facts about the data.
- **Bear agent** - strongest SELL/HOLD case; same format.
- **Verifier agent** - strict fact-checker; only marks `verified` when the data clearly supports the number.

Every prompt includes: a compact data block (all values locally computable, reproducible) and up to 5 past lessons from memory.

## The Mandate Layer

`src/mandate.py` - pure Python, unit-tested (`tests/test_mandate.py`). Rules (all configurable):

- max position size: 5% of portfolio (2% for Hunter candidates)
- max drawdown: 15% -> full stop
- max trades per day: 5
- allowed-token whitelist

The LLM can propose, but it can never override. A blocked trade is itself logged - refusals are auditable events.

## The Auditor & Learning Loop

Every decision is a JSON line in `logs/decisions.jsonl`:

```json
{"date": "...", "coin": "...", "decision": "BUY|SELL|HOLD|BLOCKED|BUY_CLOSED",
 "why": {"bull_claims": [...], "bear_claims": [...],
          "verifier": {claim: verdict}, "mandate": "..."},
 "outcome": {"pnl_pct": +22.0, "tag": "good_reasoning|bad_timing|market_move|...",
              "entry": ..., "exit": ..., "held_days": 7}}
```

Input (situation) + output (arguments) + label (win/lose) in one record = training data and audit trail simultaneously.

## Self-Training (DPO)

Not SFT on winners only (that ignores losses - contradicts "learns from mistakes"). **DPO - Direct Preference Optimization**:

For every traded day there is a natural preference pair: same situation, Bull's argument vs Bear's argument, known outcome.

```
backtest.py    -> logs/decisions.jsonl
build_pairs.py -> logs/dpo_pairs.jsonl   {prompt, chosen, rejected, margin}
train_model.py -> Unsloth 4-bit Qwen2.5-7B + TRL DPOTrainer (LoRA: 40M trainable params)
                  chosen = winning argument, rejected = losing argument
```

The model is pushed toward reasoning that made money and away from reasoning that lost - for identical market situations. All training data derives from logged, outcome-labelled decisions - the training process itself is auditable.

## Live Deployment

`python -m src.run_live --paper` (default, safe) runs the full pipeline every hour:

1. Watchlist: fetch last ~35 daily candles (Binance/Bybit, no key) -> filter -> Bull/Bear -> Verifier -> Mandate -> logged.
2. Hunter: DexScreener scan -> honeypot probe (Gate 4, always on) -> gate log.
3. **Self-audit**: positions held >= 7 days are closed automatically - PnL computed, tagged, lesson written to memory.

Observed live behaviour: consistent decisions (orca BUY repeatedly, jito flipping SELL->BUY as conditions changed), and the Hunter **rejected every hyped candidate it found via the honeypot gate** (5/5 pump.fun tokens with $0.7-1.9M volume refused).

## Trading Journal Dashboard

```bash
streamlit run app.py
```

Browser dashboard at http://localhost:8501 showing:

- **Devnet wallet balance** (live from the blockchain) + approx USD value
- Headline stats: decisions, closed trades, win rate, total PnL, best/worst trade
- **Last 30 days**: trades closed, wins, PnL, average per trade
- **Open positions** with live unrealized PnL
- **Full trade history**: every closed trade with entry/exit prices, PnL %, WIN/LOSS, and total won vs total lost
- Live decision feed (latest 15, with fact-check counts)
- Hunter panel: candidates scanned vs rejected by gates

## Real Devnet Execution

```bash
python gen_key.py            # generates a devnet wallet (key printed, put in .env)
# fund the PUBLIC key at https://faucet.solana.com
python -m src.run_live --live   # actually signs and sends transactions
```

BUY decisions execute a real swap (0.05 SOL) via Jupiter on Solana devnet. Every transaction lands on-chain and is viewable at `https://explorer.solana.com/tx/<hash>?cluster=devnet`. The tx signature is stored in the decision record (`why.tx_signature`).

**Safety:** devnet only (fake money). The devnet key must never be reused on mainnet. Sells are skipped in live mode (token account wiring is a documented TODO).

## Backtest Results (2024-2025, 20 Solana tokens)

- **1,803 decision records**, zero agent failures in the final run
- **10,844 claims checked by the Verifier: 7,315 verified, 2,252 false (19%), 1,277 unverifiable**
- 1,397 simulated trades: 75% win rate, mean +9.15% per trade
- The 19% false-claim rate demonstrates the hallucination-detection layer does real work

## Quick Start

```bash
# 1. environment
python3 -m venv venv && source venv/bin/activate      # Windows: venv\Scriptsctivate
pip install -r requirements.txt pytest

# 2. keys -> .env  (copy .env.example; CoinGecko + one LLM provider are enough)
cp .env.example .env

# 3. download 2024-2025 history (Binance/Bybit public APIs, no key needed)
python -m src.fetch_data

# 4. prove the mandate engine works
python -m pytest tests/        # expect: 4 passed

# 5. the "school" phase: walk 2024-2025, agents debate, records written
python -m src.backtest --llm   # Ctrl+C + re-run anytime = resumes (instant saves)

# 6. build training pairs + train (Google Colab / Kaggle, free T4/P100 GPU)
python -m src.build_pairs

# 7. live loop (paper) + dashboard + devnet execution
python -m src.run_live --paper
streamlit run app.py
python gen_key.py && python -m src.run_live --live
```

## Configuration

- `config/watchlist.json` - coins (CoinGecko ids + Binance/Bybit symbols), mint addresses for execution, portfolio rules
- `.env` - API keys. Supports 1-4 LLM providers (`LLM_1_*` ... `LLM_4_*`); Bull->slot1, Bear->slot2, Verifier->slot3; failover wraps around. `LLM_MAX_RPM` (default 27) caps request rate.
- `LOOP_MINUTES` - live loop interval (default 60)

## Project Structure

```
config/      watchlist + portfolio rules
src/
  fetch_data.py     historical OHLCV (Binance -> Bybit -> CoinGecko fallback)
  load_data.py      get_data(coin) + snapshot() with look-ahead protection
  filter.py         "is something special happening?"
  hunter.py         DexScreener candidate scan (Eye 2)
  signal_health.py  behavioural scam checks (Layer 1)
  agents.py         Bull / Bear / Verifier (structured JSON debate + verification)
  llm_router.py     multi-provider routing, rate limiting, failover, self-test
  mandate.py        deterministic rule engine (the bouncer)
  memory.py         lessons memory + retrieval
  auditor.py        JSONL audit trail + post-mortem tagging
  backtest.py       chronological school phase, resume-safe, instant saves
  build_pairs.py    decision records -> DPO pairs
  train_model.py    DPO fine-tuning (Colab/Kaggle)
  jupiter.py        quotes, swap, honeypot probe
  execution_devnet.py  real signed devnet transactions (solders)
  run_live.py       live loop: watchlist + hunter + self-audit (+ --live execution)
gen_key.py       devnet wallet generator
app.py           Streamlit trading journal dashboard
tests/           mandate engine unit tests
logs/            decisions.jsonl, audit.jsonl, holdings.json, hunter_candidates.jsonl
```

## Tech Stack

Python - pandas - Groq/OpenRouter/Mistral/Gemini (OpenAI-compatible) - Unsloth + TRL (DPO) - Binance/Bybit public klines - DexScreener API - Helius (Solana) - Jupiter swap API - solders (Solana signing) - Streamlit (dashboard) - CoinGecko (fallback).

## Honest Limitations

1. **Simulated outcomes** - the backtest exits at the 7-day best price for buys. Real fills are worse; headline returns are optimistic.
2. **Small training set** - a few hundred decisive trades teach bias and format more than deep strategy.
3. **Single market regime** - 2024-2025 was predominantly bullish; learned reasoning may not transfer to bear markets.
4. **Detection vs prediction** - the system detects acceleration (hours-to-days before peaks); it does not predict virality.
5. **Scanners are snapshots** - a token can pass all gates and still be rugged later; behavioural tripwires mitigate but do not eliminate this.
6. **Decision stability** - the hourly loop re-debates identical daily candles between closes (sampling variance at temperature 0.2); flagged as future work (dedupe per candle).
7. **Live sells not wired** - live mode buys only; selling requires token-account handling (TODO).

## Ethics & Safety

- Ethics approval: CEBE Ethics Committee for Taught Courses (ECTC), University of Ulster, Oct 2026.
- Mandate Layer is deterministic code, never an LLM - the auditable enforcement point.
- Human-in-the-loop for rule changes (the Auditor *recommends*, a human approves; the decision is logged).
- Live funds: capped personal funds only, devnet-first methodology, private keys never leave the deployment machine and never enter version control.
- All lessons applied chronologically; no look-ahead bias anywhere in the pipeline.

---

*Final-year Computing Science project. The goal is not a money printer - it is a trading system you can audit.*
