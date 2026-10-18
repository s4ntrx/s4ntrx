#!/usr/bin/env python3
"""Generate a self-hosted SVG of the last 30 days of GitHub activity."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen


GRAPHQL_URL = "https://api.github.com/graphql"


def fetch_contributions(username: str, token: str) -> list[dict[str, object]]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=29)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    payload = json.dumps(
        {
            "query": query,
            "variables": {
                "login": username,
                "from": f"{start.isoformat()}T00:00:00Z",
                "to": f"{today.isoformat()}T23:59:59Z",
            },
        }
    ).encode()
    request = Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "monthly-activity-wave",
        },
    )

    with urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("errors"):
        raise RuntimeError(result["errors"])

    calendar = result["data"]["user"]["contributionsCollection"][
        "contributionCalendar"
    ]
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
    return [day for day in days if start.isoformat() <= day["date"] <= today.isoformat()]


def smooth_path(points: list[tuple[float, float]]) -> str:
    commands = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    for previous, current in zip(points, points[1:]):
        midpoint = (previous[0] + current[0]) / 2
        commands.append(
            f"C {midpoint:.1f} {previous[1]:.1f}, "
            f"{midpoint:.1f} {current[1]:.1f}, "
            f"{current[0]:.1f} {current[1]:.1f}"
        )
    return " ".join(commands)


def render_svg(username: str, days: list[dict[str, object]]) -> str:
    width, height = 900, 280
    left, right, top, bottom = 54, 24, 92, 226
    chart_width, chart_height = width - left - right, bottom - top
    counts = [int(day["contributionCount"]) for day in days]
    peak = max(max(counts), 1)
    total = sum(counts)
    points = [
        (
            left + index * chart_width / max(len(days) - 1, 1),
            bottom - count * chart_height / peak,
        )
        for index, count in enumerate(counts)
    ]
    line_path = smooth_path(points)
    area_path = f"{line_path} L {points[-1][0]:.1f} {bottom} L {left} {bottom} Z"

    grid = []
    for step in range(5):
        y = bottom - step * chart_height / 4
        value = round(step * peak / 4)
        grid.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" '
            f'y2="{y:.1f}" class="grid" />'
            f'<text x="{left - 12}" y="{y + 4:.1f}" class="axis" '
            f'text-anchor="end">{value}</text>'
        )

    label_indexes = sorted({0, 7, 14, 21, len(days) - 1})
    labels = []
    for index in label_indexes:
        date = datetime.strptime(str(days[index]["date"]), "%Y-%m-%d")
        anchor = "start" if index == 0 else "end" if index == len(days) - 1 else "middle"
        labels.append(
            f'<text x="{points[index][0]:.1f}" y="252" class="axis" '
            f'text-anchor="{anchor}">{date.strftime("%b %d")}</text>'
        )

    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" class="dot" />'
        for (x, y), count in zip(points, counts)
        if count
    )
    date_range = f'{days[0]["date"]} / {days[-1]["date"]}'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
  <title id="title">{escape(username)} GitHub activity over the last 30 days</title>
  <desc id="description">{total} contributions from {days[0]["date"]} through {days[-1]["date"]}.</desc>
  <defs>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#8b5cf6" stop-opacity="0.72" />
      <stop offset="100%" stop-color="#8b5cf6" stop-opacity="0.06" />
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
  </defs>
  <style>
    .title {{ fill: #d4af37; font: 700 20px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 0; }}
    .meta {{ fill: #9aa7b4; font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 0; }}
    .axis {{ fill: #7d8996; font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 0; }}
    .grid {{ stroke: #27313c; stroke-width: 1; }}
    .wave {{ fill: none; stroke: #a78bfa; stroke-width: 3; stroke-linecap: round; filter: url(#glow); animation: glow 3.2s ease-in-out infinite; }}
    .area {{ fill: url(#area); opacity: 0.82; animation: breathe 3.2s ease-in-out infinite; }}
    .dot {{ fill: #d4af37; stroke: #0d1117; stroke-width: 2; animation: glow 3.2s ease-in-out infinite; }}
    @keyframes glow {{ 50% {{ opacity: 0.72; }} }}
    @keyframes breathe {{ 50% {{ opacity: 0.58; }} }}
    @media (prefers-reduced-motion: reduce) {{ .wave, .area, .dot {{ animation: none; }} }}
  </style>
  <rect x="1" y="1" width="898" height="278" rx="7" fill="#0d1117" stroke="#d4af37" stroke-opacity="0.55" />
  <text x="32" y="38" class="title">30-DAY ACTIVITY // {total} CONTRIBUTIONS</text>
  <text x="32" y="64" class="meta">{escape(date_range)}  •  UPDATED DAILY</text>
  {''.join(grid)}
  <path d="{area_path}" class="area" />
  <path d="{line_path}" class="wave" />
  {dots}
  {''.join(labels)}
</svg>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="s4ntrx")
    parser.add_argument("--output", default="assets/monthly-activity-wave.svg")
    args = parser.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Set GH_TOKEN or GITHUB_TOKEN before running this script.")

    days = fetch_contributions(args.username, token)
    if len(days) != 30:
        raise RuntimeError(f"Expected 30 contribution days, received {len(days)}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_svg(args.username, days), encoding="utf-8")


if __name__ == "__main__":
    main()
