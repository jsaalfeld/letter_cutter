#!/usr/bin/env python3
"""
letter_cutter.py — Generate STL cookie cutters with auto-bridges from a single letter.

Minimal toolchain: Python + fonttools + shapely + trimesh + numpy
Install:
  pip install -r requirements.txt

Usage examples:
  python letter_cutter.py -t A -o cutter_A.stl
  python letter_cutter.py -t Ä -f "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
  python letter_cutter.py -t A --size 60 --wall 1.8 --bridge 1.2 --lip-pos bottom --top-cap 1.0 -o cutter_A60.stl

Notes:
- Designed for single letters. For short words, run multiple times and arrange in your slicer.
- Bridges connect inner counters (holes) to the outer boundary so the clay piece doesn't have loose islands.
- Overlapping meshes are fine for slicers; no complex booleans are required.
"""

import argparse
import math
from typing import List, Tuple

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.flattenPen import FlattenPen

from shapely.geometry import Polygon, LineString, LinearRing
from shapely.ops import unary_union, nearest_points

import trimesh


def glyph_to_flat_contours(char: str, font_path: str, target_mm: float) -> List[np.ndarray]:
    """Return a list of flattened contours (Nx2 arrays) in mm for the given character."""
    font = TTFont(font_path)
    cmap = font.getBestCmap()
    codepoint = ord(char)
    if codepoint not in cmap:
        raise ValueError(f"Character {char!r} not found in font {font_path}")
    glyph_name = cmap[codepoint]

    glyph_set = font.getGlyphSet()
    glyph = glyph_set[glyph_name]

    # RecordingPen -> FlattenPen to approximate curves
    rec = RecordingPen()
    units_per_em = font["head"].unitsPerEm
    scale = target_mm / float(units_per_em)

    glyph.draw(rec, glyph_set)

    flat = RecordingPen()
    FlattenPen(flat, approximateSegmentLength=5, segmentLines=True).replay(rec.value)

    transformed = RecordingPen()
    tpen = TransformPen(transformed, (scale, 0, 0, -scale, 0, 0))  # scale and mirror Y
    flat.replay(tpen)

    contours: List[np.ndarray] = []
    current: List[Tuple[float, float]] = []

    for cmd, args in transformed.value:
        if cmd == "moveTo":
            if current:
                contours.append(np.array(current, dtype=float))
                current = []
            x, y = args[0]
            current.append((x, y))
        elif cmd == "lineTo":
            x, y = args[0]
            current.append((x, y))
        elif cmd == "closePath":
            if current:
                contours.append(np.array(current, dtype=float))
                current = []
        else:
            pass
    if current:
        contours.append(np.array(current, dtype=float))

    # Center around origin
    all_pts = np.vstack(contours) if contours else np.zeros((0, 2))
    if len(all_pts):
        minx, miny = all_pts.min(axis=0)
        maxx, maxy = all_pts.max(axis=0)
        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0
        contours = [c - np.array([cx, cy]) for c in contours]
    return contours


def signed_area(poly: np.ndarray) -> float:
    x = poly[:, 0]
    y = poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def contours_to_polygon(contours: List[np.ndarray]) -> Polygon:
    """Build a robust Shapely polygon using even-odd fill from contours."""
    if not contours:
        raise ValueError("No contours generated from glyph")

    outers = []
    holes = []
    for c in contours:
        ring = LinearRing(c)
        # Shapely's is_ccw is robust for orientation
        if not ring.is_ccw:
            outers.append(Polygon(ring))
        else:
            holes.append(Polygon(ring))

    if not outers:
        merged = unary_union([Polygon(LinearRing(c)) for c in contours]).buffer(0)
        return merged

    outer_union = unary_union(outers).buffer(0)
    holes_union = unary_union(holes).buffer(0) if holes else None

    final = outer_union.difference(holes_union).buffer(0) if holes_union else outer_union
    return final.buffer(0)


def ring_region_from_fill(fill_poly: Polygon, wall: float, clearance: float) -> Polygon:
    """Create cutter wall region: outer offset minus inner offset."""
    outer = fill_poly.buffer(wall, join_style=2)
    inner = fill_poly.buffer(clearance, join_style=2)
    return outer.difference(inner).buffer(0)


def bridges_for_holes(fill_poly: Polygon, ring_region: Polygon, bridge_w: float) -> Polygon:
    """Add bridges by connecting each interior hole to the exterior via the shortest path."""
    if fill_poly.is_empty or not isinstance(fill_poly, Polygon):
        return ring_region

    ex = fill_poly.exterior
    result = ring_region
    for hole in fill_poly.interiors:
        hole_line = LineString(hole.coords)
        ext_line = LineString(ex.coords)
        p1, p2 = nearest_points(hole_line, ext_line)
        seg = LineString([p1, p2])
        bridge_area = seg.buffer(bridge_w / 2.0, cap_style=2, join_style=2)
        bridge_clip = bridge_area.intersection(ring_region)
        result = unary_union([result, bridge_clip]).buffer(0)
    return result


def make_mesh_from_region(region: Polygon, z0: float, height: float) -> trimesh.Trimesh | None:
    if region.is_empty or height <= 0:
        return None
    mesh = trimesh.creation.extrude_polygon(region, height=height)
    mesh.apply_translation([0, 0, z0])
    return mesh


def main():
    ap = argparse.ArgumentParser(description="Generate STL cookie cutter with auto-bridges for counters (holes).")
    ap.add_argument("-t", "--text", required=True, help="Single character, e.g., 'A'")
    ap.add_argument("-f", "--font", default="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    help="Path to TTF/OTF font file")
    ap.add_argument("--size", type=float, default=50.0, help="Letter nominal size in mm (em height)")
    ap.add_argument("--wall", type=float, default=1.6, help="Wall thickness control in mm")
    ap.add_argument("--height", type=float, default=14.0, help="Wall height in mm (excl. base)")
    ap.add_argument("--edge", type=float, default=0.8, help="Sharp lip height in mm")
    ap.add_argument("--base", type=float, default=1.2, help="Base plate thickness in mm")
    ap.add_argument("--clearance", type=float, default=0.30, help="Inner clearance so clay releases, mm")
    ap.add_argument("--bridge", type=float, default=1.2, help="Bridge width in mm")
    ap.add_argument("--lip-pos", choices=["top", "bottom"], default="bottom",
                    help="Where to place the thin cutting lip. 'bottom' is recommended for clay.")
    ap.add_argument("--top-cap", type=float, default=0.0,
                    help="Optional reinforcement cap height at the very top in mm (adds a wider ring). 0 to disable.")
    ap.add_argument("-o", "--output", default=None, help="Output STL filename")
    ap.add_argument("--scale", type=float, default=1.00, help="Final uniform scale factor (e.g., 1.08 for shrinkage)")
    args = ap.parse_args()

    txt = args.text
    if len(txt) != 1:
        raise SystemExit("Please pass exactly one character for now. For words, run per letter.")

    contours = glyph_to_flat_contours(txt, args.font, args.size)
    fill_poly = contours_to_polygon(contours)

    # Base
    base_region = fill_poly.buffer(0.2, join_style=2)
    base_mesh = make_mesh_from_region(base_region, z0=0.0, height=args.base)

    # Ring region and bridges
    ring_region = ring_region_from_fill(fill_poly, wall=args.wall, clearance=args.clearance)
    ring_region = bridges_for_holes(fill_poly, ring_region, bridge_w=args.bridge)

    meshes = [m for m in [base_mesh] if m is not None]

    # Cutting lip placement
    if args.lip_pos == "bottom":
        # Thin lip at the bottom for cutting
        lip_outer = fill_poly.buffer(args.wall, join_style=2)
        lip_inner = fill_poly.buffer(max(args.wall - 0.6, 0.2), join_style=2)
        lip_region = lip_outer.difference(lip_inner).buffer(0)
        lip_mesh = make_mesh_from_region(lip_region, z0=args.base, height=args.edge)
        meshes.append(lip_mesh)

        # Main wall above the lip
        wall_mesh = make_mesh_from_region(ring_region, z0=args.base + args.edge, height=args.height - args.edge)
        meshes.append(wall_mesh)
    else:
        # Wall first
        wall_mesh = make_mesh_from_region(ring_region, z0=args.base, height=args.height - args.edge)
        meshes.append(wall_mesh)
        # Thin lip at the top
        lip_outer = fill_poly.buffer(args.wall, join_style=2)
        lip_inner = fill_poly.buffer(max(args.wall - 0.6, 0.2), join_style=2)
        lip_region = lip_outer.difference(lip_inner).buffer(0)
        lip_mesh = make_mesh_from_region(lip_region, z0=args.base + args.height - args.edge, height=args.edge)
        meshes.append(lip_mesh)

    # Optional top reinforcement cap: a slightly wider ring at the very top for hand comfort and rigidity
    if args.top_cap > 0:
        cap_outer = fill_poly.buffer(args.wall + 0.6, join_style=2)  # a bit wider than the wall
        cap_inner = fill_poly.buffer(args.clearance, join_style=2)   # same inner opening as wall
        cap_region = cap_outer.difference(cap_inner).buffer(0)
        cap_mesh = make_mesh_from_region(cap_region, z0=args.base + args.height, height=args.top_cap)
        meshes.append(cap_mesh)

    combined = trimesh.util.concatenate([m for m in meshes if m is not None])

    if args.scale != 1.0:
        combined.apply_scale(args.scale)

    out = args.output or f"cutter_{txt}.stl"
    combined.export(out)
    print(f"✓ Wrote {out}")


if __name__ == "__main__":
    main()
