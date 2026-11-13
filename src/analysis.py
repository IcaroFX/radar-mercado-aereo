"""
Radar Competitivo do Mercado Aéreo Doméstico: análise com dados abertos da ANAC.

Entrada : data_raw/Dados_Estatisticos.csv (ANAC, Dados Estatísticos do Transporte Aéreo)
Saída   : out/metrics.json  (números usados no carrossel, no Excel e no post)

Uso: python src/analysis.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw" / "Dados_Estatisticos.csv"
CACHE = ROOT / "data_raw" / "anac_dom_regular.pkl"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

# ----------------------------------------------------------------------------
# 1. Carga e limpeza
# ----------------------------------------------------------------------------
COLS = [
    "EMPRESA_SIGLA", "ANO", "MES",
    "AEROPORTO_DE_ORIGEM_SIGLA", "AEROPORTO_DE_DESTINO_SIGLA",
    "NATUREZA", "GRUPO_DE_VOO",
    "PASSAGEIROS_PAGOS", "ASK", "RPK", "ASSENTOS", "DECOLAGENS",
]

GRUPO = {"TAM": "LATAM", "GLO": "GOL", "AZU": "Azul", "ACN": "Azul"}  # Azul Conecta -> grupo Azul
ORDEM = ["LATAM", "GOL", "Azul", "Outras"]

# Agrupa aeroportos da mesma região metropolitana (é assim que o passageiro compara voos)
METRO = {"SBSP": "SAO", "SBGR": "SAO", "SBKP": "SAO", "SBRJ": "RIO", "SBGL": "RIO",
         "SBCF": "BHZ", "SBBH": "BHZ"}
IATA = {
    "SBSP": "CGH", "SBGR": "GRU", "SBKP": "VCP", "SBRJ": "SDU", "SBGL": "GIG", "SBCF": "CNF",
    "SBBH": "PLU", "SBBR": "BSB", "SBRF": "REC", "SBSV": "SSA", "SBPA": "POA", "SBCT": "CWB",
    "SBFZ": "FOR", "SBGO": "GYN", "SBFL": "FLN", "SBBE": "BEL", "SBVT": "VIX", "SBEG": "MAO",
    "SBMO": "MCZ", "SBCY": "CGB", "SBFI": "IGU", "SBPS": "BPS", "SBSG": "NAT", "SBNF": "NVT",
    "SBSL": "SLZ", "SBJP": "JPA", "SBCG": "CGR", "SBAR": "AJU", "SBTE": "THE", "SBUL": "UDI",
    "SBSR": "SJP", "SBMG": "MGF", "SBPJ": "PMW", "SBRP": "RAO", "SBLO": "LDB", "SBCH": "XAP",
    "SBIL": "IOS", "SBMQ": "MCP", "SBPV": "PVH", "SBJV": "JOI", "SBPL": "PNZ", "SBJU": "JDO",
    "SBSN": "STM", "SBSI": "OPS", "SBCA": "CAC", "SBVC": "VDC", "SBRB": "RBR", "SBBV": "BVB",
    "SBKG": "CPV", "SBIZ": "IMP", "SBMA": "MAB", "SBJA": "JJG", "SBMK": "MOC", "SBUR": "UBA",
    "SBGV": "GVR", "SBFN": "FEN", "SBPF": "PFB", "SBCX": "CXJ", "SBJD": "QDV",
}


def load() -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_pickle(CACHE)
    df = pd.read_csv(RAW, sep=";", skiprows=1, usecols=COLS, encoding="utf-8-sig",
                     decimal=",", low_memory=False)
    df = df[(df.ANO >= 2019) & (df.NATUREZA == "DOMÉSTICA") & (df.GRUPO_DE_VOO == "REGULAR")]
    num = ["PASSAGEIROS_PAGOS", "ASK", "RPK", "ASSENTOS", "DECOLAGENS"]
    df[num] = df[num].fillna(0)
    df["grupo"] = df.EMPRESA_SIGLA.map(GRUPO).fillna("Outras")
    df["data"] = pd.to_datetime(dict(year=df.ANO, month=df.MES, day=1))
    for side, col in (("o", "AEROPORTO_DE_ORIGEM_SIGLA"), ("d", "AEROPORTO_DE_DESTINO_SIGLA")):
        df[f"cid_{side}"] = df[col].map(lambda x: METRO.get(x, IATA.get(x, x)))
        df[f"apt_{side}"] = df[col].map(lambda x: IATA.get(x, x))
    # mercado não-direcional: SAO-REC e REC-SAO são o mesmo mercado
    df["mercado"] = [("-".join(sorted((a, b)))) for a, b in zip(df.cid_o, df.cid_d)]
    df = df[df.cid_o != df.cid_d]
    df = df.drop(columns=["NATUREZA", "GRUPO_DE_VOO"])
    df.to_pickle(CACHE)
    return df


df = load()
ULT = df.data.max()
ANO, MES = ULT.year, ULT.month
ANT = ANO - 1
MESES = list(range(1, MES + 1))
ytd = df[df.MES.isin(MESES)]
cur, prev, base19 = ytd[ytd.ANO == ANO], ytd[ytd.ANO == ANT], ytd[ytd.ANO == 2019]
PER = f"jan a {['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'][MES-1]}"
print(f"Último mês na base: {ULT:%Y-%m}  |  Comparação: {PER} {ANO} vs {ANT}")

M = {"periodo": PER, "ano": ANO, "ano_ant": ANT, "ultimo_mes": f"{ULT:%Y-%m}",
     "atualizado_em": "2026-11-13"}

# ----------------------------------------------------------------------------
# 2. Visão de mercado e market share
# ----------------------------------------------------------------------------
def agg(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby("grupo")[["PASSAGEIROS_PAGOS", "RPK", "ASK", "ASSENTOS", "DECOLAGENS"]].sum()
    g = g.reindex(ORDEM).fillna(0)
    g["share_rpk"] = g.RPK / g.RPK.sum()
    g["share_pax"] = g.PASSAGEIROS_PAGOS / g.PASSAGEIROS_PAGOS.sum()
    g["share_ask"] = g.ASK / g.ASK.sum()
    g["lf"] = g.RPK / g.ASK
    return g


a_cur, a_prev, a_19 = agg(cur), agg(prev), agg(base19)
tot = lambda d, c="PASSAGEIROS_PAGOS": float(d[c].sum())
M["mercado"] = {
    "pax": tot(cur), "pax_ant": tot(prev), "pax_2019": tot(base19),
    "cresc_pax": tot(cur) / tot(prev) - 1, "vs_2019": tot(cur) / tot(base19) - 1,
    "cresc_rpk": tot(cur, "RPK") / tot(prev, "RPK") - 1,
    "cresc_ask": tot(cur, "ASK") / tot(prev, "ASK") - 1,
    "lf": tot(cur, "RPK") / tot(cur, "ASK"), "lf_ant": tot(prev, "RPK") / tot(prev, "ASK"),
}
M["cias"] = {
    g: {
        "pax": float(a_cur.loc[g, "PASSAGEIROS_PAGOS"]),
        "cresc_pax": float(a_cur.loc[g, "PASSAGEIROS_PAGOS"] / a_prev.loc[g, "PASSAGEIROS_PAGOS"] - 1),
        "cresc_ask": float(a_cur.loc[g, "ASK"] / a_prev.loc[g, "ASK"] - 1),
        "share_rpk": float(a_cur.loc[g, "share_rpk"]), "share_rpk_ant": float(a_prev.loc[g, "share_rpk"]),
        "share_rpk_2019": float(a_19.loc[g, "share_rpk"]),
        "share_pax": float(a_cur.loc[g, "share_pax"]), "share_pax_ant": float(a_prev.loc[g, "share_pax"]),
        "share_ask": float(a_cur.loc[g, "share_ask"]),
        "lf": float(a_cur.loc[g, "lf"]), "lf_ant": float(a_prev.loc[g, "lf"]),
    }
    for g in ["LATAM", "GOL", "Azul"]
}

# série mensal por grupo
mens = (df.groupby(["data", "grupo"])[["PASSAGEIROS_PAGOS", "RPK", "ASK", "ASSENTOS", "DECOLAGENS"]]
          .sum().reset_index())
piv_rpk = mens.pivot(index="data", columns="grupo", values="RPK").reindex(columns=ORDEM).fillna(0)
share_m = piv_rpk.div(piv_rpk.sum(axis=1), axis=0)
share_12m = piv_rpk.rolling(12).sum().pipe(lambda x: x.div(x.sum(axis=1), axis=0))
M["serie_share"] = [
    {"data": f"{d:%Y-%m}", **{g: round(float(share_m.loc[d, g]), 4) for g in ["LATAM", "GOL", "Azul"]},
     **{f"{g}_12m": (None if np.isnan(share_12m.loc[d, g]) else round(float(share_12m.loc[d, g]), 4))
        for g in ["LATAM", "GOL", "Azul"]}}
    for d in share_m.index
]
mens.to_pickle(OUT / "_mensal.pkl")

# ----------------------------------------------------------------------------
# 3. Mercados (pares de cidades): onde a GOL ganha ou perde espaço
# ----------------------------------------------------------------------------
def mkt(d: pd.DataFrame) -> pd.DataFrame:
    p = d.pivot_table(index="mercado", columns="grupo", values=["PASSAGEIROS_PAGOS", "ASSENTOS"],
                      aggfunc="sum", fill_value=0)
    p = p[p["PASSAGEIROS_PAGOS"].sum(axis=1) > 0]
    out = pd.DataFrame(index=p.index)
    pax, seats = p["PASSAGEIROS_PAGOS"].reindex(columns=ORDEM, fill_value=0), p["ASSENTOS"].reindex(columns=ORDEM, fill_value=0)
    out["pax"] = pax.sum(axis=1)
    out["assentos"] = seats.sum(axis=1)
    out["gol_pax"], out["gol_assentos"] = pax["GOL"], seats["GOL"]
    sh = pax.div(out.pax.replace(0, np.nan), axis=0)
    out["share_gol"] = sh["GOL"]
    out["share_assentos_gol"] = seats["GOL"] / out.assentos.replace(0, np.nan)
    out["hhi"] = (sh ** 2).sum(axis=1) * 10000
    out["lider"] = sh.idxmax(axis=1)
    out["n_cias"] = (sh > 0.05).sum(axis=1)
    for g in ["LATAM", "GOL", "Azul"]:
        out[f"share_{g}"] = sh[g]
    out["lf_mercado"] = out.pax / out.assentos.replace(0, np.nan)
    out["lf_gol"] = out.gol_pax / out.gol_assentos.replace(0, np.nan)
    return out


mc, mp = mkt(cur), mkt(prev)
t = mc.join(mp[["pax", "share_gol", "gol_pax"]], rsuffix="_ant")
t["cresc_mercado"] = t.pax / t.pax_ant - 1
t["delta_share_pp"] = (t.share_gol - t.share_gol_ant) * 100
t["gap_oferta_pp"] = (t.share_assentos_gol - t.share_gol) * 100   # >0: GOL oferta mais do que vende
t["lf_gap_pp"] = (t.lf_gol - t.lf_mercado) * 100


def quadrante(r):
    if r.cresc_mercado >= 0 and r.delta_share_pp >= 0:
        return "Crescer junto"
    if r.cresc_mercado >= 0 and r.delta_share_pp < 0:
        return "Defender"
    if r.cresc_mercado < 0 and r.delta_share_pp >= 0:
        return "Consolidar"
    return "Rever capacidade"


top = t[(t.gol_pax >= 150_000) & (t.pax_ant > 0)].sort_values("gol_pax", ascending=False).head(25).copy()
top["quadrante"] = top.apply(quadrante, axis=1)
top.to_pickle(OUT / "_mercados_gol.pkl")
t[t.pax >= 100_000].sort_values("pax", ascending=False).to_pickle(OUT / "_mercados_todos.pkl")

cols_json = ["pax", "pax_ant", "cresc_mercado", "gol_pax", "share_gol", "share_gol_ant", "delta_share_pp",
             "share_assentos_gol", "gap_oferta_pp", "lf_gol", "lf_mercado", "lf_gap_pp", "hhi", "lider",
             "n_cias", "share_LATAM", "share_Azul", "quadrante"]
M["mercados_gol"] = [{"mercado": k, **{c: (v.item() if hasattr(v, "item") else v) for c, v in r[cols_json].items()}}
                     for k, r in top.iterrows()]
M["quadrantes"] = top.quadrante.value_counts().to_dict()
M["gol_pax_top25_pct"] = float(top.gol_pax.sum() / mc.gol_pax.sum())

# ----------------------------------------------------------------------------
# 4. Forecast de demanda (mercado total) + cenários para a GOL
#    Compara 4 modelos simples em backtest rolante (13 origens x horizonte 1-6 meses)
#    e usa o vencedor. Erros do backtest viram o intervalo de incerteza.
# ----------------------------------------------------------------------------
serie_all = mens.groupby("data").PASSAGEIROS_PAGOS.sum()
serie_gol = mens[mens.grupo == "GOL"].set_index("data").PASSAGEIROS_PAGOS


def loglin(y: pd.Series, h: int, inicio: str) -> np.ndarray:
    """log(pax) = a + b*t + dummies de mês."""
    y = y[y.index >= inicio]
    idx_f = pd.date_range(y.index[-1] + pd.DateOffset(months=1), periods=h, freq="MS")
    def X(idx):
        tt = ((idx.year - y.index[0].year) * 12 + idx.month - y.index[0].month).to_numpy(float)
        return np.column_stack([np.ones(len(idx)), tt] + [(idx.month == m).astype(float) for m in range(2, 13)])
    beta, *_ = np.linalg.lstsq(X(y.index), np.log(y.to_numpy()), rcond=None)
    return np.exp(X(idx_f) @ beta)


def snaive(y: pd.Series, h: int, drift: bool) -> np.ndarray:
    """Mesmo mês do ano anterior (x crescimento dos últimos 12 meses, se drift)."""
    g = y.iloc[-12:].sum() / y.iloc[-24:-12].sum() if drift else 1.0
    hist = list(y.to_numpy())
    for _ in range(h):
        hist.append(hist[-12] * g)
    return np.array(hist[-h:])


MODELOS = {
    "Tendência log-linear (2023+)": lambda y, h: loglin(y, h, "2023-01-01"),
    "Tendência log-linear (24m)": lambda y, h: loglin(y, h, str(y.index[-24].date())),
    "Ingênuo sazonal": lambda y, h: snaive(y, h, False),
    "Ingênuo sazonal + crescimento 12m": lambda y, h: snaive(y, h, True),
}
H = 6
origens = pd.date_range(ULT - pd.DateOffset(months=H + 12), ULT - pd.DateOffset(months=H), freq="MS")
erros = {k: [] for k in MODELOS}
for o in origens:
    y_tr = serie_all[serie_all.index <= o]
    y_te = serie_all[(serie_all.index > o)].iloc[:H].to_numpy()
    for k, f in MODELOS.items():
        erros[k].append(f(y_tr, H) / y_te - 1)   # erro relativo por horizonte
res = {k: {"mape": float(np.mean(np.abs(np.array(v)))), "vies": float(np.mean(np.array(v)))} for k, v in erros.items()}
melhor = min(res, key=lambda k: res[k]["mape"])
err_best = np.array(erros[melhor]).ravel()
q10, q90 = np.quantile(err_best, [0.1, 0.9])
M["backtest"] = {"origens": f"{origens[0]:%Y-%m} a {origens[-1]:%Y-%m}", "horizonte": H,
                 "modelos": res, "melhor": melhor, "erro_p10": float(q10), "erro_p90": float(q90)}
print("Backtest:", json.dumps(res, ensure_ascii=False, indent=1), "-> melhor:", melhor)

fut = pd.date_range(ULT + pd.DateOffset(months=1), "2027-12-01", freq="MS")
fc = MODELOS[melhor](serie_all, len(fut))
fc_s = pd.Series(fc, index=fut)
# intervalo: erro empírico do backtest (forecast/real - 1) -> real = forecast/(1+erro)
M["forecast"] = {
    "modelo": melhor,
    "historico": [{"data": f"{d:%Y-%m}", "pax": float(v)} for d, v in serie_all[serie_all.index >= "2023-01-01"].items()],
    "prev": [{"data": f"{d:%Y-%m}", "base": float(v), "p10": float(v / (1 + q90)), "p90": float(v / (1 + q10))}
             for d, v in fc_s.items()],
}

# --- Cenários 2027 para a GOL = mercado x share (premissas editáveis no Excel) ---
pax_m = mens.pivot(index="data", columns="grupo", values="PASSAGEIROS_PAGOS").fillna(0)
share_gol_12m = float(pax_m.GOL.tail(12).sum() / pax_m.sum(axis=1).tail(12).sum())
mkt_2025 = float(serie_all[serie_all.index.year == 2025].sum())
mkt_2026 = float(pd.concat([serie_all[serie_all.index.year == 2026], fc_s[fc_s.index.year == 2026]]).sum())
mkt_2027 = float(fc_s[fc_s.index.year == 2027].sum())
g_base = mkt_2027 / mkt_2026 - 1
gol_2025 = float(serie_gol[serie_gol.index.year == 2025].sum())
cen = {
    "Pessimista": {"cresc_mercado": g_base - 0.03, "share": share_gol_12m - 0.015},
    "Base": {"cresc_mercado": g_base, "share": share_gol_12m},
    "Otimista": {"cresc_mercado": g_base + 0.02, "share": share_gol_12m + 0.015},
}
for c in cen.values():
    c["mercado_2027"] = mkt_2026 * (1 + c["cresc_mercado"])
    c["gol_2027"] = c["mercado_2027"] * c["share"]
    c["vs_2025"] = c["gol_2027"] / gol_2025 - 1
M["cenarios"] = {"share_gol_12m": share_gol_12m, "gol_2025": gol_2025, "mercado_2025": mkt_2025,
                 "mercado_2026_est": mkt_2026, "cresc_base_2027": g_base, "cenarios": cen}

# ----------------------------------------------------------------------------
# 5. Test & Learn: mercados-controle sugeridos
#    Para cada mercado candidato a teste, busca o mercado com sazonalidade mais parecida
#    (correlação da série mensal de passageiros) e porte semelhante.
# ----------------------------------------------------------------------------
mm = (df[df.data >= "2025-01-01"].groupby(["mercado", "data"]).PASSAGEIROS_PAGOS.sum()
        .unstack(fill_value=0))
mm = mm[mm.sum(axis=1) > 0]
pool = t[(t.pax >= 300_000) & (t.share_gol > 0.15)].index.intersection(mm.index)
cand = top[top.gap_oferta_pp > 0.5].sort_values("gap_oferta_pp", ascending=False).head(3).index
pares = []
for m in cand:
    if m not in mm.index:
        continue
    corr = mm.loc[pool].T.corrwith(mm.loc[m]).drop(index=m, errors="ignore")
    porte = (mm.loc[pool].sum(axis=1) / mm.loc[m].sum()).reindex(corr.index)
    ok = corr[(porte > 0.4) & (porte < 2.5) & (~corr.index.isin(cand))]
    if ok.empty or ok.max() < 0.75:   # sem controle parecido o bastante -> não testa
        continue
    c = ok.idxmax()
    pares.append({"teste": m, "controle": c, "correlacao": float(ok.max()),
                  "gap_teste_pp": float(t.loc[m, "gap_oferta_pp"]), "lf_gol_teste": float(t.loc[m, "lf_gol"]),
                  "lf_mercado_teste": float(t.loc[m, "lf_mercado"])})
M["test_learn"] = pares

(OUT / "metrics.json").write_text(json.dumps(M, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print(json.dumps({k: M[k] for k in ["cenarios", "test_learn"]},
                 ensure_ascii=False, indent=1, default=float)[:6000])
