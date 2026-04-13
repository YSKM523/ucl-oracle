# UCL Oracle

AI predictions for the 2025-26 UEFA Champions League winner, from the quarterfinal stage onwards.

Uses **TSFM + Club Elo + xG-adjusted first-leg Elo + Poisson Scoreline + Monte Carlo** architecture. Compares predictions against Polymarket odds to find edges.

**Author:** [YSKM](https://github.com/YSKM523) | **License:** MIT | **Language:** Python

Sister projects: [worldcup-oracle](../worldcup-oracle) | [fin-forecast-arena](../fin-forecast-arena)

## Predictions (April 12, 2026 — xG-Adjusted, 2 Days Before Second Legs)

Model now applies a **first-leg xG performance adjustment** to team Elo before SF/Final simulation (see *First-Leg Elo Adjustment* section below). QF aggregates still use actual goals.

### UCL Winner Probabilities

| Rank | Team | AI Win% | Polymarket | Edge | Signal |
|------|------|---------|------------|------|--------|
| 1 | **Arsenal** | **53.8%** | 25.5% | **+28.3%** | **STRONG BUY** |
| 2 | Bayern Munich | 27.0% | 32.5% | -5.5% | **STRONG SELL** |
| 3 | PSG | 11.3% | 20.5% | -9.2% | **STRONG SELL** |
| 4 | Atletico Madrid | 3.8% | 7.2% | -3.4% | SELL |
| 5 | Barcelona | 1.3% | 6.9% | -5.5% | **STRONG SELL** |
| 6 | Real Madrid | 1.2% | 5.1% | -3.9% | SELL |
| 7 | Liverpool | 1.2% | 1.9% | -0.8% | — |
| 8 | Sporting CP | 0.4% | 0.7% | -0.3% | — |

### QF Advancement Probabilities (Who Reaches Semis?)

| Team | AI Adv% | Polymarket | Edge | Signal |
|------|---------|------------|------|--------|
| Arsenal | **96.9%** | 90.5% | **+6.4%** | **STRONG BUY** |
| **Bayern Munich** | **91.3%** | **84.5%** | **+6.8%** | **STRONG BUY** |
| **Atletico Madrid** | **88.1%** | **73.0%** | **+15.1%** | **STRONG BUY** |
| PSG | 86.2% | 87.5% | -1.3% | — |
| Liverpool | 13.8% | 12.5% | +1.3% | — |
| **Barcelona** | **11.9%** | **28.0%** | **-16.1%** | **STRONG SELL** |
| **Real Madrid** | **8.7%** | **16.0%** | **-7.3%** | **STRONG SELL** |
| **Sporting CP** | **3.1%** | **10.5%** | **-7.4%** | **STRONG SELL** |

### Per-Model Breakdown (P(Champion))

| Team | Chronos-2 | TimesFM-2.5 | FlowState | Elo Baseline | **Ensemble** |
|------|-----------|-------------|-----------|-------------|:------------|
| Arsenal | 53.9% | 54.1% | 54.4% | 52.7% | **53.8%** |
| Bayern Munich | 26.9% | 26.9% | 26.3% | 27.9% | **27.0%** |
| PSG | 11.2% | 11.1% | 11.3% | 11.6% | **11.3%** |
| Atletico Madrid | 3.6% | 3.6% | 3.6% | 4.4% | **3.8%** |
| Barcelona | 1.5% | 1.4% | 1.5% | 0.9% | **1.3%** |
| Real Madrid | 1.3% | 1.3% | 1.3% | 1.1% | **1.2%** |
| Liverpool | 1.3% | 1.2% | 1.2% | 1.0% | **1.2%** |
| Sporting CP | 0.4% | 0.4% | 0.4% | 0.3% | **0.4%** |

## Biggest Edges

| Team | Market | AI | Mkt | Edge | Kelly | Signal |
|------|--------|-----|------|------|-------|--------|
| Arsenal | Winner | 53.8% | 25.5% | +28.3% | 19.0% | **STRONG BUY** |
| Atletico Madrid | QF Adv | 88.1% | 73.0% | +15.1% | 27.9% | **STRONG BUY** |
| Barcelona | QF Adv | 11.9% | 28.0% | -16.1% | — | **STRONG SELL** |
| PSG | Winner | 11.3% | 20.5% | -9.2% | — | **STRONG SELL** |
| Sporting CP | QF Adv | 3.1% | 10.5% | -7.4% | — | **STRONG SELL** |
| Real Madrid | QF Adv | 8.7% | 16.0% | -7.3% | — | **STRONG SELL** |
| Bayern Munich | QF Adv | 91.3% | 84.5% | +6.8% | 21.8% | **STRONG BUY** |
| Arsenal | QF Adv | 96.9% | 90.5% | +6.4% | 33.8% | **STRONG BUY** |

## First-Leg Elo Adjustment (xG-weighted)

The April 12 update applies a performance-based Elo bump after each first leg:

| Leg | Match | Expected GD (Elo) | Effective GD (xG-blend) | Residual | ΔElo |
|-----|-------|-------------------|-------------------------|----------|------|
| QF1 | PSG 2-0 Liverpool | +0.78 | +1.28 | +0.50 | **+5.03** to PSG |
| QF2 | Real 1-2 Bayern | -0.09 | -0.34 | -0.25 | **+2.54** to Bayern |
| QF3 | Barça 0-2 Atleti | +1.15 | -1.28 | -2.43 (capped) | **+24.29** to Atleti |
| QF4 | Sporting 0-1 Arsenal | -0.99 | -0.70 | +0.29 | **+2.92** to Sporting |

**Effect on predictions** (vs non-adjusted April 12 run):
- **PSG winner**: 10.3% → 11.3% (+1.0pp) — modest xG advantage vs Liverpool shows through
- **Atletico winner**: 2.5% → 3.8% (+1.3pp) — model catches their road-domination signal
- **Atletico QF advance**: 82.5% → 88.1% (+5.6pp)
- **Barcelona QF advance**: 17.5% → 11.9% (-5.6pp) — worst xG performance in the QFs
- **Arsenal winner**: 55.6% → 53.8% (-1.8pp) — slight penalty for 1-0 win they were expected to dominate

The adjustment answers the earlier question *"why is PSG so bearish?"* — PSG bumps +1pp from xG, but the bracket (Bayern in SF, Arsenal in Final) still dominates the projection. **The bearish signal on PSG is bracket-driven, not model myopia.**

## Visualizations

### Bracket

![UCL Bracket](results/plots/ucl_bracket.png)

### Champion Probabilities

![Champion Probabilities](results/plots/champion_probabilities.png)

### AI vs Polymarket

![AI vs Polymarket Scatter](results/plots/ai_vs_polymarket_scatter.png)
![AI vs Polymarket Bars](results/plots/ai_vs_polymarket_bars.png)

### Elo Trajectories

![Elo Trajectories](results/plots/elo_trajectories.png)

## Methodology

```
clubelo.com (5yr weekly Elo for 8 teams)
        │
        ├── Chronos-2 (Amazon, 120M params)    ─┐
        ├── TimesFM 2.5 (Google, 200M params)   ├── Elo forecast (8 weeks)
        └── FlowState (IBM, 9.1M params)       ─┘
                    │
                    ▼
            Equal-weight ensemble
                    │
                    ▼
       First-leg Elo adjustment (NEW)
    xG-blended residual vs Elo expectation
     → ΔElo feeds SF/Final simulations
                    │
                    ▼
         Elo → Poisson goal model
        (team-specific attack/defense)
                    │
                    ▼
          Two-legged tie simulation
    (aggregate scoring, ET, penalties)
                    │
                    ▼
        50,000 Monte Carlo bracket sims
        QF (2nd legs) → SF → Final
                    │
                    ▼
       P(advance) and P(champion) per team
                    │
                    ▼
         Polymarket edge detection
         + Half-Kelly bet sizing
```

### Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Avg goals/match | 2.7 | UCL knockout historical average |
| Home advantage | 65 Elo | Club football standard |
| ET goal fraction | 0.33 | 30min/90min |
| Penalty advantage | 0.55 | Slight edge for higher-rated team |
| Away goals rule | **None** | Abolished in UCL from 2021-22 |
| Monte Carlo sims | 50,000 | Sufficient for 8-team bracket |
| TSFM context | 260 weeks | ~5 years of weekly Elo |
| TSFM horizon | 8 weeks | Through final (May 30) |
| xG blend α | 0.6 | Weights xG above actual goals (xG more predictive) |
| First-leg K | 10 | ΔElo per 1-goal residual (~1 week of form shift) |
| Residual cap | ±2.5 | Prevents blowouts from dominating adjustment |

### Data Sources

- **Club Elo**: [clubelo.com](http://clubelo.com) — free historical club Elo ratings
- **Market odds**: [Polymarket](https://polymarket.com) Gamma API (public, no auth)
- **xG (match-level)**: [FotMob](https://www.fotmob.com) public league API (best-effort; falls back to `config.FIRST_LEG_XG` placeholders when rate-limited). Override these manually from FBref / Opta match reports for maximum signal.
- **Models**: HuggingFace (Chronos-2, TimesFM-2.5, FlowState)

## Current State (April 12, 2026 — Pre-Second-Leg)

First legs completed April 8-9. **Second legs are April 14-15, 2026** (2 days away).

```
SILVER PATH                              BLUE PATH
QF1: PSG 2-0 Liverpool        (1st leg)  QF3: Barcelona 0-2 Atletico Madrid  (1st leg)
QF2: Real Madrid 1-2 Bayern   (1st leg)  QF4: Sporting CP 0-1 Arsenal        (1st leg)

QF1 2nd leg: Liverpool vs PSG (Apr 15)   QF3 2nd leg: Atletico vs Barça (Apr 14)
QF2 2nd leg: Bayern vs Real   (Apr 15)   QF4 2nd leg: Arsenal vs Sporting (Apr 14)

SF1: QF1 winner vs QF2 winner            SF2: QF3 winner vs QF4 winner
     (Apr 28-29 / May 5-6)                    (Apr 28-29 / May 5-6)

                    FINAL: SF1 vs SF2 (May 30, Budapest)
```

PSG are the defending champions and lead 2-0 heading into the second leg. Three of
four first-leg losers (Liverpool, Real Madrid, Barcelona, Sporting) face uphill
aggregate deficits heading into the return legs — which is why the model concentrates
probability mass on Arsenal, Bayern, PSG, and Atletico.

## Usage

```bash
# Full pipeline (Elo + TSFM + Polymarket)
python run_predictions.py

# Elo baseline only (fast, no TSFM models)
python run_predictions.py --elo-only

# Generate all visualizations
python generate_plots.py
```

## Setup

Uses the same venv as worldcup-oracle and fin-forecast-arena:

```bash
ln -sf /home/ubuntu/fin-forecast-arena/venv venv
source venv/bin/activate
python run_predictions.py
```

## License

MIT License. See [LICENSE](LICENSE) for details.
