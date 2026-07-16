"""
Dashboard interactivo del forecast semanal de SAUDA (Streamlit).

Ejecutar con:
    streamlit run app.py
"""

import streamlit as st

# set_page_config debe ser el primer comando de Streamlit del script. Por eso
# va antes que "import auth": ese import instancia stauth.Authenticate, que
# monta un componente (el manejador de cookies) y ya cuenta como un comando.
st.set_page_config(
    page_title="SAUDA – Forecast Semanal",
    page_icon="📈",
    layout="wide",
)

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd

import auth
import charts
import glosario
import logic
from data_source import cargar_forecast_raw, obtener_estado_datos

usuario = auth.require_login()

if "vista" not in st.session_state:
    st.session_state["vista"] = "dashboard"

col_titulo, col_boton = st.columns([5, 1])
with col_titulo:
    st.title("📈 SAUDA – Forecast Semanal")
with col_boton:
    st.write("")
    if st.session_state["vista"] == "glosario":
        if st.button("⬅ Volver", use_container_width=True):
            st.session_state["vista"] = "dashboard"
            st.rerun()
    else:
        if st.button("📖 Glosario", use_container_width=True):
            st.session_state["vista"] = "glosario"
            st.rerun()

if st.session_state["vista"] == "glosario":
    glosario.render()
    st.stop()

with st.sidebar:
    st.success(f"👤 {usuario}")
    auth.authenticator.logout("Cerrar sesión", "sidebar")
    st.divider()


@st.cache_resource(ttl=600, show_spinner="Cargando y transformando datos...")
def _cargar():
    # cache_resource (no cache_data): evita copiar en profundidad el
    # DataFrame completo en cada rerun del script (cada clic o cambio de
    # filtro), ya que solo se lee — nunca se muta in-place.
    df = logic.transformar_datos(cargar_forecast_raw())
    cols_dim = [col for _, col in logic.FILTRO_COLS if col in df.columns]
    dim = df[cols_dim].drop_duplicates().reset_index(drop=True)
    return df, dim


st.sidebar.header("Filtros")

if st.sidebar.button("🔄 Recargar datos"):
    st.cache_resource.clear()
    st.cache_data.clear()  # cargar_forecast_raw() y obtener_estado_datos() usan cache_data aparte
    st.rerun()


def _mostrar_estado_datos():
    estado = obtener_estado_datos()
    actualizado = estado.get("actualizado")
    if not actualizado:
        st.sidebar.caption("🕐 Sin información de la última actualización.")
        return

    delta = datetime.now(timezone.utc) - actualizado
    dias = delta.days
    if dias >= 1:
        hace = f"hace {dias} día{'s' if dias != 1 else ''}"
    else:
        horas = delta.seconds // 3600
        hace = f"hace {horas} hora{'s' if horas != 1 else ''}" if horas >= 1 else "hace instantes"

    filas = estado.get("filas")
    filas_str = f" · {filas:,} filas" if filas else ""
    texto = f"Datos actualizados: {actualizado.strftime('%d/%m/%Y %H:%M UTC')} ({hace}){filas_str}"

    if dias >= 9:  # el pipeline corre semanalmente: más de ~9 días es señal de alerta
        st.sidebar.warning(f"⚠ {texto}")
    else:
        st.sidebar.caption(f"🕐 {texto}")


_mostrar_estado_datos()

try:
    df, dim = _cargar()
except Exception as e:
    st.error(f"No se pudieron cargar los datos: {e}")
    st.stop()

if df.empty:
    st.warning("El origen de datos no devolvió filas.")
    st.stop()

FILTROS_DEFAULT = {col: logic.ALL for _, col in logic.FILTRO_COLS}

# Las opciones en cascada se calculan sobre `dim` (combinaciones únicas de
# filtros, unas pocas miles de filas) en vez del DataFrame completo
# (millones de filas) para que cambiar un filtro sea instantáneo.
ARTICULO_COL = "Articulo Desc"

seleccion_widgets = {col: st.session_state.get(f"filtro_{col}", logic.ALL) for _, col in logic.FILTRO_COLS}
for label, col in logic.FILTRO_COLS:
    if col not in dim.columns:
        continue
    otros = {k: v for k, v in seleccion_widgets.items() if k != col}
    dim_tmp = logic.aplicar_filtros(dim, otros)

    if col == ARTICULO_COL:
        # El artículo tiene miles de valores (SKU + " - " + descripción):
        # se busca por texto antes de elegirlo en el desplegable.
        busqueda = st.sidebar.text_input(
            "🔍 Buscar artículo (SKU o descripción)",
            key="busqueda_articulo",
            placeholder="Ej: 100146 o MARLBORO",
        ).strip()
        if busqueda:
            dim_tmp = dim_tmp[
                dim_tmp[col].str.contains(busqueda, case=False, na=False, regex=False)
            ]
            if dim_tmp.empty:
                st.sidebar.caption("Sin artículos que coincidan con la búsqueda.")

    opciones = [logic.ALL] + logic.opciones_col(dim_tmp, col)
    key = f"filtro_{col}"
    valor_actual = seleccion_widgets[col] if seleccion_widgets[col] in opciones else logic.ALL
    st.sidebar.selectbox(label, opciones, index=opciones.index(valor_actual), key=key)
    seleccion_widgets[col] = st.session_state[key]

col_aplicar, col_limpiar = st.sidebar.columns(2)
aplicar_click = col_aplicar.button("▶ Aplicar filtros", use_container_width=True, type="primary")
limpiar_click = col_limpiar.button("✖ Limpiar", use_container_width=True)

if limpiar_click:
    for _, col in logic.FILTRO_COLS:
        st.session_state.pop(f"filtro_{col}", None)
    st.session_state.pop("busqueda_articulo", None)
    st.session_state["filtros_aplicados"] = dict(FILTROS_DEFAULT)
    st.rerun()

if aplicar_click or "filtros_aplicados" not in st.session_state:
    st.session_state["filtros_aplicados"] = dict(seleccion_widgets)

filtros = st.session_state["filtros_aplicados"]

hist_weeks = st.sidebar.slider(
    "Semanas históricas a mostrar", min_value=4, max_value=104,
    value=logic.HIST_WEEKS_DEFAULT, step=4,
)

# El filtrado pesado sobre el DataFrame completo solo ocurre acá, al aplicar.
df_filtrado = logic.aplicar_filtros(df, filtros)

if df_filtrado.empty:
    st.warning("Sin datos con los filtros aplicados.")
    st.stop()

# ── Métricas ─────────────────────────────────────────────────────────
m = logic.calcular_metricas(df_filtrado)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Forecast próx. 4 sem.", f"{m['fc_total']:,.0f}")
c2.metric("LYSW mismo período", f"{m['lysw_total']:,.0f}")
c3.metric(
    "Variación vs LYSW",
    f"{m['var_lysw']:+.1f} %" if pd.notna(m['var_lysw']) else "—",
)
c4.metric("Real últimas 4 sem.", f"{m['hist_4sem']:,.0f}")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Venta prom. semanal", f"{m['venta_prom_semanal']:,.1f}" if pd.notna(m['venta_prom_semanal']) else "—")
c6.metric("Venta prom. diaria", f"{m['venta_prom_diario']:,.1f}" if pd.notna(m['venta_prom_diario']) else "—")
c7.metric("WAPE (backtest)", f"{m['wape']:.1f} %" if pd.notna(m['wape']) else "—")
c8.metric(
    "PROMO% (uplift)",
    f"{m['promo_uplift']:+.1f} %" if pd.notna(m['promo_uplift']) else "—",
)

partes_contexto = [
    f"**{label}:** {filtros[col]}"
    for label, col in logic.FILTRO_COLS
    if col in filtros and filtros[col] != logic.ALL
]
texto_contexto = "  ·  ".join(partes_contexto) if partes_contexto else "Todas las sucursales y artículos"
st.caption(f"🔎 Datos mostrados — {texto_contexto}")

st.divider()

tab_grafico, tab_tabla = st.tabs(["📈 Gráfico", "📋 Tabla"])

with tab_grafico:
    fig = charts.construir_figura(df_filtrado, hist_weeks)
    st.plotly_chart(fig, use_container_width=True)

with tab_tabla:
    MAX_ROWS = 5_000

    cols_presentes = [(orig, disp) for orig, disp in logic.TABLE_COLS if orig in df_filtrado.columns]
    sort_cols = [c for c in [logic.DATE_COL, "Sucursal", "Articulo Desc"] if c in df_filtrado.columns]
    df_s = df_filtrado.sort_values(sort_cols) if sort_cols else df_filtrado
    df_s = df_s.assign(Tipo=df_s["tipo"].map({"F": "Forecast", "R": "Histórico"}))

    truncado = len(df_s) > MAX_ROWS
    df_vista = df_s.head(MAX_ROWS) if truncado else df_s

    df_tabla = df_vista[["Tipo"] + [c for c, _ in cols_presentes]].rename(
        columns=dict(cols_presentes)
    )

    column_config = {
        "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
        "Real (unid.)": st.column_config.NumberColumn(format="%.0f"),
        "Forecast PURO": st.column_config.NumberColumn(format="%.0f"),
        "Forecast mín. (80%)": st.column_config.NumberColumn(format="%.0f"),
        "Forecast máx. (80%)": st.column_config.NumberColumn(format="%.0f"),
        "Venta prom. semanal": st.column_config.NumberColumn(format="%.1f"),
        "Venta prom. diaria": st.column_config.NumberColumn(format="%.1f"),
        "Error% PURO": st.column_config.NumberColumn(format="%.1f%%"),
        "LYSW": st.column_config.NumberColumn(format="%.0f"),
        "Promo%": st.column_config.NumberColumn(format="%.1f%%"),
        "CV (valor)": st.column_config.NumberColumn(format="%.3f"),
        "WMAPE serie": st.column_config.NumberColumn(format="%.1f%%"),
        "Sesgo (bias)": st.column_config.NumberColumn(format="%+.1f%%"),
        "Desvío estándar": st.column_config.NumberColumn(format="%.1f"),
        "Semanas hist. usadas": st.column_config.NumberColumn(format="%d"),
    }

    st.dataframe(
        df_tabla,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=560,
    )

    if truncado:
        st.caption(f"⚠ Tabla limitada a {MAX_ROWS:,} filas (total filtrado: {len(df_s):,}). Exportá para ver todo.")

    EXPORT_MAX_ROWS = 200_000  # Excel admite hasta ~1.048.576 filas por hoja.
    if len(df_filtrado) > EXPORT_MAX_ROWS:
        st.caption(
            f"⚠ Para exportar hay que acotar a menos de {EXPORT_MAX_ROWS:,} filas "
            f"con los filtros de la izquierda (actual: {len(df_filtrado):,})."
        )
    else:
        buffer = BytesIO()
        df_export = df_filtrado.copy()
        df_export[logic.DATE_COL] = pd.to_datetime(df_export[logic.DATE_COL]).dt.strftime("%d/%m/%Y")
        df_export.to_excel(buffer, index=False)
        st.download_button(
            "💾 Exportar a Excel",
            data=buffer.getvalue(),
            file_name="forecast_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

st.sidebar.caption(
    f"Filas filtradas: {len(df_filtrado):,}  ·  "
    f"Sem. históricas: {df_filtrado[df_filtrado['tipo']=='R'][logic.DATE_COL].nunique()}  ·  "
    f"Sem. forecast: {df_filtrado[df_filtrado['tipo']=='F'][logic.DATE_COL].nunique()}"
)
