"""Render the README's butterfly example: python docs/figures/butterfly.py

One real butterfly, pinned from the dataset so the figure regenerates without it:
BTC calls expiring 27 Nov 2026, snapshot 2026-09-09 14:59:52 UTC. Writes a light
and a dark SVG.
"""
from pathlib import Path

STRIKES = (104_000, 105_000, 106_000)
BID = (796.96, 757.11, 677.41)  # USD
ASK = (876.65, 836.81, 757.11)
MID = tuple((b + a) / 2 for b, a in zip(BID, ASK))

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
                  grid="#e1e0d9", base="#c3c2b7", spread="#d6d5cd", mid="#2a78d6", exe="#eb6834"),
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
                 grid="#2c2c2a", base="#383835", spread="#45453f", mid="#3987e5", exe="#d95926"),
}

W, H = 720, 400
LEFT, RIGHT, TOP, BASE = 60, 20, 136, 336   # plot spans y TOP..BASE
GAP, YMIN, YMAX = 40, 650.0, 900.0
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def y(v):
    return BASE - (v - YMIN) / (YMAX - YMIN) * (BASE - TOP)


def dot(x, v, fill, t):
    # 2px surface ring keeps the dot legible where it sits on the spread bar.
    return f'<circle cx="{x}" cy="{y(v):.1f}" r="5.5" fill="{fill}" stroke="{t["surface"]}" stroke-width="2"/>'


def panel(s, t, x0, width, title, subtitle, legs, color, gap_label, roles=None):
    xs = [x0 + width * f for f in (1 / 6, 3 / 6, 5 / 6)]
    s.append(f'<text x="{x0}" y="{TOP - 30}" font-size="13" font-weight="600" fill="{t["ink"]}">{title}</text>')
    s.append(f'<text x="{x0}" y="{TOP - 12}" font-size="12" fill="{t["ink2"]}">{subtitle}</text>')
    for v in (700, 750, 800, 850, 900):
        s.append(f'<line x1="{x0}" x2="{x0 + width}" y1="{y(v)}" y2="{y(v)}" stroke="{t["grid"]}" stroke-width="1"/>')
    for x, b, a, k in zip(xs, BID, ASK, STRIKES):
        s.append(f'<rect x="{x - 4}" y="{y(a):.1f}" width="8" height="{y(b) - y(a):.1f}" rx="4" fill="{t["spread"]}"/>')
        s.append(f'<text x="{x}" y="{BASE + 18}" font-size="11" text-anchor="middle" fill="{t["muted"]}">${k // 1000}k</text>')
    # The straight line between the outside legs: the middle leg must not sit above it.
    chord = (legs[0] + legs[2]) / 2
    s.append(f'<line x1="{xs[0]}" y1="{y(legs[0]):.1f}" x2="{xs[2]}" y2="{y(legs[2]):.1f}" '
             f'stroke="{t["ink2"]}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    for x, v in zip(xs, legs):
        s.append(dot(x, v, color, t))
    if roles:
        for x, v, role in zip(xs, legs, roles):
            s.append(f'<text x="{x - 12}" y="{y(v) + 4:.1f}" font-size="11" text-anchor="end" stroke="{t["surface"]}" stroke-width="4" paint-order="stroke" fill="{t["ink2"]}">{role}</text>')
    # Bracket from the middle leg to the line, labelled with the dollar gap.
    bx = xs[1] + 16
    y1, y2 = sorted((y(legs[1]), y(chord)))
    s.append(f'<path d="M{bx - 4},{y1:.1f} H{bx} V{y2:.1f} H{bx - 4}" fill="none" stroke="{t["ink"]}" stroke-width="1.5"/>')
    s.append(f'<text x="{bx + 8}" y="{(y1 + y2) / 2 + 4:.1f}" font-size="12" font-weight="600" stroke="{t["surface"]}" stroke-width="4" paint-order="stroke" fill="{t["ink"]}">'
             f'${abs(legs[1] - chord):.0f} {gap_label}</text>')
    s.append(f'<line x1="{x0}" x2="{x0 + width}" y1="{BASE}" y2="{BASE}" stroke="{t["base"]}" stroke-width="1"/>')


def render(t):
    width = (W - LEFT - RIGHT - GAP) / 2
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'role="img" font-family="{FONT}">',
         "<title>One BTC call butterfly priced at mid and at executable prices</title>",
         "<desc>Three BTC calls at strikes 104k, 105k and 106k. At mid prices the middle call is $20 "
         "above the straight line between its neighbours, which looks like arbitrage. Buying the outside "
         "calls at the ask and selling the middle at the bid, it is $60 below the line: no arbitrage.</desc>",
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         f'<text x="{LEFT}" y="34" font-size="16" font-weight="600" fill="{t["ink"]}">'
         "The same butterfly, priced two ways</text>",
         f'<text x="{LEFT}" y="56" font-size="12.5" fill="{t["ink2"]}">'
         "The middle option must not sit above the dashed line between its neighbours</text>"]

    lx = LEFT
    for label, color, shape in (("bid-ask spread", t["spread"], "bar"), ("mid price", t["mid"], "dot"),
                                ("traded price", t["exe"], "dot")):
        if shape == "bar":
            s.append(f'<rect x="{lx + 2}" y="70" width="6" height="14" rx="3" fill="{color}"/>')
        else:
            s.append(f'<circle cx="{lx + 5}" cy="77" r="5" fill="{color}"/>')
        s.append(f'<text x="{lx + 16}" y="81" font-size="12" fill="{t["ink2"]}">{label}</text>')
        lx += 16 + len(label) * 6.6 + 20

    for v in (700, 750, 800, 850, 900):
        s.append(f'<text x="{LEFT - 8}" y="{y(v) + 4}" font-size="11" text-anchor="end" '
                 f'fill="{t["muted"]}" style="font-variant-numeric:tabular-nums">${v}</text>')

    panel(s, t, LEFT, width, "At mid prices", "Looks like free money", MID, t["mid"], "above")
    panel(s, t, LEFT + width + GAP, width, "At prices you can trade", "No arbitrage",
          (ASK[0], BID[1], ASK[2]), t["exe"], "below", roles=("buy", "sell", "buy"))

    s.append(f'<text x="{LEFT}" y="{H - 14}" font-size="11" fill="{t["muted"]}">'
             "BTC calls expiring 27 Nov 2026, Deribit, 9 Sep 2026 14:59 UTC. Strike on the x-axis.</text>")
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    out = Path(__file__).parent
    for name, theme in THEMES.items():
        (out / f"butterfly-{name}.svg").write_text(render(theme), encoding="utf-8")
        print(f"wrote butterfly-{name}.svg")
