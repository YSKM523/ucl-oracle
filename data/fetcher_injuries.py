"""Fetch per-team injury lists from FotMob's public team endpoint.

The `/api/data/teams?id={id}` endpoint is Turnstile-free (unlike matchDetails)
and returns the full squad with each player's `injury` field when applicable.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from config import (
    FOTMOB_TEAM_IDS,
    MANUAL_INJURY_OVERRIDES,
    UCL_TEAMS,
)

log = logging.getLogger(__name__)

FOTMOB_TEAM_URL = "https://www.fotmob.com/api/data/teams"

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


@dataclass
class Injury:
    player: str
    transfer_value_m: float   # market value in €M
    expected_return: str      # raw FotMob string


def _fetch_team(team_id: int) -> Optional[dict]:
    try:
        resp = _SESSION.get(FOTMOB_TEAM_URL, params={"id": team_id}, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("FotMob team %s fetch failed: %s", team_id, exc)
        return None


def _extract_injuries(team_data: dict) -> list[Injury]:
    injuries: list[Injury] = []
    for group in team_data.get("squad", {}).get("squad", []):
        if group.get("title") == "coach":
            continue
        for member in group.get("members", []):
            inj_info = member.get("injury")
            if not inj_info:
                continue
            tv = member.get("transferValue") or 0
            injuries.append(
                Injury(
                    player=member.get("name", "?"),
                    transfer_value_m=tv / 1e6,
                    expected_return=str(inj_info.get("expectedReturn", "Unknown")),
                )
            )
    return injuries


def fetch_all_injuries() -> dict[str, list[Injury]]:
    """Return {team_name: [Injury, ...]}. Merges manual overrides into fetch results."""
    out: dict[str, list[Injury]] = {t: [] for t in UCL_TEAMS}

    for team, team_id in FOTMOB_TEAM_IDS.items():
        data = _fetch_team(team_id)
        if data is not None:
            out[team] = _extract_injuries(data)
        time.sleep(0.3)  # be polite

    # Merge manual overrides (append, don't replace — FotMob gaps we know about)
    for team, entries in MANUAL_INJURY_OVERRIDES.items():
        if team not in out:
            continue
        for e in entries:
            out[team].append(
                Injury(
                    player=e["name"],
                    transfer_value_m=float(e.get("transfer_value_m", 0.0)),
                    expected_return=e.get("expected_return", "Unknown"),
                )
            )

    total = sum(len(v) for v in out.values())
    log.info("Fetched injuries for %d teams (%d total)", len(out), total)
    return out
