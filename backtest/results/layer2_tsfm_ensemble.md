# 2025-26 UEFA Oracle Backtest — Layer 2 (Elo + TSFM Ensemble)

**Sample**: 83 knockout ties across seasons 2020/2021 → 2024/2025

## Headline

| Metric | Layer 2 | Layer 1 (Elo only) | Coin flip |
|--------|---------|--------------------|-----------|
| Hit rate | **63.9%** (53/83) | 63.9% | 50.0% |
| Brier score | **0.219** | 0.220 | 0.250 |
| Log loss | **0.620** | 0.622 | 0.693 |

One-sided binomial p-value (hit rate > 50%): **p = 0.0058**

## Hit rate by stage

| stage   |   n |   hit_rate |   brier |   log_loss |
|:--------|----:|-----------:|--------:|-----------:|
| R16     |  48 |      0.646 |   0.204 |      0.579 |
| QF      |  20 |      0.7   |   0.24  |      0.687 |
| SF      |  10 |      0.6   |   0.23  |      0.633 |
| Final   |   5 |      0.4   |   0.263 |      0.715 |

## Hit rate by season

| season    |   n |   hit_rate |   brier |   log_loss |
|:----------|----:|-----------:|--------:|-----------:|
| 2020/2021 |  15 |      0.533 |   0.266 |      0.716 |
| 2021/2022 |  15 |      0.6   |   0.239 |      0.669 |
| 2022/2023 |  15 |      0.733 |   0.176 |      0.524 |
| 2023/2024 |  15 |      0.733 |   0.192 |      0.553 |
| 2024/2025 |  23 |      0.609 |   0.222 |      0.63  |

## Confidence-bucketed hit rate

| confidence         |   n |   hit_rate |
|:-------------------|----:|-----------:|
| coin flip (50-55%) |   9 |      0.556 |
| mild (55-65%)      |  22 |      0.591 |
| moderate (65-75%)  |  18 |      0.389 |
| high (≥75%)        |  34 |      0.824 |

## Calibration (predicted P(home advances) vs actual)

| bin          |   n |   predicted_mean |   actual_hit_rate |
|:-------------|----:|-----------------:|------------------:|
| [0.00, 0.20) |  24 |            0.116 |             0.125 |
| [0.20, 0.40) |  17 |            0.323 |             0.471 |
| [0.40, 0.60) |  17 |            0.466 |             0.412 |
| [0.60, 0.80) |  18 |            0.674 |             0.333 |
| [0.80, 1.00) |   7 |            0.865 |             0.857 |

## Where Layer 2 differs from Layer 1

4 ties out of 83 had a different top pick.

| season    | stage   | home_team     | away_team        | actual        |   P(L1) |   P(L2) | L1 ✓   | L2 ✓   |
|:----------|:--------|:--------------|:-----------------|:--------------|--------:|--------:|:-------|:-------|
| 2022/2023 | R16     | Liverpool     | Real Madrid      | Real Madrid   |  0.5084 |  0.49   | False  | True   |
| 2022/2023 | R16     | Inter         | FC Porto         | Inter         |  0.5006 |  0.4924 | True   | False  |
| 2024/2025 | R16     | Bayern Munich | Bayer Leverkusen | Bayern Munich |  0.5042 |  0.499  | True   | False  |
| 2024/2025 | SF      | Barcelona     | Inter            | Inter         |  0.5278 |  0.4898 | False  | True   |