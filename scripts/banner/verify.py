#!/usr/bin/env python3
"""Measurement-based verification of the banner (the user's workflow demands
metrics, not eyeballing). Prints a QA report for data + both SVGs."""
import os
import sys
import numpy as np
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
NS = "{http://www.w3.org/2000/svg}"

d = np.load(os.path.join(ROOT, "data", "banner_data.npz"))
GW, GH = int(d["meta"][0]), int(d["meta"][1])
N_INTRO = int(d["meta"][2])
N_BANDS = int(d["meta"][3])
N_TRAV = int(d["meta"][4])
DRIFT_K = float(d["meta"][5])
BAND_SIGMA = float(d["meta"][6])

print("=" * 72)
print("BANNER VERIFICATION REPORT")
print("=" * 72)

# ---------------------------------------------------------------- portrait
for name in ("dark", "light"):
    dots = d[name + "_dots"]
    mask = d["mask"] if name == "dark" else np.ones_like(dots)
    n = int(dots.sum())
    ink = n / (GW * GH)
    in_subj = int((dots & mask).sum())
    print(f"[{name}] dots={n}  ink={ink * 100:.1f}%  "
          f"subject-frac={mask.mean() * 100:.1f}%  "
          f"dots-in-subject={in_subj}")
print("(spec target: ~17k dots / ~17%% ink; dark is lower because the photo "
      "is dark and the mask trims bg noise)")

# ------------------------------------------------------------ intro groups
def evenness(dots, groups, ngrp, cells=12):
    """Mean per-group deviation of spatial spread vs the global spread.
    ~0.03-0.08 = randomly interleaved (good); ~0.6+ = patchy regions."""
    ys, xs = np.nonzero(dots)
    gx, gy = xs.mean(), ys.mean()
    sx, sy = xs.std(), ys.std()
    errs = []
    for g in range(ngrp):
        sel = groups == g
        if sel.sum() == 0:
            continue
        ex, ey = xs[sel].mean(), ys[sel].mean()
        dx = (xs[sel].std() - sx) / sx
        dy = (ys[sel].std() - sy) / sy
        errs.append((abs(dx) + abs(dy)) / 2)
    return float(np.mean(errs))

for name in ("dark", "light"):
    e = evenness(d[name + "_dots"], d[name + "_groups"], N_INTRO)
    print(f"[{name}] intro group evenness = {e:.3f}   "
          f"(~0.05 good random-interleave, ~0.7 patchy regions)")

# ------------------------------------------------------------ drift bands
def boundary_wiggle(xs, ys, bid, nbcol, cell_w):
    """Mean std of vertical band-boundary x-positions across rows, in cells.
    A perfect grid scores ~0; per-dot noise sigma=4 should give ~0.1-0.2."""
    rows = {}
    for x, y, b in zip(xs, ys, bid):
        rows.setdefault(int(y), []).append((int(x), int(b % nbcol)))
    boundaries = {}
    for y, lst in rows.items():
        lst.sort()
        for (x1, c1), (x2, c2) in zip(lst, lst[1:]):
            if c1 != c2:
                key = (min(c1, c2), max(c1, c2))
                boundaries.setdefault(key, []).append((x1 + x2) / 2.0)
    wiggles = []
    for bpos in boundaries.values():
        if len(bpos) >= 5:
            wiggles.append(np.std(bpos))
    return float(np.mean(wiggles)) / cell_w if wiggles else float("nan")

for name in ("dark", "light"):
    ys, xs = np.nonzero(d[name + "_dots"])
    bid = d[name + "_bands"]
    w = boundary_wiggle(xs, ys, bid, 11, GW / 11.0)
    # baselines: clean grid (no noise) vs the noise-jittered assignment
    qx = np.clip(np.floor(xs / (GW / 11.0)), 0, 10)
    qy = np.clip(np.floor(ys / (GH / 9.0)), 0, 8)
    clean = (qy * 11 + qx).astype(int)
    w_grid = boundary_wiggle(xs, ys, clean, 11, GW / 11.0)
    displaced = float((bid != clean).mean())
    print(f"[{name}] band boundary wiggle = {w:.3f} cells (clean grid {w_grid:.3f}); "
          f"{displaced * 100:.0f}% of dots displaced across band edges by the "
          f"sigma={BAND_SIGMA} noise (0% = a straight grid)")
    print(f"        bands used: {len(np.unique(bid))}/{N_BANDS}  "
          f"drift k = {DRIFT_K}")

# ------------------------------------------------------------- travellers
l1, l2, l3 = d["logo1"], d["logo2"], d["logo3"]
p12, p23 = d["p12"], d["p23"]
m12 = np.sqrt(((l2[p12] - l1) ** 2).sum(-1)).mean()
m23 = np.sqrt(((l3[p23[p12]] - l2[p12]) ** 2).sum(-1)).mean()
print(f"[logos] travellers {len(l1)}/{len(l2)}/{len(l3)}  "
      f"mean morph travel: L1->L2 {m12:.0f}px  L2->L3 {m23:.0f}px")

# ------------------------------------------------------------------ SVGs
print("-" * 72)
for name in ("dark", "light"):
    path = os.path.join(ROOT, name + ".svg")
    size = os.path.getsize(path)
    root = ET.parse(path).getroot()
    kb = size / 1024
    # animation counts
    anims = sum(1 for _ in root.iter(NS + "animate"))
    at = sum(1 for _ in root.iter(NS + "animateTransform"))
    # rows: text elements with textLength
    tl = [e for e in root.iter(NS + "text") if e.get("textLength")]
    # loop duration + opacity phases (portrait fade animate: 5 values)
    loop_dur = None
    phases = []
    for e in root.iter(NS + "animate"):
        vals = e.get("values", "")
        kts = e.get("keyTimes") or ""
        kt = [float(v) for v in kts.split(";")] if kts else []
        if (e.get("attributeName") == "opacity"
                and vals in ("1;1;0;0;1", "0;0;1;1;0")
                and e.get("repeatCount") == "indefinite"
                and len(kt) >= 2 and kt[1] > 0.1):   # exclude cursor blink
            loop_dur = float(e.get("dur").rstrip("s"))
            phases.append([round(t * loop_dur, 1) for t in kt])
    # travellers' keyTimes sanity (8 keyframe morph schedule)
    tk = None
    for e in root.iter(NS + "animateTransform"):
        if e.get("dur") == f"{loop_dur:.1f}s" and len(
                e.get("keyTimes", "").split(";")) == 8:
            tk = e.get("keyTimes")
            break
    print(f"[{name}] size={kb:.0f} KB  texts(textLength)={len(tl)}  "
          f"anims={anims}  animTransform={at}")
    print(f"        loop opacity phase times(s): {phases}")
    print(f"        traveller keyTimes: {tk}")
    # all 16 rows present?
    labels = [e.text for e in root.iter(NS + "text") if e.text]
    expect = ["Subject", "Role", "Origin", "Education", "Status", "ToolChain",
              "Core.Lang", "Core.Frontend", "Core.Backend", "Core.Database",
              "Core.Infra", "Grid.Mail", "Grid.Portfolio", "Grid.LinkedIn",
              "Grid.GitHub"]
    missing = [l for l in expect if l not in labels]
    print(f"        missing rows: {missing or 'none'}")

print("=" * 72)
print("done. Open preview.html in a browser to check the animation.")
