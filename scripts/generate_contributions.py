"""Render the GitHub contribution calendar as a compact purple isometric SVG.

Layout and palette adapted from beydemirfurkan/awesome-github-profile's
3d-contribution-tower template (MIT; see THIRD_PARTY_NOTICES.md).
Only Python's standard library is required. GitHub supplies GITHUB_TOKEN in CI.
"""

import argparse
from datetime import date, datetime, timezone
from html import escape
import json
import math
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount weekday }
        }
      }
    }
  }
}
"""
PALETTE = ["#211a36", "#55428f", "#7355c8", "#9a78ff", "#c2a8ff"]


def fetch_calendar(username):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN is required when fetching from GitHub")
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": username}}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "oliver-profile-contribution-skyline",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise ValueError(f"GitHub API returned HTTP {exc.code}") from None
    except (URLError, TimeoutError):
        raise ValueError("Could not fetch GitHub contributions; keeping the existing image") from None
    if payload.get("errors"):
        raise ValueError("GitHub GraphQL returned errors; keeping the existing image")
    user = payload.get("data", {}).get("user")
    if not user:
        raise ValueError(f"GitHub user {username!r} was not found")
    return user["contributionsCollection"]["contributionCalendar"]


def calendar_days(calendar, today):
    """Validate, deduplicate and sort actual days; ignore future padding cells."""
    days = {}
    for week in calendar["weeks"]:
        for item in week["contributionDays"]:
            day = date.fromisoformat(item["date"])
            count = item["contributionCount"]
            if type(count) is not int or count < 0:
                raise ValueError("Contribution counts must be nonnegative integers")
            if day in days:
                raise ValueError("The contribution calendar contains duplicate dates")
            days[day] = count
    result = [(day, count) for day, count in sorted(days.items()) if day <= today]
    if not 350 <= len(result) <= 372:
        raise ValueError("Expected approximately one year of daily contributions")
    if any((right[0] - left[0]).days != 1 for left, right in zip(result, result[1:])):
        raise ValueError("The contribution calendar contains missing dates")
    if "totalContributions" in calendar and sum(count for _, count in result) != calendar["totalContributions"]:
        raise ValueError("Daily contribution counts do not match GitHub's reported total")
    return result


def tint(color, amount):
    channels = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    target = 255 if amount >= 0 else 0
    return "#" + "".join(f"{round(c + (target - c) * abs(amount)):02x}" for c in channels)


def render_svg(username, calendar, today):
    days = calendar_days(calendar, today)
    total = sum(count for _, count in days)
    peak = max(count for _, count in days)
    active = sum(count > 0 for _, count in days)
    start, end = days[0][0], days[-1][0]
    sunday_offset = (start.weekday() + 1) % 7
    blocks = []
    for day, count in days:
        index = (day - start).days + sunday_offset
        week, weekday = divmod(index, 7)
        x, y = 500 + (week - weekday) * 11, 88 + (week + weekday) * 4.6
        level = 0 if count == 0 else min(4, max(1, math.ceil(count / max(peak, 1) * 4)))
        height = 2 if count == 0 else 8 + math.sqrt(count / max(peak, 1)) * 68
        top_y = y - height
        fill = PALETTE[level]
        # Back-to-front order prevents nearer cells being covered by distant ones.
        blocks.append((week + weekday, week, f'''<g data-date="{day.isoformat()}" data-count="{count}">
<title>{day.isoformat()}: {count} contribution{'s' if count != 1 else ''}</title>
<path d="M{x-10.2:.1f},{top_y:.1f} L{x:.1f},{top_y+4.3:.1f} L{x:.1f},{y+4.3:.1f} L{x-10.2:.1f},{y:.1f} Z" fill="{fill}"/>
<path d="M{x+10.2:.1f},{top_y:.1f} L{x:.1f},{top_y+4.3:.1f} L{x:.1f},{y+4.3:.1f} L{x+10.2:.1f},{y:.1f} Z" fill="{tint(fill,-0.3)}"/>
<path d="M{x:.1f},{top_y-4.3:.1f} L{x+10.2:.1f},{top_y:.1f} L{x:.1f},{top_y+4.3:.1f} L{x-10.2:.1f},{top_y:.1f} Z" fill="{tint(fill,0.15)}"/>
</g>'''))
    block_svg = "\n".join(block for _, _, block in sorted(blocks))
    legend = "".join(f'<rect x="{60+i*30}" y="184" width="27" height="12" rx="1" fill="{color}"/>' for i, color in enumerate(PALETTE))
    safe_name = escape(username)
    # Constant geometry keeps a normal and a very busy year equally well framed.
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="420" viewBox="0 0 1200 420" role="img" aria-labelledby="title description">
<title id="title">{safe_name}'s contribution skyline</title>
<desc id="description">{total} contributions across {active} active days from {start} to {end}. Each block is one day; height and color represent contribution count. Peak: {peak} contributions in one day.</desc>
<defs>
<linearGradient id="background" x1="0" y1="0" x2="0.6" y2="1"><stop stop-color="#150a30"/><stop offset="1" stop-color="#050310"/></linearGradient>
<radialGradient id="halo"><stop stop-color="#7c3aed" stop-opacity="0.25"/><stop offset="1" stop-color="#7c3aed" stop-opacity="0"/></radialGradient>
</defs>
<rect width="1200" height="420" rx="14" fill="url(#background)"/>
<ellipse cx="815" cy="267" rx="345" ry="140" fill="url(#halo)"/>
<g font-family="Segoe UI, Arial, sans-serif">
<text x="60" y="71" font-size="27" font-weight="700" fill="#ede9fe">Contribution skyline</text>
<text x="60" y="99" font-size="12" letter-spacing="1.1" fill="#a89ce0">{start.strftime('%b %Y').upper()} — {end.strftime('%b %Y').upper()}</text>
<line x1="60" y1="127" x2="300" y2="127" stroke="#3d2f7a"/>
<text x="60" y="166" font-size="11" letter-spacing="1.6" fill="#a89ce0">CONTRIBUTIONS PER DAY</text>
{legend}
<text x="60" y="218" font-size="11" fill="#a89ce0">0</text>
<text x="207" y="218" text-anchor="end" font-size="11" fill="#a89ce0">{peak}</text>
<line x1="60" y1="250" x2="300" y2="250" stroke="#3d2f7a"/>
<text x="60" y="280" font-size="10" letter-spacing="1.4" fill="#a89ce0">TOTAL</text>
<text x="145" y="280" font-size="10" letter-spacing="1.4" fill="#a89ce0">PEAK / DAY</text>
<text x="247" y="280" font-size="10" letter-spacing="1.4" fill="#a89ce0">ACTIVE DAYS</text>
<text x="60" y="315" font-size="25" font-weight="700" fill="#ede9fe">{total:,}</text>
<text x="145" y="315" font-size="25" font-weight="700" fill="#ede9fe">{peak}</text>
<text x="247" y="315" font-size="25" font-weight="700" fill="#ede9fe">{active}</text>
<text x="60" y="372" font-size="11" fill="#8b7fd4">@{safe_name} · updated daily</text>
{block_svg}
<text x="1140" y="393" text-anchor="end" font-size="10" letter-spacing="1" fill="#8b7fd4">ONE BLOCK · ONE DAY</text>
</g>
</svg>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--data-file", type=Path, help="Render a previously fetched calendar offline")
    parser.add_argument("--output", type=Path, default=Path("profile-3d-contrib/contributions.svg"))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", args.username):
        parser.error("Invalid GitHub username")
    calendar = json.loads(args.data_file.read_text(encoding="utf-8")) if args.data_file else fetch_calendar(args.username)
    svg = render_svg(args.username, calendar, datetime.now(timezone.utc).date())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(svg, encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(f"Generated {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
