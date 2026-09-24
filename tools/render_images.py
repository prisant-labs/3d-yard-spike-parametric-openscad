#!/usr/bin/env python3
"""
Regenerate the images in docs/ from the current model.

  docs/hero.png       3/4 view of the connector end, "Round tube 15 mm ID" preset
  docs/presets.png    the five saved presets side by side, near enough the same scale
  docs/tips.png       cone, ogive and chisel tips, same length and point

Run it after any change that alters geometry, so the README never shows a part
the .scad no longer makes.

Usage:
  python tools/render_images.py
  python tools/render_images.py --openscad "C:/Program Files/OpenSCAD/openscad.com"

Requires Python 3.8+, Pillow, OpenSCAD and BOSL2.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAD = os.path.join(ROOT, "yard-spike-parametric.scad")
PRESETS = os.path.join(ROOT, "yard-spike-parametric.json")
DOCS = os.path.join(ROOT, "docs")
SCHEME = "Tomorrow"
BG = (248, 248, 248)
INK = (60, 60, 60)


def render(openscad, out, size, camera, preset=None, defines=None, ortho=False, fit=False):
    cmd = [openscad, "-o", out, "--render", f"--imgsize={size[0]},{size[1]}",
           f"--camera={','.join(str(c) for c in camera)}", f"--colorscheme={SCHEME}"]
    if ortho:
        cmd.append("--projection=o")
    if fit:
        cmd += ["--viewall", "--autocenter"]
    if preset:
        cmd += ["-p", PRESETS, "-P", preset]
    for key, value in (defines or {}).items():
        cmd += ["-D", f"{key}={value}"]
    cmd.append(SCAD)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not os.path.exists(out):
        sys.exit(f"OpenSCAD failed on {out}:\n{proc.stdout}{proc.stderr}")


def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def strip(tiles, labels, pad=24, label_h=64):
    """Lay tiles out left to right with a caption under each."""
    w = sum(t.width for t in tiles)
    h = max(t.height for t in tiles) + label_h + pad
    sheet = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(sheet)
    f = font(26)
    x = 0
    for tile, label in zip(tiles, labels):
        sheet.paste(tile, (x, 0))
        for i, line in enumerate(label.split("\n")):
            tw = draw.textlength(line, font=f)
            draw.text((x + (tile.width - tw) / 2, tile.height + 4 + i * 30), line, fill=INK, font=f)
        x += tile.width
    return sheet


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--openscad", default=os.environ.get("OPENSCAD", "openscad"))
    args = ap.parse_args()
    if shutil.which(args.openscad) is None and not os.path.exists(args.openscad):
        sys.exit(f"OpenSCAD not found at '{args.openscad}'. Pass --openscad or set OPENSCAD.")

    os.makedirs(DOCS, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="spike-img-")
    try:
        # Hero: the connector end is where all the detail lives.
        render(args.openscad, os.path.join(DOCS, "hero.png"), (1200, 800),
               (0, 0, 5, 62, 0, 30, 90), preset="Round tube 15 mm ID")

        # Presets. All five are within a few mm of the same length, so fitting
        # each to its tile keeps them at near enough the same scale.
        with open(PRESETS, encoding="utf-8") as f:
            names = list(json.load(f)["parameterSets"].keys())
        tiles = []
        for i, name in enumerate(names):
            out = os.path.join(tmp, f"preset{i}.png")
            render(args.openscad, out, (300, 1000), (0, 0, 0, 80, 0, 30, 0),
                   preset=name, ortho=True, fit=True)
            tiles.append(Image.open(out).convert("RGB"))
        labels = [n.replace(", ", ",\n").replace(" 15 mm", "\n15 mm") for n in names]
        strip(tiles, labels, label_h=70).save(os.path.join(DOCS, "presets.png"))

        # Tips at stock length and point diameter, looking up at the point.
        tiles = []
        for style in ("cone", "ogive", "chisel"):
            out = os.path.join(tmp, f"tip-{style}.png")
            render(args.openscad, out, (420, 520), (0, 0, 106, 80, 0, 35, 70),
                   defines={"Tip_style": f'"{style}"', "Connector_shape": '"circle"'})
            tiles.append(Image.open(out).convert("RGB"))
        strip(tiles, ["Cone", "Ogive", "Chisel"], label_h=40).save(os.path.join(DOCS, "tips.png"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("wrote docs/hero.png, docs/presets.png, docs/tips.png")


if __name__ == "__main__":
    main()
