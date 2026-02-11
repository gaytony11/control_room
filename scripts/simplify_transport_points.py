import json
import sys
from collections import defaultdict

if len(sys.argv) != 3:
    print("Usage: python simplify_transport_points.py input.geojson output.geojson")
    sys.exit(1)

inp, outp = sys.argv[1], sys.argv[2]

with open(inp, "r", encoding="utf-8") as f:
    data = json.load(f)

groups = defaultdict(list)

for f in data["features"]:
    name = (
        f["properties"].get("name")
        or f["properties"].get("iata")
        or f["properties"].get("icao")
        or "UNKNOWN"
    )
    groups[name].append(f)

simplified = {
    "type": "FeatureCollection",
    "features": []
}

for name, feats in groups.items():
    simplified["features"].append(feats[0])

with open(outp, "w", encoding="utf-8") as f:
    json.dump(simplified, f)

print(f"Reduced {len(data['features'])} → {len(simplified['features'])}")
