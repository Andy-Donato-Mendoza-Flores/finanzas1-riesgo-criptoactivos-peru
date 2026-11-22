# Autor: Andy Donato Mendoza Flores
# Código de matrícula: 2024200509B
# Tema 72 del temario (Unidad II): Riesgo de los criptoactivos frente a los activos financieros peruanos
# Fecha de extracción: 2026-11-22
"""
04_analisis.py  ·  TABLAS Y FIGURAS DEL ARTÍCULO

Lee SOLO /datos_procesados/datos_procesados_2024200509B.csv y genera en /salidas:
  Tablas (.csv)
    tabla1_descriptivos        estadísticos, Jarque-Bera y Dickey-Fuller aumentada
    tabla2_riesgo_retorno      retorno y volatilidad anualizados, Sharpe, VaR, CVaR, drawdown
    tabla3_correlaciones       Pearson y Spearman entre criptoactivos, BVL y tipo de cambio
    tabla4_capm                CAPM de BTC y ETH frente al índice BVL (errores Newey-West)
    tabla5_beta_subperiodos    estabilidad de la beta por subperiodos
    tabla6_diversificacion     portafolio BVL con una fracción de BTC o ETH
    tabla7_validacion_coingecko  Yahoo Finance vs CoinGecko y capitalización (2026)
    tabla8_liquidez_anual      monto negociado en la BVL vs volumen de BTC y ETH
    tabla9_igualdad_varianzas  prueba de Levene (Brown-Forsythe)
  Figuras
    figura1 a figura8 (PNG a 300 dpi y PDF vectorial)

Muestra común: días hábiles de la BVL (dia_habil_bvl = 1) sin el dato anómalo
de la fuente (anomalo_bvl = 0). Los retornos de los criptoactivos se miden entre
dos días hábiles consecutivos (incluyen lo ocurrido en fines de semana y feriados).
No se usa aleatoriedad, por lo que no se requiere semilla.
"""

# ---------------------------------------------------------------------------
# Bloque 1. Librerías
# ---------------------------------------------------------------------------
import hashlib
import warnings
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")                     # dibuja sin abrir ventanas
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.font_manager
from matplotlib.transforms import blended_transform_factory
from scipy import stats
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Bloque 2. Parámetros congelados, rutas y estilo de las figuras
# ---------------------------------------------------------------------------
CODIGO_MATRICULA = "2024200509B"
FECHA_INICIO = "2018-01-01"
FECHA_CORTE = "2026-10-31"

NIVELES_VAR = [0.95, 0.99]      # niveles de confianza del VaR y CVaR
VENTANA_VOL = 63                # ≈ 3 meses de días hábiles (volatilidad móvil)
VENTANA_CORR = 126              # ≈ 6 meses (correlación móvil)
VENTANA_BETA = 252              # ≈ 1 año (beta móvil)
REZAGOS_NW = 5                  # rezagos de los errores Newey-West (≈ 1 semana)
PESOS_CRIPTO = [0.00, 0.01, 0.02, 0.05, 0.10, 0.20]
SUBPERIODOS = [("2018-2019", "2018-01-01", "2019-12-31"),
               ("2020-2021", "2020-01-01", "2021-12-31"),
               ("2022-2023", "2022-01-01", "2023-12-31"),
               ("2024-2026", "2024-01-01", FECHA_CORTE)]

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_BASE = RAIZ / "datos_procesados" / f"datos_procesados_{CODIGO_MATRICULA}.csv"
ARCHIVO_HASH = RAIZ / "datos_procesados" / "hash_sha256.txt"
DIR_SALIDAS = RAIZ / "salidas"
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"
DIR_SALIDAS.mkdir(parents=True, exist_ok=True)
ZONA_LIMA = ZoneInfo("America/Lima")

# Un color fijo por activo (el mismo en todas las figuras; paleta validada
# para daltonismo). Los textos van en tinta gris, nunca en el color de la serie.
COLORES = {"Índice BVL": "#2a78d6", "BTC (S/)": "#eb6834",
           "ETH (S/)": "#1baf7a", "TC (S/ por US$)": "#eda100"}
TINTA, TINTA_2, TINTA_3 = "#1a1a19", "#52514e", "#898781"   # títulos, ejes, notas
GRILLA, EJE = "#e1e0d9", "#a8a79f"

# Eventos de referencia marcados en las series de tiempo
MOSTRAR_EVENTOS = True
EVENTOS = [("A", "2020-03-11", "la OMS declara la pandemia de COVID-19"),
           ("B", "2022-11-11", "FTX se declara en quiebra"),
           ("C", "2024-01-10", "la SEC de EE. UU. aprueba los ETF de bitcoin al contado")]
MESES_ABR = ["ene", "feb", "mar", "abr", "may", "jun",
             "jul", "ago", "set", "oct", "nov", "dic"]

# Fuente sans-serif: se usa la primera disponible en la computadora
_disponibles = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
FUENTE = next((f for f in ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]
               if f in _disponibles), "DejaVu Sans")
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": [FUENTE],
    "font.size": 8.5, "axes.titlesize": 9.5, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.titlecolor": TINTA, "axes.titlepad": 22,
    "axes.edgecolor": EJE, "axes.linewidth": 0.8, "axes.labelcolor": TINTA_2,
    "axes.labelsize": 8, "xtick.color": TINTA_2, "ytick.color": TINTA_2,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "xtick.major.size": 3,
    "xtick.major.width": 0.8, "ytick.major.size": 0, "ytick.major.pad": 4,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRILLA,
    "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "legend.frameon": False, "legend.fontsize": 8, "legend.handlelength": 1.8,
    "lines.linewidth": 1.3, "lines.solid_capstyle": "round",
    "figure.facecolor": "white", "axes.facecolor": "white",
    "pdf.fonttype": 42,          # letras incrustadas como texto en el PDF
})
ANCHO = 6.5                      # pulgadas (≈ 16.5 cm, ancho de página del artículo)


# ---------------------------------------------------------------------------
# Bloque 3. Funciones de apoyo
# ---------------------------------------------------------------------------
def escribir_log(mensaje: str) -> None:
    """Escribe una línea en log_ejecucion.txt con la fecha y hora de Lima."""
    marca = datetime.now(ZONA_LIMA).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"{marca} | 04_analisis | {mensaje}"
    print(linea)
    with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def guardar_tabla(tabla: pd.DataFrame, nombre: str, titulo: str) -> None:
    """Guarda la tabla en /salidas y la muestra redondeada en pantalla."""
    tabla.to_csv(DIR_SALIDAS / f"{nombre}.csv", encoding="utf-8", float_format="%.6f")
    print(f"\n=== {titulo} ===")
    print(tabla.round(4).to_string())
    escribir_log(f"Tabla guardada: {nombre}.csv | filas={len(tabla)}")


def guardar_figura(fig, nombre: str) -> None:
    """Guarda la figura en /salidas: PNG a 300 dpi y PDF vectorial (para LaTeX)."""
    for extension in ["png", "pdf"]:
        fig.savefig(DIR_SALIDAS / f"{nombre}.{extension}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    escribir_log(f"Figura guardada: {nombre}.png y {nombre}.pdf")


def eje_fechas(ax) -> None:
    """Marcas anuales en el eje de fechas."""
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def fecha_corta(valor) -> str:
    """Fecha en formato 'dic-18' (meses en español)."""
    f = pd.Timestamp(valor)
    return f"{MESES_ABR[f.month - 1]}-{f:%y}"


def encabezado(ax, unidades: str, leyenda: bool = True, ncol: int = 4) -> None:
    """Leyenda en una fila arriba y, debajo, la unidad de medida (estilo de informe)."""
    ax.text(0, 1.02, unidades, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=8, color=TINTA_2)
    if leyenda:
        ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.08), ncol=ncol,
                  columnspacing=1.4, handletextpad=0.5, borderaxespad=0)


def marcar_eventos(ax) -> None:
    """Línea vertical punteada y una letra (A, B, C) por evento; la letra se
    explica en la nota de la figura en el artículo."""
    if not MOSTRAR_EVENTOS:
        return
    if ax.get_yscale() == "linear":                   # aire arriba para las letras
        bajo, alto = ax.get_ylim()
        ax.set_ylim(bajo, alto + 0.10 * (alto - bajo))
    trans = blended_transform_factory(ax.transData, ax.transAxes)
    for letra, fecha, _ in EVENTOS:
        x = pd.Timestamp(fecha)
        ax.axvline(x, color=TINTA_3, lw=0.7, ls=(0, (2, 2)), zorder=1)
        ax.text(x, 0.985, letra, transform=trans, ha="center", va="top", fontsize=7,
                fontweight="bold", color=TINTA_2, zorder=5,
                bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec=TINTA_3, lw=0.6))


def rotulos_finales(ax, series: dict, formato: str = "{:,.0f}", separacion_pt: float = 9) -> None:
    """Punto en el último dato de cada serie y su valor a la derecha.
    Si dos rótulos quedan muy juntos, se separan verticalmente."""
    fig = ax.figure
    fig.canvas.draw()
    puntos = []
    for color, serie in series.items():
        x, y = serie.index[-1], serie.iloc[-1]
        ax.plot([x], [y], "o", ms=3.5, color=color, mec="white", mew=0.8, zorder=4)
        y_px = ax.transData.transform((mdates.date2num(x), y))[1]
        puntos.append([y_px, x, y, formato.format(y).replace(",", " ")])
    puntos.sort(key=lambda p: p[0])
    paso = separacion_pt * fig.dpi / 72
    for i in range(1, len(puntos)):
        if puntos[i][0] - puntos[i - 1][0] < paso:
            puntos[i][0] = puntos[i - 1][0] + paso
    for y_px, x, y, texto in puntos:
        y_obj_px = ax.transData.transform((mdates.date2num(x), y))[1]
        ax.annotate(texto, (x, y), xytext=(6, (y_px - y_obj_px) * 72 / fig.dpi),
                    textcoords="offset points", va="center", fontsize=7.5, color=TINTA_2)


def rotulo_minimo(ax, serie: pd.Series) -> None:
    """Marca el punto mínimo con su valor y fecha, sin salirse del panel."""
    f_min, v_min = serie.idxmin(), serie.min()
    mitad = serie.index[0] + (serie.index[-1] - serie.index[0]) / 2
    a_la_izquierda = f_min > mitad
    ax.annotate(f"{v_min:.1f} % ({fecha_corta(f_min)})".replace("-", "−", 1), (f_min, v_min),
                xytext=(-7 if a_la_izquierda else 7, 0), textcoords="offset points",
                ha="right" if a_la_izquierda else "left", va="center", fontsize=7.5,
                color=TINTA, zorder=6,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))


def linea_referencia(ax, y: float, rotulo: str = "") -> None:
    """Línea horizontal de referencia (0 o 1) con rótulo opcional a la izquierda."""
    ax.axhline(y, color=TINTA_2, lw=0.8, zorder=2)
    if rotulo:
        trans = blended_transform_factory(ax.transAxes, ax.transData)
        ax.text(0.005, y, rotulo, transform=trans, ha="left", va="bottom",
                fontsize=7, color=TINTA_2)


def max_drawdown(r: pd.Series):
    """Máxima caída desde un máximo previo (en %), y la fecha del punto más bajo."""
    valor = np.exp(r.cumsum())
    caida = valor / valor.cummax() - 1
    return caida.min() * 100, caida.idxmin(), caida


def capm(y: pd.Series, x: pd.Series) -> dict:
    """MCO de y = alfa + beta·x con errores Newey-West (HAC)."""
    modelo = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HAC",
                                               cov_kwds={"maxlags": REZAGOS_NW})
    alfa, beta = modelo.params.iloc[0], modelo.params.iloc[1]
    ee_beta = modelo.bse.iloc[1]
    t_beta_uno = (beta - 1) / ee_beta
    return {"alfa_diario_%": alfa * 100,
            "alfa_anual_%": alfa * FACTOR_ANUAL * 100,
            "p_alfa": modelo.pvalues.iloc[0],
            "beta": beta, "ee_beta_NW": ee_beta,
            "t_beta": modelo.tvalues.iloc[1], "p_beta=0": modelo.pvalues.iloc[1],
            "p_beta=1": 2 * (1 - stats.norm.cdf(abs(t_beta_uno))),
            "R2": modelo.rsquared, "N": int(modelo.nobs)}


# ---------------------------------------------------------------------------
# Bloque 4. Lectura de la base procesada y verificación del hash
# ---------------------------------------------------------------------------
escribir_log("Inicio del análisis")
sha_actual = hashlib.sha256(ARCHIVO_BASE.read_bytes()).hexdigest()
sha_declarado = ARCHIVO_HASH.read_text(encoding="utf-8").split("SHA-256:")[-1].strip() \
    if ARCHIVO_HASH.exists() else "no disponible"
escribir_log(f"SHA-256 de la base: {sha_actual} | coincide con hash_sha256.txt: "
             f"{sha_actual == sha_declarado}")

base = pd.read_csv(ARCHIVO_BASE, parse_dates=["fecha"])


# ---------------------------------------------------------------------------
# Bloque 5. Muestra común y retornos logarítmicos
# ---------------------------------------------------------------------------
comun = base[(base["dia_habil_bvl"] == 1) & (base["anomalo_bvl"] == 0)].set_index("fecha")
precios = pd.DataFrame({
    "BTC (S/)": comun["precio_btc_pen"],
    "ETH (S/)": comun["precio_eth_pen"],
    "Índice BVL": comun["indice_bvl"],
    "TC (S/ por US$)": comun["tc_venta"],
    "BTC (US$)": comun["precio_btc_usd"],
    "ETH (US$)": comun["precio_eth_usd"],
}).dropna()
R = np.log(precios).diff().dropna()                 # retornos logarítmicos
ACTIVOS_PEN = ["BTC (S/)", "ETH (S/)", "Índice BVL", "TC (S/ por US$)"]

# Tasa libre de riesgo: tasa de referencia del BCRP del día hábil anterior,
# proporcional a los días calendario transcurridos entre observaciones.
dias = precios.index.to_series().diff().dt.days.reindex(R.index)
tasa_previa = comun["tasa_referencia"].reindex(precios.index).shift(1).reindex(R.index)
rf = np.log1p(tasa_previa / 100) * dias / 365
EXCESO = R[ACTIVOS_PEN].sub(rf, axis=0)

AÑOS = (R.index[-1] - R.index[0]).days / 365.25
FACTOR_ANUAL = len(R) / AÑOS                        # observaciones por año
escribir_log(f"Muestra común: {len(R)} retornos | {R.index[0]:%Y-%m-%d} a {R.index[-1]:%Y-%m-%d} "
             f"| {AÑOS:.2f} años | factor de anualización = {FACTOR_ANUAL:.2f} obs/año")


# ---------------------------------------------------------------------------
# Bloque 6. Tabla 1: estadísticos descriptivos y pruebas
# ---------------------------------------------------------------------------
filas = {}
for activo in R.columns:
    r = R[activo]
    jb = stats.jarque_bera(r)
    adf = adfuller(r, autolag="AIC")
    filas[activo] = {"N": len(r), "media_%": r.mean() * 100, "desv_est_%": r.std() * 100,
                     "minimo_%": r.min() * 100, "maximo_%": r.max() * 100,
                     "asimetria": stats.skew(r), "curtosis_exceso": stats.kurtosis(r),
                     "JB": jb.statistic, "p_JB": jb.pvalue,
                     "ADF": adf[0], "p_ADF": adf[1]}
tabla1 = pd.DataFrame(filas).T
guardar_tabla(tabla1, "tabla1_descriptivos", "Tabla 1. Retornos logarítmicos diarios (muestra común)")


# ---------------------------------------------------------------------------
# Bloque 7. Tabla 2: perfil riesgo-retorno
# ---------------------------------------------------------------------------
filas, caidas = {}, {}
for activo in R.columns:
    r = R[activo]
    fila = {"retorno_anual_%": r.mean() * FACTOR_ANUAL * 100,
            "volatilidad_anual_%": r.std() * np.sqrt(FACTOR_ANUAL) * 100}
    if activo in ACTIVOS_PEN:
        e = EXCESO[activo]
        fila["sharpe_anual"] = e.mean() / e.std() * np.sqrt(FACTOR_ANUAL)
    else:
        fila["sharpe_anual"] = np.nan    # la tasa libre de riesgo es en soles
    for nivel in NIVELES_VAR:
        q = r.quantile(1 - nivel)
        fila[f"VaR{int(nivel * 100)}_hist_%"] = -q * 100
        fila[f"CVaR{int(nivel * 100)}_hist_%"] = -r[r <= q].mean() * 100
    fila["VaR99_normal_%"] = -(r.mean() + stats.norm.ppf(0.01) * r.std()) * 100
    mdd, fecha_mdd, caida = max_drawdown(r)
    fila["max_drawdown_%"] = mdd
    fila["fecha_minimo"] = fecha_mdd.strftime("%Y-%m-%d")
    filas[activo], caidas[activo] = fila, caida
tabla2 = pd.DataFrame(filas).T
for c in tabla2.columns.drop("fecha_minimo"):
    tabla2[c] = tabla2[c].astype(float)
guardar_tabla(tabla2, "tabla2_riesgo_retorno", "Tabla 2. Perfil riesgo-retorno (VaR y CVaR diarios)")


# ---------------------------------------------------------------------------
# Bloque 8. Tabla 3: correlaciones (Pearson y Spearman) con su significancia
# ---------------------------------------------------------------------------
filas = []
for i, a in enumerate(ACTIVOS_PEN):
    for b in ACTIVOS_PEN[i + 1:]:
        p_r, p_p = stats.pearsonr(R[a], R[b])
        s_r, s_p = stats.spearmanr(R[a], R[b])
        filas.append({"par": f"{a} – {b}", "pearson": p_r, "p_pearson": p_p,
                      "spearman": s_r, "p_spearman": s_p})
tabla3 = pd.DataFrame(filas).set_index("par")
guardar_tabla(tabla3, "tabla3_correlaciones", "Tabla 3. Correlaciones de los retornos diarios")


# ---------------------------------------------------------------------------
# Bloque 9. Tablas 4 y 5: CAPM con el índice BVL como cartera de mercado
#   (R_i - rf) = alfa + beta (R_BVL - rf) + error
# ---------------------------------------------------------------------------
tabla4 = pd.DataFrame({c: capm(EXCESO[c], EXCESO["Índice BVL"])
                       for c in ["BTC (S/)", "ETH (S/)"]}).T
guardar_tabla(tabla4, "tabla4_capm", "Tabla 4. CAPM frente al índice BVL, muestra completa")

filas = []
for nombre, ini, fin in SUBPERIODOS:
    tramo = EXCESO.loc[ini:fin]
    for c in ["BTC (S/)", "ETH (S/)"]:
        res = capm(tramo[c], tramo["Índice BVL"])
        filas.append({"subperiodo": nombre, "activo": c, "beta": res["beta"],
                      "ee_beta_NW": res["ee_beta_NW"], "p_beta=0": res["p_beta=0"],
                      "R2": res["R2"], "correlacion": tramo[c].corr(tramo["Índice BVL"]),
                      "volatilidad_anual_%": R.loc[ini:fin, c].std() * np.sqrt(FACTOR_ANUAL) * 100,
                      "N": res["N"]})
tabla5 = pd.DataFrame(filas).set_index(["subperiodo", "activo"])
guardar_tabla(tabla5, "tabla5_beta_subperiodos", "Tabla 5. Beta por subperiodos")


# ---------------------------------------------------------------------------
# Bloque 10. Tabla 6: diversificación (portafolio BVL + fracción de cripto)
#   Rebalanceo diario, sin costos de transacción.
# ---------------------------------------------------------------------------
simples = np.expm1(R[ACTIVOS_PEN])                # retornos simples
filas = []
for cripto in ["BTC (S/)", "ETH (S/)"]:
    for w in PESOS_CRIPTO:
        rp = np.log1p((1 - w) * simples["Índice BVL"] + w * simples[cripto])
        ep = rp - rf
        q95 = rp.quantile(0.05)
        filas.append({"cripto": cripto, "peso_cripto_%": w * 100,
                      "retorno_anual_%": rp.mean() * FACTOR_ANUAL * 100,
                      "volatilidad_anual_%": rp.std() * np.sqrt(FACTOR_ANUAL) * 100,
                      "sharpe_anual": ep.mean() / ep.std() * np.sqrt(FACTOR_ANUAL),
                      "VaR95_hist_%": -q95 * 100,
                      "CVaR95_hist_%": -rp[rp <= q95].mean() * 100,
                      "max_drawdown_%": max_drawdown(rp)[0]})
tabla6 = pd.DataFrame(filas).set_index(["cripto", "peso_cripto_%"])
guardar_tabla(tabla6, "tabla6_diversificacion", "Tabla 6. Portafolio BVL con una fracción de criptoactivo")


# ---------------------------------------------------------------------------
# Bloque 11. Tabla 7: validación cruzada Yahoo Finance vs CoinGecko (2026)
# ---------------------------------------------------------------------------
cal = base.set_index("fecha")
filas, diferencias = {}, {}
for alias, nombre in [("btc", "BTC"), ("eth", "ETH")]:
    par = cal[[f"precio_{alias}_usd", f"precio_{alias}_cg_usd", f"cap_mercado_{alias}_usd"]].dropna()
    dif = (par[f"precio_{alias}_cg_usd"] / par[f"precio_{alias}_usd"] - 1) * 100
    r_y = np.log(par[f"precio_{alias}_usd"]).diff()
    r_c = np.log(par[f"precio_{alias}_cg_usd"]).diff()
    cap = par[f"cap_mercado_{alias}_usd"] / 1e9
    filas[nombre] = {"N_dias": len(par), "desde": par.index[0].strftime("%Y-%m-%d"),
                     "hasta": par.index[-1].strftime("%Y-%m-%d"),
                     "dif_abs_media_%": dif.abs().mean(), "dif_abs_mediana_%": dif.abs().median(),
                     "dif_abs_maxima_%": dif.abs().max(),
                     "corr_precios": par[f"precio_{alias}_usd"].corr(par[f"precio_{alias}_cg_usd"]),
                     "corr_retornos": r_y.corr(r_c),
                     "cap_media_miles_mill_US$": cap.mean(),
                     "cap_inicio_miles_mill_US$": cap.iloc[0],
                     "cap_final_miles_mill_US$": cap.iloc[-1],
                     "var_cap_%": (cap.iloc[-1] / cap.iloc[0] - 1) * 100}
    diferencias[nombre] = dif
tabla7 = pd.DataFrame(filas).T
participacion = (cal["cap_mercado_btc_usd"] /
                 (cal["cap_mercado_btc_usd"] + cal["cap_mercado_eth_usd"])).dropna() * 100
tabla7["participacion_BTC_en_BTC+ETH_media_%"] = participacion.mean()
guardar_tabla(tabla7, "tabla7_validacion_coingecko", "Tabla 7. Yahoo Finance vs CoinGecko (2026)")


# ---------------------------------------------------------------------------
# Bloque 12. Tabla 8: liquidez anual (monto BVL vs volumen de BTC y ETH en soles)
# ---------------------------------------------------------------------------
cal_anual = cal.assign(
    año=cal.index.year,
    vol_btc_mill_pen=cal["volumen_btc_usd"] * cal["tc_venta"] / 1e6,
    vol_eth_mill_pen=cal["volumen_eth_usd"] * cal["tc_venta"] / 1e6,
)
habiles_cal = cal_anual[cal_anual["dia_habil_bvl"] == 1]
tabla8 = pd.DataFrame({
    "monto_BVL_prom_diario_mill_S/": habiles_cal.groupby("año")["monto_negociado_bvl"].mean(),
    "volumen_BTC_prom_diario_mill_S/": cal_anual.groupby("año")["vol_btc_mill_pen"].mean(),
    "volumen_ETH_prom_diario_mill_S/": cal_anual.groupby("año")["vol_eth_mill_pen"].mean(),
    "dias_habiles_BVL": habiles_cal.groupby("año").size(),
})
tabla8["veces_BTC_sobre_BVL"] = tabla8["volumen_BTC_prom_diario_mill_S/"] / \
    tabla8["monto_BVL_prom_diario_mill_S/"]
guardar_tabla(tabla8, "tabla8_liquidez_anual", "Tabla 8. Liquidez anual (millones de S/ por día)")


# ---------------------------------------------------------------------------
# Bloque 13. Tabla 9: igualdad de varianzas (Levene con mediana = Brown-Forsythe)
# ---------------------------------------------------------------------------
filas = []
for c in ["BTC (S/)", "ETH (S/)", "TC (S/ por US$)"]:
    prueba = stats.levene(R[c], R["Índice BVL"], center="median")
    filas.append({"comparacion": f"{c} vs Índice BVL",
                  "razon_varianzas": R[c].var() / R["Índice BVL"].var(),
                  "estadistico_W": prueba.statistic, "p_valor": prueba.pvalue})
tabla9 = pd.DataFrame(filas).set_index("comparacion")
guardar_tabla(tabla9, "tabla9_igualdad_varianzas", "Tabla 9. Prueba de igualdad de varianzas")


# ---------------------------------------------------------------------------
# Bloque 14. Figuras (estilo de informe institucional)
#   Sin título dentro de la imagen: el título y la nota van en LaTeX (APA 7).
#   Arriba: leyenda en una fila y unidad de medida. Solo grilla horizontal.
# ---------------------------------------------------------------------------
fin_x = R.index[-1] + pd.Timedelta(days=150)        # espacio para rótulos finales

# Figura 1. Evolución de los precios (base 100, escala logarítmica)
fig, ax = plt.subplots(figsize=(ANCHO, 3.6))
for c in ACTIVOS_PEN:
    serie = precios[c] / precios[c].iloc[0] * 100
    ax.plot(serie.index, serie, color=COLORES[c], label=c, zorder=3)
ax.set_yscale("log")
ax.yaxis.set_major_locator(mticker.LogLocator(base=10, subs=[1, 2, 5]))
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ")))
ax.yaxis.set_minor_locator(mticker.NullLocator())
linea_referencia(ax, 100)
marcar_eventos(ax)
eje_fechas(ax)
ax.set_xlim(R.index[0] - pd.Timedelta(days=30), fin_x)
rotulos_finales(ax, {COLORES[c]: precios[c] / precios[c].iloc[0] * 100 for c in ACTIVOS_PEN})
encabezado(ax, f"Índice, {precios.index[0]:%d-%m-%Y} = 100 (escala logarítmica)")
guardar_figura(fig, "figura1_precios_base100")

# Figura 2. Volatilidad móvil anualizada
fig, ax = plt.subplots(figsize=(ANCHO, 3.6))
for c in ACTIVOS_PEN:
    vol = R[c].rolling(VENTANA_VOL).std() * np.sqrt(FACTOR_ANUAL) * 100
    ax.plot(vol.index, vol, color=COLORES[c], label=c, zorder=3)
ax.set_ylim(bottom=0)
marcar_eventos(ax)
eje_fechas(ax)
encabezado(ax, f"Volatilidad anualizada (%), ventana móvil de {VENTANA_VOL} días hábiles")
guardar_figura(fig, "figura2_volatilidad_movil")

# Figura 3. Correlación móvil con el índice BVL
fig, ax = plt.subplots(figsize=(ANCHO, 3.6))
for c in ["BTC (S/)", "ETH (S/)"]:
    corr = R[c].rolling(VENTANA_CORR).corr(R["Índice BVL"])
    ax.plot(corr.index, corr, color=COLORES[c], label=f"{c} con Índice BVL", zorder=3)
    ax.axhline(R[c].corr(R["Índice BVL"]), color=COLORES[c], lw=0.8, ls=(0, (4, 3)), zorder=2)
linea_referencia(ax, 0)
ax.plot([], [], color=TINTA_2, lw=0.8, ls=(0, (4, 3)), label="Correlación de toda la muestra")
marcar_eventos(ax)
eje_fechas(ax)
encabezado(ax, f"Coeficiente de correlación de Pearson, ventana móvil de {VENTANA_CORR} días hábiles", ncol=3)
guardar_figura(fig, "figura3_correlacion_movil")

# Figura 4. Distribución de los retornos frente a la normal (paneles)
fig, ejes = plt.subplots(1, 3, figsize=(ANCHO, 2.7))
for ax, c in zip(ejes, ["BTC (S/)", "ETH (S/)", "Índice BVL"]):
    r = R[c] * 100
    lim = max(abs(r.quantile(0.002)), abs(r.quantile(0.998)))
    ax.hist(r, bins=70, range=(-lim, lim), density=True,
            color=COLORES[c], alpha=0.85, edgecolor="white", linewidth=0.25, zorder=3)
    x = np.linspace(-lim, lim, 400)
    ax.plot(x, stats.norm.pdf(x, r.mean(), r.std()), color=TINTA, lw=1, ls=(0, (3, 2)),
            label="Distribución normal", zorder=4)
    ax.set_title(c, pad=15, fontsize=8.5)
    ax.text(0, 1.02, f"Curtosis en exceso {stats.kurtosis(r):.1f} · asimetría {stats.skew(r):.2f}"
            .replace("-", "−"), transform=ax.transAxes, ha="left", va="bottom",
            fontsize=6.8, color=TINTA_2)
    ax.set_xlim(-lim, lim)
    ax.set_xlabel("Retorno diario (%)")
    ax.tick_params(axis="y", labelsize=7)
ejes[0].set_ylabel("Densidad")
fig.legend(*ejes[0].get_legend_handles_labels(), loc="upper left", bbox_to_anchor=(0.06, 1.08),
           fontsize=8)
fig.tight_layout(w_pad=1.5)
guardar_figura(fig, "figura4_distribucion_retornos")

# Figura 5. Beta móvil frente al índice BVL
fig, ax = plt.subplots(figsize=(ANCHO, 3.6))
for c in ["BTC (S/)", "ETH (S/)"]:
    beta_movil = EXCESO[c].rolling(VENTANA_BETA).cov(EXCESO["Índice BVL"]) / \
        EXCESO["Índice BVL"].rolling(VENTANA_BETA).var()
    ax.plot(beta_movil.index, beta_movil, color=COLORES[c], label=c, zorder=3)
linea_referencia(ax, 0)
ax.axhline(1, color=TINTA_2, lw=0.8, ls=(0, (4, 3)), zorder=2)
ax.set_ylim(top=max(ax.get_ylim()[1], 1.3))          # deja aire sobre la línea β = 1
trans = blended_transform_factory(ax.transAxes, ax.transData)
ax.text(0.005, 1, "β = 1: mismo riesgo sistemático que el índice", transform=trans,
        ha="left", va="center", fontsize=7, color=TINTA_2, zorder=6,
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none"))
marcar_eventos(ax)
eje_fechas(ax)
encabezado(ax, f"Beta frente al Índice BVL, ventana móvil de {VENTANA_BETA} días hábiles", ncol=2)
guardar_figura(fig, "figura5_beta_movil")

# Figura 6. Caída desde el máximo previo (drawdown), un panel por activo
paneles = ["BTC (S/)", "ETH (S/)", "Índice BVL"]
fig, ejes = plt.subplots(3, 1, figsize=(ANCHO, 5.0), sharex=True, sharey=True)
for ax, c in zip(ejes, paneles):
    dd = caidas[c] * 100
    ax.fill_between(dd.index, dd, 0, color=COLORES[c], alpha=0.30, lw=0, zorder=2)
    ax.plot(dd.index, dd, color=COLORES[c], lw=1, zorder=3)
    ax.plot([dd.idxmin()], [dd.min()], "o", ms=3.5, color=COLORES[c], mec="white", mew=0.8, zorder=5)
    rotulo_minimo(ax, dd)
    ax.set_title(c, pad=4, fontsize=8.5)
    ax.set_ylim(-105, 5)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(25))
    ax.axhline(0, color=TINTA_2, lw=0.8, zorder=2)
eje_fechas(ejes[-1])
ejes[0].text(0, 1.30, "Caída desde el máximo previo (%)", transform=ejes[0].transAxes,
             ha="left", va="bottom", fontsize=8, color=TINTA_2)
fig.tight_layout(h_pad=1.2)
guardar_figura(fig, "figura6_drawdown")

# Figura 7. Diferencia de precios CoinGecko vs Yahoo Finance (2026), un panel por activo
fig, ejes = plt.subplots(2, 1, figsize=(ANCHO, 3.8), sharex=True, sharey=True)
for ax, (nombre, color) in zip(ejes, [("BTC", COLORES["BTC (S/)"]), ("ETH", COLORES["ETH (S/)"])]):
    d = diferencias[nombre]
    ax.plot(d.index, d, color=color, lw=0.9, zorder=3)
    ax.axhline(0, color=TINTA_2, lw=0.8, zorder=2)
    ax.set_title(nombre, pad=4, fontsize=8.5)
    ax.text(1.0, 1.02, f"Diferencia absoluta media {d.abs().mean():.3f} % · mediana {d.abs().median():.3f} %",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7, color=TINTA_2)
ejes[-1].xaxis.set_major_locator(mdates.MonthLocator())
ejes[-1].xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: fecha_corta(mdates.num2date(v))))
ejes[0].text(0, 1.28, "Diferencia de precio: CoinGecko / Yahoo Finance − 1 (%)",
             transform=ejes[0].transAxes, ha="left", va="bottom", fontsize=8, color=TINTA_2)
fig.tight_layout(h_pad=1.0)
guardar_figura(fig, "figura7_validacion_coingecko")

# Figura 8. Riesgo y retorno del portafolio BVL al añadir criptoactivos (Tabla 6)
#   Los rótulos de BTC van a la izquierda de cada punto y los de ETH a la derecha.
fig, ax = plt.subplots(figsize=(ANCHO, 3.8))
lado = {"BTC (S/)": (-7, "right"), "ETH (S/)": (7, "left")}
for cripto in ["BTC (S/)", "ETH (S/)"]:
    t = tabla6.loc[cripto]
    ax.plot(t["volatilidad_anual_%"], t["retorno_anual_%"], color=COLORES[cripto], lw=1.2,
            marker="o", ms=5, mec="white", mew=0.9, label=f"Índice BVL + {cripto}", zorder=3)
    dx, alineacion = lado[cripto]
    for peso, fila in t.iterrows():
        if peso in (5.0, 10.0, 20.0):
            ax.annotate(f"{peso:.0f} %", (fila["volatilidad_anual_%"], fila["retorno_anual_%"]),
                        xytext=(dx, 0), textcoords="offset points", ha=alineacion, va="center",
                        fontsize=7, color=TINTA_2)
base_bvl = tabla6.loc[("BTC (S/)", 0.0)]
ax.plot([base_bvl["volatilidad_anual_%"]], [base_bvl["retorno_anual_%"]], "o", ms=6,
        color=COLORES["Índice BVL"], mec="white", mew=0.9, zorder=4)
ax.annotate("100 % Índice BVL", (base_bvl["volatilidad_anual_%"], base_bvl["retorno_anual_%"]),
            xytext=(8, -10), textcoords="offset points", ha="left", va="top", fontsize=7,
            color=TINTA_2)
ax.margins(x=0.10, y=0.12)
ax.grid(axis="x", color=GRILLA, lw=0.6)
ax.set_xlabel("Volatilidad anualizada (%)")
encabezado(ax, "Retorno anualizado (%); los rótulos indican el peso del criptoactivo "
               "(rebalanceo diario)", ncol=2)
guardar_figura(fig, "figura8_diversificacion")


# ---------------------------------------------------------------------------
# Bloque 15. Resumen final
# ---------------------------------------------------------------------------
print("\n================ RESUMEN DEL ANÁLISIS ================")
print("Eventos marcados en las figuras 1, 2, 3 y 5 (para la nota en el artículo):")
for letra, fecha, texto in EVENTOS:
    print(f"  {letra}: {pd.Timestamp(fecha):%d-%m-%Y}, {texto}")
print(f"Muestra común: {len(R)} retornos diarios, {R.index[0]:%Y-%m-%d} a {R.index[-1]:%Y-%m-%d}")
print(f"Archivos en /salidas: {sorted(p.name for p in DIR_SALIDAS.iterdir())}")
escribir_log("Fin del análisis")
