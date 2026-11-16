"""Health check: run  python test_providers.py
Shows which providers are alive before you start the backtest."""
from src.llm_router import ROUTER

print("Configured providers:")
ROUTER.self_test(verbose=True)
if not ROUTER.providers:
    print("\n!!! NOTHING WORKS - check .env keys and model IDs (run list_models.py) !!!")
else:
    print(f"\n{len(ROUTER.providers)} provider(s) will be used by the backtest.")
