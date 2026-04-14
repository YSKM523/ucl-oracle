# UCL Oracle

AI predictions for the 2025-26 UEFA Champions League winner, from the quarterfinal stage onwards.

Uses **TSFM + Club Elo + xG first-leg adjustment + injury-weighted Elo + Poisson Scoreline + Monte Carlo** architecture. Compares predictions against Polymarket odds to find edges.

**Author:** [YSKM](https://github.com/YSKM523) | **License:** MIT | **Language:** Python

Sister projects: [worldcup-oracle](../worldcup-oracle) | [fin-forecast-arena](../fin-forecast-arena)

## Predictions (April 14, 2026 — QF Second-Leg Match Day)

Final pre-match predictions before the QF second legs (QF3 & QF4 tonight; QF1 & QF2 tomorrow). Model applies two Elo adjustments before Monte Carlo: (1) first-leg xG performance residual (real per-shot xG pulled live from FotMob shotmap), (2) per-player injury penalties weighted by market value × expected availability. QF aggregates still use actual goals from the first legs.

### UCL Winner Probabilities

| Rank | Team | AI Win% | Polymarket | Edge | Signal |
|------|------|---------|------------|------|--------|
| 1 | **Arsenal** | **42.7%** | 25.5% | **+17.2%** | **STRONG BUY** |
| 2 | Bayern Munich | 32.3% | 31.5% | +0.8% | — |
| 3 | PSG | 15.9% | 21.5% | -5.6% | **STRONG SELL** |
| 4 | Atletico Madrid | 4.6% | 7.1% | -2.5% | — |
| 5 | Barcelona | 2.0% | 7.6% | -5.6% | **STRONG SELL** |
| 6 | Real Madrid | 1.3% | 5.3% | -4.1% | SELL |
| 7 | Liverpool | 0.7% | 2.1% | -1.4% | — |
| 8 | Sporting CP | 0.5% | 0.7% | -0.2% | — |

### QF Advancement Probabilities (Who Reaches Semis?)

| Team | AI Adv% | Polymarket | Edge | Signal |
|------|---------|------------|------|--------|
| Arsenal | **95.5%** | 89.5% | **+6.0%** | **STRONG BUY** |
| **Bayern Munich** | **91.9%** | **84.0%** | **+7.9%** | **STRONG BUY** |
| PSG | 89.9% | 87.5% | +2.4% | — |
| **Atletico Madrid** | **86.6%** | **72.0%** | **+14.6%** | **STRONG BUY** |
| **Barcelona** | **13.4%** | **30.5%** | **-17.1%** | **STRONG SELL** |
| Liverpool | 10.1% | 12.5% | -2.4% | — |
| **Real Madrid** | **8.1%** | **16.0%** | **-7.9%** | **STRONG SELL** |
| **Sporting CP** | **4.5%** | **10.5%** | **-6.0%** | **STRONG SELL** |

### Per-Model Breakdown (P(Champion))

| Team | Chronos-2 | TimesFM-2.5 | FlowState | Elo Baseline | **Ensemble** |
|------|-----------|-------------|-----------|-------------|:------------|
| Arsenal | 42.9% | 43.0% | 42.8% | 42.1% | **42.7%** |
| Bayern Munich | 32.1% | 32.2% | 32.7% | 32.4% | **32.3%** |
| PSG | 15.9% | 15.9% | 15.8% | 16.0% | **15.9%** |
| Atletico Madrid | 4.6% | 4.6% | 4.5% | 4.7% | **4.6%** |
| Barcelona | 2.1% | 2.1% | 2.0% | 1.9% | **2.0%** |
| Real Madrid | 1.3% | 1.3% | 1.2% | 1.3% | **1.3%** |
| Liverpool | 0.7% | 0.7% | 0.7% | 0.7% | **0.7%** |
| Sporting CP | 0.5% | 0.5% | 0.5% | 0.5% | **0.5%** |

## Biggest Edges

| Team | Market | AI | Mkt | Edge | Kelly | Signal |
|------|--------|-----|------|------|-------|--------|
| Arsenal | Winner | 42.7% | 25.5% | +17.2% | 11.5% | **STRONG BUY** |
| Barcelona | QF Adv | 13.4% | 30.5% | -17.1% | — | **STRONG SELL** |
| Atletico Madrid | QF Adv | 86.6% | 72.0% | +14.6% | 26.0% | **STRONG BUY** |
| Bayern Munich | QF Adv | 91.9% | 84.0% | +7.9% | 24.7% | **STRONG BUY** |
| Real Madrid | QF Adv | 8.1% | 16.0% | -7.9% | — | **STRONG SELL** |
| Arsenal | QF Adv | 95.5% | 89.5% | +6.0% | 27.3% | **STRONG BUY** |
| Sporting CP | QF Adv | 4.5% | 10.5% | -6.0% | — | **STRONG SELL** |
| Barcelona | Winner | 2.0% | 7.6% | -5.6% | — | **STRONG SELL** |
| PSG | Winner | 15.9% | 21.5% | -5.6% | — | **STRONG SELL** |

### Real xG from FotMob (extracted via Playwright + residential proxy)

| Leg | Match | Score | xG | xG Delta vs Placeholder |
|-----|-------|-------|-----|-------------------------|
| QF1 | PSG vs Liverpool | 2-0 | **2.35 - 0.17** | PSG way more dominant than scoreline |
| QF2 | Real Madrid vs Bayern | 1-2 | **2.22 - 2.92** | Both teams attacked heavily |
| QF3 | Barcelona vs Atletico | 0-2 | **1.10 - 0.43** | **Barça had MORE xG but lost** — unlucky |
| QF4 | Sporting vs Arsenal | 0-1 | **0.72 - 1.32** | Close to placeholder |

**Biggest correction from placeholder → real xG**:
- **PSG champion% +1.1pp** (14.6% → 15.7%): real dominance vs Liverpool (2.35 xG) was higher than placeholder assumed
- **Barcelona QF advance +1.7pp** (11.4% → 13.1%): their positive xG differential vs Atleti showed they were unlucky, not bad
- **Atletico champion% -0.9pp** (5.6% → 4.7%): their road win was actually less dominant than the 0-2 scoreline suggested (0.43 xG vs 1.10)

## Injury-Adjusted Elo (April 12, 2026 snapshot)

Pulled live from FotMob per-team endpoints. Each injured player contributes
`tier_base × availability_weight` of Elo penalty to their team; cap = 60 Elo per team.

| Team | ΔElo | Injured | Biggest hit |
|------|------|---------|-------------|
| **Arsenal** | **−46.5** | 5 | Saka (€98M, Doubtful), Ødegaard (€72M), Timber (€65M), Calafiori (€51M), Merino (€40M) |
| **Liverpool** | **−26.7** | 6 | Jones (€49M, Doubtful), Bradley (€39M, out for season), Leoni (€31M), Alisson (€17M) |
| Barcelona | −11.1 | 4 | Raphinha (€77M, Early May) |
| Bayern Munich | −9.1 | 5 | Karl (€39M, Late April) |
| Sporting CP | −7.8 | 3 | Ioannidis (€23M, Doubtful) |
| Real Madrid | −6.8 | 2 | Rodrygo (€56M, Early Dec — out), Courtois (€11M) |
| PSG | −5.5 | 3 | Barcola (€71M, Late April), Fabián (€28M) |
| Atletico Madrid | −5.0 | 2 | Hancko (€35M, Doubtful), Giménez (€14M) |

**Effect on predictions** (vs xG-only April 12 run):

- **Arsenal winner: 53.8% → 44.2% (−9.6pp)** — the injury pile-up (especially Saka doubtful) is the single biggest model revision of the day
- **Bayern winner: 27.0% → 31.2% (+4.2pp)** — Arsenal's loss is everyone else's gain; Bayern now nearly ties the market price (31.2% vs 32.0%)
- **PSG winner: 11.3% → 14.6% (+3.3pp)** — narrower STRONG SELL; the bracket advantage Arsenal had is less crushing
- **Atletico winner: 3.8% → 5.6%** (+1.8pp)
- **QF advance changes are small** (all already high) — injuries mostly reshape SF/Final conditional probabilities

**Why the signal is so lopsided toward Arsenal**: the doubtful list includes Saka, Ødegaard, Timber, Calafiori, and Merino — five of their top six starters. Even conservatively weighting "Doubtful" at 0.5, that's cumulative -46.5 Elo, nearly the per-team cap.

## Backtest Results (5 seasons, 2020-21 → 2024-25)

**Layer 1 baseline: pure Elo at tie date** — no TSFM, no xG, no injuries. Sampled 83 knockout ties from clubelo.com historical API at each tie's first-leg date. See [backtest/results/layer1_elo_baseline.md](backtest/results/layer1_elo_baseline.md) for the full report.

### Headline

| Metric | Model | Coin-flip baseline |
|--------|-------|--------------------|
| **Hit rate** | **63.9%** (53/83) | 50.0% |
| **Brier score** | **0.223** | 0.250 |
| **Log loss** | **0.629** | 0.693 |

**p-value (hit rate > 50%) = 0.0058** — statistically significant.

### Hit rate by stage

| Stage | n | Hit rate |
|-------|---|----------|
| R16 | 48 | **66.7%** |
| QF | 20 | **70.0%** |
| SF | 10 | 50.0% |
| Final | 5 | 40.0% (small sample) |

Signal is strongest early (R16/QF) where Elo gaps are widest. SF/Final pair comparably strong teams, so Elo advantage shrinks.

### Confidence-bucketed hit rate (key finding)

| Confidence | n | Hit rate |
|------------|---|----------|
| 50-55% (coin flip) | 10 | 50.0% |
| 55-65% (mild) | 21 | 66.7% |
| 65-75% (moderate) | 20 | **35.0% ⚠️** |
| ≥75% (high) | 32 | **84.4% ✅** |

- **High-confidence picks are very reliable** (84.4%) — when Elo gives a team ≥75% chance, trust it
- **Moderate picks (65-75%) underperform** — 35% hit rate means the model is **overconfident** in this range, likely because knockout ties have more variance than Poisson-Elo estimates suggest

### Calibration (predicted P vs actual P)

| Predicted bin | n | Mean predicted | Actual rate |
|---------------|---|----------------|-------------|
| 0-20% | 23 | 11.6% | 13.0% ✅ |
| 20-40% | 15 | 32.2% | 46.7% (overestimates underdogs) |
| 40-60% | 19 | 46.5% | 42.1% ✅ |
| 60-80% | 19 | 67.2% | **33.3% ⚠️ overconfident** |
| 80-100% | 7 | 86.9% | 85.7% ✅ |

**Takeaway**: extreme predictions (very high or very low) are well-calibrated; middle-high predictions (60-80%) are significantly overconfident.

### How to run

```bash
python scripts/fetch_historical_brackets.py   # cache 5 seasons of bracket + results
python scripts/run_backtest.py                # run model on all ties, write report
```

### Layer 2 backtest: Elo + TSFM ensemble

Same 83 ties, but each team's Elo is replaced with the ensemble forecast from 3 TSFM models (Chronos-2, TimesFM-2.5, FlowState) fed a 260-week history truncated to the tie date. See [backtest/results/layer2_tsfm_ensemble.md](backtest/results/layer2_tsfm_ensemble.md).

| Metric | Layer 2 | Layer 1 | Coin flip |
|--------|---------|---------|-----------|
| Hit rate | **63.9%** (53/83) | 63.9% | 50.0% |
| Brier | 0.219 | 0.220 | 0.250 |
| Log loss | 0.620 | 0.622 | 0.693 |

**Verdict: TSFM adds essentially zero signal** on top of Elo for knockout prediction.

- Only **4 ties out of 83** had a different top pick between L1 and L2; all four were coin-flip ties where both models hovered around 49-51%
- 2 flips helped, 2 flips hurt → net zero
- Brier and log loss improve by <1% — statistically indistinguishable

**Why**: TSFM forecasts Elo ~1-8 weeks ahead, but team strength doesn't drift meaningfully in that window. Current Elo ≈ forecasted Elo. The heavyweight time-series models add complexity without improving short-horizon predictions.

**Implication for live predictions**: keep the TSFM ensemble in `run_predictions.py` for uncertainty quantification (quantile ranges are still useful for sizing Kelly bets) but don't expect point-prediction improvements over the Elo baseline.

### Layer 3 backtest: xG-adjusted second-leg prediction

**Status: blocked on historical xG data source** (code is in place and ready — see `backtest/runner_layer3.py`, `scripts/run_backtest_layer3.py`, `tests/test_layer3_runner.py`).

Layer 3 re-frames the task to match the live pipeline: for each 2-legged tie, at 2nd-leg date with first-leg score and xG known, predict who advances. That isolates the incremental value of the xG signal (L3b) over a "first-leg score only" baseline (L3a).

**Why no historical xG**: three sources blocked:

| Source | Blocker |
|--------|---------|
| FotMob HTML (`/matches/{slug}/{code}#{matchId}`) | URL **aggregates to latest match** when teams have played again; old matchIds redirect. Requested 3497088 (2021) → served 4384190 (2024 rematch). No per-match historical access. |
| FotMob `/api/data/matchDetails?matchId=X` | Turnstile-gated; even with residential proxy + Playwright, returns `{"error":"TURNSTILE_REQUIRED"}` |
| FBref match pages | Cloudflare JS challenge; Playwright + stealth + residential proxy still held on "Just a moment…" after 30s |

**What works for the live pipeline**: `scripts/refresh_xg.py` intercepts the matchDetails response **while the current round's match page is still being served** (before FotMob aggregates it). That's how the April 13 run captured real xG for the 2025-26 QF first legs.

**To backtest Layer 3 in the future**: fill `backtest/fixtures/historical_xg.json` manually (format: `{season: {tie_key: {home_xg, away_xg}}}`) from any source — Opta reports, published research, paid API — then run `python scripts/run_backtest_layer3.py`. The runner is ready.

**Injury layer also not backtested**: FotMob's `/teams` endpoint returns *current* injury list only, no historical snapshots. Historical injury data would need a separate source (Transfermarkt has partial archive but requires scraping).

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
       First-leg Elo adjustment
    xG-blended residual vs Elo expectation
     → ΔElo feeds SF/Final simulations
                    │
                    ▼
       Injury-weighted Elo penalty (NEW)
    FotMob squad endpoint · market-value tier
     × availability weight → team Elo hit
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
| Injury tier (≥€80M) | −30 Elo | Superstar missing full tournament |
| Injury tier (€40-80M) | −15 Elo | Key starter |
| Injury tier (€15-40M) | −7 Elo | Regular starter |
| Injury tier (<€15M) | −3 Elo | Squad/rotation |
| "Doubtful" weight | 0.5 | Half penalty (uncertain) |
| "Out for season" weight | 1.0 | Full penalty |
| Per-team injury cap | −60 Elo | Prevents runaway collapses |

### Data Sources

- **Club Elo**: [clubelo.com](http://clubelo.com) — free historical club Elo ratings
- **Market odds**: [Polymarket](https://polymarket.com) Gamma API (public, no auth)
- **xG (match-level)**: [FotMob](https://www.fotmob.com) shotmap — the `/api/data/matchDetails` endpoint is Turnstile-gated, so fresh xG is pulled via `scripts/refresh_xg.py` (Playwright + residential proxy intercepts the JS-triggered API call). Values then live in `config.FIRST_LEG_XG`.
- **Injuries**: [FotMob](https://www.fotmob.com) per-team squad endpoint — returns live injury list, expected return date, and player market value. Augment with `config.MANUAL_INJURY_OVERRIDES` for anything FotMob misses.
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
# Fast mode — Elo + xG + injuries + Polymarket (≈ 10 seconds)
python run_predictions.py --fast

# Full pipeline — adds TSFM ensemble (≈ 5-7 min, negligible prediction gain)
python run_predictions.py

# Generate all visualizations
python generate_plots.py
```

`--fast` skips the TSFM time-series forecasters (Chronos-2, TimesFM-2.5, FlowState) and goes straight from current Elo → xG/injury adjustment → Monte Carlo. The [Layer 2 backtest](backtest/results/layer2_tsfm_ensemble.md) across 83 historical ties showed the TSFM ensemble changed the top pick on only 4 ties (2 helpful, 2 harmful) — net zero over pure Elo. Use `--fast` for day-to-day runs; reserve the full pipeline for when you want TSFM's uncertainty bands for Kelly sizing.

## Setup

Uses the same venv as worldcup-oracle and fin-forecast-arena:

```bash
ln -sf /home/ubuntu/fin-forecast-arena/venv venv
source venv/bin/activate
python run_predictions.py
```

## License

MIT License. See [LICENSE](LICENSE) for details.
