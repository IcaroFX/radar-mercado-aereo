# Radar Competitivo: mercado aéreo doméstico brasileiro

Análise do mercado doméstico com os dados abertos da ANAC. Cobre market share, ocupação, mercados por par de cidades, forecast de demanda, cenários para 2027 e uma proposta de teste A/B de inventário.

> Análise independente, feita só com dados públicos. Não usa informação interna de nenhuma companhia aérea.

## Principais resultados (jan a set de 2026 vs jan a set de 2025)

| Indicador | Resultado |
|---|---|
| Passageiros pagos no doméstico regular | 75,8 mi (+4,3% vs 2025; +13% vs 2019) |
| Oferta (ASK) vs demanda (RPK) | +7,2% vs +6,1%; o load factor caiu 0,8 pp, para 82,2% |
| Market share em RPK | LATAM 41,0% (+0,3 pp), GOL 31,7% (+2,1 pp), Azul 27,3% (−2,3 pp) |
| GOL | ASK +14,5%, passageiros +10,4%, LF 82,5% (−0,7 pp) |
| Gap de oferta | Em CWB-SAO e RIO-SAO, o share de assentos da GOL passa o share de passageiros (LF de 75% contra 77% a 79% do mercado). Em FOR-SAO, RIO-VIX e CWB-RIO, a GOL ocupa acima do mercado |
| Forecast | Dos 4 modelos, o melhor teve MAPE de 4,1% no backtest rolante (1 a 6 meses à frente) |
| Cenários 2027 (GOL) | 32,2 mi no pessimista, 34,8 mi no base e 37,1 mi no otimista |

## Estrutura

```
src/analysis.py        # carga, limpeza, métricas, mercados, forecast, cenários, test & learn -> out/metrics.json
src/build_excel.py     # planilha com fórmulas, gráficos, cenários editáveis e matriz de sensibilidade
src/build_carousel.py  # carrossel do LinkedIn (HTML -> PDF e PNGs, via Edge headless)
out/Radar_Mercado_Aereo.xlsx
out/Carrossel_Radar_Mercado_Aereo.pdf
```

## Como reproduzir

1. No portal de dados abertos da ANAC, entre em Voos e operações aéreas › Dados Estatísticos do Transporte Aéreo e baixe `Dados_Estatisticos.csv` (cerca de 361 MB). Salve o arquivo em `data_raw/`.
2. Instale as dependências: `pip install pandas numpy openpyxl`.
3. Rode os scripts:

```bash
python src/analysis.py
python src/build_excel.py
python src/build_carousel.py
```

## Power BI

O projeto do Power BI está em `powerbi/`, no formato PBIP (arquivos de texto, bons para versionar no GitHub). Ele é gerado assim:

```bash
python src/export_powerbi.py
python src/build_powerbi.py
```

No Power BI Desktop, use Arquivo › Abrir e escolha `powerbi/RadarMercadoAereo.pbip`. Se aparecer o aviso "Algumas das tabelas estão incompletas", clique em Atualizar agora para carregar os CSVs. Se você mudar a pasta de lugar, ajuste o parâmetro `PastaDados` em Transformar dados para o novo caminho de `powerbi/dados/`.

O relatório tem 5 páginas: visão geral, concorrência, mercados da GOL, forecast e cenários, e test & learn. São 68 medidas DAX, incluindo textos de insight que se reescrevem conforme o período escolhido e simuladores de cenário para 2027.

## Metodologia

A análise usa só voos domésticos regulares, de 2019 até o último mês da base. As companhias estão agrupadas em LATAM (TAM), GOL (GLO) e Azul (AZU mais Azul Conecta).

Cada mercado é um par de cidades sem direção, então SAO-REC e REC-SAO contam juntos. Aeroportos da mesma região metropolitana viram uma cidade só: SAO junta CGH, GRU e VCP; RIO junta SDU e GIG; BHZ junta CNF e PLU.

O market share por companhia usa RPK. Dentro de cada mercado, usa passageiros pagos.

O gap de oferta é o share de assentos da GOL menos o share de passageiros da GOL no mesmo mercado. Gap positivo quer dizer que a GOL oferece mais do que consegue vender, e aí a saída é estimular venda ou ajustar capacidade. Gap negativo quer dizer que ela ocupa acima do mercado e tem espaço para proteger tarifa.

Os quadrantes cruzam o crescimento do mercado com a variação de share da GOL e separam os mercados em crescer junto, defender, consolidar e rever capacidade.

No forecast, comparei quatro modelos num backtest rolante com 13 origens e horizonte de 1 a 6 meses: tendência log-linear com sazonalidade mensal em duas janelas de treino, ingênuo sazonal e ingênuo sazonal com crescimento de 12 meses. O vencedor gera a previsão, e a faixa P10 a P90 sai dos erros reais do backtest.

Os cenários seguem a conta passageiros GOL 2027 = mercado 2026 × (1 + crescimento) × share. Na planilha, as premissas ficam em células editáveis.

Para o test & learn, os mercados de teste são os que têm gap de oferta acima de 0,5 pp. O controle de cada um é o mercado com a série mensal mais correlacionada em 2025 e 2026 e porte entre 0,4 e 2,5 vezes o do teste. A leitura proposta é por diferença-em-diferenças.

## Limitações

A base da ANAC é por etapa de voo, não pela origem e destino final do passageiro, então uma conexão aparece como duas etapas.

A base também não tem tarifa, por isso yield e receita ficaram de fora. A base de Tarifas Aéreas Domésticas da ANAC resolveria isso.

As enchentes no RS distorceram as séries de POA em 2024. Por isso a correlação usada para escolher os controles considera só 2025 e 2026.
