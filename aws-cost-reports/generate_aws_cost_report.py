#!/usr/bin/env python3
"""
AWS Cost Report Generator (private S3)
- Fetches data from Cost Explorer
- Generates HTML report with daily chart
- Uploads to a private S3 bucket with full history
- Writes S3 paths to GitHub Actions Job Summary
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
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
        <div class="label">Services</div>
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
      <canvas id="dailyChart" height="100"></canvas>
    </div>

    <h2 style="margin-bottom:1rem;font-size:1.1rem">By service</h2>
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
          <td>{{ t.name }}</td>
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

    <h2 style="margin:2rem 0 1rem;font-size:1.1rem">Usage by type</h2>
    <p style="color:var(--muted);font-size:0.9rem;margin-bottom:1rem">
      Each row is a single usage type (consistent unit). Expand a row (▸) to see per-resource
      breakdown when Cost Explorer resource-level data is available (opt-in; last ~14 days from today).
      Rows under $0.01 omitted; top {{ usage_rows|length }} by cost.
    </p>
    {% if resources_status %}
    <p style="background:rgba(56,189,248,0.08);border:1px solid var(--border);border-radius:8px;padding:0.75rem 1rem;color:var(--muted);font-size:0.9rem;margin-bottom:1rem">
      {{ resources_status }}
    </p>
    {% endif %}
    <table class="usage-table">
      <thead>
        <tr>
          <td colspan="7" style="padding:0;border-bottom:1px solid var(--border)">
            <div class="usage-summary usage-header">
              <span class="chev"></span>
              <span class="c-service">Service</span>
              <span class="c-region">Region</span>
              <span class="c-type">Usage type</span>
              <span class="c-cost">Unblended</span>
              <span class="c-qty">Quantity</span>
              <span class="c-unit">Unit</span>
            </div>
          </td>
        </tr>
      </thead>
      <tbody>
        {% for u in usage_rows %}
        <tr>
          <td colspan="7" style="padding:0;border-bottom:1px solid var(--border)">
            <details class="usage-details" {% if u.resources %}data-has-resources="1"{% endif %}>
              <summary class="usage-summary">
                <span class="chev">{% if u.resources %}▸{% else %}·{% endif %}</span>
                <span class="c-service">{{ u.service }}</span>
                <span class="c-region">{{ u.region }}</span>
                <span class="c-type">{{ u.usage_type }}</span>
                <span class="c-cost cost">${{ "%.2f"|format(u.unblended) }}</span>
                <span class="c-qty cost">{{ u.quantity_fmt }}</span>
                <span class="c-unit">{{ u.unit }}</span>
              </summary>
              {% if u.resources %}
              <div class="resource-panel">
                <div class="resource-note">
                  Resources ({{ u.resources|length }}){% if u.resources_note %} · {{ u.resources_note }}{% endif %}
                </div>
                <table class="resource-table">
                  <thead>
                    <tr>
                      <th>Resource ID</th>
                      <th>Unblended</th>
                      <th>Quantity</th>
                      <th>Unit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {% for r in u.resources %}
                    <tr>
                      <td class="mono">{{ r.resource_id }}</td>
                      <td class="cost">${{ "%.2f"|format(r.unblended) }}</td>
                      <td class="cost">{{ r.quantity_fmt }}</td>
                      <td>{{ r.unit }}</td>
                    </tr>
                    {% endfor %}
                  </tbody>
                </table>
              </div>
              {% endif %}
            </details>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    <style>
      details.usage-details { width: 100%; }
      .usage-summary {
        display: grid;
        grid-template-columns: 1.5rem minmax(10rem,1.6fr) 7rem minmax(8rem,1.4fr) 6rem 6rem 5rem;
        gap: 0.5rem;
        align-items: center;
        padding: 0.75rem 1rem;
      }
      details.usage-details > summary {
        list-style: none;
        cursor: default;
      }
      .usage-header {
        background: #0f172a;
        color: var(--muted);
        font-weight: 500;
        font-size: 0.85rem;
        padding: 0.75rem 1rem;
      }
      .usage-header .c-cost,
      .usage-header .c-qty { text-align: right; }
      details.usage-details[data-has-resources] > summary { cursor: pointer; }
      details.usage-details > summary::-webkit-details-marker { display: none; }
      details.usage-details[open][data-has-resources] .chev { color: var(--accent); }
      details.usage-details[open][data-has-resources] .chev::before { content: "▾"; }
      details.usage-details[data-has-resources]:not([open]) .chev::before { content: "▸"; }
      .chev { color: var(--border); font-size: 0.85rem; }
      .c-service, .c-type { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .c-region, .c-unit { color: var(--muted); font-size: 0.9rem; }
      .c-cost, .c-qty { text-align: right; font-variant-numeric: tabular-nums; }
      .resource-panel {
        padding: 0 1rem 1rem 2.5rem;
        background: rgba(15, 23, 42, 0.55);
      }
      .resource-note { font-size: 0.85rem; color: var(--muted); margin: 0.35rem 0 0.6rem; }
      .resource-table {
        width: 100%;
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
        border-collapse: collapse;
      }
      .resource-table th, .resource-table td {
        padding: 0.5rem 0.75rem;
        border-bottom: 1px solid var(--border);
      }
      .resource-table tr:last-child td { border-bottom: none; }
      .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.8rem; }
    </style>

    <footer>
      Data from AWS Cost Explorer · UnblendedCost / AmortizedCost ·
      run #{{ run_id }}
    </footer>
  </div>

  <script>
    const dailyLabels = {{ daily_labels|tojson }};
    const dailyCosts  = {{ daily_costs|tojson }};
    new Chart(document.getElementById('dailyChart'), {
      type: 'bar',
      data: {
        labels: dailyLabels,
        datasets: [{
          label: 'Cost ($)',
          data: dailyCosts,
          backgroundColor: 'rgba(56, 189, 248, 0.6)',
          borderColor: 'rgb(56, 189, 248)',
          borderWidth: 1,
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { color: '#94a3b8' },
            grid: { color: '#334155' }
          },
          x: {
            ticks: { color: '#94a3b8', maxRotation: 45 },
            grid: { display: false }
          }
        }
      }
    });
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
    p.add_argument("--s3-bucket", required=True)
    p.add_argument("--s3-prefix", default="aws-cost-reports")
    p.add_argument("--run-id", default="local")
    p.add_argument("--local-dir", default="", help="Also write files locally (optional)")
    return p.parse_args()


def resolve_period(start_str: str, end_str: str) -> tuple[date, date]:
    """Return [start, end) for Cost Explorer (End is exclusive in the API).

    User-provided end_date is treated as **inclusive** (the last day of the report).
    """
    today = date.today()
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


def fetch_costs(
    client, start: date, end: date, tag_key: str = "cost-usage"
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Return (daily, services, usage_rows, tag_rows).

    usage_rows are grouped by SERVICE + USAGE_TYPE so quantity has a consistent unit.
    tag_rows are grouped by cost allocation tag `tag_key`.
    """
    daily_resp = client.get_cost_and_usage(
        TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        Granularity="DAILY",
        Metrics=["UnblendedCost", "AmortizedCost"],
    )
    daily: list[dict] = []
    for r in daily_resp["ResultsByTime"]:
        amount = float(r["Total"].get("UnblendedCost", {}).get("Amount", 0) or 0)
        daily.append({"date": r["TimePeriod"]["Start"], "cost": amount})

    service_resp = client.get_cost_and_usage(
        TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost", "AmortizedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    svc_agg: dict[str, dict] = defaultdict(lambda: {"unblended": 0.0, "amortized": 0.0})
    for r in service_resp["ResultsByTime"]:
        for g in r.get("Groups", []):
            name = g["Keys"][0]
            svc_agg[name]["unblended"] += float(g["Metrics"]["UnblendedCost"]["Amount"])
            svc_agg[name]["amortized"] += float(g["Metrics"]["AmortizedCost"]["Amount"])

    services: list[dict] = []
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

    # Cost Explorer allows at most 2 GroupBy dimensions. To get
    # Service + Region + Usage type we filter by service and group by REGION + USAGE_TYPE.
    usage_agg: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {"unblended": 0.0, "quantity": 0.0, "unit": "N/A"}
    )
    # Limit API calls to the most expensive services
    for service in [s["name"] for s in services[:25]]:
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
                region = region_raw if region_raw and region_raw not in ("NoRegion", "NoRegion$", "") else "global"
                unblended = float(g["Metrics"]["UnblendedCost"]["Amount"])
                quantity = float(g["Metrics"]["UsageQuantity"]["Amount"])
                unit = g["Metrics"]["UsageQuantity"]["Unit"] or "N/A"
                key = (service, region, usage_type)
                usage_agg[key]["unblended"] += unblended
                usage_agg[key]["quantity"] += quantity
                if unit != "N/A":
                    usage_agg[key]["unit"] = unit

    usage_rows: list[dict] = []
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
                "resources": [],
                "resources_note": "",
            }
        )
    usage_rows.sort(key=lambda x: x["unblended"], reverse=True)
    usage_rows = usage_rows[:150]

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
        print(f"  tag '{tag_key}': {len(tag_rows)} values")
    except ClientError as e:
        print(f"  tag group-by skipped ({tag_key}): {e}")

    return daily, services, usage_rows, tag_rows

def format_qty(qty: float) -> str:
    if abs(qty) >= 1_000_000:
        return f"{qty:,.0f}"
    if abs(qty) >= 100:
        return f"{qty:,.1f}"
    return f"{qty:,.4g}"


def fetch_resources_for_services(
    client,
    start: date,
    end: date,
    services: list[str],
) -> tuple[dict[str, list[dict]], str]:
    """Resource-level breakdown via GetCostAndUsageWithResources.

    Requires Cost Explorer resource-level data (opt-in in CE preferences).
    Resource-level daily data is only retained for approximately the last 14 days
    relative to *today*, not relative to the report period.

    Returns (by_service, status_message).
    """
    today = date.today()
    # Rolling window from today (not from report end)
    window_end = today + timedelta(days=1)
    window_start = today - timedelta(days=13)  # ~14 calendar days inclusive

    res_start = max(start, window_start)
    res_end = min(end, window_end)

    if res_end <= res_start:
        last_day = end - timedelta(days=1)
        msg = (
            f"No resource-level detail: Cost Explorer only keeps resource data for the "
            f"last ~14 days (about {window_start.isoformat()} → {today.isoformat()}). "
            f"Requested period {start.isoformat()} → {last_day.isoformat()} is outside that window. "
            f"Re-run for a recent period, or enable/use CUR for historical resource costs."
        )
        print(f"  {msg}")
        return {}, msg

    note = (
        f"resource data window {res_start.isoformat()} → "
        f"{(res_end - timedelta(days=1)).isoformat()}"
    )
    by_service: dict[str, list[dict]] = {}
    errors: list[str] = []

    for service in services:
        try:
            resp = client.get_cost_and_usage_with_resources(
                TimePeriod={"Start": res_start.isoformat(), "End": res_end.isoformat()},
                Granularity="DAILY",
                Metrics=["UnblendedCost", "UsageQuantity"],
                Filter={
                    "Dimensions": {
                        "Key": "SERVICE",
                        "Values": [service],
                    }
                },
                GroupBy=[
                    {"Type": "DIMENSION", "Key": "RESOURCE_ID"},
                    {"Type": "DIMENSION", "Key": "USAGE_TYPE"},
                ],
            )
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            msg = f"{service}: {code}"
            print(f"  resource-level skip for {service}: {code} {e}")
            errors.append(msg)
            continue
        except Exception as e:
            print(f"  resource-level skip for {service}: {e}")
            errors.append(f"{service}: {e}")
            continue

        agg: dict[tuple[str, str], dict] = defaultdict(
            lambda: {"unblended": 0.0, "quantity": 0.0, "unit": "N/A"}
        )
        for r in resp.get("ResultsByTime", []):
            for g in r.get("Groups", []):
                keys = g.get("Keys") or []
                if len(keys) < 2:
                    continue
                resource_id, usage_type = keys[0], keys[1]
                if not resource_id or resource_id in ("NoResourceId", "NoResourceId$"):
                    continue
                unblended = float(g["Metrics"]["UnblendedCost"]["Amount"])
                quantity = float(g["Metrics"]["UsageQuantity"]["Amount"])
                unit = g["Metrics"]["UsageQuantity"].get("Unit") or "N/A"
                key = (resource_id, usage_type)
                agg[key]["unblended"] += unblended
                agg[key]["quantity"] += quantity
                if unit != "N/A":
                    agg[key]["unit"] = unit

        rows: list[dict] = []
        for (resource_id, usage_type), v in agg.items():
            if v["unblended"] < 0.01:
                continue
            rows.append(
                {
                    "resource_id": resource_id,
                    "usage_type": usage_type,
                    "unblended": v["unblended"],
                    "quantity": v["quantity"],
                    "quantity_fmt": format_qty(v["quantity"]),
                    "unit": v["unit"],
                    "_note": note,
                }
            )
        rows.sort(key=lambda x: x["unblended"], reverse=True)
        if rows:
            by_service[service] = rows[:40]
            print(f"  resources for {service}: {len(rows)} (showing up to 40)")

    if by_service:
        status = f"Resource-level detail loaded for {len(by_service)} service(s) ({note})."
    elif errors:
        status = (
            "Resource-level detail unavailable. "
            "Enable resource-level data in Cost Explorer preferences, ensure ce:GetCostAndUsageWithResources "
            f"permission, and use a period within the last ~14 days. Errors: {'; '.join(errors[:5])}"
        )
    else:
        status = (
            f"No per-resource rows returned ({note}). "
            "Resource-level data may not be enabled for these services in Cost Explorer preferences."
        )
    print(f"  {status}")
    return by_service, status


def attach_resources_to_usage_rows(
    usage_rows: list[dict],
    resources_by_service: dict[str, list[dict]],
) -> None:
    """Attach matching resources under each usage row (same service + usage_type)."""
    for u in usage_rows:
        all_for_svc = resources_by_service.get(u["service"]) or []
        matched = [r for r in all_for_svc if r["usage_type"] == u["usage_type"]]
        # Fallback: if no exact usage_type match, show top resources for the service
        if not matched and all_for_svc:
            matched = all_for_svc[:15]
            note = (all_for_svc[0].get("_note") or "") + " · filtered by service only"
        else:
            note = (matched[0].get("_note") if matched else "") or ""
        u["resources"] = [
            {
                "resource_id": r["resource_id"],
                "unblended": r["unblended"],
                "quantity_fmt": r["quantity_fmt"],
                "unit": r["unit"],
            }
            for r in matched[:25]
        ]
        u["resources_note"] = note if u["resources"] else ""





def build_report_html(
    start: date,
    end: date,
    daily: list[dict],
    services: list[dict],
    usage_rows: list[dict],
    run_id: str,
    resources_status: str = "",
    tag_rows: list[dict] | None = None,
) -> tuple[str, float, str]:
    total = sum(s["unblended"] for s in services)
    for s in services:
        s["share"] = (s["unblended"] / total * 100) if total > 0 else 0.0

    last_day = end - timedelta(days=1)
    period_label = f"{start.strftime('%d %b %Y')} — {last_day.strftime('%d %b %Y')}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = Template(REPORT_TEMPLATE).render(
        period_label=period_label,
        generated_at=generated_at,
        total_cost=total,
        services=services,
        usage_rows=usage_rows,
        tag_rows=tag_rows or [],
        resources_status=resources_status,
        start=start.isoformat(),
        end=last_day.isoformat(),
        days=(end - start).days,
        daily_labels=[d["date"] for d in daily],
        daily_costs=[round(d["cost"], 2) for d in daily],
        run_id=run_id,
    )
    return html, total, period_label


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
) -> None:
    """Write Job Summary with S3 paths only (no cost figures)."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    lines = [
        "## AWS Cost Report",
        "",
        f"- Report: `{report_s3}`",
        f"- Index: `{index_s3}`",
        "",
    ]
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
    start, end = resolve_period(args.start_date, args.end_date)
    last_day = end - timedelta(days=1)

    print(f"Period: {start} → {last_day}")

    ce = boto3.client("ce", region_name="us-east-1")
    daily, services, usage_rows, tag_rows = fetch_costs(ce, start, end, tag_key="cost-usage")

    # Resource-level detail (opt-in in Cost Explorer; ~14-day rolling window from today)
    top_services = [s["name"] for s in services[:15]]
    print(f"Fetching resource-level data for {len(top_services)} services...")
    resources_by_service, resources_status = fetch_resources_for_services(
        ce, start, end, top_services
    )
    attach_resources_to_usage_rows(usage_rows, resources_by_service)

    report_html, total_cost, period_label = build_report_html(
        start,
        end,
        daily,
        services,
        usage_rows,
        args.run_id,
        resources_status,
        tag_rows=tag_rows,
    )
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

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

    s3 = boto3.client("s3")
    prefix = args.s3_prefix.rstrip("/")

    report_key = s3_key(prefix, folder_name, "index.html")
    meta_key = s3_key(prefix, folder_name, "meta.json")
    print(f"Uploading report → s3://{args.s3_bucket}/{report_key}")
    upload_file(s3, args.s3_bucket, report_key, report_html, "text/html; charset=utf-8")
    upload_file(
        s3,
        args.s3_bucket,
        meta_key,
        json.dumps(meta, ensure_ascii=False, indent=2),
        "application/json",
    )

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

    if args.local_dir:
        local = Path(args.local_dir)
        report_dir = local / folder_name
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "index.html").write_text(report_html, encoding="utf-8")
        (report_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Local copy written to {report_dir}")

    report_s3 = f"s3://{args.s3_bucket}/{report_key}"
    index_s3 = f"s3://{args.s3_bucket}/{index_key}"

    write_job_summary(
        report_s3=report_s3,
        index_s3=index_s3,
    )

    print(f"\nDone. Total cost: ${total_cost:.2f}")


if __name__ == "__main__":
    main()
