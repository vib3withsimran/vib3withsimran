#!/usr/bin/env python3
"""Render the dot grids to PNGs for a pixel-level QA look."""
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = 'C:/Users/simran gupta/Coding/webDevelopment/Simran_Portfolio/github repo'
d = np.load(ROOT + '/data/banner_data.npz')
dark = d['dark_dots']; light = d['light_dots']; mask = d['mask']
H, W = dark.shape
scale = 3
panel = np.array([10, 16, 31], dtype=np.uint8)
bgfill = np.array([25, 32, 52], dtype=np.uint8)

big = np.zeros((H * scale, W * scale * 3, 3), dtype=np.uint8)
big[:, :W * scale] = panel
big[:, W * scale:2 * W * scale] = 255
big[:, 2 * W * scale:] = panel

for y, x in zip(*np.nonzero(dark)):
    big[y * scale:(y + 1) * scale, x * scale:(x + 1) * scale] = (167, 139, 250)
for y, x in zip(*np.nonzero(mask & ~dark)):
    big[y * scale:(y + 1) * scale, x * scale:(x + 1) * scale] = bgfill
for y, x in zip(*np.nonzero(light)):
    big[y * scale:(y + 1) * scale, (W + x) * scale:(W + x + 1) * scale] = (10, 16, 31)
mm = ndimage.binary_dilation(mask) & ~mask
for y, x in zip(*np.nonzero(mm)):
    big[y * scale:(y + 1) * scale, (W + x) * scale:(W + x + 1) * scale] = (200, 0, 0)
Image.fromarray(big).save(ROOT + '/_qa_grid.png')

img = Image.new('RGB', (W * 4, H * 4), tuple(panel))
pix = img.load()
for y, x in zip(*np.nonzero(dark)):
    for dy in range(4):
        for dx in range(4):
            pix[x * 4 + dx, y * 4 + dy] = (167, 139, 250)
img.save(ROOT + '/_qa_dark.png')
print('saved _qa_grid.png and _qa_dark.png')
