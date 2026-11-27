#!/usr/bin/env python3
"""
cards.py - render GitHub stat, trophy and repo cards as SVGs. Stdlib only.

Replaces github-readme-stats / github-profile-trophy / streak-stats, which are
shared public instances that go down (503), run out of quota (402) or time out.
These are files in your own repo, so they render as long as GitHub renders.

    python scripts/cards.py --user gargibhardwaj24 --out assets

Writes <out>/card-stats-{dark,light}.svg, <out>/card-trophy-{dark,light}.svg
plus one card per repo listed in assets/projects.json, as
<out>/card-<repo>-{dark,light}.svg.

Star and fork counts come from the live API on every run. Descriptions come from
projects.json when set, otherwise the repo's own GitHub description.

A token in $GITHUB_TOKEN unlocks the contribution and streak numbers (they need
the GraphQL API). Without one the card still renders, minus those three tiles.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "cards.py"}

THEMES = {
    "dark": {
        "bg": "#0d1117", "border": "#30363d", "title": "#39d353",
        "text": "#c9d1d9", "muted": "#8b949e", "value": "#e6edf3",
        "accent": "#39d353",
    },
    "light": {
        "bg": "#ffffff", "border": "#d0d7de", "title": "#1a7f37",
        "text": "#1f2328", "muted": "#57606a", "value": "#1f2328",
        "accent": "#1a7f37",
    },
}

# GitHub linguist colours for the languages likely to show up here
LANG_COLOR = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5",
    "HTML": "#e34c26", "CSS": "#563d7c", "C++": "#f34b7d", "C": "#555555",
    "Java": "#b07219", "Go": "#00ADD8", "Rust": "#dea584", "Shell": "#89e051",
    "PLpgSQL": "#336790", "Vue": "#41b883", "Ruby": "#701516", "PHP": "#4F5D95",
    "Jupyter Notebook": "#DA5B0B", "SCSS": "#c6538c", "Svelte": "#ff3e00",
}

FONT = "ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"

# Octicon outlines, drawn on a 16x16 grid. These are paths rather than the
# characters U+2605 / U+2442 because those codepoints are missing from a lot of
# system fonts and fall back to a tofu box.
ICON_STAR = ("M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 "
             "2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 "
             "01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25z")
ICON_FORK = ("M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75v-.878a2.25 2.25 0 "
             "111.5 0v.878a2.25 2.25 0 01-2.25 2.25h-1.5v2.128a2.251 2.251 0 11-1.5 "
             "0V8.5h-1.5A2.25 2.25 0 013.5 6.25v-.878a2.25 2.25 0 111.5 0zM5 3.25a.75.75 0 "
             "10-1.5 0 .75.75 0 001.5 0zm6.75.75a.75.75 0 100-1.5.75.75 0 000 1.5zm-3 "
             "8.75a.75.75 0 100-1.5.75.75 0 000 1.5z")
ICON_REPO = ("M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 "
             "0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 "
             "012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 "
             "12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 "
             "00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z")
ICON_COMMIT = ("M11.93 7.75a4.002 4.002 0 01-7.86 0H.75a.75.75 0 010-1.5h3.32a4.002 4.002 0 "
               "017.86 0h3.32a.75.75 0 010 1.5h-3.32zM8 9.5a2 2 0 100-4 2 2 0 000 4z")
ICON_PR = ("M1.5 3.25a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 "
           "011.5 3.25zm5.677-.177L9.573.677A.25.25 0 0110 .854V2.5h1A2.5 2.5 0 0113.5 5v5.628a2.251 "
           "2.251 0 11-1.5 0V5a1 1 0 00-1-1h-1v1.646a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 "
           "010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm0 9.5a.75.75 0 100 1.5.75.75 0 "
           "000-1.5zm8.25.75a.75.75 0 101.5 0 .75.75 0 00-1.5 0z")
ICON_ISSUE = ("M8 9.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM8 0a8 8 0 100 16A8 8 0 008 0zM1.5 8a6.5 "
              "6.5 0 1113 0 6.5 6.5 0 01-13 0z")
ICON_PEOPLE = ("M5.25 3.5a2 2 0 100 4 2 2 0 000-4zM1.75 5.5a3.5 3.5 0 117 0 3.5 3.5 0 01-7 "
               "0zM5.25 8.5c-2.35 0-4.25 1.68-4.25 3.75V15h1.5v-2.75c0-1.24 1.23-2.25 2.75-2.25s2.75 "
               "1.01 2.75 2.25V15h1.5v-2.75c0-2.07-1.9-3.75-4.25-3.75z")


def icon(path, x, y, size, fill):
    s = size / 16
    return (f'<path transform="translate({x:.1f},{y:.1f}) scale({s:.3f})" '
            f'fill="{fill}" d="{path}"/>')


# --------------------------------------------------------------------------- #
# api
# --------------------------------------------------------------------------- #


def rest(path: str, token: str | None):
    req = urllib.request.Request("https://api.github.com" + path, headers=dict(UA))
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def graphql(query: str, variables: dict, token: str):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={**UA, "Content-Type": "application/json",
                                          "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


TROPHY_QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      totalCommitContributions
      restrictedContributionsCount
    }
    pullRequests(first:1){ totalCount }
    issues(first:1){ totalCount }
  }
}
"""

CONTRIB_QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount } }
      }
    }
  }
}
"""


def fetch_contributions(user: str, token: str | None):
    """Return (total, current_streak, longest_streak) or None without a token."""
    if not token:
        return None
    try:
        data = graphql(CONTRIB_QUERY, {"login": user}, token)
    except urllib.error.HTTPError as e:
        print(f"  contributions unavailable (HTTP {e.code})", file=sys.stderr)
        return None
    if data.get("errors"):
        print(f"  contributions unavailable: {data['errors'][0].get('message')}",
              file=sys.stderr)
        return None

    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(dt.date.fromisoformat(d["date"]), d["contributionCount"])
            for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort()

    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)

    # Today counts only if it already has activity; an empty today does not
    # break a streak that was alive yesterday.
    current = 0
    for date, c in reversed(days):
        if c > 0:
            current += 1
        elif date != days[-1][0]:
            break
    return cal["totalContributions"], current, longest


def fetch_trophy_counts(user: str, token: str | None):
    """Return {Commits, Pull requests, Issues}, or None if GitHub says nothing.

    GraphQL gives exact totals with a token; the search API covers the case
    where the token is missing or GraphQL rejects the query.
    """
    if token:
        try:
            data = graphql(TROPHY_QUERY, {"login": user}, token)
        except urllib.error.HTTPError as e:
            print(f"  trophy counts via GraphQL failed (HTTP {e.code})",
                  file=sys.stderr)
        else:
            if data.get("errors"):
                print(f"  trophy counts via GraphQL failed: "
                      f"{data['errors'][0].get('message')}", file=sys.stderr)
            else:
                u = data["data"]["user"]
                coll = u["contributionsCollection"]
                return {
                    "Commits": (coll["totalCommitContributions"]
                                + coll["restrictedContributionsCount"]),
                    "Pull requests": u["pullRequests"]["totalCount"],
                    "Issues": u["issues"]["totalCount"],
                }

    counts = {}
    for label, kind, query in (
        ("Commits", "commits", f"author:{user}"),
        ("Pull requests", "issues", f"author:{user} type:pr"),
        ("Issues", "issues", f"author:{user} type:issue"),
    ):
        total = search_count(kind, query, token)
        if total is not None:
            counts[label] = total
    return counts or None


def search_count(kind: str, query: str, token: str | None):
    """Hit count from the search API, which also works unauthenticated."""
    try:
        data = rest(f"/search/{kind}?q={urllib.parse.quote(query)}&per_page=1",
                    token)
    except urllib.error.HTTPError as e:
        print(f"  search/{kind} failed (HTTP {e.code})", file=sys.stderr)
        return None
    return data.get("total_count")


# --------------------------------------------------------------------------- #
# svg helpers
# --------------------------------------------------------------------------- #


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def text_width(s: str, size: float) -> float:
    return len(s) * size * 0.53


def wrap(text: str, size: float, max_w: float, max_lines: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if text_width(trial, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and words:
        # did everything fit?
        used = len(" ".join(lines).split())
        if used < len(words):
            while lines and text_width(lines[-1] + "…", size) > max_w:
                lines[-1] = lines[-1].rsplit(" ", 1)[0]
            lines[-1] += "…"
    return lines


def frame(w, h, c, body, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{esc(label)}" '
        f'font-family="{FONT}">'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" '
        f'fill="{c["bg"]}" stroke="{c["border"]}"/>'
        f"{body}</svg>"
    )


# --------------------------------------------------------------------------- #
# cards
# --------------------------------------------------------------------------- #


def render_stats(user, stats, theme):
    c = THEMES[theme]
    pad = 22
    tiles = [(v, k) for k, v in stats]
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    # Height follows the tile count, so the card does not leave a dead band when
    # the contribution tiles are unavailable. Measured off the last row's label
    # baseline rather than a nominal row height.
    rh, W = 46, 480
    H = pad + 52 + (rows - 1) * rh + 17 + pad
    tw = (W - 2 * pad) / cols

    out = [
        f'<text x="{pad}" y="{pad + 14}" font-size="15" font-weight="700" '
        f'fill="{c["title"]}">{esc(user)}</text>',
        f'<text x="{W - pad}" y="{pad + 14}" font-size="11" text-anchor="end" '
        f'fill="{c["muted"]}">at a glance</text>',
        f'<line x1="{pad}" y1="{pad + 26}" x2="{W - pad}" y2="{pad + 26}" '
        f'stroke="{c["border"]}"/>',
    ]
    top = pad + 52
    for i, (value, label) in enumerate(tiles):
        cx = pad + (i % cols) * tw
        cy = top + (i // cols) * rh
        out.append(
            f'<text x="{cx:.0f}" y="{cy:.0f}" font-size="23" font-weight="700" '
            f'fill="{c["value"]}">{esc(value)}</text>'
        )
        out.append(
            f'<text x="{cx:.0f}" y="{cy + 17:.0f}" font-size="10.5" '
            f'fill="{c["muted"]}">{esc(label)}</text>'
        )
    return frame(W, H, c, "".join(out), f"{user} GitHub statistics")


RANKS = ["C", "B", "A", "S", "SS", "SSS"]

# (label, icon, value needed for each rank in RANKS order). Thresholds are the
# same shape ryo-ma/github-profile-trophy uses, so the badges read the same way.
TROPHIES = [
    ("Commits", ICON_COMMIT, (1, 50, 200, 500, 1000, 2000)),
    ("Pull requests", ICON_PR, (1, 5, 20, 50, 100, 200)),
    ("Issues", ICON_ISSUE, (1, 5, 20, 50, 100, 200)),
    ("Stars", ICON_STAR, (1, 10, 50, 100, 500, 1000)),
    ("Followers", ICON_PEOPLE, (1, 5, 20, 50, 200, 500)),
    ("Repositories", ICON_REPO, (1, 5, 10, 20, 50, 100)),
]

RANK_COLOR = {
    "dark": {"SSS": "#e3b341", "SS": "#a371f7", "S": "#f0883e",
             "A": "#39d353", "B": "#58a6ff", "C": "#8b949e", "?": "#6e7681"},
    "light": {"SSS": "#9a6700", "SS": "#8250df", "S": "#bc4c00",
              "A": "#1a7f37", "B": "#0969da", "C": "#57606a", "?": "#8c959f"},
}

PANEL = {"dark": "#161b22", "light": "#f6f8fa"}


def rank_for(value: int, thresholds) -> str:
    rank = "?"
    for need, name in zip(thresholds, RANKS):
        if value >= need:
            rank = name
    return rank


def short(value: int) -> str:
    return f"{value / 1000:.1f}k" if value >= 1000 else f"{value:,}"


def render_trophies(user, values, theme):
    c = THEMES[theme]
    pad, gap, pw, ph = 14, 14, 118, 124
    items = [(label, icon_path, values[label]) for label, icon_path, _ in TROPHIES
             if label in values]
    W = 2 * pad + len(items) * pw + (len(items) - 1) * gap
    H = 2 * pad + ph

    out = []
    for i, (label, icon_path, value) in enumerate(items):
        threshold = next(t for l, _, t in TROPHIES if l == label)
        rank = rank_for(value, threshold)
        x, y = pad + i * (pw + gap), pad
        out.append(
            f'<rect x="{x}" y="{y}" width="{pw}" height="{ph}" rx="10" '
            f'fill="{PANEL[theme]}" stroke="{c["border"]}"/>'
        )
        out.append(icon(icon_path, x + 14, y + 14, 16, c["muted"]))
        out.append(
            f'<text x="{x + pw - 14}" y="{y + 28}" font-size="17" '
            f'font-weight="700" text-anchor="end" fill="{RANK_COLOR[theme][rank]}">'
            f'{rank}</text>'
        )
        out.append(
            f'<text x="{x + 14}" y="{y + 80}" font-size="24" font-weight="700" '
            f'fill="{c["value"]}">{esc(short(value))}</text>'
        )
        out.append(
            f'<text x="{x + 14}" y="{y + 100}" font-size="11" '
            f'fill="{c["muted"]}">{esc(label)}</text>'
        )
    return frame(W, H, c, "".join(out), f"{user} GitHub trophies")


def render_repo(repo, theme):
    c = THEMES[theme]
    W, H = 420, 132
    pad = 18
    out = []

    out.append(icon(ICON_REPO, pad, pad, 15, c["muted"]))
    out.append(
        f'<text x="{pad + 22}" y="{pad + 12}" font-size="14.5" font-weight="700" '
        f'fill="{c["title"]}">{esc(repo["name"])}</text>'
    )

    desc = repo.get("description") or "No description yet."
    for i, line in enumerate(wrap(desc, 11.5, W - 2 * pad, 3)):
        out.append(
            f'<text x="{pad}" y="{pad + 36 + i * 16}" font-size="11.5" '
            f'fill="{c["text"]}">{esc(line)}</text>'
        )

    fy = H - pad - 2
    x = pad
    if repo.get("language"):
        col = LANG_COLOR.get(repo["language"], c["muted"])
        out.append(f'<circle cx="{x + 5}" cy="{fy - 4}" r="5" fill="{col}"/>')
        out.append(
            f'<text x="{x + 15}" y="{fy}" font-size="11" fill="{c["muted"]}">'
            f'{esc(repo["language"])}</text>'
        )
        x += 15 + text_width(repo["language"], 11) + 18

    for path, count in ((ICON_STAR, repo.get("stars", 0)),
                        (ICON_FORK, repo.get("forks", 0))):
        out.append(icon(path, x, fy - 11, 12, c["muted"]))
        out.append(
            f'<text x="{x + 17}" y="{fy}" font-size="11" fill="{c["muted"]}">'
            f'{count}</text>'
        )
        x += 17 + text_width(str(count), 11) + 18

    return frame(W, H, c, "".join(out), f'{repo["name"]} repository card')


# --------------------------------------------------------------------------- #


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--user", required=True)
    p.add_argument("--out", type=Path, default=Path("assets"))
    p.add_argument("--projects", type=Path, default=Path("assets/projects.json"),
                   help="repos to render cards for, with description overrides")
    args = p.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    args.out.mkdir(parents=True, exist_ok=True)

    user = rest(f"/users/{args.user}", token)
    repos = []
    page = 1
    while True:
        batch = rest(f"/users/{args.user}/repos?per_page=100&page={page}&type=owner", token)
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    owned = [r for r in repos if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in owned)

    tiles = [("Total stars", f"{stars:,}"),
             ("Public repos", f"{user['public_repos']:,}"),
             ("Followers", f"{user['followers']:,}")]

    contrib = fetch_contributions(args.user, token)
    if contrib:
        total, current, longest = contrib
        tiles += [("Contributions (1y)", f"{total:,}"),
                  ("Current streak", f"{current:,}"),
                  ("Longest streak", f"{longest:,}")]
    else:
        print("  note: no usable token, skipping contribution tiles", file=sys.stderr)

    for theme in ("dark", "light"):
        dest = args.out / f"card-stats-{theme}.svg"
        dest.write_text(render_stats(args.user, tiles, theme), encoding="utf-8")
    print(f"wrote card-stats-*.svg  ({len(tiles)} tiles)")

    trophy_values = {"Stars": stars,
                     "Followers": user["followers"],
                     "Repositories": user["public_repos"]}
    counts = fetch_trophy_counts(args.user, token)
    if counts:
        trophy_values.update(counts)
    else:
        print("  note: no trophy counts available, showing the rest",
              file=sys.stderr)
    for theme in ("dark", "light"):
        dest = args.out / f"card-trophy-{theme}.svg"
        dest.write_text(render_trophies(args.user, trophy_values, theme),
                        encoding="utf-8")
    print(f"wrote card-trophy-*.svg  ({len(trophy_values)} trophies)")

    if not args.projects.exists():
        print(f"no {args.projects}, skipping repo cards")
        return
    wanted = json.loads(args.projects.read_text(encoding="utf-8"))["projects"]
    by_name = {r["name"].lower(): r for r in repos}

    for entry in wanted:
        src = by_name.get(entry["repo"].lower())
        if not src:
            print(f"  !! {entry['repo']} not found on the account, skipped")
            continue
        card = {
            "name": src["name"],
            "description": entry.get("description") or src.get("description"),
            "language": entry.get("language") or src.get("language"),
            "stars": src["stargazers_count"],
            "forks": src["forks_count"],
        }
        for theme in ("dark", "light"):
            dest = args.out / f"card-{src['name']}-{theme}.svg"
            dest.write_text(render_repo(card, theme), encoding="utf-8")
        print(f"wrote card-{src['name']}-*.svg  "
              f"({card['stars']}star {card['forks']}fork {card['language']})")


if __name__ == "__main__":
    main()
