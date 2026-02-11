import json
import sys

if len(sys.argv) != 3:
    print("Usage: python parse_global_airports.py input.txt output.geojson")
    sys.exit(1)

input_file = sys.argv[1]
output_file = sys.argv[2]

features = []

with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        line = line.strip()
        if not line or ":" not in line:
            continue

        parts = line.split(":")

        # We need at least ICAO + lat + lon
        if len(parts) < 5:
            continue

        try:
            icao = parts[0].strip()
            iata = parts[1].strip()
            airport_name = parts[3].strip()
            country = parts[4].strip()

            # ✅ LAT/LON ARE ALWAYS THE LAST TWO FIELDS
            lat = float(parts[-2])
            lon = float(parts[-1])

            # Skip junk rows
            if lat == 0.0 or lon == 0.0:
                continue

            features.append({
                "type": "Feature",
                "properties": {
                    "icao": icao,
                    "iata": None if iata == "N/A" else iata,
                    "name": airport_name,
                    "country": country,
                    "type": "airport"
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                }
            })

        except Exception:
            continue

geojson = {
    "type": "FeatureCollection",
    "features": features
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(geojson, f, indent=2)

print(f"✔ Written {len(features)} airports to {output_file}")
