import json
import sys
from collections import defaultdict

if len(sys.argv) != 3:
    print("Usage: python simplify_airports.py input.geojson output.geojson")
    sys.exit(1)

inp, outp = sys.argv[1], sys.argv[2]

with open(inp, "r", encoding="utf-8") as f:
    data = json.load(f)

groups = defaultdict(list)

for feat in data["features"]:
    props = feat.get("properties", {})

    key = (
        props.get("iata")
        or props.get("icao")
        or props.get("name")
        or "UNKNOWN"
    )

    groups[key].append(feat)

def centroid(coords):
    xs, ys = zip(*coords)
    return [sum(xs) / len(xs), sum(ys) / len(ys)]

out = {
    "type": "FeatureCollection",
    "features": []
}

for key, feats in groups.items():
    # collect all point coordinates
    points = []
    for f in feats:
        geom = f["geometry"]
        if geom["type"] == "Point":
            points.append(geom["coordinates"])

    if not points:
        continue

    c = centroid(points)

    out["features"].append({
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": c
        },
        "properties": {
            "name": feats[0]["properties"].get("name", key),
            "iata": feats[0]["properties"].get("iata"),
            "icao": feats[0]["properties"].get("icao")
        }
    })

print(f"Reduced {len(data['features'])} → {len(out['features'])}")

with open(outp, "w", encoding="utf-8") as f:
    json.dump(out, f)
