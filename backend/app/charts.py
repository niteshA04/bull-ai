"""Server-side chart rendering to fixed-size inline SVG data URIs.

Hand-rolled SVG rather than matplotlib/numpy — keeps the backend to pure-Python wheels
(no C-toolchain build step required). Chart regions are rendered once and embedded as
images, and never contribute to PDF overflow — only text/tables can grow (PLAN.md §4).
"""
from __future__ import annotations

import base64

ACCENT = "#2596be"
ACCENT_2 = "#e85d2f"
GRID = "#e6e6e6"
TEXT = "#666666"


def _svg_to_data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _scale(values: list[float], height: float, pad_top: float, pad_bottom: float):
    lo, hi = min(values), max(values)
    if hi == lo:
        hi = lo + 1
    span = hi - lo
    usable = height - pad_top - pad_bottom

    def y(v):
        return pad_top + usable - (v - lo) / span * usable

    return y


def line_chart(points: list[dict], width: int = 640, height: int = 220) -> str:
    pad_l, pad_r, pad_t, pad_b = 30, 12, 14, 26
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    n = max(len(xs) - 1, 1)
    step = (width - pad_l - pad_r) / n
    y_scale = _scale(ys, height, pad_t, pad_b)

    def pt(i, v):
        return pad_l + i * step, y_scale(v)

    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pt(i, v) for i, v in enumerate(ys)))

    has_y2 = any(p.get("y2") is not None for p in points)
    path2 = ""
    if has_y2:
        y2_scale = _scale([p.get("y2") or 0 for p in points], height, pad_t, pad_b)
        pts2 = [(pad_l + i * step, y2_scale(p.get("y2") or 0)) for i, p in enumerate(points)]
        path2 = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts2))

    label_every = max(1, len(xs) // 8)
    labels = "".join(
        f'<text x="{pad_l + i * step:.1f}" y="{height - 6}" font-size="9" fill="{TEXT}" text-anchor="middle">{xs[i]}</text>'
        for i in range(0, len(xs), label_every)
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="none"/>
  {"".join(f'<line x1="{pad_l}" y1="{pad_t + i * (height - pad_t - pad_b) / 4:.1f}" x2="{width - pad_r}" y2="{pad_t + i * (height - pad_t - pad_b) / 4:.1f}" stroke="{GRID}" stroke-width="1"/>' for i in range(5))}
  <path d="{path}" fill="none" stroke="{ACCENT}" stroke-width="2"/>
  {f'<path d="{path2}" fill="none" stroke="{ACCENT_2}" stroke-width="1.5" stroke-dasharray="4,3"/>' if path2 else ''}
  {labels}
</svg>"""
    return _svg_to_data_uri(svg)


def bar_line_combo(points: list[dict], width: int = 300, height: int = 200) -> str:
    pad_l, pad_r, pad_t, pad_b = 26, 26, 12, 30
    xs = [p["x"] for p in points]
    bars = [p["y"] for p in points]
    line = [p.get("y2") for p in points]
    n = len(xs)
    slot = (width - pad_l - pad_r) / max(n, 1)
    bar_w = slot * 0.55
    y_scale = _scale(bars + [0], height, pad_t, pad_b)
    zero_y = y_scale(0)

    bars_svg = "".join(
        f'<rect x="{pad_l + i * slot + (slot - bar_w) / 2:.1f}" y="{min(y_scale(v), zero_y):.1f}" '
        f'width="{bar_w:.1f}" height="{abs(zero_y - y_scale(v)):.1f}" fill="{ACCENT}" rx="1.5"/>'
        for i, v in enumerate(bars)
    )

    line_svg = ""
    if any(v is not None for v in line):
        vals = [v if v is not None else 0 for v in line]
        y2_scale = _scale(vals, height, pad_t, pad_b)
        pts = [(pad_l + i * slot + slot / 2, y2_scale(v)) for i, v in enumerate(vals)]
        path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="{ACCENT_2}"/>' for x, y in pts)
        line_svg = f'<path d="{path}" fill="none" stroke="{ACCENT_2}" stroke-width="1.6"/>{dots}'

    label_every = max(1, n // 5)
    labels = "".join(
        f'<text x="{pad_l + i * slot + slot / 2:.1f}" y="{height - 8}" font-size="8" fill="{TEXT}" text-anchor="middle">{xs[i]}</text>'
        for i in range(0, n, label_every)
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  {bars_svg}
  {line_svg}
  {labels}
</svg>"""
    return _svg_to_data_uri(svg)


def placeholder_chart(width: int = 300, height: int = 200) -> str:
    """Blank axes with a centered 'Data not available' label, for a chart the source
    document had no data for — keeps the grid slot instead of collapsing it."""
    pad_l, pad_r, pad_t, pad_b = 26, 26, 12, 30
    gridlines = "".join(
        f'<line x1="{pad_l}" y1="{pad_t + i * (height - pad_t - pad_b) / 4:.1f}" '
        f'x2="{width - pad_r}" y2="{pad_t + i * (height - pad_t - pad_b) / 4:.1f}" '
        f'stroke="{GRID}" stroke-width="1"/>'
        for i in range(5)
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  {gridlines}
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height - pad_b}" stroke="{GRID}" stroke-width="1"/>
  <line x1="{pad_l}" y1="{height - pad_b}" x2="{width - pad_r}" y2="{height - pad_b}" stroke="{GRID}" stroke-width="1"/>
  <text x="{width / 2:.1f}" y="{height / 2:.1f}" font-size="11" fill="{TEXT}" text-anchor="middle">Data not available</text>
</svg>"""
    return _svg_to_data_uri(svg)


GRID_CHART_IDS = ("revenue_chart", "gov_chart", "ebitda_chart", "pat_chart")
WIDE_CHART_IDS = ("recommendation_chart",)


def render_all_charts(charts: dict) -> dict:
    out = {}
    for chart_id, points in (charts or {}).items():
        if not points:
            continue
        try:
            if chart_id in ("price_chart", "recommendation_chart"):
                out[chart_id] = line_chart(points)
            else:
                out[chart_id] = bar_line_combo(points)
        except Exception:
            continue
    for chart_id in GRID_CHART_IDS:
        out.setdefault(chart_id, placeholder_chart())
    for chart_id in WIDE_CHART_IDS:
        out.setdefault(chart_id, placeholder_chart(width=640, height=220))
    return out
