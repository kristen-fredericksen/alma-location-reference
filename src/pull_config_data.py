"""
Pull location and fulfillment configuration from the Alma Config API.

Retrieves: Libraries -> Locations (with FU assignments)

Usage:
    python3 src/pull_config_data.py QC          # Pull one campus
    python3 src/pull_config_data.py --all        # Pull all campuses

Output:
    data/{campus}_config_data.json   (single campus)
    data/all_config_data.json        (all campuses)
"""

import argparse
import json
from pathlib import Path

from alma_common import (
    PROJECT_ROOT,
    EXCLUDED_LOCATIONS,
    INCLUDED_CAMPUSES,
    CAMPUS_NAMES,
    load_api_key,
    alma_get,
    extract_field,
)

DATA_DIR = PROJECT_ROOT / "data"


def pull_libraries(api_key: str) -> list[dict]:
    """Get all libraries for the institution."""
    data = alma_get("/almaws/v1/conf/libraries", api_key)
    if not data:
        return []
    return data.get("library", [])


def pull_locations(api_key: str, library_code: str) -> list[dict]:
    """Get all locations for a library from the list endpoint."""
    data = alma_get(
        f"/almaws/v1/conf/libraries/{library_code}/locations", api_key
    )
    if not data:
        return []

    locations = []
    for loc in data.get("location", []):
        code = loc.get("code", "")
        if code in EXCLUDED_LOCATIONS:
            continue

        locations.append({
            "code": code,
            "name": loc.get("name", ""),
            "external_name": loc.get("external_name", ""),
            "type": extract_field(loc, "type"),
            "fulfillment_unit_code": extract_field(loc, "fulfillment_unit"),
            "call_number_type": extract_field(loc, "call_number_type"),
            "suppress_from_publishing": str(
                loc.get("suppress_from_publishing", "")
            ).lower() == "true",
        })

    return locations


def pull_campus(campus: str) -> dict:
    """Pull all config data for one campus. Returns a campus data dict."""
    api_key = load_api_key(campus)

    libraries_raw = pull_libraries(api_key)
    libraries = []
    total_locations = 0

    for lib in libraries_raw:
        lib_code = lib.get("code", "")
        lib_name = lib.get("name", "")
        locations = pull_locations(api_key, lib_code)
        total_locations += len(locations)
        libraries.append({
            "code": lib_code,
            "name": lib_name,
            "locations": locations,
        })

    print(f"  {campus} ({CAMPUS_NAMES.get(campus, '')}): "
          f"{len(libraries)} libraries, {total_locations} locations")

    return {
        "campus": campus,
        "name": CAMPUS_NAMES.get(campus, campus),
        "libraries": libraries,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Pull Alma location config for CUNY campuses."
    )
    parser.add_argument("campus", nargs="?", help="Campus code (e.g., QC)")
    parser.add_argument("--all", action="store_true", help="Pull all campuses")
    args = parser.parse_args()

    if not args.all and not args.campus:
        parser.error("Provide a campus code or use --all")

    DATA_DIR.mkdir(exist_ok=True)

    if args.all:
        campuses = INCLUDED_CAMPUSES
    else:
        campuses = [args.campus.upper()]

    print(f"\n{'='*55}")
    print(f"  Alma Config Pull — {len(campuses)} campus(es)")
    print(f"{'='*55}\n")

    all_data = {}
    for campus in campuses:
        all_data[campus] = pull_campus(campus)

    if args.all:
        output_path = DATA_DIR / "all_config_data.json"
        with open(output_path, "w") as f:
            json.dump(all_data, f, indent=2)
    else:
        campus = campuses[0]
        output_path = DATA_DIR / f"{campus}_config_data.json"
        with open(output_path, "w") as f:
            json.dump(all_data[campus], f, indent=2)

    total_locs = sum(
        sum(len(lib["locations"]) for lib in cd["libraries"])
        for cd in all_data.values()
    )
    print(f"\nSaved to: {output_path}")
    print(f"  Total locations across all campuses: {total_locs}")


if __name__ == "__main__":
    main()
