"""Fetch club Elo ratings from clubelo.com API."""

from __future__ import annotations

import io
import logging
from datetime import datetime

import pandas as pd
import requests

from config import (
    CACHE_DIR,
    CLUBELO_API_BASE,
    CLUBELO_API_NAMES,
    CLUBELO_TO_CANONICAL,
    CANONICAL_TO_CLUBELO,
    FALLBACK_ELO,
    UCL_TEAMS,
)

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "ucl-oracle/1.0"})

CURRENT_ELOS_CACHE = CACHE_DIR / "current_elos.parquet"
CLUB_HISTORY_DIR = CACHE_DIR / "club_histories"
CLUB_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def fetch_current_elos(date: str | None = None) -> dict[str, float]:
    """Fetch current Elo ratings for UCL teams from clubelo.com.

    Parameters
    ----------
    date : YYYY-MM-DD string. Defaults to today.

    Returns
    -------
    {canonical_team_name: elo_rating}
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Fetch from API
    try:
        resp = _SESSION.get(f"{CLUBELO_API_BASE}/{date}", timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), header=0)
    except requests.RequestException as e:
        log.warning("clubelo.com API failed (%s), using fallback Elo", e)
        return dict(FALLBACK_ELO)

    # Parse response — errors here are bugs, not transient failures
    elos = {}
    for _, row in df.iterrows():
        club_name = str(row["Club"]).strip()
        if club_name in CLUBELO_TO_CANONICAL:
            canonical = CLUBELO_TO_CANONICAL[club_name]
            elos[canonical] = float(row["Elo"])

    missing = set(UCL_TEAMS) - set(elos.keys())
    if missing:
        log.warning("Missing teams from API: %s — filling from fallback", missing)
        for team in missing:
            elos[team] = FALLBACK_ELO[team]
    else:
        log.info("Fetched Elo for all %d teams from clubelo.com", len(elos))

    # Cache is best-effort — never mask live data with a write failure
    try:
        cache_df = pd.DataFrame([
            {"team": t, "elo": e, "date": date} for t, e in elos.items()
        ])
        cache_df.to_parquet(CURRENT_ELOS_CACHE)
    except Exception as e:
        log.warning("Failed to cache Elo to parquet: %s", e)

    return elos


def fetch_club_history(team: str, force: bool = False) -> pd.DataFrame:
    """Fetch full Elo history for a club from clubelo.com.

    The API returns period-format data: each row has (Elo, From, To)
    meaning the club had that Elo from date From to date To.

    Parameters
    ----------
    team : Canonical team name (e.g., "Bayern Munich")

    Returns
    -------
    DataFrame with columns: date_from, date_to, elo
    """
    cache_path = CLUB_HISTORY_DIR / f"{team.replace(' ', '_')}.parquet"
    if cache_path.exists() and not force:
        try:
            return pd.read_parquet(cache_path)
        except Exception as e:
            log.warning("Cache read failed for %s (%s), re-fetching from API", team, e)

    clubelo_name = CLUBELO_API_NAMES[team]

    # Fetch from API
    try:
        resp = _SESSION.get(f"{CLUBELO_API_BASE}/{clubelo_name}", timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Failed to fetch history for %s: %s", team, e)
        if cache_path.exists():
            try:
                return pd.read_parquet(cache_path)
            except Exception:
                pass
        raise

    # Parse response
    df = pd.read_csv(io.StringIO(resp.text), header=0)
    df = df.rename(columns={"From": "date_from", "To": "date_to", "Elo": "elo"})
    df["date_from"] = pd.to_datetime(df["date_from"])
    df["date_to"] = pd.to_datetime(df["date_to"])
    df = df[["date_from", "date_to", "elo"]].sort_values("date_from").reset_index(drop=True)

    # Cache is best-effort
    try:
        df.to_parquet(cache_path)
        log.info("Cached Elo history for %s (%d periods)", team, len(df))
    except Exception as e:
        log.warning("Failed to cache history for %s: %s", team, e)

    return df


def fetch_all_histories(force: bool = False) -> dict[str, pd.DataFrame]:
    """Fetch Elo history for all UCL teams."""
    histories = {}
    for team in UCL_TEAMS:
        histories[team] = fetch_club_history(team, force=force)
    return histories


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")

    print("Fetching current Elo ratings …")
    elos = fetch_current_elos()
    for team in sorted(elos, key=elos.get, reverse=True):
        print(f"  {team:20s} {elos[team]:.2f}")
