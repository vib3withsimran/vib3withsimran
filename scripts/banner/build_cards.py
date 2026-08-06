#!/usr/bin/env python3
"""
Build stack.svg / projects.svg / connect.svg — terminal-style cards that
match the banner's visual language (see build_banner.py).

Derived artifacts — this script is the source of truth. Rebuild with:
    python scripts/banner/build_cards.py

Cards are fixed dark-navy (like the stats cards), no light variants needed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

try:
    from build_banner import MONO, THEMES, esc, leader_dots, mw
except ImportError:
    sys.path.insert(0, HERE)
    from build_banner import MONO, THEMES, esc, leader_dots, mw

T = THEMES["dark"]
MONO = MONO
PAD = 40

# ----------------------------------------------------------------- content
STACK = [
    ("LANG", ["C++", "TypeScript", "Python", "JavaScript", "Java", "C"]),
    ("FRONTEND", ["React", "Next.js", "React Native", "Bootstrap", "Chakra UI", "EJS"]),
    ("BACKEND", ["Node.js", "Express", "FastAPI", "JWT", "Supabase"]),
    ("DATABASE", ["MongoDB", "PostgreSQL", "MySQL"]),
    ("TOOLS", ["Git", "GitHub Actions", "Vercel", "Netlify", "Expo",
               "Postman", "OpenCV", "Figma"]),
]

PROJECTS = [
    ("StayHub", "property rental platform", ["node.js", "express", "mongodb", "ejs"]),
    ("ExplainLikeMyTeacher", "ai-powered learning assistant", ["typescript", "react native"]),
    ("SafeWalk", "community safety navigation", ["typescript"]),
    ("DocPulse-Intelligence", "document intelligence", ["python", "huggingface"]),
    ("Prompt-improver-extension", "chrome extension (mv3)", ["react", "typescript", "supabase"]),
]

LINKS = [
    ("MAIL", "mssimran093@gmail.com"),
    ("PORTFOLIO", "simran-os-portfolio.netlify.app"),
    ("LINKEDIN", "linkedin.com/in/mssimran"),
    ("GITHUB", "github.com/vib3withsimran"),
    ("X", "x.com/Simran142007"),
    ("INSTAGRAM", "instagram.com/vib3with.simran"),
]


def chrome(w, h, title):
    """Terminal chrome: titlebar, traffic lights, body, border."""
    A = []
    A.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
             f'viewBox="0 0 {w} {h}" role="img">')
    A.append(f"<title>{esc(title)}</title>")
    A.append(f'<rect x="8" y="8" width="{w - 16}" height="34" rx="10" '
             f'fill="{T["titlebar"]}"/>')
    A.append(f'<rect x="8" y="42" width="{w - 16}" height="{h - 50}" '
             f'fill="{T["body"]}"/>')
    A.append(f'<rect x="8" y="8" width="{w - 16}" height="{h - 16}" rx="10" '
             f'fill="none" stroke="{T["border"]}" stroke-width="1.5"/>')
    A.append(f'<rect x="8" y="42" width="{w - 16}" height="1" '
             f'fill="{T["titleline"]}"/>')
    for i, c in enumerate(T["traffic"]):
        A.append(f'<circle cx="{24 + i * 18}" cy="25" r="4.5" fill="{c}"/>')
    A.append(f'<text x="{w / 2}" y="28.5" text-anchor="middle" '
             f'font-family="{MONO}" font-size="13" fill="{T["title"]}">'
             f'{esc(title)}</text>')
    return A


def footer(A, w, h, cmd):
    """Prompt line + blinking cursor, matching the banner footer."""
    A.append(f'<text x="{PAD}" y="{h - 26}" font-family="{MONO}" font-size="13" '
             f'fill="{T["footer"]}">$ {esc(cmd)}</text>')
    fw = mw(cmd, 13) + 12
    A.append(f'<rect x="{PAD + fw}" y="{h - 40}" width="9" height="16" '
             f'fill="{T["cursor"]}">'
             f'<animate attributeName="opacity" dur="1.1s" repeatCount="indefinite" '
             f'values="1;1;0;0;1" keyTimes="0;0.05;0.5;0.55;1"/></rect>')


def value_line(A, x, y, items, sep_fill=None, size=14):
    """Emit `a · b · c` with separators in a dim colour via tspans."""
    if sep_fill is None:
        sep_fill = T["section"]
    A.append(f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="{size}" '
             f'fill="{T["value"]}">')
    for i, item in enumerate(items):
        if i > 0:
            A.append(f'<tspan fill="{sep_fill}"> · </tspan>')
        A.append(f"<tspan>{esc(item)}</tspan>")
    A.append("</text>")


# ------------------------------------------------------------------ stack
def build_stack():
    w, h = 1000, 420
    A = chrome(w, h, "stack.sh --core")
    # prompt at top
    A.append(f'<text x="{PAD}" y="78" font-family="{MONO}" font-size="13" '
             f'fill="{T["footer"]}">$ ./stack.sh --core</text>')
    y = 116
    for sec, items in STACK:
        A.append(f'<text x="{PAD}" y="{y}" font-family="{MONO}" font-size="12" '
                 f'fill="{T["section"]}" letter-spacing="3">-- {esc(sec)} --</text>')
        value_line(A, PAD, y + 28, items)
        y += 62
    footer(A, w, h, "./stack.sh --core")
    A.append("</svg>")
    svg = "".join(A)
    out = os.path.join(ROOT, "stack.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"[stack] wrote {out} ({os.path.getsize(out) / 1024:.0f} KB)")


# --------------------------------------------------------------- projects
def build_projects():
    w, h = 1000, 440
    A = chrome(w, h, "projects.sh --featured")
    A.append(f'<text x="{PAD}" y="78" font-family="{MONO}" font-size="13" '
             f'fill="{T["footer"]}">$ ./projects.sh --featured</text>')
    y = 118
    for i, (name, desc, stack) in enumerate(PROJECTS, 1):
        nw = mw(f"[{i}] {name}", 14)
        dw = mw(desc, 13)
        lx0 = PAD + nw + 14.0
        lx1 = w - PAD - dw - 14.0
        A.append(f'<g shape-rendering="crispEdges" fill="{T["chrome"]}" '
                 f'fill-opacity="{T["leader_op"]}">'
                 f'<path d="{leader_dots(lx0, lx1, y - 5)}"/></g>')
        A.append(f'<text x="{PAD}" y="{y}" font-family="{MONO}" font-size="14" '
                 f'fill="{T["label_lav"]}">'
                 f'<tspan fill="{T["chrome"]}">[{i}]</tspan> '
                 f'<tspan>{esc(name)}</tspan></text>')
        A.append(f'<text x="{w - PAD}" y="{y}" text-anchor="end" '
                 f'font-family="{MONO}" font-size="13" fill="{T["label"]}">'
                 f'{esc(desc)}</text>')
        value_line(A, PAD + 20, y + 24, stack, size=12)
        y += 62
    footer(A, w, h, "./projects.sh --featured")
    A.append("</svg>")
    svg = "".join(A)
    out = os.path.join(ROOT, "projects.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"[projects] wrote {out} ({os.path.getsize(out) / 1024:.0f} KB)")


# ---------------------------------------------------------------- connect
def build_connect():
    w, h = 1000, 380
    A = chrome(w, h, "connect.sh --links")
    A.append(f'<text x="{PAD}" y="78" font-family="{MONO}" font-size="13" '
             f'fill="{T["footer"]}">$ ./connect.sh --links</text>')
    y = 120
    for label, value in LINKS:
        lw = mw(label, 14)
        vw = mw(value, 14)
        lx0 = PAD + lw + 14.0
        lx1 = w - PAD - vw - 14.0
        A.append(f'<g shape-rendering="crispEdges" fill="{T["chrome"]}" '
                 f'fill-opacity="{T["leader_op"]}">'
                 f'<path d="{leader_dots(lx0, lx1, y - 5)}"/></g>')
        A.append(f'<text x="{PAD}" y="{y}" font-family="{MONO}" font-size="14" '
                 f'fill="{T["label_lav"]}" textLength="{lw:.1f}" '
                 f'lengthAdjust="spacingAndGlyphs">{esc(label)}</text>')
        A.append(f'<text x="{w - PAD}" y="{y}" text-anchor="end" '
                 f'font-family="{MONO}" font-size="14" fill="{T["value"]}" '
                 f'textLength="{vw:.1f}" '
                 f'lengthAdjust="spacingAndGlyphs">{esc(value)}</text>')
        y += 32
    footer(A, w, h, "./connect.sh --links")
    A.append("</svg>")
    svg = "".join(A)
    out = os.path.join(ROOT, "connect.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"[connect] wrote {out} ({os.path.getsize(out) / 1024:.0f} KB)")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "stack"):
        build_stack()
    if which in ("all", "projects"):
        build_projects()
    if which in ("all", "connect"):
        build_connect()
