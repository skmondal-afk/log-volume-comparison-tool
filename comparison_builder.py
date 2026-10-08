"""
comparison_builder.py

Renders the cross-URL comparison sections (only-in-test1, only-in-test2,
common-to-both, and the prod/LT "reproduction" section(s)) into a
single self-contained HTML report, using the shared page shell from
theme.py.

Expects `sections`: a list of
{
  "title": str,
  "description": str,
  "badge_class": str,           # CSS class for the count badge
  "groups": [
      {
        "component": str,
        "level": str,
        "items": [
            {
              "loghash": str,
              "stats": {url_label: {"mean":.., "max":.., "total":..} | None},
              "explore_urls": {url_label: url},
              "context_source_label": str | None,
              "sample_log": str | None,
              "sample_ts": str | None,       # Loki nanosecond-epoch timestamp
              "lines_before": [(ts_ns, line), ...],
              "lines_after": [(ts_ns, line), ...],
            }, ...
        ]
      }, ...
  ]
}
"""

from datetime import datetime, timezone

import theme


def _render_item(item: dict, url_labels: list) -> str:
    loghash = theme.esc(item["loghash"])

    header_cells = "".join(
        f"<th>{theme.esc(lbl)} Mean</th><th>{theme.esc(lbl)} Max</th><th>{theme.esc(lbl)} Total</th>"
        for lbl in url_labels
    )
    value_cells = []
    for lbl in url_labels:
        stats = item["stats"].get(lbl)
        if stats:
            value_cells.append(
                f'<td>{stats["mean"]:.0f}</td><td>{stats["max"]:.0f}</td><td>{stats["total"]:.0f}</td>'
            )
        else:
            value_cells.append('<td class="not-present" colspan="3">not present</td>')

    table = (
        f'<table class="compare-table"><tr><th>Loghash</th>{header_cells}</tr>'
        f'<tr><td>{loghash}</td>{"".join(value_cells)}</tr></table>'
    )

    links = " &nbsp; ".join(
        f'<a class="explore-link" href="{theme.esc(url)}" target="_blank" rel="noopener">'
        f'Open {theme.esc(lbl)} in Grafana &#8599;</a>'
        for lbl, url in item["explore_urls"].items()
    )

    if item.get("sample_log"):
        context_parts = [
            theme.render_log_line(ts, line, "context-before") for ts, line in item.get("lines_before", [])
        ]
        context_parts.append(theme.render_log_line(item.get("sample_ts"), item["sample_log"], "highlight"))
        context_parts.extend(
            theme.render_log_line(ts, line, "context-after") for ts, line in item.get("lines_after", [])
        )
        context_html = (
            f'<p class="context-label">5 logs before &rarr; first occurrence &rarr; 5 logs after '
            f'(from {theme.esc(item["context_source_label"])})</p>' + "\n".join(context_parts)
        )
    else:
        context_html = '<p class="empty">No log excerpt captured for this entry.</p>'

    return f"""
        <details class="loghash">
          <summary>
            <span class="loghash-id">{loghash}</span>
          </summary>
          <div class="loghash-body">
            {table}
            <p>{links}</p>
            {context_html}
          </div>
        </details>"""


def _render_dual_context_item(item: dict, url_labels: list) -> str:
    loghash = theme.esc(item["loghash"])

    header_cells = "".join(
        f"<th>{theme.esc(lbl)} Mean</th><th>{theme.esc(lbl)} Max</th><th>{theme.esc(lbl)} Total</th>"
        for lbl in url_labels
    )
    value_cells = []
    for lbl in url_labels:
        stats = item["stats"].get(lbl)
        if stats:
            value_cells.append(
                f'<td>{stats["mean"]:.0f}</td><td>{stats["max"]:.0f}</td><td>{stats["total"]:.0f}</td>'
            )
        else:
            value_cells.append('<td class="not-present" colspan="3">not present</td>')
    table = (
        f'<table class="compare-table"><tr><th>Loghash</th>{header_cells}</tr>'
        f'<tr><td>{loghash}</td>{"".join(value_cells)}</tr></table>'
    )

    links = " &nbsp; ".join(
        f'<a class="explore-link" href="{theme.esc(url)}" target="_blank" rel="noopener">'
        f'Open {theme.esc(lbl)} in Grafana &#8599;</a>'
        for lbl, url in item["explore_urls"].items()
    )

    verdict_class = "badge-common" if item["same_context"] else "badge-only-2"
    verdict = (
        f'<p><span class="badge {verdict_class}">{theme.esc(item["verdict_reason"])}</span> '
        f'<span class="stat">Matched-line similarity {item["matched_line_similarity"]:.0%}</span> '
        f'<span class="stat">5-before similarity {item["before_context_similarity"]:.0%}</span> '
        f'<span class="stat">Full-context similarity {item["full_context_similarity"]:.0%}</span></p>'
    )

    context_columns = []
    for lbl in url_labels:
        ctx = item["contexts"][lbl]
        parts = [theme.render_log_line(ts, line, "context-before") for ts, line in ctx["lines_before"]]
        parts.append(theme.render_log_line(ctx.get("sample_ts"), ctx["sample_log"], "highlight"))
        parts.extend(theme.render_log_line(ts, line, "context-after") for ts, line in ctx["lines_after"])
        context_columns.append(
            f'<div class="context-column">'
            f'<p class="context-label">{theme.esc(lbl)} context</p>'
            + "\n".join(parts)
            + "</div>"
        )
    contexts_html = f'<div class="dual-context-grid">{"".join(context_columns)}</div>'

    return f"""
        <details class="loghash">
          <summary>
            <span class="loghash-id">{loghash}</span>
          </summary>
          <div class="loghash-body">
            {table}
            <p>{links}</p>
            {verdict}
            {contexts_html}
          </div>
        </details>"""


def _render_group(group: dict, url_labels: list, dual_context: bool = False) -> str:
    renderer = _render_dual_context_item if dual_context else _render_item
    items_html = "\n".join(renderer(item, url_labels) for item in group["items"])
    return f"""
    <details class="group">
      <summary>
        <span class="group-title">{theme.esc(group['component'])} / {theme.esc(group['level'])}</span>
        <span class="badge">{len(group['items'])} loghash(es)</span>
      </summary>
      <div class="group-body">
        {items_html}
      </div>
    </details>"""


def _render_section(section: dict, url_labels: list) -> str:
    dual_context = section.get("dual_context", False)
    non_empty_groups = [g for g in section["groups"] if g["items"]]
    total_items = sum(len(g["items"]) for g in non_empty_groups)

    if total_items == 0:
        groups_html = '<p class="empty">No matching loghashes.</p>'
    else:
        groups_html = "\n".join(_render_group(g, url_labels, dual_context) for g in non_empty_groups)

    badge_class = section.get("badge_class", "")
    return f"""
  <h2 class="section-title">{theme.esc(section['title'])} <span class="badge {badge_class}">{total_items}</span></h2>
  <p class="section-desc">{theme.esc(section['description'])}</p>
  {groups_html}"""


def build_comparison_html(sections: list, url_configs: list, scenario: str) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    url_labels = [u.label for u in url_configs]

    meta_items = [
        f"{u.label}: {u.environment}/{u.servicename} ({u.start_time} -> {u.end_time})"
        for u in url_configs
    ]
    meta_items.append(
        f"Scenario: {'PROD vs LT' if scenario == 'prod_vs_lt' else 'same environment type'}"
    )
    meta_items.append(f"Generated: {generated_at}")

    body = "\n".join(_render_section(s, url_labels) for s in sections)
    title = "Blaze Log Comparison Report"
    return theme.page_shell(title, meta_items, body)
