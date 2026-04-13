"""Batch-fetch first-leg xG for all historical 2-legged ties via Playwright + proxies.

Reads every two-legged tie from backtest/fixtures/*.json, finds the first leg's
matchId, opens that match page in a headless Chromium through a residential
proxy, intercepts the JS-triggered matchDetails API response, and sums per-shot
xG into (home_xg, away_xg).

Output cache: backtest/fixtures/historical_xg.json — a nested dict
    {season: {"{stage}_{home}_vs_{away}": {"home_xg": ..., "away_xg": ...}}}
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

log = logging.getLogger(__name__)
FIXTURES_DIR = ROOT / "backtest" / "fixtures"
CACHE_FILE = FIXTURES_DIR / "historical_xg.json"
PROXY_FILE = ROOT / "proxies.txt"
ALIVE_PROXY_FILE = ROOT / "proxies_alive.txt"


def load_proxies() -> list[dict]:
    # Prefer the pre-filtered live-only list when present
    source = ALIVE_PROXY_FILE if ALIVE_PROXY_FILE.exists() else PROXY_FILE
    lines = [l.strip() for l in source.read_text().splitlines() if l.strip()]
    out = []
    for line in lines:
        host, port, user, password = line.split(":", 3)
        out.append({"server": f"http://{host}:{port}", "username": user, "password": password})
    return out


def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def tie_key(tie: dict) -> str:
    return f"{tie['stage']}_{tie['home_team']}_vs_{tie['away_team']}"


def collect_jobs() -> list[dict]:
    """Flatten all first-leg match fetches we need to do across all seasons."""
    jobs = []
    for f in sorted(FIXTURES_DIR.glob("*.json")):
        if f.name == "historical_xg.json":
            continue
        data = json.loads(f.read_text())
        season = data["season"]
        for tie in data["ties"]:
            if tie.get("is_single_match", False):
                continue
            legs = tie.get("legs") or []
            if not legs:
                continue
            first = legs[0]
            if not first.get("match_id") or not first.get("slug") or not first.get("page_code"):
                continue
            jobs.append(
                {
                    "season": season,
                    "tie_key": tie_key(tie),
                    "stage": tie["stage"],
                    "home": tie["home_team"],
                    "away": tie["away_team"],
                    "match_id": first["match_id"],
                    "slug": first["slug"],
                    "page_code": first["page_code"],
                    "date": first["date"],
                }
            )
    return jobs


def parse_match_details(data: dict) -> dict | None:
    shots = data.get("content", {}).get("shotmap", {}).get("shots", [])
    if not shots:
        return None
    header = data.get("header", {}).get("teams", [])
    if len(header) < 2:
        return None
    home_id, away_id = header[0]["id"], header[1]["id"]
    totals: dict[int, float] = {}
    for s in shots:
        tid = s.get("teamId")
        xg = s.get("expectedGoals") or 0.0
        totals[tid] = totals.get(tid, 0.0) + float(xg)
    return {
        "home_xg": round(totals.get(home_id, 0.0), 3),
        "away_xg": round(totals.get(away_id, 0.0), 3),
    }


def fetch_xg_one_match(proxy: dict, match_id: int, slug: str, page_code: str) -> dict | None:
    """Fresh Playwright session per match. More reliable than batched."""
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
            for _ in range(12):
                page.wait_for_timeout(1_500)
                if "data" in captured:
                    break
        except Exception as exc:
            log.info("  page error: %s", exc)
        finally:
            browser.close()

    data = captured.get("data")
    if data is None or data.get("error"):
        return None
    return parse_match_details(data)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--skip-cached", action="store_true", default=True)
    args = parser.parse_args()

    proxies = load_proxies()
    cache = load_cache()
    jobs = collect_jobs()

    todo = []
    for job in jobs:
        cached = cache.get(job["season"], {}).get(job["tie_key"])
        if args.skip_cached and cached is not None:
            continue
        todo.append(job)

    print(f"Total jobs: {len(jobs)}  |  Cached: {len(jobs) - len(todo)}  |  To fetch: {len(todo)}")
    if not todo:
        print("Nothing to do.")
        return

    t_start = time.perf_counter()
    for i, job in enumerate(todo, start=1):
        print(
            f"[{i}/{len(todo)}] {job['season']} {job['stage']} "
            f"{job['home']} vs {job['away']} (match {job['match_id']})",
            flush=True,
        )
        got = None
        for attempt in range(args.retries):
            proxy = random.choice(proxies)
            try:
                got = fetch_xg_one_match(
                    proxy, job["match_id"], job["slug"], job["page_code"]
                )
                if got is not None:
                    break
            except Exception as exc:
                log.info("  attempt %d failed: %s", attempt + 1, exc)

        if got is None:
            print(f"  FAILED after {args.retries} tries", flush=True)
            continue

        season_cache = cache.setdefault(job["season"], {})
        season_cache[job["tie_key"]] = {
            **got,
            "home": job["home"],
            "away": job["away"],
            "match_id": job["match_id"],
            "date": job["date"],
        }
        save_cache(cache)
        elapsed = time.perf_counter() - t_start
        remaining = (len(todo) - i) * (elapsed / i)
        print(
            f"  {job['home']} {got['home_xg']:.2f} - {got['away_xg']:.2f} {job['away']} "
            f"| elapsed {elapsed:.0f}s, ETA {remaining:.0f}s",
            flush=True,
        )

    print(f"\nDone. Cache at {CACHE_FILE}")


if __name__ == "__main__":
    main()
