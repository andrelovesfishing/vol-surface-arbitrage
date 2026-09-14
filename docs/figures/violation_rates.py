"""Render the README's headline figure: python docs/figures/violation_rates.py

Numbers are pinned from the README's materiality-floor table (frozen window), so
the figure regenerates without the dataset. Writes a light and a dark SVG.
"""
from pathlib import Path

FLOORS = ("0", "1", "2")
MID = {"BTC": (16.43, 9.30, 4.95), "ETH": (13.45, 9.25, 6.11)}  # % of butterflies
EXECUTABLE = 0.0  # at every floor, on both underlyings

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
                  grid="#e1e0d9", base="#c3c2b7", mid="#2a78d6", exe="#eb6834"),
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
                 grid="#2c2c2a", base="#383835", mid="#3987e5", exe="#d95926"),
}

W, H = 720, 340
LEFT, RIGHT, TOP, BASE = 52, 20, 112, 286   # plot spans y TOP..BASE
GAP, YMAX, BAR = 28, 18.0, 24
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def y(v):
    return BASE - v / YMAX * (BASE - TOP)


def column(x, top, fill):
    """A column with a 4px rounded data-end and a square baseline."""
    r = 4
    return (f'<path d="M{x},{BASE} V{top + r} Q{x},{top} {x + r},{top} H{x + BAR - r} '
            f'Q{x + BAR},{top} {x + BAR},{top + r} V{BASE} Z" fill="{fill}"/>')


def render(t):
    panel = (W - LEFT - RIGHT - GAP) / 2
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'role="img" font-family="{FONT}">',
         "<title>Share of option butterflies violating convexity: mid vs executable prices</title>",
         "<desc>At mid prices 16.4%, 9.3% and 5.0% of BTC butterflies and 13.5%, 9.3% and 6.1% of "
         "ETH butterflies violate convexity at materiality floors of 0, 1 and 2 ticks. "
         "At executable prices the share is zero at every floor on both.</desc>",
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         f'<text x="{LEFT}" y="34" font-size="16" font-weight="600" fill="{t["ink"]}">'
         "Apparent arbitrage vanishes at tradeable prices</text>",
         f'<text x="{LEFT}" y="56" font-size="12.5" fill="{t["ink2"]}">'
         "Share of butterflies violating convexity, 5,284,244 quotes</text>"]

    # Legend: colored swatch beside ink text, never colored text.
    lx = LEFT
    for label, color in (("mid price", t["mid"]), ("executable price (bid/ask)", t["exe"])):
        s.append(f'<rect x="{lx}" y="72" width="10" height="10" rx="2" fill="{color}"/>')
        s.append(f'<text x="{lx + 16}" y="81" font-size="12" fill="{t["ink2"]}">{label}</text>')
        lx += 16 + len(label) * 6.6 + 20

    for i, cur in enumerate(MID):
        x0 = LEFT + i * (panel + GAP)
        s.append(f'<text x="{x0}" y="{TOP - 8}" font-size="12" font-weight="600" fill="{t["ink"]}">{cur}</text>')
        for v in (0, 5, 10, 15):
            if v:
                s.append(f'<line x1="{x0}" x2="{x0 + panel}" y1="{y(v)}" y2="{y(v)}" stroke="{t["grid"]}" stroke-width="1"/>')
            if i == 0:
                s.append(f'<text x="{x0 - 8}" y="{y(v) + 4}" font-size="11" text-anchor="end" '
                         f'fill="{t["muted"]}" style="font-variant-numeric:tabular-nums">{v}%</text>')
        band = panel / len(FLOORS)
        for j, (floor, v) in enumerate(zip(FLOORS, MID[cur])):
            cx = x0 + band * (j + 0.5)
            s.append(column(cx - BAR - 1, y(v), t["mid"]))
            # Executable is zero: a 2px mark on the baseline, labelled, so the zero is seen.
            s.append(f'<rect x="{cx + 1}" y="{BASE - 2}" width="{BAR}" height="2" fill="{t["exe"]}"/>')
            s.append(f'<text x="{cx + 1 + BAR / 2}" y="{BASE - 8}" font-size="12" font-weight="600" '
                     f'text-anchor="middle" fill="{t["ink"]}">0</text>')
            s.append(f'<text x="{cx}" y="{BASE + 18}" font-size="11" text-anchor="middle" '
                     f'fill="{t["muted"]}">{floor} tick{"" if floor == "1" else "s"}</text>')
        s.append(f'<line x1="{x0}" x2="{x0 + panel}" y1="{BASE}" y2="{BASE}" stroke="{t["base"]}" stroke-width="1"/>')

    s.append(f'<text x="{LEFT}" y="{H - 14}" font-size="11" fill="{t["muted"]}">'
             "Materiality floor: how large a violation must be to count. 1 tick = 0.0001 coin.</text>")
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    out = Path(__file__).parent
    for name, theme in THEMES.items():
        (out / f"violation-rates-{name}.svg").write_text(render(theme), encoding="utf-8")
        print(f"wrote violation-rates-{name}.svg")
