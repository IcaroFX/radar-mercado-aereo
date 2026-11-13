"""
Exporta o modelo estrela usado pelo Power BI (powerbi/dados/*.csv).

Fatos     : fVoos (mês x empresa x aeroporto origem/destino), fForecast, fBacktest, fCenarios,
            fPremissas, fTestLearn
Dimensões : dCia, dMercado, dAeroporto  (o calendário é criado em DAX dentro do modelo)

Uso: python src/export_powerbi.py   (depois de rodar src/analysis.py)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw" / "Dados_Estatisticos.csv"
OUT = ROOT / "powerbi" / "dados"
OUT.mkdir(parents=True, exist_ok=True)
M = json.loads((ROOT / "out" / "metrics.json").read_text(encoding="utf-8"))

import importlib.util
spec = importlib.util.spec_from_file_location("cfg", ROOT / "src" / "analysis.py")
# reaproveita os mapas METRO / IATA / GRUPO sem rodar a análise inteira
src = (ROOT / "src" / "analysis.py").read_text(encoding="utf-8")
ns = {}
exec(src[src.index("GRUPO = {"):src.index("def load()")], ns)
GRUPO, METRO, IATA = ns["GRUPO"], ns["METRO"], ns["IATA"]

COLS = ["EMPRESA_SIGLA", "ANO", "MES",
        "AEROPORTO_DE_ORIGEM_SIGLA", "AEROPORTO_DE_ORIGEM_NOME", "AEROPORTO_DE_ORIGEM_UF", "AEROPORTO_DE_ORIGEM_REGIAO",
        "AEROPORTO_DE_DESTINO_SIGLA", "AEROPORTO_DE_DESTINO_NOME", "AEROPORTO_DE_DESTINO_UF", "AEROPORTO_DE_DESTINO_REGIAO",
        "NATUREZA", "GRUPO_DE_VOO", "PASSAGEIROS_PAGOS", "ASK", "RPK", "ASSENTOS", "DECOLAGENS", "DISTANCIA_VOADA_KM"]
print("lendo CSV da ANAC...")
df = pd.read_csv(RAW, sep=";", skiprows=1, usecols=COLS, encoding="utf-8-sig", decimal=",", low_memory=False)
df = df[(df.ANO >= 2019) & (df.NATUREZA == "DOMÉSTICA") & (df.GRUPO_DE_VOO == "REGULAR")].copy()
num = ["PASSAGEIROS_PAGOS", "ASK", "RPK", "ASSENTOS", "DECOLAGENS", "DISTANCIA_VOADA_KM"]
df[num] = df[num].fillna(0)

cod = lambda x: IATA.get(x, x)
cid = lambda x: METRO.get(x, IATA.get(x, x))
df["Origem"] = df.AEROPORTO_DE_ORIGEM_SIGLA.map(cod)
df["Destino"] = df.AEROPORTO_DE_DESTINO_SIGLA.map(cod)
df["cid_o"] = df.AEROPORTO_DE_ORIGEM_SIGLA.map(cid)
df["cid_d"] = df.AEROPORTO_DE_DESTINO_SIGLA.map(cid)
df = df[df.cid_o != df.cid_d]
df["Mercado"] = ["-".join(sorted((a, b))) for a, b in zip(df.cid_o, df.cid_d)]
df["Cia"] = df.EMPRESA_SIGLA.map(GRUPO).fillna("Outras")
df["Data"] = pd.to_datetime(dict(year=df.ANO, month=df.MES, day=1)).dt.strftime("%Y-%m-%d")

# ---------------------------------------------------------------- fVoos
f = (df.groupby(["Data", "Cia", "EMPRESA_SIGLA", "Origem", "Destino", "Mercado"], as_index=False)[num].sum()
       .rename(columns={"EMPRESA_SIGLA": "Empresa", "PASSAGEIROS_PAGOS": "Passageiros", "ASSENTOS": "Assentos",
                        "DECOLAGENS": "Decolagens", "DISTANCIA_VOADA_KM": "DistanciaKm"}))
f = f[(f.Passageiros > 0) | (f.Assentos > 0)]
f.to_csv(OUT / "fVoos.csv", index=False, float_format="%.0f")
print("fVoos:", len(f), "linhas")

# ---------------------------------------------------------------- dAeroporto
ap = pd.concat([
    df[["Origem", "AEROPORTO_DE_ORIGEM_NOME", "AEROPORTO_DE_ORIGEM_UF", "AEROPORTO_DE_ORIGEM_REGIAO", "cid_o"]].set_axis(["Aeroporto", "Nome", "UF", "Regiao", "Cidade"], axis=1),
    df[["Destino", "AEROPORTO_DE_DESTINO_NOME", "AEROPORTO_DE_DESTINO_UF", "AEROPORTO_DE_DESTINO_REGIAO", "cid_d"]].set_axis(["Aeroporto", "Nome", "UF", "Regiao", "Cidade"], axis=1),
]).dropna(subset=["Aeroporto"]).drop_duplicates("Aeroporto")
ap["Regiao"] = ap.Regiao.str.title()
ap["Nome"] = ap.Nome.str.title()
ap.to_csv(OUT / "dAeroporto.csv", index=False)

# ---------------------------------------------------------------- dMercado
cid_info = ap.groupby("Cidade").agg(UF=("UF", "first"), Regiao=("Regiao", "first"))
NOMES = {"SAO": "São Paulo", "RIO": "Rio de Janeiro", "BHZ": "Belo Horizonte"}
m = (df.groupby("Mercado")[["DISTANCIA_VOADA_KM", "DECOLAGENS", "PASSAGEIROS_PAGOS"]].sum().reset_index())
m["Cidade A"] = m.Mercado.str.split("-").str[0]
m["Cidade B"] = m.Mercado.str.split("-").str[1]
for s in "AB":
    m[f"UF {s}"] = m[f"Cidade {s}"].map(cid_info.UF)
    m[f"Região {s}"] = m[f"Cidade {s}"].map(cid_info.Regiao)
m["Tipo"] = np.where(m["Região A"] == m["Região B"], "Intrarregional", "Inter-regional")
m["Conecta SAO"] = np.where(m.Mercado.str.contains("SAO"), "Sim", "Não")
m["Distância média (km)"] = (m.DISTANCIA_VOADA_KM / m.DECOLAGENS.replace(0, np.nan)).round(0)
m["Faixa de distância"] = pd.cut(m["Distância média (km)"], [0, 800, 1600, 99999],
                                 labels=["Curta (até 800 km)", "Média (800 a 1.600 km)", "Longa (acima de 1.600 km)"]).astype(str)
top = {r["mercado"]: r for r in M["mercados_gol"]}
m["Top 25 GOL"] = np.where(m.Mercado.isin(top), "Sim", "Não")
m["Quadrante GOL (jan a set 26)"] = m.Mercado.map(lambda x: top[x]["quadrante"] if x in top else "Fora do top 25")
m = m.drop(columns=["DISTANCIA_VOADA_KM", "DECOLAGENS", "PASSAGEIROS_PAGOS"])
m.to_csv(OUT / "dMercado.csv", index=False)

# ---------------------------------------------------------------- dCia
pd.DataFrame({"Cia": ["LATAM", "GOL", "Azul", "Outras"], "Ordem": [1, 2, 3, 4],
              "Cor": ["#1BAF7A", "#EB6834", "#2A78D6", "#A3A199"]}).to_csv(OUT / "dCia.csv", index=False)

# ---------------------------------------------------------------- forecast, backtest, cenários
F = M["forecast"]
fc = pd.DataFrame([{"Data": h["data"] + "-01", "Realizado": h["pax"]} for h in F["historico"]] +
                  [{"Data": p["data"] + "-01", "Previsao": p["base"], "P10": p["p10"], "P90": p["p90"]} for p in F["prev"]])
# liga a linha prevista ao último realizado
last = fc[fc.Realizado.notna()].index[-1]
fc.loc[last, ["Previsao", "P10", "P90"]] = fc.loc[last, "Realizado"]
fc.to_csv(OUT / "fForecast.csv", index=False, float_format="%.0f")

bt = M["backtest"]
pd.DataFrame([{"Modelo": k, "MAPE": v["mape"], "Vies": v["vies"], "Escolhido": "Sim" if k == bt["melhor"] else "Não"}
              for k, v in bt["modelos"].items()]).to_csv(OUT / "fBacktest.csv", index=False, float_format="%.6f")

C = M["cenarios"]
pd.DataFrame([{"Cenario": k, "Ordem": i, "Crescimento": v["cresc_mercado"], "Share": v["share"],
               "Mercado2027": v["mercado_2027"] / 1e6, "GOL2027": v["gol_2027"] / 1e6, "VsGOL2025": v["vs_2025"]}
              for i, (k, v) in enumerate(C["cenarios"].items(), 1)]).to_csv(OUT / "fCenarios.csv", index=False, float_format="%.6f")
pd.DataFrame([{"Mercado2025": C["mercado_2025"], "Mercado2026Est": C["mercado_2026_est"], "GOL2025": C["gol_2025"],
               "Share12m": C["share_gol_12m"], "CrescBase2027": C["cresc_base_2027"]}]).to_csv(OUT / "fPremissas.csv", index=False, float_format="%.6f")

pd.DataFrame([{"Teste": p["teste"], "Controle": p["controle"], "Correlacao": p["correlacao"], "GapOfertaPP": p["gap_teste_pp"],
               "LFGOLTeste": p["lf_gol_teste"], "LFMercadoTeste": p["lf_mercado_teste"]}
              for p in M["test_learn"]]).to_csv(OUT / "fTestLearn.csv", index=False, float_format="%.6f")

for p in sorted(OUT.glob("*.csv")):
    print(f"{p.name:16s} {p.stat().st_size/1e6:6.2f} MB")
