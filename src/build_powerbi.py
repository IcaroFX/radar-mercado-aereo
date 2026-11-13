"""
Gera o projeto Power BI (formato PBIP: modelo em TMDL + relatório em PBIR) em powerbi/.

    powerbi/RadarMercadoAereo.pbip                 <- abra este arquivo no Power BI Desktop
    powerbi/RadarMercadoAereo.SemanticModel/       <- tabelas, relacionamentos e medidas DAX
    powerbi/RadarMercadoAereo.Report/              <- 5 páginas de relatório
    powerbi/dados/*.csv                            <- gerados por src/export_powerbi.py

Uso: python src/build_powerbi.py [--validar PASTA_DE_SCHEMAS]
"""
import json
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
NOME = "RadarMercadoAereo"
DADOS = str((PBI / "dados").resolve()) + "\\"
SM = PBI / f"{NOME}.SemanticModel"
RP = PBI / f"{NOME}.Report"
M = json.loads((ROOT / "out" / "metrics.json").read_text(encoding="utf-8"))
ULT_ANO, ULT_MES = int(M["ultimo_mes"][:4]), int(M["ultimo_mes"][5:])

GOL, LATAM, AZUL, OUTRAS = "#EB6834", "#1BAF7A", "#2A78D6", "#A3A199"
NAVY, INK, INK2, MUTED, BG, GRID = "#14213D", "#0B0B0B", "#52514E", "#898781", "#F4F3EF", "#E1E0D9"
VERDE, VERMELHO, AZUL_DIV = "#1E8E5A", "#E34948", "#256ABF"

gid = lambda: str(uuid.uuid4())
_seq = iter(range(1, 100000))
# nomes estáveis entre execuções: as mesmas pastas de página/visual são reaproveitadas
hexid = lambda: f"{next(_seq):04d}" + uuid.uuid5(uuid.NAMESPACE_URL, "radar").hex[:16]


def limpar(pasta: Path):
    """apaga arquivos (o OneDrive às vezes trava pastas; pastas vazias que sobrarem não atrapalham)."""
    for f in sorted(pasta.rglob("*"), key=lambda x: -len(x.parts)):
        try:
            f.unlink() if f.is_file() else f.rmdir()
        except OSError:
            pass


def w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def wj(path: Path, obj):
    w(path, json.dumps(obj, ensure_ascii=False, indent=2))


def q(name: str) -> str:
    """nome TMDL: aspas simples quando não for identificador simples."""
    return name if name.replace("_", "").isalnum() and name.isascii() else "'" + name.replace("'", "''") + "'"


# =====================================================================================
# 1. MODELO SEMÂNTICO (TMDL)
# =====================================================================================
def col_tmdl(name, dtype, fmt=None, summ="none", hidden=False, source=None, sort_by=None, extra=None):
    s = f"\tcolumn {q(name)}\n\t\tdataType: {dtype}\n"
    if fmt:
        s += f"\t\tformatString: {fmt}\n"
    if hidden:
        s += "\t\tisHidden\n"
    s += f"\t\tlineageTag: {gid()}\n\t\tsummarizeBy: {summ}\n\t\tsourceColumn: {source or name}\n"
    if sort_by:
        s += f"\t\tsortByColumn: {q(sort_by)}\n"
    for e in extra or []:
        s += f"\t\t{e}\n"
    return s + "\n\t\tannotation SummarizationSetBy = Automatic\n\n"


M_TYPE = {"string": "type text", "int64": "Int64.Type", "double": "type number", "dateTime": "type date"}


def csv_table(name, cols, hidden=False):
    """cols: lista de (nome, dataType, formatString, summarizeBy, oculto)"""
    s = f"table {q(name)}\n\tlineageTag: {gid()}\n"
    if hidden:
        s += "\tisHidden\n"
    s += "\n"
    for c in cols:
        n, t, fmt, summ, hid = (list(c) + [None, "none", False])[:5]
        s += col_tmdl(n, t, fmt, summ or "none", hid)
    tipos = ", ".join(f'{{"{c[0]}", {M_TYPE[c[1]]}}}' for c in cols)
    s += (f"\tpartition {q(name)} = m\n\t\tmode: import\n\t\tsource =\n"
          f"\t\t\t\tlet\n"
          f"\t\t\t\t    Fonte = Csv.Document(File.Contents(PastaDados & \"{name}.csv\"), [Delimiter = \",\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n"
          f"\t\t\t\t    Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),\n"
          f"\t\t\t\t    Tipos = Table.TransformColumnTypes(Cabecalho, {{{tipos}}}, \"en-US\")\n"
          f"\t\t\t\tin\n\t\t\t\t    Tipos\n\n"
          f"\tannotation PBI_ResultType = Table\n")
    return s


def calc_table(name, cols, dax, extra_cols_props=None):
    s = f"table {q(name)}\n\tlineageTag: {gid()}\n\n"
    for c in cols:
        n, t, fmt = c[0], c[1], c[2]
        kw = c[3] if len(c) > 3 else {}
        s += col_tmdl(n, t, fmt, kw.get("summ", "none"), kw.get("hidden", False), f"[{n}]", kw.get("sort_by"), kw.get("extra"))
    s += f"\tpartition {q(name)} = calculated\n\t\tmode: import\n\t\tsource = ```\n"
    s += "".join(f"\t\t\t\t{ln}\n" for ln in dax.strip("\n").split("\n"))
    s += "\t\t\t\t```\n\n\tannotation PBI_Id = " + uuid.uuid4().hex + "\n"
    return s


MEDIDAS = []  # (pasta, nome, dax, formato)


def med(pasta, nome, dax, fmt=None):
    MEDIDAS.append((pasta, nome, dax.strip("\n"), fmt))


PCT, PCT_S, PP, INT, MI = "0.0%", '+0.0%;-0.0%;0.0%', '+0.0" pp";-0.0" pp";0.0" pp"', "#,0", '0.0" mi"'
PCT_S = "+0.0%;-0.0%;0.0%"

# ---- volume
med("1. Volume", "Passageiros", "SUM ( fVoos[Passageiros] )", INT)
med("1. Volume", "Passageiros (mi)", "DIVIDE ( [Passageiros], 1000000 )", '0.0" mi"')
med("1. Volume", "Assentos", "SUM ( fVoos[Assentos] )", INT)
med("1. Volume", "ASK", "SUM ( fVoos[ASK] )", INT)
med("1. Volume", "RPK", "SUM ( fVoos[RPK] )", INT)
med("1. Volume", "Decolagens", "SUM ( fVoos[Decolagens] )", INT)
med("1. Volume", "Último mês com dados", "CALCULATE ( MAX ( fVoos[Data] ), REMOVEFILTERS () )", "mmm/yyyy")
# ---- ano anterior
for base in ["Passageiros", "Assentos", "ASK", "RPK"]:
    med("2. Ano anterior", f"{base} AA", f"CALCULATE ( [{base}], SAMEPERIODLASTYEAR ( dCalendario[Data] ) )", INT)
med("2. Ano anterior", "Cresc. Passageiros", "DIVIDE ( [Passageiros] - [Passageiros AA], [Passageiros AA] )", PCT_S)
med("2. Ano anterior", "Cresc. ASK", "DIVIDE ( [ASK] - [ASK AA], [ASK AA] )", PCT_S)
med("2. Ano anterior", "Cresc. RPK", "DIVIDE ( [RPK] - [RPK AA], [RPK AA] )", PCT_S)
# ---- eficiência
med("3. Ocupação", "Load Factor", "DIVIDE ( [RPK], [ASK] )", PCT)
med("3. Ocupação", "Load Factor AA", "DIVIDE ( [RPK AA], [ASK AA] )", PCT)
med("3. Ocupação", "Var. Load Factor (pp)", "IF ( NOT ISBLANK ( [Load Factor AA] ), ( [Load Factor] - [Load Factor AA] ) * 100 )", PP)
med("3. Ocupação", "Ocupação (pax/assento)", "DIVIDE ( [Passageiros], [Assentos] )", PCT)
# ---- share
med("4. Share", "Share RPK", "DIVIDE ( [RPK], CALCULATE ( [RPK], REMOVEFILTERS ( dCia ) ) )", PCT)
med("4. Share", "Share RPK AA", "DIVIDE ( [RPK AA], CALCULATE ( [RPK AA], REMOVEFILTERS ( dCia ) ) )", PCT)
med("4. Share", "Var. Share RPK (pp)", "IF ( NOT ISBLANK ( [Share RPK AA] ), ( [Share RPK] - [Share RPK AA] ) * 100 )", PP)
med("4. Share", "Share RPK 12m", """
VAR fim = MAX ( dCalendario[Data] )
VAR periodo = DATESINPERIOD ( dCalendario[Data], fim, -12, MONTH )
RETURN
    IF (
        fim >= DATE ( 2019, 12, 1 ) && fim <= EOMONTH ( [Último mês com dados], 0 ),
        DIVIDE ( CALCULATE ( [RPK], periodo ), CALCULATE ( [RPK], periodo, REMOVEFILTERS ( dCia ) ) )
    )""", PCT)
med("4. Share", "Share Passageiros", "DIVIDE ( [Passageiros], CALCULATE ( [Passageiros], REMOVEFILTERS ( dCia ) ) )", PCT)
med("4. Share", "Load Factor mensal", """
VAR fim = MAX ( dCalendario[Data] )
RETURN IF ( fim <= EOMONTH ( [Último mês com dados], 0 ), [Load Factor] )""", PCT)
# ---- GOL
med("5. GOL", "Passageiros GOL", 'CALCULATE ( [Passageiros], dCia[Cia] = "GOL" )', INT)
med("5. GOL", "Share RPK GOL", 'CALCULATE ( [Share RPK], dCia[Cia] = "GOL" )', PCT)
med("5. GOL", "Var. Share RPK GOL (pp)", 'CALCULATE ( [Var. Share RPK (pp)], dCia[Cia] = "GOL" )', PP)
med("5. GOL", "Cresc. ASK GOL", 'CALCULATE ( [Cresc. ASK], dCia[Cia] = "GOL" )', PCT_S)
med("5. GOL", "Cresc. Passageiros GOL", 'CALCULATE ( [Cresc. Passageiros], dCia[Cia] = "GOL" )', PCT_S)
med("5. GOL", "Share GOL", 'DIVIDE ( [Passageiros GOL], CALCULATE ( [Passageiros], REMOVEFILTERS ( dCia ) ) )', PCT)
med("5. GOL", "Share GOL AA", 'DIVIDE ( CALCULATE ( [Passageiros AA], dCia[Cia] = "GOL" ), CALCULATE ( [Passageiros AA], REMOVEFILTERS ( dCia ) ) )', PCT)
med("5. GOL", "Var. Share GOL (pp)", "IF ( NOT ISBLANK ( [Share GOL AA] ) && NOT ISBLANK ( [Share GOL] ), ( [Share GOL] - [Share GOL AA] ) * 100 )", PP)
med("5. GOL", "Share Assentos GOL", 'DIVIDE ( CALCULATE ( [Assentos], dCia[Cia] = "GOL" ), CALCULATE ( [Assentos], REMOVEFILTERS ( dCia ) ) )', PCT)
med("5. GOL", "Gap de Oferta GOL (pp)", "IF ( NOT ISBLANK ( [Passageiros GOL] ), ( [Share Assentos GOL] - [Share GOL] ) * 100 )", PP)
med("5. GOL", "LF GOL", 'DIVIDE ( [Passageiros GOL], CALCULATE ( [Assentos], dCia[Cia] = "GOL" ) )', PCT)
med("5. GOL", "LF Mercado", "DIVIDE ( CALCULATE ( [Passageiros], REMOVEFILTERS ( dCia ) ), CALCULATE ( [Assentos], REMOVEFILTERS ( dCia ) ) )", PCT)
med("5. GOL", "LF GOL vs Mercado (pp)", "IF ( NOT ISBLANK ( [LF GOL] ), ( [LF GOL] - [LF Mercado] ) * 100 )", PP)
# ---- mercados
med("6. Mercados", "Passageiros Mercado", "CALCULATE ( [Passageiros], REMOVEFILTERS ( dCia ) )", INT)
med("6. Mercados", "Cresc. Mercado", "CALCULATE ( [Cresc. Passageiros], REMOVEFILTERS ( dCia ) )", PCT_S)
med("6. Mercados", "HHI", """
VAR total = [Passageiros Mercado]
RETURN
    IF (
        total > 0,
        SUMX ( ALL ( dCia[Cia] ), VAR p = CALCULATE ( [Passageiros] ) RETURN DIVIDE ( p, total ) ^ 2 ) * 10000
    )""", INT)
med("6. Mercados", "Líder", """
VAR t = ADDCOLUMNS ( ALL ( dCia[Cia] ), "@pax", CALCULATE ( [Passageiros] ) )
RETURN IF ( [Passageiros Mercado] > 0, MAXX ( TOPN ( 1, t, [@pax], DESC ), dCia[Cia] ) )""")
med("6. Mercados", "Quadrante GOL", """
VAR c = [Cresc. Mercado]
VAR d = [Var. Share GOL (pp)]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( d ) || ISBLANK ( c ), BLANK (),
        c >= 0 && d >= 0, "Crescer junto",
        c >= 0, "Defender",
        d >= 0, "Consolidar",
        "Rever capacidade"
    )""")
med("6. Mercados", "Leitura do gap", """
VAR g = [Gap de Oferta GOL (pp)]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( g ), BLANK (),
        g > 0.5, "Oferta acima da demanda: estimular venda ou ajustar capacidade",
        g < -0.5, "Ocupa acima do mercado: espaço para proteger tarifa",
        "Equilibrado"
    )""")
med("6. Mercados", "Mercados a defender", """
COUNTROWS ( FILTER ( VALUES ( dMercado[Mercado] ), [Quadrante GOL] = "Defender" ) )""", INT)
# ---- cores (formatação condicional)
med("9. Cores", "Cor Cia", f"""
SWITCH ( SELECTEDVALUE ( dCia[Cia] ), "GOL", "{GOL}", "LATAM", "{LATAM}", "Azul", "{AZUL}", "{OUTRAS}" )""")
med("9. Cores", "Cor Gap", f'IF ( [Gap de Oferta GOL (pp)] > 0, "{VERMELHO}", "{AZUL_DIV}" )')
med("9. Cores", "Cor Quadrante", f"""
SWITCH ( [Quadrante GOL], "Crescer junto", "{VERDE}", "Defender", "{VERMELHO}", "Consolidar", "{AZUL_DIV}", "Rever capacidade", "#EDA100", "{MUTED}" )""")
med("9. Cores", "Cor Ano", f"""
IF ( SELECTEDVALUE ( dCalendario[Ano] ) = YEAR ( [Último mês com dados] ), "{GOL}", "#C9C7BF" )""")
med("9. Cores", "Fundo Var. Share", """
VAR d = [Var. Share GOL (pp)]
RETURN SWITCH ( TRUE (), ISBLANK ( d ), BLANK (), d >= 1, "#CFEBDC", d > 0, "#EAF6EF", d <= -1, "#F9D3D2", "#FDECEC" )""")
med("9. Cores", "Fundo Gap", """
VAR g = [Gap de Oferta GOL (pp)]
RETURN SWITCH ( TRUE (), ISBLANK ( g ), BLANK (), g > 0.5, "#F9D3D2", g < -0.5, "#D6E4F5", "#FFFFFF" )""")
# ---- insights (texto dinâmico)
med("7. Insights", "Insight Mercado", """
VAR cp = [Cresc. Passageiros]
VAR ca = [Cresc. ASK]
VAR dlf = [Var. Load Factor (pp)]
RETURN
    IF (
        ISBLANK ( cp ),
        "Selecione um ano com dados do ano anterior para ver a comparação.",
        FORMAT ( [Passageiros (mi)], "0.0" ) & " milhões de passageiros, " & FORMAT ( cp, "+0.0%;-0.0%" )
            & " sobre o mesmo período do ano anterior. A oferta (ASK) variou " & FORMAT ( ca, "+0.0%;-0.0%" )
            & IF (
                dlf < 0,
                ", acima da demanda, e a ocupação caiu " & FORMAT ( ABS ( dlf ), "0.0" ) & " pp.",
                " e a ocupação subiu " & FORMAT ( dlf, "0.0" ) & " pp."
            )
    )""")
med("7. Insights", "Insight Share", """
VAR t = ADDCOLUMNS ( FILTER ( ALL ( dCia[Cia] ), dCia[Cia] <> "Outras" ), "@d", CALCULATE ( [Var. Share RPK (pp)] ) )
VAR ganhou = MAXX ( TOPN ( 1, t, [@d], DESC ), dCia[Cia] )
VAR perdeu = MAXX ( TOPN ( 1, t, [@d], ASC ), dCia[Cia] )
RETURN
    IF (
        ISBLANK ( [Var. Share RPK GOL (pp)] ),
        BLANK (),
        "A GOL tem " & FORMAT ( [Share RPK GOL], "0.0%" ) & " de share em RPK (" & FORMAT ( [Var. Share RPK GOL (pp)], "+0.0;-0.0" )
            & " pp). Quem mais ganhou espaço foi a " & ganhou & " (" & FORMAT ( MAXX ( t, [@d] ), "+0.0;-0.0" )
            & " pp) e quem mais perdeu foi a " & perdeu & " (" & FORMAT ( MINX ( t, [@d] ), "+0.0;-0.0" ) & " pp)."
    )""")
med("7. Insights", "Insight GOL", """
VAR ca = [Cresc. ASK GOL]
VAR cp = [Cresc. Passageiros GOL]
RETURN
    IF (
        ISBLANK ( cp ),
        BLANK (),
        "A GOL aumentou a oferta em " & FORMAT ( ca, "+0.0%;-0.0%" ) & " e os passageiros em " & FORMAT ( cp, "+0.0%;-0.0%" ) & ". "
            & IF (
                ca > cp,
                "Parte dos assentos novos ainda não foi preenchida, então o foco passa a ser ocupação e preço por voo.",
                "A demanda acompanhou a oferta e a ocupação se manteve."
            )
    )""")
med("7. Insights", "Insight Mercados", """
VAR t =
    ADDCOLUMNS (
        FILTER ( VALUES ( dMercado[Mercado] ), NOT ISBLANK ( [Passageiros GOL] ) ),
        "@gap", [Gap de Oferta GOL (pp)],
        "@d", [Var. Share GOL (pp)],
        "@q", [Quadrante GOL]
    )
VAR n = COUNTROWS ( t )
VAR nDef = COUNTROWS ( FILTER ( t, [@q] = "Defender" ) )
VAR mGap = MAXX ( TOPN ( 1, t, [@gap], DESC ), dMercado[Mercado] )
VAR mOcupa = MAXX ( TOPN ( 1, t, [@gap], ASC ), dMercado[Mercado] )
VAR mGanho = MAXX ( TOPN ( 1, t, [@d], DESC ), dMercado[Mercado] )
RETURN
    IF (
        n = 0,
        BLANK (),
        "Em " & nDef & " de " & n & " mercados, o mercado cresce e a GOL perde share. O maior gap de oferta está em " & mGap
            & " (" & FORMAT ( MAXX ( t, [@gap] ), "+0.0;-0.0" ) & " pp). Em " & mOcupa
            & ", a GOL ocupa mais que o mercado. O maior ganho de share foi em " & mGanho & "."
    )""")
# ---- forecast e cenários
med("8. Forecast", "Realizado", "SUM ( fForecast[Realizado] )", INT)
med("8. Forecast", "Previsão", "SUM ( fForecast[Previsao] )", INT)
med("8. Forecast", "Previsão P10", "SUM ( fForecast[P10] )", INT)
med("8. Forecast", "Previsão P90", "SUM ( fForecast[P90] )", INT)
med("8. Forecast", "MAPE do modelo escolhido", 'CALCULATE ( MAX ( fBacktest[MAPE] ), fBacktest[Escolhido] = "Sim" )', PCT)
med("8. Forecast", "Mercado previsto 2027", "CALCULATE ( SUM ( fForecast[Previsao] ), FILTER ( ALL ( fForecast ), YEAR ( fForecast[Data] ) = 2027 ) )", INT)
med("8. Forecast", "Premissa crescimento", "SELECTEDVALUE ( 'Cenário crescimento'[Crescimento 2027], MAX ( fPremissas[CrescBase2027] ) )", PCT_S)
med("8. Forecast", "Premissa share GOL", "SELECTEDVALUE ( 'Cenário share'[Share GOL 2027], MAX ( fPremissas[Share12m] ) )", PCT)
med("8. Forecast", "Mercado 2027 (cenário)", "MAX ( fPremissas[Mercado2026Est] ) * ( 1 + [Premissa crescimento] ) / 1000000", MI)
med("8. Forecast", "GOL 2027 (cenário)", "[Mercado 2027 (cenário)] * [Premissa share GOL]", MI)
med("8. Forecast", "GOL 2027 vs 2025", "DIVIDE ( [GOL 2027 (cenário)] * 1000000, MAX ( fPremissas[GOL2025] ) ) - 1", PCT_S)
med("8. Forecast", "GOL 2027 vs cenário base", """
VAR base = MAX ( fPremissas[Mercado2026Est] ) * ( 1 + MAX ( fPremissas[CrescBase2027] ) ) * MAX ( fPremissas[Share12m] ) / 1000000
RETURN [GOL 2027 (cenário)] - base""", '+0.0" mi";-0.0" mi";0.0" mi"')
med("7. Insights", "Insight Forecast", """
"O modelo escolhido errou em média " & FORMAT ( [MAPE do modelo escolhido], "0.0%" )
    & " no backtest (1 a 6 meses à frente). Para 2027, ele projeta " & FORMAT ( [Mercado previsto 2027] / 1000000, "0.0" )
    & " milhões de passageiros no doméstico. Mexa nas premissas abaixo para ver o efeito na GOL."
""")
med("8. Forecast", "Índice de passageiros", """
VAR media =
    DIVIDE (
        CALCULATE ( [Passageiros], ALLSELECTED ( dCalendario ) ),
        CALCULATE ( DISTINCTCOUNT ( fVoos[Data] ), ALLSELECTED ( dCalendario ) )
    )
RETURN DIVIDE ( [Passageiros], media ) * 100""", "0")


def medidas_tmdl():
    s = f"table _Medidas\n\tlineageTag: {gid()}\n\n"
    for pasta, nome, dax, fmt in MEDIDAS:
        linhas = dax.split("\n")
        if len(linhas) == 1:
            s += f"\tmeasure {q(nome)} = {dax}\n"
        else:
            s += f"\tmeasure {q(nome)} =\n" + "".join(f"\t\t\t{ln}\n" for ln in linhas)
        if fmt:
            s += f"\t\tformatString: {fmt}\n"
        s += f"\t\tdisplayFolder: {pasta}\n\t\tlineageTag: {gid()}\n\n"
    s += col_tmdl("Coluna", "string", hidden=True)
    s += ("\tpartition _Medidas = m\n\t\tmode: import\n\t\tsource =\n"
          "\t\t\t\tlet\n\t\t\t\t    Fonte = #table(type table [Coluna = text], {})\n\t\t\t\tin\n\t\t\t\t    Fonte\n\n"
          "\tannotation PBI_ResultType = Table\n")
    return s


def build_model():
    d = SM / "definition"
    wj(SM / "definition.pbism", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
                                 "version": "4.2", "settings": {}})
    wj(SM / ".platform", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                          "metadata": {"type": "SemanticModel", "displayName": NOME},
                          "config": {"version": "2.0", "logicalId": gid()}})
    w(d / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n\n")
    tabelas = ["_Medidas", "fVoos", "dCalendario", "dCia", "dMercado", "dAeroporto", "fForecast", "fBacktest",
               "fCenarios", "fPremissas", "fTestLearn", "Cenário crescimento", "Cenário share"]
    w(d / "model.tmdl",
      "model Model\n\tculture: pt-BR\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: pt-BR\n"
      "\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
      "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
      f"annotation PBI_QueryOrder = {json.dumps(['PastaDados'] + [t for t in tabelas if not t.startswith(('dCal', 'Cen'))], ensure_ascii=False)}\n\n"
      + "".join(f"ref table {q(t)}\n" for t in tabelas))
    w(d / "expressions.tmdl",
      f'expression PastaDados = "{DADOS}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
      f"\tlineageTag: {gid()}\n\n\tannotation PBI_ResultType = Text\n\n\tannotation PBI_NavigationStepName = Navigation\n")
    t = d / "tables"
    w(t / "_Medidas.tmdl", medidas_tmdl())
    w(t / "fVoos.tmdl", csv_table("fVoos", [
        ("Data", "dateTime", "dd/mm/yyyy", "none", True), ("Cia", "string", None, "none", True), ("Empresa", "string"),
        ("Origem", "string", None, "none", True), ("Destino", "string"), ("Mercado", "string", None, "none", True),
        ("Passageiros", "int64", INT, "sum"), ("ASK", "int64", INT, "sum"), ("RPK", "int64", INT, "sum"),
        ("Assentos", "int64", INT, "sum"), ("Decolagens", "int64", INT, "sum"), ("DistanciaKm", "int64", INT, "sum")]))
    w(t / "dCia.tmdl", csv_table("dCia", [("Cia", "string"), ("Ordem", "int64", "0"), ("Cor", "string")]))
    w(t / "dAeroporto.tmdl", csv_table("dAeroporto", [("Aeroporto", "string"), ("Nome", "string"), ("UF", "string"),
                                                      ("Regiao", "string"), ("Cidade", "string")]))
    w(t / "dMercado.tmdl", csv_table("dMercado", [
        ("Mercado", "string"), ("Cidade A", "string"), ("Cidade B", "string"), ("UF A", "string"), ("Região A", "string"),
        ("UF B", "string"), ("Região B", "string"), ("Tipo", "string"), ("Conecta SAO", "string"),
        ("Distância média (km)", "double", "#,0"), ("Faixa de distância", "string"), ("Top 25 GOL", "string"),
        ("Quadrante GOL (jan a set 26)", "string")]))
    w(t / "fForecast.tmdl", csv_table("fForecast", [("Data", "dateTime", "mmm/yy"), ("Realizado", "double", INT, "sum"),
                                                    ("Previsao", "double", INT, "sum"), ("P10", "double", INT, "sum"),
                                                    ("P90", "double", INT, "sum")]))
    w(t / "fBacktest.tmdl", csv_table("fBacktest", [("Modelo", "string"), ("MAPE", "double", PCT, "none"),
                                                    ("Vies", "double", PCT_S, "none"), ("Escolhido", "string")]))
    w(t / "fCenarios.tmdl", csv_table("fCenarios", [("Cenario", "string"), ("Ordem", "int64", "0"),
                                                    ("Crescimento", "double", PCT_S), ("Share", "double", PCT),
                                                    ("Mercado2027", "double", MI), ("GOL2027", "double", MI),
                                                    ("VsGOL2025", "double", PCT_S)]))
    w(t / "fPremissas.tmdl", csv_table("fPremissas", [("Mercado2025", "double", INT), ("Mercado2026Est", "double", INT),
                                                      ("GOL2025", "double", INT), ("Share12m", "double", PCT),
                                                      ("CrescBase2027", "double", PCT_S)], hidden=True))
    w(t / "fTestLearn.tmdl", csv_table("fTestLearn", [("Teste", "string"), ("Controle", "string"),
                                                      ("Correlacao", "double", "0.00"), ("GapOfertaPP", "double", "+0.0;-0.0"),
                                                      ("LFGOLTeste", "double", PCT), ("LFMercadoTeste", "double", PCT)]))
    w(t / "dCalendario.tmdl", calc_table("dCalendario", [
        ("Data", "dateTime", "dd/mm/yyyy", {"extra": ["isKey"]}),
        ("Ano", "int64", "0"),
        ("Mês Num", "int64", "0", {"hidden": True}),
        ("Mês", "string", None, {"sort_by": "Mês Num"}),
        ("Início do mês", "dateTime", "mmm/yy"),
        ("AnoMes", "int64", "0", {"hidden": True}),
        ("Mês/Ano", "string", None, {"sort_by": "AnoMes"}),
    ], """
VAR base = SELECTCOLUMNS ( CALENDAR ( DATE ( 2019, 1, 1 ), DATE ( 2027, 12, 31 ) ), "Data", [Date] )
VAR nomes = "janfevmarabrmaijunjulagosetoutnovdez"
RETURN
    ADDCOLUMNS (
        base,
        "Ano", YEAR ( [Data] ),
        "Mês Num", MONTH ( [Data] ),
        "Mês", MID ( nomes, ( MONTH ( [Data] ) - 1 ) * 3 + 1, 3 ),
        "Início do mês", DATE ( YEAR ( [Data] ), MONTH ( [Data] ), 1 ),
        "AnoMes", YEAR ( [Data] ) * 100 + MONTH ( [Data] ),
        "Mês/Ano", MID ( nomes, ( MONTH ( [Data] ) - 1 ) * 3 + 1, 3 ) & "/" & RIGHT ( YEAR ( [Data] ), 2 )
    )""").replace("table dCalendario\n", "table dCalendario\n\tdataCategory: Time\n", 1))
    w(t / "Cenário crescimento.tmdl", calc_table("Cenário crescimento", [("Crescimento 2027", "double", PCT_S)],
        'SELECTCOLUMNS ( GENERATESERIES ( -0.02, 0.12, 0.005 ), "Crescimento 2027", ROUND ( [Value], 3 ) )'))
    w(t / "Cenário share.tmdl", calc_table("Cenário share", [("Share GOL 2027", "double", PCT)],
        'SELECTCOLUMNS ( GENERATESERIES ( 0.27, 0.37, 0.005 ), "Share GOL 2027", ROUND ( [Value], 3 ) )'))
    rel = lambda a, b: f"relationship {gid()}\n\tfromColumn: {a}\n\ttoColumn: {b}\n\n"
    w(d / "relationships.tmdl",
      rel("fVoos.Data", "dCalendario.Data") + rel("fVoos.Cia", "dCia.Cia") + rel("fVoos.Mercado", "dMercado.Mercado")
      + rel("fVoos.Origem", "dAeroporto.Aeroporto"))


# =====================================================================================
# 2. RELATÓRIO (PBIR)
# =====================================================================================
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
V_VIS, V_PAGE, V_REP = "2.4.0", "2.0.0", "3.0.0"


def lit(v):
    if isinstance(v, bool):
        val = "true" if v else "false"
    elif isinstance(v, int):
        val = f"{v}L"
    elif isinstance(v, float):
        val = f"{v}D"
    else:
        val = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": val}}}


def num(v):
    return {"expr": {"Literal": {"Value": f"{v}D"}}}


def color(c):
    return {"solid": {"color": lit(c)}}


def C(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def MS(prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Medidas"}}, "Property": prop}}


def color_measure(prop):
    return {"solid": {"color": {"expr": MS(prop)}}}


def P(field, label=None):
    kind = "Column" if "Column" in field else "Measure"
    ent, prop = field[kind]["Expression"]["SourceRef"]["Entity"], field[kind]["Property"]
    p = {"field": field, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if label:
        p["displayName"] = label
    return p


def ref(field):
    kind = "Column" if "Column" in field else "Measure"
    return f"{field[kind]['Expression']['SourceRef']['Entity']}.{field[kind]['Property']}"


def filtro_in(entity, prop, valores, nome=None):
    vals = [[{"Literal": {"Value": (f"{v}L" if isinstance(v, int) else "'" + v + "'")}}] for v in valores]
    return {"name": nome or hexid(), "field": C(entity, prop), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "x", "Entity": entity, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [
                           {"Column": {"Expression": {"SourceRef": {"Source": "x"}}, "Property": prop}}],
                           "Values": vals}}}]}}


def container_objs(title=None, subtitle=None, bg=None, border=True, pad=None):
    o = {}
    if title:
        o["title"] = [{"properties": {"show": lit(True), "text": lit(title), "fontSize": num(12),
                                      "fontColor": color(INK), "bold": lit(True)}}]
    else:
        o["title"] = [{"properties": {"show": lit(False)}}]
    if subtitle:
        o["subTitle"] = [{"properties": {"show": lit(True), "text": lit(subtitle), "fontSize": num(9),
                                         "fontColor": color(MUTED)}}]
    o["background"] = [{"properties": {"show": lit(True), "color": color(bg or "#FFFFFF"), "transparency": num(0)}}]
    o["border"] = [{"properties": {"show": lit(border), "color": color(GRID), "radius": num(10)}}]
    o["dropShadow"] = [{"properties": {"show": lit(False)}}]
    if pad is not None:
        o["padding"] = [{"properties": {"top": num(pad), "bottom": num(pad), "left": num(pad), "right": num(pad)}}]
    return o


class Page:
    def __init__(self, name, display):
        self.name, self.display, self.visuals, self.inter = name, display, [], []

    def add(self, vtype, x, y, wd, ht, roles=None, objects=None, title=None, subtitle=None, sort=None,
            filters=None, bg=None, border=True, pad=None, name=None):
        v = {"$schema": f"{SCH}/visualContainer/{V_VIS}/schema.json", "name": name or hexid(),
             "position": {"x": x, "y": y, "z": len(self.visuals) * 1000, "width": wd, "height": ht,
                          "tabOrder": len(self.visuals) * 1000},
             "visual": {"visualType": vtype}}
        if roles:
            v["visual"]["query"] = {"queryState": {r: {"projections": ps} for r, ps in roles.items()}}
            if sort:
                v["visual"]["query"]["sortDefinition"] = {"sort": [{"field": f, "direction": d} for f, d in sort],
                                                          "isDefaultSort": False}
        if objects:
            v["visual"]["objects"] = objects
        v["visual"]["visualContainerObjects"] = container_objs(title, subtitle, bg, border, pad)
        v["visual"]["drillFilterOtherVisuals"] = True
        if filters:
            v["filterConfig"] = {"filters": filters}
        self.visuals.append(v)
        return v["name"]

    def no_filter(self, src, targets):
        self.inter += [{"source": src, "target": t, "type": "NoFilter"} for t in targets]


def textbox(page, x, y, wd, ht, paragraphs, bg=None, border=False, pad=None):
    """paragraphs: lista de lista de (texto, tamanho, negrito, cor)"""
    paras = []
    for runs in paragraphs:
        paras.append({"textRuns": [{"value": t, "textStyle": {"fontSize": f"{sz}pt", "fontWeight": "bold" if b else "normal",
                                                              "color": cor, "fontFamily": "Segoe UI"}}
                                   for t, sz, b, cor in runs]})
    return page.add("textbox", x, y, wd, ht, objects={"general": [{"properties": {"paragraphs": paras}}]},
                    bg=bg or "#FFFFFF", border=border, pad=pad)


def header(page, titulo, sub):
    textbox(page, 0, 0, 1280, 64, [[(titulo, 15, True, "#FFFFFF")], [(sub, 9, False, "#C9C7BF")]], bg=NAVY, pad=4)


def card(page, x, y, wd, ht, measure, label, size=24, title=None):
    return page.add("card", x, y, wd, ht, roles={"Values": [P(MS(measure), label)]},
                    objects={"labels": [{"properties": {"fontSize": num(size), "color": color(INK), "labelDisplayUnits": num(1),
                                                        "fontFamily": lit("Segoe UI Semibold")}}],
                             "categoryLabels": [{"properties": {"show": lit(True), "fontSize": num(10), "color": color(INK2)}}]},
                    title=title)


def text_card(page, x, y, wd, ht, measure, accent=GOL, filters=None):
    return page.add("card", x, y, wd, ht, roles={"Values": [P(MS(measure))]}, filters=filters,
                    objects={"labels": [{"properties": {"fontSize": num(10), "color": color(INK), "fontFamily": lit("Segoe UI")}}],
                             "categoryLabels": [{"properties": {"show": lit(False)}}],
                             "wordWrap": [{"properties": {"show": lit(True)}}]},
                    bg="#FDF0EA", border=False, pad=8)


def slicer(page, x, y, wd, ht, field, title, mode="Dropdown", single=False, default=None, horizontal=False):
    objs = {"data": [{"properties": {"mode": lit(mode)}}],
            "selection": [{"properties": {"singleSelect": lit(single)}}],
            "header": [{"properties": {"show": lit(True), "fontColor": color(INK2), "textSize": num(9)}}],
            "items": [{"properties": {"textSize": num(10)}}]}
    if horizontal:
        objs["general"] = [{"properties": {"orientation": num(1)}}]
    if default is not None:
        ent, prop = field["Column"]["Expression"]["SourceRef"]["Entity"], field["Column"]["Property"]
        f = filtro_in(ent, prop, default)["filter"]
        objs.setdefault("general", [{"properties": {}}])
        objs["general"][0]["properties"]["filter"] = {"filter": f}
    return page.add("slicer", x, y, wd, ht, roles={"Values": [P(field)]}, objects=objs, pad=4)


def series_colors(entity, prop, cores):
    return [{"properties": {"fill": color(c)},
             "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": C(entity, prop),
                                                               "Right": {"Literal": {"Value": f"'{v}'"}}}}}]}}
            for v, c in cores.items()]


def measure_colors(cores):
    return [{"properties": {"fill": color(c)}, "selector": {"metadata": f"_Medidas.{m}"}} for m, c in cores.items()]


ANO, MES = C("dCalendario", "Ano"), C("dCalendario", "Mês")
MESES_DEF = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"][:ULT_MES]
CIA = C("dCia", "Cia")
MERC = C("dMercado", "Mercado")
TOP25 = lambda: filtro_in("dMercado", "Top 25 GOL", ["Sim"])
TRES_CIAS = lambda: filtro_in("dCia", "Cia", ["LATAM", "GOL", "Azul"])
AXIS = {"categoryAxis": [{"properties": {"fontSize": num(9), "labelColor": color(MUTED), "showAxisTitle": lit(False)}}],
        "valueAxis": [{"properties": {"fontSize": num(9), "labelColor": color(MUTED), "showAxisTitle": lit(False),
                                      "gridlineColor": color(GRID)}}],
        "legend": [{"properties": {"show": lit(True), "position": lit("Top"), "fontSize": num(9)}}]}


def periodo_slicers(page, x0=20, y=72):
    a = slicer(page, x0, y, 110, 56, ANO, "Ano", single=True, default=[ULT_ANO])
    m = slicer(page, x0 + 120, y, 640, 56, MES, "Mês", mode="Basic", default=MESES_DEF, horizontal=True)
    return a, m


pages = []

# ------------------------------------------------------------------- Página 1: Visão geral
p = Page(hexid(), "Visão geral")
header(p, "Radar Competitivo · Mercado aéreo doméstico", "Dados abertos da ANAC, voos domésticos regulares. Escolha o ano e os meses; tudo é comparado com o mesmo período do ano anterior.")
s1, s2 = periodo_slicers(p)
textbox(p, 790, 72, 470, 56, [[("Como ler: ", 9, True, INK2), ("share em RPK = passageiro-km pago; load factor = RPK ÷ ASK; pp = pontos percentuais.", 9, False, INK2)]], bg=BG)
cards = [("Passageiros (mi)", "Passageiros"), ("Cresc. Passageiros", "Crescimento de passageiros"), ("Cresc. ASK", "Crescimento da oferta (ASK)"),
         ("Load Factor", "Load factor"), ("Share RPK GOL", "Share RPK da GOL"), ("Var. Share RPK GOL (pp)", "Variação do share da GOL")]
for i, (m_, lab) in enumerate(cards):
    card(p, 20 + i * 208, 138, 198, 92, m_, lab)
text_card(p, 20, 240, 615, 70, "Insight Mercado")
text_card(p, 645, 240, 615, 70, "Insight Share")
lc = p.add("lineChart", 20, 320, 800, 390,
           roles={"Category": [P(C("dCalendario", "Início do mês"), "Mês")], "Y": [P(MS("Share RPK 12m"), "Share RPK (12 meses)")],
                  "Series": [P(CIA)]},
           objects={**AXIS, "dataPoint": series_colors("dCia", "Cia", {"GOL": GOL, "LATAM": LATAM, "Azul": AZUL}),
                    "lineStyles": [{"properties": {"strokeWidth": num(3)}}]},
           title="Market share em RPK por companhia", subtitle="Média móvel de 12 meses. Este gráfico mostra a série inteira e ignora os filtros de período.",
           filters=[TRES_CIAS()])
cc = p.add("clusteredColumnChart", 830, 320, 430, 390,
           roles={"Category": [P(ANO)], "Y": [P(MS("Passageiros (mi)"), "Passageiros (mi)")]},
           objects={**AXIS, "legend": [{"properties": {"show": lit(False)}}],
                    "dataPoint": [{"properties": {"fill": color_measure("Cor Ano")},
                                   "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
                    "labels": [{"properties": {"show": lit(True), "fontSize": num(9), "labelDisplayUnits": num(1), "labelPrecision": num(1)}}]},
           title="Passageiros nos meses selecionados, por ano", subtitle="Compara o mesmo recorte de meses em cada ano (milhões)",
           sort=[(ANO, "Ascending")])
p.no_filter(s1, [lc, cc])
p.no_filter(s2, [lc])
pages.append(p)

# ------------------------------------------------------------------- Página 2: Concorrência
p = Page(hexid(), "Concorrência")
header(p, "Concorrência · LATAM, GOL e Azul", "Share, crescimento e ocupação por companhia no período escolhido.")
s1, s2 = periodo_slicers(p)
text_card(p, 20, 136, 1240, 46, "Insight GOL")
b1 = p.add("clusteredColumnChart", 20, 190, 410, 280,
           roles={"Category": [P(CIA)], "Y": [P(MS("Share RPK AA"), "Ano anterior"), P(MS("Share RPK"), "Período atual")]},
           objects={**AXIS, "dataPoint": measure_colors({"Share RPK AA": "#C9C7BF", "Share RPK": GOL}),
                    "labels": [{"properties": {"show": lit(True), "fontSize": num(9)}}]},
           title="Share em RPK: período atual vs ano anterior", filters=[TRES_CIAS()], sort=[(MS("Share RPK"), "Descending")])
b2 = p.add("clusteredBarChart", 440, 190, 410, 280,
           roles={"Category": [P(CIA)], "Y": [P(MS("Cresc. ASK"), "Oferta (ASK)"), P(MS("Cresc. Passageiros"), "Passageiros")]},
           objects={**AXIS, "dataPoint": measure_colors({"Cresc. ASK": "#F5B89D", "Cresc. Passageiros": GOL}),
                    "labels": [{"properties": {"show": lit(True), "fontSize": num(9)}}]},
           title="Crescimento: oferta vs passageiros", subtitle="Quando a oferta cresce mais que os passageiros, a ocupação cai",
           filters=[TRES_CIAS()])
l2 = p.add("lineChart", 860, 190, 400, 280,
           roles={"Category": [P(C("dCalendario", "Início do mês"), "Mês")], "Y": [P(MS("Load Factor mensal"), "Load factor")],
                  "Series": [P(CIA)]},
           objects={**AXIS, "dataPoint": series_colors("dCia", "Cia", {"GOL": GOL, "LATAM": LATAM, "Azul": AZUL})},
           title="Load factor mensal", subtitle="Desde 2024; ignora os filtros de período",
           filters=[TRES_CIAS(), filtro_in("dCalendario", "Ano", [2024, 2025, 2026])])
t2 = p.add("tableEx", 20, 478, 1240, 232,
           roles={"Values": [P(CIA, "Companhia"), P(MS("Passageiros"), "Passageiros"), P(MS("Cresc. Passageiros"), "Cresc. pax"),
                             P(MS("ASK"), "ASK"), P(MS("Cresc. ASK"), "Cresc. ASK"), P(MS("Load Factor"), "Load factor"),
                             P(MS("Var. Load Factor (pp)"), "Var. LF"), P(MS("Share RPK"), "Share RPK"),
                             P(MS("Var. Share RPK (pp)"), "Var. share")]},
           objects={"columnHeaders": [{"properties": {"fontSize": num(10), "backColor": color(BG), "fontColor": color(INK2)}}],
                    "values": [{"properties": {"fontSize": num(11)}}]},
           title="Resumo por companhia", sort=[(MS("Passageiros"), "Descending")], filters=[TRES_CIAS()])
p.no_filter(s1, [l2])
p.no_filter(s2, [l2])
pages.append(p)

# ------------------------------------------------------------------- Página 3: Mercados da GOL
p = Page(hexid(), "Mercados da GOL")
header(p, "Mercados da GOL · onde ganha, onde perde e onde sobra assento", "Top 25 mercados (pares de cidades) da GOL em 2026. SAO = CGH+GRU+VCP; RIO = SDU+GIG; BHZ = CNF+PLU.")
s1, s2 = periodo_slicers(p)
slicer(p, 790, 72, 230, 56, C("dMercado", "Faixa de distância"), "Faixa de distância")
slicer(p, 1030, 72, 230, 56, C("dMercado", "Tipo"), "Tipo de mercado")
text_card(p, 20, 136, 1240, 50, "Insight Mercados", filters=[TOP25()])
sc = p.add("scatterChart", 20, 194, 700, 290,
           roles={"Category": [P(MERC)], "X": [P(MS("Cresc. Mercado"), "Crescimento do mercado")],
                  "Y": [P(MS("Var. Share GOL (pp)"), "Variação do share GOL (pp)")], "Size": [P(MS("Passageiros GOL"), "Passageiros GOL")]},
           objects={**AXIS, "categoryLabels": [{"properties": {"show": lit(True), "fontSize": num(8), "color": color(INK2)}}],
                    "dataPoint": [{"properties": {"fill": color_measure("Cor Quadrante")},
                                   "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
                    "legend": [{"properties": {"show": lit(False)}}]},
           title="Mapa de quadrantes", subtitle="Verde: crescer junto · Vermelho: defender · Azul: consolidar · Amarelo: rever capacidade",
           filters=[TOP25()])
gb = p.add("clusteredBarChart", 730, 194, 530, 516,
           roles={"Category": [P(MERC)], "Y": [P(MS("Gap de Oferta GOL (pp)"), "Gap de oferta (pp)")]},
           objects={**AXIS, "legend": [{"properties": {"show": lit(False)}}],
                    "dataPoint": [{"properties": {"fill": color_measure("Cor Gap")},
                                   "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
                    "labels": [{"properties": {"show": lit(True), "fontSize": num(8)}}]},
           title="Gap de oferta: share de assentos − share de passageiros da GOL",
           subtitle="Vermelho: oferta acima da demanda · Azul: ocupa acima do mercado",
           filters=[TOP25()], sort=[(MS("Gap de Oferta GOL (pp)"), "Descending")])
tb = p.add("tableEx", 20, 492, 700, 218,
           roles={"Values": [P(MERC), P(MS("Passageiros Mercado"), "Pax mercado"), P(MS("Cresc. Mercado"), "Cresc. mercado"),
                             P(MS("Share GOL"), "Share GOL"), P(MS("Var. Share GOL (pp)"), "Var. share"),
                             P(MS("Gap de Oferta GOL (pp)"), "Gap oferta"), P(MS("LF GOL vs Mercado (pp)"), "LF vs mercado"),
                             P(MS("HHI"), "HHI"), P(MS("Líder"), "Líder"), P(MS("Quadrante GOL"), "Quadrante")]},
           objects={"columnHeaders": [{"properties": {"fontSize": num(9), "backColor": color(BG), "fontColor": color(INK2)}}],
                    "total": [{"properties": {"totals": lit(False)}}],
                    "values": [{"properties": {"fontSize": num(9)}},
                               {"properties": {"backColor": color_measure("Fundo Var. Share")}, "selector": {"metadata": "_Medidas.Var. Share GOL (pp)"}},
                               {"properties": {"backColor": color_measure("Fundo Gap")}, "selector": {"metadata": "_Medidas.Gap de Oferta GOL (pp)"}}]},
           title="Detalhe dos mercados", filters=[TOP25()], sort=[(MS("Passageiros GOL"), "Descending")])
pages.append(p)

# ------------------------------------------------------------------- Página 4: Forecast e cenários
p = Page(hexid(), "Forecast e cenários")
header(p, "Forecast de demanda e cenários 2027", "Previsão do mercado doméstico com faixa de incerteza do backtest. Mude as premissas para simular os passageiros da GOL em 2027.")
text_card(p, 20, 72, 1240, 52, "Insight Forecast")
FD = C("fForecast", "Data")
fl = p.add("lineChart", 20, 130, 800, 330,
           roles={"Category": [P(FD, "Mês")], "Y": [P(MS("Realizado")), P(MS("Previsão")), P(MS("Previsão P10"), "P10"), P(MS("Previsão P90"), "P90")]},
           objects={**AXIS, "dataPoint": measure_colors({"Realizado": INK, "Previsão": GOL, "Previsão P10": "#F2A27F", "Previsão P90": "#F2A27F"}),
                    "lineStyles": [{"properties": {"strokeWidth": num(3)}, "selector": {"metadata": "_Medidas.Realizado"}},
                                   {"properties": {"strokeWidth": num(3), "lineStyle": lit("dashed")}, "selector": {"metadata": "_Medidas.Previsão"}},
                                   {"properties": {"strokeWidth": num(2), "lineStyle": lit("dotted")}, "selector": {"metadata": "_Medidas.Previsão P10"}},
                                   {"properties": {"strokeWidth": num(2), "lineStyle": lit("dotted")}, "selector": {"metadata": "_Medidas.Previsão P90"}}]},
           title="Passageiros por mês: realizado e previsão", subtitle="Faixa P10 a P90 calculada com os erros reais do backtest")
p.add("tableEx", 830, 130, 430, 330,
      roles={"Values": [P(C("fBacktest", "Modelo")), P(C("fBacktest", "MAPE"), "MAPE"), P(C("fBacktest", "Vies"), "Viés")]},
      objects={"columnHeaders": [{"properties": {"fontSize": num(10), "backColor": color(BG), "fontColor": color(INK2)}}],
               "values": [{"properties": {"fontSize": num(11)}}]},
      title="Backtest rolante: 4 modelos", subtitle="13 origens, horizonte de 1 a 6 meses. Viés negativo = prevê abaixo do realizado.",
      sort=[(C("fBacktest", "MAPE"), "Ascending")])
slicer(p, 20, 470, 250, 115, C("Cenário crescimento", "Crescimento 2027"), "Crescimento do mercado 2027 (vazio = base)", single=True)
slicer(p, 20, 595, 250, 115, C("Cenário share", "Share GOL 2027"), "Share da GOL 2027 (vazio = base)", single=True)
card(p, 280, 470, 250, 115, "GOL 2027 (cenário)", "Passageiros GOL 2027", 26)
card(p, 280, 595, 250, 115, "GOL 2027 vs 2025", "Variação sobre 2025", 26)
card(p, 540, 470, 250, 115, "Mercado 2027 (cenário)", "Mercado doméstico 2027", 22)
card(p, 540, 595, 250, 115, "GOL 2027 vs cenário base", "Diferença para o cenário base", 22)
p.add("tableEx", 800, 470, 460, 240,
      roles={"Values": [P(C("fCenarios", "Cenario"), "Cenário"), P(C("fCenarios", "Crescimento"), "Cresc. mercado"),
                        P(C("fCenarios", "Share"), "Share GOL"), P(C("fCenarios", "GOL2027"), "GOL 2027"),
                        P(C("fCenarios", "VsGOL2025"), "vs 2025")]},
      objects={"columnHeaders": [{"properties": {"fontSize": num(10), "backColor": color(BG), "fontColor": color(INK2)}}],
               "values": [{"properties": {"fontSize": num(11)}}]},
      title="Cenários de referência", subtitle="Pessimista: −3 pp de mercado e −1,5 pp de share. Otimista: +2 pp e +1,5 pp.",
      sort=[(C("fCenarios", "Ordem"), "Ascending")])
pages.append(p)

# ------------------------------------------------------------------- Página 5: Test & Learn
p = Page(hexid(), "Test & Learn")
header(p, "Test & Learn · proposta de teste de inventário", "Mercados de teste com ocupação da GOL abaixo do mercado, cada um com um mercado de controle de sazonalidade parecida.")
pares = [(x["teste"], x["controle"]) for x in M["test_learn"]]
merc_tl = [m_ for par in pares for m_ in par]
p.add("tableEx", 20, 72, 620, 130,
      roles={"Values": [P(C("fTestLearn", "Teste")), P(C("fTestLearn", "Controle")), P(C("fTestLearn", "Correlacao"), "Correlação sazonal"),
                        P(C("fTestLearn", "GapOfertaPP"), "Gap de oferta (pp)"), P(C("fTestLearn", "LFGOLTeste"), "LF GOL"),
                        P(C("fTestLearn", "LFMercadoTeste"), "LF mercado")]},
      objects={"columnHeaders": [{"properties": {"fontSize": num(10), "backColor": color(BG), "fontColor": color(INK2)}}],
               "values": [{"properties": {"fontSize": num(12)}}]},
      title="Pares teste e controle")
p.add("lineChart", 20, 212, 620, 300,
      roles={"Category": [P(C("dCalendario", "Início do mês"), "Mês")], "Y": [P(MS("Índice de passageiros"), "Índice (média = 100)")],
             "Series": [P(MERC)]},
      objects={**AXIS, "dataPoint": series_colors("dMercado", "Mercado", dict(zip(merc_tl, [GOL, "#B9B7AF", AZUL_DIV, "#8FB3E0"])))},
      title="Tendências paralelas: passageiros de teste e controle", subtitle="Índice mensal (média do período = 100), 2025 e 2026",
      filters=[filtro_in("dMercado", "Mercado", merc_tl), filtro_in("dCalendario", "Ano", [2025, 2026])])
p.add("clusteredColumnChart", 650, 72, 610, 300,
      roles={"Category": [P(MERC)], "Y": [P(MS("LF GOL"), "Ocupação GOL"), P(MS("LF Mercado"), "Ocupação do mercado")]},
      objects={**AXIS, "dataPoint": measure_colors({"LF GOL": GOL, "LF Mercado": "#C9C7BF"}),
               "labels": [{"properties": {"show": lit(True), "fontSize": num(9)}}]},
      title=f"Ocupação GOL vs mercado (jan a {MESES_DEF[-1]} {ULT_ANO})",
      filters=[filtro_in("dMercado", "Mercado", merc_tl), filtro_in("dCalendario", "Ano", [ULT_ANO]),
               filtro_in("dCalendario", "Mês", MESES_DEF)])
blocos = [("Hipótese", "Liberar mais assentos nas classes promocionais só nos voos de menor ocupação aumenta o load factor sem reduzir a receita por voo."),
          ("Como medir", "Diferença-em-diferenças: teste vs controle, 6 a 8 semanas antes e depois. KPIs: load factor e receita por voo."),
          ("Guarda-corpos", "Acompanhar yield médio, share no mercado e ocupação dos voos de pico, para o teste não canibalizar esses voos."),
          ("Decisão", "Load factor +2 pp vs controle sem perda de receita por voo: escalar para os outros mercados com gap acima de 0,5 pp.")]
for i, (tit, txt) in enumerate(blocos):
    x = 650 + (i % 2) * 310
    y = 382 + (i // 2) * 165
    textbox(p, x, y, 300, 155, [[(tit, 13, True, GOL)], [(txt, 11, False, INK)]], border=True, pad=12)
textbox(p, 20, 522, 620, 188, [[("Por que esses mercados", 13, True, GOL)],
                               [("Nos mercados de teste, a GOL tem share de assentos maior que o share de passageiros e ocupa menos que a média do mercado. "
                                 "O controle de cada um foi escolhido pela correlação da série mensal de passageiros em 2025 e 2026 e por ter porte parecido. "
                                 "Se as linhas do gráfico andam juntas antes do teste, qualquer diferença depois dele pode ser atribuída à ação.", 11, False, INK)]],
        border=True, pad=12)
pages.append(p)


THEME = {
    "name": "Radar Mercado Aereo",
    "dataColors": [GOL, LATAM, AZUL, "#6250D6", "#EDA100", "#E87BA4", "#008300", VERMELHO],
    "background": "#FFFFFF", "foreground": INK, "tableAccent": GOL,
    "good": VERDE, "bad": VERMELHO, "neutral": "#EDA100",
    "textClasses": {"callout": {"fontSize": 24, "fontFace": "Segoe UI Semibold", "color": INK},
                    "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": INK},
                    "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": INK},
                    "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": INK2}},
    "visualStyles": {
        "page": {"*": {"background": [{"color": {"solid": {"color": BG}}, "transparency": 0}]}},
        "*": {"*": {"border": [{"show": True, "color": {"solid": {"color": GRID}}, "radius": 10}],
                    "dropShadow": [{"show": False}],
                    "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}]}},
    },
}


def build_report():
    wj(RP / "definition.pbir", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
                                "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOME}.SemanticModel"}}})
    wj(RP / ".platform", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                          "metadata": {"type": "Report", "displayName": NOME}, "config": {"version": "2.0", "logicalId": gid()}})
    d = RP / "definition"
    wj(d / "version.json", {"$schema": f"{SCH}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    ver = {"visual": V_VIS, "report": V_REP, "page": V_PAGE}
    wj(d / "report.json", {
        "$schema": f"{SCH}/report/{V_REP}/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": ver, "type": "SharedResources"},
                            "customTheme": {"name": "RadarTheme.json", "reportVersionAtImport": ver, "type": "RegisteredResources"}},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "RadarTheme.json", "path": "RadarTheme.json", "type": "CustomTheme"}]}],
    })
    base = dict(THEME, name="CY24SU10")
    wj(RP / "StaticResources" / "SharedResources" / "BaseThemes" / "CY24SU10.json", base)
    wj(RP / "StaticResources" / "RegisteredResources" / "RadarTheme.json", THEME)
    wj(d / "pages" / "pages.json", {"$schema": f"{SCH}/pagesMetadata/1.0.0/schema.json",
                                     "pageOrder": [pg.name for pg in pages], "activePageName": pages[0].name})
    for pg in pages:
        pj = {"$schema": f"{SCH}/page/{V_PAGE}/schema.json", "name": pg.name, "displayName": pg.display,
              "displayOption": "FitToPage", "height": 720, "width": 1280}
        if pg.inter:
            pj["visualInteractions"] = pg.inter
        wj(d / "pages" / pg.name / "page.json", pj)
        for v in pg.visuals:
            wj(d / "pages" / pg.name / "visuals" / v["name"] / "visual.json", v)


def build_pbip():
    wj(PBI / f"{NOME}.pbip", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
                               "version": "1.0", "artifacts": [{"report": {"path": f"{NOME}.Report"}}],
                               "settings": {"enableAutoRecovery": True}})
    w(PBI / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")


def validar(pasta_schemas: Path):
    from jsonschema import Draft7Validator
    from referencing import Registry, Resource

    store = {}
    for f in pasta_schemas.glob("*.json"):
        j = json.loads(f.read_text(encoding="utf-8"))
        if "$id" in j:
            store[j["$id"]] = j
            store[j["$id"].replace("schema.embedded.json", "schema-embedded.json")] = j
    reg = Registry().with_resources([(k, Resource.from_contents(v)) for k, v in store.items()])
    erros = 0
    for f in sorted(PBI.rglob("*.json")) + sorted(PBI.glob("*.pbip")) + sorted(PBI.rglob("*.pbir")) + sorted(PBI.rglob("*.pbism")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        sid = doc.get("$schema")
        if sid not in store:
            continue
        for e in Draft7Validator(store[sid], registry=reg).iter_errors(doc):
            erros += 1
            if erros <= 25:
                print(f"[ERRO] {f.relative_to(PBI)} :: {'/'.join(map(str, e.absolute_path))} :: {e.message[:300]}")
    print("validação:", "OK" if erros == 0 else f"{erros} erros")
    return erros


if __name__ == "__main__":
    for pth in (SM, RP):
        if pth.exists():
            limpar(pth)
    build_model()
    build_report()
    build_pbip()
    n_vis = sum(len(pg.visuals) for pg in pages)
    print(f"ok -> {PBI / (NOME + '.pbip')}  |  {len(MEDIDAS)} medidas, {len(pages)} páginas, {n_vis} visuais")
    if "--validar" in sys.argv:
        sys.exit(1 if validar(Path(sys.argv[sys.argv.index("--validar") + 1])) else 0)
