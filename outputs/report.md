# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Unit Economics ($/1M-Token)

- **Baseline:** $6.488 / 1M-token  
- **Optimized:** $1.126 / 1M-token  
- **Inference Unit Savings:** 82.6%  

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query (us-east-1): 0.091 gCO2e
- Cleanest region: europe-north1 (30 gCO2/kWh, -92.1% carbon vs us-east-1)
- Cheapest power region: us-east-wa ($0.055/kWh vs $0.120/kWh in us-east-1)

_Figures are June-2026 as-of snapshots; re-baseline before acting._