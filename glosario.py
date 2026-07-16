"""
Vista de Glosario del dashboard de forecast semanal de SAUDA.

Explica en lenguaje de negocio las columnas, fórmulas, la clasificación de
productos (Cluster / Grupo CV) y la configuración de los modelos LightGBM
que generan el forecast que se ve en las pestañas de Gráfico y Tabla.

El contenido está tomado directamente del pipeline de entrenamiento
(Forecast_LightGBM_v1/02_forecast_lightgbm_training_semanal/{config,engine}.py)
y de este mismo repo (logic.py, charts.py) — no son valores inventados.
"""

import streamlit as st

# Paleta compartida con charts.py, más verde/ámbar/rojo para A/B/C.
AZUL = "#2563EB"
AZUL_CLARO = "#DBEAFE"
NARANJA = "#F97316"
NARANJA_CLARO = "#FFEDD5"
GRIS = "#6B7280"
GRIS_CLARO = "#F3F4F6"
VERDE = "#16A34A"
VERDE_CLARO = "#DCFCE7"
AMBAR = "#D97706"
AMBAR_CLARO = "#FEF3C7"
ROJO = "#DC2626"
ROJO_CLARO = "#FEE2E2"
MORADO = "#7C3AED"
MORADO_CLARO = "#EDE9FE"


def _card(titulo: str, color: str, color_claro: str, cuerpo_html: str, icono: str = "") -> str:
    return f"""
<div style="
    background:{color_claro};
    border-left:5px solid {color};
    border-radius:10px;
    padding:16px 20px;
    margin-bottom:14px;
">
  <div style="font-weight:700;font-size:1rem;color:{color};margin-bottom:8px;">
    {icono} {titulo}
  </div>
  <div style="font-size:0.92rem;color:#1E293B;line-height:1.6;">
    {cuerpo_html}
  </div>
</div>
"""


def _fila(nombre: str, desc: str) -> str:
    return (
        f'<div style="display:flex;gap:10px;padding:4px 0;border-bottom:1px solid rgba(0,0,0,0.06);">'
        f'<span style="font-family:Consolas,monospace;font-weight:700;min-width:190px;flex-shrink:0;">{nombre}</span>'
        f'<span>{desc}</span></div>'
    )


def render():
    st.header("📖 Glosario del Forecast Semanal")
    st.caption(
        "Qué significa cada columna, cómo se calcula cada métrica y cómo se entrena "
        "el modelo que genera este forecast."
    )

    # ── 1. Tipos de fila y columnas de demanda ──────────────────────────
    st.markdown(
        _card(
            "Filas y columnas de demanda",
            AZUL, AZUL_CLARO,
            _fila("tipo", "<b>R</b> = Histórico real (venta ya cerrada) &nbsp;|&nbsp; <b>F</b> = Forecast (semana futura, todavía sin venta real)")
            + _fila("Real (unid.)", "Cantidad realmente vendida en esa semana (solo existe en filas <b>R</b>)")
            + _fila("Forecast PURO (F-MODELO)", "Predicción del modelo LightGBM para esa semana, sin ajustes posteriores. Ver bloque de fórmulas.")
            + _fila("LYSW", "<i>Last Year Same Week</i>: venta real de la misma semana del año anterior (alineada por año ISO + semana ISO). Se muestra como referencia, no se mezcla con el forecast.")
            + _fila("Promo", "1 si esa semana tuvo una promoción/oferta activa cargada en el maestro comercial")
            + _fila("Feriado", "1 si esa semana contiene un feriado nacional argentino")
            + _fila("Sucursal / Departamento / Familia / SubFamilia / Artículo", "Jerarquía comercial del punto de venta y del producto"),
            icono="🗂️",
        ),
        unsafe_allow_html=True,
    )

    # ── 2. Fórmulas y métricas ───────────────────────────────────────────
    st.markdown(
        _card(
            "Fórmulas de las métricas del panel superior",
            VERDE, VERDE_CLARO,
            _fila("Error% PURO", "<code>(Real − Forecast PURO) / Forecast PURO × 100</code> — error de una semana puntual, calculado solo donde ya hay venta real y Forecast PURO &gt; 0")
            + _fila("WAPE (backtest)", "<code>Σ|Real − Forecast PURO| / Σ Real × 100</code> — error absoluto ponderado por volumen, agregado sobre todas las semanas con backtest disponible. Cuanto más bajo, mejor.")
            + _fila("Variación vs LYSW", "<code>(Σ Forecast próx. 4 sem. − Σ LYSW mismo período) / Σ LYSW × 100</code> — compara el forecast contra lo vendido la misma época del año pasado")
            + _fila("Promo% (uplift)", "<code>(Real − LYSW) / LYSW × 100</code>, calculado solo en semanas históricas con <code>Promo = 1</code> — mide cuánto más (o menos) se vendió vs. el año anterior durante una promo")
            + _fila("Venta prom. semanal / diaria", "Promedio de <code>Forecast PURO</code> de las primeras 4 semanas de forecast, dividido 4 (semanal) o 28 (diaria)"),
            icono="📐",
        ),
        unsafe_allow_html=True,
    )

    # ── 2.1 Confiabilidad del modelo por serie (columnas nuevas) ─────────
    st.markdown(
        _card(
            "Confiabilidad del modelo por serie (Artículo × Sucursal)",
            AZUL, AZUL_CLARO,
            "<div style='margin-bottom:8px;'>Estas columnas <b>no se recalculan con los filtros de la izquierda</b>: vienen ya calculadas "
            "desde el pipeline, usando <b>todo el historial de backtest</b> disponible de cada serie (no solo las últimas 4 semanas). "
            "Son el diagnóstico del propio modelo sobre qué tan bien predice ese artículo puntual en esa sucursal.</div>"
            + _fila("WMAPE serie", "<code>Σ|Real − Forecast PURO| / Σ Real × 100</code>, sumado sobre todo el historial de esa serie (no solo el período filtrado)")
            + _fila("Sesgo (bias_pct)", "<code>−Σ(Real − Forecast PURO) / Σ Real × 100</code> — <b>positivo</b> = el modelo sobreestima esa serie de forma sistemática, <b>negativo</b> = la subestima")
            + _fila("Desvío estándar", "Desvío estándar de los residuos históricos (Real − Forecast PURO) de esa serie — mide cuánto varía el error semana a semana")
            + _fila("Forecast mín. / máx. (80%)", "<code>Forecast PURO ± 1.28 × Desvío estándar</code> — banda de confianza aproximada del 80% alrededor del forecast (el mínimo nunca baja de 0)")
            + _fila("Confiabilidad", "<b>Alta</b> si WMAPE serie &lt; 20% &nbsp;|&nbsp; <b>Media</b> si WMAPE serie &lt; 40% &nbsp;|&nbsp; <b>Baja</b> si WMAPE serie ≥ 40% o si hay menos de 8 semanas de historial &nbsp;|&nbsp; <b>Sin datos</b> si la serie no tiene backtest todavía")
            + _fila("Semanas hist. usadas (n_hist)", "Cantidad de semanas con Real y Forecast PURO simultáneos que se usaron para calcular las 5 métricas anteriores — a más semanas, más confiable el diagnóstico"),
            icono="📏",
        ),
        unsafe_allow_html=True,
    )

    # ── 3. Clasificación por volatilidad — Grupo CV ─────────────────────
    st.subheader("🏷️ Clasificación de productos")

    st.markdown(
        """
<div style="font-size:0.9rem;color:#1E293B;margin-bottom:10px;">
El <b>Grupo CV</b> (columna <code>cv_grupo</code>) no se elige a mano: se calcula estadísticamente
por artículo × sucursal a partir del <b>Coeficiente de Variación</b> de sus ventas semanales, y determina
qué configuración de LightGBM se usa para esa serie (ver sección siguiente).
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<div style="background:{GRIS_CLARO};border-radius:10px;padding:14px 18px;margin-bottom:14px;">
  <div style="font-weight:700;margin-bottom:6px;">Cómo se calcula (código real del pipeline)</div>
  <div style="font-family:Consolas,monospace;font-size:0.82rem;line-height:1.8;color:#1E293B;">
    cv_raw&nbsp;&nbsp;= desvío estándar de semanas con venta &gt; 0  /  promedio de esas mismas semanas<br>
    pct_cero = % de semanas con venta = 0<br>
    cv_valor = cv_raw × (1 + pct_cero) &nbsp;<span style="color:{GRIS};">(penaliza series intermitentes)</span>
  </div>
  <div style="font-size:0.82rem;color:{GRIS};margin-top:8px;">
    Requiere al menos <b>8 semanas con venta positiva</b>; si no hay suficiente historial, el artículo cae directo en Grupo C.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    col_a, col_b, col_c = st.columns(3)
    grupos = [
        (col_a, "A", VERDE, VERDE_CLARO, "Demanda estable",
         "cv_raw &lt; 0.35",
         "Baja variabilidad — productos de alto movimiento y comportamiento regular. Mejor precisión esperada del modelo."),
        (col_b, "B", AMBAR, AMBAR_CLARO, "Demanda media",
         "0.35 ≤ cv_raw &lt; 0.80",
         "Variabilidad moderada, con cierta estacionalidad. Precisión media-alta."),
        (col_c, "C", ROJO, ROJO_CLARO, "Demanda irregular",
         "cv_raw ≥ 0.80 &nbsp;o&nbsp; pct_cero ≥ 50% &nbsp;o&nbsp; historial insuficiente",
         "Alta variabilidad o muchas semanas en cero. Mayor incertidumbre — conviene revisión manual antes de generar órdenes."),
    ]
    for col, letra, color, color_claro, titulo, regla, desc in grupos:
        with col:
            st.markdown(
                f"""
<div style="background:{color_claro};border-radius:12px;padding:16px;min-height:210px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
    <div style="background:white;color:{color};font-weight:900;font-size:1.3rem;
                width:38px;height:38px;border-radius:8px;display:flex;align-items:center;justify-content:center;">
      {letra}
    </div>
    <div style="font-weight:700;color:#1E293B;">{titulo}</div>
  </div>
  <div style="font-family:Consolas,monospace;font-size:0.78rem;background:white;border-radius:6px;
              padding:6px 8px;margin-bottom:8px;color:#1E293B;">
    {regla}
  </div>
  <div style="font-size:0.8rem;color:#1E293B;">{desc}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    st.markdown(
        _card(
            "Cluster (columna Cluster) — distinto del Grupo CV",
            MORADO, MORADO_CLARO,
            _fila("1 / 2 / 3", "Nivel de volatilidad asignado comercialmente en el maestro de sucursales/artículos (carga manual, no estadística)")
            + _fila("P", "Sucursal o artículo con foco promocional")
            + _fila("T", "Sucursal o artículo en prueba/piloto")
            + "<div style='margin-top:8px;font-size:0.82rem;color:#1E293B;'>El <b>Cluster</b> es una etiqueta de negocio cargada a mano; el <b>Grupo CV</b> es calculado automáticamente por el pipeline en cada corrida semanal. Son dos filtros independientes en la barra lateral.</div>",
            icono="🏷️",
        ),
        unsafe_allow_html=True,
    )

    # ── 4. Configuración de LightGBM ─────────────────────────────────────
    st.subheader("🤖 Configuración del modelo LightGBM")
    st.caption(
        "El pipeline entrena un modelo LightGBM independiente por Grupo CV — cada uno con su propio "
        "objetivo estadístico e hiperparámetros, ajustados a la volatilidad típica de ese grupo."
    )

    def _tabla_lgb(letra, color, color_claro, params_html):
        return f"""
<div style="background:white;border:1px solid {color};border-radius:10px;padding:14px 16px;margin-bottom:12px;">
  <div style="display:inline-block;background:{color_claro};color:{color};font-weight:700;
              padding:2px 10px;border-radius:6px;font-size:0.75rem;margin-bottom:10px;">
    MODELO GRUPO {letra}
  </div>
  {params_html}
</div>
"""

    def _param(nombre, valor):
        return (
            f'<div style="display:flex;justify-content:space-between;font-size:0.82rem;'
            f'padding:2px 0;"><span style="color:{GRIS};">{nombre}</span>'
            f'<span style="font-family:Consolas,monospace;font-weight:600;">{valor}</span></div>'
        )

    col_ma, col_mb, col_mc = st.columns(3)
    with col_ma:
        st.markdown(
            _tabla_lgb(
                "A", VERDE, VERDE_CLARO,
                _param("objective", "tweedie")
                + _param("metric", "rmse")
                + _param("n_estimators", "1000")
                + _param("num_leaves", "95")
                + _param("max_depth", "9")
                + _param("min_child_samples", "24")
                + _param("learning_rate", "0.0263")
                + _param("subsample", "0.908")
                + _param("colsample_bytree", "0.915")
                + _param("reg_alpha", "0.00071")
                + _param("reg_lambda", "0.0596")
                + _param("tweedie_variance_power", "1.660"),
            ),
            unsafe_allow_html=True,
        )
    with col_mb:
        st.markdown(
            _tabla_lgb(
                "B", AMBAR, AMBAR_CLARO,
                _param("objective", "tweedie")
                + _param("metric", "mae")
                + _param("n_estimators", "1000")
                + _param("num_leaves", "132")
                + _param("max_depth", "10")
                + _param("min_child_samples", "24")
                + _param("learning_rate", "0.0222")
                + _param("subsample", "0.927")
                + _param("colsample_bytree", "0.925")
                + _param("reg_alpha", "0.0058")
                + _param("reg_lambda", "0.0421")
                + _param("tweedie_variance_power", "1.381"),
            ),
            unsafe_allow_html=True,
        )
    with col_mc:
        st.markdown(
            _tabla_lgb(
                "C", ROJO, ROJO_CLARO,
                _param("objective", "poisson")
                + _param("metric", "mae")
                + _param("n_estimators", "1000")
                + _param("num_leaves", "114")
                + _param("max_depth", "10")
                + _param("min_child_samples", "26")
                + _param("learning_rate", "0.0107")
                + _param("subsample", "0.948")
                + _param("colsample_bytree", "0.990")
                + _param("reg_alpha", "0.00011")
                + _param("reg_lambda", "0.6995"),
            ),
            unsafe_allow_html=True,
        )

    st.markdown(
        _card(
            "Qué significan estos parámetros",
            NARANJA, NARANJA_CLARO,
            _fila("objective (tweedie / poisson)", "Distribución estadística que el modelo intenta ajustar. <b>Tweedie</b> tolera ventas semi-continuas con algunos ceros (grupos A/B); <b>Poisson</b> está pensado para conteos discretos con muchos ceros (grupo C, demanda intermitente)")
            + _fila("tweedie_variance_power", "Ajusta la forma de la distribución Tweedie entre Poisson (1) y Gamma (2); cuanto más alto, más tolera valores extremos ocasionales")
            + _fila("num_leaves / max_depth", "Controlan la complejidad de cada árbol del modelo — grupos con más leaves/profundidad capturan patrones más finos, a costa de mayor riesgo de sobreajuste")
            + _fila("learning_rate", "Tamaño del paso de aprendizaje en cada árbol nuevo; más bajo = aprendizaje más lento pero más estable")
            + _fila("subsample / colsample_bytree", "% de filas y de columnas que se muestrean al azar en cada árbol, para reducir sobreajuste")
            + _fila("reg_alpha / reg_lambda", "Regularización L1 / L2 — penalizan modelos demasiado complejos")
            + _fila("n_estimators", "Cantidad máxima de árboles (1000), acotada en la práctica por early stopping")
            + _fila("random_state = 42", "Semilla fija en los tres modelos, para que el entrenamiento sea reproducible"),
            icono="⚙️",
        ),
        unsafe_allow_html=True,
    )

    # ── 5. Notas del pipeline ───────────────────────────────────────────
    st.markdown(
        _card(
            "Notas del pipeline",
            GRIS, GRIS_CLARO,
            _fila("Early stopping", "Se usan las últimas 4 semanas como set de validación para encontrar el mejor número de árboles; luego se reentrena con todo el histórico usando ese número")
            + _fila("Horizonte de forecast", "4 semanas hacia adelante, en forma recursiva (cada semana predicha alimenta los lags de la siguiente)")
            + _fila("Frecuencia de reentrenamiento", "Semanal — el pipeline vuelve a correr y clasificar los grupos CV con cada actualización de datos")
            + _fila("Forecast PURO = salida final", "La mezcla opcional de F-MODELO con LYSW (blend por Grupo CV) existe en el código del pipeline pero está <b>desactivada</b> en la versión actual: lo que ves en <i>Forecast PURO</i> es 100% la predicción del modelo, sin ajuste posterior")
            + _fila("Distribución a SKU", "El modelo predice a nivel agregado (sucursal × subfamilia) y el forecast se reparte a cada artículo según su participación (\"share\") reciente en esas ventas"),
            icono="ℹ️",
        ),
        unsafe_allow_html=True,
    )
