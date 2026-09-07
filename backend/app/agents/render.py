"""Agent 9 — Render (deterministic, Jinja2 + WeasyPrint).

Second half of the Fill Agent: takes the merged context from Assembly and a static HTML
template, fills it (loops for variable-row tables, conditionals for missing sections),
and rasterizes to a final PDF.
"""
from __future__ import annotations

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from .. import config
from ..charts import render_all_charts

LOGO_PATH = config.BASE_DIR.parent / "frontend" / "assets" / "geojit_logo.png"


def _logo_data_uri() -> str:
    if not LOGO_PATH.exists():
        return ""
    data = base64.standard_b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"

TABLE_LABELS = {
    "market_cap_cr": "Market Cap (₹ Cr)", "week52_high_low": "52W High/Low", "enterprise_value_cr": "Enterprise Value (₹ Cr)",
    "outstanding_shares_cr": "Shares O/S (Cr)", "free_float_pct": "Free Float (%)", "dividend_yield_pct": "Dividend Yield (%)",
    "avg_volume_6m_cr": "Avg Volume 6M", "beta": "Beta", "face_value": "Face Value",
    "promoters_pct": "Promoters", "fiis_pct": "FIIs", "mfs_institutions_pct": "MFs/Institutions",
    "public_pct": "Public", "others_pct": "Others", "total_pct": "Total", "promoter_pledge": "Promoter Pledge",
    "absolute_return_pct": "Absolute Return", "absolute_sensex_pct": "Absolute Sensex", "relative_return_pct": "Relative Return",
    "sales": "Sales", "ebitda": "EBITDA", "margin_pct": "Margin (%)", "ebit": "EBIT", "pbt": "PBT",
    "rep_pat": "Reported PAT", "adj_pat": "Adjusted PAT", "adj_eps": "Adjusted EPS",
    "growth_pct": "Growth (%)", "ebitda_margin_pct": "EBITDA Margin (%)", "pat_adjusted": "PAT (Adjusted)",
    "pat_growth_pct": "PAT Growth (%)", "eps_growth_pct": "EPS Growth (%)", "pe": "P/E", "pb": "P/B",
    "ev_ebitda": "EV/EBITDA", "roe_pct": "RoE (%)", "de": "D/E",
    "revenue": "Revenue", "margins_pct": "Margins (%)",
    "pct_change_sales": "Sales Growth (%)", "depreciation": "Depreciation", "interest": "Interest",
    "other_income": "Other Income", "pct_change_pbt": "PBT Growth (%)", "tax": "Tax", "tax_rate_pct": "Tax Rate (%)",
    "reported_pat": "Reported PAT", "pat_att_common": "PAT Attributable", "pct_change_pat": "PAT Growth (%)",
    "shares_outstanding_cr": "Shares O/S (Cr)", "pct_change_eps": "EPS Growth (%)", "dps": "DPS", "pct_change_ebitda": "EBITDA Growth (%)",
    "cash": "Cash", "accounts_receivable": "Accounts Receivable", "inventories": "Inventories",
    "other_current_assets": "Other Current Assets", "investments": "Investments", "gross_fixed_assets": "Gross Fixed Assets",
    "net_fixed_assets": "Net Fixed Assets", "cwip": "CWIP", "intangible_assets": "Intangible Assets",
    "deferred_tax_net": "Deferred Tax (Net)", "other_assets": "Other Assets", "total_assets": "Total Assets",
    "current_liabilities": "Current Liabilities", "provisions": "Provisions", "debt_funds": "Debt Funds",
    "other_liabilities": "Other Liabilities", "equity_capital": "Equity Capital", "reserves_surplus": "Reserves & Surplus",
    "shareholder_funds": "Shareholder Funds", "minority_interest": "Minority Interest", "total_liabilities": "Total Liabilities",
    "bvps": "BVPS", "net_inc_depreciation": "Net Income + Depreciation", "non_cash_adjustments": "Non-Cash Adjustments",
    "other_adjustments": "Other Adjustments", "changes_in_wc": "Changes in WC", "cf_operations": "CF from Operations",
    "capital_expenditure": "Capital Expenditure", "change_in_investments": "Change in Investments",
    "other_investment_cf": "Other Investing CF", "cf_investment": "CF from Investing", "issue_of_equity": "Issue of Equity",
    "issue_repay_debt": "Issue/Repay Debt", "dividends_paid": "Dividends Paid", "other_finance_cf": "Other Financing CF",
    "cf_finance": "CF from Financing", "change_in_cash": "Change in Cash", "closing_cash": "Closing Cash",
    "ebit_margin_pct": "EBIT Margin (%)", "net_profit_margin_pct": "Net Profit Margin (%)", "roce_pct": "RoCE (%)",
    "receivables_days": "Receivable Days", "inventory_days": "Inventory Days", "payables_days": "Payable Days",
    "current_ratio": "Current Ratio", "quick_ratio": "Quick Ratio", "gross_asset_turnover": "Gross Asset Turnover",
    "total_asset_turnover": "Total Asset Turnover", "interest_coverage_ratio": "Interest Coverage", "adj_debt_equity": "Adj. D/E",
    "ev_sales": "EV/Sales", "pbv": "P/BV",
    "old_fy_current": "Old FYc", "old_fy_next": "Old FYn", "new_fy_current": "New FYc", "new_fy_next": "New FYn",
    "change_pct_fy_current": "Chg % FYc", "change_pct_fy_next": "Chg % FYn",
}


def _label(row_key: str) -> str:
    return TABLE_LABELS.get(row_key, row_key.replace("_", " ").title())


def _arrow(direction) -> Markup:
    direction = (direction or "no_change").lower()
    glyph = {"up": "&#9650;", "down": "&#9660;"}.get(direction, "&#8212;")
    cls = {"up": "arrow-up", "down": "arrow-down"}.get(direction, "arrow-flat")
    return Markup(f'<span class="{cls}">{glyph}</span>')


def _kv_table(rows: dict, title: str = "Metric") -> Markup:
    if not rows:
        return Markup(f'<table class="data-table"><tr><th colspan="2">{title}</th></tr>'
                       f'<tr><td colspan="2" class="muted">— No data available —</td></tr></table>')
    body = "".join(f"<tr><td>{_label(k)}</td><td>{v}</td></tr>" for k, v in rows.items())
    return Markup(f'<table class="data-table"><tr><th colspan="2">{title}</th></tr>{body}</table>')


def _row_table(rows: dict, col_labels: list[str], section_breaks: dict | None = None, title: str = "Metric") -> Markup:
    ncols = len(col_labels) + 1
    if not rows:
        return Markup(f'<table class="data-table"><tr><th colspan="{ncols}">{title}</th></tr>'
                       f'<tr><td colspan="{ncols}" class="muted">— No data available —</td></tr></table>')
    header = f"<th>{title}</th>" + "".join(f"<th>{c}</th>" for c in col_labels)
    body_rows = []
    for row_key, cells in rows.items():
        if section_breaks and row_key in section_breaks:
            body_rows.append(f'<tr class="section-break"><td colspan="{ncols}">{section_breaks[row_key]}</td></tr>')
        cols = list(cells.values()) if isinstance(cells, dict) else [cells]
        tds = "".join(f"<td>{v}</td>" for v in cols)
        body_rows.append(f"<tr><td>{_label(row_key)}</td>{tds}</tr>")
    return Markup(f'<table class="data-table"><tr>{header}</tr>{"".join(body_rows)}</table>')


def render_pdf(ctx: dict, output_path: str) -> str:
    env = Environment(
        loader=FileSystemLoader(str(config.TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["kv_table"] = _kv_table
    env.globals["row_table"] = _row_table
    env.globals["arrow"] = _arrow
    env.filters["label"] = _label

    css = (config.TEMPLATES_DIR / "report.css").read_text(encoding="utf-8")
    static_page4 = Markup((config.TEMPLATES_DIR / "static_page4.html").read_text(encoding="utf-8"))

    ctx = dict(ctx)
    ctx["charts"] = render_all_charts(ctx.get("charts") or {})

    template = env.get_template("report.html")
    html = template.render(ctx=ctx, css=css, static_page4=static_page4, logo=_logo_data_uri())

    _html_to_pdf(html, output_path)
    return output_path


def _html_to_pdf(html: str, output_path: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path=output_path, format="A4", print_background=True,
                 margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"})
        browser.close()
