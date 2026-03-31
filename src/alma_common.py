"""
Shared utilities for Alma API and data handling.

Used by pull_config_data.py, pull_analytics_config.py, merge_data.py,
and generate_report.py.
"""

import json
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent
API_KEYS_PATH = PROJECT_ROOT.parent / "api_keys.env"
BASE_URL = "https://api-na.hosted.exlibrisgroup.com"
LOGO_PATH = PROJECT_ROOT / "assets" / "logo_white.png"

# System locations to exclude (Alma creates these automatically)
EXCLUDED_LOCATIONS = {"IN_RS_REQ", "OUT_RS_REQ"}

# CUNY campus codes → full names (from CLAUDE.md)
CAMPUS_NAMES = {
    "BB": "Baruch College",
    "BC": "Brooklyn College",
    "BM": "Borough of Manhattan Community College",
    "BX": "Bronx Community College",
    "CC": "The City College of New York",
    "CL": "CUNY School of Law",
    "GC": "CUNY Graduate Center",
    "GJ": "Craig Newmark Graduate School of Journalism at CUNY",
    "HC": "Hunter College",
    "HO": "Hostos Community College",
    "JJ": "John Jay College of Criminal Justice",
    "KB": "Kingsborough Community College",
    "LE": "Lehman College",
    "LG": "LaGuardia Community College",
    "ME": "Medgar Evers College",
    "NC": "Guttman Community College",
    "NY": "New York City College of Technology",
    "QB": "Queensborough Community College",
    "QC": "Queens College",
    "SI": "College of Staten Island",
    "YC": "York College",
}

# Alma institution codes used in Analytics (01CUNY_{campus})
CAMPUS_IZ_CODES = {code: f"01CUNY_{code}" for code in CAMPUS_NAMES}

# Campuses to include in reports (excludes AL/Central Office and NETWORK)
INCLUDED_CAMPUSES = sorted(CAMPUS_NAMES.keys())


def load_api_key(campus_code: str) -> str:
    """Load the production API key for a campus from the shared api_keys.env."""
    key_name = f"ALMA_PROD_{campus_code}"

    if not API_KEYS_PATH.exists():
        print(f"Error: Cannot find {API_KEYS_PATH}")
        sys.exit(1)

    with open(API_KEYS_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key_name}="):
                return line.split("=", 1)[1]

    print(f"Error: No key found for {key_name} in {API_KEYS_PATH}")
    sys.exit(1)


def load_json(path: Path) -> dict:
    """Load a JSON file or exit with an error."""
    if not path.exists():
        print(f"Error: {path} not found.")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def alma_get(endpoint: str, api_key: str) -> dict | None:
    """Make a GET request to the Alma API. Returns parsed JSON or None."""
    url = f"{BASE_URL}{endpoint}"
    params = {"apikey": api_key, "format": "json"}

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print(f"  API error {response.status_code} for {endpoint}")
        try:
            for error in response.json().get("errorList", {}).get("error", []):
                print(f"    {error.get('errorMessage', '')}")
        except Exception:
            print(f"    {response.text[:200]}")
        return None

    return response.json()


def paginate(endpoint: str, list_key: str, api_key: str) -> list:
    """Fetch all records from a paginated Alma endpoint."""
    params = {"limit": 100, "offset": 0, "apikey": api_key, "format": "json"}
    url = f"{BASE_URL}{endpoint}"
    results = []

    while True:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"  API error {response.status_code} for {endpoint}")
            break

        data = response.json()
        batch = data.get(list_key, [])
        total = int(data.get("total_record_count", 0))

        results.extend(batch)
        params["offset"] += len(batch)

        if params["offset"] >= total or not batch:
            break

        time.sleep(0.05)

    return results


def extract_field(obj: dict, field_name: str) -> str:
    """Extract a value from a field that might be a plain string or {value, desc} object."""
    val = obj.get(field_name, "")
    if isinstance(val, dict):
        return val.get("desc", val.get("value", ""))
    return str(val) if val else ""
