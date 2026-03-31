"""
Pull TOU and policy details from Alma Analytics (Configurations Limited).

Usage:
    python3 src/pull_analytics_config.py QC       # Pull one campus
    python3 src/pull_analytics_config.py --all     # Pull all via NZ report

Output:
    data/{campus}_analytics_tou_data.json  (single campus)
    data/all_analytics_tou_data.json       (all campuses)
"""

import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from alma_common import PROJECT_ROOT, BASE_URL, CAMPUS_IZ_CODES, load_api_key

import requests

DATA_DIR = PROJECT_ROOT / "data"

# Per-campus report paths (for single-campus mode)
REPORT_PATHS = {
    "QC": "/shared/Queens College 01CUNY_QC/Reports/TOU Policy Details",
}

# Network Zone report path (for --all mode, returns data for all institutions)
NZ_REPORT_PATH = "/shared/CUNY Network 01CUNY_NETWORK/Reports/Configuration/TOU Policy Details"


def fetch_analytics_report(api_key: str, report_path: str, limit: int = 1000):
    """Fetch an Alma Analytics report with pagination. Returns (column_names, rows)."""
    url = f"{BASE_URL}/almaws/v1/analytics/reports"
    all_rows = []
    column_names = None
    token = None
    page = 0

    while True:
        page += 1
        params = {
            "apikey": api_key,
            "limit": limit,
            "col_names": "true",
        }

        if token:
            params["token"] = token
        else:
            params["path"] = report_path

        print(f"  Fetching page {page}...", end=" ", flush=True)
        response = requests.get(url, params=params)

        if response.status_code != 200:
            print(f"ERROR (HTTP {response.status_code})")
            print(f"  Response: {response.text[:500]}")
            sys.exit(1)

        root = ET.fromstring(response.text)

        is_finished_el = root.find(".//IsFinished")
        is_finished = is_finished_el is not None and is_finished_el.text == "true"

        result_xml = root.find(".//ResultXml")
        if result_xml is None:
            print("ERROR: No ResultXml in response")
            sys.exit(1)

        rowset = None
        for elem in result_xml.iter():
            if "rowset" in elem.tag.lower():
                rowset = elem
                break
        if rowset is None:
            rowset = result_xml

        if column_names is None:
            column_names = _extract_column_names(root)
            if column_names:
                print(f"({len(column_names)} columns)", end=" ")

        rows_found = 0
        for row_elem in rowset.iter():
            if "Row" in row_elem.tag and row_elem.tag != rowset.tag:
                indexed_values = {}
                for col_elem in row_elem:
                    tag = (
                        col_elem.tag.split("}")[-1]
                        if "}" in col_elem.tag
                        else col_elem.tag
                    )
                    col_num = "".join(c for c in tag if c.isdigit())
                    if col_num:
                        indexed_values[int(col_num)] = (
                            col_elem.text if col_elem.text else ""
                        )
                if indexed_values:
                    all_rows.append(indexed_values)
                    rows_found += 1

        print(f"{rows_found} rows")

        if is_finished:
            break

        token_el = root.find(".//ResumptionToken")
        if token_el is None or not token_el.text:
            print("  Warning: No resumption token but IsFinished is false. Stopping.")
            break
        token = token_el.text
        time.sleep(0.5)

    return column_names, all_rows


def _extract_column_names(root):
    """Extract column index -> heading mapping from Analytics response schema."""
    indexed_names = {}
    for elem in root.iter():
        heading = None
        for attr_name, attr_val in elem.attrib.items():
            if "columnHeading" in attr_name:
                heading = attr_val
                break
        if heading:
            col_tag = elem.attrib.get("name", "")
            col_num = "".join(c for c in col_tag if c.isdigit())
            if col_num:
                indexed_names[int(col_num)] = heading
    return indexed_names if indexed_names else None


def rows_to_records(column_names_map: dict, rows: list) -> list[dict]:
    """Convert indexed rows to list of dicts with column names as keys."""
    if not column_names_map or not rows:
        return []
    return [
        {heading: row.get(idx, "") for idx, heading in column_names_map.items()}
        for row in rows
    ]


def group_by_tou(records: list[dict]) -> dict:
    """Group policy records by TOU Name into a structured dict."""
    tous = {}
    for rec in records:
        tou_name = rec.get("TOU Name", "").strip()
        if not tou_name:
            continue

        if tou_name not in tous:
            tous[tou_name] = {
                "tou_type": rec.get("TOU Type", ""),
                "tou_description": rec.get("TOU Description", ""),
                "tou_definition_level": rec.get("TOU Definition Level", ""),
                "policies": [],
            }

        policy_name = rec.get("Policy Name", "").strip()
        if policy_name:
            tous[tou_name]["policies"].append({
                "name": policy_name,
                "value": rec.get("Policy Value", ""),
                "unit": rec.get("Policy Unit of Measurement", ""),
                "constant": rec.get("Policy Constant", ""),
                "type": rec.get("Policy Type", ""),
                "active": rec.get("Policy Active", ""),
            })

    return tous


def group_records_by_institution(records: list[dict]) -> dict:
    """
    Split records by Institution Code, returning a dict of campus_code → records.

    Analytics returns Institution Code as '01CUNY_QC', etc.
    We reverse-map to our campus codes (QC, BB, etc.).
    """
    iz_to_campus = {v: k for k, v in CAMPUS_IZ_CODES.items()}
    grouped = {}

    for rec in records:
        iz_code = rec.get("Institution Code", "").strip()
        campus = iz_to_campus.get(iz_code)
        if not campus:
            continue
        if campus not in grouped:
            grouped[campus] = []
        grouped[campus].append(rec)

    return grouped


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 src/pull_analytics_config.py QC      # One campus")
        print("  python3 src/pull_analytics_config.py --all    # All via NZ report")
        sys.exit(1)

    use_all = "--all" in sys.argv

    if use_all:
        if not NZ_REPORT_PATH:
            print("Error: NZ_REPORT_PATH is not configured.")
            print("Set it in pull_analytics_config.py after creating the NZ report.")
            sys.exit(1)
        api_key = load_api_key("NETWORK")
        report_path = NZ_REPORT_PATH
        print(f"\n{'='*55}")
        print(f"  Analytics TOU/Policy Pull — All Campuses (NZ)")
        print(f"{'='*55}")
    else:
        campus = sys.argv[1].upper()
        if campus not in REPORT_PATHS:
            print(f"Error: No report path for {campus}.")
            print(f"Available: {', '.join(sorted(REPORT_PATHS.keys()))}")
            sys.exit(1)
        api_key = load_api_key(campus)
        report_path = REPORT_PATHS[campus]
        print(f"\n{'='*55}")
        print(f"  Analytics TOU/Policy Pull — {campus}")
        print(f"{'='*55}")

    print(f"  Report: {report_path}\n")

    column_names, rows = fetch_analytics_report(api_key, report_path)

    if not rows:
        print("No data returned.")
        sys.exit(1)

    print(f"\n  Total rows: {len(rows)}")

    records = rows_to_records(column_names, rows)

    DATA_DIR.mkdir(exist_ok=True)

    if use_all:
        # Split by institution
        by_campus = group_records_by_institution(records)
        all_data = {}
        for campus_code, campus_records in sorted(by_campus.items()):
            tous = group_by_tou(campus_records)
            all_data[campus_code] = {
                "campus": campus_code,
                "tou_count": len(tous),
                "tous": tous,
            }
            print(f"  {campus_code}: {len(tous)} TOUs")

        output_path = DATA_DIR / "all_analytics_tou_data.json"
        with open(output_path, "w") as f:
            json.dump(all_data, f, indent=2)

        print(f"\n  Saved to: {output_path}")
        print(f"  {len(all_data)} campuses found in report")
    else:
        campus = sys.argv[1].upper()
        tous = group_by_tou(records)
        output = {
            "campus": campus,
            "total_rows": len(rows),
            "tou_count": len(tous),
            "tous": tous,
        }

        output_path = DATA_DIR / f"{campus}_analytics_tou_data.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        print(f"\n  Saved to: {output_path}")
        print(f"  {len(tous)} TOUs found")


if __name__ == "__main__":
    main()
