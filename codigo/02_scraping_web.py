# Autor: Andy Donato Mendoza Flores
# Código de matrícula: 2024200509B
# Tema 72 del temario (Unidad II): Riesgo de los criptoactivos frente a los activos financieros peruanos
# Fecha de extracción: 2026-11-22 (índice y monto BVL) · 2026-11-26 (tipo de cambio)
"""
02_scraping_web.py  ·  VÍA 2: WEB SCRAPING

Qué hace este script:
  Rastrea las páginas HTML de resultados de BCRPData (portal web del BCRP) y
  extrae, con BeautifulSoup, la tabla de datos de tres series diarias:
    - PD38026MD: índice S&P/BVL Perú General (antes IGBVL), nivel del índice
    - PD04696MD: Monto negociado en acciones de la BVL (millones de S/)
    - PD04638PD: Tipo de cambio interbancario, venta (S/ por US$). Esta serie
      también se obtiene por la API en 01_extraccion_api.py: así el tipo de
      cambio llega por las dos vías y se comparan los valores.

  Uso:
    python codigo/02_scraping_web.py              -> rastrea las tres series
    python codigo/02_scraping_web.py PD04638PD    -> rastrea solo las series indicadas

  Paginación: el periodo se pide año por año (una página por año y serie),
  con una pausa entre solicitudes para no cargar el servidor.
  Antes de rastrear se lee el robots.txt del portal.
  Selectores usados: td.periodo (fecha, p. ej. "01Ene18") y td.dato (valor).

Evidencia que se guarda en /datos_crudos (sin editar):
  - html_bcrp/robots_txt.txt          copia del robots.txt leído
  - html_bcrp/<serie>_<año>.html      cada página tal como llegó
  - bcrp_html_<serie>_<código>.csv    filas extraídas (texto original)
"""

# ---------------------------------------------------------------------------
# Bloque 1. Librerías
# ---------------------------------------------------------------------------
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Bloque 2. Parámetros congelados
# ---------------------------------------------------------------------------
CODIGO_MATRICULA = "2024200509B"
FECHA_INICIO = "2018-01-01"
FECHA_CORTE = "2026-10-31"

SERIES_HTML = {
    "PD38026MD": "indice_bvl",       # Índice S&P/BVL Perú General (antes IGBVL)
    "PD04696MD": "monto_negociado",  # Monto negociado en acciones (millones S/)
    "PD04638PD": "tc_venta_html",    # Tipo de cambio interbancario venta (S/ por US$)
}

# Series a rastrear en esta ejecución: todas, o solo las que se indiquen al llamar
# al script (por ejemplo: python codigo/02_scraping_web.py PD04638PD)
SERIES_A_RASTREAR = [s.upper() for s in sys.argv[1:]] or list(SERIES_HTML)
desconocidas = [s for s in SERIES_A_RASTREAR if s not in SERIES_HTML]
if desconocidas:
    raise SystemExit(f"Series no declaradas en SERIES_HTML: {desconocidas}")

DOMINIO = "https://estadisticas.bcrp.gob.pe"
PLANTILLA_URL = DOMINIO + "/estadisticas/series/diarias/resultados/{codigo}/html/{inicio}/{fin}/"

USER_AGENT = (
    "Mozilla/5.0 (compatible; proyecto-academico-Finanzas-I-UNCP; "
    "contacto: e_2024200509B@uncp.edu.pe)"
)
PAUSA_SEGUNDOS = 1.5
TIMEOUT_SEGUNDOS = 120
REINTENTOS = 3

# Patrón de las fechas diarias en la página HTML del BCRP, por ejemplo "03Ene18"
# (en la API vienen como "03.Ene.18"; en la web, sin puntos)
PATRON_FECHA = re.compile(r"^\d{2}[A-Za-zé]{3}\d{2}$")

RAIZ = Path(__file__).resolve().parent.parent
DIR_CRUDOS = RAIZ / "datos_crudos"
DIR_HTML = DIR_CRUDOS / "html_bcrp"
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"
DIR_HTML.mkdir(parents=True, exist_ok=True)

ZONA_LIMA = ZoneInfo("America/Lima")
CABECERAS = {"User-Agent": USER_AGENT, "Accept": "text/html"}


# ---------------------------------------------------------------------------
# Bloque 3. Funciones de apoyo
# ---------------------------------------------------------------------------
def escribir_log(mensaje: str) -> None:
    """Escribe una línea en log_ejecucion.txt con la fecha y hora de Lima."""
    marca = datetime.now(ZONA_LIMA).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"{marca} | 02_scraping_web | {mensaje}"
    print(linea)
    with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def descargar(url: str, etiqueta: str):
    """GET con User-Agent, pausa y reintentos. Devuelve la respuesta o None."""
    for intento in range(1, REINTENTOS + 1):
        try:
            r = requests.get(url, headers=CABECERAS, timeout=TIMEOUT_SEGUNDOS)
            escribir_log(f"{etiqueta} | intento {intento} | HTTP {r.status_code} | {url}")
            time.sleep(PAUSA_SEGUNDOS)
            if r.status_code == 200:
                return r
        except requests.RequestException as error:
            escribir_log(f"{etiqueta} | intento {intento} | ERROR {type(error).__name__}: {error}")
            time.sleep(PAUSA_SEGUNDOS * intento)
    return None


def paginas_por_año(inicio: str, corte: str):
    """Divide el periodo en tramos anuales: [(año, fecha_ini, fecha_fin), ...]."""
    año_ini, año_fin = int(inicio[:4]), int(corte[:4])
    tramos = []
    for año in range(año_ini, año_fin + 1):
        ini = inicio if año == año_ini else f"{año}-01-01"
        fin = corte if año == año_fin else f"{año}-12-31"
        tramos.append((año, ini, fin))
    return tramos


def extraer_filas(html: str):
    """
    Extrae (periodo, valor) de la tabla de resultados del BCRP.
    En el HTML cada fila tiene dos celdas:
        <td class="periodo"><b>01Ene18</b></td>  <td class="dato"> 19974.4 </td>
    Se busca cada celda td.periodo y se toma la celda td.dato que le sigue.
    (No se recorre por <table>, porque el HTML trae tablas anidadas y el
    analizador corta la tabla 'series' antes de tiempo.)
    """
    sopa = BeautifulSoup(html, "html.parser")
    datos = []
    for celda_fecha in sopa.select("td.periodo"):
        celda_valor = celda_fecha.find_next("td", class_="dato")
        if celda_valor is None:
            continue
        periodo = celda_fecha.get_text(strip=True)
        valor = celda_valor.get_text(strip=True)
        if PATRON_FECHA.match(periodo):
            datos.append((periodo, valor))
    return datos, "td.periodo + td.dato", len(sopa.find_all("table"))


# ---------------------------------------------------------------------------
# Bloque 4. Revisión del robots.txt antes de rastrear
# ---------------------------------------------------------------------------
url_robots = DOMINIO + "/robots.txt"
lector = RobotFileParser()
permitido = True
try:
    r = requests.get(url_robots, headers=CABECERAS, timeout=TIMEOUT_SEGUNDOS)
    escribir_log(f"robots.txt | HTTP {r.status_code} | {url_robots}")
    (DIR_HTML / "robots_txt.txt").write_text(
        f"# Consultado: {datetime.now(ZONA_LIMA):%Y-%m-%d %H:%M:%S} (Lima) | HTTP {r.status_code}\n"
        + r.text, encoding="utf-8")
    if r.status_code == 200:
        lector.parse(r.text.splitlines())
        url_prueba = PLANTILLA_URL.format(codigo="PD38026MD", inicio="2018-01-01", fin="2018-12-31")
        permitido = lector.can_fetch(USER_AGENT, url_prueba)
    else:
        escribir_log("robots.txt | no publicado: no hay restricciones declaradas")
except requests.RequestException as error:
    escribir_log(f"robots.txt | ERROR {type(error).__name__}: {error}")

escribir_log(f"robots.txt | ¿rastreo permitido para la ruta de resultados?: {permitido}")
if not permitido:
    escribir_log("Rastreo NO permitido por robots.txt: se detiene el script (numeral 2.4.3)")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Bloque 5. Rastreo página por página (serie × año)
# ---------------------------------------------------------------------------
escribir_log(f"Series a rastrear en esta ejecución: {SERIES_A_RASTREAR}")
resumen = []
for codigo in SERIES_A_RASTREAR:
    alias = SERIES_HTML[codigo]
    filas_serie = []
    for año, ini, fin in paginas_por_año(FECHA_INICIO, FECHA_CORTE):
        url = PLANTILLA_URL.format(codigo=codigo, inicio=ini, fin=fin)
        respuesta = descargar(url, f"BCRP HTML {codigo} {año}")
        if respuesta is None:
            escribir_log(f"BCRP HTML {codigo} {año} | página NO descargada")
            continue

        # 5.1 Se guarda la página completa, tal como llegó
        respuesta.encoding = respuesta.apparent_encoding or "utf-8"
        (DIR_HTML / f"{codigo}_{año}.html").write_text(respuesta.text, encoding="utf-8")

        # 5.2 Se extraen las filas de la tabla
        filas, selector, n_tablas = extraer_filas(respuesta.text)
        escribir_log(f"BCRP HTML {codigo} {año} | tablas={n_tablas} | selector={selector} | "
                     f"filas={len(filas)}")
        if not filas:
            # Diagnóstico: se muestra el inicio del texto visible de la página
            texto = BeautifulSoup(respuesta.text, "html.parser").get_text(" ", strip=True)
            print(f"   [diagnóstico] texto de la página: {texto[:600]}")
        for periodo, valor in filas:
            filas_serie.append({"periodo": periodo, "valor": valor, "pagina": año, "url": url})

    # 5.3 CSV crudo de la serie (texto original, sin convertir)
    tabla = pd.DataFrame(filas_serie, columns=["periodo", "valor", "pagina", "url"])
    archivo = DIR_CRUDOS / f"bcrp_html_{codigo}_{CODIGO_MATRICULA}.csv"
    tabla.to_csv(archivo, index=False, encoding="utf-8")
    escribir_log(f"BCRP HTML {codigo} ({alias}) | filas totales={len(tabla)} | archivo={archivo.name}")
    resumen.append({"serie": f"{codigo} ({alias})", "filas": len(tabla),
                    "desde": tabla["periodo"].iloc[0] if len(tabla) else "-",
                    "hasta": tabla["periodo"].iloc[-1] if len(tabla) else "-",
                    "n.d.": int((tabla["valor"] == "n.d.").sum()) if len(tabla) else 0,
                    "archivo": archivo.name})


# ---------------------------------------------------------------------------
# Bloque 6. Resumen en pantalla
# ---------------------------------------------------------------------------
print("\n============== RESUMEN DE LA VÍA 2 (SCRAPING) ==============")
print(pd.DataFrame(resumen).to_string(index=False))
for codigo in SERIES_A_RASTREAR:
    archivo = DIR_CRUDOS / f"bcrp_html_{codigo}_{CODIGO_MATRICULA}.csv"
    df = pd.read_csv(archivo)
    print(f"\n--- {archivo.name} ---")
    print(df[["periodo", "valor", "pagina"]].head(3).to_string(index=False))
    print(df[["periodo", "valor", "pagina"]].tail(2).to_string(index=False, header=False))
escribir_log("Fin de la vía 2 (scraping)")
