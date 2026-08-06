#!/usr/bin/env python3
"""
Build dark.svg / light.svg from data/banner_data.npz.

Derived artifact — the .npz + scripts/banner/datagen.py are the source of
truth. Rebuild with:  python scripts/banner/build_banner.py [dark|light|all]

Timeline (all in seconds):
  intro (once) : 0..3.2  60 random interleaved groups shimmer in (~2s),
                 crossfade to the loop layer at 3.2-3.5
  loop (14.2s, begins 3.2s):
      0.0-3.0  portrait hold  (bands drift ~42% toward the first-logo
               centroid while dipping in opacity, staggered, then return)
      3.0-4.3  transition: portrait fades out, travellers fade in
      4.3-6.3  logo 1 (Next)
      6.3-7.6  morph
      7.6-9.6  logo 2 (</>)
      9.6-10.9 morph
     10.9-12.9 logo 3 (Vercel)
     12.9-14.2 transition back (portrait fades in, travellers out)
"""
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data", "banner_data.npz")
OUTDIR = ROOT

# Timing is derived from these constants (user asked for slower logo holds)
PORTRAIT_HOLD = 3.0
TRANS = 1.3                 # transition between phases
LOGO_HOLD = 4.0             # each logo shown 2s longer than the original spec
LOOP = PORTRAIT_HOLD + 4 * TRANS + 3 * LOGO_HOLD   # 20.2s
BEGIN = 3.2
# phase fractions of the loop
F_HOLD_OUT = PORTRAIT_HOLD / LOOP
F_TRANS_OUT = (PORTRAIT_HOLD + TRANS) / LOOP
F_L1_END = (PORTRAIT_HOLD + TRANS + LOGO_HOLD) / LOOP
F_M12_END = (PORTRAIT_HOLD + 2 * TRANS + LOGO_HOLD) / LOOP
F_L2_END = (PORTRAIT_HOLD + 2 * TRANS + 2 * LOGO_HOLD) / LOOP
F_M23_END = (PORTRAIT_HOLD + 3 * TRANS + 2 * LOGO_HOLD) / LOOP
F_L3_END = (PORTRAIT_HOLD + 3 * TRANS + 3 * LOGO_HOLD) / LOOP
F_RET_END = 1.0

MONO = "Consolas,'Cascadia Mono',Menlo,'DejaVu Sans Mono',monospace"

# ------------------------------------------------------------------ themes
THEMES = {
    "dark": dict(
        bg="#0A101F", body="#0A101F", panel="#0D1428", titlebar="#0C1322",
        titleline="#1E2C4C", border="#223052",
        traffic=("#FF5F57", "#FEBC2E", "#28C840"),
        title="#8FA3C8", frame_stroke="#A78BFA", frame_stroke_op="0.35",
        label_lav="#A78BFA", chrome="#22D3EE", chrome_dim="#7DD3FC",
        label="#7E8FB5", value="#D3DDF2", section="#55648C",
        leader_op="0.35", dots="#A78BFA",
        live_dot="#F43F5E", live_text="#F87171",
        pill=("#A78BFA", "#22D3EE"), pill_text="#0A101F",
        footer="#44537A", cursor="#22D3EE",
    ),
    "light": dict(
        bg="#EEF2FA", body="#EEF2FA", panel="#F7F9FE", titlebar="#E6EBF6",
        titleline="#D7DFF0", border="#C4CFE4",
        traffic=("#F87171", "#FBBF24", "#34D399"),
        title="#4A5B80", frame_stroke="#4C1D95", frame_stroke_op="0.30",
        label_lav="#4C1D95", chrome="#0E7490", chrome_dim="#155E75",
        label="#5A6B8E", value="#24324F", section="#9AA7C6",
        leader_op="0.45", dots="#4C1D95",
        live_dot="#DC2626", live_text="#B91C1C",
        pill=("#8B5CF6", "#06B6D4"), pill_text="#FFFFFF",
        footer="#8A97B8", cursor="#0E7490",
    ),
}

# ----------------------------------------------------------------- content
ROWS = [
    ("Subject", "Simran Gupta"),
    ("Role", "Full Stack Developer"),
    ("Origin", "Delhi, India"),
    ("Education", "B.Tech"),
    ("Status", "building + learning + shipping"),
    ("ToolChain", "TS · JS · C++ · Python · Node · Next · Supabase · Vercel"),
]
CORE = [
    ("Core.Lang", "C++ · TypeScript · Python · JavaScript"),
    ("Core.Frontend", "React · Next.js · React Native"),
    ("Core.Backend", "Node.js · Express · FastAPI"),
    ("Core.Database", "MongoDB · PostgreSQL · MySQL"),
    ("Core.Infra", "Vercel · Supabase · GitHub Actions"),
]
GRID = [
    ("Grid.Mail", "mssimran093@gmail.com"),
    ("Grid.Portfolio", "simran-os-portfolio.netlify.app"),
    ("Grid.LinkedIn", "linkedin.com/in/mssimran"),
    ("Grid.GitHub", "github.com/vib3withsimran"),
]

X0, X1 = 520.0, 1140.0        # label start / value right margin
LEADER_STEP = 16.0


def mw(s, size):
    return len(s) * 0.6 * size


# ----------------------------------------------------------------- helpers
def runs(xs, ys):
    """Consecutive dots in a row -> compact <path> h/v runs."""
    order = np.lexsort((xs, ys))
    parts = []
    i, n = 0, len(xs)
    while i < n:
        y = ys[order[i]]
        x = xs[order[i]]
        j = i
        while (j + 1 < n and ys[order[j + 1]] == y
               and xs[order[j + 1]] == xs[order[j]] + 1):
            j += 1
        length = j - i + 1
        if length == 1:
            parts.append("M%d,%dh1v1h-1z" % (x, y))
        else:
            parts.append("M%d,%dh%dv1h-%dz" % (x, y, length, length))
        i = j + 1
    return "".join(parts)


def leader_dots(x0, x1, y):
    """Dotted leaders computed from label/value width (never hand-edited)."""
    pts = []
    x = x0
    while x <= x1:
        pts.append("M%d,%dh2v2h-2z" % (int(x), int(y)))
        x += LEADER_STEP
    return "".join(pts)


def fmt(v):
    if abs(v) < 0.05:
        return "0"
    return ("%.1f" % v).rstrip("0").rstrip(".")


def kt(fracs):
    return ";".join("%.5f" % f for f in fracs)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(theme_name):
    t = THEMES[theme_name]
    d = np.load(DATA)
    dots = d["dark_dots"] if theme_name == "dark" else d["light_dots"]
    groups = d["dark_groups"] if theme_name == "dark" else d["light_groups"]
    bands = d["dark_bands"] if theme_name == "dark" else d["light_bands"]
    drift = d["dark_drift"] if theme_name == "dark" else d["light_drift"]
    logo1, logo2, logo3 = d["logo1"], d["logo2"], d["logo3"]
    p12, p23 = d["p12"], d["p23"]

    ys, xs = np.nonzero(dots)
    n = len(xs)
    ndots = n
    print(f"[{theme_name}] dots={n} groups={len(np.unique(groups))} "
          f"bands={len(np.unique(bands))}")

    out = []
    A = out.append
    A(f'<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="610" '
      f'viewBox="0 0 1180 610" role="img" '
      f'aria-label="Simran Gupta - full stack developer - animated profile banner">')
    A(f"<title>Simran Gupta — profile.sh --live</title>")
    A("<desc>Animated terminal-style profile banner: portrait, tech stack, "
      "morphing logos.</desc>")
    A("<defs>")
    A(f'<linearGradient id="pillGrad" x1="0" y1="0" x2="1" y2="1">'
      f'<stop offset="0" stop-color="{t["pill"][0]}"/>'
      f'<stop offset="1" stop-color="{t["pill"][1]}"/></linearGradient>')
    A("</defs>")

    # ---- terminal chrome ----
    A(f'<rect x="8" y="8" width="1164" height="34" rx="10" fill="{t["titlebar"]}"/>')
    A(f'<rect x="8" y="42" width="1164" height="560" fill="{t["body"]}"/>')
    A(f'<rect x="8" y="8" width="1164" height="594" rx="10" fill="none" '
      f'stroke="{t["border"]}" stroke-width="1.5"/>')
    A(f'<rect x="8" y="42" width="1164" height="1" fill="{t["titleline"]}"/>')
    for i, c in enumerate(t["traffic"]):
        A(f'<circle cx="{24 + i * 18}" cy="25" r="4.5" fill="{c}"/>')
    A(f'<text x="590" y="28.5" text-anchor="middle" font-family="{MONO}" '
      f'font-size="13" fill="{t["title"]}">profile.sh --live</text>')

    # ---- left: VISUAL.MAP frame ----
    A(f'<text x="40" y="58" font-family="{MONO}" font-size="12" '
      f'fill="{t["label_lav"]}" letter-spacing="3">VISUAL.MAP</text>')
    A(f'<rect x="40" y="70" width="450" height="510" rx="6" fill="{t["panel"]}" '
      f'stroke="{t["frame_stroke"]}" stroke-opacity="{t["frame_stroke_op"]}"/>')

    # ================= PORTRAIT =================
    # grid: 300x340 at scale 1.5 -> 450x510, crisp 1px cells
    dots_fill = t["dots"]

    # ---- intro layer (duplicate dot paths, 60 interleaved groups) ----
    A(f'<g id="intro" transform="translate(40 70) scale(1.5)" '
      f'shape-rendering="crispEdges" fill="{dots_fill}">')
    gidx = np.argsort(groups, kind="stable")
    gb = np.searchsorted(groups[gidx], np.arange(60))
    gb = np.append(gb, n)
    for g in range(60):
        sel = gidx[gb[g]:gb[g + 1]]
        if len(sel) == 0:
            continue
        dd = runs(xs[sel], ys[sel])
        begin = "%.2fs" % (g / 59.0 * 2.0)
        A(f'<g opacity="0"><path d="{dd}"/><animate attributeName="opacity" '
          f'begin="{begin}" dur="0.9s" from="0" to="1" fill="freeze"/></g>')
    A('<animate attributeName="opacity" dur="3.5s" keyTimes="0;0.914;1" '
      'values="1;1;0" fill="freeze"/>')
    A("</g>")

    # ---- main portrait layer: 94 drift bands (loop) ----
    A(f'<g transform="translate(40 70) scale(1.5)" '
      f'shape-rendering="crispEdges" fill="{dots_fill}" opacity="0">')
    nbands = int(d["meta"][3])
    bidx = np.argsort(bands, kind="stable")
    bb = np.searchsorted(bands[bidx], np.arange(nbands))
    bb = np.append(bb, n)
    for b in range(nbands):
        sel = bidx[bb[b]:bb[b + 1]]
        if len(sel) == 0:
            continue
        dx, dy = drift[b][0], drift[b][1]
        i = b / float(nbands)
        t_out = 2.4 + i * 1.9
        t_ret = (LOOP - 2.6) + i * 1.3
        k = kt([0, t_out / LOOP, (t_out + 1.3) / LOOP, t_ret / LOOP,
                (t_ret + 1.3) / LOOP, 1.0])
        tr = "0 0;0 0;%s %s;%s %s;0 0;0 0" % (fmt(dx), fmt(dy), fmt(dx), fmt(dy))
        dd = runs(xs[sel], ys[sel])
        A(f'<g><path d="{dd}"/>'
          f'<animateTransform attributeName="transform" type="translate" '
          f'begin="{BEGIN}s" dur="{LOOP}s" repeatCount="indefinite" '
          f'keyTimes="{k}" values="{tr}"/>'
          f'<animate attributeName="opacity" begin="{BEGIN}s" dur="{LOOP}s" '
          f'repeatCount="indefinite" keyTimes="{k}" '
          f'values="1;1;0.15;0.15;1;1"/></g>')
    kp = kt([0, F_HOLD_OUT, F_TRANS_OUT, F_L3_END, 1.0])
    A(f'<animate attributeName="opacity" begin="{BEGIN}s" dur="{LOOP}s" '
      f'repeatCount="indefinite" keyTimes="{kp}" values="1;1;0;0;1"/>')
    A("</g>")

    # ---- travellers: ~900 dots morphing between the three logos ----
    A(f'<g id="travellers" shape-rendering="crispEdges" fill="{dots_fill}" '
      f'opacity="0">')
    m2_of_i = p12                       # L2 target for traveller i
    m3_of_i = p23[p12]                  # L3 target for traveller i
    ktrav = kt([0, F_TRANS_OUT, F_L1_END, F_M12_END, F_L2_END, F_M23_END,
                F_L3_END, 1.0])
    for i in range(len(logo1)):
        x1, y1 = logo1[i]
        dx2 = logo2[m2_of_i[i]][0] - x1
        dy2 = logo2[m2_of_i[i]][1] - y1
        dx3 = logo3[m3_of_i[i]][0] - x1
        dy3 = logo3[m3_of_i[i]][1] - y1
        vals = ("0 0;0 0;%s %s;%s %s;%s %s;%s %s;0 0;0 0"
                % (fmt(dx2), fmt(dy2), fmt(dx2), fmt(dy2),
                   fmt(dx3), fmt(dy3), fmt(dx3), fmt(dy3)))
        A(f'<path d="M{int(x1)},{int(y1)}h5v5h-5z" transform="translate(0 0)">'
          f'<animateTransform attributeName="transform" type="translate" '
          f'begin="{BEGIN}s" dur="{LOOP}s" repeatCount="indefinite" '
          f'keyTimes="{ktrav}" values="{vals}"/></path>')
    kt2 = kt([0, F_HOLD_OUT, F_TRANS_OUT, F_L3_END, 1.0])
    A(f'<animate attributeName="opacity" begin="{BEGIN}s" dur="{LOOP}s" '
      f'repeatCount="indefinite" keyTimes="{kt2}" values="0;0;1;1;0"/>')
    A("</g>")

    # ================= SYSTEM.INFO panel =================
    A(f'<text x="520" y="58" font-family="{MONO}" font-size="13" font-weight="700" '
      f'fill="{t["chrome"]}" letter-spacing="3">SYSTEM.INFO</text>')

    # LIVE badge (pulsing)
    A(f'<g>'
      f'<rect x="902" y="45" width="74" height="26" rx="13" '
      f'fill="{t["live_dot"]}" fill-opacity="0.14" '
      f'stroke="{t["live_dot"]}" stroke-opacity="0.6" stroke-width="1"/>'
      f'<circle cx="915" cy="58" r="4" fill="{t["live_dot"]}"/>'
      f'<text x="925" y="61.5" font-family="{MONO}" font-size="12" '
      f'font-weight="700" fill="{t["live_text"]}">LIVE</text>'
      f'<animate attributeName="opacity" dur="1.4s" repeatCount="indefinite" '
      f'values="1;0.45;1" keyTimes="0;0.5;1"/></g>')

    # coloured pill with handle
    A(f'<rect x="988" y="44" width="152" height="28" rx="14" '
      f'fill="url(#pillGrad)"/>')
    A(f'<text x="1064" y="62.5" text-anchor="middle" font-family="{MONO}" '
      f'font-size="14" font-weight="700" fill="{t["pill_text"]}">'
      f'@vib3withsimran</text>')

    # ---- rows with dotted leaders ----
    def emit_row(label, value, y):
        lw = mw(label, 14)
        vw = mw(value, 14)
        lx0 = X0 + lw + 14.0
        lx1 = X1 - vw - 14.0
        A(f'<g shape-rendering="crispEdges" fill="{t["chrome"]}" '
          f'fill-opacity="{t["leader_op"]}">'
          f'<path d="{leader_dots(lx0, lx1, y - 5)}"/></g>')
        A(f'<text x="{X0}" y="{y}" font-family="{MONO}" font-size="14" '
          f'fill="{t["label"]}" textLength="{lw:.1f}" '
          f'lengthAdjust="spacingAndGlyphs">{esc(label)}</text>')
        A(f'<text x="{X1}" y="{y}" text-anchor="end" font-family="{MONO}" '
          f'font-size="14" fill="{t["value"]}" textLength="{vw:.1f}" '
          f'lengthAdjust="spacingAndGlyphs">{esc(value)}</text>')

    y = 124
    for label, value in ROWS:
        emit_row(label, value, y)
        y += 23
    for sec in ("CORE", "GRID"):
        A(f'<text x="520" y="{y + 3}" font-family="{MONO}" font-size="12" '
          f'fill="{t["section"]}" letter-spacing="3">-- {sec} --</text>')
        y += 23
        block = CORE if sec == "CORE" else GRID
        for label, value in block:
            emit_row(label, value, y)
            y += 23

    # footer prompt + blinking cursor
    A(f'<text x="520" y="578" font-family="{MONO}" font-size="13" '
      f'fill="{t["footer"]}">$ ./profile.sh --live</text>')
    A(f'<rect x="702" y="564" width="9" height="16" fill="{t["cursor"]}">'
      f'<animate attributeName="opacity" dur="1.1s" repeatCount="indefinite" '
      f'values="1;1;0;0;1" keyTimes="0;0.05;0.5;0.55;1"/></rect>')

    A("</svg>")

    svg = "".join(out)
    path = os.path.join(OUTDIR, f"{theme_name}.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"[{theme_name}] wrote {path}  ({os.path.getsize(path) / 1024:.0f} KB)")
    return path


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which == "all":
        build("dark")
        build("light")
    else:
        build(which)
