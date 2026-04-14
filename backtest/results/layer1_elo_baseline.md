# 2025-26 UEFA Oracle Backtest — Layer 1 (Elo baseline)

**Sample**: 83 knockout ties across seasons 2020/2021 → 2024/2025

## Headline

| Metric | Model | Coin-flip baseline |
|--------|-------|--------------------|
| Hit rate | **63.9%** (53/83) | 50.0% |
| Brier score | **0.220** | 0.250 |
| Log loss   | **0.622** | 0.693 |

One-sided binomial p-value (hit rate > 50%): **p = 0.0058**

## Hit rate by stage

| stage   |   n |   hit_rate |   brier |   log_loss |
|:--------|----:|-----------:|--------:|-----------:|
| R16     |  48 |      0.667 |   0.201 |      0.572 |
| QF      |  20 |      0.7   |   0.248 |      0.709 |
| SF      |  10 |      0.5   |   0.234 |      0.639 |
| Final   |   5 |      0.4   |   0.264 |      0.716 |

## Hit rate by season

| season    |   n |   hit_rate |   brier |   log_loss |
|:----------|----:|-----------:|--------:|-----------:|
| 2020/2021 |  15 |      0.533 |   0.265 |      0.717 |
| 2021/2022 |  15 |      0.6   |   0.241 |      0.676 |
| 2022/2023 |  15 |      0.733 |   0.171 |      0.509 |
| 2023/2024 |  15 |      0.733 |   0.193 |      0.554 |
| 2024/2025 |  23 |      0.609 |   0.228 |      0.642 |

## Confidence-bucketed hit rate

*Does the model get it right more often when it's confident?*

| confidence         |   n |   hit_rate |
|:-------------------|----:|-----------:|
| coin flip (50-55%) |  10 |      0.5   |
| mild (55-65%)      |  20 |      0.65  |
| moderate (65-75%)  |  20 |      0.35  |
| high (≥75%)        |  33 |      0.848 |

## Calibration (predicted P(home advances) vs actual)

*A well-calibrated model's predicted bucket and actual rate should match.*

| bin          |   n |   predicted_mean |   actual_hit_rate |
|:-------------|----:|-----------------:|------------------:|
| [0.00, 0.20) |  24 |            0.112 |             0.125 |
| [0.20, 0.40) |  15 |            0.322 |             0.467 |
| [0.40, 0.60) |  19 |            0.465 |             0.421 |
| [0.60, 0.80) |  18 |            0.672 |             0.333 |
| [0.80, 1.00) |   7 |            0.869 |             0.857 |

## Interpretation

- **Hit rate > 60%** → Elo has real signal (50% is coin flip; top-pick home advantage isn't a free 60%)
- **Brier < 0.22** → substantially better calibrated than coin flip
- **p < 0.05** → statistically unlikely to be chance
- **Confidence buckets**: if 'high confidence (≥75%)' isn't >80% hit rate, model is overconfident