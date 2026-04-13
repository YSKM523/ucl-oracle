"""Central configuration for ucl-oracle."""

from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
RESULTS_DIR = ROOT / "results"
PLOTS_DIR = RESULTS_DIR / "plots"

for d in [CACHE_DIR, RESULTS_DIR, PLOTS_DIR,
          RESULTS_DIR / "predictions", RESULTS_DIR / "edges"]:
    d.mkdir(parents=True, exist_ok=True)

# ── Tournament: 2025-26 UEFA Champions League ──────────────────────────────
TOURNAMENT_NAME = "2025-26 UEFA Champions League"
QF_SECOND_LEG_DATES = ("2026-04-14", "2026-04-15")
SF_DATES = ("2026-04-28", "2026-04-29", "2026-05-05", "2026-05-06")
FINAL_DATE = "2026-05-30"
FINAL_VENUE = "Budapest"

# ── 8 remaining teams ──────────────────────────────────────────────────────
UCL_TEAMS = [
    "PSG", "Liverpool",
    "Real Madrid", "Bayern Munich",
    "Barcelona", "Atletico Madrid",
    "Sporting CP", "Arsenal",
]

# ── First-leg results (already played) ─────────────────────────────────────
FIRST_LEG_RESULTS = {
    "QF1": {"home": "PSG", "away": "Liverpool", "home_goals": 2, "away_goals": 0},
    "QF2": {"home": "Real Madrid", "away": "Bayern Munich", "home_goals": 1, "away_goals": 2},
    "QF3": {"home": "Barcelona", "away": "Atletico Madrid", "home_goals": 0, "away_goals": 2},
    "QF4": {"home": "Sporting CP", "away": "Arsenal", "home_goals": 0, "away_goals": 1},
}

# ── First-leg xG (expected goals) ──────────────────────────────────────────
# Post-match xG feeds the Elo adjustment step (see elo_adjuster). These are
# scoreline-regressed placeholders; override with real values from FBref /
# FotMob / Opta match reports for a sharper signal.
FIRST_LEG_XG = {
    "QF1": {"home_xg": 1.7, "away_xg": 0.9},   # PSG 2-0 Liverpool
    "QF2": {"home_xg": 1.5, "away_xg": 1.4},   # Real 1-2 Bayern
    "QF3": {"home_xg": 0.8, "away_xg": 1.6},   # Barça 0-2 Atleti
    "QF4": {"home_xg": 0.7, "away_xg": 1.2},   # Sporting 0-1 Ars
}

# ── First-leg Elo adjustment ───────────────────────────────────────────────
# After first legs, bump each team's Elo based on how they performed vs the
# Elo-implied expectation. This flows into SF/Final Monte Carlo (QF sims
# continue to use actual first-leg goals for aggregate scoring).
#
# effective_gd = α·(xg_home - xg_away) + (1-α)·(goals_home - goals_away)
# residual     = effective_gd - poisson_expected_gd(Elo, home_adv)
# ΔElo         = K · clip(residual, -CAP, +CAP)
#
# α=0.6 weights xG over goals (xG is more predictive of future performance).
# K=10 is conservative — a 1-goal residual ≈ ±10 Elo (~1 week of form shift).
# CAP=2.5 prevents one anomalous blowout from dominating.
XG_BLEND_ALPHA = 0.6
FIRST_LEG_ELO_K = 10.0
FIRST_LEG_RESIDUAL_CAP = 2.5
FIRST_LEG_ADJUSTMENT_ENABLED = True

# ── Bracket structure (from the official Feb 27 draw) ─────────────────────
# SF home/away is fixed by bracket position, NOT by seeding.
# In each SF pairing, the team from the "bottom" QF in the bracket gets
# second-leg home (first arg = first-leg home = top QF winner).
# Source: UEFA official draw — bracket positions determine order.
#   SF1: QF1 winner (top) vs QF2 winner (bottom) → QF2 winner has 2nd-leg home
#   SF2: QF3 winner (top) vs QF4 winner (bottom) → QF4 winner has 2nd-leg home
BRACKET = {
    "SF1": ("QF1", "QF2"),   # Silver path — QF2 winner gets 2nd-leg home
    "SF2": ("QF3", "QF4"),   # Blue path — QF4 winner gets 2nd-leg home
    "Final": ("SF1", "SF2"),
}

# For each SF: which QF slot's winner gets second-leg home (= "bottom" in bracket).
# The other QF slot's winner is first-leg home (= "top" in bracket).
SF_SECOND_LEG_HOME = {
    "SF1": "QF2",   # QF2 winner gets 2nd-leg home
    "SF2": "QF4",   # QF4 winner gets 2nd-leg home
}

# ── clubelo.com API ────────────────────────────────────────────────────────
CLUBELO_API_BASE = "http://api.clubelo.com"

# clubelo.com team names → our canonical names
CLUBELO_TO_CANONICAL = {
    "Arsenal": "Arsenal",
    "Bayern": "Bayern Munich",
    "Barcelona": "Barcelona",
    "ParisSG": "PSG",
    "Paris SG": "PSG",
    "RealMadrid": "Real Madrid",
    "Real Madrid": "Real Madrid",
    "Liverpool": "Liverpool",
    "Sporting": "Sporting CP",
    "Atletico": "Atletico Madrid",
}

# API names for per-club history endpoint (no spaces)
CLUBELO_API_NAMES = {
    "Arsenal": "Arsenal",
    "Bayern Munich": "Bayern",
    "Barcelona": "Barcelona",
    "PSG": "ParisSG",
    "Real Madrid": "RealMadrid",
    "Liverpool": "Liverpool",
    "Sporting CP": "Sporting",
    "Atletico Madrid": "Atletico",
}
CANONICAL_TO_CLUBELO = {v: k for k, v in CLUBELO_TO_CANONICAL.items()}

# Hardcoded fallback Elo ratings (from clubelo.com API, 2026-04-09)
FALLBACK_ELO = {
    "Arsenal": 2064.62,
    "Bayern Munich": 2007.07,
    "Barcelona": 1986.76,
    "PSG": 1953.50,
    "Real Madrid": 1938.08,
    "Liverpool": 1927.24,
    "Sporting CP": 1869.37,
    "Atletico Madrid": 1861.18,
}

# ── Poisson Goal Model ────────────────────────────────────────────────────
POISSON_AVG_GOALS = 2.7       # UCL average total goals per match
ET_GOAL_FRACTION = 0.33       # Extra time is 30min / 90min
UCL_HOME_ADVANTAGE_ELO = 65   # Home advantage in club football
FINAL_HOME_ADVANTAGE_ELO = 0  # Neutral venue (Budapest)

# ── Bradley-Terry (for single-leg Final) ───────────────────────────────────
BRADLEY_TERRY_DRAW_NU = 0.28
KNOCKOUT_PENALTY_ADVANTAGE = 0.55

# ── TSFM Parameters ───────────────────────────────────────────────────────
TSFM_CONTEXT_WEEKS = 260     # ~5 years of weekly Elo history
TSFM_FORECAST_HORIZON = 8    # Weeks forward (QF → Final spans ~7 weeks)

FOUNDATION_MODELS = [
    ("models.chronos2_sports", "Chronos2SportsForecaster"),
    ("models.timesfm_sports", "TimesFMSportsForecaster"),
    ("models.flowstate_sports", "FlowStateSportsForecaster"),
]
FM_NAMES = ["Chronos-2", "TimesFM-2.5", "FlowState"]

# ── Monte Carlo ───────────────────────────────────────────────────────────
MONTE_CARLO_SIMULATIONS = 50_000

# ── Edge Detection ────────────────────────────────────────────────────────
MIN_EDGE_PCT = 3.0
STRONG_EDGE_PCT = 5.0
STRONG_EDGE_MIN_MODELS = 3

# ── Polymarket ────────────────────────────────────────────────────────────
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
UCL_WINNER_EVENT_SLUG = "uefa-champions-league-winner"
UCL_SEMIS_EVENT_SLUG = "uefa-champions-league-team-to-advance-to-semis"
