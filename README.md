# Log Volume Comparison Tool

Compares log volume (per-loghash error/warning/fail counts) between two Grafana "BitC Blaze Log Dashboard" runs, and generates self-contained HTML reports highlighting which loghashes crossed a configurable threshold.

## What it does

- Reads a list of components from an `.xlsx` file.
- Queries Loki (via its Prometheus-compatible `query_range` API) once per component × log level, for one or two dashboard URLs.
- Flags loghashes whose Mean/Max/Total count crosses a configured threshold.
- Fetches sample log lines and surrounding context (before/after) for each flagged loghash.
- Generates:
  - A per-URL HTML report showing violations for that run.
  - A comparison HTML report (when two URLs are given) showing:
    - Loghashes only violating in run 1
    - Loghashes only violating in run 2
    - Loghashes violating in both (with context similarity verdicts)
    - A "reproduction" section (e.g. prod vs. load-test) showing whether a violation reproduces on the other side at all

## Requirements

- Python 3.9+
- A Loki/Grafana API token with read access to the relevant logs

## Setup

```bash
pip install -r requirements.txt
```

## Configuration

Edit [`config.py`](config.py):

| Setting | Description |
|---|---|
| `URL1` / `URL2` | Full Grafana dashboard URLs to compare (leave `URL2 = None` for a single report) |
| `COMPONENTS_XLSX_PATH` | Path to the `.xlsx` file listing components to check |
| `LOG_LEVELS` | Log levels checked for every component (e.g. `ERR`, `WARN`, `FAIL`) |
| `THRESHOLD` / `THRESHOLD_METRIC` | The value and stat (`total`/`mean`/`max`) that flags a loghash |
| `STEP_SECONDS` | Must match the step shown in Grafana's Inspect → Query panel |
| `CONTEXT_LINES`, `CONTEXT_LOOKBACK_HOURS`, `CONTEXT_LOOKAHEAD_HOURS` | Controls the before/after log context captured per loghash |
| `OUTPUT_DIR` | Where the generated HTML reports are written |

## Usage

```bash
python generate_reports.py
```

Or override config values via CLI arguments:

```bash
python generate_reports.py URL1 URL2 --threshold 1000000 --threshold_metric total --components components.xlsx
```

You'll be prompted for your Loki API token (input hidden).

## Output

- `report_<label1>.html` — violations for URL1
- `report_<label2>.html` — violations for URL2 (if URL2 given)
- `report_<label1>_vs_<label2>.html` — comparison report (if URL2 given)

## Project structure

```
config.py              # user-editable settings
generate_reports.py     # entry point / orchestration
dashboard_url.py        # parses Grafana dashboard URLs
loki_client.py          # Loki API queries + stats computation
comparison_builder.py   # renders comparison report sections
html_builder.py         # renders per-URL report
components.py           # reads component list from .xlsx
log_normalizer.py        # context similarity classification
theme.py                # shared HTML/CSS page shell
```