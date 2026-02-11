import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter


def local_name(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def parse_xml_file(path: str, encoding: str | None = None):
    with open(path, "rb") as f:
        raw = f.read()
    if encoding:
        text = raw.decode(encoding, errors="ignore")
        return ET.fromstring(text)
    return ET.fromstring(raw.decode("utf-8", errors="ignore"))


def parse_import_spec(path: str) -> dict:
    root = parse_xml_file(path, encoding="utf-16")
    data = root.find(".//{*}Data")
    source_type = data.attrib.get("Source") if data is not None else ""
    entities = []
    links = []
    user_columns = []
    date_formats = []
    actions = set()
    referenced_columns = set()

    for uc in root.findall(".//{*}UserColumn"):
        cid = uc.attrib.get("ColumnId")
        if cid:
            user_columns.append(cid)

    for dt in root.findall(".//{*}DateTimeFormat"):
        date_formats.append(
            {
                "column": dt.attrib.get("ColumnId", ""),
                "format": dt.attrib.get("Format", ""),
            }
        )

    for action in root.findall(".//{*}Actions/*"):
        actions.add(local_name(action.tag))

    for expr in root.findall(".//{*}ColumnExpression"):
        if expr.text:
            for match in re.findall(r"\[([^\]]+)\]", expr.text):
                referenced_columns.add(match)

    for entity in root.findall(".//{*}Entity"):
        item_type = entity.find(".//{*}ItemType")
        db_props = []
        for prop in entity.findall(".//{*}DatabaseProperty"):
            db_props.append(
                {
                    "id": prop.attrib.get("Identifier", ""),
                    "name": prop.attrib.get("DisplayName", ""),
                }
            )
        entities.append(
            {
                "entity_id": entity.attrib.get("EntityId", ""),
                "type_id": item_type.attrib.get("Identifier", "") if item_type is not None else "",
                "type_name": item_type.attrib.get("DisplayName", "") if item_type is not None else "",
                "property_count": len(db_props),
                "properties": db_props,
            }
        )

    for link in root.findall(".//{*}Link"):
        item_type = link.find(".//{*}ItemType")
        db_props = []
        for prop in link.findall(".//{*}DatabaseProperty"):
            db_props.append(
                {
                    "id": prop.attrib.get("Identifier", ""),
                    "name": prop.attrib.get("DisplayName", ""),
                }
            )
        links.append(
            {
                "link_id": link.attrib.get("LinkId", ""),
                "type_id": item_type.attrib.get("Identifier", "") if item_type is not None else "",
                "type_name": item_type.attrib.get("DisplayName", "") if item_type is not None else "",
                "property_count": len(db_props),
                "properties": db_props,
            }
        )

    identity_type_ids = []
    for ident in root.findall(".//{*}ItemTypeIdentity"):
        tid = ident.attrib.get("TypeId")
        if tid:
            identity_type_ids.append(tid)

    return {
        "file": os.path.basename(path),
        "source_type": source_type,
        "entities": entities,
        "links": links,
        "user_columns": sorted(set(user_columns)),
        "date_formats": date_formats,
        "actions": sorted(actions),
        "referenced_columns": sorted(referenced_columns),
        "identity_type_ids": sorted(set(identity_type_ids)),
    }


def parse_cfs(path: str) -> dict:
    root = parse_xml_file(path, encoding="utf-8")
    rules = []
    for rule in root.findall(".//FormattingRule"):
        target_el = rule.find("./Target/*")
        style_el = rule.find("./Style/*")
        param_el = rule.find("./Parameter/*")
        rules.append(
            {
                "target": target_el.tag if target_el is not None else "",
                "style": style_el.tag if style_el is not None else "",
                "parameter": param_el.tag if param_el is not None else "",
            }
        )
    details = root.find(".//Details")
    subject = ""
    if details is not None:
        subject_el = details.find("Subject")
        if subject_el is not None:
            subject = subject_el.attrib.get("Value", "")
    return {"file": os.path.basename(path), "subject": subject, "rule_count": len(rules), "rules": rules}


def parse_match_rules(path: str) -> dict:
    root = ET.parse(path).getroot()
    rules = []
    operators = Counter()
    normalizations = Counter()

    for el in root.iter():
        ln = local_name(el.tag)
        if ln == "matchRule":
            rules.append(
                {
                    "display_name": el.attrib.get("displayName", ""),
                    "item_type_id": el.attrib.get("itemTypeId", ""),
                    "active": el.attrib.get("active", ""),
                }
            )
        elif ln == "operator" and el.text:
            operators[el.text] += 1
        elif ln == "normalization" and el.text:
            normalizations[el.text] += 1

    return {
        "file": os.path.basename(path),
        "rule_count": len(rules),
        "rules": rules,
        "operators": dict(operators),
        "normalizations": dict(normalizations),
    }


def parse_information_store(path: str) -> dict:
    root = ET.parse(path).getroot()
    entity_types = []
    link_types = []
    labels = []

    for entity in root.findall(".//{*}EntityType"):
        entity_types.append({"id": entity.attrib.get("Id", ""), "name": entity.attrib.get("DisplayName", "")})
    for link in root.findall(".//{*}LinkType"):
        link_types.append({"id": link.attrib.get("Id", ""), "name": link.attrib.get("DisplayName", "")})
    for label in root.findall(".//{*}LabelDefinition"):
        labels.append({"item_type_id": label.attrib.get("ItemTypeId", "")})

    return {
        "entity_type_count": len(entity_types),
        "link_type_count": len(link_types),
        "entity_types": entity_types,
        "link_types": link_types,
        "label_definition_count": len(labels),
    }


def main():
    parser = argparse.ArgumentParser(description="Extract useful i2 spec artifacts into JSON.")
    parser.add_argument(
        "--base-dir",
        default=r"data\i2 Specs",
        help="Base directory containing i2 specs",
    )
    parser.add_argument(
        "--out-dir",
        default=r"data\i2 Specs\parsed",
        help="Output directory for parsed JSON summaries",
    )
    args = parser.parse_args()

    base_dir = os.path.abspath(args.base_dir)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    import_specs_dir = os.path.join(base_dir, "Import Specifications")
    cfs_dirs = [
        os.path.join(base_dir, "Conditional Formatting"),
        os.path.join(base_dir, "Conditional Formatting Specifications"),
    ]
    match_files = [
        os.path.join(base_dir, "Matching Settings", "cached-system-match-rules.xml"),
        os.path.join(base_dir, "Matching Settings", "cached-fmr-match-rules.xml"),
    ]
    schema_file = os.path.join(base_dir, "Offline Cache", "Schema", "InformationStore.dat")

    import_specs = []
    if os.path.isdir(import_specs_dir):
        for name in sorted(os.listdir(import_specs_dir)):
            if name.lower().endswith(".oimp"):
                import_specs.append(parse_import_spec(os.path.join(import_specs_dir, name)))

    formatting_specs = []
    for cfs_dir in cfs_dirs:
        if not os.path.isdir(cfs_dir):
            continue
        for name in sorted(os.listdir(cfs_dir)):
            if name.lower().endswith(".cfs"):
                formatting_specs.append(parse_cfs(os.path.join(cfs_dir, name)))

    match_rules = []
    for file_path in match_files:
        if os.path.exists(file_path):
            match_rules.append(parse_match_rules(file_path))

    schema_summary = {}
    if os.path.exists(schema_file):
        schema_summary = parse_information_store(schema_file)

    with open(os.path.join(out_dir, "import_specs_summary.json"), "w", encoding="utf-8") as f:
        json.dump(import_specs, f, indent=2)
    with open(os.path.join(out_dir, "formatting_rules_summary.json"), "w", encoding="utf-8") as f:
        json.dump(formatting_specs, f, indent=2)
    with open(os.path.join(out_dir, "matching_rules_summary.json"), "w", encoding="utf-8") as f:
        json.dump(match_rules, f, indent=2)
    with open(os.path.join(out_dir, "schema_summary.json"), "w", encoding="utf-8") as f:
        json.dump(schema_summary, f, indent=2)

    print(f"Wrote parsed i2 summaries to: {out_dir}")
    print(f"- Import specs: {len(import_specs)}")
    print(f"- Formatting specs: {len(formatting_specs)}")
    print(f"- Match rule files: {len(match_rules)}")
    if schema_summary:
        print(f"- Entity types: {schema_summary.get('entity_type_count', 0)}")
        print(f"- Link types: {schema_summary.get('link_type_count', 0)}")


if __name__ == "__main__":
    main()
