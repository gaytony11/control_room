#!/usr/bin/env python3
"""
Build lightweight thematic overlays from a large OSM PBF.

Why:
- The raw GB PBF is too large for browser delivery.
- This script extracts only operationally useful themes and writes compact GeoJSON.

Dependencies:
  pip install pyrosm geopandas shapely pyproj

Example:
  python scripts/build_osm_layers.py ^
    --pbf "data/OS Map/great-britain-260211.osm.pbf" ^
    --out "data/osm_derived" ^
    --simplify 25
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict


def _fail_missing_deps() -> None:
    print(
        "Missing dependencies. Install with:\n"
        "  pip install pyrosm geopandas shapely pyproj",
        file=sys.stderr,
    )
    raise SystemExit(2)


try:
    import geopandas as gpd
    import pandas as pd
    from pyrosm import OSM
except Exception:
    _fail_missing_deps()


MAJOR_ROAD_TAGS = [
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
]

RAIL_TAGS = [
    "rail",
    "subway",
    "light_rail",
    "tram",
]

PLACE_TAGS = [
    "city",
    "town",
    "village",
    "hamlet",
    "suburb",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract compact OSM overlays from PBF.")
    parser.add_argument("--pbf", required=True, help="Path to .osm.pbf source file.")
    parser.add_argument(
        "--out",
        default="data/osm_derived",
        help="Output directory for extracted overlays.",
    )
    parser.add_argument(
        "--simplify",
        type=float,
        default=25.0,
        help="Geometry simplify tolerance in meters (for line layers).",
    )
    return parser.parse_args()


def simplify_lines(gdf: gpd.GeoDataFrame, tolerance_m: float) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    line_like = gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])].copy()
    other = gdf[~gdf.index.isin(line_like.index)].copy()
    if not line_like.empty:
        simplified = line_like.to_crs(27700)
        simplified.geometry = simplified.geometry.simplify(tolerance=tolerance_m, preserve_topology=True)
        line_like = simplified.to_crs(4326)
    if other.empty:
        return line_like
    return gpd.GeoDataFrame(
        pd.concat([line_like, other], ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )


def compact_columns(gdf: gpd.GeoDataFrame, columns: list[str]) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    keep = [c for c in columns if c in gdf.columns]
    keep.append("geometry")
    return gdf[keep].copy()


def write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> Dict[str, int]:
    if gdf.empty:
        payload = {"type": "FeatureCollection", "features": []}
        path.write_text(json.dumps(payload), encoding="utf-8")
    else:
        gdf.to_file(path, driver="GeoJSON")
    return {
        "features": int(len(gdf)),
        "bytes": int(path.stat().st_size),
    }


def main() -> None:
    args = parse_args()
    pbf = Path(args.pbf)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not pbf.exists():
        raise SystemExit(f"PBF not found: {pbf}")

    print(f"Loading OSM PBF: {pbf}")
    osm = OSM(str(pbf))

    print("Extracting major roads...")
    roads = osm.get_data_by_custom_criteria(
        custom_filter={"highway": MAJOR_ROAD_TAGS},
        filter_type="keep",
        keep_nodes=False,
        keep_ways=True,
        keep_relations=False,
    )
    roads = roads.set_crs(4326, allow_override=True)
    roads = compact_columns(roads, ["name", "ref", "highway", "maxspeed"])
    roads = simplify_lines(roads, args.simplify)

    print("Extracting rail lines...")
    rail = osm.get_data_by_custom_criteria(
        custom_filter={"railway": RAIL_TAGS},
        filter_type="keep",
        keep_nodes=False,
        keep_ways=True,
        keep_relations=False,
    )
    rail = rail.set_crs(4326, allow_override=True)
    rail = compact_columns(rail, ["name", "operator", "railway"])
    rail = simplify_lines(rail, args.simplify)

    print("Extracting populated places...")
    places = osm.get_data_by_custom_criteria(
        custom_filter={"place": PLACE_TAGS},
        filter_type="keep",
        keep_nodes=True,
        keep_ways=False,
        keep_relations=False,
    )
    places = places.set_crs(4326, allow_override=True)
    places = compact_columns(places, ["name", "place", "population"])

    manifest = {
        "source_pbf": str(pbf),
        "outputs": {},
    }

    roads_path = out_dir / "gb_major_roads.geojson"
    rail_path = out_dir / "gb_rail_lines.geojson"
    places_path = out_dir / "gb_places.geojson"

    manifest["outputs"]["major_roads"] = write_geojson(roads, roads_path)
    manifest["outputs"]["rail_lines"] = write_geojson(rail, rail_path)
    manifest["outputs"]["places"] = write_geojson(places, places_path)

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nDone.")
    print(f"- {roads_path}")
    print(f"- {rail_path}")
    print(f"- {places_path}")
    print(f"- {manifest_path}")


if __name__ == "__main__":
    main()
