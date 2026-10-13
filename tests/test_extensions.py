import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finops import pricing
from missions import m1_efficiency_audit, m2_inference_levers


def test_cache_break_even_reads():
    # Base case: 1.0x write price, 90% discount -> 1 / 0.90 = 1.111...
    be_standard = pricing.cache_break_even_reads(write_cost_per_m=3.0, read_discount=0.10)
    assert abs(be_standard - (1.0 / 0.90)) < 1e-4

    # Premium case (Anthropic 1.25x write): 1.25 / 0.90 = 1.3888...
    be_premium = pricing.cache_break_even_reads(
        write_cost_per_m=3.75, read_discount=0.10, base_read_cost_per_m=3.0
    )
    assert abs(be_premium - (1.25 / 0.90)) < 1e-4

    # Zero savings case
    assert pricing.cache_break_even_reads(3.0, read_discount=1.0) == float("inf")


def test_cache_is_worth_it():
    # With 1.0 read (below 1.11 threshold), caching loses money
    assert pricing.cache_is_worth_it(avg_reads=1.0, write_cost=3.0, read_discount=0.10) is False

    # With 2.0 reads (above 1.11 threshold), caching is profitable
    assert pricing.cache_is_worth_it(avg_reads=2.0, write_cost=3.0, read_discount=0.10) is True

    # High reuse (chat/rag workload with ~20 reads)
    assert pricing.cache_is_worth_it(avg_cache_reads=20.0, write_cost_per_m=0.20, read_discount=0.10) is True

    # Positional args compatibility
    assert pricing.cache_is_worth_it(5.0, 3.0, 0.10) is True
    assert pricing.cache_is_worth_it(0.5, 3.0, 0.10) is False


def test_extension2_mbu_rightsizing():
    res = m1_efficiency_audit.run(verbose=False)
    assert "rightsizing" in res
    assert "vram_economics" in res
    assert len(res["rightsizing"]) >= 3
    assert res["rightsize_monthly_savings"] > 0

    # Ensure H100 with low MBU/MFU is recommended to right-size to A100
    h100_rec = next((r for r in res["rightsizing"] if r["gpu_id"] == "gpu-h100-4"), None)
    assert h100_rec is not None
    assert h100_rec["proposed_type"] == "A100"
    assert h100_rec["monthly_savings"] > 500.0


def test_extension3_m2_integration():
    res = m2_inference_levers.run(verbose=False)
    assert 60 <= res["savings_pct"] <= 95
    assert res["optimized_daily"] < res["baseline_daily"]


def test_bandwidth_constraint_rejects_insufficient_bw():
    # If a workload on A10G requires 0.59 TB/s BW, L4 (0.30 TB/s) must be rejected
    from missions._common import catalog_by_type, num
    cat = catalog_by_type()
    cur_price = num(cat["A10G"]["on_demand_hr"])  # $1.00
    req_bw = 0.59 * 1.15  # 0.6785 TB/s

    cheaper_with_enough_bw = [
        g for g, s in cat.items()
        if num(s["on_demand_hr"]) < cur_price and num(s["peak_bw_tbs"]) >= req_bw
    ]
    # Verify that L4 is rejected because its 0.30 TB/s cannot satisfy 0.59 TB/s
    assert "L4" not in cheaper_with_enough_bw
    assert len(cheaper_with_enough_bw) == 0

