"""Agent 5 — Metrics (deterministic, no LLM).

Recomputes growth/margin figures in code from the raw values the Financial Table agent
extracted, rather than trusting any percentage the LLM may have echoed from prose.
"""
from __future__ import annotations


def _pct_growth(current, prior):
    if current is None or prior in (None, 0):
        return None
    try:
        return round((current - prior) / abs(prior) * 100, 2)
    except (TypeError, ZeroDivisionError):
        return None


def _margin(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return round(numerator / denominator * 100, 2)
    except (TypeError, ZeroDivisionError):
        return None


def compute_metrics(tables: dict) -> dict:
    tables = dict(tables or {})

    qf = dict(tables.get("quarterly_financials_table") or {})
    sales = dict(qf.get("sales") or {})
    ebitda = dict(qf.get("ebitda") or {})
    margin = dict(qf.get("margin_pct") or {})

    if sales:
        sales["yoy_growth_pct"] = sales.get("yoy_growth_pct") or _pct_growth(sales.get("q_current"), sales.get("q_yoy"))
        sales["qoq_growth_pct"] = sales.get("qoq_growth_pct") or _pct_growth(sales.get("q_current"), sales.get("q_qoq"))
        qf["sales"] = sales

    if ebitda:
        ebitda["yoy_growth_pct"] = ebitda.get("yoy_growth_pct") or _pct_growth(ebitda.get("q_current"), ebitda.get("q_yoy"))
        ebitda["qoq_growth_pct"] = ebitda.get("qoq_growth_pct") or _pct_growth(ebitda.get("q_current"), ebitda.get("q_qoq"))
        qf["ebitda"] = ebitda

    if sales.get("q_current") and ebitda.get("q_current") is not None:
        margin["q_current"] = margin.get("q_current") or _margin(ebitda.get("q_current"), sales.get("q_current"))
    if sales.get("q_yoy") and ebitda.get("q_yoy") is not None:
        margin["q_yoy"] = margin.get("q_yoy") or _margin(ebitda.get("q_yoy"), sales.get("q_yoy"))
    if margin:
        qf["margin_pct"] = margin
    tables["quarterly_financials_table"] = qf

    pl = dict(tables.get("profit_loss_table") or {})
    for row_name, base_row in (("pct_change_sales", "sales"), ("pct_change_ebitda", "ebitda"), ("pct_change_pbt", "pbt"), ("pct_change_pat", "adj_pat"), ("pct_change_eps", "adj_eps")):
        base = dict(pl.get(base_row) or {})
        pct_row = dict(pl.get(row_name) or {})
        cols = ["fy_minus2_actual", "fy_minus1_actual", "fy_current_actual", "fy_current_estimate", "fy_next_estimate"]
        for i in range(1, len(cols)):
            cur, prior = base.get(cols[i]), base.get(cols[i - 1])
            if cur is not None and prior is not None and pct_row.get(cols[i]) is None:
                pct_row[cols[i]] = _pct_growth(cur, prior)
        if pct_row:
            pl[row_name] = pct_row
    if pl:
        tables["profit_loss_table"] = pl

    ratios = dict(tables.get("ratios_table") or {})
    bs = dict(tables.get("balance_sheet_table") or {})
    for col in ["fy_minus2_actual", "fy_minus1_actual", "fy_current_actual", "fy_current_estimate", "fy_next_estimate"]:
        sales_v = (pl.get("sales") or {}).get(col)
        ebitda_v = (pl.get("ebitda") or {}).get(col)
        pat_v = (pl.get("adj_pat") or {}).get(col)
        equity_v = (bs.get("shareholder_funds") or {}).get(col)
        for row_name, val in (
            ("ebitda_margin_pct", _margin(ebitda_v, sales_v)),
            ("net_profit_margin_pct", _margin(pat_v, sales_v)),
            ("roe_pct", _margin(pat_v, equity_v)),
        ):
            row = dict(ratios.get(row_name) or {})
            if row.get(col) is None and val is not None:
                row[col] = val
                ratios[row_name] = row
    if ratios:
        tables["ratios_table"] = ratios

    return tables
