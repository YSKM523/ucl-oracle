"""Load historical UCL fixture data + Elo snapshots for backtest."""

from __future__ import annotations

import io
import json
import logging
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests

from config import CLUBELO_API_BASE, CLUBELO_API_NAMES, CLUBELO_TO_CANONICAL

log = logging.getLogger(__name__)

# Historical team-name → clubelo short-name bridge. clubelo uses shortened
# forms ("Man City", "Dortmund") that don't appear in our canonical list.
BACKTEST_CLUBELO_ALIASES: dict[str, str] = {
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Borussia Dortmund": "Dortmund",
    "Borussia M'Gladbach": "Gladbach",
    "Bayer Leverkusen": "Leverkusen",
    "Eintracht Frankfurt": "Frankfurt",
    "FC Porto": "Porto",
    "RB Salzburg": "Salzburg",
    "Club Brugge": "Brugge",
    "FC Copenhagen": "FC Kobenhavn",
    "FC København": "FC Kobenhavn",
    "Real Sociedad": "Sociedad",
    "SSC Napoli": "Napoli",
    "Milan": "Milan",
    "AC Milan": "Milan",
    "Feyenoord": "Feyenoord",
    "PSV Eindhoven": "PSV",
    "Tottenham": "Tottenham",
    "Crvena Zvezda": "Crvena Zvezda",
    "Shakhtar Donetsk": "Shakhtar",
    "Young Boys": "Young Boys",
    "Slavia Praha": "Slavia Praha",
    "FC Copenhagen": "Kobenhavn",
    "Red Star Belgrade": "Crvena Zvezda",
    "FC Kobenhavn": "FC Kobenhavn",
}

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "ucl-oracle-backtest/1.0"})


def load_seasons(season_files: list[str] | None = None) -> list[dict]:
    """Load all fixture JSONs under backtest/fixtures/. Each entry has a 'ties' list."""
    files = sorted(FIXTURES_DIR.glob("*.json"))
    if season_files is not None:
        files = [FIXTURES_DIR / f for f in season_files]
    out = []
    for f in files:
        out.append(json.loads(f.read_text()))
    return out


@lru_cache(maxsize=256)
def _fetch_elo_snapshot(date: str) -> pd.DataFrame:
    """Fetch clubelo.com rankings for a given date (cached per-date)."""
    url = f"{CLUBELO_API_BASE}/{date}"
    resp = _SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text))


def get_elos_at_date(teams: list[str], date: str) -> dict[str, float | None]:
    """Return {team: elo_at_date} for each requested team. None if unknown."""
    df = _fetch_elo_snapshot(date)
    # Build reverse lookup: canonical name → Elo value
    df_map: dict[str, float] = {}
    for _, row in df.iterrows():
        club = row["Club"]
        canon = CLUBELO_TO_CANONICAL.get(club, club)
        df_map[canon] = float(row["Elo"])
    out: dict[str, float | None] = {}
    for t in teams:
        # 1. Exact match on canonical name
        if t in df_map:
            out[t] = df_map[t]
            continue
        # 2. Current-season API-name map
        api_name = CLUBELO_API_NAMES.get(t)
        if api_name and api_name in df_map:
            out[t] = df_map[api_name]
            continue
        # 3. Backtest-specific alias table (clubelo short names)
        alias = BACKTEST_CLUBELO_ALIASES.get(t)
        if alias and alias in df_map:
            out[t] = df_map[alias]
            continue
        out[t] = None
    return out
