"""
Split postcodes.json into per-area files under data/postcodes/
e.g. data/postcodes/BS.json, data/postcodes/SW.json, etc.

Also writes data/postcodes_index.json listing every area prefix.
"""

import json, os, re

SRC = os.path.join(os.path.dirname(__file__), "..", "data", "postcodes.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "postcodes")
INDEX_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "postcodes_index.json")

os.makedirs(OUT_DIR, exist_ok=True)

print("Loading postcodes.json ...")
with open(SRC, encoding="utf-8") as f:
    data = json.load(f)

print(f"Loaded {len(data)} postcodes, splitting by area prefix ...")

# Group by area prefix (leading letters before any digit)
buckets = {}
for key, val in data.items():
    m = re.match(r"^([A-Z]{1,2})", key)
    if not m:
        continue
    prefix = m.group(1)
    if prefix not in buckets:
        buckets[prefix] = {}
    buckets[prefix][key] = val

# Write each bucket
for prefix in sorted(buckets):
    path = os.path.join(OUT_DIR, f"{prefix}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(buckets[prefix], f, separators=(",", ":"))
    size_kb = os.path.getsize(path) / 1024
    print(f"  {prefix}.json — {len(buckets[prefix]):>6} postcodes  ({size_kb:.0f} KB)")

# Write index
index = sorted(buckets.keys())
with open(INDEX_FILE, "w", encoding="utf-8") as f:
    json.dump(index, f)

print(f"\nDone — {len(index)} area files written to {OUT_DIR}")
