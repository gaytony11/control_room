import argparse
import csv
import json
import os
import re
import unicodedata
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zipfile import ZipFile


I2_DEFAULT_BASE = Path("data") / "i2 Specs"


@dataclass
class DateFormatSpec:
    column: str
    fmt: str


@dataclass
class PropertyMap:
    property_id: str
    property_name: str
    expression: str
    blank_handling: str


@dataclass
class EntityTemplate:
    entity_id: str
    type_id: str
    type_name: str
    identity_expression: str = ""
    properties: List[PropertyMap] = field(default_factory=list)


@dataclass
class LinkTemplate:
    link_id: str
    from_entity_id: str
    to_entity_id: str
    type_id: str
    type_name: str
    properties: List[PropertyMap] = field(default_factory=list)


@dataclass
class UserColumn:
    column_id: str
    expression: str


@dataclass
class ColumnAction:
    column_id: str
    action: str
    order: int
    args: Dict[str, str]


@dataclass
class IdentityRule:
    type_id: str
    criteria_property_ids: List[str]


@dataclass
class MatchCondition:
    property_id: str
    operator: str
    value: Optional[str]
    normalizations: List[str]


@dataclass
class MatchRule:
    item_type_id: str
    display_name: str
    conditions: List[MatchCondition]


@dataclass
class ImportTemplate:
    file_name: str
    source_type: str
    row_header_index: int
    exclude_ranges: List[Tuple[int, int]]
    ignore_rows_starting_with: str
    delimiters: str
    user_columns: List[UserColumn]
    column_actions: List[ColumnAction]
    date_formats: List[DateFormatSpec]
    entities: List[EntityTemplate]
    links: List[LinkTemplate]
    identity_rules: Dict[str, IdentityRule]


def local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def parse_xml_with_fallback(path: Path) -> ET.Element:
    raw = path.read_bytes()
    # i2 specs are commonly UTF-16; some are UTF-8
    for enc in ("utf-16", "utf-8", "windows-1252"):
        try:
            text = raw.decode(enc)
            return ET.fromstring(text)
        except Exception:
            continue
    # final fallback
    return ET.fromstring(raw.decode("utf-8", errors="ignore"))


def find_text(node: Optional[ET.Element], path: str, default: str = "") -> str:
    if node is None:
        return default
    child = node.find(path)
    if child is None:
        return default
    return child.text or default


def find_text_or_value(node: Optional[ET.Element], path: str, default: str = "") -> str:
    if node is None:
        return default
    child = node.find(path)
    if child is None:
        return default
    return child.attrib.get("Value", "") or (child.text or default)


def parse_import_template(path: Path) -> ImportTemplate:
    root = parse_xml_with_fallback(path)

    data_node = root.find(".//{*}Data")
    source_type = data_node.attrib.get("Source", "File") if data_node is not None else "File"

    row_header_node = root.find(".//{*}RowContainingColumnIdentifiers")
    row_header_index = int(row_header_node.attrib.get("RowIndex", "1")) if row_header_node is not None else 1

    ignore_prefix_node = root.find(".//{*}RowDefinitions")
    ignore_rows_starting_with = ignore_prefix_node.attrib.get("IgnoreRowsStartingWith", "") if ignore_prefix_node is not None else ""

    exclude_ranges: List[Tuple[int, int]] = []
    for er in root.findall(".//{*}ExcludeRows"):
        raw_range = er.attrib.get("Range", "").strip()
        if "-" in raw_range:
            a, b = raw_range.split("-", 1)
            try:
                exclude_ranges.append((int(a), int(b)))
            except ValueError:
                pass

    delimiter_node = root.find(".//{*}DelimitedColumns")
    delimiters = delimiter_node.attrib.get("Delimiters", ",") if delimiter_node is not None else ","
    if delimiters == "&#x9;" or delimiters == "\t":
        delimiters = "\t"

    user_columns: List[UserColumn] = []
    for uc in root.findall(".//{*}UserColumn"):
        user_columns.append(
            UserColumn(
                column_id=uc.attrib.get("ColumnId", ""),
                expression=find_text(uc, ".//{*}ColumnExpression", ""),
            )
        )

    column_actions: List[ColumnAction] = []
    for col in root.findall(".//{*}Column"):
        col_id = col.attrib.get("ColumnId", "")
        actions_node = col.find(".//{*}Actions")
        if actions_node is None:
            continue
        for action in list(actions_node):
            args = dict(action.attrib)
            # keep nested args where needed
            for nested in action:
                args[f"{local(nested.tag)}.{','.join(nested.attrib.keys())}"] = "|".join(nested.attrib.values())
                for nn in nested:
                    args[f"{local(nested.tag)}.{local(nn.tag)}"] = "|".join(nn.attrib.values())
            order = int(action.attrib.get("Order", "9999"))
            column_actions.append(
                ColumnAction(
                    column_id=col_id,
                    action=local(action.tag),
                    order=order,
                    args=args,
                )
            )

    date_formats: List[DateFormatSpec] = []
    for dt in root.findall(".//{*}DateTimeFormat"):
        date_formats.append(
            DateFormatSpec(
                column=dt.attrib.get("ColumnId", ""),
                fmt=dt.attrib.get("Format", ""),
            )
        )

    entities: List[EntityTemplate] = []
    for e in root.findall(".//{*}Entity"):
        item_type = e.find(".//{*}ItemType")
        type_id = item_type.attrib.get("Identifier", "") if item_type is not None else ""
        type_name = (
            item_type.attrib.get("DisplayName", "")
            if item_type is not None
            else find_text_or_value(e, ".//{*}Type/{*}Text", "Unknown")
        )
        identity_expression = find_text(e, ".//{*}Identity/{*}ColumnExpression", "")
        props: List[PropertyMap] = []
        for p in e.findall(".//{*}DatabaseProperty"):
            expr_node = p.find(".//{*}ColumnExpression")
            expr = expr_node.text if expr_node is not None and expr_node.text else ""
            blank_handling = expr_node.attrib.get("BlankHandling", "") if expr_node is not None else ""
            props.append(
                PropertyMap(
                    property_id=p.attrib.get("Identifier", ""),
                    property_name=p.attrib.get("DisplayName", ""),
                    expression=expr,
                    blank_handling=blank_handling,
                )
            )
        entities.append(
            EntityTemplate(
                entity_id=e.attrib.get("EntityId", ""),
                type_id=type_id,
                type_name=type_name,
                identity_expression=identity_expression,
                properties=props,
            )
        )

    links: List[LinkTemplate] = []
    for l in root.findall(".//{*}Link"):
        item_type = l.find(".//{*}ItemType")
        type_id = item_type.attrib.get("Identifier", "") if item_type is not None else ""
        type_name = (
            item_type.attrib.get("DisplayName", "")
            if item_type is not None
            else find_text_or_value(l, ".//{*}Type/{*}Text", "Link")
        )
        props: List[PropertyMap] = []
        for p in l.findall(".//{*}DatabaseProperty"):
            expr_node = p.find(".//{*}ColumnExpression")
            expr = expr_node.text if expr_node is not None and expr_node.text else ""
            blank_handling = expr_node.attrib.get("BlankHandling", "") if expr_node is not None else ""
            props.append(
                PropertyMap(
                    property_id=p.attrib.get("Identifier", ""),
                    property_name=p.attrib.get("DisplayName", ""),
                    expression=expr,
                    blank_handling=blank_handling,
                )
            )
        links.append(
            LinkTemplate(
                link_id=l.attrib.get("LinkId", ""),
                from_entity_id=l.attrib.get("FromEntityId", ""),
                to_entity_id=l.attrib.get("ToEntityId", ""),
                type_id=type_id,
                type_name=type_name,
                properties=props,
            )
        )

    identity_rules: Dict[str, IdentityRule] = {}
    for item_identity in root.findall(".//{*}ItemTypeIdentity"):
        type_id = item_identity.attrib.get("TypeId", "")
        prop_ids = []
        for prop in item_identity.findall(".//{*}Property"):
            pid = prop.attrib.get("TypeId", "")
            if pid:
                prop_ids.append(pid)
        if type_id:
            identity_rules[type_id] = IdentityRule(type_id=type_id, criteria_property_ids=prop_ids)

    return ImportTemplate(
        file_name=path.name,
        source_type=source_type,
        row_header_index=row_header_index,
        exclude_ranges=exclude_ranges,
        ignore_rows_starting_with=ignore_rows_starting_with,
        delimiters=delimiters,
        user_columns=user_columns,
        column_actions=sorted(column_actions, key=lambda a: (a.column_id, a.order)),
        date_formats=date_formats,
        entities=entities,
        links=links,
        identity_rules=identity_rules,
    )


def parse_match_rules(path: Path) -> Dict[str, List[MatchRule]]:
    if not path.exists():
        return {}
    root = ET.parse(path).getroot()
    out: Dict[str, List[MatchRule]] = {}
    for rule in root.iter():
        if local(rule.tag) != "matchRule":
            continue
        item_type_id = rule.attrib.get("itemTypeId", "")
        display_name = rule.attrib.get("displayName", "")
        if not item_type_id:
            continue
        conditions: List[MatchCondition] = []
        for cond in rule.findall(".//{*}condition"):
            operator = find_text(cond, ".//{*}operator", "")
            value = find_text(cond, ".//{*}value", "")
            norms = [n.text for n in cond.findall(".//{*}normalization") if n.text]
            conditions.append(
                MatchCondition(
                    property_id=cond.attrib.get("propertyTypeId", ""),
                    operator=operator,
                    value=value if value else None,
                    normalizations=norms,
                )
            )
        out.setdefault(item_type_id, []).append(
            MatchRule(item_type_id=item_type_id, display_name=display_name, conditions=conditions)
        )
    return out


def xlsx_to_matrix(path: Path) -> List[List[str]]:
    # Simple stdlib XLSX reader: first worksheet only.
    with ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        ns = {
            "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        }
        first_sheet = wb.find(".//a:sheets/a:sheet", ns)
        if first_sheet is None:
            return []
        rid = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rel_map = {}
        for rel in rels.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
            rel_map[rel.attrib.get("Id", "")] = rel.attrib.get("Target", "")
        target = rel_map.get(rid, "")
        if not target:
            return []
        part = f"xl/{target}" if not target.startswith("xl/") else target
        ws = ET.fromstring(z.read(part))

        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in ss.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                shared_strings.append(
                    "".join(
                        t.text or ""
                        for t in si.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    )
                )

        def cell_value(c: ET.Element) -> str:
            t = c.attrib.get("t")
            v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
            if v is None:
                return ""
            if t == "s":
                try:
                    idx = int(v.text or "0")
                    return shared_strings[idx] if 0 <= idx < len(shared_strings) else ""
                except Exception:
                    return ""
            return v.text or ""

        all_rows: List[List[str]] = []
        for row in ws.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
            vals = [cell_value(c).strip() for c in row.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c")]
            all_rows.append(vals)

        return all_rows


def load_matrix(path: Path, delimiter: str = ",") -> List[List[str]]:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return xlsx_to_matrix(path)
    if suffix not in (".csv", ".txt", ".tsv"):
        raise ValueError(f"Unsupported input type: {path.suffix}. Use CSV/TXT/TSV/XLSX.")

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        return [[v.strip() for v in row] for row in reader]


def normalize_value(value: str, norms: List[str]) -> str:
    out = value or ""
    for n in norms:
        if n == "IGNORE_CASE":
            out = out.lower()
        elif n == "SIMPLIFY_LIGATURES":
            out = out.replace("æ", "ae").replace("œ", "oe").replace("Æ", "AE").replace("Œ", "OE")
        elif n == "IGNORE_DIACRITICS":
            out = "".join(ch for ch in unicodedata.normalize("NFKD", out) if not unicodedata.combining(ch))
        elif n == "IGNORE_NONALPHANUMERIC":
            out = re.sub(r"[^A-Za-z0-9]", "", out)
        elif n == "IGNORE_WHITESPACE_BETWEEN":
            out = re.sub(r"\s+", "", out)
        elif n == "IGNORE_WHITESPACE_AROUND":
            out = out.strip()
    return out


def apply_operator(value: str, operator: str, op_value: Optional[str]) -> str:
    if operator == "EXACT_MATCH_END":
        try:
            n = int(op_value or "0")
            return value[-n:] if n > 0 else value
        except Exception:
            return value
    if operator == "EXACT_MATCH_START":
        try:
            n = int(op_value or "0")
            return value[:n] if n > 0 else value
        except Exception:
            return value
    return value


def evaluate_expression(expr: str, row: dict) -> str:
    if not expr:
        return ""

    def repl(match):
        col = match.group(1)
        return str(row.get(col, ""))

    return re.sub(r"\[([^\]]+)\]", repl, expr).strip()


def parse_datetime_value(value: str, fmt: str) -> str:
    if not value:
        return value
    py_fmt = (
        fmt.replace("yyyy", "%Y")
        .replace("dd", "%d")
        .replace("MM", "%m")
        .replace("HH", "%H")
        .replace("mm", "%M")
        .replace("ss", "%S")
    )
    try:
        dt = datetime.strptime(value, py_fmt)
        return dt.isoformat()
    except Exception:
        return value


def apply_column_action(value: str, action: ColumnAction, row: dict) -> str:
    if action.action == "RemoveCharacters":
        chars = action.args.get("Characters", "")
        for c in chars:
            value = value.replace(c, "")
        return value

    if action.action == "ExtractText":
        from_raw = action.args.get("From.Origin,Index", "")
        to_raw = action.args.get("To.Origin,Index", "")
        try:
            from_index = int(from_raw.split("|")[1]) if "|" in from_raw else 0
            to_index = int(to_raw.split("|")[1]) if "|" in to_raw else len(value) - 1
            return value[from_index : to_index + 1]
        except Exception:
            return value

    if action.action == "ValuePrefix":
        return f"{action.args.get('Text', '')}{value}"

    if action.action == "ValueSuffix":
        return f"{value}{action.args.get('Text', '')}"

    if action.action == "ColumnSuffix":
        col = action.args.get("ColumnId", "")
        sep = action.args.get("SeparateWith", "")
        return f"{value}{sep}{row.get(col, '')}"

    return value


def load_rows_for_template(template: ImportTemplate, input_path: Path) -> List[dict]:
    delimiter = template.delimiters if template.delimiters else ","
    matrix = load_matrix(input_path, delimiter=delimiter)
    if not matrix:
        return []

    header_idx = max(0, template.row_header_index - 1)
    if header_idx >= len(matrix):
        header_idx = 0
    headers = [h.strip() for h in matrix[header_idx]]

    filtered: List[dict] = []
    for idx, values in enumerate(matrix, start=1):
        if idx <= template.row_header_index:
            continue
        if any(a <= idx <= b for a, b in template.exclude_ranges):
            continue
        first_val = values[0] if values else ""
        if template.ignore_rows_starting_with and first_val.startswith(template.ignore_rows_starting_with):
            continue

        row = {}
        for i, h in enumerate(headers):
            if not h:
                continue
            row[h] = values[i] if i < len(values) else ""
        filtered.append(row)

    # Derive user columns
    for row in filtered:
        for uc in template.user_columns:
            row[uc.column_id] = evaluate_expression(uc.expression, row)

    # Apply column actions
    actions_by_col: Dict[str, List[ColumnAction]] = {}
    for action in template.column_actions:
        actions_by_col.setdefault(action.column_id, []).append(action)
    for row in filtered:
        for col, actions in actions_by_col.items():
            value = str(row.get(col, ""))
            for action in sorted(actions, key=lambda a: a.order):
                value = apply_column_action(value, action, row)
            row[col] = value

    # Date conversions
    for row in filtered:
        for df in template.date_formats:
            if df.column in row:
                row[df.column] = parse_datetime_value(str(row.get(df.column, "")), df.fmt)

    return filtered


def dedup_key_for_item(
    type_id: str,
    properties: Dict[str, str],
    identity_rules: Dict[str, IdentityRule],
    match_rules: Dict[str, List[MatchRule]],
) -> Optional[str]:
    # Prefer explicit identity rules in import template
    if type_id in identity_rules:
        ids = identity_rules[type_id].criteria_property_ids
        vals = [properties.get(pid, "") for pid in ids]
        if any(vals):
            return f"{type_id}|IDRULE|" + "|".join(vals)

    # Fallback to first active match rule
    rules = match_rules.get(type_id, [])
    if rules:
        r = rules[0]
        comps = []
        for cond in r.conditions:
            raw = properties.get(cond.property_id, "")
            normalized = normalize_value(raw, cond.normalizations)
            normalized = apply_operator(normalized, cond.operator, cond.value)
            comps.append(f"{cond.property_id}:{normalized}")
        if any(c.split(":", 1)[1] for c in comps):
            return f"{type_id}|MATCH|" + "|".join(comps)

    # Last resort: no key
    return None


def choose_label(type_name: str, prop_map: Dict[str, str]) -> str:
    for key in ("PT123", "PER4", "PER6", "VEH2", "ACC3", "PT170"):
        if prop_map.get(key):
            return prop_map[key]
    for v in prop_map.values():
        if v:
            return v
    return type_name


def run_template(
    template: ImportTemplate,
    rows: List[dict],
    match_rules: Dict[str, List[MatchRule]],
) -> dict:
    nodes = []
    edges = []
    node_index: Dict[str, dict] = {}  # dedup key -> node
    node_by_row_entity: Dict[Tuple[int, str], str] = {}
    edge_index: Dict[str, dict] = {}

    for i, row in enumerate(rows, start=1):
        # entities
        for ent in template.entities:
            props_by_id: Dict[str, str] = {}
            props_by_name: Dict[str, str] = {}
            for pm in ent.properties:
                val = evaluate_expression(pm.expression, row)
                if pm.blank_handling == "DoNotImportIfBlank" and not val:
                    continue
                props_by_id[pm.property_id] = val
                props_by_name[pm.property_name or pm.property_id] = val

            # ximp identity fallback
            identity_expr_value = evaluate_expression(ent.identity_expression, row) if ent.identity_expression else ""
            if identity_expr_value:
                props_by_id.setdefault("IDENTITY", identity_expr_value)
                props_by_name.setdefault("Identity", identity_expr_value)

            dedup_key = dedup_key_for_item(ent.type_id or ent.type_name, props_by_id, template.identity_rules, match_rules)
            if not dedup_key and identity_expr_value:
                dedup_key = f"{ent.type_name}|IDENTITY|{identity_expr_value}"

            if dedup_key and dedup_key in node_index:
                node_id = node_index[dedup_key]["id"]
                # merge new properties if missing
                existing_props = node_index[dedup_key]["properties"]
                for k, v in props_by_name.items():
                    if v and not existing_props.get(k):
                        existing_props[k] = v
            else:
                node_id = f"N-{uuid.uuid4().hex[:12]}"
                node_obj = {
                    "id": node_id,
                    "type_id": ent.type_id,
                    "type_name": ent.type_name,
                    "label": choose_label(ent.type_name, props_by_id),
                    "properties": props_by_name,
                    "identity_key": dedup_key or "",
                    "source_row": i,
                }
                nodes.append(node_obj)
                if dedup_key:
                    node_index[dedup_key] = node_obj
            node_by_row_entity[(i, ent.entity_id)] = node_id

        # links
        for link in template.links:
            src = node_by_row_entity.get((i, link.from_entity_id))
            dst = node_by_row_entity.get((i, link.to_entity_id))
            if not src or not dst:
                continue
            props_by_id: Dict[str, str] = {}
            props_by_name: Dict[str, str] = {}
            for pm in link.properties:
                val = evaluate_expression(pm.expression, row)
                if pm.blank_handling == "DoNotImportIfBlank" and not val:
                    continue
                props_by_id[pm.property_id] = val
                props_by_name[pm.property_name or pm.property_id] = val

            dedup_key = dedup_key_for_item(link.type_id or link.type_name, props_by_id, template.identity_rules, match_rules)
            if not dedup_key:
                stable = "|".join([link.type_id or link.type_name, src, dst] + [f"{k}={v}" for k, v in sorted(props_by_id.items()) if v])
                dedup_key = f"EDGE|{stable}"

            if dedup_key in edge_index:
                continue
            edge_obj = {
                "id": f"E-{uuid.uuid4().hex[:12]}",
                "type_id": link.type_id,
                "type_name": link.type_name,
                "source": src,
                "target": dst,
                "properties": props_by_name,
                "identity_key": dedup_key,
                "source_row": i,
            }
            edges.append(edge_obj)
            edge_index[dedup_key] = edge_obj

    return {
        "metadata": {
            "template_file": template.file_name,
            "source_type": template.source_type,
            "rows_processed": len(rows),
            "nodes": len(nodes),
            "edges": len(edges),
        },
        "nodes": nodes,
        "edges": edges,
    }


def list_templates(base_dir: Path):
    specs_dir = base_dir / "Import Specifications"
    if not specs_dir.exists():
        print(f"No import specs directory found: {specs_dir}")
        return
    for p in sorted(specs_dir.glob("*.oimp")):
        print(p.name)


def resolve_template(base_dir: Path, template_name_or_path: str) -> Path:
    p = Path(template_name_or_path)
    if p.exists():
        return p
    cand = base_dir / "Import Specifications" / template_name_or_path
    if cand.exists():
        return cand
    raise FileNotFoundError(f"Template not found: {template_name_or_path}")


def main():
    parser = argparse.ArgumentParser(description="Run i2 .oimp/.ximp template ingestion into graph JSON.")
    parser.add_argument("--base-dir", default=str(I2_DEFAULT_BASE), help="Base i2 specs directory")
    parser.add_argument("--list-templates", action="store_true", help="List available .oimp templates")
    parser.add_argument("--template", help="Template filename (.oimp/.ximp) or absolute path")
    parser.add_argument("--input", help="Input CSV/TXT/TSV/XLSX file path")
    parser.add_argument("--matching-file", default="", help="Optional override for matching rules XML")
    parser.add_argument("--out", default="data/i2 Specs/parsed/graph_output.json", help="Output graph JSON path")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    if args.list_templates:
        list_templates(base_dir)
        return

    if not args.template or not args.input:
        parser.error("Use --template and --input (or --list-templates).")

    template_path = resolve_template(base_dir, args.template)
    template = parse_import_template(template_path)
    input_path = Path(args.input)
    rows = load_rows_for_template(template, input_path)

    matching_path = Path(args.matching_file) if args.matching_file else (base_dir / "Matching Settings" / "cached-system-match-rules.xml")
    match_rules = parse_match_rules(matching_path) if matching_path.exists() else {}

    graph = run_template(template, rows, match_rules)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print(f"Wrote graph output: {out_path}")
    print(
        f"Template={template.file_name} Rows={graph['metadata']['rows_processed']} "
        f"Nodes={graph['metadata']['nodes']} Edges={graph['metadata']['edges']}"
    )


if __name__ == "__main__":
    main()
