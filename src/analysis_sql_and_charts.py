# ==============================================================================
# PROYECTO 3: Análisis de Accidentes de Tránsito en Zonas Urbanas (US Accidents)
# Ejecución de Consultas SQL + Generación de Gráficas Analíticas en Python
# ==============================================================================
# Ejecuta las consultas SQL contra data/us_accidents.db, exporta los resultados
# tabulares a resultados/ y genera las visualizaciones de Python (Matplotlib +
# Seaborn) en assets/charts/ para los 10 requerimientos analíticos y demografía.
# ==============================================================================

import json
import os
import sqlite3
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "us_accidents.db")
PARQUET_PATH = os.path.join(BASE_DIR, "data", "us_accidents_clean.parquet")
OUT_RESULTS = os.path.join(BASE_DIR, "resultados")
OUT_CHARTS = os.path.join(BASE_DIR, "assets", "charts")

os.makedirs(OUT_RESULTS, exist_ok=True)
os.makedirs(OUT_CHARTS, exist_ok=True)

# Estilo visual uniforme y limpio
sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "font.family": "sans-serif",
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "xtick.labelsize": 9.5,
    "ytick.labelsize": 9.5,
})


def query_sql(conn: sqlite3.Connection, sql: str, csv_name: str | None = None) -> pd.DataFrame:
    df = pd.read_sql_query(sql, conn)
    if csv_name:
        df.to_csv(os.path.join(OUT_RESULTS, csv_name), index=False, encoding="utf-8")
    return df


def fmt_k(x: float) -> str:
    if x >= 1_000_000:
        return f"{x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"{x/1_000:.1f}K"
    return f"{int(x)}"


def main():
    t0 = time.time()
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -1048576")
    conn.execute("PRAGMA mmap_size = 4294967296")
    summary = {}

    print("==============================================================================")
    print(" PROYECTO 3: ANALISIS DE ACCIDENTES DE TRANSITO EN ZONAS URBANAS (US-ACCIDENTS)")
    print("==============================================================================")
    print("=== 1. Auditoría General SQL ===")
    df_audit = query_sql(conn, """
        SELECT
            COUNT(*) AS total_registros,
            COUNT(DISTINCT state) AS estados_cubiertos,
            COUNT(DISTINCT city) AS ciudades_cubiertas,
            MIN(start_time) AS fecha_inicio,
            MAX(start_time) AS fecha_fin,
            ROUND(AVG(duration_raw_min), 2) AS duracion_media_bruta_min,
            ROUND(AVG(duration_clean_min), 2) AS duracion_media_depurada_min,
            ROUND(AVG(severity), 3) AS severidad_media_global
        FROM accidents
    """, "01_auditoria_general.csv")
    total_n = int(df_audit["total_registros"].iloc[0])
    summary["auditoria"] = df_audit.iloc[0].to_dict()
    print(df_audit.to_string(index=False))

    # --------------------------------------------------------------------------
    # REQ 1: Frecuencia por Estado, Ciudad y Demografía (Tasa x 100k hab)
    # --------------------------------------------------------------------------
    print("\n=== Req 1: Estados, Ciudades y Demografía ===")
    df_states = query_sql(conn, f"""
        SELECT
            a.state,
            d.state_name,
            d.region,
            d.population_2023,
            d.density_per_sqmi,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_nacional,
            ROUND(COUNT(*) * 100000.0 / d.population_2023, 2) AS tasa_x_100k_hab,
            ROUND(AVG(a.severity), 3) AS severidad_promedio
        FROM accidents a
        LEFT JOIN dim_demographics d ON a.state = d.state
        GROUP BY a.state, d.state_name, d.region, d.population_2023, d.density_per_sqmi
        ORDER BY total_accidentes DESC
    """, "02_accidentes_por_estado_demografia.csv")

    df_cities = query_sql(conn, f"""
        SELECT
            city,
            state,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_nacional,
            ROUND(AVG(severity), 3) AS severidad_promedio,
            SUM(CASE WHEN severity >= 3 THEN 1 ELSE 0 END) AS accidentes_graves
        FROM accidents
        WHERE city IS NOT NULL AND city <> 'Sin dato'
        GROUP BY city, state
        ORDER BY total_accidentes DESC
        LIMIT 15
    """, "03_top15_ciudades.csv")

    df_regions = query_sql(conn, f"""
        SELECT
            d.region,
            COUNT(DISTINCT a.state) AS estados,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_total,
            ROUND(AVG(a.severity), 3) AS severidad_promedio
        FROM accidents a
        INNER JOIN dim_demographics d ON a.state = d.state
        GROUP BY d.region
        ORDER BY total_accidentes DESC
    """, "04_resumen_regional.csv")

    summary["top5_estados"] = df_states.head(5).to_dict(orient="records")
    summary["top5_estados_tasa"] = df_states.sort_values("tasa_x_100k_hab", ascending=False).head(5).to_dict(orient="records")
    summary["top10_ciudades"] = df_cities.head(10).to_dict(orient="records")
    summary["regiones"] = df_regions.to_dict(orient="records")

    print("\n[Req 1a] Top 10 Estados por Volumen:")
    print(df_states[["state", "state_name", "region", "total_accidentes", "pct_nacional", "tasa_x_100k_hab", "severidad_promedio"]].head(10).to_string(index=False))
    print("\n[Req 1b] Top 10 Estados por Tasa Demográfica (x 100k hab.):")
    print(df_states.sort_values("tasa_x_100k_hab", ascending=False)[["state", "state_name", "population_2023", "total_accidentes", "tasa_x_100k_hab"]].head(10).to_string(index=False))
    print("\n[Req 1c] Top 10 Ciudades Urbanas:")
    print(df_cities.head(10).to_string(index=False))
    print("\n[Req 1d] Resumen por Región Censal:")
    print(df_regions.to_string(index=False))

    # Gráfica 01: Top 10 Estados y Top 10 Ciudades
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    top10_st = df_states.head(10).sort_values("total_accidentes")
    bars1 = axes[0].barh(top10_st["state_name"] + " (" + top10_st["state"] + ")", top10_st["total_accidentes"], color="#1d4ed8")
    axes[0].set_title("Top 10 Estados con Mayor Frecuencia de Accidentes")
    axes[0].set_xlabel("Total de Accidentes")
    axes[0].xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[0].set_xlim(0, top10_st["total_accidentes"].max() * 1.18)
    for b in bars1:
        w = b.get_width()
        axes[0].text(w * 1.02, b.get_y() + b.get_height()/2, fmt_k(w), va="center", fontsize=9, fontweight="bold")

    top10_ct = df_cities.head(10).sort_values("total_accidentes")
    bars2 = axes[1].barh(top10_ct["city"] + ", " + top10_ct["state"], top10_ct["total_accidentes"], color="#0284c7")
    axes[1].set_title("Top 10 Ciudades Urbanas con Más Accidentes")
    axes[1].set_xlabel("Total de Accidentes")
    axes[1].xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[1].set_xlim(0, top10_ct["total_accidentes"].max() * 1.18)
    for b in bars2:
        w = b.get_width()
        axes[1].text(w * 1.02, b.get_y() + b.get_height()/2, fmt_k(w), va="center", fontsize=9, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "01_top10_estados_y_ciudades.png"))
    plt.close()

    # Gráfica 02: Tasa Demográfica x 100k Hab + Regiones
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    top10_rate = df_states.sort_values("tasa_x_100k_hab", ascending=False).head(12).sort_values("tasa_x_100k_hab")
    bars_r = axes[0].barh(top10_rate["state_name"] + " (" + top10_rate["state"] + ")", top10_rate["tasa_x_100k_hab"], color="#dc2626")
    axes[0].set_title("Top 12 Estados por Tasa Demográfica (x 100,000 Hab.)")
    axes[0].set_xlabel("Accidentes acumulados por cada 100k habitantes (Censo 2023)")
    axes[0].set_xlim(0, top10_rate["tasa_x_100k_hab"].max() * 1.18)
    for b in bars_r:
        w = b.get_width()
        axes[0].text(w * 1.02, b.get_y() + b.get_height()/2, f"{w:,.0f}", va="center", fontsize=9, fontweight="bold")

    reg_plot = df_regions.sort_values("total_accidentes", ascending=False)
    bars_reg = axes[1].bar(reg_plot["region"], reg_plot["total_accidentes"], color=["#2563eb", "#0ea5e9", "#f59e0b", "#64748b"])
    axes[1].set_title("Distribución de Accidentes por Región Censal")
    axes[1].set_ylabel("Total de Accidentes")
    axes[1].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[1].set_ylim(0, reg_plot["total_accidentes"].max() * 1.15)
    for b, pct in zip(bars_reg, reg_plot["pct_total"]):
        h = b.get_height()
        axes[1].text(b.get_x() + b.get_width()/2, h * 1.02, f"{fmt_k(h)}\n({pct}%)", ha="center", va="bottom", fontsize=9.5, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "02_demografia_tasa_y_regiones.png"))
    plt.close()

    # --------------------------------------------------------------------------
    # REQ 2 & REQ 6: Hora del día, Día de la semana y Matriz Hora x Día
    # --------------------------------------------------------------------------
    print("=== Req 2 y 6: Hora del Día y Días de la Semana ===")
    df_hour = query_sql(conn, f"""
        SELECT
            hour,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_total,
            ROUND(AVG(severity), 3) AS severidad_promedio
        FROM accidents
        WHERE hour IS NOT NULL
        GROUP BY hour
        ORDER BY hour ASC
    """, "05_accidentes_por_hora.csv")

    df_day = query_sql(conn, f"""
        SELECT
            day_of_week_num,
            day_name,
            CASE WHEN is_weekend = 1 THEN 'Fin de Semana' ELSE 'Día Laboral' END AS tipo_dia,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_total,
            ROUND(AVG(severity), 3) AS severidad_promedio
        FROM accidents
        GROUP BY day_of_week_num, day_name, is_weekend
        ORDER BY day_of_week_num ASC
    """, "06_accidentes_por_dia_semana.csv")

    df_hour_day = query_sql(conn, """
        SELECT day_of_week_num, day_name, hour, COUNT(*) AS total
        FROM accidents
        WHERE hour IS NOT NULL
        GROUP BY day_of_week_num, day_name, hour
        ORDER BY day_of_week_num, hour
    """)

    df_light = query_sql(conn, f"""
        SELECT
            sunrise_sunset,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_total,
            ROUND(AVG(severity), 3) AS severidad_promedio
        FROM accidents
        GROUP BY sunrise_sunset
        ORDER BY total_accidentes DESC
    """, "06b_ciclo_luz.csv")

    summary["por_hora"] = df_hour.to_dict(orient="records")
    summary["por_dia"] = df_day.to_dict(orient="records")
    summary["ciclo_luz"] = df_light.to_dict(orient="records")

    print("\n[Req 2] Top 8 Horas de Mayor Accidentalidad:")
    print(df_hour.sort_values("total_accidentes", ascending=False).head(8).to_string(index=False))
    print("\n[Req 6] Accidentes por Día de la Semana:")
    print(df_day.to_string(index=False))
    print("\n[Req 2/6b] Ciclo de Luz Solar (Día vs Noche):")
    print(df_light.to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    axes[0].fill_between(df_hour["hour"], df_hour["total_accidentes"], color="#0284c7", alpha=0.25)
    axes[0].plot(df_hour["hour"], df_hour["total_accidentes"], marker="o", color="#0369a1", linewidth=2.4)
    axes[0].axvspan(7, 9, color="#f59e0b", alpha=0.16, label="Pico Mañana (07–09h)")
    axes[0].axvspan(15, 18, color="#ef4444", alpha=0.14, label="Pico Tarde (15–18h)")
    axes[0].set_title("Distribución Horaria de Accidentes (00h–23h)")
    axes[0].set_xlabel("Hora del Día")
    axes[0].set_ylabel("Total de Accidentes")
    axes[0].set_xticks(range(0, 24, 2))
    axes[0].set_ylim(0, df_hour["total_accidentes"].max() * 1.15)
    axes[0].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[0].legend(loc="upper right")

    colors_day = ["#f97316" if t == "Fin de Semana" else "#2563eb" for t in df_day["tipo_dia"]]
    bars_d = axes[1].bar(df_day["day_name"], df_day["total_accidentes"], color=colors_day)
    axes[1].set_title("Accidentes por Día de la Semana (Laboral vs Fin de Semana)")
    axes[1].set_ylabel("Total de Accidentes")
    axes[1].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[1].set_ylim(0, df_day["total_accidentes"].max() * 1.15)
    for b, pct in zip(bars_d, df_day["pct_total"]):
        h = b.get_height()
        axes[1].text(b.get_x() + b.get_width()/2, h * 1.02, f"{fmt_k(h)}\n({pct}%)", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "03_patron_horario_y_semanal.png"))
    plt.close()

    # Gráfica 04: Heatmap Hora x Día de la semana
    piv_hd = df_hour_day.pivot(index="day_name", columns="hour", values="total")
    day_order = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    piv_hd = piv_hd.reindex(day_order)
    plt.figure(figsize=(14, 5.2))
    sns.heatmap(piv_hd / 1000.0, cmap="YlOrRd", linewidths=0.3, cbar_kws={"label": "Miles de accidentes"})
    plt.title("Mapa de Calor: Concentración de Accidentes por Día de la Semana y Hora")
    plt.xlabel("Hora del Día (00–23h)")
    plt.ylabel("Día de la Semana")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "04_heatmap_dia_hora.png"))
    plt.close()

    # --------------------------------------------------------------------------
    # REQ 3 & REQ 7: Severidad y Duración del Incidente (Bruta vs Depurada)
    # --------------------------------------------------------------------------
    print("=== Req 3 y 7: Severidad y Duración ===")
    df_sev = query_sql(conn, f"""
        SELECT
            severity,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_total,
            ROUND(AVG(distance_mi), 3) AS distancia_media_mi,
            ROUND(AVG(duration_raw_min), 2) AS duracion_media_bruta_min,
            ROUND(AVG(duration_clean_min), 2) AS duracion_media_depurada_min
        FROM accidents
        GROUP BY severity
        ORDER BY severity ASC
    """, "07_severidad_y_duracion.csv")

    # Mediana exacta desde Parquet en memoria compacta (solo 2 columnas)
    df_dur_cols = pd.read_parquet(PARQUET_PATH, columns=["severity", "duration_raw_min", "duration_clean_min"])
    med_raw = df_dur_cols.groupby("severity")["duration_raw_min"].median().round(2)
    med_clean = df_dur_cols.groupby("severity")["duration_clean_min"].median().round(2)
    df_sev["mediana_bruta_min"] = df_sev["severity"].map(med_raw)
    df_sev["mediana_depurada_min"] = df_sev["severity"].map(med_clean)
    df_sev.to_csv(os.path.join(OUT_RESULTS, "07_severidad_y_duracion.csv"), index=False, encoding="utf-8")

    summary["mediana_global_bruta_min"] = round(float(df_dur_cols["duration_raw_min"].median()), 2)
    summary["mediana_global_depurada_min"] = round(float(df_dur_cols["duration_clean_min"].median()), 2)
    summary["media_global_bruta_min"] = round(float(df_dur_cols["duration_raw_min"].mean()), 2)
    summary["media_global_depurada_min"] = round(float(df_dur_cols["duration_clean_min"].mean()), 2)
    summary["severidad"] = df_sev.to_dict(orient="records")

    print("\n[Req 3 y 7] Severidad y Duración del Incidente (Global: Media Bruta =",
          f"{summary['media_global_bruta_min']}m | Media Depurada <=24h = {summary['media_global_depurada_min']}m | Mediana Depurada = {summary['mediana_global_depurada_min']}m):")
    print(df_sev.to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.5))
    sev_colors = ["#38bdf8", "#1e3a8a", "#ea580c", "#7e22ce"]
    bars_s = axes[0].bar(df_sev["severity"].astype(str), df_sev["total_accidentes"], color=sev_colors)
    axes[0].set_title("Distribución de Accidentes por Nivel de Severidad")
    axes[0].set_xlabel("Nivel de Severidad (1 = Leve ... 4 = Crítica)")
    axes[0].set_ylabel("Total de Accidentes")
    axes[0].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[0].set_ylim(0, df_sev["total_accidentes"].max() * 1.15)
    for b, pct in zip(bars_s, df_sev["pct_total"]):
        h = b.get_height()
        axes[0].text(b.get_x() + b.get_width()/2, h * 1.02, f"{fmt_k(h)}\n({pct}%)", ha="center", va="bottom", fontsize=9.5, fontweight="bold")

    x = np.arange(len(df_sev))
    w_bar = 0.27
    b1 = axes[1].bar(x - w_bar, df_sev["duracion_media_bruta_min"], width=w_bar, label="Media Bruta (con outliers)", color="#94a3b8")
    b2 = axes[1].bar(x, df_sev["duracion_media_depurada_min"], width=w_bar, label="Media Depurada (≤24h)", color="#0284c7")
    b3 = axes[1].bar(x + w_bar, df_sev["mediana_depurada_min"], width=w_bar, label="Mediana Depurada", color="#f97316")
    axes[1].set_title("Duración del Incidente por Severidad (Media vs Mediana)")
    axes[1].set_xlabel("Nivel de Severidad")
    axes[1].set_ylabel("Duración (minutos)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"Sev {s}" for s in df_sev["severity"]])
    axes[1].set_ylim(0, df_sev["duracion_media_bruta_min"].max() * 1.18)
    axes[1].legend()
    for grp in [b1, b2, b3]:
        for bar in grp:
            val = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width()/2, val + 18, f"{val:.0f}", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "05_severidad_y_duracion.png"))
    plt.close()
    del df_dur_cols

    # --------------------------------------------------------------------------
    # REQ 4: Condiciones Climáticas y Severidad
    # --------------------------------------------------------------------------
    print("=== Req 4: Condiciones Climáticas ===")
    df_weather = query_sql(conn, f"""
        SELECT
            weather_group,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_total,
            SUM(CASE WHEN severity = 1 THEN 1 ELSE 0 END) AS sev_1,
            SUM(CASE WHEN severity = 2 THEN 1 ELSE 0 END) AS sev_2,
            SUM(CASE WHEN severity = 3 THEN 1 ELSE 0 END) AS sev_3,
            SUM(CASE WHEN severity = 4 THEN 1 ELSE 0 END) AS sev_4,
            ROUND(SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_graves,
            ROUND(AVG(visibility_mi), 2) AS visibilidad_media_mi,
            ROUND(AVG(temperature_f), 2) AS temperatura_media_f
        FROM accidents
        GROUP BY weather_group
        ORDER BY total_accidentes DESC
    """, "08_accidentes_por_clima.csv")
    summary["clima"] = df_weather.to_dict(orient="records")
    print("\n[Req 4] Accidentes y Severidad por Condición Climática:")
    print(df_weather.to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    w_ord = df_weather.sort_values("total_accidentes")
    bw = axes[0].barh(w_ord["weather_group"], w_ord["total_accidentes"], color="#0ea5e9")
    axes[0].set_title("Volumen Total de Accidentes por Condición Climática")
    axes[0].set_xlabel("Total de Accidentes")
    axes[0].xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[0].set_xlim(0, w_ord["total_accidentes"].max() * 1.2)
    for b, pct in zip(bw, w_ord["pct_total"]):
        w = b.get_width()
        axes[0].text(w * 1.02, b.get_y() + b.get_height()/2, f"{fmt_k(w)} ({pct}%)", va="center", fontsize=9, fontweight="bold")

    w_pct = df_weather.copy()
    for s in ["sev_1", "sev_2", "sev_3", "sev_4"]:
        w_pct[s] = w_pct[s] * 100.0 / w_pct["total_accidentes"]
    w_pct = w_pct.sort_values("pct_graves", ascending=True)
    left = np.zeros(len(w_pct))
    cols_s = ["sev_1", "sev_2", "sev_3", "sev_4"]
    labels_s = ["Sev 1", "Sev 2", "Sev 3", "Sev 4"]
    for col, lbl, c in zip(cols_s, labels_s, sev_colors):
        vals = w_pct[col].values
        axes[1].barh(w_pct["weather_group"], vals, left=left, color=c, label=lbl)
        left += vals
    axes[1].set_title("Composición Porcentual de Severidad según Clima (100%)")
    axes[1].set_xlabel("Porcentaje (%)")
    axes[1].set_xlim(0, 100)
    axes[1].legend(loc="lower center", bbox_to_anchor=(0.5, -0.2), ncol=4)
    for y_i, g_pct in enumerate(w_pct["pct_graves"]):
        axes[1].text(98.5, y_i, f"Graves S3+4: {g_pct:.1f}%", va="center", ha="right", color="white", fontsize=8.5, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "06_clima_y_severidad.png"))
    plt.close()

    # --------------------------------------------------------------------------
    # REQ 5: Tipos de Vía Más Peligrosos e Infraestructura Vial
    # --------------------------------------------------------------------------
    print("=== Req 5: Tipos de Vía y Calles Críticas ===")
    df_road_type = query_sql(conn, f"""
        SELECT
            road_type,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_total,
            ROUND(AVG(severity), 3) AS severidad_promedio,
            ROUND(SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_graves
        FROM accidents
        GROUP BY road_type
        ORDER BY total_accidentes DESC
    """, "09_tipos_via_peligrosos.csv")

    df_top_streets = query_sql(conn, """
        SELECT
            street,
            road_type,
            COUNT(*) AS total_accidentes,
            ROUND(AVG(severity), 3) AS severidad_promedio,
            SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) AS accidentes_graves
        FROM accidents
        WHERE street IS NOT NULL AND street <> 'Sin dato'
        GROUP BY street, road_type
        ORDER BY total_accidentes DESC
        LIMIT 12
    """, "09b_top12_vias_especificas.csv")

    df_poi = query_sql(conn, """
        SELECT
            SUM(traffic_signal) AS Semaforo,
            SUM(junction) AS Interseccion,
            SUM(crossing) AS Cruce_Peatonal,
            SUM(stop) AS Senal_Pare,
            SUM(station) AS Estacion_Transito,
            SUM(railway) AS Cruce_Ferroviario,
            SUM(roundabout) AS Glorieta
        FROM accidents
    """, "09c_infraestructura_vial.csv")

    summary["tipo_via"] = df_road_type.to_dict(orient="records")
    summary["top10_vias_reales"] = df_top_streets.head(10).to_dict(orient="records")
    summary["infraestructura"] = df_poi.iloc[0].to_dict()

    print("\n[Req 5a] Peligrosidad por Categoría de Vía:")
    print(df_road_type.to_string(index=False))
    print("\n[Req 5b] Top 10 Vías Específicas por Volumen:")
    print(df_top_streets.head(10).to_string(index=False))
    print("\n[Req 5c] Puntos de Infraestructura Cercanos:")
    print(df_poi.to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.8))
    rt_ord = df_road_type.sort_values("total_accidentes")
    brt = axes[0].barh(rt_ord["road_type"], rt_ord["total_accidentes"], color="#0f766e")
    axes[0].set_title("Accidentes por Categoría de Vía y % Graves (Sev 3–4)")
    axes[0].set_xlabel("Total de Accidentes")
    axes[0].xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[0].set_xlim(0, rt_ord["total_accidentes"].max() * 1.28)
    for b, pct, g in zip(brt, rt_ord["pct_total"], rt_ord["pct_graves"]):
        w = b.get_width()
        axes[0].text(w * 1.02, b.get_y() + b.get_height()/2, f"{fmt_k(w)} ({pct}% | Sev3-4: {g}%)", va="center", fontsize=8.5, fontweight="bold")

    st_ord = df_top_streets.head(10).sort_values("total_accidentes")
    bst = axes[1].barh(st_ord["street"], st_ord["total_accidentes"], color="#be123c")
    axes[1].set_title("Top 10 Vías Específicas Más Peligrosas (Por Volumen Real)")
    axes[1].set_xlabel("Total de Accidentes")
    axes[1].xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[1].set_xlim(0, st_ord["total_accidentes"].max() * 1.18)
    for b in bst:
        w = b.get_width()
        axes[1].text(w * 1.02, b.get_y() + b.get_height()/2, fmt_k(w), va="center", fontsize=9, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "07_tipos_via_y_top10_calles.png"))
    plt.close()

    # --------------------------------------------------------------------------
    # REQ 8: Tendencias Anuales y Mensuales (+ MoM)
    # --------------------------------------------------------------------------
    print("=== Req 8: Tendencias Anuales y Mensuales ===")
    df_year = query_sql(conn, """
        SELECT
            year,
            COUNT(*) AS total_accidentes,
            ROUND(AVG(severity), 3) AS severidad_promedio,
            SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) AS accidentes_graves
        FROM accidents
        WHERE year IS NOT NULL
        GROUP BY year
        ORDER BY year ASC
    """, "10_tendencia_anual.csv")

    df_month = query_sql(conn, f"""
        SELECT
            month,
            month_name,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_total,
            ROUND(AVG(severity), 3) AS severidad_promedio
        FROM accidents
        WHERE month IS NOT NULL
        GROUP BY month, month_name
        ORDER BY month ASC
    """, "10b_estacionalidad_mensual.csv")

    df_ym = query_sql(conn, """
        WITH mensual AS (
            SELECT year_month, COUNT(*) AS total_accidentes
            FROM accidents WHERE year_month IS NOT NULL
            GROUP BY year_month
        )
        SELECT
            year_month,
            total_accidentes,
            LAG(total_accidentes) OVER (ORDER BY year_month) AS mes_anterior,
            ROUND((total_accidentes - LAG(total_accidentes) OVER (ORDER BY year_month)) * 100.0
                  / NULLIF(LAG(total_accidentes) OVER (ORDER BY year_month), 0), 2) AS var_mom_pct
        FROM mensual
        ORDER BY year_month ASC
    """, "10c_serie_mensual_mom.csv")

    summary["anual"] = df_year.to_dict(orient="records")
    summary["mensual"] = df_month.to_dict(orient="records")

    print("\n[Req 8a] Tendencia Anual (2016 - Marzo 2023):")
    print(df_year.to_string(index=False))
    print("\n[Req 8b] Estacionalidad Mensual Acumulada:")
    print(df_month.to_string(index=False))
    print("\n[Req 8c] Últimos 6 Meses de Variación Mensual (MoM):")
    print(df_ym.tail(6).to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    axes[0].plot(df_year["year"], df_year["total_accidentes"], marker="o", linewidth=2.6, color="#1d4ed8")
    axes[0].fill_between(df_year["year"], df_year["total_accidentes"], color="#3b82f6", alpha=0.15)
    axes[0].set_title("Tendencia Anual de Accidentes (2016 – Marzo 2023)")
    axes[0].set_xlabel("Año")
    axes[0].set_ylabel("Total de Accidentes")
    axes[0].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[0].set_ylim(0, df_year["total_accidentes"].max() * 1.15)
    for x_y, y_v in zip(df_year["year"], df_year["total_accidentes"]):
        axes[0].text(x_y, y_v * 1.03, fmt_k(y_v), ha="center", fontsize=8.8, fontweight="bold")

    axes[1].bar(df_month["month_name"].str[:3], df_month["total_accidentes"], color="#0284c7")
    axes[1].set_title("Estacionalidad Mensual Acumulada (Enero – Diciembre)")
    axes[1].set_xlabel("Mes")
    axes[1].set_ylabel("Total de Accidentes")
    axes[1].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[1].set_ylim(0, df_month["total_accidentes"].max() * 1.15)
    for idx_m, y_m in enumerate(df_month["total_accidentes"]):
        axes[1].text(idx_m, y_m * 1.02, fmt_k(y_m), ha="center", fontsize=8, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "08_tendencias_anuales_y_mensuales.png"))
    plt.close()

    # --------------------------------------------------------------------------
    # REQ 9: Accidentes por Tipo de Vehículo Involucrado (NLP desde Description)
    # --------------------------------------------------------------------------
    print("=== Req 9: Tipos de Vehículo Involucrado ===")
    df_veh = query_sql(conn, f"""
        SELECT
            vehicle_type,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100.0 / {total_n}, 2) AS pct_sobre_total,
            ROUND(AVG(severity), 3) AS severidad_promedio,
            ROUND(SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_graves,
            ROUND(AVG(duration_clean_min), 2) AS duracion_media_min
        FROM accidents
        GROUP BY vehicle_type
        ORDER BY total_accidentes DESC
    """, "11_accidentes_por_vehiculo.csv")
    summary["vehiculos"] = df_veh.to_dict(orient="records")

    df_veh_known = df_veh[df_veh["vehicle_type"] != "No especificado"].copy()
    df_veh_known["pct_identificados"] = (df_veh_known["total_accidentes"] * 100.0 / df_veh_known["total_accidentes"].sum()).round(2)
    df_veh_known.to_csv(os.path.join(OUT_RESULTS, "11b_vehiculos_identificados.csv"), index=False, encoding="utf-8")

    print("\n[Req 9] Tipos de Vehículo Involucrado (NLP desde Description):")
    print(df_veh_known.to_string(index=False))
    no_esp = df_veh[df_veh["vehicle_type"] == "No especificado"]
    if not no_esp.empty:
        print(f"  * Nota: {int(no_esp['total_accidentes'].iloc[0]):,} registros ({no_esp['pct_sobre_total'].iloc[0]}%) no especifican vehículo en Description.")

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    vk_ord = df_veh_known.sort_values("total_accidentes")
    bv = axes[0].barh(vk_ord["vehicle_type"], vk_ord["total_accidentes"], color="#7c3aed")
    axes[0].set_title("Accidentes por Tipo de Vehículo (Menciones en Descripción)")
    axes[0].set_xlabel("Accidentes con mención explícita")
    axes[0].xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt_k(v)))
    axes[0].set_xlim(0, vk_ord["total_accidentes"].max() * 1.25)
    for b, pct in zip(bv, vk_ord["pct_identificados"]):
        w = b.get_width()
        axes[0].text(w * 1.02, b.get_y() + b.get_height()/2, f"{w:,} ({pct}%)", va="center", fontsize=8.8, fontweight="bold")

    vk_sev = df_veh_known.sort_values("pct_graves")
    bsv = axes[1].barh(vk_sev["vehicle_type"], vk_sev["pct_graves"], color="#dc2626")
    axes[1].set_title("Proporción de Eventos Graves (Sev 3–4) por Tipo de Vehículo")
    axes[1].set_xlabel("% de Accidentes con Severidad 3 o 4")
    axes[1].set_xlim(0, max(vk_sev["pct_graves"].max() * 1.25, 10))
    for b, dur in zip(bsv, vk_sev["duracion_media_min"]):
        w = b.get_width()
        axes[1].text(w + 0.5, b.get_y() + b.get_height()/2, f"{w:.1f}% (Dur: {dur:.0f}m)", va="center", fontsize=8.8, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "09_tipos_de_vehiculo.png"))
    plt.close()

    # --------------------------------------------------------------------------
    # REQ 10: Distribución Geoespacial de Puntos Críticos (Hotspots EE.UU.)
    # --------------------------------------------------------------------------
    print("=== Req 10: Distribución Geoespacial de Puntos Críticos ===")
    df_hotspots = query_sql(conn, """
        SELECT
            ROUND(start_lat, 1) AS lat_bin,
            ROUND(start_lng, 1) AS lng_bin,
            state,
            MAX(city) AS ciudad_referencia,
            COUNT(*) AS total_accidentes,
            SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) AS accidentes_graves,
            ROUND(AVG(severity), 3) AS severidad_promedio
        FROM accidents
        WHERE start_lat BETWEEN 24 AND 50 AND start_lng BETWEEN -125 AND -66
        GROUP BY lat_bin, lng_bin, state
        ORDER BY total_accidentes DESC
    """, "12_hotspots_geoespaciales.csv")
    summary["top15_hotspots"] = df_hotspots.head(15).to_dict(orient="records")
    print("\n[Req 10] Top 15 Puntos Críticos Geoespaciales (Celdas 0.1° x 0.1°):")
    print(df_hotspots.head(15).to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    # Mapa de densidad nacional (todas las celdas continentales)
    sc1 = axes[0].scatter(
        df_hotspots["lng_bin"], df_hotspots["lat_bin"],
        c=np.log10(df_hotspots["total_accidentes"] + 1),
        s=np.clip(df_hotspots["total_accidentes"] / 450.0, 2, 110),
        cmap="inferno", alpha=0.72, edgecolors="none"
    )
    axes[0].set_title("Distribución Geoespacial Nacional (Densidad de Siniestros)")
    axes[0].set_xlabel("Longitud")
    axes[0].set_ylabel("Latitud")
    axes[0].set_xlim(-126, -66)
    axes[0].set_ylim(24, 50)
    cbar = plt.colorbar(sc1, ax=axes[0])
    cbar.set_label("log10(Accidentes por celda 0.1°)")

    # Mapa enfocado en Top 200 hotspots graves (Sev 3-4) con etiquetas Top 8 ciudades
    top_hs = df_hotspots.head(300)
    sc2 = axes[1].scatter(
        top_hs["lng_bin"], top_hs["lat_bin"],
        c=top_hs["severidad_promedio"],
        s=np.clip(top_hs["total_accidentes"] / 250.0, 15, 280),
        cmap="coolwarm", alpha=0.8, edgecolors="black", linewidth=0.3
    )
    for _, row in df_cities.head(8).iterrows():
        # Buscar coordenada representativa del hotspot de esa ciudad
        match = df_hotspots[df_hotspots["ciudad_referencia"] == row["city"]].head(1)
        if not match.empty:
            axes[1].annotate(
                row["city"],
                (match["lng_bin"].iloc[0], match["lat_bin"].iloc[0]),
                xytext=(4, 4), textcoords="offset points",
                fontsize=8, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8)
            )
    axes[1].set_title("Top 300 Puntos Críticos Urbanos y Severidad Promedio")
    axes[1].set_xlabel("Longitud")
    axes[1].set_ylabel("Latitud")
    axes[1].set_xlim(-126, -66)
    axes[1].set_ylim(24, 50)
    cbar2 = plt.colorbar(sc2, ax=axes[1])
    cbar2.set_label("Severidad Promedio")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "10_distribucion_geoespacial_hotspots.png"))
    plt.close()

    # --------------------------------------------------------------------------
    # EXPLORACIÓN ADICIONAL: Matriz de Correlación Climática y de Impacto
    # --------------------------------------------------------------------------
    print("=== Exploración Adicional: Correlaciones Numéricas ===")
    num_cols = [
        "severity", "duration_clean_min", "distance_mi",
        "temperature_f", "humidity_pct", "visibility_mi",
        "wind_speed_mph", "precipitation_in", "hour"
    ]
    df_num = pd.read_parquet(PARQUET_PATH, columns=num_cols).dropna()
    corr_mat = df_num.corr().round(3)
    corr_mat.to_csv(os.path.join(OUT_RESULTS, "13_matriz_correlacion.csv"), encoding="utf-8")
    print("\n[Exploración Adicional] Matriz de Correlación de Pearson:")
    print(corr_mat.to_string())

    plt.figure(figsize=(10, 8))
    mask = np.triu(np.ones_like(corr_mat, dtype=bool))
    sns.heatmap(
        corr_mat, mask=mask, annot=True, fmt=".2f", cmap="RdBu_r",
        center=0, vmin=-0.5, vmax=0.5, linewidths=0.5
    )
    plt.title("Matriz de Correlación de Pearson (Severidad, Duración y Variables Climáticas)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "14_matriz_correlacion_exploratoria.png"))
    plt.close()

    conn.close()
    summary["elapsed_seconds"] = round(time.time() - t0, 2)
    with open(os.path.join(OUT_RESULTS, "summary_analisis.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n[COMPLETADO] Consultas SQL + Gráficas Python finalizadas en {summary['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
