"""
config.py (html_report_compare)

Shared settings for the URL-comparison report generator. You can run
generate_reports.py in either of two ways:

  1. Fill in URL1/URL2/THRESHOLD/etc. below and just run:
         python generate_reports.py
  2. Or pass everything as CLI arguments instead (see generate_reports.py's
     module docstring) -- any CLI argument you provide overrides the
     matching value below; anything you omit falls back to this file.

This is a standalone tool -- it does not read or modify the top-level
main.py / config.py, nor the html_report/ tool.
"""

# ============================== AUTH ==============================
# Multi-tenant header value, if your Loki setup requires it. Set to
# None if not needed. The token itself is prompted at runtime.
X_SCOPE_ORG_ID = None


# =========================== ENDPOINT MODE ===========================
LOKI_BASE_URL = "https://logs.darkside.ea.com"

# Used only to build clickable Grafana Explore links in the reports --
# not used for the actual Loki queries above.
GRAFANA_EXPLORE_BASE_URL = "https://ea.grafana.net"


# ========================= DASHBOARD URLS =========================
# Paste full "BitC Blaze Log Dashboard" URLs here to run with no CLI
# arguments needed. Environment, servicename, time range, org id, and
# Loki datasource uid are all parsed out of these automatically -- see
# dashboard_url.py. Passing url1/url2 on the CLI overrides these.
#
# Leave URL2 = None to generate a single report for URL1 only.

URL1 = "https://ea.grafana.net/d/BitC_AFB_SYSTEST/bitc-blaze-dashboard-afb?orgId=1&from=2026-08-27T15:12:04.000Z&to=2026-08-28T03:52:48.340Z&timezone=utc&var-blaze_environment=test&var-blaze_servicename=madden-2027-common-stress&var-prom_datasource_data=gs-sports-madden-2027-bitc-lt-metrics&var-Datasource=921414026&var-loki_datasource_data=gs-sports-madden-2027-bitc-lt-logs&var-loki_datasource=130352841&var-blaze_nodepools=$__all&var-cluster=$__all&var-blaze_hpa_instancetypes_cpu=$__all&var-blaze_hpa_instancetypes_mem=$__all&var-blaze_hpa_instancetypes_custom=$__all&var-blaze_desired_pods=2186&var-blaze_running_pods_on_latest_rollout=&var-blaze_components=$__all&var-blaze_instancetypes=$__all&var-Ext_services=$__all&var-datasource=3222088095&var-fast_metrics_mode=or&refresh=auto"

URL2 = "https://ea.grafana.net/d/BitC_AFB_SYSTEST/bitc-blaze-dashboard-afb?orgId=1&from=2026-09-07T13:55:13.545Z&to=2026-09-08T03:06:59.114Z&timezone=utc&var-blaze_environment=test&var-blaze_servicename=madden-2027-common-stress&var-prom_datasource_data=gs-sports-madden-2027-bitc-lt-metrics&var-Datasource=921414026&var-loki_datasource_data=gs-sports-madden-2027-bitc-lt-logs&var-loki_datasource=130352841&var-blaze_nodepools=$__all&var-cluster=$__all&var-blaze_hpa_instancetypes_cpu=$__all&var-blaze_hpa_instancetypes_mem=$__all&var-blaze_hpa_instancetypes_custom=$__all&var-blaze_desired_pods=2186&var-blaze_running_pods_on_latest_rollout=&var-blaze_components=$__all&var-blaze_instancetypes=$__all&var-Ext_services=$__all&var-datasource=3222088095&var-fast_metrics_mode=or&refresh=auto"


# ========================= QUERY PARAMETERS =========================
APP_NAME = "blaze-app"

# Path to an .xlsx file listing the components to check. Expects a
# header row with a column named "component" (case-insensitive); if no
# such header is found, the first column is used instead.
COMPONENTS_XLSX_PATH = "components.xlsx"

# Log levels checked for EVERY component, on BOTH urls -- each becomes
# its own accordion section under that component in the report.
LOG_LEVELS = ["ERR", "WARN", "FAIL"]

# Grafana auto-picks step based on panel width/time range -- check each
# dashboard's Inspect -> Query ("Step: ...") and match it here. If the
# two dashboards use different steps, set the larger one here (or edit
# STEP_SECONDS per-url in dashboard_url.py if they truly differ).
STEP_SECONDS = 120


# ============================= THRESHOLD =============================
THRESHOLD = 1000000  # loghashes whose chosen metric >= THRESHOLD are selected

# Which per-loghash statistic to compare against THRESHOLD -- must be
# one of "total", "mean", "max".
THRESHOLD_METRIC = "total"

# How many log lines to show before/after each loghash's first
# occurrence in the reports.
CONTEXT_LINES = 5

# How far before/after the matched log line to search for those
# CONTEXT_LINES -- independent of the dashboard's own START_TIME/END_TIME,
# so context isn't cut short when the failure happens right at the edge
# of the reporting window (matches Grafana's own "Show context" behavior,
# which uses a fixed window around the log line, not the panel's range).
CONTEXT_LOOKBACK_HOURS = 2
CONTEXT_LOOKAHEAD_HOURS = 2


# ============================= OUTPUT =============================
# Directory where report_test1.html / report_test2.html / report_comparison.html
# get written. Use "." for the current directory.
OUTPUT_DIR = "."
