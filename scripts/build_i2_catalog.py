import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def parse_schema(schema_path: Path):
    root = ET.parse(schema_path).getroot()

    entities = []
    links = []

    for entity in root.findall(".//{*}EntityType"):
        e_id = entity.attrib.get("Id", "")
        e_name = entity.attrib.get("DisplayName", "")
        e_icon = entity.attrib.get("Icon", "")
        properties = []
        for prop in entity.findall(".//{*}PropertyType"):
            values = [pv.attrib.get("Value", "") for pv in prop.findall(".//{*}PossibleValue")]
            properties.append(
                {
                    "property_id": prop.attrib.get("Id", ""),
                    "property_name": prop.attrib.get("DisplayName", ""),
                    "logical_type": prop.attrib.get("LogicalType", ""),
                    "mandatory": prop.attrib.get("Mandatory", ""),
                    "max_len": prop.attrib.get("MaximumLengthChars", ""),
                    "semantic_type_id": prop.attrib.get("SemanticTypeId", ""),
                    "possible_values": values,
                }
            )
        entities.append({"entity_id": e_id, "entity_name": e_name, "icon": e_icon, "properties": properties})

    for link in root.findall(".//{*}LinkType"):
        l_id = link.attrib.get("Id", "")
        l_name = link.attrib.get("DisplayName", "")
        properties = []
        for prop in link.findall(".//{*}PropertyType"):
            values = [pv.attrib.get("Value", "") for pv in prop.findall(".//{*}PossibleValue")]
            properties.append(
                {
                    "property_id": prop.attrib.get("Id", ""),
                    "property_name": prop.attrib.get("DisplayName", ""),
                    "logical_type": prop.attrib.get("LogicalType", ""),
                    "mandatory": prop.attrib.get("Mandatory", ""),
                    "max_len": prop.attrib.get("MaximumLengthChars", ""),
                    "semantic_type_id": prop.attrib.get("SemanticTypeId", ""),
                    "possible_values": values,
                }
            )
        links.append({"link_id": l_id, "link_name": l_name, "properties": properties})

    return entities, links


def write_flat_catalogs(out_dir: Path, entities: list, links: list):
    out_dir.mkdir(parents=True, exist_ok=True)

    entities_json = out_dir / "entity_catalog.json"
    links_json = out_dir / "link_catalog.json"
    entities_csv = out_dir / "entity_catalog.csv"
    links_csv = out_dir / "link_catalog.csv"

    entities_json.write_text(json.dumps(entities, indent=2), encoding="utf-8")
    links_json.write_text(json.dumps(links, indent=2), encoding="utf-8")

    with entities_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "entity_id",
                "entity_name",
                "icon",
                "property_id",
                "property_name",
                "logical_type",
                "mandatory",
                "max_len",
                "semantic_type_id",
                "possible_values_count",
                "possible_values",
            ],
        )
        w.writeheader()
        for e in entities:
            for p in e["properties"]:
                w.writerow(
                    {
                        "entity_id": e["entity_id"],
                        "entity_name": e["entity_name"],
                        "icon": e["icon"],
                        "property_id": p["property_id"],
                        "property_name": p["property_name"],
                        "logical_type": p["logical_type"],
                        "mandatory": p["mandatory"],
                        "max_len": p["max_len"],
                        "semantic_type_id": p["semantic_type_id"],
                        "possible_values_count": len(p["possible_values"]),
                        "possible_values": " | ".join(p["possible_values"]),
                    }
                )

    with links_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "link_id",
                "link_name",
                "property_id",
                "property_name",
                "logical_type",
                "mandatory",
                "max_len",
                "semantic_type_id",
                "possible_values_count",
                "possible_values",
            ],
        )
        w.writeheader()
        for l in links:
            for p in l["properties"]:
                w.writerow(
                    {
                        "link_id": l["link_id"],
                        "link_name": l["link_name"],
                        "property_id": p["property_id"],
                        "property_name": p["property_name"],
                        "logical_type": p["logical_type"],
                        "mandatory": p["mandatory"],
                        "max_len": p["max_len"],
                        "semantic_type_id": p["semantic_type_id"],
                        "possible_values_count": len(p["possible_values"]),
                        "possible_values": " | ".join(p["possible_values"]),
                    }
                )

    return {
        "entities_json": str(entities_json),
        "links_json": str(links_json),
        "entities_csv": str(entities_csv),
        "links_csv": str(links_csv),
    }


def main():
    base = Path("data") / "i2 Specs"
    schema_path = base / "Offline Cache" / "Schema" / "InformationStore.dat"
    out_dir = base / "parsed"

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    entities, links = parse_schema(schema_path)
    outputs = write_flat_catalogs(out_dir, entities, links)

    print("Generated i2 catalog artifacts:")
    for k, v in outputs.items():
        print(f"- {k}: {v}")
    print(f"Entity types: {len(entities)}")
    print(f"Link types: {len(links)}")
    print(f"Entity properties: {sum(len(e['properties']) for e in entities)}")
    print(f"Link properties: {sum(len(l['properties']) for l in links)}")


if __name__ == "__main__":
    main()
