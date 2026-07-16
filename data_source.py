"""
Origen de datos del forecast semanal.

Dos modos, elegidos con el secret/env var DATA_SOURCE:

- "parquet"  : lee Data/forecast_final_semanal.parquet en el filesystem local.
               Útil para desarrollo sin acceso al Lakehouse.
- "onelake"  : lee la tabla Delta directo de OneLake (Microsoft Fabric) con el
               paquete `deltalake` (Python puro), autenticado con un Service
               Principal de Microsoft Entra ID. No requiere ningún driver de
               sistema, por eso funciona en Streamlit Community Cloud (donde
               no se puede instalar el ODBC Driver de Microsoft que exigiría
               conectarse por el SQL Analytics Endpoint).

El Service Principal necesita rol Contributor (o superior) en el workspace de
Fabric: el rol Viewer no incluye el permiso "ReadAll" que exige la lectura
directa de archivos vía OneLake.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

_BASE = Path(__file__).resolve().parent
FORECAST_PARQUET_PATH = _BASE / "Data" / "forecast_final_semanal.parquet"

# TTL largo: el pipeline corre semanalmente y la lectura completa desde
# OneLake es pesada (~1 minuto, cientos de MB) — no tiene sentido repetirla
# cada pocos minutos. "🔄 Recargar datos" fuerza una lectura nueva de todos modos.
_ONELAKE_CACHE_TTL = 3600

# Columnas realmente usadas por la app (ver logic.py). Pedir solo estas —en
# vez de las ~24 que trae la tabla real, que además incluye columnas todavía
# sin usar en el dashboard (IDSucursal, IDArticulo, week_of_year)— reduce
# bastante la memoria y el tiempo de lectura. Nombres en crudo, tal como
# están en la tabla del Lakehouse (antes del rename de logic.py).
_ONELAKE_COLUMNAS_NECESARIAS = [
    "FechaCbte", "Sucursal", "Departamento", "Familia", "SubFamilia",
    "Articulo_Desc", "Cluster", "cv_grupo", "cv_valor", "real", "F_MODELO",
    "F_MIN", "F_MAX", "Promo", "Feriado", "LYSW",
    "confiabilidad", "wmape", "bias_pct", "desv_estandar", "n_hist",
]

# Columnas de texto con pocos valores únicos repetidos en ~2M filas. Se
# convierten a "dictionary encoded" (equivalente Arrow de category) ANTES de
# pasar a pandas: de lo contrario pandas materializa cada fila como un
# string de Python suelto y el pico de memoria durante la conversión llega a
# ~950MB (llegó a tirar Segmentation fault en Streamlit Cloud); codificando
# antes, el pico baja a ~150-390MB.
_ONELAKE_COLUMNAS_CATEGORICAS = [
    "Sucursal", "Departamento", "Familia", "SubFamilia",
    "Articulo_Desc", "Cluster", "cv_grupo", "confiabilidad",
]


def _secret(nombre: str, default: str = "") -> str:
    return str(st.secrets.get(nombre, default))


def _onelake_table_path(tabla: str) -> str:
    workspace = _secret("ONELAKE_WORKSPACE")
    lakehouse = _secret("ONELAKE_LAKEHOUSE")
    # Los Lakehouse con esquemas habilitados (carpeta "dbo" debajo de Tables
    # en el explorador de Fabric) requieren el esquema en la ruta; los que no
    # tienen esquemas dejan ONELAKE_SCHEMA vacío y se omite ese segmento.
    schema = _secret("ONELAKE_SCHEMA")
    segmento_tabla = f"{schema}/{tabla}" if schema else tabla
    return f"abfss://{workspace}@onelake.dfs.fabric.microsoft.com/{lakehouse}.Lakehouse/Tables/{segmento_tabla}"


def _onelake_storage_options() -> dict:
    return {
        "azure_tenant_id": _secret("AZURE_TENANT_ID"),
        "azure_client_id": _secret("AZURE_CLIENT_ID"),
        "azure_client_secret": _secret("AZURE_CLIENT_SECRET"),
        # OneLake responde en onelake.dfs.fabric.microsoft.com en vez del
        # dominio estándar de ADLS Gen2 (<cuenta>.dfs.core.windows.net); este
        # flag es reconocido por delta-rs para las rutas/endpoints de Fabric.
        # (delta-rs también trae claves separadas para "workload identity"
        # dentro de un runtime de Fabric —azure_fabric_workload_host,
        # azure_fabric_session_token—, que NO aplican acá: nos autenticamos
        # como Service Principal externo, no desde dentro de Fabric.)
        "use_fabric_endpoint": "true",
    }


@st.cache_data(ttl=_ONELAKE_CACHE_TTL, show_spinner="Consultando OneLake...")
def _leer_onelake(tabla: str) -> pd.DataFrame:
    from deltalake import DeltaTable

    dt = DeltaTable(_onelake_table_path(tabla), storage_options=_onelake_storage_options())
    tabla_arrow = dt.to_pyarrow_table(columns=_ONELAKE_COLUMNAS_NECESARIAS)

    for col in _ONELAKE_COLUMNAS_CATEGORICAS:
        if col in tabla_arrow.schema.names:
            idx = tabla_arrow.schema.get_field_index(col)
            tabla_arrow = tabla_arrow.set_column(idx, col, tabla_arrow.column(col).dictionary_encode())

    return tabla_arrow.to_pandas()


@st.cache_data(ttl=600, show_spinner="Leyendo archivo local...")
def _leer_parquet_local() -> pd.DataFrame:
    if not FORECAST_PARQUET_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró {FORECAST_PARQUET_PATH}.\n"
            "En modo 'parquet', copiar ahí el archivo generado por el pipeline, "
            "o cambiar DATA_SOURCE a 'onelake' en secrets.toml."
        )
    return pd.read_parquet(FORECAST_PARQUET_PATH)


def cargar_forecast_raw() -> pd.DataFrame:
    modo = _secret("DATA_SOURCE", "parquet")
    if modo == "onelake":
        tabla = _secret("ONELAKE_TABLA_FORECAST", "forecast_final_semanal")
        return _leer_onelake(tabla)
    return _leer_parquet_local()


@st.cache_data(ttl=_ONELAKE_CACHE_TTL, show_spinner=False)
def obtener_estado_datos() -> dict:
    """Frescura del origen de datos: cuándo se escribió por última vez y cuántas filas tenía.

    En modo OneLake usa el historial de commits de la tabla Delta (no hace
    falta ninguna llamada extra a la API de Fabric ni permisos adicionales).
    En modo parquet usa la fecha de modificación del archivo local.
    """
    modo = _secret("DATA_SOURCE", "parquet")

    if modo == "onelake":
        from deltalake import DeltaTable

        tabla = _secret("ONELAKE_TABLA_FORECAST", "forecast_final_semanal")
        dt = DeltaTable(_onelake_table_path(tabla), storage_options=_onelake_storage_options())
        historial = dt.history(limit=1)
        if not historial:
            return {"actualizado": None, "filas": None}
        ultimo = historial[0]
        filas = (ultimo.get("operationMetrics") or {}).get("numOutputRows")
        return {
            "actualizado": datetime.fromtimestamp(ultimo["timestamp"] / 1000, tz=timezone.utc),
            "filas": int(filas) if filas is not None else None,
        }

    if FORECAST_PARQUET_PATH.exists():
        mtime = FORECAST_PARQUET_PATH.stat().st_mtime
        return {"actualizado": datetime.fromtimestamp(mtime, tz=timezone.utc), "filas": None}
    return {"actualizado": None, "filas": None}
