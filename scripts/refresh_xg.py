"""Fetch real match xG from FotMob via Playwright + residential proxy.

The FotMob /api/data/matchDetails endpoint requires a Turnstile token in
direct API calls, but a headless Chromium session (loading the match page
with a residential proxy) triggers the JS that fetches it — we just listen
to the response and capture the JSON.

Usage:
    python scripts/refresh_xg.py              # refresh QF first legs
    python scripts/refresh_xg.py --leg qf2    # refresh one leg only

Requires: playwright with chromium installed, a proxies.txt file in repo
root with one `host:port:user:password` line per proxy (gitignored).
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import FIRST_LEG_RESULTS  # noqa: E402

log = logging.getLogger(__name__)
PROXY_FILE = ROOT / "proxies.txt"
OUT_FILE = ROOT / "data" / "cache" / "first_leg_xg.json"

# FotMob matchIds + slugs for the 2025-26 UCL QFs.
# NB: if you re-run this for a new round, update this dict with the new IDs.
MATCH_META = {
    "QF1": {"match_id": 5205789, "slug": "paris-saint-germain-vs-liverpool", "page": "379cod"},
    "QF2": {"match_id": 5205791, "slug": "real-madrid-vs-bayern-munchen",    "page": "2tes97"},
    "QF3": {"match_id": 5205793, "slug": "barcelona-vs-atletico-madrid",      "page": "x"},
    "QF4": {"match_id": 5205795, "slug": "sporting-cp-vs-arsenal",            "page": "x"},
}


def load_proxies() -> list[dict]:
    if not PROXY_FILE.exists():
        raise FileNotFoundError(
            f"{PROXY_FILE} not found. Put one `host:port:user:password` line per proxy "
            "(file is gitignored by design)."
        )
    proxies = []
    for line in PROXY_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        host, port, user, password = line.split(":", 3)
        proxies.append(
            {"server": f"http://{host}:{port}", "username": user, "password": password}
        )
    return proxies


def fetch_one(proxy: dict, match_id: int, slug: str, page_code: str) -> dict | None:
    """Open the match page and capture the matchDetails API response."""
    captured: dict = {}

    def on_response(resp):
        if "matchDetails" in resp.url and f"matchId={match_id}" in resp.url:
            try:
                captured["data"] = resp.json()
            except Exception:
                pass

    url = f"https://www.fotmob.com/matches/{slug}/{page_code}#{match_id}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy=proxy)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        page.on("response", on_response)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            for _ in range(15):
                page.wait_for_timeout(2_000)
                if "data" in captured:
                    break
        finally:
            browser.close()
    return captured.get("data")


def extract_team_xg(match_json: dict) -> dict | None:
    """Sum per-shot expectedGoals into (home_xg, away_xg)."""
    shots = match_json.get("content", {}).get("shotmap", {}).get("shots", [])
    if not shots:
        return None
    header = match_json.get("header", {}).get("teams", [])
    if len(header) < 2:
        return None
    home_id, away_id = header[0]["id"], header[1]["id"]
    totals: dict[int, float] = {}
    for s in shots:
        tid = s.get("teamId")
        xg = s.get("expectedGoals") or 0.0
        totals[tid] = totals.get(tid, 0.0) + float(xg)
    return {
        "home_name": header[0]["name"],
        "away_name": header[1]["name"],
        "home_xg": round(totals.get(home_id, 0.0), 3),
        "away_xg": round(totals.get(away_id, 0.0), 3),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--leg", help="Single leg to refresh (qf1|qf2|qf3|qf4); default = all")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    proxies = load_proxies()
    targets = MATCH_META if args.leg is None else {args.leg.upper(): MATCH_META[args.leg.upper()]}

    results: dict[str, dict] = {}
    for leg_id, meta in targets.items():
        match_id, slug, page = meta["match_id"], meta["slug"], meta["page"]
        print(f"Fetching {leg_id} (match {match_id}) …")
        success = False
        for attempt in range(args.retries):
            proxy = random.choice(proxies)
            data = fetch_one(proxy, match_id, slug, page)
            if data and not data.get("error"):
                xg = extract_team_xg(data)
                if xg:
                    results[leg_id] = xg
                    scoreline = FIRST_LEG_RESULTS.get(leg_id, {})
                    s = f"{scoreline.get('home_goals','?')}-{scoreline.get('away_goals','?')}"
                    print(
                        f"  {leg_id}: {xg['home_name']} {xg['home_xg']:.2f}-{xg['away_xg']:.2f} "
                        f"{xg['away_name']} (actual: {s})"
                    )
                    success = True
                    break
            print(f"  retry {attempt + 1}/{args.retries} with fresh proxy …")
        if not success:
            print(f"  {leg_id}: FAILED after {args.retries} attempts")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if OUT_FILE.exists():
        existing = json.loads(OUT_FILE.read_text())
        existing.update(results)
        results = existing
    OUT_FILE.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {OUT_FILE}")
    print("To activate: copy these values into config.FIRST_LEG_XG")
    for leg_id, xg in results.items():
        print(
            f'  "{leg_id}": {{"home_xg": {xg["home_xg"]}, "away_xg": {xg["away_xg"]}}},'
        )


if __name__ == "__main__":
    main()
