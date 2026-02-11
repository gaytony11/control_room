"""
Read every ONSPD multi_csv file and produce a single JSON lookup:
  { "BS15AH": {"lat": 51.4495, "lon": -2.5784}, ... }

Keys are uppercase postcodes with all whitespace stripped.
Rows with blank lat/long or terminated postcodes (doterm non-empty) are skipped.
"""

import csv, json, os, glob

SRC_DIR = os.path.join(
    os.path.dirname(__file__), "..",
    "data", "postcode_data", "ONSPD_MAY_2025", "Data", "multi_csv"
)
OUT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "postcodes.json"
)

lookup = {}

csv_files = sorted(glob.glob(os.path.join(SRC_DIR, "*.csv")))
print(f"Found {len(csv_files)} CSV files")

for i, path in enumerate(csv_files, 1):
    basename = os.path.basename(path)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            lat = row.get("lat", "").strip()
            lng = row.get("long", "").strip()
            pcd = row.get("pcd", "").strip()

            if not lat or not lng or not pcd:
                continue

            # Skip terminated postcodes
            if row.get("doterm", "").strip():
                continue

            try:
                lat_f = float(lat)
                lon_f = float(lng)
            except ValueError:
                continue

            key = pcd.upper().replace(" ", "")
            lookup[key] = {"lat": round(lat_f, 6), "lon": round(lon_f, 6)}
            count += 1

    print(f"  [{i}/{len(csv_files)}] {basename}: +{count} postcodes  (total: {len(lookup)})")

print(f"\nWriting {len(lookup)} postcodes to {OUT_FILE} ...")
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(lookup, f, separators=(",", ":"))

size_mb = os.path.getsize(OUT_FILE) / (1024 * 1024)
print(f"Done — {size_mb:.1f} MB")
