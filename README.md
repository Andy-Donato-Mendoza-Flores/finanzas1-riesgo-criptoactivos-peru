# Riesgo de los criptoactivos frente a los activos financieros peruanos

Artículo científico de aplicación · Finanzas I (055D) · Unidad II · Periodo 2026-II
Escuela Profesional de Economía · Universidad Nacional del Centro del Perú (UNCP)
Docente: Dr. Ciro Iván Machacuay Meza

| Dato | Detalle |
|---|---|
| Autor | Andy Donato Mendoza Flores |
| Código de matrícula | 2024200509B |
| Tema del temario | N.º 72 · S11 · Riesgo financiero y CAPM |
| Objetivo | Comparar el perfil riesgo-retorno de Bitcoin y Ethereum con el del mercado bursátil peruano |
| Periodo (parámetros congelados) | FECHA_INICIO = 2018-01-01 · FECHA_CORTE = 2026-10-31 |
| Fecha de extracción | 2026-11-22 (hora de Lima en `log_ejecucion.txt`) |
| Repositorio | https://github.com/Andy-Donato-Mendoza-Flores/finanzas1-riesgo-criptoactivos-peru |

## Fuentes y endpoints

**Vía 1 · API**

| Fuente | Series | Endpoint |
|---|---|---|
| Yahoo Finance (librería yfinance) | BTC-USD, ETH-USD | `yfinance.download(ticker, start="2018-01-01", end="2026-11-01", interval="1d")` |
| CoinGecko API v3 | bitcoin, ethereum | `https://api.coingecko.com/api/v3/coins/{id}/market_chart/range?vs_currency=usd&from=1767225600&to=1793491199` |
| BCRPData API | PD04638PD (TC interbancario venta), PD12301MD (tasa de referencia) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{codigo}/json/2018-01-01/2026-10-31/esp` |

**Vía 2 · Web scraping**

| Fuente | Series | URL rastreada |
|---|---|---|
| BCRPData, páginas HTML de resultados | PD38026MD (Índice General Bursátil BVL), PD04696MD (monto negociado en acciones) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/diarias/resultados/{codigo}/html/{inicio}/{fin}/` · una página por año · selectores `td.periodo` y `td.dato` · pausa de 1.5 s · User-Agent con correo institucional |

Llave común de unión: **fecha (día)**.

## Estructura

```
codigo/
  01_extraccion_api.py      Vía 1: Yahoo Finance, CoinGecko y BCRPData (API)
  02_scraping_web.py        Vía 2: scraping de BCRPData (BeautifulSoup)
  03_limpieza_datos.py      tipificación, faltantes, atípicos, unión por fecha, hash
  04_analisis.py            tablas y figuras del artículo
datos_crudos/               archivos tal como salieron de las fuentes (no editados)
  html_bcrp/                páginas HTML rastreadas y copia del robots.txt consultado
datos_procesados/           datos_procesados_2024200509B.csv y hash_sha256.txt
salidas/                    tabla1 a tabla9 (.csv) y figura1 a figura8 (.png y .pdf)
diccionario_variables.md    definición, unidad, fuente y endpoint de cada variable
requirements.txt            versiones exactas de las librerías
.env.example                plantilla de la clave (opcional) de CoinGecko
log_ejecucion.txt           fecha y hora, filas y código HTTP de cada extracción
```

## Orden de ejecución

```bash
pip install -r requirements.txt
export COINGECKO_DEMO_API_KEY="su_clave"   # opcional (ver .env.example)
python codigo/01_extraccion_api.py
python codigo/02_scraping_web.py
python codigo/03_limpieza_datos.py
python codigo/04_analisis.py
```

Los scripts leen la clave desde la variable de entorno `COINGECKO_DEMO_API_KEY`. Sin clave, CoinGecko responde por su acceso público, con un límite menor de llamadas.

## Versiones

Python 3.13.18

- pandas==2.2.3
- numpy==2.4.6
- requests==2.32.4
- yfinance==1.8.0
- beautifulsoup4==4.13.5
- matplotlib==3.10.0
- scipy==1.16.3
- statsmodels==0.15.0

## Verificación de integridad

SHA-256 de `datos_procesados/datos_procesados_2024200509B.csv`:

`c1e2504a87ccb14cd803032c12a488c9c29aaf63c8f129f8209a07f716b0460a`

```python
import hashlib; print(hashlib.sha256(open("datos_procesados/datos_procesados_2024200509B.csv", "rb").read()).hexdigest())
```

## Notas sobre las fuentes

1. **CoinGecko (plan gratuito):** solo entrega los últimos 365 días. Por eso su ventana va del 2026-01-01 al 2026-10-31, y se usa para validar los precios de Yahoo Finance y para medir la capitalización de mercado. Una reejecución posterior a esa ventana puede no obtener todos los días; el crudo entregado y el log acreditan la extracción original (numeral 2.4.5).
2. **Fechado de CoinGecko:** su dato diario corresponde a las 00:00 UTC y se asigna al día anterior para compararlo con el cierre de Yahoo Finance. La mayor diferencia entre ambas fuentes (−3.65 % en BTC y −4.32 % en ETH) se da en un solo día, el 2026-02-22, en los dos activos a la vez.
3. **robots.txt:** `https://estadisticas.bcrp.gob.pe/robots.txt` respondió HTTP 404 el 2026-11-22; el portal no declara restricciones. Se guarda la constancia en `datos_crudos/html_bcrp/robots_txt.txt`.
4. **Dato anómalo de la fuente:** el BCRP publica 22 521.03 para el índice BVL el 2024-06-21 (29 857.57 el día hábil anterior y 30 058.66 el siguiente), tanto en la web como en la API. No se edita: se marca `anomalo_bvl = 1` y se excluye del cálculo de retornos.
5. **Feriados:** el BCRP repite el índice con monto negociado igual a cero o sin monto; esos días tienen `dia_habil_bvl = 0`.
6. **Volumen de criptoactivos:** el volumen de Yahoo Finance es un agregado internacional de plataformas, no un volumen negociado en el Perú.

## Uso de inteligencia artificial

Se usó IA generativa (Claude, de Anthropic) como apoyo para escribir y depurar el código. Las decisiones de diseño, la ejecución, la verificación de los datos y la interpretación son del autor.
