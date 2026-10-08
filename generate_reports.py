"""
generate_reports.py

Reads component list from an .xlsx file, queries Loki once per
(component x log level) for url1 (and url2, if given), and writes:

  - report_<label1>.html               -- loghashes violating threshold for url1
  - report_<label2>.html               -- loghashes violating threshold for url2 (if given)
  - report_<label1>_vs_<label2>.html   -- only-in-1 / only-in-2 / common /
                                           PROD-vs-LT (or same-type) reproduction
                                           sections (only if url2 is given)

Labels are derived from each URL's environment: same environment on
both sides -> "<env>1"/"<env>2" (e.g. test1/test2); different
environments -> the raw environment names (e.g. test/prod), since
those are already distinguishable.

This is a standalone tool -- it does not read or modify the top-level
main.py / config.py, nor the html_report/ tool.

Requires: requests, openpyxl (pip install requests openpyxl)

Usage -- two equivalent ways to run this:
  1. Fill in config.py (URL1/URL2/THRESHOLD/THRESHOLD_METRIC/COMPONENTS_XLSX_PATH), then:
         python generate_reports.py
  2. Or pass everything as CLI arguments (each one overrides its config.py value if given):
         python generate_reports.py URL1 [URL2] [--threshold N] [--threshold_metric total|mean|max] [--components components.xlsx] [--token TOKEN]

If --token is omitted, you'll be prompted for it securely (input hidden).
"""

import argparse
import os
from getpass import getpass

import comparison_builder
import components
import config
import dashboard_url
import html_builder
import loki_client
import log_normalizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Blaze log reports from one or two dashboard URLs.")
    parser.add_argument("url1", nargs="?", default=config.URL1, help="First dashboard URL")
    parser.add_argument("url2", nargs="?", default=config.URL2, help="Second dashboard URL (optional)")
    parser.add_argument("--threshold", type=float, default=config.THRESHOLD, help="Default: %(default)s")
    parser.add_argument(
        "--threshold_metric",
        choices=("total", "mean", "max"),
        default=config.THRESHOLD_METRIC,
        help="Default: %(default)s",
    )
    parser.add_argument("--components", default=config.COMPONENTS_XLSX_PATH, help="Path to components .xlsx")
    parser.add_argument("--token", default=None, help="Loki bearer token (omit to be prompted securely)")
    args = parser.parse_args()

    if not args.url1:
        parser.error("url1 is required (pass it as an argument, or set config.URL1 as a fallback default)")

    return args


def prompt_api_token() -> str:
    token = getpass("Prometheus query token: ").strip()
    if not token:
        raise ValueError("Prometheus query token is required")
    return token


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def collect_all_data(url_cfg, component_list: list, token: str) -> dict:
    """Returns {(component, level): {"stats": {...all loghashes...}, "qualifying": {...over-threshold, with context...}}}"""
    metric = config.THRESHOLD_METRIC.lower()
    if metric not in ("total", "mean", "max"):
        raise ValueError(f'THRESHOLD_METRIC must be "total", "mean", or "max", got {metric!r}')

    data = {}
    for component in component_list:
        for level in config.LOG_LEVELS:
            print(f"  [{url_cfg.label}] querying component={component!r} level={level!r} ...")
            logql_query = loki_client.build_logql_query(url_cfg, component, level)
            raw_result = loki_client.query_range(logql_query, url_cfg, token)
            stats = loki_client.compute_stats(raw_result)

            qualifying = {}
            over_threshold = {
                loghash: s for loghash, s in stats.items() if s[metric] >= config.THRESHOLD
            }
            for loghash, s in over_threshold.items():
                ts_ns, sample_log, labels = loki_client.fetch_sample_log(
                    url_cfg, component, level, loghash, token
                )
                lines_before, lines_after = [], []
                if ts_ns:
                    lines_before, lines_after = loki_client.fetch_log_context(
                        url_cfg, ts_ns, labels, token
                    )
                qualifying[loghash] = {
                    **s,
                    "sample_log": sample_log,
                    "sample_ts": ts_ns,
                    "lines_before": lines_before,
                    "lines_after": lines_after,
                    "explore_url": loki_client.build_explore_url(url_cfg, component, level, loghash),
                }

            data[(component, level)] = {"stats": stats, "qualifying": qualifying}

    return data


def build_report_data_for_html(data: dict, component_list: list) -> list:
    metric = config.THRESHOLD_METRIC.lower()
    report_data = []

    for component in component_list:
        levels = []
        for level in config.LOG_LEVELS:
            entry = data.get((component, level), {"stats": {}, "qualifying": {}})
            qualifying_sorted = sorted(
                entry["qualifying"].items(), key=lambda kv: kv[1][metric], reverse=True
            )
            qualifying_list = [{"loghash": loghash, **info} for loghash, info in qualifying_sorted]

            levels.append(
                {"level": level, "all_count": len(entry["stats"]), "qualifying": qualifying_list}
            )

        report_data.append({"component": component, "levels": levels})

    return report_data


def _make_comparison_item(
    loghash: str,
    component: str,
    level: str,
    url1_cfg,
    url2_cfg,
    qualifying_1: dict,
    qualifying_2: dict,
    stats_1: dict,
    stats_2: dict,
) -> dict:
    stats_by_label = {}
    explore_urls = {}
    context_source_label = None
    sample_log = None
    sample_ts = None
    lines_before, lines_after = [], []

    for label, cfg_obj, quals, all_stats in (
        (url1_cfg.label, url1_cfg, qualifying_1, stats_1),
        (url2_cfg.label, url2_cfg, qualifying_2, stats_2),
    ):
        entry = quals.get(loghash) or all_stats.get(loghash)
        if entry:
            stats_by_label[label] = {
                "mean": entry["mean"],
                "max": entry["max"],
                "total": entry["total"],
            }
            explore_urls[label] = loki_client.build_explore_url(cfg_obj, component, level, loghash)
        else:
            stats_by_label[label] = None

        if context_source_label is None and loghash in quals and quals[loghash].get("sample_log"):
            context_source_label = label
            sample_log = quals[loghash]["sample_log"]
            sample_ts = quals[loghash].get("sample_ts")
            lines_before = quals[loghash].get("lines_before", [])
            lines_after = quals[loghash].get("lines_after", [])

    return {
        "loghash": loghash,
        "stats": stats_by_label,
        "explore_urls": explore_urls,
        "context_source_label": context_source_label,
        "sample_log": sample_log,
        "sample_ts": sample_ts,
        "lines_before": lines_before,
        "lines_after": lines_after,
    }


def _make_dual_context_item(loghash, component, level, url1_cfg, url2_cfg, entry_1, entry_2):
    """For a loghash qualifying on BOTH sides -- both entry_1/entry_2 already
    have sample_log/lines_before/lines_after fetched, so no extra Loki calls
    are needed here."""
    before_1_text = [line for _, line in entry_1.get("lines_before", [])]
    after_1_text = [line for _, line in entry_1.get("lines_after", [])]
    before_2_text = [line for _, line in entry_2.get("lines_before", [])]
    after_2_text = [line for _, line in entry_2.get("lines_after", [])]

    verdict = log_normalizer.classify_context_match(
        entry_1["sample_log"], before_1_text, after_1_text,
        entry_2["sample_log"], before_2_text, after_2_text,
    )

    def _stats(entry):
        return {"mean": entry["mean"], "max": entry["max"], "total": entry["total"]}

    return {
        "loghash": loghash,
        "stats": {url1_cfg.label: _stats(entry_1), url2_cfg.label: _stats(entry_2)},
        "explore_urls": {
            url1_cfg.label: loki_client.build_explore_url(url1_cfg, component, level, loghash),
            url2_cfg.label: loki_client.build_explore_url(url2_cfg, component, level, loghash),
        },
        "contexts": {
            url1_cfg.label: {
                "sample_log": entry_1["sample_log"],
                "sample_ts": entry_1.get("sample_ts"),
                "lines_before": entry_1.get("lines_before", []),
                "lines_after": entry_1.get("lines_after", []),
            },
            url2_cfg.label: {
                "sample_log": entry_2["sample_log"],
                "sample_ts": entry_2.get("sample_ts"),
                "lines_before": entry_2.get("lines_before", []),
                "lines_after": entry_2.get("lines_after", []),
            },
        },
        **verdict,
    }


def build_comparison_sections(url1_cfg, url2_cfg, data1: dict, data2: dict, component_list: list, scenario: str) -> list:
    only_in_1_groups, only_in_2_groups, common_groups = [], [], []
    same_context_groups, diff_context_groups = [], []
    repro_groups_single = []  # prod_vs_lt scenario
    repro_groups_1_to_2, repro_groups_2_to_1 = [], []  # same_type scenario

    prod_cfg = lt_cfg = None
    if scenario == "prod_vs_lt":
        prod_cfg, lt_cfg = (url1_cfg, url2_cfg) if url1_cfg.is_prod else (url2_cfg, url1_cfg)

    for component in component_list:
        for level in config.LOG_LEVELS:
            entry1 = data1.get((component, level), {"stats": {}, "qualifying": {}})
            entry2 = data2.get((component, level), {"stats": {}, "qualifying": {}})
            qualifying_1, stats_1 = entry1["qualifying"], entry1["stats"]
            qualifying_2, stats_2 = entry2["qualifying"], entry2["stats"]

            def make_items(keys):
                return [
                    _make_comparison_item(
                        lh, component, level, url1_cfg, url2_cfg, qualifying_1, qualifying_2, stats_1, stats_2
                    )
                    for lh in keys
                ]

            only_1_keys = sorted(set(qualifying_1) - set(qualifying_2))
            only_2_keys = sorted(set(qualifying_2) - set(qualifying_1))
            common_keys = sorted(set(qualifying_1) & set(qualifying_2))

            only_in_1_groups.append({"component": component, "level": level, "items": make_items(only_1_keys)})
            only_in_2_groups.append({"component": component, "level": level, "items": make_items(only_2_keys)})
            common_groups.append({"component": component, "level": level, "items": make_items(common_keys)})

            same_items, diff_items = [], []
            for loghash in common_keys:
                item = _make_dual_context_item(
                    loghash, component, level, url1_cfg, url2_cfg, qualifying_1[loghash], qualifying_2[loghash]
                )
                (same_items if item["same_context"] else diff_items).append(item)
            same_context_groups.append({"component": component, "level": level, "items": same_items})
            diff_context_groups.append({"component": component, "level": level, "items": diff_items})

            if scenario == "prod_vs_lt":
                prod_qualifying = qualifying_1 if prod_cfg.label == url1_cfg.label else qualifying_2
                lt_stats = stats_2 if lt_cfg.label == url2_cfg.label else stats_1
                repro_keys = sorted(set(prod_qualifying) & set(lt_stats))
                repro_groups_single.append({"component": component, "level": level, "items": make_items(repro_keys)})
            else:
                repro_1_keys = sorted(set(qualifying_1) & set(stats_2))
                repro_2_keys = sorted(set(qualifying_2) & set(stats_1))
                repro_groups_1_to_2.append({"component": component, "level": level, "items": make_items(repro_1_keys)})
                repro_groups_2_to_1.append({"component": component, "level": level, "items": make_items(repro_2_keys)})

    sections = [
        {
            "title": f"Only violating in {url1_cfg.label} ({url1_cfg.environment}/{url1_cfg.servicename})",
            "description": "Loghashes that crossed the threshold in url1 but did not in url2.",
            "badge_class": "badge-only-1",
            "groups": only_in_1_groups,
        },
        {
            "title": f"Only violating in {url2_cfg.label} ({url2_cfg.environment}/{url2_cfg.servicename})",
            "description": "Loghashes that crossed the threshold in url2 but did not in url1.",
            "badge_class": "badge-only-2",
            "groups": only_in_2_groups,
        },
        {
            "title": "Violating in both",
            "description": "Loghashes that crossed the threshold in both url1 and url2.",
            "badge_class": "badge-common",
            "groups": common_groups,
        },
        {
            "title": "Violating in both -- same context",
            "description": (
                "Of the loghashes violating in both, these have a matching triggering log "
                "line once player/card/league/member ids, pointers, and timestamps are "
                "masked out -- i.e. the same underlying failure."
            ),
            "badge_class": "badge-common",
            "groups": same_context_groups,
            "dual_context": True,
        },
        {
            "title": "Violating in both -- different context",
            "description": (
                "Of the loghashes violating in both, these do NOT match after masking "
                "variable ids -- worth a manual look, since the same loghash fired for a "
                "structurally different reason on each side."
            ),
            "badge_class": "badge-only-2",
            "groups": diff_context_groups,
            "dual_context": True,
        },
    ]

    if scenario == "prod_vs_lt":
        sections.append(
            {
                "title": f"Violating in PROD ({prod_cfg.label}), also present in LT ({lt_cfg.label})",
                "description": (
                    "Loghashes that crossed the threshold in the PROD dashboard and also "
                    "appear at all in the LT dashboard's logs (regardless of whether they "
                    "crossed the threshold there) -- i.e. confirmed reproducible in LT."
                ),
                "badge_class": "badge-common",
                "groups": repro_groups_single,
            }
        )
    else:
        sections.append(
            {
                "title": f"Violating in {url1_cfg.label}, also present in {url2_cfg.label}",
                "description": (
                    f"Both environments are the same type ({url1_cfg.environment} vs "
                    f"{url2_cfg.environment}), so priority can't be assigned by environment. "
                    f"Loghashes that crossed the threshold in {url1_cfg.label} and also appear "
                    f"at all in {url2_cfg.label}'s logs."
                ),
                "badge_class": "badge-common",
                "groups": repro_groups_1_to_2,
            }
        )
        sections.append(
            {
                "title": f"Violating in {url2_cfg.label}, also present in {url1_cfg.label}",
                "description": (
                    f"Loghashes that crossed the threshold in {url2_cfg.label} and also appear "
                    f"at all in {url1_cfg.label}'s logs."
                ),
                "badge_class": "badge-common",
                "groups": repro_groups_2_to_1,
            }
        )

    return sections


def main():
    args = parse_args()
    token = args.token or prompt_api_token()

    config.THRESHOLD = args.threshold
    config.THRESHOLD_METRIC = args.threshold_metric

    url1_cfg = dashboard_url.parse_dashboard_url(args.url1, "url1")
    url2_cfg = dashboard_url.parse_dashboard_url(args.url2, "url2") if args.url2 else None
    dashboard_url.assign_labels(url1_cfg, url2_cfg)

    component_list = components.load_components(args.components)
    print(f"Loaded {len(component_list)} component(s) from {args.components}")

    print(f"\n=== Collecting data for {url1_cfg.label} ({url1_cfg.environment}/{url1_cfg.servicename}) ===")
    data1 = collect_all_data(url1_cfg, component_list, token)
    report_data1 = build_report_data_for_html(data1, component_list)
    path1 = os.path.join(config.OUTPUT_DIR, f"report_{url1_cfg.label}.html")
    _write(path1, html_builder.build_report_html(report_data1, url1_cfg))
    print(f"Report written to {path1}")

    if not url2_cfg:
        print("\nurl2 not given -- skipping comparison report.")
        return

    print(f"\n=== Collecting data for {url2_cfg.label} ({url2_cfg.environment}/{url2_cfg.servicename}) ===")
    data2 = collect_all_data(url2_cfg, component_list, token)
    report_data2 = build_report_data_for_html(data2, component_list)
    path2 = os.path.join(config.OUTPUT_DIR, f"report_{url2_cfg.label}.html")
    _write(path2, html_builder.build_report_html(report_data2, url2_cfg))
    print(f"Report written to {path2}")

    scenario = dashboard_url.determine_scenario(url1_cfg, url2_cfg)
    print(f"\nScenario: {scenario}")
    sections = build_comparison_sections(url1_cfg, url2_cfg, data1, data2, component_list, scenario)
    comparison_html = comparison_builder.build_comparison_html(sections, [url1_cfg, url2_cfg], scenario)
    path3 = os.path.join(config.OUTPUT_DIR, f"report_{url1_cfg.label}_vs_{url2_cfg.label}.html")
    _write(path3, comparison_html)
    print(f"Comparison report written to {path3}")


if __name__ == "__main__":
    main()
