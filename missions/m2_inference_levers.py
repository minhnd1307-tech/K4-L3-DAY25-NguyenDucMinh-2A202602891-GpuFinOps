"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0

    # Extension 3: Cache Economics (Break-even & Worth-it Analysis)
    # Estimate average reads per cached prefix by project (chat & rag share static system prompts)
    project_counts = {}
    for r in rows:
        proj = r["project"] or "untagged"
        project_counts[proj] = project_counts.get(proj, 0) + 1

    # Break-even threshold: reads * (price_in * 0.90) >= write_cost
    # Standard write (1.0x price_in): 1 / 0.90 ~= 1.11 reads
    # Premium write (1.25x price_in like Anthropic): 1.25 / 0.90 ~= 1.39 reads
    be_small = pricing.cache_break_even_reads(MODEL_PRICES["small"][0], read_discount=0.10)
    be_large = pricing.cache_break_even_reads(MODEL_PRICES["large"][0], read_discount=0.10)
    be_small_prem = pricing.cache_break_even_reads(MODEL_PRICES["small"][0] * 1.25, read_discount=0.10, base_read_cost_per_m=MODEL_PRICES["small"][0])
    be_large_prem = pricing.cache_break_even_reads(MODEL_PRICES["large"][0] * 1.25, read_discount=0.10, base_read_cost_per_m=MODEL_PRICES["large"][0])

    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        total_tokens += inp + out

        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)

        # OPTIMIZED: cascade (route_tier), prompt caching (gated by cache_is_worth_it), batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]

        # Extension 3 Gate: Only apply caching if reuse frequency exceeds break-even
        proj = r["project"] or "untagged"
        # Shared system prompt reuse estimated over 24h (min 15-30 reads/prefix for chat/doc-qa)
        est_reads = max(1.0, project_counts.get(proj, 10) / 24.0)
        cache_approved = pricing.cache_is_worth_it(
            avg_cache_reads=est_reads,
            write_cost_per_m=pin,
            read_discount=0.10,
            base_read_cost_per_m=pin,
        )
        effective_cached = cached if cache_approved else 0

        opt_cost += pricing.request_cost(inp, out, pin, pout, cached_in=effective_cached, batch=is_batch)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")

        # Extension 3 details output
        print("\n-- Extension 3: Cache Economics Analysis (cache_is_worth_it) --")
        print(f"{'Tier':8}{'Input $/1M':>12}{'Break-Even (1.0x)':>18}{'Break-Even (1.25x)':>18}")
        print(f"{'small':8}{MODEL_PRICES['small'][0]:>12.2f}{be_small:>18.2f}{be_small_prem:>18.2f}")
        print(f"{'large':8}{MODEL_PRICES['large'][0]:>12.2f}{be_large:>18.2f}{be_large_prem:>18.2f}")
        print("\nModeling Hypothesis & Sensitivity Analysis:")
        print(f"  - Simulation note: token_usage.csv does not log individual prefix IDs or cache TTL.")
        print(f"    We model prefix reuse assuming shared static system prompts per project over hourly windows.")
        print(f"  - Model traffic: chat ~{project_counts.get('chat',0)/24:.1f} req/hr, doc-qa ~{project_counts.get('doc-qa',0)/24:.1f} req/hr.")
        print(f"  - Mathematical break-even: requires >= {be_small:.2f} reads (1.0x write) or >= {be_small_prem:.2f} reads (1.25x write premium).")
        print(f"  - Sensitivity conclusion: Any prefix reused >= 2 times is guaranteed to be cost-effective.")
        print(f"    Threshold test (15.0 reads >= {be_small:.2f}): {pricing.cache_is_worth_it(15.0, MODEL_PRICES['small'][0], 0.10)}")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
    }


if __name__ == "__main__":
    run()
