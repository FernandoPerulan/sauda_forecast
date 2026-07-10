"""
Prueba standalone de la conexión a OneLake, sin necesidad de levantar Streamlit.

Lee las credenciales de .streamlit/secrets.toml y trata de leer la tabla del
forecast. Útil para depurar la conexión (permisos, nombres, secreto vencido)
antes de desplegar la app.

Uso:
    python scripts/probar_onelake.py
"""

import sys
import tomllib
from pathlib import Path


def main():
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        print(f"No se encontró {secrets_path}. Copiar secrets.toml.example y completarlo primero.")
        sys.exit(1)

    with open(secrets_path, "rb") as f:
        secrets = tomllib.load(f)

    faltantes = [
        k for k in ("ONELAKE_WORKSPACE", "ONELAKE_LAKEHOUSE", "AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
        if not secrets.get(k)
    ]
    if faltantes:
        print(f"Faltan completar en secrets.toml: {', '.join(faltantes)}")
        sys.exit(1)

    workspace = secrets["ONELAKE_WORKSPACE"]
    lakehouse = secrets["ONELAKE_LAKEHOUSE"]
    tabla = secrets.get("ONELAKE_TABLA_FORECAST", "forecast_final_semanal")
    path = f"abfss://{workspace}@onelake.dfs.fabric.microsoft.com/{lakehouse}.Lakehouse/Tables/{tabla}"

    storage_options = {
        "azure_tenant_id": secrets["AZURE_TENANT_ID"],
        "azure_client_id": secrets["AZURE_CLIENT_ID"],
        "azure_client_secret": secrets["AZURE_CLIENT_SECRET"],
        "use_fabric_endpoint": "true",
    }

    print(f"Conectando a: {path}")
    from deltalake import DeltaTable

    dt = DeltaTable(path, storage_options=storage_options)
    df = dt.to_pandas()
    print(f"OK — {len(df):,} filas, columnas: {list(df.columns)}")


if __name__ == "__main__":
    main()
