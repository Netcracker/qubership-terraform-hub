#!/usr/bin/env python3
"""
AWS Cost Report Generator (private S3)
- Fetches data from Cost Explorer
- Generates HTML report with daily chart, tag breakdown, and untagged-by-service
- Generates PDF report (optional, requires reportlab)
- Exports daily spend by cost-usage tag to costs.csv
- "Usage by type" is optional (--include-usage)
- Uploads HTML, PDF, CSV (+ meta/index) to a private S3 bucket
- Writes S3 paths to GitHub Actions Job Summary
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # allow local demo without AWS SDK
    boto3 = None  # type: ignore

    class ClientError(Exception):  # type: ignore
        pass

from jinja2 import Template

REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AWS Cost Report — {{ period_label }}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --border: #334155;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 2rem 1rem;
    }
    .container { max-width: 1100px; margin: 0 auto; }
    h1 { font-size: 1.75rem; margin-bottom: 0.25rem; }
    .subtitle { color: var(--muted); margin-bottom: 1.5rem; }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .nav { margin-bottom: 1.5rem; font-size: 0.9rem; }
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem;
    }
    .card .label { color: var(--muted); font-size: 0.85rem; }
    .card .value { font-size: 1.4rem; font-weight: 600; margin-top: 0.25rem; }
    .chart-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 2rem;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--card);
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid var(--border);
    }
    th, td {
      padding: 0.75rem 1rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    th { background: #0f172a; color: var(--muted); font-weight: 500; font-size: 0.85rem; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: rgba(56, 189, 248, 0.05); }
    .cost { font-variant-numeric: tabular-nums; }
    .bar {
      height: 6px;
      background: var(--border);
      border-radius: 3px;
      overflow: hidden;
      margin-top: 4px;
    }
    .bar-fill { height: 100%; background: var(--accent); border-radius: 3px; }
    details.tag-desc {
      margin-top: 0.35rem;
      font-size: 0.82rem;
      color: var(--muted);
    }
    details.tag-desc > summary {
      cursor: pointer;
      color: var(--accent);
      list-style: none;
      user-select: none;
    }
    details.tag-desc > summary::-webkit-details-marker { display: none; }
    details.tag-desc > summary::before {
      content: '▸ ';
      color: var(--accent);
    }
    details.tag-desc[open] > summary::before { content: '▾ '; }
    details.tag-desc .tag-desc-body {
      margin-top: 0.4rem;
      padding: 0.55rem 0.75rem;
      background: rgba(15, 23, 42, 0.55);
      border: 1px solid var(--border);
      border-radius: 8px;
      line-height: 1.45;
    }
    details.tag-desc .tag-desc-body p { margin: 0 0 0.35rem; }
    details.tag-desc .tag-desc-body p:last-child { margin-bottom: 0; }
    details.tag-desc .tag-desc-body ul {
      margin: 0.25rem 0 0.35rem 1.1rem;
      padding: 0;
    }
    details.tag-desc .tag-desc-body li { margin: 0.15rem 0; }
    footer {
      margin-top: 2.5rem;
      color: var(--muted);
      font-size: 0.85rem;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="nav"><a href="../index.html">← All reports</a></div>
    <h1>AWS Cost Report</h1>
    <p class="subtitle">{{ period_label }} · generated {{ generated_at }}</p>

    <div class="cards">
      <div class="card">
        <div class="label">Total cost</div>
        <div class="value">${{ "%.2f"|format(total_cost) }}</div>
      </div>
      <div class="card">
        <div class="label">Untagged services</div>
        <div class="value">{{ services|length }}</div>
      </div>
      <div class="card">
        <div class="label">Period</div>
        <div class="value" style="font-size:1rem">{{ start }} → {{ end }}</div>
      </div>
      <div class="card">
        <div class="label">Days</div>
        <div class="value">{{ days }}</div>
      </div>
    </div>

    <div class="chart-card">
      <h2 style="margin-bottom:1rem;font-size:1.1rem">Daily spend</h2>
      <canvas id="dailyChart" height="140"></canvas>
    </div>

    <div class="chart-card">
      <h2 style="margin-bottom:1rem;font-size:1.1rem">Monthly trend (last {{ trend_months }} months)</h2>
      <canvas id="trendChart" height="120"></canvas>
    </div>
    {% if trend_rows %}
    <table style="margin-bottom:2rem">
      <thead>
        <tr>
          <th>Month</th>
          <th>Unblended</th>
          <th>Change</th>
        </tr>
      </thead>
      <tbody>
        {% for t in trend_rows %}
        <tr>
          <td>{{ t.label }}</td>
          <td class="cost">${{ "%.2f"|format(t.unblended) }}</td>
          <td>
            {% if t.change is none %}
            —
            {% elif t.change > 0 %}
            <span style="color:#f87171">+{{ "%.1f"|format(t.change) }}%</span>
            {% elif t.change < 0 %}
            <span style="color:#34d399">{{ "%.1f"|format(t.change) }}%</span>
            {% else %}
            0.0%
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% endif %}

    <h2 style="margin:2rem 0 1rem;font-size:1.1rem">By tag: cost-usage</h2>
    <p style="color:var(--muted);font-size:0.9rem;margin-bottom:1rem">
      Costs grouped by the cost allocation tag <code style="color:var(--accent)">cost-usage</code>.
      Untagged spend appears as <em>(untagged)</em>.
    </p>
    {% if tag_rows %}
    <table>
      <thead>
        <tr>
          <th>Tag value</th>
          <th>Unblended</th>
          <th>Amortized</th>
          <th>Share</th>
        </tr>
      </thead>
      <tbody>
        {% for t in tag_rows %}
        <tr>
          <td>
            <code style="color:var(--text)">{{ t.name }}</code>
            {# {% if t.desc %}
            <details class="tag-desc">
              <summary>description</summary>
              <div class="tag-desc-body">
                <p>{{ t.desc.summary }}</p>
                {% if t.desc.resources %}
                <p><strong style="color:var(--text)">Resources:</strong></p>
                <ul>
                  {% for item in t.desc.resources %}
                  <li>{{ item }}</li>
                  {% endfor %}
                </ul>
                {% endif %}
                {% if t.desc.owner %}
                <p><strong style="color:var(--text)">Owner:</strong> {{ t.desc.owner }}</p>
                {% endif %}
                {% if t.desc.notes %}
                <ul>
                  {% for note in t.desc.notes %}
                  <li>{{ note }}</li>
                  {% endfor %}
                </ul>
                {% endif %}
              </div>
            </details>
            {% endif %} #}
          </td>
          <td class="cost">${{ "%.2f"|format(t.unblended) }}</td>
          <td class="cost">${{ "%.2f"|format(t.amortized) }}</td>
          <td>
            {{ "%.1f"|format(t.share) }}%
            <div class="bar"><div class="bar-fill" style="width:{{ [t.share, 100]|min }}%"></div></div>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p style="color:var(--muted);margin-bottom:1.5rem">
      No data for tag <code>cost-usage</code>. Ensure it is activated as a cost allocation tag
      in Billing → Cost allocation tags.
    </p>
    {% endif %}

    <h2 style="margin:2rem 0 1rem;font-size:1.1rem">By service (untagged)</h2>
    <p style="color:var(--muted);font-size:0.9rem;margin-bottom:1rem">
      Breakdown of the <em>(untagged)</em> row above — spend on resources without the
      <code style="color:var(--accent)">cost-usage</code> tag.
    </p>
    {% if services %}
    <table>
      <thead>
        <tr>
          <th>Service</th>
          <th>Unblended</th>
          <th>Amortized</th>
          <th>Share</th>
        </tr>
      </thead>
      <tbody>
        {% for s in services %}
        <tr>
          <td>{{ s.name }}</td>
          <td class="cost">${{ "%.2f"|format(s.unblended) }}</td>
          <td class="cost">${{ "%.2f"|format(s.amortized) }}</td>
          <td>
            {{ "%.1f"|format(s.share) }}%
            <div class="bar"><div class="bar-fill" style="width:{{ [s.share, 100]|min }}%"></div></div>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p style="color:var(--muted);margin-bottom:1.5rem">
      No untagged spend in this period (or the tag is not activated).
    </p>
    {% endif %}

    {% if usage_rows %}
    <h2 style="margin:2rem 0 1rem;font-size:1.1rem">Usage by type</h2>
    <p style="color:var(--muted);font-size:0.9rem;margin-bottom:1rem">
      Each row is a single usage type (consistent unit). Rows under $0.01 omitted;
      top {{ usage_rows|length }} by cost.
    </p>
    <table>
      <thead>
        <tr>
          <th>Service</th>
          <th>Region</th>
          <th>Usage type</th>
          <th>Unblended</th>
          <th>Quantity</th>
          <th>Unit</th>
        </tr>
      </thead>
      <tbody>
        {% for u in usage_rows %}
        <tr>
          <td>{{ u.service }}</td>
          <td>{{ u.region }}</td>
          <td>{{ u.usage_type }}</td>
          <td class="cost">${{ "%.2f"|format(u.unblended) }}</td>
          <td class="cost">{{ u.quantity_fmt }}</td>
          <td>{{ u.unit }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% endif %}

    <footer>
      Data from AWS Cost Explorer · UnblendedCost / AmortizedCost ·
      run #{{ run_id }}
    </footer>
  </div>

  <script>
    const dailyLabels = {{ daily_labels|tojson }};
    const chartSeries = {{ chart_series|tojson }};
    const datasets = chartSeries.map((s) => ({
      label: s.label,
      data: s.data,
      backgroundColor: s.backgroundColor,
      borderWidth: 0,
      borderRadius: 2,
      stack: 'daily',
    }));
    new Chart(document.getElementById('dailyChart'), {
      type: 'bar',
      data: { labels: dailyLabels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        interaction: {
          mode: 'index',
          axis: 'x',
          intersect: false,
        },
        plugins: {
          legend: {
            display: true,
            position: 'bottom',
            labels: {
              color: '#94a3b8',
              boxWidth: 12,
              boxHeight: 12,
              padding: 16,
              font: { size: 12 },
            },
          },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            titleColor: '#e2e8f0',
            bodyColor: '#e2e8f0',
            borderColor: '#334155',
            borderWidth: 1,
            padding: 12,
            callbacks: {
              title: (items) => items.length ? items[0].label : '',
              label: (ctx) => {
                const v = ctx.parsed.y || 0;
                if (v < 0.005) return null;
                return ` ${ctx.dataset.label}: $${v.toFixed(2)}`;
              },
              footer: (items) => {
                const total = items.reduce((s, i) => s + (i.parsed.y || 0), 0);
                return `Total: $${total.toFixed(2)}`;
              },
            },
            footerColor: '#38bdf8',
            footerFont: { weight: 'bold' },
          },
        },
        scales: {
          y: {
            stacked: true,
            beginAtZero: true,
            ticks: {
              color: '#94a3b8',
              callback: (v) => '$' + v,
            },
            grid: { color: '#334155' },
          },
          x: {
            stacked: true,
            ticks: { color: '#94a3b8', maxRotation: 45 },
            grid: { display: false },
          },
        },
      },
    });

    const trendLabels = {{ trend_labels|tojson }};
    const trendSeries = {{ trend_series|tojson }};
    const trendDatasets = trendSeries.map((s) => ({
      label: s.label,
      data: s.data,
      backgroundColor: s.backgroundColor,
      borderWidth: 0,
      borderRadius: 2,
      stack: 'monthly',
    }));
    if (trendLabels.length) {
      new Chart(document.getElementById('trendChart'), {
        type: 'bar',
        data: { labels: trendLabels, datasets: trendDatasets },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          interaction: {
            mode: 'index',
            axis: 'x',
            intersect: false,
          },
          plugins: {
            legend: {
              display: true,
              position: 'bottom',
              labels: {
                color: '#94a3b8',
                boxWidth: 12,
                boxHeight: 12,
                padding: 16,
                font: { size: 12 },
              },
            },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.95)',
              titleColor: '#e2e8f0',
              bodyColor: '#e2e8f0',
              borderColor: '#334155',
              borderWidth: 1,
              padding: 12,
              callbacks: {
                title: (items) => items.length ? items[0].label : '',
                label: (ctx) => {
                  const v = ctx.parsed.y || 0;
                  if (v < 0.005) return null;
                  return ` ${ctx.dataset.label}: $${v.toFixed(2)}`;
                },
                footer: (items) => {
                  const total = items.reduce((s, i) => s + (i.parsed.y || 0), 0);
                  return `Total: $${total.toFixed(2)}`;
                },
              },
              footerColor: '#38bdf8',
              footerFont: { weight: 'bold' },
            },
          },
          scales: {
            y: {
              stacked: true,
              beginAtZero: true,
              ticks: {
                color: '#94a3b8',
                callback: (v) => '$' + v,
              },
              grid: { color: '#334155' },
            },
            x: {
              stacked: true,
              ticks: { color: '#94a3b8' },
              grid: { display: false },
            },
          },
        },
      });
    }
  </script>
</body>
</html>
"""

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AWS Cost Reports — History</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --border: #334155;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 2rem 1rem;
    }
    .container { max-width: 800px; margin: 0 auto; }
    h1 { font-size: 1.75rem; margin-bottom: 0.5rem; }
    .subtitle { color: var(--muted); margin-bottom: 2rem; }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--card);
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid var(--border);
    }
    th, td {
      padding: 0.85rem 1.1rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    th { background: #0f172a; color: var(--muted); font-weight: 500; font-size: 0.85rem; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: rgba(56, 189, 248, 0.05); }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .cost { font-variant-numeric: tabular-nums; font-weight: 500; }
    .badge {
      display: inline-block;
      font-size: 0.75rem;
      padding: 0.15rem 0.5rem;
      border-radius: 999px;
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent);
    }
    footer {
      margin-top: 2.5rem;
      color: var(--muted);
      font-size: 0.85rem;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>AWS Cost Reports</h1>
    <p class="subtitle">Report history · updated {{ generated_at }}</p>

    {% if reports %}
    <table>
      <thead>
        <tr>
          <th>Period</th>
          <th>Generated</th>
          <th>Cost</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {% for r in reports %}
        <tr>
          <td>
            {{ r.period_label }}
            {% if loop.first %}<span class="badge">latest</span>{% endif %}
          </td>
          <td>{{ r.generated_at }}</td>
          <td class="cost">${{ "%.2f"|format(r.total_cost) }}</td>
          <td><a href="{{ r.path }}">Open →</a></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p style="color:var(--muted)">No reports yet.</p>
    {% endif %}

    <footer>
      Stored in a private S3 bucket · access only for authorized users
    </footer>
  </div>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate AWS cost report and upload to S3")
    p.add_argument("--start-date", default="")
    p.add_argument("--end-date", default="")
    p.add_argument(
        "--previous-month",
        action="store_true",
        help="Use the previous full calendar month (overrides start/end dates)",
    )
    p.add_argument(
        "--trend-months",
        type=int,
        default=3,
        help="Number of months in the spend trend chart (default: 3)",
    )
    p.add_argument(
        "--include-usage",
        action="store_true",
        help="Include the optional 'Usage by type' table (extra Cost Explorer API calls)",
    )
    p.add_argument("--s3-bucket", required=True)
    p.add_argument("--s3-prefix", default="aws-cost-reports")
    p.add_argument("--run-id", default="local")
    p.add_argument("--local-dir", default="", help="Also write files locally (optional)")
    return p.parse_args()


def previous_calendar_month(today: date | None = None) -> tuple[date, date]:
    """Return [first_of_prev, first_of_this) for the last complete calendar month."""
    today = today or date.today()
    first_this = today.replace(day=1)
    first_prev = (first_this - timedelta(days=1)).replace(day=1)
    return first_prev, first_this


def resolve_period(
    start_str: str, end_str: str, previous_month: bool = False
) -> tuple[date, date]:
    """Return [start, end) for Cost Explorer (End is exclusive in the API).

    User-provided end_date is treated as **inclusive** (the last day of the report).
    """
    today = date.today()
    if previous_month:
        return previous_calendar_month(today)
    if start_str and end_str:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        # Inclusive end from the user → exclusive end for the API
        end = datetime.strptime(end_str, "%Y-%m-%d").date() + timedelta(days=1)
    elif start_str:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = today + timedelta(days=1)
    elif end_str:
        # Only end provided: from first of that month through inclusive end
        end_inclusive = datetime.strptime(end_str, "%Y-%m-%d").date()
        start = end_inclusive.replace(day=1)
        end = end_inclusive + timedelta(days=1)
    else:
        start = today.replace(day=1)
        end = today + timedelta(days=1)
    if end <= start:
        raise SystemExit(
            f"Invalid period: start={start} end_exclusive={end} "
            f"(user end must be on or after start)"
        )
    return start, end


def shift_month(d: date, delta: int) -> date:
    """Shift a date by `delta` months, keeping day=1."""
    y, m = d.year, d.month + delta
    while m <= 0:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return date(y, m, 1)


CHART_COLORS = [
    "rgba(56, 189, 248, 0.85)",   # sky
    "rgba(52, 211, 153, 0.85)",   # emerald
    "rgba(251, 191, 36, 0.85)",   # amber
    "rgba(248, 113, 113, 0.85)",  # red
    "rgba(167, 139, 250, 0.85)",  # violet
    "rgba(251, 146, 60, 0.85)",   # orange
    "rgba(45, 212, 191, 0.85)",   # teal
    "rgba(244, 114, 182, 0.85)",  # pink
    "rgba(148, 163, 184, 0.85)",  # slate (Other)
]

# Human-readable descriptions for cost-usage tag values (shown under each row).
# Keys are matched case-insensitively against the tag value from Cost Explorer.
TAG_DESCRIPTIONS: dict[str, dict] = {
    "(untagged)": {
        "summary": "Resources WITHOUT the cost-usage tag.",
        "resources": [
            "Monthly TAX fee (applied on the 1st day of each month, causing a cost spike)",
            "Any resources without cost-usage tag, e.g. Lambda (qstp-s3-notification until tagged)",
        ],
        "owner": None,
        "notes": None,
    },
    "common": {
        "summary": "Shared infrastructure resources used across multiple projects.",
        "resources": [
            "Shared databases",
            "VPC / networking",
            "Monitoring tools (Prometheus, Grafana, etc.)",
        ],
        "owner": None,
        "notes": None,
    },
    "Istio-SVT": {
        "summary": "Cloud core Istio integration research.",
        "resources": [
            "EKS Kubernetes cluster, worker nodes, load balancers, and related AWS infrastructure",
        ],
        "owner": "Aleksandr Iglin",
        "notes": None,
    },
    "api-hub": {
        "summary": "API-Hub test environment in Qubership AWS.",
        "resources": [
            "EKS Kubernetes cluster, worker nodes, load balancers, and related AWS infrastructure",
        ],
        "owner": "Aleksandr Agishev",
        "notes": None,
    },
    "cncf_report": {
        "summary": "CNCF cloud report (exadmin.github.io/opensource_team_monitor).",
        "resources": [
            "S3 storage, static site hosting (CloudFront), and supporting AWS services",
        ],
        "owner": "Ilya Smirnov",
        "notes": None,
    },
    "github-runner": {
        "summary": "Obsolete; previously used by OpenSearch autotests.",
        "resources": [
            "EC2 instances running ephemeral GitHub Actions runners",
        ],
        "owner": "Sergey Ivanov",
        "notes": None,
    },
    "pioneer": {
        "summary": "Qubership sandbox environment.",
        "resources": [
            "EKS Kubernetes cluster (VPC, NAT gateway, node groups, EBS volumes, ELB), and related resources",
        ],
        "owner": "Qubership DevOps team",
        "notes": None,
    },
    "qstp": {
        "summary": "ATP project.",
        "resources": [
            "S3 buckets (qstp-results, qstp-consul)",
            "Lambda (qstp-s3-notification — triggers GitHub Actions on new test results)",
            "Related infrastructure",
        ],
        "owner": "Denis Arychkov",
        "notes": None,
    },
}


def lookup_tag_description(tag_name: str) -> dict | None:
    """Return description dict for a cost-usage tag value, or None if unknown."""
    if tag_name in TAG_DESCRIPTIONS:
        return TAG_DESCRIPTIONS[tag_name]
    lower_map = {k.lower(): v for k, v in TAG_DESCRIPTIONS.items()}
    return lower_map.get(tag_name.lower())


def build_stacked_series(
    labels: list[str],
    by_key: dict[str, dict[str, float]],
    totals: dict[str, float],
    top_n: int = 8,
) -> list[dict]:
    top_names = [n for n, _ in sorted(totals.items(), key=lambda x: -x[1])[:top_n]]
    top_set = set(top_names)
    series: list[dict] = []
    for i, name in enumerate(top_names):
        series.append(
            {
                "label": name,
                "data": [round(by_key.get(lab, {}).get(name, 0.0), 2) for lab in labels],
                "backgroundColor": CHART_COLORS[i % (len(CHART_COLORS) - 1)],
            }
        )
    other_data = []
    for lab in labels:
        other = sum(v for k, v in by_key.get(lab, {}).items() if k not in top_set)
        other_data.append(round(other, 2))
    if any(x > 0 for x in other_data):
        series.append(
            {
                "label": "Other",
                "data": other_data,
                "backgroundColor": CHART_COLORS[-1],
            }
        )
    return series


def fetch_costs(
    client,
    start: date,
    end: date,
    tag_key: str = "cost-usage",
    include_usage: bool = False,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[str], list[dict], float]:
    """Return (daily, untagged_services, usage_rows, tag_rows, daily_labels, chart_series, total_cost).

    untagged_services: costs by SERVICE filtered to resources without `tag_key`
      (breakdown of the (untagged) row in the tag table).
    usage_rows are optional (only if include_usage); grouped by SERVICE + USAGE_TYPE.
    tag_rows are grouped by cost allocation tag `tag_key`.
    chart_series is stacked daily spend by top services for Chart.js.
    total_cost is CE Total.UnblendedCost for the report period (MONTHLY aggregation,
    same basis as the trend table — used for invoicing header figure).
    """
    # Authoritative period total — same source as monthly trend rows (CE Total).
    # Do NOT derive this from summed daily rows: management invoices off the header.
    total_resp = client.get_cost_and_usage(
        TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
    )
    total_cost = 0.0
    for r in total_resp.get("ResultsByTime", []):
        total_metrics = r.get("Total") or {}
        if "UnblendedCost" in total_metrics:
            total_cost += float(total_metrics["UnblendedCost"]["Amount"])
    total_cost = round(total_cost, 2)
    print(f"  period Total.UnblendedCost: ${total_cost:.2f}")

    # Daily costs broken down by service (for stacked chart + daily table)
    daily_resp = client.get_cost_and_usage(
        TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    daily_labels: list[str] = []
    # date -> {service: cost} (for stacked chart; tiny lines may be omitted from series)
    daily_by_svc: dict[str, dict[str, float]] = {}
    svc_totals: dict[str, float] = defaultdict(float)
    daily_full: dict[str, float] = {}
    for r in daily_resp["ResultsByTime"]:
        day = r["TimePeriod"]["Start"]
        daily_labels.append(day)
        daily_by_svc[day] = {}
        total_metrics = r.get("Total") or {}
        if "UnblendedCost" in total_metrics:
            daily_full[day] = float(total_metrics["UnblendedCost"]["Amount"])
        else:
            daily_full[day] = 0.0
        for g in r.get("Groups", []):
            name = g["Keys"][0]
            amount = float(g["Metrics"]["UnblendedCost"]["Amount"])
            if "UnblendedCost" not in total_metrics:
                daily_full[day] += amount
            if amount < 0.005:
                continue
            daily_by_svc[day][name] = amount
            svc_totals[name] += amount

    # Top services for the chart; rest → "Other"
    chart_series = build_stacked_series(daily_labels, daily_by_svc, svc_totals, top_n=8)

    daily: list[dict] = [
        {"date": d, "cost": round(daily_full.get(d, 0.0), 2)} for d in daily_labels
    ]

    # --- Untagged services only (ABSENT cost-usage tag) ---
    # Breakdown of the (untagged) row from the tag table.
    services: list[dict] = []
    try:
        untagged_resp = client.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost", "AmortizedCost"],
            Filter={
                "Tags": {
                    "Key": tag_key,
                    "MatchOptions": ["ABSENT"],
                }
            },
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        svc_agg: dict[str, dict] = defaultdict(lambda: {"unblended": 0.0, "amortized": 0.0})
        for r in untagged_resp["ResultsByTime"]:
            for g in r.get("Groups", []):
                name = g["Keys"][0]
                svc_agg[name]["unblended"] += float(g["Metrics"]["UnblendedCost"]["Amount"])
                svc_agg[name]["amortized"] += float(g["Metrics"]["AmortizedCost"]["Amount"])

        for name, v in svc_agg.items():
            if v["unblended"] < 0.005 and v["amortized"] < 0.005:
                continue
            services.append(
                {
                    "name": name,
                    "unblended": v["unblended"],
                    "amortized": v["amortized"],
                }
            )
        services.sort(key=lambda x: x["unblended"], reverse=True)
        print(f"  untagged services: {len(services)}")
    except ClientError as e:
        print(f"  untagged services query skipped: {e}")

    # --- Optional: Usage by type (expensive — many API calls) ---
    usage_rows: list[dict] = []
    if include_usage:
        # Prefer top untagged services; fall back to overall top from daily totals
        top_for_usage = [s["name"] for s in services[:25]]
        if not top_for_usage:
            top_for_usage = [n for n, _ in sorted(svc_totals.items(), key=lambda x: -x[1])[:25]]

        usage_agg: dict[tuple[str, str, str], dict] = defaultdict(
            lambda: {"unblended": 0.0, "quantity": 0.0, "unit": "N/A"}
        )
        for service in top_for_usage:
            usage_resp = client.get_cost_and_usage(
                TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost", "UsageQuantity"],
                Filter={
                    "Dimensions": {
                        "Key": "SERVICE",
                        "Values": [service],
                    }
                },
                GroupBy=[
                    {"Type": "DIMENSION", "Key": "REGION"},
                    {"Type": "DIMENSION", "Key": "USAGE_TYPE"},
                ],
            )
            for r in usage_resp["ResultsByTime"]:
                for g in r.get("Groups", []):
                    region_raw, usage_type = g["Keys"][0], g["Keys"][1]
                    region = (
                        region_raw
                        if region_raw and region_raw not in ("NoRegion", "NoRegion$", "")
                        else "global"
                    )
                    unblended = float(g["Metrics"]["UnblendedCost"]["Amount"])
                    quantity = float(g["Metrics"]["UsageQuantity"]["Amount"])
                    unit = g["Metrics"]["UsageQuantity"]["Unit"] or "N/A"
                    key = (service, region, usage_type)
                    usage_agg[key]["unblended"] += unblended
                    usage_agg[key]["quantity"] += quantity
                    if unit != "N/A":
                        usage_agg[key]["unit"] = unit

        for (service, region, usage_type), v in usage_agg.items():
            if v["unblended"] < 0.01:
                continue
            qty = v["quantity"]
            if abs(qty) >= 1_000_000:
                qty_fmt = f"{qty:,.0f}"
            elif abs(qty) >= 100:
                qty_fmt = f"{qty:,.1f}"
            else:
                qty_fmt = f"{qty:,.4g}"
            usage_rows.append(
                {
                    "service": service,
                    "region": region,
                    "usage_type": usage_type,
                    "unblended": v["unblended"],
                    "quantity": qty,
                    "quantity_fmt": qty_fmt,
                    "unit": v["unit"],
                }
            )
        usage_rows.sort(key=lambda x: x["unblended"], reverse=True)
        usage_rows = usage_rows[:150]
        print(f"  usage rows: {len(usage_rows)}")

    # --- By cost allocation tag ---
    tag_rows: list[dict] = []
    try:
        tag_resp = client.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost", "AmortizedCost"],
            GroupBy=[{"Type": "TAG", "Key": tag_key}],
        )
        tag_agg: dict[str, dict] = defaultdict(lambda: {"unblended": 0.0, "amortized": 0.0})
        for r in tag_resp["ResultsByTime"]:
            for g in r.get("Groups", []):
                raw = g["Keys"][0] if g.get("Keys") else ""
                # CE returns "tag_key$value" or "tag_key$" for empty
                if "$" in raw:
                    value = raw.split("$", 1)[1]
                else:
                    value = raw
                if not value:
                    value = "(untagged)"
                tag_agg[value]["unblended"] += float(g["Metrics"]["UnblendedCost"]["Amount"])
                tag_agg[value]["amortized"] += float(g["Metrics"]["AmortizedCost"]["Amount"])

        for name, v in tag_agg.items():
            if v["unblended"] < 0.005 and v["amortized"] < 0.005:
                continue
            tag_rows.append(
                {
                    "name": name,
                    "unblended": v["unblended"],
                    "amortized": v["amortized"],
                }
            )
        tag_rows.sort(key=lambda x: x["unblended"], reverse=True)
        total_tag = sum(t["unblended"] for t in tag_rows) or 1.0
        for t in tag_rows:
            t["share"] = t["unblended"] / total_tag * 100
            t["desc"] = lookup_tag_description(t["name"])
        print(f"  tag '{tag_key}': {len(tag_rows)} values")
    except ClientError as e:
        print(f"  tag group-by skipped ({tag_key}): {e}")

    return daily, services, usage_rows, tag_rows, daily_labels, chart_series, total_cost


def fetch_monthly_trend(
    client, end: date, n_months: int
) -> tuple[list[str], list[dict], list[dict]]:
    """Monthly spend for the last `n_months` ending at the report period.

    Returns (trend_labels, trend_series, trend_rows).
    """
    n_months = max(1, min(int(n_months), 24))
    last_day = end - timedelta(days=1)
    trend_end_month = last_day.replace(day=1)
    trend_start = shift_month(trend_end_month, -(n_months - 1))
    # Exclusive end: first day of month after last_day's month, or end if later
    trend_end = shift_month(trend_end_month, 1)
    if trend_end < end:
        trend_end = end

    print(f"Trend window: {trend_start} → {last_day} ({n_months} months)")

    resp = client.get_cost_and_usage(
        TimePeriod={"Start": trend_start.isoformat(), "End": trend_end.isoformat()},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    labels: list[str] = []
    by_month: dict[str, dict[str, float]] = {}
    totals: dict[str, float] = defaultdict(float)
    month_totals: list[float] = []

    for r in resp.get("ResultsByTime", []):
        start_s = r["TimePeriod"]["Start"]
        month_date = datetime.strptime(start_s, "%Y-%m-%d").date()
        label = month_date.strftime("%b %Y")
        labels.append(label)
        by_month[label] = {}
        # Month total from CE Total metric (same basis as header total_cost)
        total_metrics = r.get("Total") or {}
        if "UnblendedCost" in total_metrics:
            month_sum = float(total_metrics["UnblendedCost"]["Amount"])
        else:
            month_sum = 0.0
        for g in r.get("Groups", []):
            name = g["Keys"][0]
            amount = float(g["Metrics"]["UnblendedCost"]["Amount"])
            if "UnblendedCost" not in total_metrics:
                month_sum += amount
            if amount < 0.005:
                continue
            by_month[label][name] = amount
            totals[name] += amount
        month_totals.append(month_sum)

    series = build_stacked_series(labels, by_month, totals, top_n=8)

    rows: list[dict] = []
    prev: float | None = None
    for label, total in zip(labels, month_totals):
        change = None
        if prev is not None and prev > 0:
            change = (total - prev) / prev * 100
        rows.append({"label": label, "unblended": total, "change": change})
        prev = total

    return labels, series, rows


def build_report_html(
    start: date,
    end: date,
    daily: list[dict],
    services: list[dict],
    usage_rows: list[dict],
    run_id: str,
    total_cost: float | None = None,
    tag_rows: list[dict] | None = None,
    daily_labels: list[str] | None = None,
    chart_series: list[dict] | None = None,
    trend_months: int = 3,
    trend_labels: list[str] | None = None,
    trend_series: list[dict] | None = None,
    trend_rows: list[dict] | None = None,
) -> tuple[str, float, str]:
    # total_cost is overall period spend; services are untagged-only for the breakdown table
    if total_cost is None:
        total_cost = sum(s["unblended"] for s in services)
    untagged_total = sum(s["unblended"] for s in services)
    for s in services:
        s["share"] = (s["unblended"] / untagged_total * 100) if untagged_total > 0 else 0.0

    last_day = end - timedelta(days=1)
    period_label = f"{start.strftime('%d %b %Y')} — {last_day.strftime('%d %b %Y')}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    labels = daily_labels if daily_labels is not None else [d["date"] for d in daily]
    series = chart_series or []

    html = Template(REPORT_TEMPLATE).render(
        period_label=period_label,
        generated_at=generated_at,
        total_cost=total_cost,
        services=services,
        usage_rows=usage_rows,
        tag_rows=tag_rows or [],
        start=start.isoformat(),
        end=last_day.isoformat(),
        days=(end - start).days,
        daily_labels=labels,
        chart_series=series,
        trend_months=trend_months,
        trend_labels=trend_labels or [],
        trend_series=trend_series or [],
        trend_rows=trend_rows or [],
        run_id=run_id,
    )
    return html, total_cost, period_label


# Preferred row order in the costs CSV (others appended alphabetically before untagged).
CSV_TAG_ORDER = [
    "Istio-SVT",
    "api-hub",
    "cncf_report",
    "common",
    "github-runner",
    "pioneer",
    "qstp",
]


def normalize_tag_csv_name(name: str) -> str:
    """Map CE tag label to CSV row name (untagged without parentheses)."""
    if not name or name in ("(untagged)", "untagged"):
        return "untagged"
    return name


def fetch_daily_costs_by_tag(
    client, start: date, end: date, tag_key: str = "cost-usage"
) -> tuple[list[str], dict[str, dict[str, float]]]:
    """Daily UnblendedCost by cost-usage tag.

    Returns (day_labels ISO, {tag_name: {day: amount}}).
    Tag names are normalized (untagged without parentheses).
    """
    resp = client.get_cost_and_usage(
        TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "TAG", "Key": tag_key}],
    )
    day_labels: list[str] = []
    by_tag: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in resp.get("ResultsByTime", []):
        day = r["TimePeriod"]["Start"]
        day_labels.append(day)
        for g in r.get("Groups", []):
            raw = g["Keys"][0] if g.get("Keys") else ""
            if "$" in raw:
                value = raw.split("$", 1)[1]
            else:
                value = raw
            if not value:
                value = "untagged"
            value = normalize_tag_csv_name(value)
            amount = float(g["Metrics"]["UnblendedCost"]["Amount"])
            by_tag[value][day] += amount
    # Ensure every day in [start, end) is present even if CE omitted empty days
    expected: list[str] = []
    d = start
    while d < end:
        expected.append(d.isoformat())
        d += timedelta(days=1)
    if not day_labels:
        day_labels = expected
    else:
        # keep CE order but fill missing
        seen = set(day_labels)
        for day in expected:
            if day not in seen:
                day_labels.append(day)
        day_labels = sorted(set(day_labels))
    return day_labels, {k: dict(v) for k, v in by_tag.items()}


def build_tag_costs_csv(
    day_labels: list[str],
    by_tag: dict[str, dict[str, float]],
) -> str:
    """Build CSV matching the costs.csv template (daily columns + Total)."""
    tags_present = set(by_tag.keys())
    ordered: list[str] = []
    for name in CSV_TAG_ORDER:
        if name in tags_present:
            ordered.append(name)
            tags_present.discard(name)
    # remaining (except untagged) alphabetical
    rest = sorted(t for t in tags_present if t != "untagged")
    ordered.extend(rest)
    if "untagged" in by_tag or "untagged" in tags_present:
        ordered.append("untagged")

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    header = ["Tag value (cost-usage)", *day_labels, "Total costs($)"]
    writer.writerow(header)

    day_totals = {day: 0.0 for day in day_labels}
    for tag in ordered:
        row_amounts = []
        total = 0.0
        for day in day_labels:
            amt = float(by_tag.get(tag, {}).get(day, 0.0))
            row_amounts.append(f"{amt:.2f}")
            total += amt
            day_totals[day] += amt
        writer.writerow([tag, *row_amounts, f"{total:.2f}"])

    total_row = [f"{day_totals[d]:.2f}" for d in day_labels]
    grand = sum(day_totals.values())
    writer.writerow(["TOTAL", *total_row, f"{grand:.2f}"])
    return buf.getvalue()


def build_report_pdf(
    pdf_path: Path,
    *,
    period_label: str,
    total_cost: float,
    start: date,
    end: date,
    services: list[dict],
    tag_rows: list[dict],
    usage_rows: list[dict] | None = None,
    trend_rows: list[dict] | None = None,
    trend_months: int = 3,
    daily: list[dict] | None = None,
    run_id: str = "local",
) -> bool:
    """Write a laconic print-oriented PDF from the same in-memory report data.

    No browser, no extra API calls — tables + compact summary only.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
            KeepTogether,
        )
    except ImportError:
        print(
            "Warning: reportlab not installed — skipping PDF. "
            "Install with: pip install reportlab"
        )
        return False

    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    last_day = end - timedelta(days=1)
    days = (end - start).days
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Palette — print-friendly, laconic
    ink = colors.HexColor("#0f172a")
    muted = colors.HexColor("#64748b")
    line = colors.HexColor("#e2e8f0")
    header_bg = colors.HexColor("#f1f5f9")
    accent = colors.HexColor("#0369a1")
    row_alt = colors.HexColor("#f8fafc")
    up = colors.HexColor("#b91c1c")
    down = colors.HexColor("#047857")

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=ink,
            spaceAfter=2 * mm,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSub",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=muted,
            spaceAfter=4 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Sec",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=ink,
            spaceBefore=5 * mm,
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyMuted",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=muted,
            spaceAfter=2 * mm,
            leading=11,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Cell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=ink,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellMuted",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            textColor=muted,
            leading=9,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Num",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=ink,
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Footer",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            textColor=muted,
            alignment=TA_LEFT,
        )
    )

    def money(v: float) -> str:
        return f"${v:,.2f}"

    def pct(v: float | None) -> Paragraph:
        if v is None:
            return Paragraph("—", styles["Num"])
        if v > 0:
            return Paragraph(f'<font color="#b91c1c">+{v:.1f}%</font>', styles["Num"])
        if v < 0:
            return Paragraph(f'<font color="#047857">{v:.1f}%</font>', styles["Num"])
        return Paragraph("0.0%", styles["Num"])

    def table_style(ncols: int) -> TableStyle:
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                ("TEXTCOLOR", (0, 0), (-1, 0), muted),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("TEXTCOLOR", (0, 1), (-1, -1), ink),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, line),
                ("LINEBELOW", (0, 1), (-1, -2), 0.3, line),
                ("LINEBELOW", (0, -1), (-1, -1), 0.6, line),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, row_alt]),
            ]
        )

    story: list = []

    # --- Header ---
    story.append(Paragraph("AWS Cost Report", styles["CoverTitle"]))
    story.append(
        Paragraph(
            f"{period_label}  ·  generated {generated_at}  ·  run #{run_id}",
            styles["CoverSub"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=line, spaceAfter=3 * mm))

    # --- KPI strip ---
    avg_daily = (total_cost / days) if days else 0.0
    kpi_data = [
        [
            Paragraph("<b>Total</b>", styles["CellMuted"]),
            Paragraph("<b>Days</b>", styles["CellMuted"]),
            Paragraph("<b>Avg / day</b>", styles["CellMuted"]),
            Paragraph("<b>Untagged svcs</b>", styles["CellMuted"]),
            Paragraph("<b>Tag values</b>", styles["CellMuted"]),
        ],
        [
            Paragraph(f"<b>{money(total_cost)}</b>", styles["Cell"]),
            Paragraph(str(days), styles["Cell"]),
            Paragraph(money(avg_daily), styles["Cell"]),
            Paragraph(str(len(services)), styles["Cell"]),
            Paragraph(str(len(tag_rows)), styles["Cell"]),
        ],
    ]
    kpi = Table(kpi_data, colWidths=[35 * mm, 25 * mm, 30 * mm, 35 * mm, 30 * mm])
    kpi.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), header_bg),
                ("BOX", (0, 0), (-1, -1), 0.5, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, line),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(kpi)

    # --- Daily totals (compact, no chart) ---
    # PDF has no horizontal scroll — use a compact multi-column Date|Cost layout
    # with full yyyy-mm-dd labels so a full month stays readable on one page.
    if daily:
        story.append(Paragraph("Daily totals", styles["Sec"]))
        n = len(daily)
        # 3 side-by-side Date|Cost pairs
        cols = 3
        col_w = [28 * mm, 22 * mm] * cols
        # split days into `cols` vertical strips
        per_col = (n + cols - 1) // cols
        strips: list[list[dict]] = [
            daily[i * per_col : (i + 1) * per_col] for i in range(cols)
        ]
        max_rows = max(len(s) for s in strips)
        header = []
        for _ in range(cols):
            header.extend(
                [
                    Paragraph("Date", styles["CellMuted"]),
                    Paragraph("Cost", styles["CellMuted"]),
                ]
            )
        rows = [header]
        for r in range(max_rows):
            row = []
            for s in strips:
                if r < len(s):
                    row.append(Paragraph(s[r]["date"], styles["Cell"]))
                    row.append(Paragraph(money(s[r]["cost"]), styles["Num"]))
                else:
                    row.append(Paragraph("", styles["Cell"]))
                    row.append(Paragraph("", styles["Cell"]))
            rows.append(row)
        t = Table(rows, colWidths=col_w)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                    ("TEXTCOLOR", (0, 0), (-1, 0), muted),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("TEXTCOLOR", (0, 1), (-1, -1), ink),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                    ("ALIGN", (5, 0), (5, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, line),
                    ("LINEBELOW", (0, 1), (-1, -2), 0.25, line),
                    ("BOX", (0, 0), (-1, -1), 0.5, line),
                    ("LINEBEFORE", (2, 0), (2, -1), 0.4, line),
                    ("LINEBEFORE", (4, 0), (4, -1), 0.4, line),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, row_alt]),
                ]
            )
        )
        story.append(t)

    # --- Trend ---
    if trend_rows:
        story.append(
            Paragraph(f"Monthly trend (last {trend_months} months)", styles["Sec"])
        )
        rows = [[
            Paragraph("Month", styles["CellMuted"]),
            Paragraph("Unblended", styles["CellMuted"]),
            Paragraph("Change", styles["CellMuted"]),
        ]]
        for t in trend_rows:
            rows.append(
                [
                    Paragraph(t["label"], styles["Cell"]),
                    Paragraph(money(t["unblended"]), styles["Num"]),
                    pct(t.get("change")),
                ]
            )
        t = Table(rows, colWidths=[50 * mm, 40 * mm, 30 * mm])
        t.setStyle(table_style(3))
        story.append(t)

    # --- By tag ---
    story.append(Paragraph("By tag: cost-usage", styles["Sec"]))
    story.append(
        Paragraph(
            "Costs grouped by the cost allocation tag cost-usage. "
            "Untagged spend appears as (untagged).",
            styles["BodyMuted"],
        )
    )
    if tag_rows:
        rows = [[
            Paragraph("Tag value", styles["CellMuted"]),
            Paragraph("Unblended", styles["CellMuted"]),
            Paragraph("Amortized", styles["CellMuted"]),
            Paragraph("Share", styles["CellMuted"]),
            Paragraph("Description", styles["CellMuted"]),
        ]]
        for t in tag_rows:
            desc = t.get("desc") or {}
            summary = desc.get("summary") if isinstance(desc, dict) else ""
            owner = desc.get("owner") if isinstance(desc, dict) else None
            desc_bits = []
            if summary:
                desc_bits.append(summary)
            if owner:
                desc_bits.append(f"Owner: {owner}")
            desc_text = " ".join(desc_bits) if desc_bits else "—"
            rows.append(
                [
                    Paragraph(str(t["name"]), styles["Cell"]),
                    Paragraph(money(t["unblended"]), styles["Num"]),
                    Paragraph(money(t["amortized"]), styles["Num"]),
                    Paragraph(f"{t.get('share', 0):.1f}%", styles["Num"]),
                    Paragraph(desc_text, styles["CellMuted"]),
                ]
            )
        t = Table(rows, colWidths=[28 * mm, 24 * mm, 24 * mm, 16 * mm, 78 * mm])
        t.setStyle(table_style(5))
        story.append(t)
    else:
        story.append(
            Paragraph("No data for tag cost-usage in this period.", styles["BodyMuted"])
        )

    # --- Untagged services ---
    story.append(Paragraph("By service (untagged)", styles["Sec"]))
    story.append(
        Paragraph(
            "Breakdown of the (untagged) row — spend on resources without the cost-usage tag.",
            styles["BodyMuted"],
        )
    )
    if services:
        rows = [[
            Paragraph("Service", styles["CellMuted"]),
            Paragraph("Unblended", styles["CellMuted"]),
            Paragraph("Amortized", styles["CellMuted"]),
            Paragraph("Share", styles["CellMuted"]),
        ]]
        for s in services:
            rows.append(
                [
                    Paragraph(str(s["name"]), styles["Cell"]),
                    Paragraph(money(s["unblended"]), styles["Num"]),
                    Paragraph(money(s["amortized"]), styles["Num"]),
                    Paragraph(f"{s.get('share', 0):.1f}%", styles["Num"]),
                ]
            )
        t = Table(rows, colWidths=[95 * mm, 28 * mm, 28 * mm, 22 * mm])
        t.setStyle(table_style(4))
        story.append(t)
    else:
        story.append(
            Paragraph("No untagged spend in this period.", styles["BodyMuted"])
        )

    # --- Usage (optional) ---
    if usage_rows:
        story.append(Paragraph("Usage by type", styles["Sec"]))
        story.append(
            Paragraph(
                f"Top {len(usage_rows)} usage types by cost (rows under $0.01 omitted).",
                styles["BodyMuted"],
            )
        )
        rows = [[
            Paragraph("Service", styles["CellMuted"]),
            Paragraph("Region", styles["CellMuted"]),
            Paragraph("Usage type", styles["CellMuted"]),
            Paragraph("Unblended", styles["CellMuted"]),
            Paragraph("Qty", styles["CellMuted"]),
            Paragraph("Unit", styles["CellMuted"]),
        ]]
        for u in usage_rows[:40]:
            rows.append(
                [
                    Paragraph(str(u["service"])[:40], styles["Cell"]),
                    Paragraph(str(u["region"]), styles["Cell"]),
                    Paragraph(str(u["usage_type"])[:36], styles["Cell"]),
                    Paragraph(money(u["unblended"]), styles["Num"]),
                    Paragraph(str(u.get("quantity_fmt", "")), styles["Num"]),
                    Paragraph(str(u.get("unit", "")), styles["Cell"]),
                ]
            )
        t = Table(rows, colWidths=[42 * mm, 22 * mm, 42 * mm, 22 * mm, 22 * mm, 18 * mm])
        t.setStyle(table_style(6))
        story.append(t)

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=line, spaceAfter=2 * mm))
    story.append(
        Paragraph(
            f"Data from AWS Cost Explorer · UnblendedCost / AmortizedCost · "
            f"{start.isoformat()} → {last_day.isoformat()} · run #{run_id}",
            styles["Footer"],
        )
    )

    try:
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title=f"AWS Cost Report — {period_label}",
            author="AWS Cost Report Generator",
        )
        doc.build(story)
        print(f"  PDF written → {pdf_path}")
        return True
    except Exception as e:
        print(f"Warning: PDF generation failed: {e}")
        return False


def html_to_pdf(html: str, pdf_path: Path) -> bool:
    """Deprecated browser PDF path — kept for compatibility; prefer build_report_pdf."""
    print(
        "Warning: html_to_pdf (Chromium) is deprecated; use build_report_pdf instead."
    )
    return False


def s3_key(prefix: str, *parts: str) -> str:
    return "/".join(p.strip("/") for p in (prefix, *parts) if p)


def list_existing_reports(s3, bucket: str, prefix: str) -> list[dict]:
    """Scan S3 for report folders that contain meta.json."""
    reports: list[dict] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix.rstrip('/')}/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith("/meta.json"):
                continue
            try:
                body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
                meta = json.loads(body)
                folder = key[len(prefix.rstrip("/")) + 1 :].rsplit("/", 1)[0]
                meta["path"] = f"{folder}/index.html"
                reports.append(meta)
            except (ClientError, json.JSONDecodeError, KeyError) as e:
                print(f"Warning: skip meta {key}: {e}")
    reports.sort(key=lambda m: m.get("generated_at", ""), reverse=True)
    return reports


def upload_file(s3, bucket: str, key: str, body: str | bytes, content_type: str) -> None:
    extra = {
        "ContentType": content_type,
        "CacheControl": "no-cache" if key.endswith("index.html") else "max-age=3600",
    }
    # Private by default — do NOT set ACL public-read
    s3.put_object(Bucket=bucket, Key=key, Body=body, **extra)
    print(f"  uploaded s3://{bucket}/{key}")



def write_job_summary(
    report_s3: str,
    index_s3: str,
    pdf_s3: str | None = None,
    csv_s3: str | None = None,
) -> None:
    """Write Job Summary with S3 paths only (no cost figures)."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    lines = [
        "## AWS Cost Report",
        "",
        f"- Report (HTML): `{report_s3}`",
    ]
    if pdf_s3:
        lines.append(f"- Report (PDF): `{pdf_s3}`")
    if csv_s3:
        lines.append(f"- Costs by tag (CSV): `{csv_s3}`")
    lines.extend([f"- Index: `{index_s3}`", ""])
    body = "\n".join(lines) + "\n"
    print("\n" + body)

    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(body)
        print(f"Job Summary updated → {summary_path}")
    else:
        print("(GITHUB_STEP_SUMMARY not set — summary only printed above)")



def main() -> None:
    args = parse_args()
    start, end = resolve_period(
        args.start_date, args.end_date, previous_month=args.previous_month
    )
    last_day = end - timedelta(days=1)
    trend_months = max(1, int(args.trend_months or 3))

    print(f"Period: {start} → {last_day}")

    ce = boto3.client("ce", region_name="us-east-1")
    (
        daily,
        services,
        usage_rows,
        tag_rows,
        daily_labels,
        chart_series,
        total_cost,
    ) = fetch_costs(
        ce,
        start,
        end,
        tag_key="cost-usage",
        include_usage=args.include_usage,
    )
    trend_labels, trend_series, trend_rows = fetch_monthly_trend(ce, end, trend_months)

    report_html, total_cost, period_label = build_report_html(
        start,
        end,
        daily,
        services,
        usage_rows,
        args.run_id,
        total_cost=total_cost,
        tag_rows=tag_rows,
        daily_labels=daily_labels,
        chart_series=chart_series,
        trend_months=trend_months,
        trend_labels=trend_labels,
        trend_series=trend_series,
        trend_rows=trend_rows,
    )
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Daily costs by tag → CSV (template-compatible)
    try:
        csv_days, csv_by_tag = fetch_daily_costs_by_tag(ce, start, end, tag_key="cost-usage")
        costs_csv = build_tag_costs_csv(csv_days, csv_by_tag)
        print(f"  costs CSV: {len(csv_by_tag)} tags × {len(csv_days)} days")
    except ClientError as e:
        print(f"  costs CSV skipped: {e}")
        costs_csv = build_tag_costs_csv([], {})

    folder_name = f"{start.isoformat()}_{last_day.isoformat()}"
    meta = {
        "period_start": start.isoformat(),
        "period_end": last_day.isoformat(),
        "period_label": period_label,
        "total_cost": round(total_cost, 2),
        "generated_at": generated_at,
        "run_id": args.run_id,
        "services_count": len(services),
    }

    local_root = Path(args.local_dir) if args.local_dir else Path("./out")
    local_root.mkdir(parents=True, exist_ok=True)
    report_dir = local_root / folder_name
    report_dir.mkdir(parents=True, exist_ok=True)

    # Local artifacts (stable names for email action)
    (report_dir / "index.html").write_text(report_html, encoding="utf-8")
    (report_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (local_root / "report.html").write_text(report_html, encoding="utf-8")
    (local_root / "costs.csv").write_text(costs_csv, encoding="utf-8")
    (report_dir / "costs.csv").write_text(costs_csv, encoding="utf-8")

    pdf_ok = build_report_pdf(
        local_root / "report.pdf",
        period_label=period_label,
        total_cost=total_cost,
        start=start,
        end=end,
        services=services,
        tag_rows=tag_rows,
        usage_rows=usage_rows,
        trend_rows=trend_rows,
        trend_months=trend_months,
        daily=daily,
        run_id=args.run_id,
    )
    if pdf_ok:
        (report_dir / "report.pdf").write_bytes((local_root / "report.pdf").read_bytes())

    email_body = (
        "<p>AWS Cost Report is attached.</p>\n"
        f"<p>Period: {period_label}</p>\n"
        f"<p>Generated: {generated_at}</p>\n"
        "<ul>\n"
        "  <li><strong>report.html</strong> — full interactive report</li>\n"
        "  <li><strong>report.pdf</strong> — compact printable summary (same data)</li>\n"
        "  <li><strong>costs.csv</strong> — daily spend by cost-usage tag</li>\n"
        "</ul>\n"
    )
    (local_root / "email-body.html").write_text(email_body, encoding="utf-8")
    print(f"Local copy written to {report_dir}")

    s3 = boto3.client("s3")
    prefix = args.s3_prefix.rstrip("/")

    report_key = s3_key(prefix, folder_name, "index.html")
    meta_key = s3_key(prefix, folder_name, "meta.json")
    csv_key = s3_key(prefix, folder_name, "costs.csv")
    pdf_key = s3_key(prefix, folder_name, "report.pdf")

    print(f"Uploading report → s3://{args.s3_bucket}/{report_key}")
    upload_file(s3, args.s3_bucket, report_key, report_html, "text/html; charset=utf-8")
    upload_file(
        s3,
        args.s3_bucket,
        meta_key,
        json.dumps(meta, ensure_ascii=False, indent=2),
        "application/json",
    )
    upload_file(s3, args.s3_bucket, csv_key, costs_csv, "text/csv; charset=utf-8")
    pdf_s3 = None
    if pdf_ok:
        upload_file(
            s3,
            args.s3_bucket,
            pdf_key,
            (local_root / "report.pdf").read_bytes(),
            "application/pdf",
        )
        pdf_s3 = f"s3://{args.s3_bucket}/{pdf_key}"

    reports = list_existing_reports(s3, args.s3_bucket, prefix)
    if not any(
        r.get("period_start") == start.isoformat() and r.get("period_end") == last_day.isoformat()
        for r in reports
    ):
        reports.insert(0, {**meta, "path": f"{folder_name}/index.html"})
        reports.sort(key=lambda m: m.get("generated_at", ""), reverse=True)

    index_html = Template(INDEX_TEMPLATE).render(
        reports=reports,
        generated_at=generated_at,
    )
    index_key = s3_key(prefix, "index.html")
    print(f"Uploading history index → s3://{args.s3_bucket}/{index_key}")
    upload_file(s3, args.s3_bucket, index_key, index_html, "text/html; charset=utf-8")

    report_s3 = f"s3://{args.s3_bucket}/{report_key}"
    index_s3 = f"s3://{args.s3_bucket}/{index_key}"
    csv_s3 = f"s3://{args.s3_bucket}/{csv_key}"

    write_job_summary(
        report_s3=report_s3,
        index_s3=index_s3,
        pdf_s3=pdf_s3,
        csv_s3=csv_s3,
    )

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"period_label={period_label}\n")
            f.write(f"report_file={local_root / 'report.html'}\n")

    print("Done.")


if __name__ == "__main__":
    main()
