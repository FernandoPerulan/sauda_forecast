"""
Transformación de datos, filtros y métricas del forecast semanal de SAUDA.

Portado desde dashboard_semanal.py (versión Tkinter), sin cambios en la lógica
de negocio. La diferencia es que `transformar_datos` recibe un DataFrame crudo
en lugar de leerlo directamente de un archivo (el origen lo resuelve data_source.py).
"""

import numpy as np
import pandas as pd

DATE_COL = "FechaCbte"
HIST_WEEKS_DEFAULT = 26
ALL = "Todos"

FILTRO_COLS = [
    ("Sucursal",     "Sucursal"),
    ("Departamento", "Departamento"),
    ("Familia",      "Familia"),
    ("SubFamilia",   "SubFamilia"),
    ("Artículo",     "Articulo Desc"),
    ("Cluster",      "Cluster"),
    ("Grupo CV",     "cv_grupo"),   # A = baja variab. | B = media | C = alta
]

TABLE_COLS = [
    ("FechaCbte",           "Fecha"),
    ("Sucursal",            "Sucursal"),
    ("Departamento",        "Departamento"),
    ("Familia",             "Familia"),
    ("SubFamilia",          "SubFamilia"),
    ("Articulo Desc",       "Artículo"),
    ("Cluster",             "Cluster"),
    ("cv_grupo",            "Grupo CV"),
    ("cv_valor",            "CV (valor)"),
    ("real",                "Real (unid.)"),
    ("F-MODELO",            "Forecast PURO"),
    ("F_MIN",               "Forecast mín. (80%)"),
    ("F_MAX",               "Forecast máx. (80%)"),
    ("venta_prom_semanal",  "Venta prom. semanal"),
    ("venta_prom_diario",   "Venta prom. diaria"),
    ("error_pct",           "Error% PURO"),
    ("LYSW",                "LYSW"),
    ("Promo",               "Promo"),
    ("promo_pct",           "Promo%"),
    ("Feriado",             "Feriado"),
    ("confiabilidad",       "Confiabilidad"),
    ("wmape",               "WMAPE serie"),
    ("bias_pct",            "Sesgo (bias)"),
    ("desv_estandar",       "Desvío estándar"),
    ("n_hist",              "Semanas hist. usadas"),
]

COL_DISPLAY = {orig: disp for orig, disp in TABLE_COLS}


def transformar_datos(df: pd.DataFrame) -> pd.DataFrame:
    # Sin .copy(): el df que llega ya es una copia aislada (viene de una
    # función cacheada con @st.cache_data, que entrega una copia nueva en
    # cada llamada), y con ~2M filas duplicar el DataFrame acá arriba puede
    # duplicar el pico de memoria sin necesidad.

    # La tabla del Lakehouse usa "_" donde el resto del código espera "-" o
    # espacio (los caracteres originales no son válidos como nombre de
    # columna SQL/Delta). rename() ignora en silencio las claves que no
    # existan, así que es seguro también cuando el origen ya viene con los
    # nombres "correctos" (modo parquet local). inplace evita otra copia.
    df.rename(columns={
        "F_MODELO": "F-MODELO",
        "Articulo_Desc": "Articulo Desc",
    }, inplace=True)

    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce").dt.normalize()

    if "tipo" not in df.columns:
        if "forecast" in df.columns:
            df["tipo"] = np.where(
                df["forecast"].notna() & df["real"].isna(), "F", "R"
            )
        else:
            # La tabla de producción no trae columna "forecast": una fila es
            # de forecast cuando todavía no tiene venta real registrada.
            df["tipo"] = np.where(df["real"].isna(), "F", "R")

    for col in [
        "real", "forecast", "LYSW", "F-MODELO",
        "cv_valor", "desv_estandar", "F_MIN", "F_MAX",
        "wmape", "bias_pct", "n_hist",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Error porcentual PURO: (real − Forecast PURO) / Forecast PURO × 100
    if "real" in df.columns and "F-MODELO" in df.columns:
        mask = df["real"].notna() & df["F-MODELO"].notna() & (df["F-MODELO"] > 0)
        df["error_pct"] = np.nan
        df.loc[mask, "error_pct"] = (
            (df.loc[mask, "real"] - df.loc[mask, "F-MODELO"])
            / df.loc[mask, "F-MODELO"]
            * 100
        )

    # Venta promedio semanal/diaria por artículo-sucursal (primeras 4 semanas de forecast)
    df["venta_prom_semanal"] = np.nan
    df["venta_prom_diario"] = np.nan
    df_f_temp = df[df["tipo"] == "F"]
    if not df_f_temp.empty and "F-MODELO" in df_f_temp.columns:
        fechas_4 = df_f_temp[DATE_COL].drop_duplicates().nsmallest(4)
        df_4w = df_f_temp[df_f_temp[DATE_COL].isin(fechas_4)]
        grp_cols = [c for c in ["Sucursal", "Articulo Desc"] if c in df.columns]
        if grp_cols:
            vp_df = (
                # observed=True: grp_cols puede ser category (ver data_source.py);
                # sin esto, groupby generaría el producto cartesiano de TODAS las
                # combinaciones posibles de sucursal×artículo, no solo las reales.
                df_4w.groupby(grp_cols, as_index=False, observed=True)["F-MODELO"]
                .sum()
                .rename(columns={"F-MODELO": "_fc4"})
            )
            vp_df["venta_prom_semanal"] = vp_df["_fc4"] / 4
            vp_df["venta_prom_diario"] = vp_df["_fc4"] / 28
            vp_df = vp_df.drop(columns=["_fc4"])

            df_f_idx = df[df["tipo"] == "F"].index
            merged = df.loc[df_f_idx, grp_cols].merge(vp_df, on=grp_cols, how="left")
            df.loc[df_f_idx, "venta_prom_semanal"] = merged["venta_prom_semanal"].values
            df.loc[df_f_idx, "venta_prom_diario"] = merged["venta_prom_diario"].values

    # Promo%: (real − LYSW) / LYSW × 100 en semanas con Promo = 1
    df["promo_pct"] = np.nan
    if all(c in df.columns for c in ["Promo", "real", "LYSW"]):
        promo_flag = df["Promo"].astype(str).str.strip().isin(["1", "1.0", "True", "true"])
        con_promo_mask = (
            promo_flag
            & (df.get("tipo", pd.Series("R", index=df.index)) == "R")
            & df["real"].notna()
            & (df["real"] > 0)
            & df["LYSW"].notna()
            & (df["LYSW"] > 0)
        )
        df.loc[con_promo_mask, "promo_pct"] = (
            (df.loc[con_promo_mask, "real"] - df.loc[con_promo_mask, "LYSW"])
            / df.loc[con_promo_mask, "LYSW"]
            * 100
        )

    for _, dcol in FILTRO_COLS:
        if dcol in df.columns:
            df[dcol] = df[dcol].astype(str).str.strip()
            df.loc[df[dcol].isin(["nan", "None", ""]), dcol] = pd.NA
            # category en vez de string: estas columnas tienen pocos valores
            # únicos repetidos en millones de filas — con ~2M filas la
            # diferencia de memoria es de cientos de MB a unos pocos.
            df[dcol] = df[dcol].astype("category")

    return df.sort_values(DATE_COL)


def aplicar_filtros(df: pd.DataFrame, filtros: dict) -> pd.DataFrame:
    for col, val in filtros.items():
        if val and val != ALL and col in df.columns:
            df = df[df[col].astype(str).str.strip() == val]
    return df.copy()


def opciones_col(df: pd.DataFrame, col: str) -> list:
    if col not in df.columns:
        return []
    return (
        df[col].dropna()
        .astype(str).str.strip()
        .replace("", pd.NA).dropna()
        .drop_duplicates().sort_values()
        .tolist()
    )


def calcular_metricas(df: pd.DataFrame) -> dict:
    df_r = df[df["tipo"] == "R"]
    df_f = df[df["tipo"] == "F"]

    fc_total = float(df_f["F-MODELO"].sum()) if "F-MODELO" in df_f.columns else 0.0
    lysw_total = float(df_f["LYSW"].sum()) if "LYSW" in df_f.columns else 0.0

    var_lysw = (
        (fc_total - lysw_total) / lysw_total * 100
        if lysw_total > 0 else float("nan")
    )

    if not df_r.empty and "real" in df_r.columns:
        ultimas_4 = df_r[DATE_COL].drop_duplicates().nlargest(4)
        hist_4 = float(df_r[df_r[DATE_COL].isin(ultimas_4)]["real"].sum())
    else:
        hist_4 = 0.0

    df_bt = df[df["real"].notna() & df["F-MODELO"].notna() & (df["real"] > 0)] \
        if "F-MODELO" in df.columns else pd.DataFrame()
    if not df_bt.empty and "error_abs" in df_bt.columns:
        wape = float(df_bt["error_abs"].sum() / df_bt["real"].sum() * 100)
    else:
        wape = float("nan")

    promo_uplift = float("nan")
    if "promo_pct" in df.columns:
        vals = df.loc[(df["tipo"] == "R") & df["promo_pct"].notna(), "promo_pct"]
        if not vals.empty:
            promo_uplift = float(vals.mean())

    if not df_f.empty and "F-MODELO" in df_f.columns:
        fechas_fut = df_f[DATE_COL].drop_duplicates().nsmallest(4)
        fc_4 = float(df_f[df_f[DATE_COL].isin(fechas_fut)]["F-MODELO"].sum())
        venta_prom_semanal = fc_4 / 4
        venta_prom_diario = fc_4 / 28
    else:
        venta_prom_semanal = float("nan")
        venta_prom_diario = float("nan")

    return {
        "fc_total": fc_total,
        "lysw_total": lysw_total,
        "var_lysw": var_lysw,
        "hist_4sem": hist_4,
        "wape": wape,
        "promo_uplift": promo_uplift,
        "venta_prom_semanal": venta_prom_semanal,
        "venta_prom_diario": venta_prom_diario,
    }
