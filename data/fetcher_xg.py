"""Best-effort xG fetcher for UCL first-leg matches.

Tries FotMob's matchDetails endpoint. Many CDN paths now require a Turnstile
token; when that happens we log and return None so callers fall back to the
config placeholders. Values that *do* come back override the config for the
current run without mutating it.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import requests

from config import FIRST_LEG_XG, UCL_TEAMS

log = logging.getLogger(__name__)

FOTMOB_UCL_ID = 42
FOTMOB_LEAGUE_URL = "https://www.fotmob.com/api/data/leagues"
FOTMOB_MATCH_URL = "https://www.fotmob.com/api/data/matchDetails"

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/127.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://www.fotmob.com/",
    }
)

# Map canonical team → FotMob short/long name fragments for matching QF fixtures.
TEAM_NAME_ALIASES = {
    "PSG": ["Paris Saint-Germain", "PSG"],
    "Liverpool": ["Liverpool"],
    "Real Madrid": ["Real Madrid"],
    "Bayern Munich": ["Bayern München", "Bayern Munich"],
    "Barcelona": ["Barcelona"],
    "Atletico Madrid": ["Atletico Madrid", "Atlético Madrid"],
    "Sporting CP": ["Sporting CP"],
    "Arsenal": ["Arsenal"],
}


def _match_team(name: str) -> Optional[str]:
    for canonical, aliases in TEAM_NAME_ALIASES.items():
        if name in aliases or any(a in name for a in aliases):
            return canonical
    return None


def fetch_qf_first_leg_match_ids() -> dict[str, int]:
    """Return {qf_id: first_leg_matchId} by inspecting FotMob's UCL league data."""
    try:
        resp = _SESSION.get(
            FOTMOB_LEAGUE_URL, params={"id": FOTMOB_UCL_ID, "ccode3": "ENG"}, timeout=20
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("FotMob league fetch failed: %s", exc)
        return {}

    rounds = data.get("playoff", {}).get("rounds", [])
    qf_round = next((r for r in rounds if r.get("participantCount") == 8), None)
    if qf_round is None:
        return {}

    # Order matchups by drawOrder so QF1..QF4 matches FIRST_LEG_RESULTS slot order.
    matchups = sorted(qf_round.get("matchups", []), key=lambda m: m.get("drawOrder", 0))
    out: dict[str, int] = {}
    for i, mu in enumerate(matchups, start=1):
        matches = mu.get("matches") or []
        finished = [m for m in matches if m.get("status", {}).get("finished")]
        if finished:
            out[f"QF{i}"] = int(finished[0]["matchId"])
    return out


def fetch_match_xg(match_id: int) -> Optional[tuple[str, str, float, float]]:
    """Return (home_name, away_name, home_xg, away_xg) or None."""
    try:
        resp = _SESSION.get(FOTMOB_MATCH_URL, params={"matchId": match_id}, timeout=20)
        if resp.status_code != 200:
            log.info("FotMob matchDetails %s → %s", match_id, resp.status_code)
            return None
        data = resp.json()
        if data.get("error"):
            log.info("FotMob matchDetails %s error: %s", match_id, data.get("error"))
            return None
    except (requests.RequestException, json.JSONDecodeError) as exc:
        log.info("FotMob matchDetails %s fetch error: %s", match_id, exc)
        return None

    header = data.get("header", {}).get("teams", [])
    if len(header) < 2:
        return None
    home_name, away_name = header[0].get("name"), header[1].get("name")

    # xG lives in content.stats.stats[*] as a row labelled "Expected goals (xG)".
    stats_root = data.get("content", {}).get("stats", {}).get("stats") or []
    xg_row = None
    for group in stats_root:
        for row in group.get("stats") or []:
            if row.get("title") in {"Expected goals (xG)", "Expected goals", "xG"}:
                xg_row = row
                break
        if xg_row:
            break
    if xg_row is None:
        return None

    stats_val = xg_row.get("stats") or xg_row.get("values")
    if not stats_val or len(stats_val) < 2:
        return None
    try:
        return home_name, away_name, float(stats_val[0]), float(stats_val[1])
    except (TypeError, ValueError):
        return None


def fetch_first_leg_xg() -> dict[str, dict[str, float]]:
    """Merge FotMob-fetched xG over config placeholders. Never raises."""
    merged = {qf: dict(v) for qf, v in FIRST_LEG_XG.items()}
    ids = fetch_qf_first_leg_match_ids()
    if not ids:
        log.info("Using config FIRST_LEG_XG placeholders (no live xG available).")
        return merged

    for qf_id, match_id in ids.items():
        got = fetch_match_xg(match_id)
        if got is None:
            continue
        home_name, away_name, home_xg, away_xg = got
        canonical_home = _match_team(home_name)
        canonical_away = _match_team(away_name)
        if canonical_home is None or canonical_away is None:
            log.info("%s: team name unmatched (%s, %s)", qf_id, home_name, away_name)
            continue
        merged[qf_id] = {"home_xg": home_xg, "away_xg": away_xg}
        log.info(
            "%s xG refreshed from FotMob: %s %.2f - %.2f %s",
            qf_id, canonical_home, home_xg, away_xg, canonical_away,
        )
    return merged
