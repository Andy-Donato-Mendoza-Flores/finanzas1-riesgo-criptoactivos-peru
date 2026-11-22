# Diccionario de variables · datos_procesados_2024200509B.csv

Autor: Andy Donato Mendoza Flores · Código 2024200509B · Tema 72 (Unidad II)
Frecuencia: diaria (día calendario) · Periodo: 2018-01-01 a 2026-10-31 · 3 226 filas × 18 columnas
Llave de unión entre fuentes: `fecha`

| Variable | Definición | Unidad | Fuente | Endpoint o URL de origen |
|---|---|---|---|---|
| fecha | Día calendario; llave común de unión | AAAA-MM-DD | Construida en 03_limpieza_datos.py | — |
| dia_habil_bvl | 1 si es día de semana con índice BVL publicado y monto negociado mayor que cero; 0 en otro caso | 0/1 | Derivada (BCRPData, scraping) | — |
| precio_btc_usd | Precio de cierre diario de Bitcoin | US$ | Yahoo Finance (API vía yfinance) | `yfinance.download("BTC-USD", start, end, interval="1d")` |
| precio_eth_usd | Precio de cierre diario de Ethereum | US$ | Yahoo Finance (API vía yfinance) | `yfinance.download("ETH-USD", start, end, interval="1d")` |
| volumen_btc_usd | Volumen diario negociado de Bitcoin reportado por Yahoo Finance (agregado de plataformas, no solo Perú) | US$ | Yahoo Finance | Igual que precio_btc_usd |
| volumen_eth_usd | Volumen diario negociado de Ethereum reportado por Yahoo Finance | US$ | Yahoo Finance | Igual que precio_eth_usd |
| tc_venta | Tipo de cambio interbancario, venta (serie PD04638PD). Fines de semana y feriados: último valor vigente | S/ por US$ | BCRPData (API) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04638PD/json/2018-01-01/2026-10-31/esp` |
| tasa_referencia | Tasa de referencia de la política monetaria (serie PD12301MD). Fines de semana y feriados: último valor vigente | % anual | BCRPData (API) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD12301MD/json/2018-01-01/2026-10-31/esp` |
| imputado_bcrp | 1 si tc_venta y tasa_referencia se rellenaron con el último valor vigente | 0/1 | Derivada | — |
| precio_btc_pen | precio_btc_usd × tc_venta | S/ | Derivada (Yahoo Finance + BCRPData) | — |
| precio_eth_pen | precio_eth_usd × tc_venta | S/ | Derivada (Yahoo Finance + BCRPData) | — |
| indice_bvl | Índice General Bursátil BVL (serie PD38026MD), valor tal como lo publica el BCRP | puntos del índice | BCRPData (web scraping) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/diarias/resultados/PD38026MD/html/{inicio}/{fin}/` |
| monto_negociado_bvl | Monto negociado en acciones, promedio diario (serie PD04696MD) | millones de S/ | BCRPData (web scraping) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/diarias/resultados/PD04696MD/html/{inicio}/{fin}/` |
| anomalo_bvl | 1 si el índice BVL salta más de 10 % y se revierte al día hábil siguiente (suma de ambos retornos < 1 %). Solo 2024-06-21. El valor original se conserva | 0/1 | Derivada | — |
| precio_btc_cg_usd | Precio de Bitcoin de CoinGecko a las 00:00 UTC, asignado al día anterior (equivale al cierre). Solo del 2025-12-31 al 2026-10-30 | US$ | CoinGecko (API v3) | `https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range?vs_currency=usd&from=1767225600&to=1793491199` |
| cap_mercado_btc_usd | Capitalización de mercado de Bitcoin | US$ | CoinGecko (API v3) | Igual que precio_btc_cg_usd |
| precio_eth_cg_usd | Precio de Ethereum de CoinGecko a las 00:00 UTC, asignado al día anterior | US$ | CoinGecko (API v3) | `https://api.coingecko.com/api/v3/coins/ethereum/market_chart/range?vs_currency=usd&from=1767225600&to=1793491199` |
| cap_mercado_eth_usd | Capitalización de mercado de Ethereum | US$ | CoinGecko (API v3) | Igual que precio_eth_cg_usd |

Celdas vacías: el dato no existe en la fuente para ese día (por ejemplo, la BVL en fines de semana o CoinGecko antes de su ventana).
