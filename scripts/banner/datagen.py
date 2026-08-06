#!/usr/bin/env python3
"""
Banner data generator — THE SOURCE OF TRUTH (SVGs in the repo are derived).

Reads img.JPG and produces data/banner_data.npz containing:

  * dark_dots / light_dots : 300x340 boolean grids, 1-bit Floyd-Steinberg
    dither (serpentine order) after autocontrast(cutoff=1) -> contrast 1.3x
    -> UnsharpMask(radius=3, percent=140).
        dark  : dots draw the LIT SUBJECT only (background segmented out)
        light : dots draw the dark parts of the whole photo
  * mask                 : subject mask used for the dark theme
  * intro group ids      : 60 random interleaved groups (fade-in shimmer)
  * drift band ids       : ~94 bands, per-dot noise (sigma=4) added BEFORE
    grouping so band boundaries are organic, plus per-band drift vectors
    (42% toward the first-logo centroid in grid space)
  * logos                : three logo dot sets (~900 travellers each) in
    viewBox space + optimal-transport morph matching (scipy Hungarian)

Keep this script + the .npz; they are the source of truth, not the SVG.
"""
import os
import sys
import numpy as np
from scipy import ndimage
from scipy.optimize import linear_sum_assignment
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
def _newest_photo():
    cands = [os.path.join(ROOT, n) for n in ("img.png", "img.jpg", "img.jpeg", "img.JPG")]
    cands = [p for p in cands if os.path.exists(p)]
    if not cands:
        raise RuntimeError("no img.png / img.JPG found in repo root")
    return max(cands, key=os.path.getmtime)

PHOTO = _newest_photo()
OUTDIR = os.path.join(ROOT, "data")
OUT = os.path.join(OUTDIR, "banner_data.npz")

# ---------------------------------------------------------------- constants
GW, GH = 300, 340              # dither grid
N_INTRO = 60                   # intro fade groups
NBX, NBY = 11, 9               # drift band grid  (99 bands ~ "~94")
BAND_SIGMA = 4.0               # per-dot noise (px) before band grouping
N_TRAV = 900                   # travellers per logo
DRIFT_K = 0.42                 # band drift fraction toward first-logo centroid
GRID_CX, GRID_CY = 150.0, 170.0  # first-logo centroid in grid space (frame centre)
LOGO_BOX = (125, 145, 405, 505)  # glyph region in viewBox space (280x360)
SEED = 42
rng = np.random.default_rng(SEED)


# ------------------------------------------------------------------ helpers
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def floyd_steinberg(gray, threshold=128):
    """1-bit Floyd-Steinberg error diffusion, serpentine scan order."""
    a = np.asarray(gray, dtype=np.float64).copy()
    h, w = a.shape
    out = np.zeros((h, w), dtype=bool)
    for y in range(h):
        left_to_right = (y % 2 == 0)
        cols = range(w) if left_to_right else range(w - 1, -1, -1)
        for x in cols:
            old = a[y, x]
            new = 255.0 if old >= threshold else 0.0
            out[y, x] = (new == 0.0)
            err = old - new
            if left_to_right:
                if x + 1 < w:  a[y, x + 1] += err * 7 / 16
                if y + 1 < h:
                    if x > 0:      a[y + 1, x - 1] += err * 3 / 16
                    a[y + 1, x] += err * 5 / 16
                    if x + 1 < w:  a[y + 1, x + 1] += err * 1 / 16
            else:
                if x - 1 >= 0:  a[y, x - 1] += err * 7 / 16
                if y + 1 < h:
                    if x + 1 < w:  a[y + 1, x + 1] += err * 3 / 16
                    a[y + 1, x] += err * 5 / 16
                    if x - 1 >= 0: a[y + 1, x - 1] += err * 1 / 16
    return out


def fit_to_frame(dots, margin=6):
    """Scale + centre a dot set so its bbox fills the grid.

    The light theme fills the VISUAL.MAP frame because the photo's dark
    background dithers edge-to-edge. The dark theme draws only the subject,
    so on photos where the person is small / off-centre the portrait shrinks
    into a corner of the frame. This maps the dark dot bbox onto the full
    300x340 grid (with a small margin) so both themes fill the box.
    """
    ys, xs = np.nonzero(dots)
    if len(xs) == 0:
        return dots
    H, W = dots.shape
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    aw, ah = W - 2 * margin, H - 2 * margin
    s = min(aw / bw, ah / bh)
    tx = (W - bw * s) / 2 - x0 * s
    ty = (H - bh * s) / 2 - y0 * s
    nx = np.clip(np.round(xs * s + tx), 0, W - 1).astype(int)
    ny = np.clip(np.round(ys * s + ty), 0, H - 1).astype(int)
    out = np.zeros_like(dots)
    out[ny, nx] = True
    return out


def subject_mask(crop):
    """Background out for the dark theme.

    Seed = warm saturated skin (R-G clearly positive, not too dark) OR a
    flat-dark floor (hair, clothing). Works across different backdrops:
    a near-white wall (old photo) or a textured warm-gray wall (new photo).
    Then closing, fill holes, keep the main component and any large
    component touching the border (the shoulders); small corner shadow
    blobs touching the frame edge are dropped.
    """
    rgb = np.asarray(crop.convert("RGB"), dtype=np.float64)
    h, w, _ = rgb.shape
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = R * 0.299 + G * 0.587 + B * 0.114
    # subject = warm saturated skin (R-G clearly positive) + dark floor
    # (hair, eyes, dark clothing). The dark floor is gated by PROXIMITY to
    # the face skin so distant dark background corners are never included
    # (hair is adjacent to the face, clothing to the neck/shoulders).
    skin = (R - G > 25.0) & (R > 130.0) & (lum > 85.0)
    skin = ndimage.binary_closing(skin, iterations=2, structure=np.ones((5, 5)))
    lab, n = ndimage.label(skin)
    if n > 1:
        sizes = ndimage.sum(skin, lab, range(1, n + 1))
        skin = lab == int(np.argmax(sizes) + 1)
    reach = ndimage.binary_dilation(skin, structure=np.ones((5, 5)),
                                    iterations=90)   # ~216 px halo
    m = skin | ((lum < 85.0) & reach)
    m = ndimage.binary_closing(m, iterations=2, structure=np.ones((5, 5)))
    m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    if n > 1:
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        main = int(np.argmax(sizes) + 1)
        border_mask = np.zeros_like(m)
        border_mask[0, :] = border_mask[-1, :] = True
        border_mask[:, 0] = border_mask[:, -1] = True
        touching = np.unique(lab[border_mask])
        touching = touching[touching > 0]
        keep = {main}
        for lbl in touching:
            if sizes[lbl - 1] > 0.005 * (h * w):
                keep.add(int(lbl))
        m = np.isin(lab, list(keep))
    return m, np.median(np.stack([R[0, :], G[0, :], B[0, :]], -1), axis=0)


def crop_head_shoulders(pil_img):
    """The source photo is already a head-and-shoulders shot: crop to the
    300x340 aspect, centred. Face detection only nudges the frame vertically
    so the face centre sits near ~56% of the frame height."""
    import cv2
    W, H = pil_img.size
    aspect = GW / GH
    if W / H >= aspect:
        cw, ch = int(H * aspect), H
    else:
        ch, cw = int(W / aspect), W
    left, top = (W - cw) // 2, (H - ch) // 2
    arr = np.asarray(pil_img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
    if len(faces) == 0:
        faces = cascade.detectMultiScale(gray, 1.05, 3, minSize=(50, 50))
    if len(faces):
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        if fh > 0.06 * H:   # ignore tiny false positives (background faces)
            print("face box (x,y,w,h):", (int(fx), int(fy), int(fw), int(fh)))
            desired = int((fy + fh / 2.0) - 0.56 * ch)
            top = int(clamp(desired, 0, H - ch))
        else:
            print("WARN: no usable face (largest %dpx), keeping centred crop"
                  % int(fh))
    else:
        print("WARN: no face detected, keeping centred crop")
    crop = pil_img.crop((left, top, left + cw, top + ch))
    return crop, (left, top, cw, ch)


def _pool(arr, w, h):
    """Max-pool a bool array into an (h, w) grid (faithful preview)."""
    out = np.zeros((h, w), dtype=bool)
    ys, xs = np.nonzero(arr)
    gy = np.clip((ys * h) // arr.shape[0], 0, h - 1)
    gx = np.clip((xs * w) // arr.shape[1], 0, w - 1)
    out[gy, gx] = True
    return out


def ascii_preview(dots, mask, w=96):
    """Print a coarse ASCII render of the dot grid (mask context)."""
    hgt = int(dots.shape[0] * w / dots.shape[1])
    ds = _pool(dots, w, hgt)
    mres = _pool(mask, w, hgt)
    for r in range(hgt):
        line = ""
        for c in range(w):
            if ds[r, c]:
                line += "#"
            elif mres[r, c]:
                line += "."
            else:
                line += " "
        print(line)
    print()


def ascii_photo(arr, w=96):
    """Print a grayscale ascii of an image array (for framing QA)."""
    img = Image.fromarray(arr).convert("L")
    hgt = int(img.size[1] * w / img.size[0])
    a = np.asarray(img.resize((w, hgt), Image.BILINEAR))
    chars = " .:-=+*#%@"
    for row in a:
        print("".join(chars[min(9, int(v / 25.6))] for v in row))
    print()


# ------------------------------------------------------------------- logos
def _font(size):
    cands = [
        "C:/Windows/Fonts/DejaVuSansMono-Bold.ttf",
        "C:/Windows/Fonts/consolab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    ]
    for p in cands:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return None


def rasterize(mask_func, box, scale=2):
    """mask_func(x,y) -> bool over the box; returns boolean pixel mask."""
    x0, y0, x1, y1 = box
    w, h = int((x1 - x0) * scale), int((y1 - y0) * scale)
    yy, xx = np.mgrid[0:h, 0:w]
    m = mask_func(x0 + xx / scale, y0 + yy / scale)
    return m, (x0, y0), scale


def logo_vercel():
    x0, y0, x1, y1 = LOGO_BOX
    cx = (x0 + x1) / 2
    apex = (cx, y0 + 8)
    bl = (x0 + 18, y1 - 8)
    br = (x1 - 18, y1 - 8)

    def mf(x, y):
        # CCW winding apex->bl->br -> inside = all cross products <= 0
        return (((br[0] - bl[0]) * (y - bl[1]) - (br[1] - bl[1]) * (x - bl[0]) <= 0)
                & ((apex[0] - br[0]) * (y - br[1]) - (apex[1] - br[1]) * (x - br[0]) <= 0)
                & ((bl[0] - apex[0]) * (y - apex[1]) - (bl[1] - apex[1]) * (x - apex[0]) <= 0))
    return rasterize(mf, LOGO_BOX)


def logo_next():
    x0, y0, x1, y1 = LOGO_BOX
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    R = 0.47 * (x1 - x0)      # ring outer radius
    r_in = R - 0.085 * (x1 - x0)
    # N letterform strokes (traced from the canonical mark, N touches ring)
    sx0, sx1 = cx - 0.42 * R, cx + 0.42 * R
    hw = 0.13 * R             # half stroke width
    yt, yb = cy - R + 4.0, cy + R - 4.0
    d0 = (sx0 + hw, yb - hw)
    d1 = (sx1 - hw, yt + hw)
    u = (d1[0] - d0[0], d1[1] - d0[1])
    denom = u[0] ** 2 + u[1] ** 2

    def in_stroke(x, y):
        t = ((x - d0[0]) * u[0] + (y - d0[1]) * u[1]) / denom
        t = np.clip(t, 0, 1)
        px = d0[0] + t * u[0]
        py = d0[1] + t * u[1]
        return (x - px) ** 2 + (y - py) ** 2 <= hw ** 2

    def mf(x, y):
        dist = np.hypot(x - cx, y - cy)
        ring = (dist <= R) & (dist >= r_in)
        vert = (((x >= sx0 - hw) & (x <= sx0 + hw) & (y >= yt - hw) & (y <= yb + hw))
                | ((x >= sx1 - hw) & (x <= sx1 + hw) & (y >= yt - hw) & (y <= yb + hw)))
        return ring | vert | in_stroke(x, y)
    return rasterize(mf, LOGO_BOX)


def logo_angle():
    """</> glyph traced from a bold monospace font."""
    x0, y0, x1, y1 = LOGO_BOX
    w, h = (x1 - x0), (y1 - y0)
    fsize = 150
    f = _font(fsize)
    if f is None:
        raise RuntimeError("no bold monospace font found for the </> glyph")
    img = Image.new("L", (int(w), int(h)), 0)
    d = ImageDraw.Draw(img)
    text = "</>"
    tw = d.textlength(text, font=f)
    d.text(((w - tw) / 2, (h - fsize) / 2 - 14), text, font=f, fill=255)
    a = np.asarray(img, dtype=bool)

    def mf(x, y):
        xx = np.clip((x - x0).astype(int), 0, w - 1)
        yy = np.clip((y - y0).astype(int), 0, h - 1)
        return a[yy, xx]
    return rasterize(mf, LOGO_BOX, scale=2)


def sample_dots(mask, box, scale, target=N_TRAV):
    """Sample ~target dot positions from a rasterized logo mask (viewBox coords)."""
    x0, y0 = box[0], box[1]
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise RuntimeError("empty logo mask")
    total = len(xs)
    stride = max(1, int(np.ceil(np.sqrt(total / target))))
    # one dot per stride^2 block, at a RANDOM cell inside it: evenly spread
    # yet organic (a fixed block-corner pick shows a visible lattice)
    keys = (ys // stride) * 100000 + (xs // stride)
    order = np.argsort(keys, kind="stable")
    ksort = keys[order]
    starts = np.searchsorted(ksort, np.unique(ksort))
    idx = []
    for b in range(len(starts)):
        g = order[starts[b]: starts[b + 1] if b + 1 < len(starts) else len(order)]
        idx.append(int(g[rng.integers(0, len(g))]))
    idx = np.array(idx, dtype=np.int64)            # real indices into xs/ys
    # pad / trim to exactly N_TRAV (deterministic)
    if len(idx) > target:
        idx = idx[rng.permutation(len(idx))[:target]]
    while len(idx) < target:
        extra = rng.choice(len(xs), target - len(idx), replace=False)
        idx = np.concatenate([idx, extra])
    # mask pixels are at `scale` px per viewBox unit
    xy = np.stack([x0 + xs[idx] / scale, y0 + ys[idx] / scale], axis=1)
    return xy.astype(np.float64)


def optimal_transport(A, B):
    """Return permutation p such that sum |A_i - B_{p(i)}| is minimal."""
    cost = ((A[:, None, :] - B[None, :, :]) ** 2).sum(-1)
    ri, ci = linear_sum_assignment(cost)
    p = np.empty(len(A), dtype=np.int64)
    p[ri] = ci
    return p, cost[ri, ci].sum()


# ---------------------------------------------------------------- pipeline
def main():
    print("== banner datagen ==")
    img = Image.open(PHOTO)
    img = ImageOps.exif_transpose(img)
    crop, box = crop_head_shoulders(img)
    print("crop box (l,t,w,h):", box, " crop:", crop.size)
    print("crop ascii (framing QA):")
    ascii_photo(np.asarray(crop))

    # grayscale pipeline: autocontrast(1) -> contrast 1.3 -> unsharp(3,140)
    g = crop.convert("L")
    g = ImageOps.autocontrast(g, cutoff=1)
    g = ImageEnhance.Contrast(g).enhance(1.3)
    g = g.filter(ImageFilter.UnsharpMask(radius=3, percent=140))
    g = g.resize((GW, GH), Image.LANCZOS)

    # 1-bit FS ink is mean-driven (ink ~= 1 - mean/255; the threshold only
    # picks the tonal anchor). On this photo the raw pipeline yields ~40%
    # ink; a mild density tone curve lands ~18-20% ink (the photo is dark, so
    # 17% would wash out the face).
    vals = np.asarray(g, dtype=np.float64)
    target_ink = 0.19
    vn = vals / 255.0
    lo, hi = 0.12, 1.0
    for _ in range(28):
        gam = (lo + hi) / 2
        if 1.0 - (vn ** gam).mean() > target_ink:
            hi = gam
        else:
            lo = gam
    g2 = Image.fromarray(np.clip(255.0 * vn ** gam, 0, 255).astype(np.uint8))
    print("density gamma: %.3f -> predicted ink %.1f%%"
          % (gam, (1.0 - (vn ** gam).mean()) * 100))
    dither = floyd_steinberg(g2, threshold=128)  # dots = dark parts
    mask, bg = subject_mask(crop)
    mask = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).resize(
        (GW, GH), Image.NEAREST)) > 127

    dark_dots = dither & mask
    light_dots = dither
    print("bg colour (RGB):", np.round(bg).astype(int))
    print("subject fraction: %.3f" % mask.mean())
    print("dark dots: %d  light dots: %d" % (dark_dots.sum(), light_dots.sum()))

    # The dark portrait must fill the VISUAL.MAP frame like the light one.
    # On photos where the subject is small / off-centre the dark dots would
    # otherwise hug the top-left of the box (light fills it only because the
    # photo background dithers edge-to-edge). Fit the dark bbox to the grid.
    dark_dots = fit_to_frame(dark_dots)
    mask = fit_to_frame(mask)
    print("dark dots fitted to frame: bbox x[%d..%d] y[%d..%d] of %dx%d"
          % (np.nonzero(dark_dots)[1].min(), np.nonzero(dark_dots)[1].max(),
             np.nonzero(dark_dots)[0].min(), np.nonzero(dark_dots)[0].max(),
             GW, GH))

    # ---- ASCII QA preview (framing + density check) ----
    print("dark dots preview (subject='.', dots='#'):")
    ascii_preview(dark_dots, mask)
    print("light dots preview:")
    ascii_preview(light_dots, np.ones_like(light_dots))

    # ---- band grouping (per-dot noise BEFORE quantizing) ----
    bands = {}
    drifts = {}
    for name, dots in (("dark", dark_dots), ("light", light_dots)):
        ys, xs = np.nonzero(dots)
        n = len(xs)
        noise = rng.normal(0.0, BAND_SIGMA, (n, 2))
        qx = np.clip(np.floor((xs + noise[:, 0]) / (GW / NBX)), 0, NBX - 1)
        qy = np.clip(np.floor((ys + noise[:, 1]) / (GH / NBY)), 0, NBY - 1)
        bid = (qy * NBX + qx).astype(int)
        # drift vector per band: 42% toward the first-logo centroid (grid space)
        drift = {}
        for b in range(NBX * NBY):
            sel = bid == b
            if sel.sum() == 0:
                drift[b] = (0.0, 0.0)
                continue
            cxm = xs[sel].mean()
            cym = ys[sel].mean()
            drift[b] = (DRIFT_K * (GRID_CX - cxm), DRIFT_K * (GRID_CY - cym))
        bands[name] = bid
        drifts[name] = np.array([drift[b] for b in range(NBX * NBY)], dtype=float)
        print(f"{name}: bands used = {len(np.unique(bid))}")

    # ---- intro groups: 60 random interleaved groups ----
    groups = {}
    for name, dots in (("dark", dark_dots), ("light", light_dots)):
        n = int(dots.sum())
        groups[name] = rng.integers(0, N_INTRO, size=n)

    # ---- logos + optimal transport ----
    print("rasterizing logos ...")
    m1, _, s1 = logo_next()
    m2, _, s2 = logo_angle()
    m3, _, s3 = logo_vercel()
    l1 = sample_dots(m1, LOGO_BOX, s1)
    l2 = sample_dots(m2, LOGO_BOX, s2)
    l3 = sample_dots(m3, LOGO_BOX, s3)
    print("travellers: L1(Next) %d  L2(</>) %d  L3(Vercel) %d"
          % (len(l1), len(l2), len(l3)))
    p12, c12 = optimal_transport(l1, l2)
    p23, c23 = optimal_transport(l2, l3)
    p31, c31 = optimal_transport(l3, l1)
    print("OT mean travel px: L1->L2 %.1f  L2->L3 %.1f  L3->L1 %.1f"
          % (np.sqrt(c12 / len(l1)), np.sqrt(c23 / len(l2)), np.sqrt(c31 / len(l3))))

    # ---- logo QA preview ----
    for name, a in (("L1 Next", l1), ("L2 </>", l2), ("L3 Vercel", l3)):
        img = np.zeros((510, 450), dtype=bool)
        xx = np.clip(((a[:, 0] - 40) / 3.0).astype(int), 0, 149)
        yy = np.clip(((a[:, 1] - 70) / 3.4).astype(int), 0, 149)
        img[yy * 3, xx * 3] = True
        print("--- %s  (x[%.0f..%.0f] y[%.0f..%.0f])"
              % (name, a[:, 0].min(), a[:, 0].max(), a[:, 1].min(), a[:, 1].max()))
        for row in img[::5]:
            print("".join("#" if v else " " for v in row[::5]))

    os.makedirs(OUTDIR, exist_ok=True)
    np.savez_compressed(
        OUT,
        dark_dots=dark_dots, light_dots=light_dots, mask=mask,
        dark_groups=groups["dark"], light_groups=groups["light"],
        dark_bands=bands["dark"], light_bands=bands["light"],
        dark_drift=drifts["dark"], light_drift=drifts["light"],
        logo1=l1, logo2=l2, logo3=l3,
        p12=p12, p23=p23, p31=p31,
        crop_box=np.array(box), bg=np.array(bg),
        meta=np.array([GW, GH, N_INTRO, NBX * NBY, N_TRAV, DRIFT_K, BAND_SIGMA]),
    )
    print("wrote", OUT)


if __name__ == "__main__":
    sys.exit(main())
