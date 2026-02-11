import csv
import json
import os
import sys
from pathlib import Path

# ================== CONFIG ==================

INPUT_CSV = Path(
    r"data/companies_house/BasicCompanyDataAsOneFile-2026-02-01/BasicCompanyDataAsOneFile-2026-02-01.csv"
)

OUTPUT_DIR = Path("data/companies_house_subsets")
INDEX_FILE = Path("data/companies_house_index.json")

ROWS_PER_FILE = 100_000
ENCODING = "utf-8-sig"

# ================== SETUP ==================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if not INDEX_FILE.exists():
    INDEX_FILE.write_text("[]", encoding="utf-8")

def chunk_filename(start, end):
    return OUTPUT_DIR / f"companies_{start:06d}_{end:06d}.json"

def load_index():
    return json.loads(INDEX_FILE.read_text(encoding="utf-8"))

def save_index(index):
    INDEX_FILE.write_text(json.dumps(index, indent=2), encoding="utf-8")

# ================== MAIN ==================

def main():
    print("▶ Starting Companies House CSV split")
    print(f"▶ Input: {INPUT_CSV}")
    print(f"▶ Output dir: {OUTPUT_DIR}")
    print(f"▶ Rows per file: {ROWS_PER_FILE:,}\n")

    index = load_index()
    existing_ranges = {(e["start"], e["end"]) for e in index}

    total_rows = 0
    current_chunk = []
    chunk_start = 0

    with INPUT_CSV.open("r", encoding=ENCODING, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            current_chunk.append(row)
            total_rows += 1

            # When chunk full → write
            if len(current_chunk) >= ROWS_PER_FILE:
                chunk_end = chunk_start + ROWS_PER_FILE - 1
                out_file = chunk_filename(chunk_start, chunk_end)

                if (chunk_start, chunk_end) not in existing_ranges:
                    out_file.write_text(
                        json.dumps(current_chunk, ensure_ascii=False),
                        encoding="utf-8"
                    )

                    index.append({
                        "start": chunk_start,
                        "end": chunk_end,
                        "file": str(out_file).replace("\\", "/"),
                        "rows": len(current_chunk)
                    })

                    save_index(index)

                print(
                    f"✔ Written rows {chunk_start:,} → {chunk_end:,} "
                    f"(total processed: {total_rows:,})"
                )

                current_chunk = []
                chunk_start = total_rows

            # Progress ping every 25k rows
            if total_rows % 25_000 == 0:
                print(f"… processed {total_rows:,} rows")

        # Write remainder
        if current_chunk:
            chunk_end = chunk_start + len(current_chunk) - 1
            out_file = chunk_filename(chunk_start, chunk_end)

            out_file.write_text(
                json.dumps(current_chunk, ensure_ascii=False),
                encoding="utf-8"
            )

            index.append({
                "start": chunk_start,
                "end": chunk_end,
                "file": str(out_file).replace("\\", "/"),
                "rows": len(current_chunk)
            })

            save_index(index)

            print(
                f"✔ Final write rows {chunk_start:,} → {chunk_end:,} "
                f"(total processed: {total_rows:,})"
            )

    print("\n✅ DONE")
    print(f"Total rows processed: {total_rows:,}")
    print(f"Total files written: {len(index)}")

# ================== ENTRY ==================

if __name__ == "__main__":
    main()
