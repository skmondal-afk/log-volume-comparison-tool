"""
loki_client.py

Loki query helpers parameterized by (url_cfg, component, log_level) so
the same functions work against either of the two compared dashboards
/ environments. url_cfg is a dashboard_url.UrlConfig (environment,
servicename, time range, datasource uid, org id); everything else
(Loki host, app name, step, ...) comes from config.py and is shared.
"""

import json
from datetime import datetime
from urllib.parse import quote

import requests

import config


def build_logql_query(url_cfg, component: str, log_level: str) -> str:
    stream_selector = (
        f'{{app="{config.APP_NAME}", '
        f'environment="{url_cfg.environment}", '
        f'servicename="{url_cfg.servicename}"}}'
    )
    line_filter = f'|~ "Z {log_level} +[a-zA-Z0-9-]+ +{component} "'
    # NOTE the doubled backslashes are intentional -- Loki parses this
    # as raw LogQL text, so the string literal needs \\ to produce a
    # literal \ for the regex engine.
    extract = (
        '| regexp ".*(?P<loghash>\\\\[[[:xdigit:]]+:[[:xdigit:]]+\\\\]).*"'
    )
    loghash_match = '| loghash =~ ".*"'

    return (
        f"sum(count_over_time({stream_selector}[1m] "
        f"{line_filter} {extract} {loghash_match})) by (loghash)"
    )


def _headers(api_token: str) -> dict:
    headers = {"Authorization": f"Bearer {api_token}"}
    if config.X_SCOPE_ORG_ID:
        headers["X-Scope-OrgID"] = config.X_SCOPE_ORG_ID
    return headers


def query_range(logql_query: str, url_cfg, api_token: str) -> dict:
    params = {
        "query": logql_query,
        "start": url_cfg.start_time,
        "end": url_cfg.end_time,
        "step": config.STEP_SECONDS,
    }

    url = f"{config.LOKI_BASE_URL}/loki/api/v1/query_range"
    resp = requests.get(url, headers=_headers(api_token), params=params, timeout=60)
    if not resp.ok:
        print(f"--- Request failed: {resp.status_code} ---")
        print(f"URL: {resp.url}")
        print(f"Response body: {resp.text}")
        print("---")
    resp.raise_for_status()
    return resp.json()


def compute_stats(result: dict) -> dict:
    """Returns {loghash: {"total": ..., "mean": ..., "max": ...}}"""
    stats = {}
    series_list = result.get("data", {}).get("result", [])

    for series in series_list:
        loghash = series.get("metric", {}).get("loghash", "<unknown>")
        values = [float(v[1]) for v in series.get("values", []) if v[1] is not None]
        if not values:
            continue

        entry = stats.setdefault(loghash, {"total": 0.0, "max": 0.0, "count": 0})
        entry["total"] += sum(values)
        entry["max"] = max(entry["max"], max(values))
        entry["count"] += len(values)

    for entry in stats.values():
        entry["mean"] = entry["total"] / entry["count"] if entry["count"] else 0.0
        del entry["count"]

    return stats


def build_sample_log_query(url_cfg, component: str, log_level: str, loghash: str) -> str:
    stream_selector = (
        f'{{app="{config.APP_NAME}", '
        f'environment="{url_cfg.environment}", '
        f'servicename="{url_cfg.servicename}"}}'
    )
    line_filter = f'|~ "Z {log_level} +[a-zA-Z0-9-]+ +{component} "'
    # loghash already includes its surrounding brackets (captured by the
    # \[...\] regex group), so don't add another pair here.
    loghash_filter = f'|= "{loghash}"'

    return f"{stream_selector} {line_filter} {loghash_filter}"


def fetch_sample_log(url_cfg, component: str, log_level: str, loghash: str, api_token: str):
    """Returns (timestamp_ns, log_line, stream_labels) for the FIRST
    occurrence of the loghash in the time range (i.e. when it started
    failing), or (None, placeholder, {}) if none is found."""
    params = {
        "query": build_sample_log_query(url_cfg, component, log_level, loghash),
        "start": url_cfg.start_time,
        "end": url_cfg.end_time,
        "limit": 1,
        "direction": "forward",
    }

    url = f"{config.LOKI_BASE_URL}/loki/api/v1/query_range"
    resp = requests.get(url, headers=_headers(api_token), params=params, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    for stream in result.get("data", {}).get("result", []):
        values = stream.get("values", [])
        if values:
            ts_ns, line = values[0]
            return ts_ns, line, stream.get("stream", {})

    return None, "<no log found>", {}


def build_stream_selector(labels: dict) -> str:
    # Confirmed via Grafana's "Show context" modal -- only these are true
    # indexed stream labels; anything else (e.g. detected_level) is
    # structured metadata and breaks the selector if included.
    context_label_keys = ("app", "environment", "instancename", "service_name", "servicename")
    pairs = ", ".join(
        f'{key}="{labels[key]}"' for key in context_label_keys if key in labels
    )
    return f"{{{pairs}}}"


def _extract_sorted_lines(result: dict) -> list:
    entries = []
    for stream in result.get("data", {}).get("result", []):
        entries.extend(stream.get("values", []))
    entries.sort(key=lambda item: int(item[0]))
    return entries


def fetch_log_context(url_cfg, ts_ns: str, labels: dict, api_token: str, before: int = None, after: int = None):
    """
    Returns (lines_before, lines_after) as lists of (timestamp_ns, line)
    tuples, each oldest-first, scoped to the exact stream (same
    instancename etc.) that produced the log at ts_ns -- matches
    Grafana's "Show context" behavior. Timestamps are kept (not just the
    text) so genuinely-repeated identical log lines can be told apart
    from a fetch bug -- their nanosecond timestamps will differ.

    The search window is CONTEXT_LOOKBACK_HOURS/CONTEXT_LOOKAHEAD_HOURS
    around ts_ns -- NOT clamped to url_cfg.start_time/end_time -- so
    context isn't cut short when the failure happens right at the edge
    of the report's own time range.
    """
    before = config.CONTEXT_LINES if before is None else before
    after = config.CONTEXT_LINES if after is None else after

    lookback_ns = int(config.CONTEXT_LOOKBACK_HOURS * 3600 * 1_000_000_000)
    lookahead_ns = int(config.CONTEXT_LOOKAHEAD_HOURS * 3600 * 1_000_000_000)
    before_start = str(max(int(ts_ns) - lookback_ns, 0))
    after_end = str(int(ts_ns) + lookahead_ns)

    stream_selector = build_stream_selector(labels)
    headers = _headers(api_token)
    url = f"{config.LOKI_BASE_URL}/loki/api/v1/query_range"

    # end is exclusive, so ts_ns itself is naturally excluded here
    before_params = {
        "query": stream_selector,
        "start": before_start,
        "end": ts_ns,
        "limit": before,
        "direction": "backward",
    }
    before_resp = requests.get(url, headers=headers, params=before_params, timeout=60)
    before_resp.raise_for_status()
    lines_before = _extract_sorted_lines(before_resp.json())

    # start is inclusive, so bump by 1ns to exclude the matched log itself
    after_params = {
        "query": stream_selector,
        "start": str(int(ts_ns) + 1),
        "end": after_end,
        "limit": after,
        "direction": "forward",
    }
    after_resp = requests.get(url, headers=headers, params=after_params, timeout=60)
    after_resp.raise_for_status()
    lines_after = _extract_sorted_lines(after_resp.json())

    return lines_before, lines_after


def _to_epoch_ms(rfc3339_ts: str) -> str:
    dt = datetime.fromisoformat(rfc3339_ts.replace("Z", "+00:00"))
    return str(int(dt.timestamp() * 1000))


def build_explore_url(url_cfg, component: str, log_level: str, loghash: str) -> str:
    """Returns a clickable Grafana Explore link for the loghash's sample-log query."""
    left_payload = {
        "datasource": url_cfg.datasource_uid,
        "queries": [
            {"refId": "A", "expr": build_sample_log_query(url_cfg, component, log_level, loghash)}
        ],
        "range": {
            "from": _to_epoch_ms(url_cfg.start_time),
            "to": _to_epoch_ms(url_cfg.end_time),
        },
    }
    left_json = quote(json.dumps(left_payload))
    return f"{config.GRAFANA_EXPLORE_BASE_URL}/explore?orgId={url_cfg.org_id}&left={left_json}"
