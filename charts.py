"""
Gráfico interactivo Real histórico vs F-MODELO (backtest + forecast) vs LYSW.

Portado desde dashboard_semanal.py (matplotlib) a Plotly, que da zoom/pan/hover
nativos en el navegador sin necesidad de manejar tooltips a mano.
"""

import pandas as pd
import plotly.graph_objects as go

from logic import DATE_COL

C = {
    "real":     "#2563EB",
    "bt_model": "#F472B6",
    "forecast": "#F97316",
    "lysw":     "#9CA3AF",
    "today":    "#16A34A",
    "vline":    "#374151",
    "fc_shade": "#FEF3C7",
}


def construir_figura(df: pd.DataFrame, hist_weeks: int) -> go.Figure:
    df_r = df[df["tipo"] == "R"].copy()
    df_f = df[df["tipo"] == "F"].copy()

    hist_agg = df_r.groupby(DATE_COL, as_index=False)["real"].sum()
    fc_agg = df_f.groupby(DATE_COL, as_index=False)["F-MODELO"].sum()

    bt_agg = (
        df_r[df_r["F-MODELO"].notna()].groupby(DATE_COL, as_index=False)["F-MODELO"].sum()
        if "F-MODELO" in df_r.columns else pd.DataFrame()
    )

    if "LYSW" in df.columns:
        lysw_agg = df.groupby(DATE_COL, as_index=False)["LYSW"].sum()
        lysw_agg = lysw_agg[lysw_agg["LYSW"] > 0]
    else:
        lysw_agg = pd.DataFrame()

    if hist_weeks and not hist_agg.empty:
        cutoff = hist_agg[DATE_COL].max() - pd.Timedelta(weeks=hist_weeks)
        hist_agg = hist_agg[hist_agg[DATE_COL] >= cutoff]
        if not bt_agg.empty:
            bt_agg = bt_agg[bt_agg[DATE_COL] >= cutoff]
        if not lysw_agg.empty:
            lysw_agg = lysw_agg[lysw_agg[DATE_COL] >= cutoff]

    fig = go.Figure()

    if not hist_agg.empty:
        fig.add_trace(go.Scatter(
            x=hist_agg[DATE_COL], y=hist_agg["real"],
            name="Real histórico", mode="lines+markers",
            line=dict(color=C["real"], width=2.5),
            marker=dict(size=6),
        ))

    if not bt_agg.empty:
        fig.add_trace(go.Scatter(
            x=bt_agg[DATE_COL], y=bt_agg["F-MODELO"],
            name="F-MODELO (backtest)", mode="lines",
            line=dict(color=C["bt_model"], width=1.4),
            opacity=0.85,
        ))

    if not fc_agg.empty:
        fig.add_trace(go.Scatter(
            x=fc_agg[DATE_COL], y=fc_agg["F-MODELO"],
            name="Forecast PURO", mode="lines+markers",
            line=dict(color=C["forecast"], width=2.6, dash="dash"),
            marker=dict(size=8, symbol="diamond"),
        ))
        fig.add_vrect(
            x0=fc_agg[DATE_COL].min(), x1=fc_agg[DATE_COL].max(),
            fillcolor=C["fc_shade"], opacity=0.35, line_width=0,
        )

    if not lysw_agg.empty:
        fig.add_trace(go.Scatter(
            x=lysw_agg[DATE_COL], y=lysw_agg["LYSW"],
            name="LYSW (año anterior)", mode="lines",
            line=dict(color=C["lysw"], width=1.6, dash="dot"),
        ))

    if "Promo" in df.columns:
        promo_flag = df["Promo"].astype(str).str.strip().isin(["1", "1.0", "True", "true"])
        promo_r_dates = df.loc[promo_flag & (df["tipo"] == "R"), DATE_COL].unique()
        promo_f_dates = df.loc[promo_flag & (df["tipo"] == "F"), DATE_COL].unique()

        if not hist_agg.empty and len(promo_r_dates) > 0:
            ph = hist_agg[hist_agg[DATE_COL].isin(promo_r_dates)]
            if not ph.empty:
                fig.add_trace(go.Scatter(
                    x=ph[DATE_COL], y=ph["real"], name="Semana con Promo",
                    mode="markers", marker=dict(symbol="star", size=12, color="black"),
                ))
        if not fc_agg.empty and len(promo_f_dates) > 0:
            pf = fc_agg[fc_agg[DATE_COL].isin(promo_f_dates)]
            if not pf.empty:
                fig.add_trace(go.Scatter(
                    x=pf[DATE_COL], y=pf["F-MODELO"], name="Semana con Promo",
                    mode="markers", marker=dict(symbol="star", size=12, color="black"),
                    showlegend=False,
                ))

    if "Feriado" in df.columns:
        feriado_flag = df["Feriado"].astype(str).str.strip().isin(["1", "1.0", "True", "true"])
        feriado_r_dates = df.loc[feriado_flag & (df["tipo"] == "R"), DATE_COL].unique()
        feriado_f_dates = df.loc[feriado_flag & (df["tipo"] == "F"), DATE_COL].unique()

        if not hist_agg.empty and len(feriado_r_dates) > 0:
            fh = hist_agg[hist_agg[DATE_COL].isin(feriado_r_dates)]
            if not fh.empty:
                fig.add_trace(go.Scatter(
                    x=fh[DATE_COL], y=fh["real"], name="Semana con Feriado",
                    mode="markers", marker=dict(symbol="diamond", size=9, color=C["today"]),
                ))
        if not fc_agg.empty and len(feriado_f_dates) > 0:
            ff = fc_agg[fc_agg[DATE_COL].isin(feriado_f_dates)]
            if not ff.empty:
                fig.add_trace(go.Scatter(
                    x=ff[DATE_COL], y=ff["F-MODELO"], name="Semana con Feriado",
                    mode="markers", marker=dict(symbol="diamond", size=9, color=C["today"]),
                    showlegend=False,
                ))

    if not hist_agg.empty:
        fig.add_vline(
            x=hist_agg[DATE_COL].max().timestamp() * 1000,
            line=dict(color=C["vline"], dash="dash", width=1.2),
            opacity=0.6,
        )

    fig.add_vline(
        x=pd.Timestamp.today().normalize().timestamp() * 1000,
        line=dict(color=C["today"], dash="dot", width=1.6),
        opacity=0.75,
    )

    fig.update_layout(
        title="Real histórico  vs  F-MODELO (backtest + forecast)  vs  LYSW",
        xaxis_title="Semana (inicio lunes)",
        yaxis_title="Cantidad",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=40, r=20, t=70, b=40),
        height=520,
        template="plotly_white",
    )
    fig.update_xaxes(tickformat="%d/%m/%y")
    fig.update_yaxes(tickformat=",.0f")

    return fig
