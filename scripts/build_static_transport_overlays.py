#!/usr/bin/env python3
"""
Build compact static transport overlays for fast client-side rendering.

Inputs:
  data/osm_derived/gb_major_roads_lite.geojson
  data/osm_derived/gb_rail_lines_lite.geojson

Outputs:
  data/transport_static/roads_core.json
  data/transport_static/rail_core.json
  data/transport_static/rail_stations_core.json
  data/transport_static/manifest.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
OSM_DERIVED = ROOT / "data" / "osm_derived"
OUT_DIR = ROOT / "data" / "transport_static"

ROADS_IN = OSM_DERIVED / "gb_major_roads_lite.geojson"
RAIL_IN = OSM_DERIVED / "gb_rail_lines_lite.geojson"

ROADS_OUT = OUT_DIR / "roads_core.json"
RAIL_OUT = OUT_DIR / "rail_core.json"
STATIONS_OUT = OUT_DIR / "rail_stations_core.json"
MANIFEST_OUT = OUT_DIR / "manifest.json"


def _to_latlon_pairs(coords: Sequence[Sequence[float]]) -> List[List[float]]:
    out: List[List[float]] = []
    for p in coords:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        lng = float(p[0])
        lat = float(p[1])
        out.append([lat, lng])
    return out


def _rdp(points: List[List[float]], epsilon: float) -> List[List[float]]:
    if len(points) < 3:
        return points

    def perp_dist(pt: List[float], a: List[float], b: List[float]) -> float:
        x, y = pt[1], pt[0]
        x1, y1 = a[1], a[0]
        x2, y2 = b[1], b[0]
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
        t = 0 if t < 0 else 1 if t > 1 else t
        px = x1 + t * dx
        py = y1 + t * dy
        return ((x - px) ** 2 + (y - py) ** 2) ** 0.5

    first = points[0]
    last = points[-1]
    max_d = -1.0
    idx = -1
    for i in range(1, len(points) - 1):
        d = perp_dist(points[i], first, last)
        if d > max_d:
            max_d = d
            idx = i
    if max_d > epsilon and idx > 0:
        left = _rdp(points[: idx + 1], epsilon)
        right = _rdp(points[idx:], epsilon)
        return left[:-1] + right
    return [first, last]


def _simplify(points: List[List[float]], epsilon: float, max_points: int) -> List[List[float]]:
    if len(points) <= 2:
        return points
    simplified = _rdp(points, epsilon)
    if len(simplified) <= max_points:
        return simplified
    step = max(1, len(simplified) // max_points)
    out = simplified[::step]
    if out[-1] != simplified[-1]:
        out.append(simplified[-1])
    return out


def _iter_lines(geom: dict) -> Iterable[List[List[float]]]:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "LineString" and isinstance(coords, list):
        yield _to_latlon_pairs(coords)
    elif gtype == "MultiLineString" and isinstance(coords, list):
        for part in coords:
            if isinstance(part, list):
                yield _to_latlon_pairs(part)


def build_roads() -> List[dict]:
    raw = json.loads(ROADS_IN.read_text(encoding="utf-8"))
    features = raw.get("features", [])
    keep_types = {"motorway", "trunk", "primary", "secondary"}
    out: List[dict] = []
    for f in features:
        props = f.get("properties", {}) or {}
        hwy = str(props.get("highway", "")).lower()
        if hwy not in keep_types:
            continue
        name = str(props.get("name", "")).strip()
        for line in _iter_lines(f.get("geometry", {}) or {}):
            if len(line) < 2:
                continue
            simp = _simplify(line, epsilon=0.0009, max_points=64)
            if len(simp) < 2:
                continue
            out.append({
                "name": name,
                "type": hwy,
                "coords": simp,
            })
    return out[:3500]


def build_rail() -> Tuple[List[dict], List[dict]]:
    raw = json.loads(RAIL_IN.read_text(encoding="utf-8"))
    features = raw.get("features", [])
    keep_types = {"rail", "subway", "light_rail"}
    lines_out: List[dict] = []
    stations: dict[str, dict] = {}

    for f in features:
        props = f.get("properties", {}) or {}
        rtype = str(props.get("railway", "")).lower()
        if rtype not in keep_types:
            continue
        name = str(props.get("name", "")).strip()
        for line in _iter_lines(f.get("geometry", {}) or {}):
            if len(line) < 2:
                continue
            simp = _simplify(line, epsilon=0.0007, max_points=80)
            if len(simp) < 2:
                continue
            lines_out.append({
                "name": name,
                "type": rtype,
                "coords": simp,
            })
            # endpoint nodes as lightweight station-like anchors
            for endpoint in (simp[0], simp[-1]):
                lat, lon = endpoint
                key = f"{lat:.5f},{lon:.5f}"
                if key not in stations:
                    stations[key] = {
                        "name": name or "Rail Node",
                        "lat": lat,
                        "lon": lon,
                    }

    station_list = list(stations.values())[:2200]
    return lines_out[:4200], station_list


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    roads = build_roads()
    rail, stations = build_rail()

    ROADS_OUT.write_text(json.dumps({"routes": roads}, separators=(",", ":")), encoding="utf-8")
    RAIL_OUT.write_text(json.dumps({"routes": rail}, separators=(",", ":")), encoding="utf-8")
    STATIONS_OUT.write_text(json.dumps({"stations": stations}, separators=(",", ":")), encoding="utf-8")

    manifest = {
        "roads_routes": len(roads),
        "rail_routes": len(rail),
        "rail_nodes": len(stations),
        "source": {
            "roads": str(ROADS_IN.relative_to(ROOT)),
            "rail": str(RAIL_IN.relative_to(ROOT)),
        },
    }
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {ROADS_OUT.relative_to(ROOT)} ({len(roads)} routes)")
    print(f"Wrote {RAIL_OUT.relative_to(ROOT)} ({len(rail)} routes)")
    print(f"Wrote {STATIONS_OUT.relative_to(ROOT)} ({len(stations)} nodes)")
    print(f"Wrote {MANIFEST_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

