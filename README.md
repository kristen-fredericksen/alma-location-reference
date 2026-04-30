# Alma Location Reference

Interactive HTML reference tool for CUNY Alma location and fulfillment policy configuration. Helps library staff see what locations and policies their campus already has before requesting changes.

## What it does

CUNY library staff request new or updated Alma locations from OLS via a LibWizard form, but they often don't understand fulfillment policies (loan periods, fines, recall rules, etc.). This tool generates a single self-contained HTML page that shows, for each campus:

1. **All Locations** — code, name, library, type, fulfillment unit, call number type, suppression status. Sortable, searchable, exportable to CSV.
2. **By Fulfillment Unit** — locations grouped by FU so staff can see which locations circulate the same way (useful when filling out the "make a new location like an existing one" form option).
3. **Loan Policies (TOUs)** — every Loan Term of Use at the campus with full policy details (loan period, fines, renewals, recalls). Filterable by policy type and value, exportable to CSV.

The HTML is a single self-contained file with embedded data — drop it on a web server and it works.

## How it works

Two data sources are joined:

- **Alma Configuration API** — provides locations and their fulfillment unit assignments per campus
- **Alma Analytics (Configurations Limited subject area)** — provides Terms of Use and their policy values

Neither source has the complete picture alone. The Analytics subject area has no Location or Fulfillment Unit dimension, and the `/conf/fulfillment-units` Configuration API endpoint returns 404. So the tool pulls from both and joins on Institution Code.

```
CONFIG API (per institution)            ANALYTICS NZ (all institutions)
────────────────────────────            ──────────────────────────────
Location (code, name, type...)
  └→ Fulfillment Unit (name)            TOU Name
                                          └→ Policy Name
                                          └→ Policy Value
                                          └→ Policy Unit of Measurement
```

## Setup

```bash
git clone https://github.com/kristen-fredericksen/alma-location-reference.git
cd alma-location-reference

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment

The pipeline expects an `api_keys.env` file at the **parent directory** of this project (i.e., shared across multiple Alma scripts). Copy `.env.example` to see the format. Required keys:

- `ALMA_PROD_{campus}` for each campus you want to include (e.g., `ALMA_PROD_QC`, `ALMA_PROD_BB`)
- `ALMA_PROD_NETWORK` for the multi-campus Analytics pull

API keys need:
- **Configuration - Production Read-only** permission
- **Analytics - Production Read-only** permission

### Analytics report

A Configurations (Limited) report must exist in the Network Zone shared folder at:
`/shared/CUNY Network 01CUNY_NETWORK/Reports/Configuration/TOU Policy Details`

Required columns:
- Institution Name, Institution Code
- TOU Name, TOU Type, TOU Description, TOU Definition Level
- Policy Name, Policy Value, Policy Unit of Measurement, Policy Constant, Policy Type, Policy Active
- Rule Name, Rule Parameter Value, Rule Type

If the report path differs, update `NZ_REPORT_PATH` in `src/pull_analytics_config.py`.

## Usage

### Multi-campus (production)

```bash
source venv/bin/activate

python3 src/pull_config_data.py --all       # locations from Config API for all 21 campuses
python3 src/pull_analytics_config.py --all  # TOU/policies from one NZ Analytics report
python3 src/merge_data.py --all             # join the two
python3 src/generate_report.py --all        # generate output/location_reference.html
```

Open `output/location_reference.html` in a browser.

### Single campus (debugging)

```bash
python3 src/pull_config_data.py QC
python3 src/pull_analytics_config.py QC
python3 src/merge_data.py QC
python3 src/generate_report.py QC
```

Output: `output/QC_location_reference.html`

## Project structure

```
.
├── src/
│   ├── alma_common.py          Shared utilities, campus constants
│   ├── pull_config_data.py     Config API → locations + FUs
│   ├── pull_analytics_config.py Analytics API → TOUs + policies
│   ├── merge_data.py           Join Config + Analytics
│   ├── generate_report.py      Render Jinja2 template → HTML
│   └── location_lookup.py      Original CLI (kept for backward compat)
├── templates/
│   └── report.html             Jinja2 template (single + multi-campus modes)
├── assets/
│   ├── logo_color.png          CUNY Library Services color logo (footer)
│   └── logo_white.png          White logo (alternate)
├── data/                       Intermediate JSON (gitignored)
├── output/                     Generated HTML (gitignored)
├── requirements.txt
└── .env.example
```

## Dependencies

- **Python 3.10+** (uses `str.removeprefix`, type hints with `|`)
- **requests** — Alma API calls
- **python-dotenv** — environment loading
- **Jinja2** — HTML templating

The HTML output uses CDN-loaded **DataTables** + **DataTables Buttons** + **jQuery** for sortable tables and CSV export. No frontend build step.

## Refreshing the data

Alma Analytics data is one day behind. Run the full pipeline whenever you want fresh data:

```bash
python3 src/pull_config_data.py --all && \
python3 src/pull_analytics_config.py --all && \
python3 src/merge_data.py --all && \
python3 src/generate_report.py --all
```

Then deploy `output/location_reference.html` to wherever it's hosted (e.g., `ols.cuny.edu/alma/`).

## Known limitations

- The fulfillment-units API endpoint (`GET /conf/fulfillment-units`) returns 404 for all keys and is not in the official Ex Libris docs. This means we can't programmatically determine which TOUs each FU uses — the tool shows locations and TOUs as separate browsable views instead.
- Each campus has a daily API request quota. Running `--all` for many campuses in quick succession can hit the daily threshold (HTTP 429 with `DAILY_THRESHOLD`).
- Single-campus Analytics mode requires per-campus report paths configured in `REPORT_PATHS` (currently only QC is configured). Use `--all` for any campus other than QC.

## Accessibility

The generated HTML aims for WCAG AA compliance:
- Semantic HTML5 landmarks (`<header>`, `<nav>`, `<main>`, `<footer>`)
- ARIA tablist/tabpanel pattern for view switching
- `aria-expanded` on collapsible TOU cards
- Skip-to-content link
- Live region announcements when switching campuses
- All color combinations meet 4.5:1 contrast ratio
- Keyboard-accessible interactive elements
- Table captions and labeled form controls
