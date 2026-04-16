"""Fetch UCL odds and market data from Polymarket."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import pandas as pd
import requests

from config import GAMMA_API_BASE, CLOB_API_BASE, UCL_WINNER_EVENT_SLUG, UCL_SEMIS_EVENT_SLUG, UCL_FINALS_EVENT_SLUG

log = logging.getLogger(__name__)

# Polymarket display names → our canonical names
_POLYMARKET_TO_CANONICAL = {
    # Direct matches
    "Arsenal": "Arsenal",
    "Arsenal FC": "Arsenal",
    "Bayern Munich": "Bayern Munich",
    "Bayern München": "Bayern Munich",
    "FC Bayern München": "Bayern Munich",
    "Bayern": "Bayern Munich",
    "FC Bayern Munich": "Bayern Munich",
    "FC Bayern München": "Bayern Munich",
    "Barcelona": "Barcelona",
    "FC Barcelona": "Barcelona",
    "PSG": "PSG",
    "Paris Saint-Germain": "PSG",
    "Paris Saint-Germain FC": "PSG",
    "Paris SG": "PSG",
    "Paris Saint-Germain (PSG)": "PSG",
    "Real Madrid": "Real Madrid",
    "Real Madrid CF": "Real Madrid",
    "Liverpool": "Liverpool",
    "Liverpool FC": "Liverpool",
    "Sporting CP": "Sporting CP",
    "Sporting Lisbon": "Sporting CP",
    "Sporting": "Sporting CP",
    "Atletico Madrid": "Atletico Madrid",
    "Atlético Madrid": "Atletico Madrid",
    "Atlético de Madrid": "Atletico Madrid",
    "Atlético de Madrid": "Atletico Madrid",
    "Atletico": "Atletico Madrid",
    "Club Atlético de Madrid": "Atletico Madrid",
    "Atleti": "Atletico Madrid",
}


def _normalize_name(name: str) -> str:
    """Normalize a Polymarket team name to canonical form."""
    return _POLYMARKET_TO_CANONICAL.get(name, name)


class PolymarketClient:
    """Client for the Polymarket Gamma API (public, no auth needed)."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _get_event_by_slug(self, slug: str) -> dict | None:
        """Fetch an event by its slug."""
        try:
            resp = self.session.get(
                f"{GAMMA_API_BASE}/events",
                params={"slug": slug},
                timeout=30,
            )
            resp.raise_for_status()
            events = resp.json()
            return events[0] if events else None
        except (requests.RequestException, IndexError) as e:
            log.warning("Failed to fetch event '%s': %s", slug, e)
            return None

    def _parse_ucl_markets(self, markets: list[dict], event: dict, question_patterns: list[str]) -> pd.DataFrame | None:
        """Parse binary markets from a UCL event."""
        rows = []
        for market in markets:
            question = market.get("question", "")

            # Extract team name from question
            team_name = question
            for pattern in question_patterns:
                if pattern in team_name.lower():
                    # Try to extract just the team name
                    pass

            # Generic extraction: strip common prefixes/suffixes
            for prefix in ["Will ", "will "]:
                if team_name.startswith(prefix):
                    team_name = team_name[len(prefix):]

            # Remove various UCL suffixes (handle both regular hyphens and em-dashes)
            # Match: " win the YYYY-YY Champions League?" or "reach the ... semifinal?" etc.
            team_name = re.sub(
                r'\s+(win the|reach the)\s+.*$',
                '', team_name, flags=re.IGNORECASE
            )
            # Fallback: remove trailing "win?" or "advance?"
            for suffix in [" win?", " advance?"]:
                if team_name.lower().endswith(suffix):
                    team_name = team_name[: -len(suffix)]

            team_name = team_name.strip()

            # Get Yes price (= implied probability)
            prices_raw = market.get("outcomePrices", "[]")
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw

            if not prices:
                continue

            yes_price = float(prices[0])
            canonical = _normalize_name(team_name)

            rows.append({
                "team": canonical,
                "polymarket_name": team_name,
                "implied_prob": yes_price,
                "market_id": str(market.get("id", "")),
                "question": question,
            })

        if not rows:
            return None

        df = pd.DataFrame(rows)
        df["event_title"] = event.get("title", "")
        df["volume"] = float(event.get("volume", 0) or 0)
        df["liquidity"] = float(event.get("liquidity", 0) or 0)
        df["timestamp"] = datetime.now(timezone.utc).isoformat()

        return df.sort_values("implied_prob", ascending=False).reset_index(drop=True)

    def fetch_ucl_winner_odds(self) -> pd.DataFrame | None:
        """Fetch UCL winner market odds."""
        slugs = [
            UCL_WINNER_EVENT_SLUG,
            "champions-league-winner",
            "ucl-winner-2025-26",
            "2025-26-champions-league-winner",
        ]

        for slug in slugs:
            event = self._get_event_by_slug(slug)
            if event and event.get("markets"):
                df = self._parse_ucl_markets(
                    event["markets"], event,
                    ["champions league", "ucl"]
                )
                if df is not None and not df.empty:
                    return df

        # Fallback: search by query
        try:
            resp = self.session.get(
                f"{GAMMA_API_BASE}/events",
                params={"limit": 50, "active": "true", "order": "volume", "ascending": "false"},
                timeout=30,
            )
            resp.raise_for_status()
            for event in resp.json():
                title = event.get("title", "").lower()
                if "champions league" in title and "winner" in title:
                    markets = event.get("markets", [])
                    if markets:
                        df = self._parse_ucl_markets(markets, event, ["champions league"])
                        if df is not None and not df.empty:
                            return df
        except requests.RequestException as e:
            log.warning("Fallback search failed: %s", e)

        log.warning("Could not find UCL winner market on Polymarket")
        return None

    def fetch_ucl_semis_odds(self) -> pd.DataFrame | None:
        """Fetch UCL semi-final advancement market odds."""
        slugs = [
            UCL_SEMIS_EVENT_SLUG,
            "champions-league-semi-finals",
            "ucl-semi-finals-2025-26",
        ]

        for slug in slugs:
            event = self._get_event_by_slug(slug)
            if event and event.get("markets"):
                df = self._parse_ucl_markets(
                    event["markets"], event,
                    ["semi-final", "semifinal", "advance"]
                )
                if df is not None and not df.empty:
                    return df

        # Fallback search
        try:
            resp = self.session.get(
                f"{GAMMA_API_BASE}/events",
                params={"limit": 100, "active": "true", "order": "volume", "ascending": "false"},
                timeout=30,
            )
            resp.raise_for_status()
            for event in resp.json():
                title = event.get("title", "").lower()
                if "champions league" in title and ("semi" in title or "advance" in title):
                    markets = event.get("markets", [])
                    if markets:
                        df = self._parse_ucl_markets(markets, event, ["advance", "semi"])
                        if df is not None and not df.empty:
                            return df
        except requests.RequestException as e:
            log.warning("Fallback semis search failed: %s", e)

        log.warning("Could not find UCL semis advancement market on Polymarket")
        return None


    def fetch_ucl_finals_odds(self) -> pd.DataFrame | None:
        """Fetch UCL final advancement market odds (who reaches the final)."""
        slugs = [
            UCL_FINALS_EVENT_SLUG,
            "champions-league-finalists",
            "ucl-finals-2025-26",
            "champions-league-team-to-reach-final",
        ]

        for slug in slugs:
            event = self._get_event_by_slug(slug)
            if event and event.get("markets"):
                df = self._parse_ucl_markets(
                    event["markets"], event,
                    ["final", "advance"]
                )
                if df is not None and not df.empty:
                    return df

        # Fallback search
        try:
            resp = self.session.get(
                f"{GAMMA_API_BASE}/events",
                params={"limit": 100, "active": "true", "order": "volume", "ascending": "false"},
                timeout=30,
            )
            resp.raise_for_status()
            for event in resp.json():
                title = event.get("title", "").lower()
                if "champions league" in title and "final" in title and "winner" not in title:
                    markets = event.get("markets", [])
                    if markets:
                        df = self._parse_ucl_markets(markets, event, ["final", "advance"])
                        if df is not None and not df.empty:
                            return df
        except requests.RequestException as e:
            log.warning("Fallback finals search failed: %s", e)

        log.warning("Could not find UCL finals advancement market on Polymarket")
        return None


def fetch_all_ucl_odds() -> dict[str, pd.DataFrame | None]:
    """Fetch all UCL market odds."""
    client = PolymarketClient()
    return {
        "winner": client.fetch_ucl_winner_odds(),
        "semis": client.fetch_ucl_semis_odds(),
        "finals": client.fetch_ucl_finals_odds(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")

    odds = fetch_all_ucl_odds()

    for market_name, df in odds.items():
        print(f"\n{'='*60}")
        print(f"Market: {market_name}")
        if df is not None:
            print(f"Event: {df['event_title'].iloc[0]}")
            print(f"Volume: ${df['volume'].iloc[0]:,.0f}")
            print(f"\n{'Team':20s} {'Implied Prob':>12s}")
            print("-" * 35)
            for _, row in df.iterrows():
                print(f"{row['team']:20s} {row['implied_prob']:11.1%}")
        else:
            print("  Not found")
