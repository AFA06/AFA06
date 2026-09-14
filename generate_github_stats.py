#!/usr/bin/env python3

import datetime as dt
import html
import json
import os
import urllib.request


USERNAME = "AFA06"
GRAPHQL_URL = "https://api.github.com/graphql"

BG = "#0d1117"
CARD = "#161b22"
BORDER = "#30363d"
TEXT = "#f0f6fc"
MUTED = "#8b949e"
GREEN = "#39d353"
GREEN_DARK = "#0e4429"
BLUE = "#58a6ff"
PURPLE = "#a371f7"


def github_graphql(query):
    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        raise RuntimeError("GITHUB_TOKEN environment variable is missing.")

    payload = json.dumps({"query": query}).encode("utf-8")

    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "AFA06-github-stats",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    if "errors" in data:
        raise RuntimeError(json.dumps(data["errors"], indent=2))

    return data["data"]


def get_contribution_data():
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=364)

    query = f"""
    query {{
      viewer {{
        login
        name
        followers {{
          totalCount
        }}
        repositories(first: 1, ownerAffiliations: OWNER) {{
          totalCount
        }}
        contributionsCollection(
          from: "{start.isoformat()}T00:00:00Z"
          to: "{today.isoformat()}T23:59:59Z"
        ) {{
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          totalRepositoriesWithContributedCommits
          restrictedContributionsCount
          contributionCalendar {{
            totalContributions
            weeks {{
              contributionDays {{
                date
                contributionCount
                color
                weekday
              }}
            }}
          }}
        }}
      }}
    }}
    """

    return github_graphql(query)


def flatten_days(calendar):
    days = []

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append(day)

    days.sort(key=lambda item: item["date"])

    return days


def calculate_streaks(days):
    contribution_dates = {
        dt.date.fromisoformat(day["date"])
        for day in days
        if day["contributionCount"] > 0
    }

    if not contribution_dates:
        return 0, 0

    today = dt.datetime.now(dt.timezone.utc).date()

    # A streak can end yesterday if today's contribution has not happened yet.
    if today in contribution_dates:
        current_end = today
    elif today - dt.timedelta(days=1) in contribution_dates:
        current_end = today - dt.timedelta(days=1)
    else:
        current_end = None

    current_streak = 0

    if current_end:
        cursor = current_end

        while cursor in contribution_dates:
            current_streak += 1
            cursor -= dt.timedelta(days=1)

    longest_streak = 0
    running = 0
    previous = None

    for contribution_date in sorted(contribution_dates):
        if previous is not None and contribution_date == previous + dt.timedelta(days=1):
            running += 1
        else:
            running = 1

        longest_streak = max(longest_streak, running)
        previous = contribution_date

    return current_streak, longest_streak


def svg_start(width, height):
    return f"""<svg xmlns="http://www.w3.org/2000/svg"
    width="{width}"
    height="{height}"
    viewBox="0 0 {width} {height}">
    <rect width="100%" height="100%" rx="18" fill="{BG}"/>
    """


def svg_end():
    return "</svg>\n"


def text(x, y, value, size=16, fill=TEXT, weight="400", anchor="start"):
    safe = html.escape(str(value))

    return (
        f'<text x="{x}" y="{y}" '
        f'fill="{fill}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif" '
        f'font-size="{size}px" font-weight="{weight}" text-anchor="{anchor}">'
        f"{safe}</text>"
    )


def rounded_rect(x, y, width, height, fill=CARD, stroke=BORDER, radius=14):
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="{radius}" fill="{fill}" stroke="{stroke}"/>'
    )


def generate_stats_svg(stats):
    svg = svg_start(900, 250)

    svg += text(32, 40, "GitHub Activity", 24, TEXT, "700")
    svg += text(
        32,
        65,
        "AFA06 · automatically generated from GitHub",
        13,
        MUTED,
    )

    cards = [
        ("Contributions", stats["total_contributions"], GREEN),
        ("Repositories", stats["repositories"], BLUE),
        ("Followers", stats["followers"], PURPLE),
        ("Contributed Repos", stats["contributed_repos"], "#f0883e"),
    ]

    x_positions = [32, 248, 464, 680]

    for (label, value, accent), x in zip(cards, x_positions):
        svg += rounded_rect(x, 95, 188, 112)
        svg += text(x + 18, 128, label, 14, MUTED)
        svg += text(x + 18, 174, f"{value:,}", 31, accent, "700")

    svg += text(
        32,
        232,
        "Last 365 days · commits · issues · pull requests · reviews",
        12,
        MUTED,
    )

    svg += svg_end()

    return svg


def generate_streak_svg(current_streak, longest_streak):
    svg = svg_start(900, 230)

    svg += text(32, 40, "Contribution Streak", 24, TEXT, "700")
    svg += text(
        32,
        65,
        "Calculated from GitHub's contribution calendar",
        13,
        MUTED,
    )

    svg += rounded_rect(32, 95, 404, 100)
    svg += rounded_rect(464, 95, 404, 100)

    svg += text(55, 128, "Current Streak", 14, MUTED)
    svg += text(55, 174, f"{current_streak} days", 32, GREEN, "700")

    svg += text(487, 128, "Longest Streak", 14, MUTED)
    svg += text(487, 174, f"{longest_streak} days", 32, BLUE, "700")

    svg += svg_end()

    return svg


def generate_contributions_svg(days):
    svg = svg_start(900, 285)

    svg += text(32, 38, "Contribution Activity", 24, TEXT, "700")
    svg += text(
        32,
        63,
        "Last 365 days · generated automatically by GitHub Actions",
        13,
        MUTED,
    )

    # Build a complete 53-week calendar.
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=364)

    # Move to Sunday to make a conventional GitHub-style grid.
    grid_start = start - dt.timedelta(days=(start.weekday() + 1) % 7)

    day_map = {
        dt.date.fromisoformat(day["date"]): day["contributionCount"]
        for day in days
    }

    cell = 11
    gap = 3
    step = cell + gap

    x0 = 42
    y0 = 88

    for column in range(53):
        for row in range(7):
            current = grid_start + dt.timedelta(
                days=column * 7 + row
            )

            if current < start or current > today:
                continue

            count = day_map.get(current, 0)

            if count == 0:
                fill = "#161b22"
            elif count == 1:
                fill = "#0e4429"
            elif count <= 3:
                fill = "#006d32"
            elif count <= 6:
                fill = "#26a641"
            else:
                fill = "#39d353"

            x = x0 + column * step
            y = y0 + row * step

            svg += (
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'rx="2" fill="{fill}" stroke="{BORDER}" stroke-width="0.3">'
                f"<title>{current.isoformat()}: {count} contributions</title>"
                f"</rect>"
            )

    svg += text(42, 205, "Less", 11, MUTED)

    legend = [
        "#161b22",
        "#0e4429",
        "#006d32",
        "#26a641",
        "#39d353",
    ]

    for index, color in enumerate(legend):
        x = 72 + index * 18

        svg += (
            f'<rect x="{x}" y="196" width="12" height="12" '
            f'rx="2" fill="{color}"/>'
        )

    svg += text(
        180,
        205,
        "More",
        11,
        MUTED,
    )

    svg += svg_end()

    return svg


def main():
    data = get_contribution_data()

    viewer = data["viewer"]
    collection = viewer["contributionsCollection"]
    calendar = collection["contributionCalendar"]

    days = flatten_days(calendar)

    current_streak, longest_streak = calculate_streaks(days)

    stats = {
        "total_contributions": calendar["totalContributions"],
        "repositories": viewer["repositories"]["totalCount"],
        "followers": viewer["followers"]["totalCount"],
        "contributed_repos": collection["totalRepositoriesWithContributedCommits"],
    }

    os.makedirs("assets", exist_ok=True)

    with open("assets/github-stats.svg", "w", encoding="utf-8") as file:
        file.write(generate_stats_svg(stats))

    with open("assets/github-streak.svg", "w", encoding="utf-8") as file:
        file.write(generate_streak_svg(current_streak, longest_streak))

    with open(
        "assets/github-contributions.svg",
        "w",
        encoding="utf-8",
    ) as file:
        file.write(generate_contributions_svg(days))

    print("GitHub statistics generated successfully.")
    print(f"Total contributions: {stats['total_contributions']}")
    print(f"Current streak: {current_streak} days")
    print(f"Longest streak: {longest_streak} days")


if __name__ == "__main__":
    main()