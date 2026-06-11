"""
Merge Config API data and Analytics TOU/policy data.

Usage:
    python3 src/merge_data.py QC          # Merge one campus
    python3 src/merge_data.py --all        # Merge all campuses

Output:
    data/{campus}_merged.json   (single campus)
    data/all_merged.json        (all campuses)
"""

import json
import sys
from pathlib import Path

from alma_common import PROJECT_ROOT, CAMPUS_NAMES, INCLUDED_CAMPUSES, load_json

DATA_DIR = PROJECT_ROOT / "data"


def merge_campus(campus: str, config_data: dict, analytics_data: dict) -> dict:
    """Merge config + analytics data for one campus."""
    # Filter to Loan TOUs only
    tou_policies = {}
    for tou_name, tou_data in analytics_data.get("tous", {}).items():
        if tou_data.get("tou_type") == "Loan":
            tou_policies[tou_name] = tou_data

    # Build FU groups
    fu_groups = {}
    for lib in config_data.get("libraries", []):
        for loc in lib["locations"]:
            fu = loc.get("fulfillment_unit_code", "(none)")
            if fu not in fu_groups:
                fu_groups[fu] = {"locations": []}
            fu_groups[fu]["locations"].append({
                "library": lib["name"],
                "library_code": lib["code"],
                "code": loc["code"],
                "name": loc["name"],
            })

    return {
        "campus": campus,
        "name": CAMPUS_NAMES.get(campus, campus),
        "libraries": config_data.get("libraries", []),
        "fu_groups": fu_groups,
        "all_tous": tou_policies,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 src/merge_data.py QC")
        print("  python3 src/merge_data.py --all")
        sys.exit(1)

    use_all = "--all" in sys.argv

    print(f"\n{'='*55}")
    print(f"  Merge Data{' — All Campuses' if use_all else ''}")
    print(f"{'='*55}")

    if use_all:
        all_config = load_json(DATA_DIR / "all_config_data.json")
        all_analytics = load_json(DATA_DIR / "all_analytics_tou_data.json")

        all_merged = {}
        for campus in INCLUDED_CAMPUSES:
            config_data = all_config.get(campus, {"libraries": []})
            analytics_data = all_analytics.get(campus, {"tous": {}})
            merged = merge_campus(campus, config_data, analytics_data)

            total_locs = sum(len(lib["locations"]) for lib in merged["libraries"])
            tou_count = len(merged["all_tous"])
            print(f"  {campus} ({CAMPUS_NAMES[campus]}): "
                  f"{total_locs} locations, {tou_count} Loan TOUs")

            all_merged[campus] = merged

        output_path = DATA_DIR / "all_merged.json"
        with open(output_path, "w") as f:
            json.dump(all_merged, f, indent=2)
    else:
        campus = sys.argv[1].upper()
        config_data = load_json(DATA_DIR / f"{campus}_config_data.json")

        per_campus_analytics = DATA_DIR / f"{campus}_analytics_tou_data.json"
        all_analytics_path = DATA_DIR / "all_analytics_tou_data.json"
        if per_campus_analytics.exists():
            analytics_data = load_json(per_campus_analytics)
        elif all_analytics_path.exists():
            all_analytics = load_json(all_analytics_path)
            if campus in all_analytics:
                analytics_data = all_analytics[campus]
                print(f"  Using {campus} entry from all_analytics_tou_data.json")
            else:
                print(f"Error: {campus} not found in all_analytics_tou_data.json.")
                print("Run: python3 src/pull_analytics_config.py --all")
                sys.exit(1)
        else:
            print("Error: No analytics data found.")
            print("Run: python3 src/pull_analytics_config.py --all")
            sys.exit(1)

        merged = merge_campus(campus, config_data, analytics_data)

        total_locs = sum(len(lib["locations"]) for lib in merged["libraries"])
        print(f"  {campus}: {total_locs} locations, {len(merged['all_tous'])} Loan TOUs")

        output_path = DATA_DIR / f"{campus}_merged.json"
        with open(output_path, "w") as f:
            json.dump(merged, f, indent=2)

    print(f"\n  Saved to: {output_path}")


if __name__ == "__main__":
    main()
