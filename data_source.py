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

El Service Principal necesita acceso de lectura al workspace/Lakehouse de
Fabric (rol Viewer o superior).
"""

from pathlib import Path

import pandas as pd
import streamlit as st

_BASE = Path(__file__).resolve().parent
FORECAST_PARQUET_PATH = _BASE / "Data" / "forecast_final_semanal.parquet"


def _secret(nombre: str, default: str = "") -> str:
    return str(st.secrets.get(nombre, default))


def _onelake_table_path(tabla: str) -> str:
    workspace = _secret("ONELAKE_WORKSPACE")
    lakehouse = _secret("ONELAKE_LAKEHOUSE")
    return f"abfss://{workspace}@onelake.dfs.fabric.microsoft.com/{lakehouse}.Lakehouse/Tables/{tabla}"


@st.cache_data(ttl=600, show_spinner="Consultando OneLake...")
def _leer_onelake(tabla: str) -> pd.DataFrame:
    from deltalake import DeltaTable

    storage_options = {
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
    dt = DeltaTable(_onelake_table_path(tabla), storage_options=storage_options)
    return dt.to_pandas()


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
