"""
Gera o carrossel do LinkedIn (out/carrossel.html -> out/Carrossel_Radar_Mercado_Aereo.pdf).
Slides 1080x1350 com gráficos em SVG desenhados a partir de out/metrics.json.

Uso: python src/build_carousel.py
"""
import json
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
M = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
mens = pd.read_pickle(OUT / "_mensal.pkl")

C = {"GOL": "#eb6834", "Azul": "#2a78d6", "LATAM": "#1baf7a"}
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
NEG, POS = "#e34948", "#256abf"
TOTAL = 10
FONTE = f"Fonte: ANAC, Dados Estatísticos do Transporte Aéreo (voos domésticos regulares), base até {M['ultimo_mes'][5:]}/{M['ultimo_mes'][:4]}."


# ------------------------------------------------------------------ formatação pt-BR
def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, d=1, sign=False):
    s = br(x * 100, d) + "%"
    return ("+" + s if x > 0 else s.replace("-", "−")) if sign else s


def pp(x, d=1):
    return ("+" if x > 0 else "−" if x < 0 else "") + br(abs(x), d) + " pp"


def mi(x, d=1):
    return br(x / 1e6, d) + " mi"


P, ANO, ANT = M["periodo"], M["ano"], M["ano_ant"]
MK, CI = M["mercado"], M["cias"]


# ------------------------------------------------------------------ helpers SVG
def svg(w, h, body):
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, system-ui, sans-serif">{body}</svg>'


def t(x, y, s, size=22, fill=MUTED, anchor="start", weight=400, extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" {extra}>{s}</text>'


def line(x1, y1, x2, y2, stroke=GRID, w=1.5, extra=""):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{w}" {extra}/>'


def bar_v(x, y0, y1, w, fill):
    """barra vertical com topo arredondado (4px) ancorada na base."""
    top, h = min(y0, y1), abs(y1 - y0)
    r = min(6, h)
    return (f'<path d="M{x:.1f},{y0:.1f} V{top + r:.1f} Q{x:.1f},{top:.1f} {x + r:.1f},{top:.1f} '
            f'H{x + w - r:.1f} Q{x + w:.1f},{top:.1f} {x + w:.1f},{top + r:.1f} V{y0:.1f} Z" fill="{fill}"/>')


def bar_h(x0, x1, y, h, fill):
    """barra horizontal, ponta arredondada no lado do valor."""
    r = min(6, abs(x1 - x0))
    if x1 >= x0:
        d = f"M{x0:.1f},{y:.1f} H{x1 - r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} V{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 - r:.1f},{y + h:.1f} H{x0:.1f} Z"
    else:
        d = f"M{x0:.1f},{y:.1f} H{x1 + r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} V{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 + r:.1f},{y + h:.1f} H{x0:.1f} Z"
    return f'<path d="{d}" fill="{fill}"/>'


# ------------------------------------------------------------------ gráficos
def chart_pax_anos():
    ytd = mens[mens.data.dt.month <= int(M["ultimo_mes"][-2:])]
    s = ytd.groupby(ytd.data.dt.year).PASSAGEIROS_PAGOS.sum() / 1e6
    W, H, L, R, T, B = 960, 470, 20, 20, 50, 60
    bw = (W - L - R) / len(s)
    mx = s.max() * 1.12
    y = lambda v: T + (H - T - B) * (1 - v / mx)
    out = [line(L, H - B, W - R, H - B, AXIS, 2)]
    for i, (ano, v) in enumerate(s.items()):
        x = L + i * bw + bw * 0.18
        cor = C["GOL"] if ano == ANO else "#c9c7bf" if ano != 2019 else "#9e9c94"
        out.append(bar_v(x, H - B, y(v), bw * 0.64, cor))
        out.append(t(x + bw * 0.32, y(v) - 14, br(v, 1), 26, INK if ano in (ANO, 2019) else INK2, "middle",
                     700 if ano == ANO else 500))
        out.append(t(x + bw * 0.32, H - B + 36, str(ano), 24, INK2, "middle", 600 if ano == ANO else 400))
    return svg(W, H, "".join(out))


def chart_share():
    rows = [r for r in M["serie_share"] if r["GOL_12m"] is not None and r["data"] >= "2019-12"]
    W, H, L, R, T, B = 960, 560, 70, 150, 30, 50
    lo, hi = 0.20, 0.45
    n = len(rows)
    X = lambda i: L + (W - L - R) * i / (n - 1)
    Y = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo))
    out = []
    for v in (0.20, 0.25, 0.30, 0.35, 0.40, 0.45):
        out.append(line(L, Y(v), W - R, Y(v), GRID, 1.5))
        out.append(t(L - 12, Y(v) + 8, f"{int(v * 100)}%", 22, MUTED, "end"))
    for i, r in enumerate(rows):
        if r["data"].endswith("-12") or i == n - 1:
            lab = r["data"][:4] if r["data"].endswith("-12") else r["data"][5:] + "/" + r["data"][2:4]
            if r["data"].endswith("-12"):
                lab = "dez/" + r["data"][2:4]
            out.append(t(X(i), H - B + 34, lab, 20, MUTED, "middle"))
    ends = []
    for g in ["LATAM", "GOL", "Azul"]:
        pts = " ".join(f"{X(i):.1f},{Y(r[g + '_12m']):.1f}" for i, r in enumerate(rows))
        w = 6 if g == "GOL" else 4
        out.append(f'<polyline points="{pts}" fill="none" stroke="{C[g]}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"/>')
        v = rows[-1][g + "_12m"]
        ends.append([g, v, Y(v)])
    # rótulos diretos no fim (evita sobreposição)
    ends.sort(key=lambda e: e[2])
    for k in range(1, len(ends)):
        if ends[k][2] - ends[k - 1][2] < 46:
            ends[k][2] = ends[k - 1][2] + 46
    for g, v, yy in ends:
        out.append(f'<circle cx="{X(n - 1):.1f}" cy="{Y(v):.1f}" r="8" fill="{C[g]}" stroke="#fcfcfb" stroke-width="3"/>')
        out.append(t(X(n - 1) + 18, yy + 2, g, 24, INK, "start", 700))
        out.append(t(X(n - 1) + 18, yy + 28, pct(v), 22, INK2, "start", 500))
    return svg(W, H, "".join(out))


def chart_cresc():
    gs = ["LATAM", "GOL", "Azul"]
    W, H, L, R, T, B = 960, 470, 150, 20, 60, 30
    lo, hi = -0.04, 0.24
    X = lambda v: L + (W - L - R) * (v - lo) / (hi - lo)
    out = []
    for v in (0, 0.05, 0.10, 0.15, 0.20):
        out.append(line(X(v), T - 20, X(v), H - B, AXIS if v == 0 else GRID, 2 if v == 0 else 1.5))
        out.append(t(X(v), T - 32, pct(v, 0, True) if v else "0%", 20, MUTED, "middle"))
    rowh = (H - T - B) / 3
    for i, g in enumerate(gs):
        y0 = T + i * rowh + 22
        out.append(t(L - 24, y0 + 52, g, 28, INK, "end", 700))
        for k, (key, lab, op) in enumerate((("cresc_ask", "Oferta (ASK)", 0.45), ("cresc_pax", "Passageiros", 1))):
            v = CI[g][key]
            yy = y0 + k * 46
            col = C[g]
            out.append(bar_h(X(0), X(v), yy, 36, col).replace('/>', f' fill-opacity="{op}"/>'))
            lx = max(X(v), X(0)) + 14
            out.append(t(lx, yy + 27, f"{lab} {pct(v, 1, True)}", 22, INK if k else INK2, "start", 700 if k else 500))
    return svg(W, H, "".join(out))


def chart_quadrante():
    ms = M["mercados_gol"]
    W, H, L, R, T, B = 960, 720, 80, 30, 60, 70
    xlo, xhi, ylo, yhi = -0.15, 0.35, -8, 8
    cx_ = lambda v: min(max(v, xlo + 0.02), xhi - 0.02)
    cy_ = lambda v: min(max(v, ylo + 0.8), yhi - 0.8)
    X = lambda v: L + (W - L - R) * (cx_(v) - xlo) / (xhi - xlo)
    Y = lambda v: T + (H - T - B) * (1 - (cy_(v) - ylo) / (yhi - ylo))
    out = []
    for v in (-8, -4, 0, 4, 8):
        out.append(line(L, Y(v) if abs(v) < 8 else T + (H - T - B) * (1 - (v - ylo) / (yhi - ylo)), W - R,
                        Y(v) if abs(v) < 8 else T + (H - T - B) * (1 - (v - ylo) / (yhi - ylo)), AXIS if v == 0 else GRID, 2.5 if v == 0 else 1.5))
    for v in (-4, 0, 4):
        out.append(t(L - 12, Y(v) + 8, pp(v, 0) if v else "0", 20, MUTED, "end"))
    x0 = L + (W - L - R) * (0 - xlo) / (xhi - xlo)
    for v in (-0.10, 0, 0.10, 0.20, 0.30):
        xv = L + (W - L - R) * (v - xlo) / (xhi - xlo)
        out.append(line(xv, T, xv, H - B, AXIS if v == 0 else GRID, 2.5 if v == 0 else 1.5))
        out.append(t(xv, H - B + 32, pct(v, 0, True) if v else "0%", 20, MUTED, "middle"))
    # rótulos dos quadrantes fora da área de dados (acima e abaixo)
    out.append(t(x0 - 14, T - 22, "↖ CONSOLIDAR", 22, "#6b6960", "end", 700, 'letter-spacing="1.5"'))
    out.append(t(x0 + 14, T - 22, "CRESCER JUNTO ↗", 22, "#6b6960", "start", 700, 'letter-spacing="1.5"'))
    out.append(t((L + W - R) / 2, H - 6, "Crescimento do mercado (passageiros, jan a set, 2026 vs 2025) →", 22, INK2, "middle"))
    out.append(t(22, (T + H - B) / 2, "Variação do share da GOL →", 22, INK2, "middle", 400,
                 f'transform="rotate(-90 22 {(T + H - B) / 2})"'))
    mxp = max(m["gol_pax"] for m in ms)
    pts = []
    for m in sorted(ms, key=lambda m: -m["gol_pax"]):
        r = 10 + 24 * (m["gol_pax"] / mxp) ** 0.5
        pts.append((m, X(m["cresc_mercado"]), Y(m["delta_share_pp"]), r))
    for m, cx, cy, r in pts:
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{C["GOL"]}" fill-opacity="0.75" stroke="#fcfcfb" stroke-width="2.5"/>')
    # rótulos: posicionamento guloso evitando bolhas e outros rótulos
    boxes = [(cx - r, cy - r, cx + r, cy + r) for _, cx, cy, r in pts]
    hit = lambda b1, b2: not (b1[2] < b2[0] or b2[2] < b1[0] or b1[3] < b2[1] or b2[3] < b1[1])
    rotular = ["RIO-SAO", "SAO-SSA", "BSB-SAO", "POA-SAO", "BHZ-SAO", "CWB-SAO", "REC-SAO", "GYN-SAO", "SAO-VIX",
               "IGU-RIO", "REC-RIO", "CWB-RIO", "POA-RIO", "FOR-SAO", "BSB-RIO", "RIO-SSA", "FOR-RIO"]
    yb = H - B - 14
    out.append(t(x0 - 14, yb, "↙ REVER CAPACIDADE", 22, "#6b6960", "end", 700, 'letter-spacing="1.5"'))
    out.append(t(x0 + 14, yb, "DEFENDER ↘", 22, "#6b6960", "start", 700, 'letter-spacing="1.5"'))
    placed = [(x0 - 14 - 250, yb - 20, x0 - 14, yb + 4), (x0 + 14, yb - 20, x0 + 14 + 150, yb + 4)]
    for m, cx, cy, r in pts:
        if m["mercado"] not in rotular:
            continue
        fora = not (xlo + 0.02 <= m["cresc_mercado"] <= xhi - 0.02 and ylo + 0.8 <= m["delta_share_pp"] <= yhi - 0.8)
        xfora = m["cresc_mercado"] > xhi - 0.02
        lab = m["mercado"] + (f" ({pp(m['delta_share_pp'], 0)}" + (f"; mercado {pct(m['cresc_mercado'], 0, True)}" if xfora else "") + ")" if fora else "")
        w, h = 11.2 * len(lab), 22
        cands = [(cx + r + 6, cy + 7, "start"), (cx - r - 6, cy + 7, "end"), (cx, cy - r - 8, "middle"),
                 (cx, cy + r + 22, "middle"), (cx + r * 0.7 + 4, cy - r * 0.7 - 4, "start"),
                 (cx - r * 0.7 - 4, cy - r * 0.7 - 4, "end"), (cx + r * 0.7 + 4, cy + r * 0.7 + 18, "start"),
                 (cx - r * 0.7 - 4, cy + r * 0.7 + 18, "end")]
        for x, y, anc in cands:
            x0b = x if anc == "start" else x - w if anc == "end" else x - w / 2
            bb = (x0b, y - h + 4, x0b + w, y + 4)
            if bb[0] < L or bb[2] > W - R + 20 or bb[1] < T or bb[3] > H - B:
                continue
            others = [bx for (mm, ccx, ccy, rr), bx in zip(pts, boxes) if mm is not m]
            if any(hit(bb, o) for o in others + placed):
                continue
            placed.append(bb)
            out.append(t(x, y, lab, 20, INK, anc, 600))
            break
    return svg(W, H, "".join(out))


def chart_gap():
    ms = sorted(M["mercados_gol"], key=lambda m: -m["gap_oferta_pp"])
    ms = ms[:6] + ms[-6:]
    W, H, L, R, T, B = 960, 720, 150, 40, 40, 20
    lo, hi = -2.0, 2.6
    X = lambda v: L + (W - L - R) * (v - lo) / (hi - lo)
    rowh = (H - T - B) / len(ms)
    out = [line(X(0), T - 10, X(0), H - B, AXIS, 2.5)]
    for v in (-2, -1, 1, 2):
        out.append(line(X(v), T - 10, X(v), H - B, GRID, 1.5))
    for v in (-2, -1, 0, 1, 2):
        out.append(t(X(v), T - 18, pp(v, 0) if v else "0", 20, MUTED, "middle"))
    for i, m in enumerate(ms):
        y = T + i * rowh + 8
        g = m["gap_oferta_pp"]
        out.append(t(L - 18, y + rowh / 2 + 4, m["mercado"], 24, INK, "end", 600))
        out.append(bar_h(X(0), X(g), y + 4, rowh - 22, NEG if g > 0 else POS))
        lf = f"LF {pct(m['lf_gol'], 0)} vs {pct(m['lf_mercado'], 0)}"
        out.append(t(max(X(g), X(0)) + 12, y + rowh / 2 + 4, f"{pp(g)} · {lf}", 20, INK2, "start", 500))
    return svg(W, H, "".join(out))


def chart_forecast():
    F = M["forecast"]
    hist = [(pd.Timestamp(h["data"]), h["pax"] / 1e6) for h in F["historico"] if h["data"] >= "2024-01"]
    prev = [(pd.Timestamp(p["data"]), p["base"] / 1e6, p["p10"] / 1e6, p["p90"] / 1e6) for p in F["prev"]]
    allx = [h[0] for h in hist] + [p[0] for p in prev]
    W, H, L, R, T, B = 960, 520, 60, 30, 30, 50
    lo, hi = 6.5, 11
    i0 = allx[0]
    idx = lambda d: (d.year - i0.year) * 12 + d.month - i0.month
    n = idx(allx[-1])
    X = lambda d: L + (W - L - R) * idx(d) / n
    Y = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo))
    out = []
    for v in (7, 8, 9, 10, 11):
        out.append(line(L, Y(v), W - R, Y(v), GRID, 1.5))
        out.append(t(L - 10, Y(v) + 8, f"{v} mi", 20, MUTED, "end"))
    for d in allx:
        if d.month == 1:
            out.append(t(X(d), H - B + 32, str(d.year), 20, MUTED, "start"))
            out.append(line(X(d), H - B, X(d), H - B + 8, AXIS, 2))
    band = [(X(p[0]), Y(p[3])) for p in prev] + [(X(p[0]), Y(p[2])) for p in reversed(prev)]
    out.append(f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in band)}" fill="{C["GOL"]}" fill-opacity="0.16"/>')
    out.append(f'<polyline points="{" ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in hist)}" fill="none" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>')
    pts = [hist[-1][:2]] + [(p[0], p[1]) for p in prev]
    out.append(f'<polyline points="{" ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in pts)}" fill="none" stroke="{C["GOL"]}" stroke-width="4" stroke-dasharray="10 8" stroke-linejoin="round"/>')
    xs = X(hist[-1][0])
    out.append(line(xs, T, xs, H - B, AXIS, 2, 'stroke-dasharray="4 6"'))
    out.append(t(xs - 12, Y(10.6), "realizado", 22, INK2, "end", 600))
    out.append(t(xs + 12, Y(10.6), "previsão", 22, "#b5451b", "start", 600))
    return svg(W, H, "".join(out))


def sens_table():
    base_m, sh0 = cen["mercado_2026_est"], cen["share_gol_12m"]
    shares = [sh0 - 0.02, sh0 - 0.01, sh0, sh0 + 0.01, sh0 + 0.02]
    growths = [0.01, 0.03, cen["cresc_base_2027"], 0.07, 0.09]
    vals = [[base_m * (1 + g_) * s_ / 1e6 for s_ in shares] for g_ in growths]
    flat = sorted(v for r_ in vals for v in r_)
    lo_, hi_ = flat[0], flat[-1]
    def bg(v):  # rampa sequencial azul (claro -> escuro)
        ramp = ["#e6eefa", "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec"]
        return ramp[min(5, int((v - lo_) / (hi_ - lo_ + 1e-9) * 6))]
    h = "<table class='sens'><tr><th>Cresc. ↓ / Share →</th>" + "".join(f"<th>{pct(s_)}</th>" for s_ in shares) + "</tr>"
    for g_, row in zip(growths, vals):
        h += f"<tr><th>{pct(g_, 1, True)}</th>" + "".join(
            f"<td style='background:{bg(v)}' class='{'mid' if (g_ == growths[2] and k == 2) else ''}'>{br(v, 1)}</td>" for k, v in enumerate(row)) + "</tr>"
    return h + "</table>"


# ------------------------------------------------------------------ slides
def slide(n, kicker, titulo, corpo, nota=FONTE, cls=""):
    return f"""
<section class="slide {cls}">
  <div class="top"><span class="kick">{kicker}</span><span class="num">{n}/{TOTAL}</span></div>
  <h2>{titulo}</h2>
  <div class="body">{corpo}</div>
  <div class="foot"><span>{nota}</span></div>
</section>"""


g, l, a = CI["GOL"], CI["LATAM"], CI["Azul"]
bt, cen = M["backtest"], M["cenarios"]
tl = M["test_learn"]
gap_top = sorted(M["mercados_gol"], key=lambda m: -m["gap_oferta_pp"])
mods = sorted(bt["modelos"].items(), key=lambda kv: kv[1]["mape"])

slides = []
slides.append(f"""
<section class="slide capa">
  <div class="top"><span class="kick">Análise independente · dados abertos</span><span class="num">1/{TOTAL}</span></div>
  <div class="capa-mid">
    <p class="eyebrow">Radar Competitivo</p>
    <h1>O mercado aéreo doméstico em {ANO}, lido como um analista de mercado</h1>
    <p class="lead">Market share, ocupação por mercado, forecast e cenários, feitos com dados públicos da ANAC, Python e Excel.</p>
  </div>
  <div class="hero">
    <div><b>{mi(MK['pax'])}</b><span>passageiros pagos em {P} {ANO}</span></div>
    <div><b>{pct(MK['cresc_pax'], 1, True)}</b><span>vs mesmo período de {ANT}</span></div>
    <div><b>{pct(MK['vs_2019'], 0, True)}</b><span>acima de 2019 (pré-pandemia)</span></div>
  </div>
  <div class="foot"><span>{FONTE}</span><span class="swipe">arraste →</span></div>
</section>""")

slides.append(slide(2, "01 · O mercado",
    f"Demanda subiu {pct(MK['cresc_pax'], 1)}, mas a oferta subiu mais. A ocupação caiu {br(abs(MK['lf'] - MK['lf_ant']) * 100)} pp.",
    f"""<div class="stats">
      <div><b>{pct(MK['cresc_pax'], 1, True)}</b><span>passageiros</span></div>
      <div><b>{pct(MK['cresc_rpk'], 1, True)}</b><span>RPK (demanda em km)</span></div>
      <div><b>{pct(MK['cresc_ask'], 1, True)}</b><span>ASK (oferta em km)</span></div>
      <div><b>{pct(MK['lf'], 1)}</b><span>load factor ({pp((MK['lf'] - MK['lf_ant']) * 100)})</span></div>
    </div>
    <p class="cap">Passageiros pagos, {P} de cada ano (milhões)</p>
    {chart_pax_anos()}
    <p class="so">Com mais assento sobrando, as companhias passam a disputar passageiro com preço e gestão de inventário.</p>"""))

slides.append(slide(3, "02 · Market share",
    f"A GOL foi quem mais ganhou espaço em {ANO}: {pp((g['share_rpk'] - g['share_rpk_ant']) * 100)} de share em RPK.",
    f"""<p class="cap">Market share em RPK, média móvel de 12 meses</p>
    {chart_share()}
    <table class="tb">
      <tr><th></th><th>Share {P} {ANT}</th><th>Share {P} {ANO}</th><th>Variação</th></tr>
      {''.join(f"<tr><td><i style='background:{C[k]}'></i>{k}</td><td>{pct(CI[k]['share_rpk_ant'])}</td><td><b>{pct(CI[k]['share_rpk'])}</b></td><td>{pp((CI[k]['share_rpk'] - CI[k]['share_rpk_ant']) * 100)}</td></tr>" for k in ['LATAM', 'GOL', 'Azul'])}
    </table>"""))

slides.append(slide(4, "03 · Crescimento x ocupação",
    f"A GOL aumentou a oferta em {pct(g['cresc_ask'], 1)} e os passageiros em {pct(g['cresc_pax'], 1)}. A ocupação caiu {br(abs(g['lf'] - g['lf_ant']) * 100)} pp.",
    f"""<p class="cap">Crescimento {P} {ANO} vs {ANT}</p>
    {chart_cresc()}
    <div class="stats three">
      {''.join(f"<div><b>{pct(CI[k]['lf'], 1)}</b><span>LF {k} ({pp((CI[k]['lf'] - CI[k]['lf_ant']) * 100)})</span></div>" for k in ['LATAM', 'GOL', 'Azul'])}
    </div>
    <p class="so">Com a oferta crescendo acima da demanda, pricing precisa decidir em quais voos e a que preço abrir mais assentos baratos.</p>"""))

slides.append(slide(5, "04 · Onde a GOL ganha e perde",
    f"Em {M['quadrantes'].get('Defender', 0)} dos 25 maiores mercados da GOL, o mercado cresce e a GOL perde share.",
    f"""<p class="cap">Cada bolha é um par de cidades. Tamanho = passageiros da GOL. Valores fora da escala estão entre parênteses.</p>
    {chart_quadrante()}
    <div class="stats four">
      {''.join(f"<div><b>{M['quadrantes'].get(k, 0)}</b><span>{k.lower()}</span></div>" for k in ['Crescer junto', 'Defender', 'Consolidar', 'Rever capacidade'])}
    </div>"""))

slides.append(slide(6, "05 · Oferta x demanda por mercado",
    f"Em {gap_top[0]['mercado']} e {gap_top[1]['mercado']}, a GOL oferta mais do que vende. Em {gap_top[-3]['mercado']}, {gap_top[-2]['mercado']} e {gap_top[-1]['mercado']}, ocupa acima do mercado.",
    f"""<p class="cap">Gap de oferta = share de assentos da GOL − share de passageiros da GOL (pp)</p>
    {chart_gap()}
    <div class="legend"><span><i style="background:{NEG}"></i>Oferta acima da demanda: estimular venda ou ajustar capacidade</span>
    <span><i style="background:{POS}"></i>Ocupação acima do mercado: espaço para proteger tarifa</span></div>"""))

slides.append(slide(7, "06 · Forecast",
    f"Comparei 4 modelos de forecast. O melhor errou {pct(bt['modelos'][bt['melhor']]['mape'], 1)} em média, prevendo até 6 meses à frente.",
    f"""<p class="cap">Passageiros pagos por mês no doméstico regular (milhões). Faixa = P10 a P90 dos erros do backtest.</p>
    {chart_forecast()}
    <table class="tb">
      <tr><th>Modelo (backtest rolante, 13 origens)</th><th>Erro médio (MAPE)</th><th>Viés</th></tr>
      {''.join(f"<tr class='{'win' if k == bt['melhor'] else ''}'><td>{k}</td><td>{pct(v['mape'])}</td><td>{pct(v['vies'], 1, True)}</td></tr>" for k, v in mods)}
    </table>
    <p class="note">MAPE = erro absoluto médio. Viés negativo = o modelo tende a prever abaixo do realizado (conservador).</p>"""))

cc = cen["cenarios"]
slides.append(slide(8, "07 · Cenários 2027",
    f"Passageiros da GOL em 2027: de {mi(cc['Pessimista']['gol_2027'])} a {mi(cc['Otimista']['gol_2027'])}, conforme o crescimento do mercado e o share.",
    f"""<div class="cards">
      {''.join(f'''<div class="card {'base' if k == 'Base' else ''}"><p class="cn">{k}</p><b>{mi(v['gol_2027'])}</b>
        <span class="vs">{pct(v['vs_2025'], 1, True)} vs 2025</span>
        <ul><li>Mercado 2027: <b>{pct(v['cresc_mercado'], 1, True)}</b></li><li>Share GOL: <b>{pct(v['share'], 1)}</b></li></ul></div>''' for k, v in cc.items())}
    </div>
    <div class="formula">Passageiros GOL 2027 = Mercado {ANO} × (1 + crescimento) × share</div>
    <p class="cap">Sensibilidade: passageiros GOL 2027 (milhões) por crescimento do mercado × share</p>
    {sens_table()}
    <p class="note">Mercado {ANO} = {mi(cen['mercado_2026_est'])} (realizado até set + forecast out a dez). Base = crescimento do modelo ({pct(cen['cresc_base_2027'], 1, True)}) e share dos últimos 12 meses. Na planilha, tudo isso é fórmula e as premissas são editáveis.</p>"""))

tl_html = "".join(f"""<div class="pair"><div><span>Teste</span><b>{p['teste']}</b><em>LF GOL {pct(p['lf_gol_teste'], 1)} vs mercado {pct(p['lf_mercado_teste'], 1)}</em></div>
  <div class="vs2">vs</div><div><span>Controle</span><b>{p['controle']}</b><em>correlação sazonal {br(p['correlacao'], 2)}</em></div></div>""" for p in tl)
slides.append(slide(9, "08 · Test & Learn",
    "Proposta de teste: mais assentos promocionais em 2 mercados onde a GOL ocupa abaixo do mercado.",
    f"""{tl_html}
    <div class="grid2">
      <div><h4>Hipótese</h4><p>Liberar mais assentos nas classes promocionais só nos voos de menor ocupação aumenta o load factor sem reduzir a receita por voo.</p></div>
      <div><h4>Como medir</h4><p>Diferença-em-diferenças: teste vs controle, 6 a 8 semanas antes e depois. KPI: LF e receita por voo.</p></div>
      <div><h4>Guarda-corpos</h4><p>Acompanhar yield médio, share no mercado e ocupação dos voos de pico, para garantir que o teste não canibalize esses voos.</p></div>
      <div><h4>Decisão</h4><p>LF +2 pp vs controle sem perda de receita por voo: escala para os outros mercados com gap acima de 0,5 pp.</p></div>
    </div>""",
    nota="Controle escolhido por correlação da série mensal de passageiros (2025 e 2026) e porte parecido. " + FONTE))

slides.append(f"""
<section class="slide fim">
  <div class="top"><span class="kick">09 · Como fiz</span><span class="num">{TOTAL}/{TOTAL}</span></div>
  <h2>Como fiz a análise</h2>
  <ol class="flow">
    <li><b>Dados</b><span>CSV oficial da ANAC (361 MB, 2000 a 2026). Filtrei voos domésticos regulares de 2019 em diante.</span></li>
    <li><b>Tratamento (Python + pandas)</b><span>Agrupei aeroportos por cidade (CGH+GRU+VCP = SAO), juntei ida e volta no mesmo mercado e calculei share, LF, HHI e gap de oferta.</span></li>
    <li><b>Forecast</b><span>4 modelos comparados em backtest rolante. A faixa de incerteza vem dos erros reais do teste.</span></li>
    <li><b>Excel</b><span>7 abas com fórmulas auditáveis, gráficos, cenários editáveis e matriz de sensibilidade.</span></li>
  </ol>
  <div class="limits"><b>Limitações:</b> a base é por etapa de voo, não por origem-destino final do passageiro, e não tem tarifa. Por isso não medi yield nem receita. Para medir isso, dá para cruzar com a base de tarifas da ANAC.</div>
  <p class="cta">Planilha e código no primeiro comentário.<br>Se você trabalha com pricing ou revenue management, o que olharia diferente?</p>
  <div class="foot"><span>Análise independente, feita só com dados públicos. Não representa nenhuma companhia aérea.</span></div>
</section>""")

CSS = """
@page { size: 1080px 1350px; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #e9e8e3; font-family: "Segoe UI", system-ui, sans-serif; color: #0b0b0b; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.slide { width: 1080px; height: 1350px; background: #fcfcfb; padding: 72px 60px 56px; display: flex; flex-direction: column; position: relative; overflow: hidden; page-break-after: always; break-after: page; margin: 0 auto 24px; }
.slide::before { content: ""; position: absolute; left: 0; top: 0; width: 100%; height: 12px; background: #eb6834; }
.top { display: flex; justify-content: space-between; font-size: 22px; color: #52514e; letter-spacing: 2px; text-transform: uppercase; font-weight: 600; }
.num { color: #898781; font-weight: 500; }
h2 { font-size: 50px; line-height: 1.12; font-weight: 700; margin: 26px 0 26px; letter-spacing: -0.5px; text-wrap: balance; }
.body { flex: 1; display: flex; flex-direction: column; gap: 20px; }
.cap { font-size: 22px; color: #52514e; font-weight: 600; }
.so { font-size: 27px; line-height: 1.35; color: #0b0b0b; border-left: 6px solid #eb6834; padding: 4px 0 4px 20px; margin-top: auto; }
.foot { display: flex; justify-content: space-between; align-items: end; gap: 24px; font-size: 17px; color: #898781; padding-top: 18px; border-top: 1.5px solid #e1e0d9; margin-top: 16px; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.stats.three { grid-template-columns: repeat(3, 1fr); }
.stats > div { background: #f4f3ef; border-radius: 16px; padding: 18px 20px; }
.stats b { display: block; font-size: 44px; font-weight: 700; letter-spacing: -1px; }
.stats span { font-size: 20px; color: #52514e; }
.stats.four b { font-size: 40px; }
.tb { width: 100%; border-collapse: collapse; font-size: 24px; font-variant-numeric: tabular-nums; }
.tb th { text-align: left; font-size: 19px; color: #898781; font-weight: 600; padding: 8px 10px; border-bottom: 2px solid #c3c2b7; }
.tb td { padding: 11px 10px; border-bottom: 1.5px solid #e1e0d9; }
.tb td i { display: inline-block; width: 18px; height: 18px; border-radius: 4px; margin-right: 12px; vertical-align: -2px; }
.tb tr.win td { font-weight: 700; background: #fdf0ea; }
.legend { display: flex; flex-direction: column; gap: 10px; font-size: 22px; color: #52514e; }
.legend i { display: inline-block; width: 20px; height: 20px; border-radius: 4px; margin-right: 12px; vertical-align: -3px; }
.capa { background: #14213d; color: #f6f5f1; }
.capa .top, .capa .num { color: #c9c7bf; }
.capa .foot { border-color: #2e3b5a; color: #a9adbb; }
.capa-mid { margin-top: 90px; }
.eyebrow { color: #f08a5d; font-size: 30px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; }
h1 { font-size: 78px; line-height: 1.06; font-weight: 800; margin: 22px 0 30px; letter-spacing: -1.5px; }
.lead { font-size: 32px; line-height: 1.4; color: #d6d4cc; max-width: 900px; }
.hero { margin-top: auto; display: grid; grid-template-columns: 1.25fr 1fr 1fr; gap: 18px; margin-bottom: 26px; }
.hero div { border-top: 4px solid #eb6834; padding-top: 18px; }
.hero b { display: block; font-size: 58px; font-weight: 800; letter-spacing: -1px; color: #fff; }
.hero span { font-size: 22px; color: #c9c7bf; }
.swipe { color: #f08a5d; font-weight: 700; font-size: 24px; white-space: nowrap; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.card { background: #f4f3ef; border-radius: 18px; padding: 26px 24px; }
.card.base { background: #14213d; color: #fff; }
.card .cn { font-size: 22px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #898781; }
.card.base .cn { color: #f08a5d; }
.card > b { display: block; font-size: 56px; font-weight: 800; letter-spacing: -1px; margin: 12px 0 4px; }
.card .vs { font-size: 24px; font-weight: 600; }
.card ul { list-style: none; margin-top: 20px; font-size: 21px; line-height: 1.7; border-top: 1.5px solid rgba(128,128,128,.3); padding-top: 14px; }
.formula { font-size: 26px; font-weight: 600; text-align: center; background: #fdf0ea; color: #8a3412; padding: 22px; border-radius: 14px; margin-top: 10px; }
.bul { font-size: 25px; line-height: 1.45; padding-left: 28px; color: #2b2a28; display: flex; flex-direction: column; gap: 12px; margin-top: 6px; }
.pair { display: grid; grid-template-columns: 1fr 70px 1fr; align-items: center; background: #f4f3ef; border-radius: 16px; padding: 20px 26px; }
.pair span { display: block; font-size: 19px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #898781; }
.pair b { display: block; font-size: 44px; font-weight: 800; }
.pair em { font-style: normal; font-size: 21px; color: #52514e; }
.vs2 { font-size: 24px; color: #898781; text-align: center; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 6px; }
.grid2 div { border-top: 4px solid #eb6834; padding-top: 14px; }
.grid2 h4 { font-size: 26px; margin-bottom: 8px; }
.grid2 p { font-size: 22px; line-height: 1.4; color: #2b2a28; }
.flow { list-style: none; counter-reset: s; display: flex; flex-direction: column; gap: 18px; }
.flow li { counter-increment: s; display: grid; grid-template-columns: 64px 1fr; column-gap: 18px; }
.flow li::before { content: counter(s); grid-row: span 2; width: 56px; height: 56px; border-radius: 50%; background: #eb6834; color: #fff; font-weight: 800; font-size: 28px; display: grid; place-items: center; }
.flow b { font-size: 29px; }
.flow span { font-size: 23px; line-height: 1.4; color: #52514e; }
.limits { margin-top: 30px; background: #f4f3ef; border-radius: 14px; padding: 22px 26px; font-size: 22px; line-height: 1.45; color: #2b2a28; }
.cta { margin-top: auto; font-size: 34px; line-height: 1.35; font-weight: 700; }

.note { font-size: 20px; line-height: 1.45; color: #52514e; }
.sens { width: 100%; border-collapse: separate; border-spacing: 4px; font-size: 26px; font-variant-numeric: tabular-nums; text-align: center; }
.sens th { font-size: 20px; color: #52514e; font-weight: 600; padding: 8px; }
.sens td { padding: 16px 8px; border-radius: 8px; color: #0b0b0b; font-weight: 500; }
.sens td.mid { outline: 3px solid #0b0b0b; font-weight: 800; }
.pair b { font-size: 50px !important; }
.grid2 { gap: 26px 26px !important; margin-top: 18px !important; }
.grid2 h4 { font-size: 30px !important; }
.grid2 p { font-size: 25px !important; }
.fim .flow { gap: 30px; margin-top: 16px; }
.fim .flow b { font-size: 32px; }
.fim .flow span { font-size: 25px; }
.fim .limits { font-size: 24px; margin-top: 40px; }
"""

html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Radar Competitivo: mercado aéreo</title>
<style>{CSS}</style></head><body>{''.join(slides)}
<script>/* #s3 mostra só o slide 3 (usado para exportar PNGs) */
const m = location.hash.match(/^#s(\\d+)$/);
if (m) {{ document.querySelectorAll('.slide').forEach((el, i) => {{ if (i + 1 != m[1]) el.remove(); else el.style.margin = '0'; }}); }}
</script></body></html>"""
hp = OUT / "carrossel.html"
hp.write_text(html, encoding="utf-8")

edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
pdf = OUT / "Carrossel_Radar_Mercado_Aereo.pdf"
subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-margins",
                f"--print-to-pdf={pdf}", hp.as_uri()], check=True, capture_output=True, timeout=120)
png_dir = OUT / "slides_png"
png_dir.mkdir(exist_ok=True)
for i in range(1, TOTAL + 1):
    subprocess.run([edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1080,1350",
                    f"--screenshot={png_dir / f'slide_{i:02d}.png'}", hp.as_uri() + f"#s{i}"],
                   check=True, capture_output=True, timeout=120)
print("ok ->", pdf, "e", png_dir)
