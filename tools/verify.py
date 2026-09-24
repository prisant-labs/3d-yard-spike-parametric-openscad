#!/usr/bin/env python3
"""
Measurement pass for yard-spike-parametric.scad.

Renders each configuration to STL with OpenSCAD, then reads the mesh back and
measures it, so a change is judged by numbers rather than by a screenshot.

For every configuration it reports:

  tris        triangle count in the exported STL
  volume      signed volume in mm^3
  parts       face-connected pieces in the STL. A clean print is 1
  solid       OpenSCAD's own verdict on the solid before export: CGAL must say
              "Simple: yes" with 2 volumes (the part plus the outside), the
              Manifold backend must say "Status: NoError"
  steepest    worst overhang in degrees, measured from vertical, bed face
              excluded, slivers under 0.001 mm^2 ignored
  >45 area    mm^2 of facets overhanging past 45 degrees, bed face excluded
  flat area   mm^2 of flat, downward facing area off the bed, which is what
              a printer has to bridge
  top area    mm^2 of the final layer, the area at the very tip

A configuration fails if OpenSCAD does not call it a clean solid, if the STL
is more than one piece, or if Support_free is on and any area overhangs past
45 degrees.

Usage:
  python tools/verify.py                        presets and the full matrix
  python tools/verify.py --presets              the five saved presets only
  python tools/verify.py --only "Round tube"    configurations whose name contains this
  python tools/verify.py --stl part.stl         measure an STL you already have
  python tools/verify.py --openscad "C:/Program Files/OpenSCAD/openscad.com"

Requires Python 3.8+, numpy, OpenSCAD and BOSL2. Set OPENSCAD or pass
--openscad if the binary is not on PATH.
"""

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAD = os.path.join(ROOT, "yard-spike-parametric.scad")
PRESETS = os.path.join(ROOT, "yard-spike-parametric.json")

LIMIT_DEG = 45.0
TOL_DEG = 0.01       # a 45 degree chamfer sits exactly on the limit, so allow float noise
FLAT_DEG = 89.9
SLIVER_MM2 = 0.001   # CGAL exports leave needle triangles whose normals mean nothing

# Each row is (name, overrides). Overrides go to OpenSCAD as -D name=value on
# top of the defaults in the .scad. Both connector shapes run the same sweep.
SWEEP = [
    ("defaults",           {}),
    ("solid, Spines=0",    {"Spines": 0}),
    ("Spines=3",           {"Spines": 3}),
    ("Spines=6",           {"Spines": 6}),
    ("Spines=8",           {"Spines": 8}),
    ("ogive tip",          {"Tip_style": "ogive"}),
    ("chisel tip",         {"Tip_style": "chisel"}),
    ("rings, 0.3 fit",     {"Grip_rings": 2, "Fit_clearance": 0.3}),
    ("screw hole, rings",  {"Screw_hole": 3.5, "Grip_rings": 2, "Connector_depth": 18, "Fit_clearance": 0.35}),
    ("size 9",             {"Connector_size": 9}),
    ("size 30",            {"Connector_size": 30}),
    ("Support_free off",   {"Support_free": False}),
]


def matrix():
    rows = []
    for shape in ("square", "circle"):
        for name, overrides in SWEEP:
            rows.append((f"{shape}: {name}", dict(Connector_shape=shape, **overrides)))
    return rows


def load_presets():
    with open(PRESETS, encoding="utf-8") as f:
        return json.load(f)["parameterSets"]


def scad_literal(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    return repr(value)


def render(openscad, out, preset=None, overrides=None):
    cmd = [openscad, "-o", out]
    if preset:
        cmd += ["-p", PRESETS, "-P", preset]
    for key, value in (overrides or {}).items():
        cmd += ["-D", f"{key}={scad_literal(value)}"]
    cmd.append(SCAD)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log = proc.stdout + proc.stderr
    if proc.returncode != 0 or not os.path.exists(out):
        lines = [l for l in log.strip().splitlines() if "ERROR" in l or "assert" in l.lower()]
        raise RuntimeError(lines[0] if lines else "OpenSCAD failed")
    return log


def solid_verdict(log):
    """OpenSCAD's own opinion of the solid, or None if it did not give one."""
    simple = re.search(r"Simple:\s+(\w+)", log)
    if simple:
        volumes = re.search(r"Volumes:\s+(\d+)", log)
        return simple.group(1) == "yes" and volumes is not None and int(volumes.group(1)) == 2
    status = re.search(r"Status:\s+(\w+)", log)
    if status:
        return status.group(1) == "NoError"
    return None


def read_stl(path):
    """Triangles as an (n, 3, 3) array. Handles ASCII and binary STL."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) >= 84:
        count = struct.unpack("<I", data[80:84])[0]
        if 84 + count * 50 == len(data):
            rec = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
            return np.frombuffer(data, dtype=rec, count=count, offset=84)["v"].astype(float)
    nums = re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", data)
    return np.array(nums, dtype=float).reshape(-1, 3, 3)


def measure(tris):
    # Topology first, on every triangle. CGAL leaves zero-area needles along
    # some edges, and they carry edges their neighbours pair with, so dropping
    # them before this step would make a clean mesh look torn.
    verts, idx = np.unique(np.round(tris.reshape(-1, 3), 5), axis=0, return_inverse=True)
    faces = idx.reshape(-1, 3)
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    _, edge_id, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
    # Needles can also leave an edge referenced four times, so this is only a
    # fallback for STLs that arrive without an OpenSCAD log.
    edges_paired = bool(np.all(counts == 2))

    parent = list(range(len(faces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    first = {}
    for e, f in zip(edge_id.ravel(), np.tile(np.arange(len(faces)), 3)):
        if e in first:
            a, b = find(first[e]), find(f)
            if a != b:
                parent[a] = b
        else:
            first[e] = f
    parts = len({find(f) for f in range(len(faces))})

    # Geometry, on triangles with real area. Needles have no normal.
    triangles = len(tris)
    cross = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    double_area = np.linalg.norm(cross, axis=1)
    keep = double_area > 1e-12
    tris, cross, double_area = tris[keep], cross[keep], double_area[keep]
    area = double_area / 2
    nz = cross[:, 2] / double_area

    volume = float(np.einsum("ij,ij->i", tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum() / 6)

    z = tris[:, :, 2]
    zmin, zmax = z.min(), z.max()
    on_bed = np.all(np.abs(z - zmin) < 1e-4, axis=1)
    at_top = np.all(np.abs(z - zmax) < 1e-4, axis=1)

    # Overhang measured from vertical: a wall is 0, a ceiling is 90.
    overhang = np.degrees(np.arcsin(np.clip(-nz, -1, 1)))
    off_bed = ~on_bed
    steep = off_bed & (overhang > LIMIT_DEG + TOL_DEG)
    flat = off_bed & (overhang > FLAT_DEG)
    visible = off_bed & (area >= SLIVER_MM2)

    lo, hi = verts.min(axis=0), verts.max(axis=0)
    return {
        "triangles": int(triangles),
        "volume": volume,
        "parts": parts,
        "edges_paired": edges_paired,
        "steepest": float(overhang[visible].max()) if visible.any() else 0.0,
        "steep_area": float(area[steep].sum()),
        "flat_area": float(area[flat].sum()),
        "top_area": float(area[at_top].sum()),
        "bbox": [round(float(x), 4) for x in hi - lo],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--openscad", default=os.environ.get("OPENSCAD", "openscad"))
    ap.add_argument("--presets", action="store_true", help="saved presets only, skip the matrix")
    ap.add_argument("--only", help="only configurations whose name contains this text")
    ap.add_argument("--stl", help="measure this STL instead of rendering")
    ap.add_argument("--keep", help="keep rendered STLs in this folder")
    args = ap.parse_args()

    if args.stl:
        print(json.dumps(measure(read_stl(args.stl)), indent=2))
        return 0

    if shutil.which(args.openscad) is None and not os.path.exists(args.openscad):
        sys.exit(f"OpenSCAD not found at '{args.openscad}'. Pass --openscad or set OPENSCAD.")
    version = subprocess.run([args.openscad, "--version"], capture_output=True, text=True)
    print((version.stdout + version.stderr).strip() + "\n")

    saved = load_presets()
    jobs = [(f"preset: {name}", name, None, str(p.get("Support_free", "true")).lower() == "true")
            for name, p in saved.items()]
    if not args.presets:
        jobs += [(name, None, o, o.get("Support_free", True)) for name, o in matrix()]
    if args.only:
        jobs = [j for j in jobs if args.only.lower() in j[0].lower()]

    outdir = args.keep or tempfile.mkdtemp(prefix="spike-verify-")
    os.makedirs(outdir, exist_ok=True)

    header = (f"{'configuration':<38} {'tris':>6} {'volume':>8} {'parts':>5} {'solid':>5} "
              f"{'steepest':>8} {'>45 area':>8} {'flat area':>9} {'top area':>8}  result")
    print(header)
    print("-" * len(header))
    failures = 0
    for i, (name, preset, overrides, support_free) in enumerate(jobs):
        out = os.path.join(outdir, f"{i:02d}.stl")
        try:
            log = render(args.openscad, out, preset, overrides)
            m = measure(read_stl(out))
        except RuntimeError as e:
            print(f"{name:<38} render failed: {e}")
            failures += 1
            continue
        solid = solid_verdict(log)
        if solid is None:
            solid = m["edges_paired"]
        problems = []
        if not solid:
            problems.append("not a clean solid")
        if m["parts"] != 1:
            problems.append(f"{m['parts']} parts")
        if support_free and m["steep_area"] > 0.005:
            problems.append("overhang past 45")
        failures += bool(problems)
        print(f"{name:<38} {m['triangles']:>6} {m['volume']:>8.0f} {m['parts']:>5} {'yes' if solid else 'NO':>5} "
              f"{m['steepest']:>8.1f} {m['steep_area']:>8.2f} {m['flat_area']:>9.2f} {m['top_area']:>8.2f}  "
              f"{'ok' if not problems else ', '.join(problems)}")

    print(f"\n{len(jobs) - failures} of {len(jobs)} passed")
    if args.keep:
        print(f"STLs kept in {outdir}")
    else:
        shutil.rmtree(outdir, ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
