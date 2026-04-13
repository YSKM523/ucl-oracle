"""Fetch historical UCL knockout brackets + results from FotMob.

Writes one JSON per season to backtest/fixtures/{season}.json with all
knockout ties (R16, QF, SF, Final) including leg dates, aggregate scores,
winner team, and canonical team names.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import CLUBELO_TO_CANONICAL  # noqa: E402

log = logging.getLogger(__name__)
FIXTURES_DIR = ROOT / "backtest" / "fixtures"
FOTMOB_UCL_ID = 42

SEASONS = ["2020/2021", "2021/2022", "2022/2023", "2023/2024", "2024/2025"]

STAGE_LABELS = {16: "R16", 8: "QF", 4: "SF", 2: "Final"}

# FotMob uses varied name strings; map to our canonical names when possible.
# Fall back to raw name if unmatched.
FOTMOB_NAME_FIXES = {
    "Paris Saint-Germain": "PSG",
    "Bayern München": "Bayern Munich",
    "Atlético Madrid": "Atletico Madrid",
    "Inter": "Inter",
    "Internazionale": "Inter",
    "AC Milan": "AC Milan",
    "Manchester City": "Manchester City",
    "Man City": "Manchester City",
    "Manchester United": "Manchester United",
    "Borussia Dortmund": "Borussia Dortmund",
    "Real Madrid": "Real Madrid",
    "Barcelona": "Barcelona",
    "Atalanta": "Atalanta",
    "Chelsea": "Chelsea",
    "Arsenal": "Arsenal",
    "Liverpool": "Liverpool",
    "Tottenham Hotspur": "Tottenham",
    "Tottenham": "Tottenham",
    "Juventus": "Juventus",
    "Napoli": "Napoli",
    "Roma": "Roma",
    "Sporting CP": "Sporting CP",
    "Benfica": "Benfica",
    "Porto": "Porto",
    "Ajax": "Ajax",
    "PSV": "PSV",
    "PSV Eindhoven": "PSV",
    "RB Leipzig": "RB Leipzig",
    "Bayer Leverkusen": "Bayer Leverkusen",
    "Villarreal": "Villarreal",
    "Sevilla": "Sevilla",
    "Feyenoord": "Feyenoord",
    "Lazio": "Lazio",
    "Copenhagen": "FC Copenhagen",
    "FC Copenhagen": "FC Copenhagen",
    "Red Star Belgrade": "Crvena Zvezda",
    "Salzburg": "RB Salzburg",
    "FC Salzburg": "RB Salzburg",
    "RB Salzburg": "RB Salzburg",
    "Shakhtar Donetsk": "Shakhtar Donetsk",
    "Club Brugge": "Club Brugge",
    "Lille": "Lille",
    "Lyon": "Lyon",
    "AS Monaco": "Monaco",
    "Monaco": "Monaco",
    "Inter Milan": "Inter",
    "Bayern Munich": "Bayern Munich",
    "BVB": "Borussia Dortmund",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "Union Berlin": "Union Berlin",
    "AS Roma": "Roma",
    "SC Braga": "Braga",
    "Braga": "Braga",
    "Galatasaray": "Galatasaray",
    "Young Boys": "Young Boys",
    "Red Bull Salzburg": "RB Salzburg",
    "Real Sociedad": "Real Sociedad",
    "Aston Villa": "Aston Villa",
    "Slavia Prague": "Slavia Praha",
    "Stuttgart": "Stuttgart",
    "Newcastle United": "Newcastle",
    "Celtic": "Celtic",
    "Bologna": "Bologna",
    "Girona": "Girona",
    "Brest": "Brest",
}


def canonical_name(fotmob_name: str) -> str:
    return FOTMOB_NAME_FIXES.get(fotmob_name, fotmob_name)


def fetch_season(season: str) -> dict | None:
    url = "https://www.fotmob.com/api/data/leagues"
    params = {"id": FOTMOB_UCL_ID, "season": season, "ccode3": "ENG"}
    try:
        r = requests.get(
            url, params=params,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.fotmob.com/"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.error("Fetch %s failed: %s", season, exc)
        return None


def extract_ties(data: dict) -> list[dict]:
    """Return a flat list of all knockout ties in this season."""
    ties = []
    for round_obj in data.get("playoff", {}).get("rounds", []):
        pc = round_obj.get("participantCount")
        stage = STAGE_LABELS.get(pc)
        if stage is None:
            continue
        for mu in round_obj.get("matchups", []):
            legs = []
            for m in mu.get("matches") or []:
                status = m.get("status", {})
                if not status.get("finished"):
                    continue
                # Page URL looks like "/matches/real-madrid-vs-bayern-munchen/2tes97#5161876"
                page_url = m.get("pageUrl", "")
                slug = code = None
                if "/matches/" in page_url:
                    parts = page_url.split("/matches/")[-1].split("#")[0]
                    bits = parts.split("/")
                    if len(bits) >= 2:
                        slug, code = bits[0], bits[1]
                legs.append(
                    {
                        "date": status.get("utcTime", "")[:10],
                        "match_id": m.get("matchId"),
                        "slug": slug,
                        "page_code": code,
                        "home": canonical_name(m["home"]["name"]),
                        "away": canonical_name(m["away"]["name"]),
                        "home_goals": m["home"].get("score"),
                        "away_goals": m["away"].get("score"),
                    }
                )
            if len(legs) < 1:
                continue
            home_team = canonical_name(mu["homeTeam"])
            away_team = canonical_name(mu["awayTeam"])
            winner_id = mu.get("winner")
            winner_team = (
                home_team if winner_id == mu.get("homeTeamId")
                else away_team if winner_id == mu.get("awayTeamId")
                else None
            )
            ties.append(
                {
                    "stage": stage,
                    "home_team": home_team,
                    "away_team": away_team,
                    "agg_home": mu.get("homeScore"),
                    "agg_away": mu.get("awayScore"),
                    "winner": winner_team,
                    "legs": legs,
                    "first_leg_date": legs[0]["date"] if legs else None,
                    "is_single_match": len(legs) == 1,
                }
            )
    return ties


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    for season in SEASONS:
        out_path = FIXTURES_DIR / f"{season.replace('/', '-')}.json"
        print(f"Fetching {season} …")
        data = fetch_season(season)
        if data is None:
            print(f"  {season}: FAILED")
            continue
        ties = extract_ties(data)
        # Filter out ties with missing winner (unfinished)
        ties = [t for t in ties if t["winner"] is not None]
        out_path.write_text(json.dumps({"season": season, "ties": ties}, indent=2))
        stages = {}
        for t in ties:
            stages[t["stage"]] = stages.get(t["stage"], 0) + 1
        print(f"  {season}: {len(ties)} ties ({stages})")
        time.sleep(1)


if __name__ == "__main__":
    main()
