"""
theme.py

Shared Google Material-style page shell (Roboto font, Material color
palette, light/dark toggle persisted via localStorage) plus small
rendering helpers, reused by both html_builder.py (single-url reports)
and comparison_builder.py (the 3rd comparison report).

Note: "Google Sans" itself isn't available on the public Google Fonts
CDN, so this uses Roboto (Google's own font, used throughout Material
Design) with system-ui fallbacks.
"""

import html as html_lib
from datetime import datetime, timezone


def esc(value) -> str:
    return html_lib.escape(str(value))


def format_ts_ns(ts_ns) -> str:
    """Formats a Loki nanosecond-epoch timestamp with full ns precision,
    so genuinely-distinct log entries with identical visible text (e.g.
    rapid duplicate spam) can still be told apart."""
    if not ts_ns:
        return ""
    ns = int(ts_ns)
    seconds, remainder_ns = divmod(ns, 1_000_000_000)
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S')}.{remainder_ns:09d}Z"


def render_log_line(ts_ns, line: str, css_class: str = "") -> str:
    classes = f"log-line {css_class}".strip()
    prefix = f"[{format_ts_ns(ts_ns)}] " if ts_ns else ""
    return f'<pre class="{classes}">{esc(prefix + line)}</pre>'


def page_shell(title: str, meta_items: list, body_html: str) -> str:
    meta_html = "\n".join(f"      <span>{esc(item)}</span>" for item in meta_items)

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{_CSS}
</style>
</head>
<body>
  <header class="app-bar">
    <div class="app-bar-title">
      <span class="logo-dot dot-blue"></span><span class="logo-dot dot-red"></span><span class="logo-dot dot-yellow"></span><span class="logo-dot dot-green"></span>
      <span class="title-text">{esc(title)}</span>
    </div>
    <div class="app-bar-meta">
{meta_html}
    </div>
    <button id="theme-toggle" class="theme-toggle" title="Toggle dark mode" aria-label="Toggle dark mode">&#127769;</button>
  </header>
  <main>
{body_html}
  </main>
<script>
{_JS}
</script>
</body>
</html>
"""


_CSS = """
:root {
  --color-bg: #ffffff;
  --color-surface: #f8f9fa;
  --color-surface-alt: #ffffff;
  --color-border: #dadce0;
  --color-text: #202124;
  --color-text-secondary: #5f6368;
  --color-primary: #1a73e8;
  --color-error: #d93025;
  --color-error-bg: #fce8e6;
  --color-success: #188038;
  --color-success-bg: #e6f4ea;
  --color-warn: #e37400;
  --color-warn-bg: #fef7e0;
  --shadow: 0 1px 2px rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15);
}

[data-theme="dark"] {
  --color-bg: #202124;
  --color-surface: #292a2d;
  --color-surface-alt: #303134;
  --color-border: #5f6368;
  --color-text: #e8eaed;
  --color-text-secondary: #9aa0a6;
  --color-primary: #8ab4f8;
  --color-error: #f28b82;
  --color-error-bg: #3c2a29;
  --color-success: #81c995;
  --color-success-bg: #24322a;
  --color-warn: #fdd663;
  --color-warn-bg: #362f1f;
  --shadow: 0 1px 2px rgba(0,0,0,0.5), 0 1px 3px 1px rgba(0,0,0,0.3);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  transition: background 0.2s ease, color 0.2s ease;
}

.app-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 10;
  flex-wrap: wrap;
}
.app-bar-title { display: flex; align-items: center; gap: 4px; font-size: 20px; font-weight: 500; }
.logo-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.dot-blue { background: #4285F4; } .dot-red { background: #EA4335; }
.dot-yellow { background: #FBBC05; } .dot-green { background: #34A853; }
.title-text { margin-left: 8px; }
.app-bar-meta {
  display: flex; gap: 16px; flex-wrap: wrap;
  font-size: 13px; color: var(--color-text-secondary); margin-left: auto;
}
.theme-toggle {
  border: 1px solid var(--color-border);
  background: var(--color-surface-alt);
  color: var(--color-text);
  border-radius: 20px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}
.theme-toggle:hover { box-shadow: var(--shadow); }

main { padding: 24px; max-width: 1200px; margin: 0 auto; }

h2.section-title {
  font-size: 18px;
  font-weight: 500;
  margin: 28px 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--color-primary);
}
p.section-desc { color: var(--color-text-secondary); font-size: 13px; margin: -4px 0 12px 0; }

details.component, details.level, details.loghash, details.group {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}
details.component > summary,
details.level > summary,
details.loghash > summary,
details.group > summary {
  cursor: pointer;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  list-style: none;
  font-weight: 500;
  user-select: none;
  flex-wrap: wrap;
}
summary::-webkit-details-marker { display: none; }
summary::before {
  content: "\\25B6";
  display: inline-block;
  transition: transform 0.15s ease;
  color: var(--color-primary);
  font-size: 11px;
}
details[open] > summary::before { transform: rotate(90deg); }

.component-name { font-size: 16px; }
.level-name { font-size: 14px; color: var(--color-primary); }
.loghash-id { font-family: 'Roboto Mono', monospace; font-size: 13px; }
.group-title { font-size: 15px; }

.badge {
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 2px 10px;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-left: auto;
}
.badge-primary { color: var(--color-primary); border-color: var(--color-primary); }
.badge-only-1, .badge-only-2 { color: var(--color-warn); border-color: var(--color-warn); }
.badge-common { color: var(--color-success); border-color: var(--color-success); }

.component-body { padding: 0 16px 16px 16px; }
.level-body { padding: 0 0 0 16px; }
.loghash-body { padding: 0 16px 16px 16px; }
.group-body { padding: 0 16px 16px 16px; }

.stat {
  font-size: 12px; color: var(--color-text-secondary);
  background: var(--color-surface-alt); border: 1px solid var(--color-border);
  border-radius: 8px; padding: 2px 8px;
}
.explore-link { margin-left: auto; font-size: 13px; color: var(--color-primary); text-decoration: none; }
.explore-link:hover { text-decoration: underline; }

.context-label { font-size: 12px; color: var(--color-text-secondary); margin: 8px 0; }

.log-line {
  font-family: 'Roboto Mono', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  border-left: 3px solid transparent;
  border-radius: 4px;
  padding: 6px 10px;
  margin: 4px 0;
}
.log-line.context-before, .log-line.context-after {
  border-left-color: var(--color-text-secondary);
  opacity: 0.85;
}
.log-line.highlight {
  border-left-color: var(--color-error);
  background: var(--color-error-bg);
  font-weight: 500;
  opacity: 1;
}

table.compare-table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0 16px 0;
  font-size: 13px;
}
table.compare-table th, table.compare-table td {
  border: 1px solid var(--color-border);
  padding: 6px 10px;
  text-align: right;
}
table.compare-table th:first-child, table.compare-table td:first-child { text-align: left; }
table.compare-table th {
  background: var(--color-surface-alt);
  font-weight: 500;
}
.not-present { color: var(--color-text-secondary); font-style: italic; }

.dual-context-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}
.context-column {
  min-width: 0;
  border-left: 1px solid var(--color-border);
  padding-left: 12px;
}
.context-column:first-child { border-left: none; padding-left: 0; }
@media (max-width: 900px) {
  .dual-context-grid { grid-template-columns: 1fr; }
  .context-column { border-left: none; padding-left: 0; border-top: 1px solid var(--color-border); padding-top: 12px; }
  .context-column:first-child { border-top: none; padding-top: 0; }
}

.empty { color: var(--color-text-secondary); font-style: italic; padding: 8px 0; }
"""

_JS = """
(function () {
  var root = document.documentElement;
  var toggle = document.getElementById('theme-toggle');
  var saved = localStorage.getItem('blaze-report-theme');
  var preferred = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  root.setAttribute('data-theme', preferred);
  toggle.textContent = preferred === 'dark' ? String.fromCodePoint(0x2600) : String.fromCodePoint(0x1F319);

  toggle.addEventListener('click', function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('blaze-report-theme', next);
    toggle.textContent = next === 'dark' ? String.fromCodePoint(0x2600) : String.fromCodePoint(0x1F319);
  });
})();
"""
