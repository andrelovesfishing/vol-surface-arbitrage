"""Render the README's headline figure: python docs/figures/violation_rates.py

Numbers are pinned from the README's results table (frozen window, 1-tick floor),
so the figure regenerates without the dataset. Writes a light and a dark SVG.
"""
from pathlib import Path

MID = {"BTC": 9.30, "ETH": 9.25}  # % of butterflies violating at mid
EXECUTABLE = 0.0  # on both underlyings

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
                  grid="#e1e0d9", base="#c3c2b7", mid="#2a78d6", exe="#eb6834"),
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
                 grid="#2c2c2a", base="#383835", mid="#3987e5", exe="#d95926"),
}

W, H = 720, 336
LEFT, RIGHT, TOP, BASE = 52, 20, 112, 268   # plot spans y TOP..BASE
YMAX, BAR = 10.0, 56
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def y(v):
    return BASE - v / YMAX * (BASE - TOP)


def column(x, top, fill):
    """A column with a 4px rounded data-end and a square baseline."""
    r = 4
    return (f'<path d="M{x},{BASE} V{top + r} Q{x},{top} {x + r},{top} H{x + BAR - r} '
            f'Q{x + BAR},{top} {x + BAR},{top + r} V{BASE} Z" fill="{fill}"/>')


def render(t):
    plot = W - LEFT - RIGHT
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'role="img" font-family="{FONT}">',
         "<title>Share of option butterflies that look like arbitrage: mid vs executable prices</title>",
         "<desc>At mid prices 9.30% of BTC butterflies and 9.25% of ETH butterflies look like arbitrage. "
         "At executable prices the share is zero on both.</desc>",
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         f'<text x="{LEFT}" y="34" font-size="16" font-weight="600" fill="{t["ink"]}">'
         "Apparent arbitrage vanishes at tradeable prices</text>",
         f'<text x="{LEFT}" y="56" font-size="12.5" fill="{t["ink2"]}">'
         "Share of 4.7 million option butterflies that look like arbitrage</text>"]

    # Legend: colored swatch beside ink text, never colored text.
    lx = LEFT
    for label, color in (("mid price", t["mid"]), ("executable price (buy at ask, sell at bid)", t["exe"])):
        s.append(f'<rect x="{lx}" y="72" width="10" height="10" rx="2" fill="{color}"/>')
        s.append(f'<text x="{lx + 16}" y="81" font-size="12" fill="{t["ink2"]}">{label}</text>')
        lx += 16 + len(label) * 6.6 + 20

    for v in (0, 5, 10):
        if v:
            s.append(f'<line x1="{LEFT}" x2="{LEFT + plot}" y1="{y(v)}" y2="{y(v)}" stroke="{t["grid"]}" stroke-width="1"/>')
        s.append(f'<text x="{LEFT - 8}" y="{y(v) + 4}" font-size="11" text-anchor="end" '
                 f'fill="{t["muted"]}" style="font-variant-numeric:tabular-nums">{v}%</text>')

    band = plot / len(MID)
    for i, (cur, v) in enumerate(MID.items()):
        cx = LEFT + band * (i + 0.5)
        s.append(column(cx - BAR - 4, y(v), t["mid"]))
        s.append(f'<text x="{cx - 4 - BAR / 2}" y="{y(v) - 8}" font-size="13" font-weight="600" '
                 f'text-anchor="middle" fill="{t["ink"]}">{v:.2f}%</text>')
        # Executable is zero: a 2px mark on the baseline, labelled, so the zero is seen.
        s.append(f'<rect x="{cx + 4}" y="{BASE - 2}" width="{BAR}" height="2" fill="{t["exe"]}"/>')
        s.append(f'<text x="{cx + 4 + BAR / 2}" y="{BASE - 8}" font-size="13" font-weight="600" '
                 f'text-anchor="middle" fill="{t["ink"]}">0</text>')
        s.append(f'<text x="{cx}" y="{BASE + 20}" font-size="12" font-weight="600" text-anchor="middle" '
                 f'fill="{t["ink"]}">{cur}</text>')
    s.append(f'<line x1="{LEFT}" x2="{LEFT + plot}" y1="{BASE}" y2="{BASE}" stroke="{t["base"]}" stroke-width="1"/>')

    s.append(f'<text x="{LEFT}" y="{H - 14}" font-size="11" fill="{t["muted"]}">'
             "Counts violations larger than 1 tick (0.0001 of a coin), the most rounding can create. "
             "Deribit, 6-10 Sep 2026.</text>")
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    out = Path(__file__).parent
    for name, theme in THEMES.items():
        (out / f"violation-rates-{name}.svg").write_text(render(theme), encoding="utf-8")
        print(f"wrote violation-rates-{name}.svg")
