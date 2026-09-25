#!/usr/bin/env python3
"""
Regenerate the images in docs/ from the current model.

  docs/hero.png                 3/4 view of the connector end, "Round tube 15 mm ID"
  docs/presets.png              the five saved presets side by side
  docs/tips.png                 cone, ogive and chisel tips
  docs/gallery/spines.png       0 (solid), 2, 3, 4, 6 and 8 spines
  docs/gallery/support-free.png square and round, Support_free on and off, seen from below
  docs/gallery/retention.png    bare, tie band, grip rings, screw hole
  docs/gallery/sizes.png        9, 15 and 30 mm connectors at the same scale
  docs/gallery/preset-*.png     a close-up of each saved preset

Each variant is rendered to STL first and then photographed as an imported
mesh. That gives every face one colour; rendering the .scad directly tints
any surface cut by a subtraction yellow, which reads as a defect in a picture.

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
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAD = os.path.join(ROOT, "yard-spike-parametric.scad")
PRESETS = os.path.join(ROOT, "yard-spike-parametric.json")
DOCS = os.path.join(ROOT, "docs")
GALLERY = os.path.join(DOCS, "gallery")
SCHEME = "Tomorrow"
PART = "#d9822b"
BG = (248, 248, 248)
INK = (60, 60, 60)

# Cameras are OpenSCAD --camera values: target x,y,z, rotation x,y,z, distance.
# Rotation x is 0 looking straight down, 90 level, past 90 looking up.
CONNECTOR = (0, 0, 5, 62, 0, 30, 90)      # 3/4 view of the connector end
UNDERSIDE = (0, 0, 4, 112, 0, 30, 85)     # looking up at the plates
STANDING = (0, 0, 0, 80, 0, 30, 0)        # whole part, fitted to the frame
TIP = (0, 0, 106, 80, 0, 35, 70)          # the last 15 mm


class Renderer:
    def __init__(self, openscad, tmp):
        self.openscad = openscad
        self.tmp = tmp
        self.meshes = {}

    def run(self, args, what):
        proc = subprocess.run([self.openscad] + args, capture_output=True, text=True)
        if proc.returncode != 0:
            sys.exit(f"OpenSCAD failed on {what}:\n{proc.stdout}{proc.stderr}")

    def mesh(self, preset=None, **defines):
        """STL for one configuration, rendered once and reused."""
        key = (preset, tuple(sorted(defines.items())))
        if key not in self.meshes:
            out = os.path.join(self.tmp, f"part{len(self.meshes)}.stl")
            args = ["-o", out]
            if preset:
                args += ["-p", PRESETS, "-P", preset]
            for name, value in defines.items():
                if isinstance(value, bool):
                    value = "true" if value else "false"
                elif isinstance(value, str):
                    value = f'"{value}"'
                args += ["-D", f"{name}={value}"]
            self.run(args + [SCAD], preset or str(defines))
            self.meshes[key] = out
        return self.meshes[key]

    def section(self, stl, z):
        """The same part cut off flat at height z, as a new STL. Cutting in a
        separate export keeps the cut face the same colour as the rest."""
        n = len(os.listdir(self.tmp))
        wrapper = os.path.join(self.tmp, f"cut{n}.scad")
        out = os.path.join(self.tmp, f"cut{n}.stl")
        with open(wrapper, "w", encoding="utf-8") as f:
            f.write(f'intersection() {{ import("{stl.replace(os.sep, "/")}"); '
                    f"translate([-500, -500, -500]) cube([1000, 1000, {500 + z}]); }}\n")
        self.run(["-o", out, wrapper], stl)
        return out

    def shot(self, stl, size, camera, ortho=False, fit=False):
        """Photograph an STL and return the image."""
        n = len(os.listdir(self.tmp))
        wrapper = os.path.join(self.tmp, f"shot{n}.scad")
        png = os.path.join(self.tmp, f"shot{n}.png")
        with open(wrapper, "w", encoding="utf-8") as f:
            f.write(f'color("{PART}") import("{stl.replace(os.sep, "/")}");\n')
        args = ["-o", png, f"--imgsize={size[0]},{size[1]}",
                f"--camera={','.join(str(c) for c in camera)}", f"--colorscheme={SCHEME}"]
        if ortho:
            args.append("--projection=o")
        if fit:
            args += ["--viewall", "--autocenter"]
        self.run(args + [wrapper], stl)
        return Image.open(png).convert("RGB")


def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def strip(tiles, labels, pad=20):
    """Lay tiles out left to right with a caption under each."""
    f = font(26)
    lines = max(len(label.split("\n")) for label in labels)
    label_h = 12 + lines * 32
    w = sum(t.width for t in tiles)
    h = max(t.height for t in tiles) + label_h + pad
    sheet = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(sheet)
    x = 0
    for tile, label in zip(tiles, labels):
        sheet.paste(tile, (x, 0))
        for i, line in enumerate(label.split("\n")):
            tw = draw.textlength(line, font=f)
            draw.text((x + (tile.width - tw) / 2, tile.height + 6 + i * 32), line, fill=INK, font=f)
        x += tile.width
    return sheet


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--openscad", default=os.environ.get("OPENSCAD", "openscad"))
    args = ap.parse_args()
    if shutil.which(args.openscad) is None and not os.path.exists(args.openscad):
        sys.exit(f"OpenSCAD not found at '{args.openscad}'. Pass --openscad or set OPENSCAD.")

    os.makedirs(GALLERY, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="spike-img-")
    r = Renderer(args.openscad, tmp)
    written = []

    def save(img, *path):
        out = os.path.join(DOCS, *path)
        img.save(out)
        written.append(os.path.relpath(out, ROOT).replace(os.sep, "/"))

    try:
        with open(PRESETS, encoding="utf-8") as f:
            presets = list(json.load(f)["parameterSets"].keys())

        # Hero: the connector end is where all the detail lives.
        save(r.shot(r.mesh("Round tube 15 mm ID"), (1200, 800), CONNECTOR), "hero.png")

        # Presets, whole part. They are all within a few mm of the same
        # length, so fitting each to its tile keeps them at a common scale.
        tiles = [r.shot(r.mesh(p), (300, 1000), STANDING, ortho=True, fit=True) for p in presets]
        labels = [p.replace(", ", ",\n").replace(" 15 mm", "\n15 mm") for p in presets]
        save(strip(tiles, labels), "presets.png")

        # One close-up per preset.
        for p in presets:
            save(r.shot(r.mesh(p), (900, 900), CONNECTOR), "gallery", f"preset-{slug(p)}.png")

        # Tips at stock length and point diameter.
        tiles = [r.shot(r.mesh(Connector_shape="circle", Tip_style=s), (420, 520), TIP)
                 for s in ("cone", "ogive", "chisel")]
        save(strip(tiles, ["Cone", "Ogive", "Chisel"]), "tips.png")

        # Spine counts, cut off 30 mm up so the cross section reads as a star.
        counts = [0, 2, 3, 4, 6, 8]
        tiles = [r.shot(r.section(r.mesh(Spines=n), 30), (360, 460), (0, 0, 12, 30, 0, 30, 105))
                 for n in counts]
        labels = ["Solid\nSpines = 0"] + [f"{n} spines\n " for n in counts[1:]]
        save(strip(tiles, labels), "gallery", "spines.png")

        # Support_free on and off, looking up at the undersides.
        combos = [("square", True), ("square", False), ("circle", True), ("circle", False)]
        tiles = [r.shot(r.mesh(Connector_shape=s, Support_free=sf, Tie_band=False), (420, 460), UNDERSIDE)
                 for s, sf in combos]
        labels = [f"{'Square' if s == 'square' else 'Round'}\nSupport_free {'on' if sf else 'off'}"
                  for s, sf in combos]
        save(strip(tiles, labels), "gallery", "support-free.png")

        # Retention hardware, building up on a round connector.
        steps = [
            ("Bare\n ", dict(Tie_band=False)),
            ("Tie band\n ", dict()),
            ("Grip rings\n+ 0.3 fit", dict(Grip_rings=2, Fit_clearance=0.3)),
            ("Screw hole\n+ rings", dict(Screw_hole=3.5, Grip_rings=2, Connector_depth=18, Fit_clearance=0.35)),
        ]
        tiles = [r.shot(r.mesh(Connector_shape="circle", **d), (420, 460), CONNECTOR) for _, d in steps]
        save(strip(tiles, [label for label, _ in steps]), "gallery", "retention.png")

        # Sizes at one fixed scale, so the difference is real.
        sizes = [9, 15, 30]
        tiles = [r.shot(r.mesh(Connector_size=s), (340, 1000), (0, 0, 54, 80, 0, 30, 330), ortho=True)
                 for s in sizes]
        save(strip(tiles, [f"{s} mm connector" for s in sizes]), "gallery", "sizes.png")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("wrote\n  " + "\n  ".join(written))


if __name__ == "__main__":
    main()
