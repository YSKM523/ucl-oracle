# UCL Oracle

AI predictions for the 2025-26 UEFA Champions League winner, from the quarterfinal stage onwards.

Uses **TSFM + Club Elo + Bradley-Terry + Monte Carlo** architecture. Compares predictions against Polymarket odds to find edges.

Sister projects: [worldcup-oracle](../worldcup-oracle) | [fin-forecast-arena](../fin-forecast-arena)

## Predictions (April 9, 2026 — Pre-QF Second Legs)

### UCL Winner Probabilities

| Rank | Team | AI Win% | Polymarket | Edge | Signal |
|------|------|---------|------------|------|--------|
| 1 | **Arsenal** | **50.7%** | 29.5% | **+21.2%** | **STRONG BUY** |
| 2 | Bayern Munich | 26.8% | 29.5% | -2.7% | — |
| 3 | PSG | 12.6% | 20.5% | -7.9% | STRONG SELL |
| 4 | Barcelona | 3.0% | 6.2% | -3.2% | SELL |
| 5 | Atletico Madrid | 3.0% | 7.6% | -4.7% | SELL |
| 6 | Liverpool | 1.7% | 1.8% | -0.1% | — |
| 7 | Real Madrid | 1.6% | 5.0% | -3.4% | SELL |
| 8 | Sporting CP | 0.5% | 0.7% | -0.2% | — |

### QF Advancement Probabilities (Who Reaches Semis?)

| Team | AI Adv% | Polymarket | Edge | Signal |
|------|---------|------------|------|--------|
| Arsenal | 97.2% | 93.0% | +4.2% | BUY |
| **Bayern Munich** | **90.6%** | **83.0%** | **+7.6%** | **STRONG BUY** |
| PSG | 84.8% | 86.5% | -1.7% | — |
| **Atletico Madrid** | **81.3%** | **75.5%** | **+5.8%** | **STRONG BUY** |
| **Barcelona** | **18.7%** | **27.5%** | **-8.8%** | **STRONG SELL** |
| Liverpool | 15.2% | 14.0% | +1.2% | — |
| **Real Madrid** | **9.4%** | **16.5%** | **-7.1%** | **STRONG SELL** |
| Sporting CP | 2.8% | 7.0% | -4.2% | SELL |

### Per-Model Breakdown (P(Champion))

| Team | Chronos-2 | TimesFM-2.5 | FlowState | Elo Baseline | **Ensemble** |
|------|-----------|-------------|-----------|-------------|:------------|
| Arsenal | 50.6% | 50.7% | 51.1% | 50.6% | **50.7%** |
| Bayern Munich | 27.0% | 27.0% | 26.4% | 27.0% | **26.8%** |
| PSG | 12.6% | 12.6% | 12.8% | 12.6% | **12.6%** |
| Atletico Madrid | 3.0% | 3.0% | 2.8% | 3.0% | **3.0%** |
| Barcelona | 2.9% | 3.0% | 3.0% | 3.0% | **3.0%** |
| Liverpool | 1.8% | 1.7% | 1.8% | 1.7% | **1.7%** |
| Real Madrid | 1.6% | 1.6% | 1.7% | 1.6% | **1.6%** |
| Sporting CP | 0.5% | 0.5% | 0.5% | 0.5% | **0.5%** |

## Biggest Edges

| Team | Market | AI | Mkt | Edge | Kelly | Signal |
|------|--------|-----|------|------|-------|--------|
| Arsenal | Winner | 50.7% | 29.5% | +21.2% | 15.1% | **STRONG BUY** |
| PSG | Winner | 12.7% | 20.5% | -7.8% | — | **STRONG SELL** |
| Barcelona | QF Adv | 18.7% | 27.5% | -8.8% | — | **STRONG SELL** |
| Bayern Munich | QF Adv | 90.6% | 83.0% | +7.6% | 22.2% | **STRONG BUY** |
| Real Madrid | QF Adv | 9.4% | 16.5% | -7.1% | — | **STRONG SELL** |
| Atletico Madrid | QF Adv | 81.3% | 75.5% | +5.8% | 11.8% | **STRONG BUY** |

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

## Current State (April 8-9, 2026)

```
SILVER PATH                              BLUE PATH
QF1: PSG 2-0 Liverpool                   QF3: Barcelona 0-2 Atletico Madrid
QF2: Real Madrid 1-2 Bayern Munich       QF4: Sporting CP 0-1 Arsenal

SF1: QF1 winner vs QF2 winner            SF2: QF3 winner vs QF4 winner
     (Apr 28-29 / May 5-6)                    (Apr 28-29 / May 5-6)

                    FINAL: SF1 vs SF2 (May 30, Budapest)
```

PSG are the defending champions.

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
