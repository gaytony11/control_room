import json
import sys
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform


def convert_geojson(
    input_file,
    output_file,
    src_crs="EPSG:27700",
    dst_crs="EPSG:4326"
):
    transformer = Transformer.from_crs(
        src_crs,
        dst_crs,
        always_xy=True
    )

    def project(x, y, z=None):
        return transformer.transform(x, y)

    with open(input_file, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    if geojson.get("type") != "FeatureCollection":
        raise RuntimeError("Input is not a GeoJSON FeatureCollection")

    out_features = []

    for feature in geojson["features"]:
        geom = feature.get("geometry")
        if geom is None:
            out_features.append(feature)
            continue

        shp = shape(geom)
        shp_out = transform(project, shp)

        out_features.append({
            "type": "Feature",
            "id": feature.get("id"),
            "properties": feature.get("properties", {}),
            "geometry": mapping(shp_out)
        })

    out_geojson = {
        "type": "FeatureCollection",
        "features": out_features
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(out_geojson, f, ensure_ascii=False)

    print(f"✔ Converted to WGS84: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage:")
        print("python convert_coordinates.py <input.geojson> <output.geojson>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        sys.exit(1)

    convert_geojson(input_path, output_path)
