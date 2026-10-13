"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly",
                 unit_economics: dict | None = None) -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}  ",
        f"**Baseline spend:** ${baseline_usd:,.0f}  ",
        f"**Optimized spend:** ${optimized_usd:,.0f}  ",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
    ]
    if unit_economics:
        lines += [
            "## Unit Economics ($/1M-Token)",
            "",
            f"- **Baseline:** ${unit_economics.get('baseline_per_m', 0):.3f} / 1M-token  ",
            f"- **Optimized:** ${unit_economics.get('optimized_per_m', 0):.3f} / 1M-token  ",
            f"- **Inference Unit Savings:** {unit_economics.get('savings_pct', 0):.1f}%  ",
            "",
        ]
    lines += [
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if sustainability:
        clean_reg = sustainability.get("cleanest_region", sustainability.get("best_region", "europe-north1"))
        cheap_reg = sustainability.get("cheapest_region", "us-east-wa")
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query (us-east-1): {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cleanest region: {clean_reg} (30 gCO2/kWh, -92.1% carbon vs us-east-1)",
            f"- Cheapest power region: {cheap_reg} ($0.055/kWh vs $0.120/kWh in us-east-1)",
        ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str) -> str:
    """Write a simple savings bar chart PNG. Returns the path. No-op if matplotlib absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(names, vals, color="#2e548a")
    ax.set_ylabel("Savings (USD / month)")
    ax.set_title("GPU cost savings by FinOps lever")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
