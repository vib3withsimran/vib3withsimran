#!/usr/bin/env python3
"""
build_socials.py — terminal-style social links card (green GitHub theme).

    python scripts/build_socials.py

Writes connect.svg in the repo root.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MONO = "ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"
PAD = 40

# Green GitHub theme
T = {
    "bg": "#0d1117", "border": "#30363d", "titlebar": "#161b22",
    "titleline": "#21262d", "title": "#8b949e",
    "traffic": ("#ff5f57", "#febc2e", "#28c840"),
    "label": "#39d353", "value": "#c9d1d9", "leader": "#21262d",
    "footer": "#8b949e", "cursor": "#39d353",
}

LINKS = [
    ("GITHUB", "github.com/vib3withsimran"),
    ("LINKEDIN", "linkedin.com/in/mssimran"),
    ("PORTFOLIO", "simran-os-portfolio.netlify.app"),
    ("MAIL", "mssimran093@gmail.com"),
    ("X", "x.com/Simran142007"),
    ("INSTAGRAM", "instagram.com/vib3with.simran"),
]


def mw(s, size):
    return len(s) * 0.6 * size


def leader_dots(x0, x1, y, step=16):
    pts = []
    x = x0
    while x <= x1:
        pts.append("M%d,%dh2v2h-2z" % (int(x), int(y)))
        x += step
    return "".join(pts)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build():
    w, h = 1000, 340
    A = []

    # svg + title
    A.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
             f'viewBox="0 0 {w} {h}" role="img" aria-label="social links">')
    A.append("<title>connect.sh --links</title>")

    # terminal chrome
    A.append(f'<rect x="8" y="8" width="{w - 16}" height="34" rx="10" fill="{T["titlebar"]}"/>')
    A.append(f'<rect x="8" y="42" width="{w - 16}" height="{h - 50}" fill="{T["bg"]}"/>')
    A.append(f'<rect x="8" y="8" width="{w - 16}" height="{h - 16}" rx="10" '
             f'fill="none" stroke="{T["border"]}" stroke-width="1.5"/>')
    A.append(f'<rect x="8" y="42" width="{w - 16}" height="1" fill="{T["titleline"]}"/>')
    for i, c in enumerate(T["traffic"]):
        A.append(f'<circle cx="{24 + i * 18}" cy="25" r="4.5" fill="{c}"/>')
    A.append(f'<text x="{w / 2}" y="28.5" text-anchor="middle" '
             f'font-family="{MONO}" font-size="13" fill="{T["title"]}">'
             f'connect.sh --links</text>')

    # prompt line
    A.append(f'<text x="{PAD}" y="78" font-family="{MONO}" font-size="13" '
             f'fill="{T["footer"]}">$ ./connect.sh --links</text>')

    # link rows with dotted leaders
    y = 120
    for label, value in LINKS:
        lw = mw(label, 14)
        vw = mw(value, 14)
        lx0 = PAD + lw + 14.0
        lx1 = w - PAD - vw - 14.0
        A.append(f'<g shape-rendering="crispEdges" fill="{T["leader"]}" '
                 f'fill-opacity="0.6">'
                 f'<path d="{leader_dots(lx0, lx1, y - 5)}"/></g>')
        A.append(f'<text x="{PAD}" y="{y}" font-family="{MONO}" font-size="14" '
                 f'fill="{T["label"]}" textLength="{lw:.1f}" '
                 f'lengthAdjust="spacingAndGlyphs">{esc(label)}</text>')
        A.append(f'<text x="{w - PAD}" y="{y}" text-anchor="end" '
                 f'font-family="{MONO}" font-size="14" fill="{T["value"]}" '
                 f'textLength="{vw:.1f}" '
                 f'lengthAdjust="spacingAndGlyphs">{esc(value)}</text>')
        y += 32

    # footer prompt + blinking cursor
    A.append(f'<text x="{PAD}" y="{h - 26}" font-family="{MONO}" font-size="13" '
             f'fill="{T["footer"]}">$ ./connect.sh --links</text>')
    cmd = "./connect.sh --links"
    fw = mw(cmd, 13) + 12
    A.append(f'<rect x="{PAD + fw}" y="{h - 40}" width="9" height="16" '
             f'fill="{T["cursor"]}">'
             f'<animate attributeName="opacity" dur="1.1s" repeatCount="indefinite" '
             f'values="1;1;0;0;1" keyTimes="0;0.05;0.5;0.55;1"/></rect>')

    A.append("</svg>")

    svg = "".join(A)
    out = os.path.join(ROOT, "connect.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {out}  ({os.path.getsize(out) / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
