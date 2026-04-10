"""
Generate a self-contained HTML report from merged location/policy data.

Usage:
    python3 src/generate_report.py QC          # Single campus report
    python3 src/generate_report.py --all        # All campuses with selector

Output:
    output/{campus}_location_reference.html  (single campus)
    output/location_reference.html           (all campuses)
"""

import base64
import json
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from alma_common import PROJECT_ROOT, LOGO_PATH, CAMPUS_NAMES, CAMPUS_SORT_NAMES, load_json

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

POLICY_TYPE_ORDER = [
    "Due Date", "Grace Period", "Overdue Fine", "Maximum Fine",
    "Maximum Renewal Period", "Recall Period", "Recalled Overdue Fine",
    "Requested Item Due Date", "Hold Shelf Period",
    "Lost Item Fine", "Lost Item Replacement Fee", "Reloan Limit",
]

POLICY_SECTION_MAP = {
    "Due Date": "Loans",
    "Overdue Fine": "Fines & Fees",
    "Maximum Fine": "Fines & Fees",
    "Grace Period": "Fines & Fees",
    "Lost Item Fine": "Fines & Fees",
    "Lost Item Replacement Fee": "Fines & Fees",
    "Maximum Renewal Period": "Renewals",
    "Recall Period": "Recalls & Requests",
    "Recalled Overdue Fine": "Recalls & Requests",
    "Requested Item Due Date": "Recalls & Requests",
    "Hold Shelf Period": "Recalls & Requests",
    "Reloan Limit": "Renewals",
}


def load_logo() -> str:
    """Load the logo as a base64 string, or return empty string."""
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def group_policies(policies: list) -> OrderedDict:
    """Group a list of policy dicts into display sections."""
    sections = OrderedDict([
        ("Loans", []), ("Renewals", []),
        ("Fines & Fees", []), ("Recalls & Requests", []), ("Other", []),
    ])
    for p in policies:
        section = POLICY_SECTION_MAP.get(p.get("type", ""), "Other")
        sections[section].append(p)
    return sections


def get_policy_types(all_tous: dict) -> list[str]:
    """Get ordered list of policy types across all TOUs."""
    seen = set()
    ordered = []
    for pt in POLICY_TYPE_ORDER:
        for tou_data in all_tous.values():
            if any(p.get("type") == pt for p in tou_data.get("policies", [])):
                if pt not in seen:
                    ordered.append(pt)
                    seen.add(pt)
                break
    for tou_data in all_tous.values():
        for p in tou_data.get("policies", []):
            pt = p.get("type", "")
            if pt and pt not in seen:
                ordered.append(pt)
                seen.add(pt)
    return ordered


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 src/generate_report.py QC")
        print("  python3 src/generate_report.py --all")
        sys.exit(1)

    use_all = "--all" in sys.argv

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    env.globals["group_policies"] = group_policies

    if use_all:
        all_merged = load_json(DATA_DIR / "all_merged.json")

        # Collect all policy types across all campuses
        combined_tous = {}
        for campus_data in all_merged.values():
            combined_tous.update(campus_data.get("all_tous", {}))

        template = env.get_template("report.html")
        html = template.render(
            multi_campus=True,
            campuses=all_merged,
            campus_names=CAMPUS_NAMES,
            campus_sort_names=CAMPUS_SORT_NAMES,
            policy_types=get_policy_types(combined_tous),
            logo_b64=load_logo(),
            generated_date=date.today().strftime("%B %d, %Y"),
            tous_json="{}",  # not used in multi-campus mode
        )

        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / "location_reference.html"
        with open(output_path, "w") as f:
            f.write(html)

        print(f"Generated multi-campus report: {output_path}")
        print(f"  {len(all_merged)} campuses included")
    else:
        campus = sys.argv[1].upper()
        merged = load_json(DATA_DIR / f"{campus}_merged.json")

        template = env.get_template("report.html")
        html = template.render(
            multi_campus=False,
            campus=campus,
            libraries=merged["libraries"],
            fu_groups=merged["fu_groups"],
            all_tous=merged["all_tous"],
            policy_types=get_policy_types(merged["all_tous"]),
            logo_b64=load_logo(),
            generated_date=date.today().strftime("%B %d, %Y"),
            tous_json=json.dumps(merged["all_tous"], indent=None),
        )

        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / f"{campus}_location_reference.html"
        with open(output_path, "w") as f:
            f.write(html)

        print(f"Generated: {output_path}")


if __name__ == "__main__":
    main()
