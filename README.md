# UCL Oracle

AI predictions for the 2025-26 UEFA Champions League winner, from the quarterfinal stage onwards.

Uses **TSFM + Club Elo + Poisson Scoreline + Monte Carlo** architecture. Compares predictions against Polymarket odds to find edges.

**Author:** [YSKM](https://github.com/YSKM523) | **License:** MIT | **Language:** Python

Sister projects: [worldcup-oracle](../worldcup-oracle) | [fin-forecast-arena](../fin-forecast-arena)

## Predictions (April 12, 2026 — 2 Days Before QF Second Legs)

### UCL Winner Probabilities

| Rank | Team | AI Win% | Polymarket | Edge | Signal |
|------|------|---------|------------|------|--------|
| 1 | **Arsenal** | **55.6%** | 26.5% | **+29.1%** | **STRONG BUY** |
| 2 | Bayern Munich | 26.0% | 30.5% | -4.5% | SELL |
| 3 | PSG | 10.3% | 20.5% | -10.2% | **STRONG SELL** |
| 4 | Barcelona | 2.6% | 7.3% | -4.8% | SELL |
| 5 | Atletico Madrid | 2.5% | 7.4% | -4.9% | SELL |
| 6 | Real Madrid | 1.4% | 4.7% | -3.3% | SELL |
| 7 | Liverpool | 1.3% | 1.8% | -0.6% | — |
| 8 | Sporting CP | 0.3% | 0.6% | -0.3% | — |

### QF Advancement Probabilities (Who Reaches Semis?)

| Team | AI Adv% | Polymarket | Edge | Signal |
|------|---------|------------|------|--------|
| Arsenal | **97.2%** | 91.5% | **+5.7%** | **STRONG BUY** |
| **Bayern Munich** | **90.6%** | **83.5%** | **+7.1%** | **STRONG BUY** |
| PSG | 85.0% | 87.0% | -2.0% | — |
| **Atletico Madrid** | **82.5%** | **73.5%** | **+9.0%** | **STRONG BUY** |
| **Barcelona** | **17.5%** | **27.0%** | **-9.5%** | **STRONG SELL** |
| Liverpool | 15.0% | 13.0% | +2.0% | — |
| **Real Madrid** | **9.4%** | **17.0%** | **-7.6%** | **STRONG SELL** |
| Sporting CP | 2.8% | 8.5% | -5.7% | **STRONG SELL** |

### Per-Model Breakdown (P(Champion))

| Team | Chronos-2 | TimesFM-2.5 | FlowState | Elo Baseline | **Ensemble** |
|------|-----------|-------------|-----------|-------------|:------------|
| Arsenal | 55.6% | 55.7% | 56.2% | 54.9% | **55.6%** |
| Bayern Munich | 25.9% | 26.0% | 25.2% | 27.0% | **26.0%** |
| PSG | 10.2% | 10.1% | 10.3% | 10.6% | **10.3%** |
| Barcelona | 2.8% | 2.8% | 2.9% | 1.7% | **2.6%** |
| Atletico Madrid | 2.4% | 2.4% | 2.4% | 3.1% | **2.5%** |
| Real Madrid | 1.4% | 1.4% | 1.4% | 1.3% | **1.4%** |
| Liverpool | 1.4% | 1.3% | 1.3% | 1.0% | **1.3%** |
| Sporting CP | 0.3% | 0.4% | 0.4% | 0.3% | **0.3%** |

## Biggest Edges

| Team | Market | AI | Mkt | Edge | Kelly | Signal |
|------|--------|-----|------|------|-------|--------|
| Arsenal | Winner | 55.6% | 26.5% | +29.1% | 19.8% | **STRONG BUY** |
| PSG | Winner | 10.3% | 20.5% | -10.2% | — | **STRONG SELL** |
| Barcelona | QF Adv | 17.5% | 27.0% | -9.5% | — | **STRONG SELL** |
| Atletico Madrid | QF Adv | 82.5% | 73.5% | +9.0% | 17.1% | **STRONG BUY** |
| Real Madrid | QF Adv | 9.4% | 17.0% | -7.6% | — | **STRONG SELL** |
| Bayern Munich | QF Adv | 90.6% | 83.5% | +7.1% | 21.5% | **STRONG BUY** |
| Sporting CP | QF Adv | 2.8% | 8.5% | -5.7% | — | **STRONG SELL** |

### What Changed Since April 9

- **Arsenal winner edge widened** from +21.2% to **+29.1%** — market drifted down (29.5% → 26.5%) while model climbed (50.7% → 55.6%).
- **PSG flipped from mild to STRONG SELL** on the winner market (-7.9% → -10.2%) as market held 20.5% but model dropped to 10.3%.
- **Atletico QF edge strengthened** (+5.8% → +9.0%) — model now 82.5% vs market 73.5%.
- **Sporting CP QF became STRONG SELL** — market at 8.5% vs model 2.8% (7-point overpricing of upset).
- **Bayern winner signal flipped to SELL** as market now prices them above Arsenal (30.5% > 26.5%).

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

### Data Sources

- **Club Elo**: [clubelo.com](http://clubelo.com) — free historical club Elo ratings
- **Market odds**: [Polymarket](https://polymarket.com) Gamma API (public, no auth)
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
