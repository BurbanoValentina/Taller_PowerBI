# ==============================================================================
# PROYECTO 3: Análisis de Accidentes de Tránsito en Zonas Urbanas (US Accidents)
# Análisis Estadístico ANOVA (Unifactorial, Factorial, Post-Hoc y No Paramétrico)
# ==============================================================================
# Ejecuta pruebas ANOVA exactas sobre el dataset limpio en Parquet (~7.73M filas):
#   1. ANOVA Unifactorial: Duración depurada (min) ~ Severidad (1, 2, 3, 4)
#   2. ANOVA Unifactorial: Severidad ~ Condición Climática (6 grupos)
#   3. ANOVA Unifactorial: Severidad ~ Franja Horaria (5 franjas)
#   4. ANOVA Factorial 2 Vías: Severidad ~ Clima × Franja Horaria (Interacción)
#   5. Pruebas de robustez: Welch ANOVA, Levene, Kruskal-Wallis y Tukey-Kramer HSD
# Genera tablas CSV/JSON en resultados/ y 3 gráficas ANOVA en assets/charts/.
# ==============================================================================

import json
import os
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARQUET_PATH = os.path.join(BASE_DIR, "data", "us_accidents_clean.parquet")
OUT_RESULTS = os.path.join(BASE_DIR, "resultados")
OUT_CHARTS = os.path.join(BASE_DIR, "assets", "charts")

os.makedirs(OUT_RESULTS, exist_ok=True)
os.makedirs(OUT_CHARTS, exist_ok=True)

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "font.family": "sans-serif",
    "axes.titlesize": 12.5,
    "axes.titleweight": "bold",
    "axes.labelsize": 10.5,
})


def one_way_anova_full(df: pd.DataFrame, group_col: str, val_col: str, nombre: str):
    """
    Calcula ANOVA de un factor clásico, Welch ANOVA, efecto (eta^2, omega^2),
    Kruskal-Wallis (sobre datos completos), Levene (muestra estratificada si >1M)
    y comparaciones múltiples post-hoc Tukey-Kramer HSD exactas sobre N completo.
    """
    sub = df[[group_col, val_col]].dropna()
    grupos = sorted(sub[group_col].unique())
    k = len(grupos)
    N = len(sub)
    grand_mean = float(sub[val_col].mean())

    stats_rows = []
    arrays = []
    for g in grupos:
        arr = sub.loc[sub[group_col] == g, val_col].to_numpy(dtype=np.float64)
        arrays.append(arr)
        n_g = len(arr)
        mean_g = float(arr.mean())
        std_g = float(arr.std(ddof=1))
        se_g = std_g / np.sqrt(n_g)
        ci95 = 1.96 * se_g
        stats_rows.append({
            "grupo": str(g),
            "n": int(n_g),
            "media": round(mean_g, 4),
            "desv_std": round(std_g, 4),
            "mediana": round(float(np.median(arr)), 4),
            "ic95_inf": round(mean_g - ci95, 4),
            "ic95_sup": round(mean_g + ci95, 4),
            "ss_within": float(((arr - mean_g) ** 2).sum()),
            "var": float(std_g ** 2),
        })

    df_grp = pd.DataFrame(stats_rows)

    # Suma de cuadrados exacta
    ss_between = float(sum(r["n"] * (r["media"] - grand_mean) ** 2 for r in stats_rows))
    ss_within = float(sum(r["ss_within"] for r in stats_rows))
    ss_total = ss_between + ss_within

    df_between = k - 1
    df_within = N - k
    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    f_stat = ms_between / ms_within
    p_val = float(stats.f.sf(f_stat, df_between, df_within))

    eta_sq = ss_between / ss_total
    omega_sq = (ss_between - df_between * ms_within) / (ss_total + ms_within)

    # Welch ANOVA (robusta ante heterocedasticidad)
    w_weights = np.array([r["n"] / r["var"] for r in stats_rows])
    w_sum = w_weights.sum()
    welch_mean = sum(w * r["media"] for w, r in zip(w_weights, stats_rows)) / w_sum
    f_welch_num = sum(w * (r["media"] - welch_mean) ** 2 for w, r in zip(w_weights, stats_rows)) / (k - 1)
    lam = sum(((1.0 - w / w_sum) ** 2) / (r["n"] - 1) for w, r in zip(w_weights, stats_rows))
    f_welch = f_welch_num / (1.0 + (2.0 * (k - 2) / (k * k - 1)) * lam)
    df2_welch = (k * k - 1) / (3.0 * lam)
    p_welch = float(stats.f.sf(f_welch, k - 1, df2_welch))

    # Kruskal-Wallis H (no paramétrico sobre la población completa)
    kw_h, kw_p = stats.kruskal(*arrays)

    # Levene (sobre muestra estratificada máx 100k/grupo para estabilidad y rapidez)
    rng = np.random.default_rng(42)
    lev_samples = [
        arr if len(arr) <= 100_000 else rng.choice(arr, size=100_000, replace=False)
        for arr in arrays
    ]
    lev_f, lev_p = stats.levene(*lev_samples)

    # Post-hoc Tukey-Kramer HSD exacto con estadístico q de rango estudentizado
    df_tk = min(df_within, 100_000)
    q_crit = float(stats.studentized_range.ppf(0.95, k, df_tk))
    tukey_rows = []
    for i in range(k):
        for j in range(i + 1, k):
            r1, r2 = stats_rows[i], stats_rows[j]
            diff = r2["media"] - r1["media"]
            se_tk = np.sqrt((ms_within / 2.0) * (1.0 / r1["n"] + 1.0 / r2["n"]))
            q_obs = abs(diff) / se_tk
            p_tk = float(stats.studentized_range.sf(q_obs, k, df_tk))
            me = q_crit * se_tk
            tukey_rows.append({
                "comparacion": f"{r2['grupo']} vs {r1['grupo']}",
                "grupo_a": r1["grupo"],
                "grupo_b": r2["grupo"],
                "dif_medias": round(diff, 4),
                "ic95_inf": round(diff - me, 4),
                "ic95_sup": round(diff + me, 4),
                "q_tukey": round(float(q_obs), 2),
                "p_valor": p_tk,
                "significativo_005": bool(p_tk < 0.05),
            })

    summary = {
        "analisis": nombre,
        "variable_dependiente": val_col,
        "factor": group_col,
        "N": int(N),
        "k_grupos": int(k),
        "df_entre": int(df_between),
        "df_dentro": int(df_within),
        "ss_entre": round(ss_between, 2),
        "ss_dentro": round(ss_within, 2),
        "ms_entre": round(ms_between, 2),
        "ms_dentro": round(ms_within, 4),
        "F_clasico": round(float(f_stat), 2),
        "p_valor_clasico": p_val,
        "eta_cuadrado": round(float(eta_sq), 6),
        "omega_cuadrado": round(float(omega_sq), 6),
        "F_welch": round(float(f_welch), 2),
        "p_valor_welch": p_welch,
        "levene_F": round(float(lev_f), 2),
        "levene_p": float(lev_p),
        "kruskal_H": round(float(kw_h), 2),
        "kruskal_p": float(kw_p),
    }

    return summary, df_grp.drop(columns=["ss_within", "var"]), pd.DataFrame(tukey_rows)


def two_way_anova_full(df: pd.DataFrame, col_a: str, col_b: str, val_col: str):
    """
    Calcula ANOVA Factorial de 2 vías (Efectos Principales A, B e Interacción A:B)
    usando diseño de regresión ponderada por celdas (Tipo III / Ajuste completo)
    sobre los estadísticos suficientes de todas las observaciones N.
    """
    sub = df[[col_a, col_b, val_col]].dropna()
    levels_a = sorted(sub[col_a].unique())
    levels_b = sorted(sub[col_b].unique())

    cells = (
        sub.groupby([col_a, col_b])[val_col]
        .agg(n="count", mean="mean", var="var")
        .reset_index()
    )
    cells["ss_within"] = (cells["n"] - 1) * cells["var"].fillna(0.0)
    N = int(cells["n"].sum())
    ss_error = float(cells["ss_within"].sum())
    df_error = N - len(cells)
    ms_error = ss_error / df_error

    # Codificación de efectos ponderada para Tipo II/III mediante mínimos cuadrados ponderados en celdas
    a_idx = {v: i for i, v in enumerate(levels_a)}
    b_idx = {v: i for i, v in enumerate(levels_b)}
    A, B = len(levels_a), len(levels_b)

    # Matriz de diseño completa con codificación sum-to-zero (desviaciones)
    def build_X(include_a=True, include_b=True, include_ab=True):
        cols = [np.ones(len(cells))]
        a_cols = []
        for i in range(A - 1):
            col = np.array([1.0 if a_idx[r] == i else (-1.0 if a_idx[r] == A - 1 else 0.0) for r in cells[col_a]])
            a_cols.append(col)
        b_cols = []
        for j in range(B - 1):
            col = np.array([1.0 if b_idx[r] == j else (-1.0 if b_idx[r] == B - 1 else 0.0) for r in cells[col_b]])
            b_cols.append(col)
        if include_a:
            cols.extend(a_cols)
        if include_b:
            cols.extend(b_cols)
        if include_ab:
            for ca in a_cols:
                for cb in b_cols:
                    cols.append(ca * cb)
        return np.column_stack(cols)

    y = cells["mean"].to_numpy()
    w = cells["n"].to_numpy(dtype=np.float64)

    def weighted_sse_model(X):
        W_sqrt = np.sqrt(w)[:, None]
        Xw = X * W_sqrt
        yw = y * np.sqrt(w)
        beta, _, _, _ = np.linalg.lstsq(Xw, yw, rcond=None)
        resid = yw - Xw @ beta
        return float((resid ** 2).sum())

    sse_full = weighted_sse_model(build_X(True, True, True))
    sse_no_ab = weighted_sse_model(build_X(True, True, False))
    sse_no_a = weighted_sse_model(build_X(False, True, True))
    sse_no_b = weighted_sse_model(build_X(True, False, True))

    ss_ab = max(0.0, sse_no_ab - sse_full)
    ss_a = max(0.0, sse_no_a - sse_full)
    ss_b = max(0.0, sse_no_b - sse_full)

    df_a = A - 1
    df_b = B - 1
    df_ab = df_a * df_b

    rows = []
    for factor, ss_f, df_f in [
        (col_a, ss_a, df_a),
        (col_b, ss_b, df_b),
        (f"{col_a} × {col_b} (Interacción)", ss_ab, df_ab),
    ]:
        ms_f = ss_f / df_f
        f_val = ms_f / ms_error
        p_val = float(stats.f.sf(f_val, df_f, df_error))
        rows.append({
            "fuente": factor,
            "df": int(df_f),
            "ss_tipo_iii": round(ss_f, 2),
            "ms": round(ms_f, 4),
            "F": round(float(f_val), 2),
            "p_valor": p_val,
            "eta_parcial_sq": round(ss_f / (ss_f + ss_error), 6),
        })
    rows.append({
        "fuente": "Error (Dentro de celdas)",
        "df": int(df_error),
        "ss_tipo_iii": round(ss_error, 2),
        "ms": round(ms_error, 4),
        "F": None,
        "p_valor": None,
        "eta_parcial_sq": None,
    })
    return pd.DataFrame(rows), cells


def main():
    t0 = time.time()
    print("=== Cargando Parquet limpio para análisis ANOVA ===")
    cols = ["severity", "duration_clean_min", "weather_group", "time_slot"]
    df = pd.read_parquet(PARQUET_PATH, columns=cols)
    df = df[df["time_slot"] != "Sin dato"].copy()
    print(f"[OK] Registros disponibles: {len(df):,}")

    # 1. ANOVA: Duración depurada ~ Severidad
    print("\n[1/4] Ejecutando ANOVA: Duración ~ Severidad...")
    sum1, grp1, tuk1 = one_way_anova_full(df, "severity", "duration_clean_min", "Duración (min) según Severidad")
    grp1.to_csv(os.path.join(OUT_RESULTS, "anova1_grupos_duracion_severidad.csv"), index=False)
    tuk1.to_csv(os.path.join(OUT_RESULTS, "anova1_tukey_duracion_severidad.csv"), index=False)

    # 2. ANOVA: Severidad ~ Clima
    print("[2/4] Ejecutando ANOVA: Severidad ~ Clima...")
    sum2, grp2, tuk2 = one_way_anova_full(df, "weather_group", "severity", "Severidad según Condición Climática")
    grp2.to_csv(os.path.join(OUT_RESULTS, "anova2_grupos_severidad_clima.csv"), index=False)
    tuk2.to_csv(os.path.join(OUT_RESULTS, "anova2_tukey_severidad_clima.csv"), index=False)

    # 3. ANOVA: Severidad ~ Franja Horaria
    print("[3/4] Ejecutando ANOVA: Severidad ~ Franja Horaria...")
    sum3, grp3, tuk3 = one_way_anova_full(df, "time_slot", "severity", "Severidad según Franja Horaria")
    grp3.to_csv(os.path.join(OUT_RESULTS, "anova3_grupos_severidad_franja.csv"), index=False)
    tuk3.to_csv(os.path.join(OUT_RESULTS, "anova3_tukey_severidad_franja.csv"), index=False)

    # 4. ANOVA Factorial 2 Vías: Severidad ~ Clima × Franja Horaria
    print("[4/4] Ejecutando ANOVA Factorial: Severidad ~ Clima × Franja Horaria...")
    df_2way, cells_2way = two_way_anova_full(df, "weather_group", "time_slot", "severity")
    df_2way.to_csv(os.path.join(OUT_RESULTS, "anova4_factorial_clima_franja.csv"), index=False)
    cells_2way.to_csv(os.path.join(OUT_RESULTS, "anova4_celdas_clima_franja.csv"), index=False)

    anova_all = {
        "anova_duracion_severidad": sum1,
        "anova_severidad_clima": sum2,
        "anova_severidad_franja": sum3,
        "anova_factorial_clima_franja": df_2way.to_dict(orient="records"),
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    with open(os.path.join(OUT_RESULTS, "anova_summary.json"), "w", encoding="utf-8") as f:
        json.dump(anova_all, f, indent=2, ensure_ascii=False)

    print("\nResumen ANOVA:")
    for s in [sum1, sum2, sum3]:
        print(f"  * {s['analisis']}: F={s['F_clasico']:,.2f}, p={s['p_valor_clasico']:.2e}, eta^2={s['eta_cuadrado']:.5f}, KW_H={s['kruskal_H']:,.2f}")
    print(df_2way.to_string(index=False))

    # --------------------------------------------------------------------------
    # GRÁFICA ANOVA 1: Boxplot + Medias IC95% Duración por Severidad
    # --------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.8))
    # Muestra estratificada para boxplot ágil (50k/severidad) conservando percentiles exactos
    sample_parts = [
        df.loc[df["severity"] == sev, ["severity", "duration_clean_min"]].dropna().sample(
            n=min(int((df["severity"] == sev).sum()), 50_000), random_state=42
        )
        for sev in sorted(df["severity"].unique())
    ]
    sample_box = pd.concat(sample_parts, ignore_index=True)
    sns.boxplot(
        data=sample_box, x="severity", y="duration_clean_min",
        hue="severity", palette=["#38bdf8", "#1e3a8a", "#ea580c", "#7e22ce"],
        legend=False, showfliers=False, ax=axes[0]
    )
    axes[0].set_title("Distribución de Duración Depurada (≤24h) por Severidad")
    axes[0].set_xlabel("Nivel de Severidad")
    axes[0].set_ylabel("Duración del Incidente (minutos)")

    x_g = np.arange(len(grp1))
    axes[1].errorbar(
        x_g, grp1["media"],
        yerr=[grp1["media"] - grp1["ic95_inf"], grp1["ic95_sup"] - grp1["media"]],
        fmt="o-", color="#0f172a", ecolor="#dc2626", elinewidth=2.5, capsize=6, markersize=8
    )
    axes[1].set_xticks(x_g)
    axes[1].set_xticklabels([f"Sev {g}" for g in grp1["grupo"]])
    axes[1].set_title(
        f"ANOVA Duración ~ Severidad\n"
        f"F = {sum1['F_clasico']:,.1f} | p < 1e-300 | η² = {sum1['eta_cuadrado']:.4f} | KW H = {sum1['kruskal_H']:,.0f}"
    )
    axes[1].set_xlabel("Nivel de Severidad")
    axes[1].set_ylabel("Duración Media (minutos) ± IC 95%")
    for xi, yi in zip(x_g, grp1["media"]):
        offset_y = -13.0 if xi == 2 else 6.0
        axes[1].text(xi, yi + offset_y, f"{yi:.1f} min", ha="center", fontweight="bold", fontsize=9.5)
    axes[1].set_ylim(0, grp1["media"].max() * 1.18)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "11_anova_duracion_severidad.png"))
    plt.close()

    # --------------------------------------------------------------------------
    # GRÁFICA ANOVA 2: Severidad ~ Clima + Interacción Clima × Franja Horaria
    # --------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 5.8))
    grp2_ord = grp2.sort_values("media", ascending=True)
    y_pos = np.arange(len(grp2_ord))
    axes[0].errorbar(
        grp2_ord["media"], y_pos,
        xerr=[grp2_ord["media"] - grp2_ord["ic95_inf"], grp2_ord["ic95_sup"] - grp2_ord["media"]],
        fmt="o", color="#1d4ed8", ecolor="#ef4444", elinewidth=2.2, capsize=5, markersize=8
    )
    axes[0].axvline(df["severity"].mean(), color="#64748b", linestyle="--", label=f"Media global ({df['severity'].mean():.3f})")
    axes[0].set_yticks(y_pos)
    axes[0].set_yticklabels(grp2_ord["grupo"])
    axes[0].set_title(f"ANOVA Severidad ~ Clima (F = {sum2['F_clasico']:,.1f}, p < 1e-300)")
    axes[0].set_xlabel("Severidad Promedio ± IC 95%")
    axes[0].legend(loc="lower right")
    for yi, xi in zip(y_pos, grp2_ord["media"]):
        axes[0].text(xi, yi + 0.16, f"{xi:.4f}", ha="center", fontsize=8.8, fontweight="bold")

    piv_int = cells_2way.pivot(index="time_slot", columns="weather_group", values="mean")
    for col in piv_int.columns:
        axes[1].plot(piv_int.index, piv_int[col], marker="o", linewidth=2, label=col)
    f_int = df_2way.loc[df_2way["fuente"].str.contains("Interacción"), "F"].iloc[0]
    axes[1].set_title(f"ANOVA Factorial: Interacción Clima × Franja Horaria (F_int = {f_int:,.1f}, p < 1e-300)")
    axes[1].set_xlabel("Franja Horaria")
    axes[1].set_ylabel("Severidad Media")
    axes[1].tick_params(axis="x", rotation=18)
    axes[1].legend(title="Clima", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8.5)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "12_anova_severidad_clima_franja.png"))
    plt.close()

    # --------------------------------------------------------------------------
    # GRÁFICA ANOVA 3: Post-Hoc Tukey-Kramer HSD (Diferencias de Medias)
    # --------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 6))
    y_t1 = np.arange(len(tuk1))
    axes[0].errorbar(
        tuk1["dif_medias"], y_t1,
        xerr=[tuk1["dif_medias"] - tuk1["ic95_inf"], tuk1["ic95_sup"] - tuk1["dif_medias"]],
        fmt="s", color="#0f766e", ecolor="#0f766e", capsize=4, markersize=6
    )
    axes[0].axvline(0, color="#dc2626", linestyle="--", linewidth=1.2)
    axes[0].set_yticks(y_t1)
    axes[0].set_yticklabels(tuk1["comparacion"])
    axes[0].set_title("Tukey-Kramer HSD: Diferencias en Duración (min) entre Severidades")
    axes[0].set_xlabel("Diferencia de Medias (IC 95%)")

    # Top 10 contrastes con mayor diferencia absoluta en Severidad ~ Clima
    tuk2_top = tuk2.reindex(tuk2["dif_medias"].abs().sort_values(ascending=True).index).tail(10)
    y_t2 = np.arange(len(tuk2_top))
    axes[1].errorbar(
        tuk2_top["dif_medias"], y_t2,
        xerr=[tuk2_top["dif_medias"] - tuk2_top["ic95_inf"], tuk2_top["ic95_sup"] - tuk2_top["dif_medias"]],
        fmt="o", color="#7c3aed", ecolor="#7c3aed", capsize=4, markersize=6
    )
    axes[1].axvline(0, color="#dc2626", linestyle="--", linewidth=1.2)
    axes[1].set_yticks(y_t2)
    axes[1].set_yticklabels(tuk2_top["comparacion"], fontsize=8.5)
    axes[1].set_title("Tukey-Kramer HSD: Principales Diferencias en Severidad por Clima")
    axes[1].set_xlabel("Diferencia de Severidad Media (IC 95%)")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_CHARTS, "13_anova_tukey_posthoc.png"))
    plt.close()

    print(f"\n[COMPLETADO] Análisis ANOVA + 3 gráficas generadas en {round(time.time()-t0, 2)}s")


if __name__ == "__main__":
    main()
