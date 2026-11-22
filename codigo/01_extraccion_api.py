# Autor: Andy Donato Mendoza Flores
# Código de matrícula: 2024200509B
# Tema 72 del temario (Unidad II): Riesgo de los criptoactivos frente a los activos financieros peruanos
# Fecha de extracción: 2026-11-22
"""
01_extraccion_api.py  ·  VÍA 1: CONSUMO DE API

Qué hace este script:
  1. Yahoo Finance (librería yfinance): precios diarios de Bitcoin (BTC-USD) y
     Ethereum (ETH-USD) en dólares, para todo el periodo de estudio.
  2. CoinGecko (API REST, endpoint /coins/{id}/market_chart/range): precio,
     capitalización de mercado y volumen de BTC y ETH en 2026. El plan gratuito
     (Demo) solo entrega los últimos 365 días; por eso su ventana es más corta y
     se usa para validar los precios de Yahoo y para medir la capitalización.
  3. BCRPData (API REST del BCRP): tipo de cambio interbancario venta y tasa de
     referencia de la política monetaria (tasa libre de riesgo en soles).

Todo lo descargado se guarda SIN EDITAR en /datos_crudos.
Cada solicitud queda registrada en log_ejecucion.txt (hora de Lima).
"""

# ---------------------------------------------------------------------------
# Bloque 1. Librerías
# ---------------------------------------------------------------------------
import os
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

# ---------------------------------------------------------------------------
# Bloque 2. Parámetros congelados (no se usan fechas dinámicas tipo "hoy")
# ---------------------------------------------------------------------------
CODIGO_MATRICULA = "2024200509B"

FECHA_INICIO = "2018-01-01"   # inicio del periodo de estudio
FECHA_CORTE = "2026-10-31"    # último día incluido

# Ventana de CoinGecko: el plan Demo solo permite los últimos 365 días.
CG_INICIO = "2026-01-01"
CG_FIN = FECHA_CORTE

# Activos y series que se consultan
TICKERS_YAHOO = {"BTC-USD": "btc", "ETH-USD": "eth"}
MONEDAS_COINGECKO = {"bitcoin": "btc", "ethereum": "eth"}
SERIES_BCRP = {
    "PD04638PD": "tc_venta",          # TC interbancario (S/ por US$) - venta
    "PD12301MD": "tasa_referencia",   # Tasa de referencia de la política monetaria (%)
}

# Ética de la extracción: identificación y pausa entre solicitudes
USER_AGENT = (
    "Mozilla/5.0 (compatible; proyecto-academico-Finanzas-I-UNCP; "
    "contacto: e_2024200509B@uncp.edu.pe)"
)
PAUSA_SEGUNDOS = 1.5
TIMEOUT_SEGUNDOS = 120
REINTENTOS = 3

# Clave Demo de CoinGecko: se lee de una variable de entorno, nunca se escribe aquí
CLAVE_COINGECKO = os.environ.get("COINGECKO_DEMO_API_KEY", "").strip()

# Rutas relativas a la carpeta del proyecto (no rutas de la computadora)
RAIZ = Path(__file__).resolve().parent.parent
DIR_CRUDOS = RAIZ / "datos_crudos"
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"
DIR_CRUDOS.mkdir(parents=True, exist_ok=True)

ZONA_LIMA = ZoneInfo("America/Lima")


# ---------------------------------------------------------------------------
# Bloque 3. Funciones de apoyo
# ---------------------------------------------------------------------------
def escribir_log(mensaje: str) -> None:
    """Escribe una línea en log_ejecucion.txt con la fecha y hora de Lima."""
    marca = datetime.now(ZONA_LIMA).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"{marca} | 01_extraccion_api | {mensaje}"
    print(linea)
    with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def solicitar(url: str, fuente: str, params=None, cabeceras_extra=None):
    """GET con User-Agent, pausa y reintentos. Devuelve la respuesta o None."""
    cabeceras = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if cabeceras_extra:
        cabeceras.update(cabeceras_extra)

    for intento in range(1, REINTENTOS + 1):
        try:
            r = requests.get(url, params=params, headers=cabeceras,
                             timeout=TIMEOUT_SEGUNDOS)
            escribir_log(f"{fuente} | intento {intento} | HTTP {r.status_code} | {r.url}")
            if r.status_code == 200:
                time.sleep(PAUSA_SEGUNDOS)
                return r
            if r.status_code == 429:
                # Demasiadas solicitudes: se espera un minuto antes de reintentar
                escribir_log(f"{fuente} | límite de solicitudes (429): espera de 60 s")
                time.sleep(60)
            else:
                time.sleep(PAUSA_SEGUNDOS * intento)
        except requests.RequestException as error:
            escribir_log(f"{fuente} | intento {intento} | ERROR {type(error).__name__}: {error}")
            time.sleep(PAUSA_SEGUNDOS * intento)
    return None


def a_unix(fecha_texto: str, fin_del_dia: bool = False) -> int:
    """Convierte 'AAAA-MM-DD' a segundos UNIX (UTC)."""
    fecha = datetime.strptime(fecha_texto, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if fin_del_dia:
        fecha = fecha + timedelta(hours=23, minutes=59, seconds=59)
    return int(fecha.timestamp())


resumen = []  # aquí se acumula lo descargado para el cuadro final


# ---------------------------------------------------------------------------
# Bloque 4. Yahoo Finance: BTC-USD y ETH-USD (periodo completo)
# ---------------------------------------------------------------------------
# yfinance trata la fecha 'end' como exclusiva: se suma un día a FECHA_CORTE.
fin_exclusivo = (datetime.strptime(FECHA_CORTE, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

for ticker, alias in TICKERS_YAHOO.items():
    datos = yf.download(ticker, start=FECHA_INICIO, end=fin_exclusivo,
                        interval="1d", auto_adjust=False, actions=False,
                        progress=False)
    # Las versiones recientes devuelven columnas en dos niveles (Precio, Ticker)
    if isinstance(datos.columns, pd.MultiIndex):
        datos.columns = datos.columns.get_level_values(0)
    datos = datos.reset_index()

    archivo = DIR_CRUDOS / f"yahoo_{alias}_usd_{CODIGO_MATRICULA}.csv"
    datos.to_csv(archivo, index=False, encoding="utf-8")
    escribir_log(f"Yahoo Finance | {ticker} | filas={len(datos)} | "
                 f"HTTP no expuesto por yfinance | archivo={archivo.name}")
    resumen.append({"fuente": "Yahoo Finance", "serie": ticker, "filas": len(datos),
                    "desde": str(datos["Date"].min())[:10] if len(datos) else "-",
                    "hasta": str(datos["Date"].max())[:10] if len(datos) else "-",
                    "archivo": archivo.name})
    time.sleep(PAUSA_SEGUNDOS)


# ---------------------------------------------------------------------------
# Bloque 5. CoinGecko: precio, capitalización y volumen (ventana 2026)
# ---------------------------------------------------------------------------
cabecera_cg = {"x-cg-demo-api-key": CLAVE_COINGECKO} if CLAVE_COINGECKO else None
if not CLAVE_COINGECKO:
    escribir_log("CoinGecko | sin clave Demo: se intenta el acceso público (límite más bajo)")

for id_moneda, alias in MONEDAS_COINGECKO.items():
    url = f"https://api.coingecko.com/api/v3/coins/{id_moneda}/market_chart/range"
    parametros = {"vs_currency": "usd",
                  "from": a_unix(CG_INICIO),
                  "to": a_unix(CG_FIN, fin_del_dia=True)}
    respuesta = solicitar(url, f"CoinGecko {id_moneda}", parametros, cabecera_cg)
    if respuesta is None:
        escribir_log(f"CoinGecko | {id_moneda} | NO se obtuvo respuesta válida")
        continue

    contenido = respuesta.json()
    # 5.1 Respaldo literal: el JSON exactamente como lo entregó la API
    (DIR_CRUDOS / f"coingecko_{alias}_{CODIGO_MATRICULA}.json").write_text(
        json.dumps(contenido, ensure_ascii=False), encoding="utf-8")

    # 5.2 Mismos datos en CSV (solo se ponen las tres listas lado a lado)
    tabla = pd.DataFrame({
        "timestamp_ms": [p[0] for p in contenido.get("prices", [])],
        "price": [p[1] for p in contenido.get("prices", [])],
        "market_cap": [p[1] for p in contenido.get("market_caps", [])],
        "total_volume": [p[1] for p in contenido.get("total_volumes", [])],
    })
    archivo = DIR_CRUDOS / f"coingecko_{alias}_{CODIGO_MATRICULA}.csv"
    tabla.to_csv(archivo, index=False, encoding="utf-8")

    fechas = pd.to_datetime(tabla["timestamp_ms"], unit="ms", utc=True)
    escribir_log(f"CoinGecko | {id_moneda} | filas={len(tabla)} | archivo={archivo.name}")
    resumen.append({"fuente": "CoinGecko", "serie": id_moneda, "filas": len(tabla),
                    "desde": str(fechas.min())[:10] if len(tabla) else "-",
                    "hasta": str(fechas.max())[:10] if len(tabla) else "-",
                    "archivo": archivo.name})


# ---------------------------------------------------------------------------
# Bloque 6. BCRPData: una serie por consulta (evita valores desalineados)
# ---------------------------------------------------------------------------
for codigo, alias in SERIES_BCRP.items():
    url = (f"https://estadisticas.bcrp.gob.pe/estadisticas/series/api/"
           f"{codigo}/json/{FECHA_INICIO}/{FECHA_CORTE}/esp")
    respuesta = solicitar(url, f"BCRPData {codigo}")
    if respuesta is None:
        escribir_log(f"BCRPData | {codigo} | NO se obtuvo respuesta válida")
        continue

    # El BCRP a veces antepone un BOM al JSON: se decodifica con utf-8-sig
    contenido = json.loads(respuesta.content.decode("utf-8-sig"))

    # 6.1 Respaldo literal del JSON
    (DIR_CRUDOS / f"bcrp_{codigo}_{CODIGO_MATRICULA}.json").write_text(
        json.dumps(contenido, ensure_ascii=False), encoding="utf-8")

    # 6.2 CSV con el periodo y el valor tal como vienen (texto, sin convertir)
    periodos = contenido.get("periods", [])
    tabla = pd.DataFrame({
        "periodo": [p.get("name") for p in periodos],
        "valor": [p.get("values", [None])[0] for p in periodos],
    })
    archivo = DIR_CRUDOS / f"bcrp_{codigo}_{CODIGO_MATRICULA}.csv"
    tabla.to_csv(archivo, index=False, encoding="utf-8")

    nombre_serie = contenido.get("config", {}).get("series", [{}])[0].get("name", "")
    escribir_log(f"BCRPData | {codigo} ({alias}) | {nombre_serie} | filas={len(tabla)} | "
                 f"archivo={archivo.name}")
    resumen.append({"fuente": "BCRPData", "serie": f"{codigo} ({alias})", "filas": len(tabla),
                    "desde": tabla["periodo"].iloc[0] if len(tabla) else "-",
                    "hasta": tabla["periodo"].iloc[-1] if len(tabla) else "-",
                    "archivo": archivo.name})


# ---------------------------------------------------------------------------
# Bloque 7. Resumen en pantalla para revisar la descarga
# ---------------------------------------------------------------------------
print("\n================ RESUMEN DE LA VÍA 1 (API) ================")
print(pd.DataFrame(resumen).to_string(index=False))
print("\nPrimeras y últimas filas de cada archivo crudo:")
for archivo in sorted(DIR_CRUDOS.glob(f"*_{CODIGO_MATRICULA}.csv")):
    df = pd.read_csv(archivo)
    print(f"\n--- {archivo.name} ---")
    print(df.head(3).to_string(index=False))
    print(df.tail(2).to_string(index=False, header=False))
escribir_log("Fin de la vía 1 (API)")
