"""
Gera out/Radar_Mercado_Aereo.xlsx a partir dos resultados de src/analysis.py.
As colunas derivadas (share, crescimento, load factor, cenários) são FÓRMULAS do Excel,
para quem abrir a planilha conseguir auditar e alterar premissas.

Uso: python src/build_excel.py
"""
import json
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
M = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
mens = pd.read_pickle(OUT / "_mensal.pkl")
mk = pd.read_pickle(OUT / "_mercados_gol.pkl")

AZUL_ESCURO, CINZA, AMARELO = "1F2A44", "F2F4F7", "FFF4CC"
H = Font(bold=True, color="FFFFFF")
HFILL = PatternFill("solid", fgColor=AZUL_ESCURO)
INFILL = PatternFill("solid", fgColor=AMARELO)
THIN = Border(bottom=Side(style="thin", color="D0D5DD"))
PCT, PCT1, NUM, PP = "0.0%", "0.0%", "#,##0", '+0.0" pp";-0.0" pp";0.0" pp"'

wb = Workbook()


def header(ws, row, cols, start_col=1):
    for i, c in enumerate(cols):
        cell = ws.cell(row=row, column=start_col + i, value=c)
        cell.font, cell.fill = H, HFILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 32


def widths(ws, w):
    for i, x in enumerate(w, 1):
        ws.column_dimensions[get_column_letter(i)].width = x


def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=16, color=AZUL_ESCURO)
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(italic=True, color="667085")


# ---------------------------------------------------------------- Leia-me
ws = wb.active
ws.title = "Leia-me"
title(ws, "Radar Competitivo: mercado aéreo doméstico brasileiro",
      f"Fonte: ANAC, Dados Estatísticos do Transporte Aéreo (dados abertos). Base até {M['ultimo_mes']}.")
linhas = [
    ("Escopo", "Voos domésticos regulares. Grupos: LATAM (TAM), GOL (GLO), Azul (AZU + Azul Conecta), Outras."),
    ("Período comparado", f"{M['periodo']} {M['ano']} vs {M['periodo']} {M['ano_ant']} (acumulado no ano)."),
    ("Market share", "Por RPK (passageiro-km pago), padrão da indústria. Nos mercados, share por passageiros pagos."),
    ("Mercado", "Par de cidades sem direção (SAO-REC = REC-SAO). SAO = CGH+GRU+VCP; RIO = SDU+GIG; BHZ = CNF+PLU."),
    ("Load factor (LF)", "RPK / ASK na visão de companhia; passageiros pagos / assentos na visão de mercado."),
    ("Gap de oferta", "Share de assentos da GOL − share de passageiros da GOL no mercado. Positivo = oferta acima da demanda capturada."),
    ("Forecast", f"Modelo vencedor do backtest: {M['backtest']['melhor']}. Intervalo = erros reais do backtest (P10 a P90)."),
    ("Cenários", "Células amarelas na aba Cenarios são premissas editáveis. Todo o resto recalcula sozinho."),
    ("Limitações", "Dados por etapa de voo (não origem-destino final do passageiro) e sem tarifa: não mede yield/receita."),
    ("Aviso", "Análise independente, feita só com dados públicos. Não usa nenhuma informação interna de companhia aérea."),
]
for i, (k, v) in enumerate(linhas, start=4):
    ws.cell(row=i, column=1, value=k).font = Font(bold=True)
    ws.cell(row=i, column=2, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[i].height = 30
widths(ws, [20, 110])

# ---------------------------------------------------------------- Resumo
ws = wb.create_sheet("Resumo")
title(ws, f"Resumo por companhia, {M['periodo']} {M['ano']} vs {M['ano_ant']}")
ytd = mens[mens.data.dt.month <= int(M["ultimo_mes"][-2:])]
g = ytd.assign(ano=ytd.data.dt.year).groupby(["grupo", "ano"])[["PASSAGEIROS_PAGOS", "RPK", "ASK"]].sum()
cols = ["Companhia", f"Pax {M['ano']}", f"Pax {M['ano_ant']}", "Cresc. pax",
        f"RPK {M['ano']}", f"RPK {M['ano_ant']}", f"ASK {M['ano']}", f"ASK {M['ano_ant']}",
        f"LF {M['ano']}", f"LF {M['ano_ant']}", "Δ LF", f"Share RPK {M['ano']}", f"Share RPK {M['ano_ant']}", "Δ share"]
header(ws, 3, cols)
grupos = ["LATAM", "GOL", "Azul", "Outras"]
for i, gr in enumerate(grupos, start=4):
    a, b = g.loc[(gr, M["ano"])], g.loc[(gr, M["ano_ant"])]
    vals = [gr, a.PASSAGEIROS_PAGOS, b.PASSAGEIROS_PAGOS, f"=B{i}/C{i}-1", a.RPK, b.RPK, a.ASK, b.ASK,
            f"=E{i}/G{i}", f"=F{i}/H{i}", f"=(I{i}-J{i})*100",
            f"=E{i}/E$8", f"=F{i}/F$8", f"=(L{i}-M{i})*100"]
    for j, v in enumerate(vals, 1):
        ws.cell(row=i, column=j, value=v)
r = 8
ws.cell(row=r, column=1, value="Total").font = Font(bold=True)
for col in "BCEFGH":
    ws[f"{col}{r}"] = f"=SUM({col}4:{col}7)"
ws[f"D{r}"], ws[f"I{r}"], ws[f"J{r}"], ws[f"K{r}"] = f"=B{r}/C{r}-1", f"=E{r}/G{r}", f"=F{r}/H{r}", f"=(I{r}-J{r})*100"
for row in ws.iter_rows(min_row=4, max_row=8):
    for c in row[1:]:
        c.number_format = NUM
    for idx in (3, 8, 9, 11, 12):
        row[idx].number_format = PCT
    for idx in (10, 13):
        row[idx].number_format = PP
    for c in row:
        c.border = THIN
for c in ws[8]:
    c.font = Font(bold=True)
widths(ws, [12] + [15] * 13)
ws.freeze_panes = "B4"

# ---------------------------------------------------------------- Mensal
ws = wb.create_sheet("Mensal")
title(ws, "Série mensal de RPK por grupo e market share (fórmulas)")
rpk = mens.pivot(index="data", columns="grupo", values="RPK").reindex(columns=grupos).fillna(0)
header(ws, 3, ["Mês"] + [f"RPK {x}" for x in grupos] + ["RPK total"] + [f"Share {x}" for x in grupos[:3]])
for i, (d, rw) in enumerate(rpk.iterrows(), start=4):
    ws.cell(row=i, column=1, value=d.to_pydatetime()).number_format = "mmm/yy"
    for j, gr in enumerate(grupos, 2):
        ws.cell(row=i, column=j, value=float(rw[gr])).number_format = NUM
    ws.cell(row=i, column=6, value=f"=SUM(B{i}:E{i})").number_format = NUM
    for j, col in enumerate("BCD", 7):
        ws.cell(row=i, column=j, value=f"={col}{i}/F{i}").number_format = PCT
last = 3 + len(rpk)
ch = LineChart()
ch.title, ch.y_axis.title, ch.height, ch.width = "Market share mensal (RPK)", "Share", 9, 22
ch.y_axis.number_format = "0%"
ch.add_data(Reference(ws, min_col=7, max_col=9, min_row=3, max_row=last), titles_from_data=True)
ch.set_categories(Reference(ws, min_col=1, min_row=4, max_row=last))
ws.add_chart(ch, "L3")
widths(ws, [10] + [17] * 5 + [12] * 3)
ws.freeze_panes = "B4"

# ---------------------------------------------------------------- Mercados GOL
ws = wb.create_sheet("Mercados_GOL")
title(ws, f"Top 25 mercados da GOL, {M['periodo']} {M['ano']} vs {M['ano_ant']}",
      "Pax e assentos = valores da ANAC. Colunas em azul-claro = fórmulas. Quadrante: crescimento do mercado x variação de share.")
cols = ["Mercado", f"Pax mercado {M['ano']}", f"Pax mercado {M['ano_ant']}", f"Pax GOL {M['ano']}",
        f"Pax GOL {M['ano_ant']}", "Assentos mercado", "Assentos GOL", "Líder", "Share LATAM", "Share Azul",
        "Cresc. mercado", "Share GOL", "Share GOL ant.", "Δ share", "Share assentos GOL", "Gap de oferta",
        "LF GOL", "LF mercado", "Δ LF vs mercado", "HHI", "Quadrante", "Leitura"]
header(ws, 4, cols)
FORM = PatternFill("solid", fgColor="EEF4FF")
for i, (m, r) in enumerate(mk.iterrows(), start=5):
    vals = [m, r.pax, r.pax_ant, r.gol_pax, r.gol_pax_ant, r.assentos, r.gol_assentos, r.lider,
            r.share_LATAM, r.share_Azul,
            f"=B{i}/C{i}-1", f"=D{i}/B{i}", f"=E{i}/C{i}", f"=(L{i}-M{i})*100", f"=G{i}/F{i}",
            f"=(O{i}-L{i})*100", f"=D{i}/G{i}", f"=B{i}/F{i}", f"=(Q{i}-R{i})*100", round(float(r.hhi)),
            f'=IF(K{i}>=0,IF(N{i}>=0,"Crescer junto","Defender"),IF(N{i}>=0,"Consolidar","Rever capacidade"))',
            f'=IF(P{i}>0.5,"Oferta > demanda: estimular ou ajustar capacidade",IF(P{i}<-0.5,"Ocupa acima do mercado: espaço p/ proteger tarifa","Equilibrado"))']
    for j, v in enumerate(vals, 1):
        c = ws.cell(row=i, column=j, value=v)
        c.border = THIN
        if isinstance(v, str) and v.startswith("="):
            c.fill = FORM
    for j in (2, 3, 4, 5, 6, 7, 20):
        ws.cell(row=i, column=j).number_format = NUM
    for j in (9, 10, 11, 12, 13, 15, 17, 18):
        ws.cell(row=i, column=j).number_format = PCT
    for j in (14, 16, 19):
        ws.cell(row=i, column=j).number_format = PP
last = 4 + len(mk)
for col in ("N", "P", "S"):
    ws.conditional_formatting.add(f"{col}5:{col}{last}", ColorScaleRule(
        start_type="min", start_color="F8696B", mid_type="num", mid_value=0, mid_color="FFFFFF",
        end_type="max", end_color="63BE7B"))
ws.auto_filter.ref = f"A4:V{last}"
ws.freeze_panes = "B5"
widths(ws, [11] + [13] * 6 + [8] + [10] * 12 + [16, 46])

# ---------------------------------------------------------------- Forecast
ws = wb.create_sheet("Forecast")
F = M["forecast"]
title(ws, "Forecast de passageiros no mercado doméstico regular",
      f"Modelo: {F['modelo']}. Faixa P10 a P90 calculada com os erros reais do backtest.")
header(ws, 4, ["Mês", "Realizado", "Previsão base", "P10", "P90"])
i = 5
for h in F["historico"]:
    ws.cell(row=i, column=1, value=pd.Timestamp(h["data"]).to_pydatetime()).number_format = "mmm/yy"
    ws.cell(row=i, column=2, value=h["pax"]).number_format = NUM
    i += 1
for p in F["prev"]:
    ws.cell(row=i, column=1, value=pd.Timestamp(p["data"]).to_pydatetime()).number_format = "mmm/yy"
    for j, k in enumerate(("base", "p10", "p90"), 3):
        ws.cell(row=i, column=j, value=p[k]).number_format = NUM
    i += 1
ch = LineChart()
ch.title, ch.height, ch.width = "Passageiros pagos / mês", 9, 22
ch.add_data(Reference(ws, min_col=2, max_col=5, min_row=4, max_row=i - 1), titles_from_data=True)
ch.set_categories(Reference(ws, min_col=1, min_row=5, max_row=i - 1))
ws.add_chart(ch, "G4")
widths(ws, [10, 14, 14, 14, 14])

# backtest
ws.cell(row=4, column=20, value="Backtest (rolante, horizonte de 1 a 6 meses)").font = Font(bold=True)
header(ws, 5, ["Modelo", "MAPE", "Viés"], start_col=20)
for k, (nome, v) in enumerate(M["backtest"]["modelos"].items(), start=6):
    ws.cell(row=k, column=20, value=nome + ("  ← escolhido" if nome == M["backtest"]["melhor"] else ""))
    ws.cell(row=k, column=21, value=v["mape"]).number_format = PCT
    ws.cell(row=k, column=22, value=v["vies"]).number_format = PCT
ws.column_dimensions["T"].width = 40

# ---------------------------------------------------------------- Cenários
ws = wb.create_sheet("Cenarios")
C = M["cenarios"]
title(ws, "Cenários 2027: passageiros da GOL no doméstico",
      "Altere as células amarelas. GOL 2027 = Mercado 2026 × (1 + crescimento) × share.")
ws["A4"], ws["B4"] = "Mercado 2025 (realizado)", C["mercado_2025"]
ws["A5"], ws["B5"] = "Mercado 2026 (realizado + previsão out a dez)", C["mercado_2026_est"]
ws["A6"], ws["B6"] = "GOL 2025 (realizado)", C["gol_2025"]
ws["A7"], ws["B7"] = "Share GOL últimos 12 meses", C["share_gol_12m"]
for r_ in (4, 5, 6):
    ws[f"B{r_}"].number_format = NUM
ws["B7"].number_format = PCT1
header(ws, 9, ["", "Pessimista", "Base", "Otimista"])
labels = ["Crescimento do mercado 2027", "Share GOL 2027", "Mercado 2027", "Passageiros GOL 2027",
          "vs GOL 2025", "Δ passageiros vs base"]
for k, lab in enumerate(labels, start=10):
    ws.cell(row=k, column=1, value=lab).font = Font(bold=True)
for j, nome in enumerate(["Pessimista", "Base", "Otimista"], start=2):
    col = get_column_letter(j)
    cc = C["cenarios"][nome]
    ws[f"{col}10"] = round(cc["cresc_mercado"], 4)
    ws[f"{col}11"] = round(cc["share"], 4)
    ws[f"{col}10"].fill = ws[f"{col}11"].fill = INFILL
    ws[f"{col}12"] = f"=$B$5*(1+{col}10)"
    ws[f"{col}13"] = f"={col}12*{col}11"
    ws[f"{col}14"] = f"={col}13/$B$6-1"
    ws[f"{col}15"] = f"={col}13-$C$13"
    for rr, fmt in ((10, PCT1), (11, PCT1), (12, NUM), (13, NUM), (14, PCT1), (15, NUM)):
        ws[f"{col}{rr}"].number_format = fmt

# matriz de sensibilidade: crescimento x share
ws["A18"] = "Sensibilidade: passageiros GOL 2027 (milhões)"
ws["A18"].font = Font(bold=True, size=12, color=AZUL_ESCURO)
ws["A19"] = "Cresc. mercado ↓ / Share GOL →"
shares = [-0.02, -0.01, 0, 0.01, 0.02]
growths = [-0.01, 0.01, 0.03, 0.05, 0.07, 0.09]
for j, s in enumerate(shares, start=2):
    c = ws.cell(row=19, column=j, value=f"=$B$7+{s}")
    c.number_format, c.font, c.fill = PCT1, H, HFILL
for i_, gr in enumerate(growths, start=20):
    c = ws.cell(row=i_, column=1, value=gr)
    c.number_format, c.font, c.fill = PCT1, H, HFILL
    for j in range(2, 2 + len(shares)):
        col = get_column_letter(j)
        ws.cell(row=i_, column=j, value=f"=$B$5*(1+$A{i_})*{col}$19/1000000").number_format = "0.0"
ws.conditional_formatting.add("B20:F25", ColorScaleRule(start_type="min", start_color="F8696B",
                              mid_type="percentile", mid_value=50, mid_color="FFFFFF",
                              end_type="max", end_color="63BE7B"))
widths(ws, [44, 16, 16, 16, 16, 16])

# ---------------------------------------------------------------- Test & Learn
ws = wb.create_sheet("Test_Learn")
title(ws, "Proposta de Test & Learn: preço e inventário em mercados com oferta acima da demanda",
      "Controle = mercado com sazonalidade mais parecida (correlação mensal de 2025 e 2026) e porte semelhante.")
header(ws, 4, ["Mercado teste", "Mercado controle", "Correlação", "Gap de oferta (pp)", "LF GOL teste", "LF mercado teste"])
for i, p in enumerate(M["test_learn"], start=5):
    for j, v in enumerate([p["teste"], p["controle"], p["correlacao"], p["gap_teste_pp"],
                           p["lf_gol_teste"], p["lf_mercado_teste"]], 1):
        c = ws.cell(row=i, column=j, value=v)
    ws.cell(row=i, column=3).number_format = "0.00"
    ws.cell(row=i, column=4).number_format = "0.0"
    ws.cell(row=i, column=5).number_format = ws.cell(row=i, column=6).number_format = PCT
desenho = [
    ("Hipótese", "Nos mercados teste, a GOL oferta mais assentos do que captura de demanda. Abrir mais classes tarifárias promocionais em dias/voos de menor ocupação aumenta o load factor sem derrubar a receita por voo."),
    ("Ação", "Ajuste de inventário (mais assentos nas classes mais baratas) só em voos de vale, por 6 a 8 semanas."),
    ("KPI principal", "Load factor do voo e receita por voo (RASK), comparando teste e controle antes e depois (diferença-em-diferenças)."),
    ("KPIs de guarda", "Share de passageiros no mercado, yield médio, ocupação dos voos de pico (não pode canibalizar)."),
    ("Critério de sucesso", "LF +2 pp vs controle sem queda de receita por voo. Se der certo, escala para os outros mercados com gap > 0,5 pp."),
]
for i, (k, v) in enumerate(desenho, start=9):
    ws.cell(row=i, column=1, value=k).font = Font(bold=True)
    ws.cell(row=i, column=2, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=6)
    ws.row_dimensions[i].height = 34
widths(ws, [18, 18, 14, 18, 14, 18])

path = OUT / "Radar_Mercado_Aereo.xlsx"
wb.save(path)
print("ok ->", path)
