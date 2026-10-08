"""
html_builder.py

Renders a single URL's collected report data (component -> log level ->
qualifying loghashes with before/after context) into a self-contained
HTML report, using the shared Google Material-style page shell from
theme.py.
"""

from datetime import datetime, timezone

import theme


def _render_loghash_section(entry: dict) -> str:
    loghash = theme.esc(entry["loghash"])
    mean = f'{entry["mean"]:.0f}'
    max_ = f'{entry["max"]:.0f}'
    total = f'{entry["total"]:.0f}'
    explore_url = theme.esc(entry["explore_url"])

    context_parts = [
        theme.render_log_line(ts, line, "context-before") for ts, line in entry["lines_before"]
    ]
    context_parts.append(theme.render_log_line(entry.get("sample_ts"), entry["sample_log"], "highlight"))
    context_parts.extend(
        theme.render_log_line(ts, line, "context-after") for ts, line in entry["lines_after"]
    )
    context_block = "\n".join(context_parts)

    return f"""
      <details class="loghash">
        <summary>
          <span class="loghash-id">{loghash}</span>
          <span class="stat">Mean {mean}</span>
          <span class="stat">Max {max_}</span>
          <span class="stat">Total {total}</span>
          <a class="explore-link" href="{explore_url}" target="_blank" rel="noopener">Open in Grafana &#8599;</a>
        </summary>
        <div class="loghash-body">
          <p class="context-label">5 logs before &rarr; first occurrence &rarr; 5 logs after</p>
          {context_block}
        </div>
      </details>"""


def _render_level_section(level_entry: dict) -> str:
    level = theme.esc(level_entry["level"])
    qualifying = level_entry["qualifying"]
    all_count = level_entry["all_count"]

    if not qualifying:
        body = '<p class="empty">No loghashes met the threshold for this log level.</p>'
    else:
        body = "\n".join(_render_loghash_section(entry) for entry in qualifying)

    return f"""
    <details class="level">
      <summary>
        <span class="level-name">{level}</span>
        <span class="badge">{len(qualifying)} of {all_count} loghash(es) qualify</span>
      </summary>
      <div class="level-body">
        {body}
      </div>
    </details>"""


def _render_component_section(component_entry: dict) -> str:
    component = theme.esc(component_entry["component"])
    levels_html = "\n".join(_render_level_section(le) for le in component_entry["levels"])
    total_qualifying = sum(len(le["qualifying"]) for le in component_entry["levels"])

    return f"""
  <details class="component">
    <summary>
      <span class="component-name">{component}</span>
      <span class="badge badge-primary">{total_qualifying} loghash(es) across {len(component_entry['levels'])} level(s)</span>
    </summary>
    <div class="component-body">
      {levels_html}
    </div>
  </details>"""


def build_report_html(report_data: list, url_cfg) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    components_html = "\n".join(_render_component_section(c) for c in report_data)

    meta_items = [
        f"Source: {url_cfg.label}",
        f"Environment: {url_cfg.environment}",
        f"Service: {url_cfg.servicename}",
        f"Range: {url_cfg.start_time} \u2192 {url_cfg.end_time}",
        f"Generated: {generated_at}",
    ]

    title = f"Blaze Log Report -- {url_cfg.label} ({url_cfg.environment}/{url_cfg.servicename})"
    return theme.page_shell(title, meta_items, components_html)
