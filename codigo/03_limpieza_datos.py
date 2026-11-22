# Autor: Andy Donato Mendoza Flores
# Código de matrícula: 2024200509B
# Tema 72 del temario (Unidad II): Riesgo de los criptoactivos frente a los activos financieros peruanos
# Fecha de extracción: 2026-11-22
"""
03_limpieza_datos.py  ·  DEPURACIÓN Y UNIÓN DE LAS FUENTES

Qué hace este script:
  1. Lee los archivos de /datos_crudos (vía API y vía scraping) sin modificarlos.
  2. Convierte fechas y valores a su tipo correcto ("n.d." pasa a vacío).
  3. Une todas las fuentes por la llave común FECHA (día calendario).
  4. Trata los faltantes:
       - Tipo de cambio y tasa de referencia: en fines de semana y feriados se
         usa el último valor vigente (relleno hacia adelante) y se marca en la
         columna imputado_bcrp = 1.
       - Índice BVL y monto negociado: NO se rellenan; en días sin bolsa
         quedan vacíos y se identifican con dia_habil_bvl = 0. Un día es
         hábil si tiene índice y un monto negociado mayor que cero.
  5. Revisa valores atípicos en los retornos diarios (regla de Tukey, 3 × RIC).
     No se eliminan: son movimientos reales del mercado; solo se informan.
     Excepción: un salto del índice BVL que se revierte al día siguiente es
     un dato erróneo de la fuente; se marca con anomalo_bvl = 1 (sin borrarlo).
  6. Guarda /datos_procesados/datos_procesados_2024200509B.csv y su hash SHA-256.
"""

# ---------------------------------------------------------------------------
# Bloque 1. Librerías
# ---------------------------------------------------------------------------
import hashlib
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Bloque 2. Parámetros congelados y rutas
# ---------------------------------------------------------------------------
CODIGO_MATRICULA = "2024200509B"
FECHA_INICIO = "2018-01-01"
FECHA_CORTE = "2026-10-31"
FACTOR_RIC = 3.0              # umbral de Tukey para "atípico extremo"
UMBRAL_SALTO = 0.10           # salto diario > 10 % en el índice BVL...
TOLERANCIA_REVERSION = 0.01   # ...que se revierte (suma de ambos días < 1 %)

RAIZ = Path(__file__).resolve().parent.parent
DIR_CRUDOS = RAIZ / "datos_crudos"
DIR_PROCESADOS = RAIZ / "datos_procesados"
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"
DIR_PROCESADOS.mkdir(parents=True, exist_ok=True)
ARCHIVO_SALIDA = DIR_PROCESADOS / f"datos_procesados_{CODIGO_MATRICULA}.csv"

ZONA_LIMA = ZoneInfo("America/Lima")

# Abreviaturas de meses que usa el BCRP (septiembre aparece como "Set")
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
         "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12}


# ---------------------------------------------------------------------------
# Bloque 3. Funciones de apoyo
# ---------------------------------------------------------------------------
def escribir_log(mensaje: str) -> None:
    """Escribe una línea en log_ejecucion.txt con la fecha y hora de Lima."""
    marca = datetime.now(ZONA_LIMA).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"{marca} | 03_limpieza_datos | {mensaje}"
    print(linea)
    with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def fecha_bcrp(texto: str):
    """Convierte '03.Ene.18' (API) o '03Ene18' (web) en una fecha."""
    m = re.match(r"^(\d{2})\.?([A-Za-zé]{3})\.?(\d{2})$", str(texto).strip())
    if not m:
        return pd.NaT
    dia, mes, año = int(m.group(1)), MESES.get(m.group(2).lower()), 2000 + int(m.group(3))
    return pd.Timestamp(year=año, month=mes, day=dia) if mes else pd.NaT


def numero(serie: pd.Series) -> pd.Series:
    """Texto a número: 'n.d.' u otro texto no numérico pasa a vacío (NaN)."""
    return pd.to_numeric(serie.astype(str).str.replace(",", "", regex=False).str.strip(),
                         errors="coerce")


def leer_bcrp(nombre_archivo: str, columna: str) -> pd.DataFrame:
    """Lee un CSV crudo del BCRP (API o web) y devuelve [fecha, columna]."""
    crudo = pd.read_csv(DIR_CRUDOS / nombre_archivo, dtype=str)
    tabla = pd.DataFrame({"fecha": crudo["periodo"].map(fecha_bcrp),
                          columna: numero(crudo["valor"])})
    n_sin_fecha = tabla["fecha"].isna().sum()
    if n_sin_fecha:
        escribir_log(f"{nombre_archivo} | {n_sin_fecha} filas con fecha no reconocida (se descartan)")
    tabla = tabla.dropna(subset=["fecha"]).drop_duplicates("fecha", keep="last")
    escribir_log(f"{nombre_archivo} | filas={len(tabla)} | con dato={tabla[columna].notna().sum()} "
                 f"| n.d.={tabla[columna].isna().sum()}")
    return tabla


def leer_yahoo(nombre_archivo: str, alias: str) -> pd.DataFrame:
    """Lee el CSV crudo de Yahoo Finance: precio de cierre y volumen en USD."""
    crudo = pd.read_csv(DIR_CRUDOS / nombre_archivo)
    tabla = pd.DataFrame({
        "fecha": pd.to_datetime(crudo["Date"]).dt.tz_localize(None).dt.normalize(),
        f"precio_{alias}_usd": pd.to_numeric(crudo["Close"], errors="coerce"),
        f"volumen_{alias}_usd": pd.to_numeric(crudo["Volume"], errors="coerce"),
    }).drop_duplicates("fecha", keep="last")
    escribir_log(f"{nombre_archivo} | filas={len(tabla)} | precios vacíos="
                 f"{tabla[f'precio_{alias}_usd'].isna().sum()}")
    return tabla


def leer_coingecko(nombre_archivo: str, alias: str) -> pd.DataFrame:
    """
    Lee el CSV crudo de CoinGecko. Su dato diario está fechado a las 00:00 UTC,
    que equivale al cierre del día anterior; por eso se asigna a fecha - 1 día,
    para que sea comparable con el cierre diario de Yahoo Finance.
    """
    crudo = pd.read_csv(DIR_CRUDOS / nombre_archivo)
    marca_utc = pd.to_datetime(crudo["timestamp_ms"], unit="ms", utc=True)
    tabla = pd.DataFrame({
        "fecha": (marca_utc - pd.Timedelta(days=1)).dt.tz_localize(None).dt.normalize(),
        f"precio_{alias}_cg_usd": pd.to_numeric(crudo["price"], errors="coerce"),
        f"cap_mercado_{alias}_usd": pd.to_numeric(crudo["market_cap"], errors="coerce"),
    }).drop_duplicates("fecha", keep="last")
    escribir_log(f"{nombre_archivo} | filas={len(tabla)} | se fecha como cierre del día anterior")
    return tabla


def atipicos_tukey(retornos: pd.Series):
    """Cuenta retornos fuera de [Q1 - k·RIC, Q3 + k·RIC] y da los 3 más extremos."""
    r = retornos.dropna()
    q1, q3 = r.quantile(0.25), r.quantile(0.75)
    ric = q3 - q1
    fuera = r[(r < q1 - FACTOR_RIC * ric) | (r > q3 + FACTOR_RIC * ric)]
    extremos = r.reindex(r.abs().sort_values(ascending=False).index[:3])
    return len(r), len(fuera), extremos


# ---------------------------------------------------------------------------
# Bloque 4. Lectura de las fuentes crudas
# ---------------------------------------------------------------------------
escribir_log("Inicio de la limpieza")

# 4.1 Vía API: Yahoo Finance (criptoactivos, periodo completo)
btc = leer_yahoo(f"yahoo_btc_usd_{CODIGO_MATRICULA}.csv", "btc")
eth = leer_yahoo(f"yahoo_eth_usd_{CODIGO_MATRICULA}.csv", "eth")

# 4.2 Vía API: CoinGecko (2026: validación de precios y capitalización)
cg_btc = leer_coingecko(f"coingecko_btc_{CODIGO_MATRICULA}.csv", "btc")
cg_eth = leer_coingecko(f"coingecko_eth_{CODIGO_MATRICULA}.csv", "eth")

# 4.3 Vía API: BCRPData (tipo de cambio y tasa de referencia)
tc = leer_bcrp(f"bcrp_PD04638PD_{CODIGO_MATRICULA}.csv", "tc_venta")
tasa = leer_bcrp(f"bcrp_PD12301MD_{CODIGO_MATRICULA}.csv", "tasa_referencia")

# 4.4 Vía scraping: páginas web de BCRPData (Bolsa de Valores de Lima)
bvl = leer_bcrp(f"bcrp_html_PD38026MD_{CODIGO_MATRICULA}.csv", "indice_bvl")
monto = leer_bcrp(f"bcrp_html_PD04696MD_{CODIGO_MATRICULA}.csv", "monto_negociado_bvl")


# ---------------------------------------------------------------------------
# Bloque 5. Unión por la llave común: fecha (calendario diario completo)
# ---------------------------------------------------------------------------
calendario = pd.DataFrame({"fecha": pd.date_range(FECHA_INICIO, FECHA_CORTE, freq="D")})
base = calendario
for tabla in [btc, eth, tc, tasa, bvl, monto, cg_btc, cg_eth]:
    base = base.merge(tabla, on="fecha", how="left")

# Control: solo se conserva el periodo declarado.
# (Con el desfase, CoinGecko cubre del 31-12-2025 al 30-10-2026.)
base = base[(base["fecha"] >= FECHA_INICIO) & (base["fecha"] <= FECHA_CORTE)].copy()
escribir_log(f"Unión por fecha | filas={len(base)} (días calendario {FECHA_INICIO} a {FECHA_CORTE})")


# ---------------------------------------------------------------------------
# Bloque 6. Tratamiento de faltantes
# ---------------------------------------------------------------------------
# 6.1 Día hábil de la bolsa: día de semana con índice publicado y monto negociado
#     mayor que cero. En los feriados el BCRP repite el índice con monto = 0
#     (o sin monto), así que esos días no cuentan como sesión bursátil.
base["dia_habil_bvl"] = (base["fecha"].dt.weekday < 5) & base["indice_bvl"].notna() \
    & (base["monto_negociado_bvl"] > 0)
base["dia_habil_bvl"] = base["dia_habil_bvl"].astype(int)

con_indice = base["indice_bvl"].notna()
sin_monto = con_indice & base["monto_negociado_bvl"].isna()
monto_cero = con_indice & (base["monto_negociado_bvl"] == 0)
escribir_log(f"Días con índice BVL pero sin monto (feriados): {sin_monto.sum()} | "
             f"con monto = 0 (feriados): {monto_cero.sum()} -> no son días hábiles")
sin_cambio = (base.loc[base["dia_habil_bvl"] == 1, "indice_bvl"].diff() == 0)
escribir_log(f"Días hábiles con índice BVL idéntico al anterior: {sin_cambio.sum()} "
             f"{[d.strftime('%Y-%m-%d') for d in base.loc[sin_cambio[sin_cambio].index, 'fecha']]}")

# 6.2 Tipo de cambio y tasa: último valor vigente (solo hacia adelante)
faltaba = base["tc_venta"].isna() | base["tasa_referencia"].isna()
base["tc_venta"] = base["tc_venta"].ffill()
base["tasa_referencia"] = base["tasa_referencia"].ffill()
base["imputado_bcrp"] = (faltaba & base["tc_venta"].notna()).astype(int)
escribir_log(f"TC y tasa rellenados con el último valor vigente: {base['imputado_bcrp'].sum()} días "
             f"| quedan vacíos al inicio: {base['tc_venta'].isna().sum()}")

# 6.3 Criptoactivos en soles (precio en USD × tipo de cambio venta)
base["precio_btc_pen"] = base["precio_btc_usd"] * base["tc_venta"]
base["precio_eth_pen"] = base["precio_eth_usd"] * base["tc_venta"]

# 6.4 Dato anómalo de la fuente en el índice BVL.
#     Regla objetiva: el retorno de un día hábil supera UMBRAL_SALTO en valor
#     absoluto y al día hábil siguiente se revierte casi por completo
#     (la suma de ambos retornos es menor que TOLERANCIA_REVERSION).
#     El valor NO se borra (se conserva igual a la fuente); solo se marca con
#     anomalo_bvl = 1 para que 04_analisis.py lo excluya al calcular retornos.
habiles_idx = base.index[base["dia_habil_bvl"] == 1]
r_bvl = np.log(base.loc[habiles_idx, "indice_bvl"]).diff()
r_sig = r_bvl.shift(-1)
es_anomalo = (r_bvl.abs() > UMBRAL_SALTO) & (np.sign(r_bvl) != np.sign(r_sig)) \
    & ((r_bvl + r_sig).abs() < TOLERANCIA_REVERSION)
base["anomalo_bvl"] = 0
base.loc[es_anomalo[es_anomalo].index, "anomalo_bvl"] = 1
for i in es_anomalo[es_anomalo].index:
    escribir_log(f"Dato anómalo de la fuente | {base.loc[i, 'fecha']:%Y-%m-%d} | "
                 f"índice={base.loc[i, 'indice_bvl']} | retorno={r_bvl[i]:+.2%} | "
                 f"retorno del día hábil siguiente={r_sig[i]:+.2%} | se marca anomalo_bvl=1")
escribir_log(f"Días marcados como anomalo_bvl: {base['anomalo_bvl'].sum()}")


# ---------------------------------------------------------------------------
# Bloque 7. Revisión de valores atípicos en retornos logarítmicos diarios
# ---------------------------------------------------------------------------
habiles = base[(base["dia_habil_bvl"] == 1) & (base["anomalo_bvl"] == 0)]
retornos = {
    "BTC (USD, diario)": np.log(base["precio_btc_usd"]).diff(),
    "ETH (USD, diario)": np.log(base["precio_eth_usd"]).diff(),
    "Índice BVL (días hábiles)": np.log(habiles["indice_bvl"]).diff().set_axis(habiles["fecha"]),
    "TC venta (días hábiles)": np.log(habiles["tc_venta"]).diff().set_axis(habiles["fecha"]),
}
retornos["BTC (USD, diario)"].index = base["fecha"]
retornos["ETH (USD, diario)"].index = base["fecha"]

print("\n------ Atípicos extremos (Tukey, 3 × RIC): se conservan ------")
for nombre, r in retornos.items():
    n, n_fuera, extremos = atipicos_tukey(r)
    detalle = ", ".join(f"{f:%Y-%m-%d}: {v:+.2%}" for f, v in extremos.items())
    escribir_log(f"Atípicos | {nombre} | {n_fuera} de {n} ({n_fuera / n:.2%}) | más extremos: {detalle}")


# ---------------------------------------------------------------------------
# Bloque 8. Orden de columnas, guardado y hash SHA-256
# ---------------------------------------------------------------------------
columnas = ["fecha", "dia_habil_bvl",
            "precio_btc_usd", "precio_eth_usd", "volumen_btc_usd", "volumen_eth_usd",
            "tc_venta", "tasa_referencia", "imputado_bcrp",
            "precio_btc_pen", "precio_eth_pen",
            "indice_bvl", "monto_negociado_bvl", "anomalo_bvl",
            "precio_btc_cg_usd", "cap_mercado_btc_usd",
            "precio_eth_cg_usd", "cap_mercado_eth_usd"]
base = base[columnas].sort_values("fecha").reset_index(drop=True)
base["fecha"] = base["fecha"].dt.strftime("%Y-%m-%d")
base.to_csv(ARCHIVO_SALIDA, index=False, encoding="utf-8", float_format="%.6f")

sha256 = hashlib.sha256(ARCHIVO_SALIDA.read_bytes()).hexdigest()
(DIR_PROCESADOS / "hash_sha256.txt").write_text(
    f"{ARCHIVO_SALIDA.name}  SHA-256: {sha256}\n", encoding="utf-8")
escribir_log(f"Guardado {ARCHIVO_SALIDA.name} | filas={len(base)} | columnas={base.shape[1]} "
             f"| SHA-256={sha256}")


# ---------------------------------------------------------------------------
# Bloque 9. Resumen en pantalla
# ---------------------------------------------------------------------------
print("\n================ RESUMEN DE LA BASE PROCESADA ================")
print(f"Filas: {len(base)} | Columnas: {base.shape[1]} | Periodo: {base['fecha'].iloc[0]} a {base['fecha'].iloc[-1]}")
print(f"Días hábiles BVL: {base['dia_habil_bvl'].sum()} | "
      f"Días con BTC, ETH, TC e índice BVL a la vez: "
      f"{base[['precio_btc_usd', 'precio_eth_usd', 'tc_venta', 'indice_bvl']].dropna().shape[0]}")
print("\nDatos disponibles por columna:")
print(base.notna().sum().to_string())
print("\nPrimeras filas:")
print(base.head(3).T.to_string())
print("\nÚltimas filas:")
print(base.tail(3).T.to_string())

# Validación cruzada rápida Yahoo vs CoinGecko (días comunes de 2026)
for alias in ["btc", "eth"]:
    par = base[[f"precio_{alias}_usd", f"precio_{alias}_cg_usd"]].dropna()
    dif = (par[f"precio_{alias}_cg_usd"] / par[f"precio_{alias}_usd"] - 1).abs()
    print(f"\n{alias.upper()}: Yahoo vs CoinGecko | días={len(par)} | "
          f"diferencia absoluta media={dif.mean():.3%} | máxima={dif.max():.3%} | "
          f"correlación={par.corr().iloc[0, 1]:.5f}")
escribir_log("Fin de la limpieza")
