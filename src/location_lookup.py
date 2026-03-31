"""
Alma Location Lookup Tool

Queries the Alma Configuration API to display a school's libraries,
locations, and their properties. Helps staff see what already exists
before requesting new locations or changes.

Usage:
    python3 src/location_lookup.py              # list all libraries and their locations
    python3 src/location_lookup.py LIBRARY_CODE  # show locations for one library
"""

import sys
import os
import requests
from dotenv import load_dotenv

# System locations that should never appear in lookup results
EXCLUDED_LOCATIONS = {"IN_RS_REQ", "OUT_RS_REQ"}


def load_config():
    """Load API configuration from .env file."""
    load_dotenv()

    api_key = os.getenv("ALMA_API_KEY")
    base_url = os.getenv("ALMA_API_BASE_URL", "https://api-na.hosted.exlibrisgroup.com")

    if not api_key:
        print("Error: ALMA_API_KEY not found in .env file.")
        print("Copy .env.example to .env and paste your API key.")
        sys.exit(1)

    return api_key, base_url


def alma_get(base_url, endpoint, api_key):
    """Make a GET request to the Alma API and return JSON."""
    url = f"{base_url}{endpoint}"
    params = {"apikey": api_key, "format": "json"}

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print(f"Error: API returned status {response.status_code}")
        try:
            error_data = response.json()
            for error in error_data.get("errorList", {}).get("error", []):
                print(f"  {error.get('errorCode')}: {error.get('errorMessage')}")
        except Exception:
            print(f"  {response.text[:200]}")
        return None

    return response.json()


def get_libraries(base_url, api_key):
    """Retrieve all libraries for the institution."""
    data = alma_get(base_url, "/almaws/v1/conf/libraries", api_key)
    if not data:
        return []
    return data.get("library", [])


def get_locations(base_url, api_key, library_code):
    """Retrieve all locations for a given library."""
    data = alma_get(base_url, f"/almaws/v1/conf/libraries/{library_code}/locations", api_key)
    if not data:
        return []
    return data.get("location", [])


def get_location_detail(base_url, api_key, library_code, location_code):
    """Retrieve full details for a single location."""
    data = alma_get(
        base_url,
        f"/almaws/v1/conf/libraries/{library_code}/locations/{location_code}",
        api_key,
    )
    return data


def display_location(location):
    """Display a single location's properties in a readable format."""
    code = location.get("code", "?")
    name = location.get("name", "?")
    external_name = location.get("external_name", "")

    # Type field is an object with value and desc
    loc_type = location.get("type", {})
    if isinstance(loc_type, dict):
        type_desc = loc_type.get("desc", loc_type.get("value", "?"))
    else:
        type_desc = str(loc_type)

    # Fulfillment unit is an object with value and desc
    fu = location.get("fulfillment_unit", {})
    if isinstance(fu, dict):
        fu_desc = fu.get("desc", fu.get("value", "None"))
    else:
        fu_desc = str(fu) if fu else "None"

    # Call number type is an object with value and desc
    cn = location.get("call_number_type", {})
    if isinstance(cn, dict):
        cn_desc = cn.get("desc", cn.get("value", "?"))
    else:
        cn_desc = str(cn) if cn else "?"

    # Suppress from publishing
    suppress = location.get("suppress_from_publishing", "")

    print(f"  {name}")
    print(f"    Code:             {code}")
    if external_name and external_name != name:
        print(f"    External name:    {external_name}")
    print(f"    Type:             {type_desc}")
    print(f"    Fulfillment unit: {fu_desc}")
    print(f"    Call number type: {cn_desc if cn_desc else '(not set)'}")
    if suppress and str(suppress).lower() == "true":
        print("    Suppressed:       Yes")
    print()


def display_library(base_url, api_key, library):
    """Display a library and all its locations."""
    lib_code = library.get("code", "?")
    lib_name = library.get("name", "?")

    print(f"Library: {lib_name} ({lib_code})")
    print("-" * 50)

    locations = get_locations(base_url, api_key, lib_code)

    if not locations:
        print("  No locations found.")
        print()
        return

    # Check if the list response includes fulfillment_unit.
    # If not, we need to fetch each location's detail individually.
    first_loc = locations[0]
    needs_detail = "fulfillment_unit" not in first_loc

    for loc in locations:
        if loc.get("code", "") in EXCLUDED_LOCATIONS:
            continue
        if needs_detail:
            detail = get_location_detail(base_url, api_key, lib_code, loc.get("code", ""))
            if detail:
                loc = detail
        display_location(loc)


def main():
    api_key, base_url = load_config()

    # Optional: filter to a specific library code
    library_filter = sys.argv[1].upper() if len(sys.argv) > 1 else None

    print()
    print("=" * 50)
    print("  Alma Location Lookup")
    print("=" * 50)
    print()

    libraries = get_libraries(base_url, api_key)

    if not libraries:
        print("No libraries found. Check your API key and permissions.")
        return

    if library_filter:
        # Find the matching library
        matches = [lib for lib in libraries if lib.get("code", "").upper() == library_filter]
        if not matches:
            print(f"Library '{library_filter}' not found. Available libraries:")
            for lib in libraries:
                print(f"  {lib.get('code', '?'):15} {lib.get('name', '?')}")
            return
        libraries = matches

    for library in libraries:
        display_library(base_url, api_key, library)


if __name__ == "__main__":
    main()
