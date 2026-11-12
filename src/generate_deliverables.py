# ==============================================================================
# PROYECTO 3: Análisis de Accidentes de Tránsito en Zonas Urbanas (US Accidents)
# Generador Automático de Entregables:
#   - docs/informe_tecnico.md
#   - docs/informe_tecnico.html
#   - docs/informe_tecnico.pdf  (vía ReportLab Platypus)
#   - docs/informe_tecnico.docx (vía python-docx)
#   - docs/presentacion_oral.pptx (vía python-pptx)
#   - docs/guion_presentacion_oral.md
#   - README.md (raíz del repositorio con todas las gráficas Python)
# ==============================================================================

import html
import io
import json
import os
import re
import matplotlib
import pandas as pd
from PIL import Image
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pptx import Presentation
from pptx.util import Inches as PptxInches, Pt as PptxPt
from pptx.dml.color import RGBColor as PptxRGB
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES_DIR = os.path.join(BASE_DIR, "resultados")
CHARTS_DIR = os.path.join(BASE_DIR, "assets", "charts")
PBI_DIR = os.path.join(BASE_DIR, "assets", "powerbi")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
os.makedirs(DOCS_DIR, exist_ok=True)


def load_json(name):
    with open(os.path.join(RES_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_int(n):
    return f"{int(round(float(n))):,}"


def md_table(headers, rows):
    line1 = "| " + " | ".join(headers) + " |"
    line2 = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join([line1, line2] + body)


def image_to_png_stream(path):
    """Convierte cualquier imagen (incluidos JPEG con cabeceras especiales) a stream PNG RGB."""
    buf = io.BytesIO()
    with Image.open(path) as im:
        w, h = im.size
        im.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf, w, h


def build_technical_markdown(audit, summary, anova, dfs):
    aud = summary["auditoria"]
    top_st = dfs["states"].head(10)
    top_rate = dfs["states"].sort_values("tasa_x_100k_hab", ascending=False).head(10)
    top_ct = dfs["cities"].head(10)
    df_sev = dfs["sev"]
    df_w = dfs["weather"]
    df_road = dfs["road"]
    df_streets = dfs["streets"].head(10)
    df_day = dfs["day"]
    df_year = dfs["year"]
    df_month = dfs["month"]
    df_veh_k = dfs["veh_k"]
    df_poi = dfs["poi"].iloc[0]

    s1 = anova["anova_duracion_severidad"]
    s2 = anova["anova_severidad_clima"]
    s3 = anova["anova_severidad_franja"]
    df_2w = dfs["anova_2w"]
    df_g1 = dfs["anova_g1"]
    df_g2 = dfs["anova_g2"]

    peak_hour_row = max(summary["por_hora"], key=lambda x: x["total_accidentes"])
    peak_day_row = max(summary["por_dia"], key=lambda x: x["total_accidentes"])
    peak_year_row = max(summary["anual"], key=lambda x: x["total_accidentes"])
    peak_month_row = max(summary["mensual"], key=lambda x: x["total_accidentes"])

    weekend_total = sum(int(r["total_accidentes"]) for _, r in df_day.iterrows() if r["tipo_dia"] == "Fin de Semana")
    weekend_pct = round(weekend_total * 100.0 / audit["total_clean_rows"], 2)
    veh_ident_total = int(df_veh_k["total_accidentes"].sum())
    veh_ident_pct = round(veh_ident_total * 100.0 / audit["total_clean_rows"], 2)

    md = f"""# Informe Técnico — Proyecto 3: Análisis de Accidentes de Tránsito en Zonas Urbanas (EE.UU., 2016–2023)

**Fuente de Datos:** Kaggle *US Accidents (2016–2023)* — `sobhanmoosavi/us-accidents` (`US_Accidents_March23.csv`) + Enriquecimiento Demográfico del Censo de EE.UU. (`us_state_demographics.csv`).  
**Herramientas:** Python 3.13 (Pandas, PyArrow, NumPy, SciPy, Matplotlib, Seaborn), PySpark / Spark SQL, SQLite 3, Power Query (Lenguaje M) y Microsoft Power BI Desktop (DAX).

---

## 1. Objetivos del Proyecto

### 1.1 Objetivo General
Integrar datos abiertos de accidentes de tránsito en zonas urbanas y corredores viales de Estados Unidos con variables climáticas, de infraestructura vial y demográficas, con el fin de identificar patrones temporales, factores críticos de severidad y puntos geoespaciales de alta concentración mediante un flujo reproducible ETL + SQL + Power BI + ANOVA.

### 1.2 Objetivos Específicos
1. **Diseñar e implementar un pipeline ETL híbrido (Python/PyArrow, PySpark, SQLite y Power Query M)** capaz de procesar **{fmt_int(audit['total_raw_rows'])} registros** y ~3.06 GB de texto, normalizando *timestamps* con nanosegundos, filtrando valores atípicos y enriqueciendo cada incidente con variables climáticas, viales, vehiculares y poblacionales.
2. **Responder los 10 requerimientos analíticos de negocio** mediante consultas SQL reproducibles y visualizaciones estadísticas en Python, cubriendo distribución geográfica, horarios pico, días críticos, severidad, clima, vías peligrosas, duración, estacionalidad y tipos de vehículo.
3. **Documentar y auditar el tablero interactivo desarrollado en Power BI**, detallando el lenguaje M, las medidas DAX empleadas y el contraste técnico entre las métricas del dashboard y la depuración en Python/SQL.
4. **Evaluar estadísticamente mediante pruebas ANOVA unifactoriales, factoriales y post-hoc (Tukey-Kramer HSD / Kruskal-Wallis)** si la duración del incidente y la severidad difieren significativamente según el nivel de gravedad, la condición climática y la franja horaria.

---

## 2. Descripción del Proceso ETL e Implementación (Python, SQL, PySpark, Power Query)

El pipeline ETL se diseñó bajo una arquitectura de procesamiento por bloques (*streaming* de 500,000 filas por lote) en `src/etl_us_accidents.py`, complementada con una versión distribuida en `src/etl_pyspark.py`, las consultas analíticas en `sql/queries_analisis.sql` y el script de Power Query M en `powerbi/power_query_etl.pq`.

### 2.1 Extracción
- **Fuente principal:** `US_Accidents_March23.csv` (46 columnas originales, **{fmt_int(audit['total_raw_rows'])} registros**, período `{aud['fecha_inicio']}` a `{aud['fecha_fin']}`).
- **Fuente demográfica complementaria:** `data/us_state_demographics.csv` con estimaciones poblacionales oficiales 2023 del Censo de EE.UU., superficie en millas cuadradas, densidad poblacional y región censal (*South, West, Midwest, Northeast*) para los 50 estados + D.C.

### 2.2 Limpieza y Calidad de Datos (Auditoría Real)
Durante la fase de transformación se detectaron y resolvieron problemas críticos de calidad de datos:

| Hallazgo / Métrica de Auditoría | Cantidad Observada | Decisión ETL Aplicada |
|---|---|---|
| Registros brutos extraídos | **{fmt_int(audit['total_raw_rows'])}** | Lectura íntegra por bloques de 500k registros sin muestreo destructivo. |
| Registros únicos tras deduplicación por `ID` | **{fmt_int(audit['total_clean_rows'])}** | Se eliminaron `{fmt_int(audit['duplicates_removed'])}` duplicados; 100% de integridad por clave. |
| *Timestamps* con sufijo de nanosegundos (`.000000000`) | **{fmt_int(audit['dotted_timestamps_fixed'])}** | Recorte y parseo estricto `yyyy-MM-dd HH:mm:ss` (`Start_Time` y `End_Time`). |
| Valores nulos en `Weather_Condition` | **{fmt_int(audit['nulls_weather'])}** | Imputación semántica a la categoría `"Otro"` para no perder registros en análisis generales. |
| Valores nulos en `Street` / `City` | `{fmt_int(audit['nulls_street'])}` / `{fmt_int(audit['nulls_city'])}` | Etiquetado explícito como `"Sin dato"` y exclusión solo en rankings de calles/ciudades. |
| *Outliers* extremos de duración (`> 1,440 min` / 24h) | **{fmt_int(audit['outliers_gt_24h'])}** | Preservación en `duration_raw_min` (para auditoría Power BI) y depuración en `duration_clean_min` (`≤ 24h`). |

### 2.3 Ingeniería de Variables y Enriquecimiento
- **Agrupación climática (`weather_group`):** Mapeo de más de 140 cadenas originales en inglés a 6 categorías analíticas estandarizadas en español: `Despejado`, `Nublado`, `Lluvia`, `Niebla`, `Nieve/Hielo` y `Otro`.
- **Clasificación vial (`road_type`):** Expresiones regulares C++ (PyArrow RE2) sobre `Street` para distinguir `Autopista / Interstate` (`I-95`, `Fwy`, `Expy`), `Carretera / Highway` (`US-`, `SR-`, `Hwy`), `Avenida / Boulevard` y `Calle / Vía Urbana`.
- **Extracción de tipo de vehículo (`vehicle_type`):** El dataset original no posee columna nativa de vehículo; mediante NLP/RE2 sobre `Description` se extrajeron menciones explícitas de `Automóvil / Multivehículo`, `Camión / Tráiler`, `Peatón involucrado`, `Autobús`, `Motocicleta`, `SUV / Van / Pickup` y `Bicicleta`, **filtrando falsos positivos toponímicos de EE.UU.** como `"I-80 Bus"` (Business Route), `"Van Ness Ave"`, `"Van Buren St"`, `"Auto Mall Pkwy"` y `"Truck Route"`.
- **Carga Analítica:** Exportación columnar comprimida a `data/us_accidents_clean.parquet` y carga relacional indexada en SQLite (`data/us_accidents.db` con tablas `accidents` y `dim_demographics`).

### 2.4 Extractos de Implementación ETL (Python, SQL y Power Query M)

```python
# src/etl_us_accidents.py — Normalización temporal y outliers por bloques de 500k filas
audit["dotted_timestamps_fixed"] += int(st_str.str.contains(".", regex=False).sum())
start_dt = pd.to_datetime(st_str.str.slice(0, 19), format="%Y-%m-%d %H:%M:%S", errors="coerce")
dur_raw = (end_dt - start_dt).dt.total_seconds() / 60.0
dur_clean = dur_raw.mask(dur_raw > 1440.0, np.nan)
```

```sql
-- sql/queries_analisis.sql — Tasa demográfica x100k habitantes y variación MoM con función ventana LAG()
SELECT a.state, d.state_name, COUNT(*) AS total_accidentes,
       ROUND(COUNT(*) * 100000.0 / d.population_2023, 2) AS tasa_x_100k_hab
FROM accidents a LEFT JOIN dim_demographics d ON a.state = d.state
GROUP BY a.state, d.state_name, d.population_2023 ORDER BY total_accidentes DESC;
```

```powerquery
// powerbi/power_query_etl.pq — Agrupación climática y cruce demográfico en Lenguaje M
JoinDemografia = Table.NestedJoin(ConVehiculo, {{"State"}}, DemografiaTyped, {{"State"}}, "DimDemografia", JoinKind.LeftOuter),
ExpandDemografia = Table.ExpandTableColumn(JoinDemografia, "DimDemografia", {{"State_Name", "Region", "Population_2023", "Density_Per_SqMi"}})
```

---

## 3. Exploración de Datos y Respuesta a los 10 Requerimientos Analíticos

### 3.1 Requerimiento 1: Frecuencia de Accidentes por Estado, Ciudad y Tasa Demográfica
El dataset cubre **{aud['estados_cubiertos']} entidades** (48 estados contiguos + D.C.) y **{fmt_int(aud['ciudades_cubiertas'])} ciudades**.

- **Por volumen absoluto**, lidera **California (`{fmt_int(top_st.iloc[0]['total_accidentes'])}`, `{top_st.iloc[0]['pct_nacional']}%`)**, seguida de Florida (`880,192`), Texas (`582,837`), Carolina del Sur (`382,557`) y Nueva York (`347,960`).
- **Por ciudad urbana**, encabeza **Miami, FL (`{fmt_int(top_ct.iloc[0]['total_accidentes'])}`)**, seguida por Houston, TX (`169,428`) y Los Angeles, CA (`156,491`).
- **Integración demográfica (Tasa por 100,000 habitantes):** Al normalizar por población del Censo 2023, **Carolina del Sur (`{top_rate.iloc[0]['tasa_x_100k_hab']:,.0f}` por 100k hab.)** y **Oregón (`4,244` por 100k hab.)** superan ampliamente en incidencia per cápita a Texas (`1,911`) y Nueva York (`1,778`), demostrando la importancia del cruce demográfico.

**Top 10 Estados por Frecuencia y Tasa Demográfica:**

{md_table(
    ["Estado", "Nombre", "Región", "Accidentes", "% Nacional", "Población 2023", "Tasa x 100k Hab.", "Sev. Prom."],
    [[r["state"], r["state_name"], r["region"], fmt_int(r["total_accidentes"]), f"{r['pct_nacional']}%", fmt_int(r["population_2023"]), f"{r['tasa_x_100k_hab']:,.1f}", r["severidad_promedio"]] for _, r in top_st.iterrows()]
)}

![Top 10 Estados y Ciudades](../assets/charts/01_top10_estados_y_ciudades.png)

![Tasa Demográfica y Regiones](../assets/charts/02_demografia_tasa_y_regiones.png)

---

### 3.2 Requerimientos 2 y 6: Hora del Día y Días de la Semana Críticos
- **Hora pico principal:** Las **{int(peak_hour_row['hour']):02d}:00 horas** (`{fmt_int(peak_hour_row['total_accidentes'])}` eventos, `{peak_hour_row['pct_total']}%`), dentro de un patrón **bimodal laboral** con pico matutino (07:00–08:59h) y pico vespertino sostenido (15:00–17:59h).
- **Día de la semana crítico:** El **{peak_day_row['day_name']}** concentra el mayor volumen (`{fmt_int(peak_day_row['total_accidentes'])}` eventos, `{peak_day_row['pct_total']}%`), mientras que sábado y domingo reducen drásticamente la frecuencia conjunta a `{fmt_int(weekend_total)}` eventos (`{weekend_pct}%`), aunque presentan **mayor severidad promedio** (`2.259` en domingo y `2.241` en sábado frente a `2.203–2.209` entre semana) debido a velocidades más altas y menor congestión.

{md_table(
    ["Día", "Tipo de Día", "Total Accidentes", "% Total", "Severidad Promedio"],
    [[r["day_name"], r["tipo_dia"], fmt_int(r["total_accidentes"]), f"{r['pct_total']}%", r["severidad_promedio"]] for _, r in df_day.iterrows()]
)}

![Patrón Horario y Semanal](../assets/charts/03_patron_horario_y_semanal.png)

![Mapa de Calor Día x Hora](../assets/charts/04_heatmap_dia_hora.png)

---

### 3.3 Requerimientos 3 y 7: Análisis por Severidad y Duración del Incidente
La severidad (escala 1 = impacto mínimo en tráfico a 4 = impacto severo/cierre prolongado) muestra una fuerte concentración en el **Nivel 2 ({df_sev.loc[df_sev['severity']==2, 'pct_total'].iloc[0]}%)**, seguido del **Nivel 3 ({df_sev.loc[df_sev['severity']==3, 'pct_total'].iloc[0]}%)**.

En cuanto a la **duración**, el contraste entre la media bruta (**{summary['media_global_bruta_min']:.1f} min**, coincidente con los `444` min del tablero Power BI) y la mediana global (**{summary['mediana_global_bruta_min']:.1f} min**, coincidente con `75` min en Power BI) evidencia una **severa asimetría positiva** generada por `{fmt_int(audit['outliers_gt_24h'])}` cierres viales extremos superiores a 24 horas. Al depurar a incidentes `≤ 24h`, la duración media operativa desciende a **{summary['media_global_depurada_min']:.1f} min** (`45.7 min` en Sev. 1, `114.7 min` en Sev. 2, `67.8 min` en Sev. 3 por despeje rápido prioritario en autopistas y `185.9 min` en Sev. 4 por cierres prolongados).

{md_table(
    ["Severidad", "Total Accidentes", "% Total", "Dist. Media (mi)", "Media Bruta (min)", "Media Depurada ≤24h (min)", "Mediana Depurada (min)"],
    [[int(r["severity"]), fmt_int(r["total_accidentes"]), f"{r['pct_total']}%", r["distancia_media_mi"], r["duracion_media_bruta_min"], r["duracion_media_depurada_min"], r["mediana_depurada_min"]] for _, r in df_sev.iterrows()]
)}

![Severidad y Duración](../assets/charts/05_severidad_y_duracion.png)

---

### 3.4 Requerimiento 4: Relación con Condiciones Climáticas
Aunque en volumen absoluto predominan condiciones **Despejadas (44.06%)** y **Nubladas (40.94%)** (porque representan la mayor exposición diaria de tráfico), el porcentaje de incidentes graves (`Severidad 3 y 4`) aumenta en condiciones adversas como **Lluvia (`22.76%`)** y **Nieve/Hielo (`19.95%`)** frente a **Despejado (`16.91%`)**, cayendo además la visibilidad promedio de `9.85 mi` a `6.15 mi` (Lluvia), `3.08 mi` (Niebla) y `2.85 mi` (Nieve/Hielo).

{md_table(
    ["Grupo Climático", "Total Accidentes", "% Total", "% Graves (Sev 3–4)", "Visibilidad Media (mi)", "Temp. Media (°F)"],
    [[r["weather_group"], fmt_int(r["total_accidentes"]), f"{r['pct_total']}%", f"{r['pct_graves']}%", r["visibilidad_media_mi"], r["temperatura_media_f"]] for _, r in df_w.iterrows()]
)}

![Clima y Severidad](../assets/charts/06_clima_y_severidad.png)

---

### 3.5 Requerimiento 5: Tipos de Vía Más Peligrosos e Infraestructura Vial
- **Por categoría de vía:** Las **Calles / Vías Urbanas** agrupan alta capilaridad (`31.07%`), pero las **Autopistas / Interstates** (`34.29%`) concentran la **mayor proporción de accidentes graves (`32.44%` en Severidad 3–4)** frente al `10.17%` en calles urbanas, debido a velocidades de circulación y colisiones múltiples.
- **Top 10 vías específicas reales:** A diferencia del orden alfabético descendente visto en una captura de Power BI (`Zuni Rd SE`), el ranking real por volumen está encabezado por grandes arterias interestatales (`{df_streets.iloc[0]['street']}` con `{fmt_int(df_streets.iloc[0]['total_accidentes'])}`, `{df_streets.iloc[1]['street']}` con `{fmt_int(df_streets.iloc[1]['total_accidentes'])}` y `{df_streets.iloc[2]['street']}` con `{fmt_int(df_streets.iloc[2]['total_accidentes'])}`).
- **Infraestructura vial:** Los accidentes se concentran alrededor de **Semáforos (`Traffic_Signal`: {fmt_int(df_poi['Semaforo'])})**, **Cruces Peatonales (`Crossing`: {fmt_int(df_poi['Cruce_Peatonal'])})** e **Intersecciones (`Junction`: {fmt_int(df_poi['Interseccion'])})**.

{md_table(
    ["Tipo de Vía", "Total Accidentes", "% Total", "Severidad Promedio", "% Graves (Sev 3–4)"],
    [[r["road_type"], fmt_int(r["total_accidentes"]), f"{r['pct_total']}%", r["severidad_promedio"], f"{r['pct_graves']}%"] for _, r in df_road.iterrows()]
)}

![Tipos de Vía y Top 10 Calles](../assets/charts/07_tipos_via_y_top10_calles.png)

---

### 3.6 Requerimiento 8: Tendencias Anuales y Mensuales
El volumen anual muestra un crecimiento sostenido desde **2016 (`410,821`)** hasta alcanzar su máximo histórico en **{int(peak_year_row['year'])} (`{fmt_int(peak_year_row['total_accidentes'])}` accidentes)** —impulsado por el retorno pleno de la movilidad post-pandemia y mayor cobertura de sensores—, cerrando **2023** con cobertura parcial de tres meses hasta marzo (`246,633`). No obstante, la severidad promedio descendió de `2.389` (2017) a `2.072` (2022) al ampliarse la detección de incidentes leves/moderados. Estacionalmente, **{peak_month_row['month_name']} (`{fmt_int(peak_month_row['total_accidentes'])}`, `{peak_month_row['pct_total']}%`)** y el último trimestre (octubre–diciembre) concentran la mayor accidentalidad por menor luz diurna y clima invernal.

![Tendencias Anuales y Mensuales](../assets/charts/08_tendencias_anuales_y_mensuales.png)

---

### 3.7 Requerimiento 9: Accidentes por Tipo de Vehículo Involucrado
Dado que Kaggle no incluye columna estructurada de vehículo (~99.1% de las descripciones detallan únicamente la vía y afectación de carriles), el módulo NLP extrajo menciones explícitas válidas en **`{fmt_int(veh_ident_total)}` descripciones (`{veh_ident_pct}%` del total)** tras excluir falsos positivos toponímicos:
- **Automóvil / Multivehículo** encabeza los casos identificados (`45,195`; `66.22%`) seguido por **Camión / Tráiler** (`16,389`; `24.01%`), **Peatón involucrado** (`2,559`; `3.75%`), **Autobús** (`1,502`; `2.20%`) y **Motocicleta** (`1,136`; `1.66%`).
- Destacan **Camión / Tráiler** (`2.521` mayor severidad promedio, `39.67%` graves, `124.95 min`) y **Automóvil / Multivehículo** (`43.02%` graves, `2.474` sev. prom.) por ocurrir predominantemente en autopistas de alta velocidad, mientras **Motocicleta** alcanza `14.88%` de eventos graves y **SUV / Van / Pickup** registra la mayor duración media (`158.20 min`).

{md_table(
    ["Tipo de Vehículo (NLP Description)", "Accidentes", "% sobre Identificados", "Severidad Prom.", "% Graves (S3–4)", "Duración Media (min)"],
    [[r["vehicle_type"], fmt_int(r["total_accidentes"]), f"{r['pct_identificados']}%", r["severidad_promedio"], f"{r['pct_graves']}%", r["duracion_media_min"]] for _, r in df_veh_k.iterrows()]
)}

![Tipos de Vehículo](../assets/charts/09_tipos_de_vehiculo.png)

---

### 3.8 Requerimiento 10: Distribución Geoespacial y Matriz de Correlación
El análisis por cuadrículas de `0.1° × 0.1°` confirma clústeres urbanos críticos en **Los Ángeles / Sur de California**, **Miami–Orlando–Tampa (Florida)**, **Houston–Dallas–Austin (Texas)**, **Charlotte–Raleigh (Carolina del Norte)** y el **corredor atlántico Noreste (NY–NJ–PA)**.

![Distribución Geoespacial](../assets/charts/10_distribucion_geoespacial_hotspots.png)

![Matriz de Correlación Exploratoria](../assets/charts/14_matriz_correlacion_exploratoria.png)

---

## 4. Visualizaciones de Power BI y Auditoría del Tablero

El tablero desarrollado en Power BI Desktop (`LO DE POWER BI YA ESTA FINALIZADO`, desplegado en `powerbi/dashboard_powerbi.html`) organiza la exploración en 8 vistas interactivas:

| # | Vista en Power BI | Captura | Hallazgo y Auditoría Técnica |
|---|---|---|---|
| 1 | Frecuencia por Estado y Top 10 Ciudades | `assets/powerbi/01_frecuencia_estado_top10_ciudades.jpg` | Mapa coroplético + ranking Miami, Houston, Los Angeles, Charlotte, Dallas, Orlando, Austin, Raleigh, Nashville y Baton Rouge. |
| 2 | KPIs, Patrón Horario y Día de la Semana | `assets/powerbi/02_kpis_hora_dia_semana.jpg` | Suma semanal exacta `7,728K` (viernes `1,366K` líder). Card `FinDeSemana=366` afectada por contexto YTD 2023 (total real Sáb+Dom: `1,231,427`). |
| 3 | Severidad y Clima al 100% | `assets/powerbi/03_severidad_clima_porcentaje.jpg` | Donut exacto `7728K` (`67K / 6157K / 1299K / 205K`) y proporción de severidad 3 superior al 20% en Lluvia y Otro. |
| 4 | Accidentes por Clima y Estado | `assets/powerbi/04_accidentes_clima_estado.jpg` | Totales exactos: Despejado `3,369,545`, Nublado `2,915,115`, Otro `623,936`, Lluvia `478,761`, Niebla `191,668`, Nieve/Hielo `149,367`. |
| 5 | Top 10 Vías Más Peligrosas | `assets/powerbi/05_top10_vias_peligrosas.png` | Se detectó ordenamiento alfabético descendente (`Zuni Rd SE`) en lugar de por volumen (`I-95 N`, `I-95 S`), corregido en Python/SQL. |
| 6 | Duración Promedio vs Mediana | `assets/powerbi/06_duracion_promedio_severidad.png` | Media `444 min` vs Mediana `75 min`, confirmando sesgo por outliers extremos en Severidad 4 (`1,685 min`). |
| 7 | Tendencias Anuales/Mensuales y Var MoM % | `assets/powerbi/07_tendencias_anuales_mensuales_mom.png` | Presencia de `(Blank)` en eje mensual por fechas con nanosegundos `.000000000` no parseadas; corregido en ETL Python/M. |
| 8 | Mapa Geoespacial de Severidad | `assets/powerbi/08_mapa_geoespacial_severidad.jpg` | Burbujas por `Start_Lat`/`Start_Lng` con segmentadores interactivos de Estado y Severidad. |

#### Capturas del Tablero Power BI

![PBI Vista 1: Frecuencia por Estado y Top 10 Ciudades](../assets/powerbi/01_frecuencia_estado_top10_ciudades.jpg)
![PBI Vista 2: KPIs, Patrón Horario y Semanal](../assets/powerbi/02_kpis_hora_dia_semana.jpg)
![PBI Vista 3: Severidad y Clima 100%](../assets/powerbi/03_severidad_clima_porcentaje.jpg)
![PBI Vista 4: Accidentes por Clima y Estado](../assets/powerbi/04_accidentes_clima_estado.jpg)
![PBI Vista 5: Top 10 Vías Más Peligrosas](../assets/powerbi/05_top10_vias_peligrosas.png)
![PBI Vista 6: Duración Promedio vs Mediana](../assets/powerbi/06_duracion_promedio_severidad.png)
![PBI Vista 7: Tendencias Anuales/Mensuales y Var MoM](../assets/powerbi/07_tendencias_anuales_mensuales_mom.png)
![PBI Vista 8: Mapa Geoespacial de Severidad](../assets/powerbi/08_mapa_geoespacial_severidad.jpg)

---

## 5. Medidas DAX Explicadas

Las definiciones completas y comentadas se encuentran en [`powerbi/dax_measures.md`](../powerbi/dax_measures.md):

1. **`Total Accidentes = COUNTROWS(Accidents)`**: Métrica base aditiva sobre la tabla de hechos que responde a cualquier segmentación de Estado, Ciudad, Clima, Fecha o Severidad (`7,728,394` / `8M`).
2. **`Accidentes FinDeSemana = CALCULATE([Total Accidentes], WEEKDAY(Accidents[Start_Time], 2) IN {{6, 7}})`**: Modifica el contexto de filtro para aislar sábados y domingos (`1,231,427` reales en todo el histórico).
3. **`Accidentes YTD = TOTALYTD([Total Accidentes], Dim_Calendario[Date])`**: Acumulado anual hasta la fecha máxima del contexto activo (marzo de 2023).
4. **`Var MoM % = DIVIDE([Total Accidentes] - [Accidentes Mes Anterior], [Accidentes Mes Anterior], 0)`**: Variación porcentual mensual usando `DATEADD(..., -1, MONTH)` protegida ante división por cero.
5. **`Duración Promedio` (`AVERAGE`) y `Duración Mediana` (`MEDIAN`)**: Par de medidas que diagnostican la asimetría de los tiempos de atención (`444 min` vs `75 min`).
6. **`Tasa x 100k Hab = DIVIDE([Total Accidentes] * 100000, MAX(Dim_Demografia[Population_2023]), 0)`**: Medida de normalización demográfica integrada mediante la tabla del Censo EE.UU.

---

## 6. Resultados y Visualización del ANOVA

Se ejecutaron **4 modelos ANOVA exactos** sobre la totalidad de los registros depurados en Python (`src/anova_analysis.py`), acompañados de verificación no paramétrica (**Kruskal-Wallis H**), prueba de homogeneidad de varianzas (**Levene**), corrección ante heterocedasticidad (**Welch ANOVA**) y contrastes múltiples post-hoc (**Tukey-Kramer HSD**).

### 6.1 Tabla Resumen de Pruebas ANOVA

| Modelo Evaluado | N Válido | F Clásico | p-valor | $\\eta^2$ (Tamaño del Efecto) | F Welch | Kruskal-Wallis H | Conclusión Estadística |
|---|---|---|---|---|---|---|---|
| **1. Duración (≤24h) ~ Severidad** | {fmt_int(s1['N'])} | **{s1['F_clasico']:,.2f}** | `< 1e-300` | **{s1['eta_cuadrado']:.5f}** | {s1['F_welch']:,.2f} | {s1['kruskal_H']:,.1f} | Se rechaza $H_0$: la severidad determina diferencias altamente significativas en duración. |
| **2. Severidad ~ Clima** | {fmt_int(s2['N'])} | **{s2['F_clasico']:,.2f}** | `< 1e-300` | **{s2['eta_cuadrado']:.5f}** | {s2['F_welch']:,.2f} | {s2['kruskal_H']:,.1f} | Se rechaza $H_0$: el clima altera significativamente la severidad promedio (Lluvia/Otro más graves). |
| **3. Severidad ~ Franja Horaria** | {fmt_int(s3['N'])} | **{s3['F_clasico']:,.2f}** | `< 1e-300` | **{s3['eta_cuadrado']:.5f}** | {s3['F_welch']:,.2f} | {s3['kruskal_H']:,.1f} | Se rechaza $H_0$: la franja horaria (noche/madrugada vs pico) incide en la severidad. |

### 6.2 ANOVA Factorial de 2 Vías: `Severidad ~ Clima × Franja Horaria`

{md_table(
    ["Fuente de Variación", "gl (df)", "Suma de Cuadrados (Tipo III)", "Cuadrado Medio", "F", "p-valor", "Eta Parcial²"],
    [[r["fuente"], fmt_int(r["df"]), f"{r['ss_tipo_iii']:,.2f}", f"{r['ms']:.4f}" if pd.notna(r["ms"]) else "-", f"{r['F']:,.2f}" if pd.notna(r["F"]) else "-", f"{r['p_valor']:.2e}" if pd.notna(r["p_valor"]) else "-", f"{r['eta_parcial_sq']:.6f}" if pd.notna(r["eta_parcial_sq"]) else "-"] for _, r in df_2w.iterrows()]
)}

### 6.3 Estadísticos por Grupo (Duración ~ Severidad y Severidad ~ Clima)

{md_table(
    ["Severidad", "n", "Media (min)", "Desv. Est.", "Mediana (min)", "IC 95%"],
    [[int(r["grupo"]), fmt_int(r["n"]), r["media"], r["desv_std"], r["mediana"], f"[{r['ic95_inf']}, {r['ic95_sup']}]"] for _, r in df_g1.iterrows()]
)}

{md_table(
    ["Clima", "n", "Severidad Media", "Desv. Est.", "IC 95%"],
    [[r["grupo"], fmt_int(r["n"]), r["media"], r["desv_std"], f"[{r['ic95_inf']}, {r['ic95_sup']}]"] for _, r in df_g2.iterrows()]
)}

**Interpretación Práctica vs. Significancia Estadística:**  
Dado el tamaño masivo ($N > 7.7$ millones), casi cualquier diferencia mínima produce $p < 0.001$; por ello es fundamental analizar el **tamaño del efecto ($\\eta^2$)** y las **diferencias reales de medias (Tukey HSD)**:
- En **Duración ~ Severidad**, el efecto es **sustantivo** ($\\eta^2 = {s1['eta_cuadrado']:.4f}$): los incidentes de Severidad 4 promedian `185.9 min` (vs `45.7 min` en Severidad 1 y `67.8 min` en Severidad 3), resultando **todos los 6 pares significativos** en Tukey-Kramer HSD (`p < 1e-300`).
- En **Severidad ~ Clima × Franja Horaria**, tanto los efectos principales como la **interacción son significativos** (`F = 87.58`, `p < 1e-300`): mientras en `Lluvia`, `Nublado` y `Despejado` la severidad máxima ocurre en horario nocturno (`20–23h`, ej. Lluvia nocturna = `2.279` vs pico tarde = `2.230`), en `Nieve/Hielo` y `Niebla` la gravedad promedio es mayor al mediodía (`2.259` y `2.203`).

![ANOVA Duración vs Severidad](../assets/charts/11_anova_duracion_severidad.png)

![ANOVA Severidad Clima y Franja](../assets/charts/12_anova_severidad_clima_franja.png)

![ANOVA Tukey Post-Hoc](../assets/charts/13_anova_tukey_posthoc.png)

---

## 7. Conclusiones y Recomendaciones

1. **Concentración geográfica y enfoque per cápita:** California (`1.74M`), Florida (`880K`) y Texas (`583K`) lideran en volumen bruto, mientras Miami, Houston y Los Ángeles encabezan la siniestralidad urbana. Sin embargo, al cruzar con datos demográficos del Censo, Carolina del Sur (`7,119` x 100k hab.) y Oregón (`4,244` x 100k hab.) superan en riesgo relativo per cápita, demostrando que la planeación vial debe combinar volumen absoluto e incidencia ajustada por población.
2. **Ventana crítica de gestión del tráfico:** La siniestralidad alcanza su máximo los **viernes (`17.68%`)** y entre las **15:00 y 18:00 horas** (pico vespertino), siendo las **autopistas interestatales** (`I-95`, `I-5`, `I-10`) los corredores con mayor proporción de eventos graves (`32.44%` en `Sev 3–4`).
3. **Impacto climático y nocturno:** Aunque el 85% de los incidentes ocurre en clima despejado o nublado por mayor exposición vehicular, la **lluvia (`22.76%` graves)** y la **nieve/hielo (`19.95%` graves)** elevan de forma estadísticamente significativa la severidad promedio (ANOVA $p < 10^{{-300}}$), con interacción significativa según la franja horaria.
4. **Control de calidad de datos y gobernanza BI:** La auditoría conjunta Python + SQL + Power BI permitió detectar y corregir *timestamps* con nanosegundos (`.000000000`), separar *outliers* de duración superiores a 24 horas (explicando la brecha media `444 min` vs mediana `75 min`), corregir el orden alfabético en el ranking de vías y depurar falsos positivos toponímicos en la extracción NLP de tipos de vehículo.
"""
    return md


def md_to_html(md_text: str, title: str) -> str:
    """Convierte Markdown estructurado a HTML imprimible (soporta tablas, h1-h4, bloques de código, inline code con * y LaTeX básico)."""
    lines = md_text.splitlines()
    out = []
    in_table = False
    in_ul = False
    in_ol = False
    in_code = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def inline_fmt(s: str) -> str:
        # 1. Proteger fragmentos `código` antes de escapar o aplicar *italica* / **negrita**
        code_tokens = []

        def _save_code(m):
            code_tokens.append(f"<code>{html.escape(m.group(1))}</code>")
            return f"@@CODE{len(code_tokens) - 1}@@"

        s = re.sub(r"`([^`]+)`", _save_code, s)

        # 2. Convertir expresiones LaTeX simples $...$ a Unicode legible
        def _clean_math(m):
            expr = m.group(1)
            expr = expr.replace("\\eta^2", "η²")
            expr = expr.replace("H_0", "H₀")
            expr = expr.replace("10^{-300}", "10⁻³⁰⁰")
            return expr

        s = re.sub(r"\$([^$]+)\$", _clean_math, s)

        # 3. Escapar HTML e interpretar imágenes, enlaces y énfasis
        s = html.escape(s)
        s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<figure><img src="\2" alt="\1" /><figcaption>\1</figcaption></figure>', s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)

        # 4. Restaurar fragmentos de código protegidos
        for idx, tok in enumerate(code_tokens):
            s = s.replace(f"@@CODE{idx}@@", tok)
        return s

    for line in lines:
        s = line.strip()
        if s.startswith("```"):
            close_lists()
            if in_table:
                out.append("</tbody></table>")
                in_table = False
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if s.startswith("<details>") or s.startswith("</details>") or s.startswith("<summary>") or s.startswith("</summary>"):
            continue
        if s.startswith("|") and s.endswith("|"):
            close_lists()
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(set(c) <= {"-", ":"} for c in cells):
                continue
            if not in_table:
                out.append("<table><thead><tr>" + "".join(f"<th>{inline_fmt(c)}</th>" for c in cells) + "</tr></thead><tbody>")
                in_table = True
            else:
                out.append("<tr>" + "".join(f"<td>{inline_fmt(c)}</td>" for c in cells) + "</tr>")
            continue
        elif in_table:
            out.append("</tbody></table>")
            in_table = False

        if s == "---":
            close_lists()
            out.append("<hr />")
        elif s.startswith("#### "):
            close_lists()
            out.append(f"<h4>{inline_fmt(s[5:])}</h4>")
        elif s.startswith("### "):
            close_lists()
            out.append(f"<h3>{inline_fmt(s[4:])}</h3>")
        elif s.startswith("## "):
            close_lists()
            out.append(f"<h2>{inline_fmt(s[3:])}</h2>")
        elif s.startswith("# "):
            close_lists()
            out.append(f"<h1>{inline_fmt(s[2:])}</h1>")
        elif s.startswith("- "):
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline_fmt(s[2:])}</li>")
        elif re.match(r"^\d+\.\s+", s):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{inline_fmt(re.sub(r'^\d+\.\s+', '', s))}</li>")
        elif s == "":
            close_lists()
        else:
            close_lists()
            out.append(f"<p>{inline_fmt(s)}</p>")

    close_lists()
    if in_table:
        out.append("</tbody></table>")

    body_html = "\n".join(out)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>{html.escape(title)}</title>
  <style>
    @page {{ size: A4; margin: 16mm 15mm; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #1e293b; max-width: 980px; margin: 0 auto; padding: 24px; line-height: 1.55; font-size: 10.5pt; }}
    h1 {{ color: #0f172a; border-bottom: 3px solid #0284c7; padding-bottom: 8px; font-size: 19pt; margin-top: 0; }}
    h2 {{ color: #0369a1; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; margin-top: 22px; page-break-after: avoid; font-size: 14pt; }}
    h3 {{ color: #0f172a; margin-top: 14px; page-break-after: avoid; font-size: 11.5pt; }}
    h4 {{ color: #334155; margin-top: 12px; page-break-after: avoid; font-size: 10.5pt; }}
    p {{ margin: 7px 0; }}
    ul, ol {{ margin: 6px 0 10px 22px; }}
    li {{ margin: 4px 0; }}
    code {{ background: #f1f5f9; padding: 1px 5px; border-radius: 4px; font-family: Consolas, monospace; font-size: 9pt; color: #0f172a; }}
    pre {{ background: #0f172a; color: #e2e8f0; padding: 10px 14px; border-radius: 6px; overflow-x: auto; font-size: 8.5pt; line-height: 1.45; page-break-inside: avoid; }}
    pre code {{ background: transparent; color: #e2e8f0; padding: 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 8.8pt; page-break-inside: avoid; }}
    th {{ background: #0f172a; color: #fff; text-align: left; padding: 6px 8px; }}
    td {{ border: 1px solid #cbd5e1; padding: 5px 8px; }}
    tr:nth-child(even) td {{ background: #f8fafc; }}
    figure {{ margin: 12px 0; text-align: center; page-break-inside: avoid; }}
    figure img {{ max-width: 96%; max-height: 400px; border: 1px solid #cbd5e1; border-radius: 6px; }}
    figcaption {{ font-size: 8.6pt; color: #475569; margin-top: 4px; font-style: italic; }}
    hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 18px 0; }}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""


def build_docx_report(audit, summary, anova, dfs):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    # Portada
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_title.add_run("\n\nINFORME TÉCNICO — PROYECTO 3\n")
    r.bold = True
    r.font.size = Pt(22)
    r.font.color.rgb = RGBColor(15, 23, 42)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p_sub.add_run("Análisis de Accidentes de Tránsito en Zonas Urbanas (EE.UU., 2016–2023)\n")
    r2.bold = True
    r2.font.size = Pt(15)
    r2.font.color.rgb = RGBColor(3, 105, 161)

    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_meta.add_run(
        "Dataset: Kaggle US Accidents (sobhanmoosavi/us-accidents) + Censo Demográfico EE.UU. 2023\n"
        "Tecnologías: Python (Pandas, PyArrow, SciPy, Matplotlib, Seaborn), PySpark, SQLite, Power Query (M) y Power BI (DAX)\n"
    )
    doc.add_page_break()

    def add_h1(text):
        return doc.add_heading(text, level=1)

    def add_h2(text):
        return doc.add_heading(text, level=2)

    def add_df_table(df_tbl):
        t = doc.add_table(rows=1, cols=len(df_tbl.columns))
        t.style = "Light Grid Accent 1"
        for i, col in enumerate(df_tbl.columns):
            t.rows[0].cells[i].text = str(col)
        for _, row in df_tbl.iterrows():
            cells = t.add_row().cells
            for i, val in enumerate(row):
                cells[i].text = str(val)
        doc.add_paragraph()

    def add_img(path, caption, width=6.1):
        if os.path.exists(path):
            png_buf, _, _ = image_to_png_stream(path)
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(png_buf, width=Inches(width))
            pc = doc.add_paragraph(caption)
            pc.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pc.runs[0].italic = True
            pc.runs[0].font.size = Pt(9)

    # 1. Objetivos específicos
    add_h1("1. Objetivos del Proyecto")
    add_h2("1.1 Objetivo General")
    doc.add_paragraph(
        "Integrar datos abiertos de accidentes de tránsito en zonas urbanas de Estados Unidos con variables climáticas, "
        "viales y demográficas, identificando patrones espacio-temporales, factores críticos de severidad y zonas de riesgo "
        "mediante un flujo reproducible en Python, SQL, PySpark, Power Query, Power BI y análisis estadístico ANOVA."
    )
    add_h2("1.2 Objetivos Específicos")
    for ob in [
        f"Implementar un pipeline ETL escalable sobre {fmt_int(audit['total_raw_rows'])} registros para normalizar fechas con nanosegundos, depurar outliers de duración y enriquecer con demografía estatal.",
        "Responder los 10 requerimientos analíticos utilizando consultas SQL sobre SQLite y visualizaciones generadas en Python.",
        "Documentar las 8 vistas del tablero desarrollado en Power BI, explicar sus medidas DAX y detallar el código Power Query M.",
        "Validar estadísticamente mediante pruebas ANOVA unifactoriales, factoriales y post-hoc Tukey-Kramer HSD el impacto de la severidad, clima y franja horaria."
    ]:
        doc.add_paragraph(ob, style="List Bullet")

    # 2. Descripción del ETL
    add_h1("2. Descripción del Proceso ETL e Implementación (Python, SQL, Power Query)")
    doc.add_paragraph(
        f"El flujo ETL procesó {fmt_int(audit['total_raw_rows'])} registros en bloques de 500,000 filas (src/etl_us_accidents.py), "
        f"complementado con versión distribuida PySpark (src/etl_pyspark.py) y script Power Query M (powerbi/power_query_etl.pq). "
        f"Se corrigieron {fmt_int(audit['dotted_timestamps_fixed'])} marcas de tiempo con nanosegundos (.000000000), "
        f"se imputaron {fmt_int(audit['nulls_weather'])} nulos de clima a 'Otro' y se identificaron {fmt_int(audit['outliers_gt_24h'])} "
        "cierres viales atípicos superiores a 24 horas (preservados en duration_raw_min y acotados en duration_clean_min <= 1440 min)."
    )
    etl_tbl = pd.DataFrame([
        ["Registros brutos procesados", fmt_int(audit["total_raw_rows"])],
        ["Registros únicos tras deduplicación", fmt_int(audit["total_clean_rows"])],
        ["Timestamps con nanosegundos corregidos", fmt_int(audit["dotted_timestamps_fixed"])],
        ["Outliers de duración (> 24h)", fmt_int(audit["outliers_gt_24h"])],
        ["Nulos originales en Weather_Condition", fmt_int(audit["nulls_weather"])],
        ["Menciones vehiculares válidas (NLP Description)", fmt_int(dfs["veh_k"]["total_accidentes"].sum())],
    ], columns=["Métrica ETL", "Valor"])
    add_df_table(etl_tbl)

    # 3. Exploración y 10 requerimientos
    add_h1("3. Exploración de Datos y los 10 Requerimientos Analíticos")
    add_h2("3.1 Estados, Ciudades y Tasa Demográfica (Req. 1)")
    st_tbl = dfs["states"].head(10)[["state", "state_name", "total_accidentes", "pct_nacional", "tasa_x_100k_hab", "severidad_promedio"]]
    add_df_table(st_tbl)
    add_img(os.path.join(CHARTS_DIR, "01_top10_estados_y_ciudades.png"), "Figura 1. Top 10 estados y ciudades urbanas con mayor siniestralidad.")
    add_img(os.path.join(CHARTS_DIR, "02_demografia_tasa_y_regiones.png"), "Figura 2. Tasa demográfica por 100k habitantes y distribución regional.")

    add_h2("3.2 Patrón Horario y Días de la Semana (Req. 2 y 6)")
    add_df_table(dfs["day"][["day_name", "tipo_dia", "total_accidentes", "pct_total", "severidad_promedio"]])
    add_img(os.path.join(CHARTS_DIR, "03_patron_horario_y_semanal.png"), "Figura 3. Distribución bimodal horaria y semanal.")
    add_img(os.path.join(CHARTS_DIR, "04_heatmap_dia_hora.png"), "Figura 4. Mapa de calor de accidentalidad por día y hora.")

    add_h2("3.3 Severidad y Duración del Incidente (Req. 3 y 7)")
    add_df_table(dfs["sev"][["severity", "total_accidentes", "pct_total", "duracion_media_bruta_min", "duracion_media_depurada_min", "mediana_depurada_min"]])
    add_img(os.path.join(CHARTS_DIR, "05_severidad_y_duracion.png"), "Figura 5. Severidad y comparación media bruta vs depurada y mediana.")

    add_h2("3.4 Condiciones Climáticas (Req. 4)")
    add_df_table(dfs["weather"][["weather_group", "total_accidentes", "pct_total", "pct_graves", "visibilidad_media_mi"]])
    add_img(os.path.join(CHARTS_DIR, "06_clima_y_severidad.png"), "Figura 6. Volumen climático y porcentaje de severidad 1–4.")

    add_h2("3.5 Vías Más Peligrosas y Tendencias Temporales (Req. 5 y 8)")
    doc.add_paragraph(
        "El máximo anual se registró en 2022 (1,762,452 accidentes), cerrando 2023 con cobertura parcial hasta marzo (246,633). "
        "El ranking real de vías corrige el orden alfabético del dashboard BI al ser encabezado por I-95 N (78,430), I-95 S (74,528) e I-5 N (71,968)."
    )
    add_df_table(dfs["road"][["road_type", "total_accidentes", "pct_total", "pct_graves"]])
    add_img(os.path.join(CHARTS_DIR, "07_tipos_via_y_top10_calles.png"), "Figura 7. Categorías de vía y Top 10 vías específicas.")
    add_img(os.path.join(CHARTS_DIR, "08_tendencias_anuales_y_mensuales.png"), "Figura 8. Tendencia anual 2016–2023 y estacionalidad mensual.")

    add_h2("3.6 Tipo de Vehículo, Geoespacialidad y Correlación (Req. 9 y 10)")
    doc.add_paragraph(
        "Automóvil / Multivehículo lidera los incidentes identificados en descripciones (45,195; 43.02% graves), seguido por "
        "Camión / Tráiler (16,389; mayor severidad media = 2.521 y 124.95 min de duración), Peatón involucrado (2,559), Autobús (1,502) y Motocicleta (1,136)."
    )
    add_df_table(dfs["veh_k"][["vehicle_type", "total_accidentes", "pct_identificados", "severidad_promedio", "pct_graves", "duracion_media_min"]])
    add_img(os.path.join(CHARTS_DIR, "09_tipos_de_vehiculo.png"), "Figura 9. Accidentes y severidad grave por tipo de vehículo involucrado.")
    add_img(os.path.join(CHARTS_DIR, "10_distribucion_geoespacial_hotspots.png"), "Figura 10. Mapa nacional de densidad y Top 300 hotspots críticos.")
    add_img(os.path.join(CHARTS_DIR, "14_matriz_correlacion_exploratoria.png"), "Figura 11. Matriz de correlación exploratoria.")

    # 4. Visualizaciones de Power BI (las 8 capturas completas)
    add_h1("4. Visualizaciones de Power BI y Auditoría del Tablero")
    doc.add_paragraph(
        "El tablero finalizado en Power BI Desktop está desplegado en powerbi/dashboard_powerbi.html e integra 8 vistas interactivas "
        "auditadas frente a los resultados de Python y SQL:"
    )
    for fname, cap in [
        ("01_frecuencia_estado_top10_ciudades.jpg", "Power BI Vista 1: Mapa coroplético por estado y Top 10 ciudades (Miami líder con 186,768)."),
        ("02_kpis_hora_dia_semana.jpg", "Power BI Vista 2: KPIs generales, distribución horaria bimodal y día semanal (Viernes 1,366K; Sáb+Dom reales = 1,231,427)."),
        ("03_severidad_clima_porcentaje.jpg", "Power BI Vista 3: Anillo de severidad (7728K) y participación porcentual 100% por clima."),
        ("04_accidentes_clima_estado.jpg", "Power BI Vista 4: Accidentes por grupo climático y mapa tooltip estatal."),
        ("05_top10_vias_peligrosas.png", "Power BI Vista 5: Visual de vías en BI (orden alfabético descendente Zuni Rd SE; auditado vs I-95 N/S)."),
        ("06_duracion_promedio_severidad.png", "Power BI Vista 6: Duración media global (444 min) vs mediana (75 min) por sesgo positivo."),
        ("07_tendencias_anuales_mensuales_mom.png", "Power BI Vista 7: Serie anual/mensual con Var MoM % y detección de (Blank) por nanosegundos."),
        ("08_mapa_geoespacial_severidad.jpg", "Power BI Vista 8: Distribución geoespacial de severidad 1–4 por coordenadas."),
    ]:
        add_img(os.path.join(PBI_DIR, fname), cap, width=5.5)

    # 5. Medidas DAX Explicadas
    add_h1("5. Medidas DAX Explicadas")
    doc.add_paragraph("Catálogo completo de medidas DAX documentadas en powerbi/dax_measures.md:")
    dax_tbl = pd.DataFrame([
        ["Total Accidentes", "COUNTROWS(Accidents)", "Conteo aditivo sensible a todos los segmentadores (7,728,394 / 8M)."],
        ["Accidentes FinDeSemana", "CALCULATE([Total Accidentes], WEEKDAY(Accidents[Start_Time], 2) IN {6, 7})", "Aísla sábado y domingo (1,231,427 reales; 15.93% del total)."],
        ["Accidentes YTD", "TOTALYTD([Total Accidentes], Dim_Calendario[Date])", "Acumulado anual hasta la fecha máxima del contexto activo (marzo 2023)."],
        ["Var MoM %", "DIVIDE([Total Accidentes] - [Accidentes Mes Anterior], [Accidentes Mes Anterior], 0)", "Crecimiento porcentual mes vs mes previo usando DATEADD(..., -1, MONTH)."],
        ["Duración Promedio / Mediana", "AVERAGE(Accidents[Duracion_Min]) / MEDIAN(Accidents[Duracion_Min])", "Diagnostica la asimetría extrema por outliers >24h (444 min vs 75 min)."],
        ["Tasa x 100k Hab", "DIVIDE([Total Accidentes] * 100000, MAX(Dim_Demografia[Population_2023]), 0)", "Normalización poblacional cruzada con Censo EE.UU. 2023."],
    ], columns=["Medida DAX", "Fórmula", "Explicación Funcional"])
    add_df_table(dax_tbl)

    # 6. Resultados y visualización del ANOVA
    add_h1("6. Resultados y Visualización del ANOVA")
    s1 = anova["anova_duracion_severidad"]
    s2 = anova["anova_severidad_clima"]
    s3 = anova["anova_severidad_franja"]
    anova_tbl = pd.DataFrame([
        ["Duración ~ Severidad", fmt_int(s1["N"]), f"{s1['F_clasico']:,.2f}", "< 1e-300", f"{s1['eta_cuadrado']:.5f}", f"{s1['kruskal_H']:,.1f}"],
        ["Severidad ~ Clima", fmt_int(s2["N"]), f"{s2['F_clasico']:,.2f}", "< 1e-300", f"{s2['eta_cuadrado']:.5f}", f"{s2['kruskal_H']:,.1f}"],
        ["Severidad ~ Franja Horaria", fmt_int(s3["N"]), f"{s3['F_clasico']:,.2f}", "< 1e-300", f"{s3['eta_cuadrado']:.5f}", f"{s3['kruskal_H']:,.1f}"],
    ], columns=["Modelo", "N", "F", "p-valor", "Eta²", "Kruskal H"])
    add_df_table(anova_tbl)
    add_df_table(dfs["anova_2w"])
    doc.add_paragraph(
        "La interacción Clima × Franja Horaria resultó altamente significativa (F = 87.58, p < 1e-300): "
        "Lluvia, Nublado y Despejado exhiben su pico de severidad en horario nocturno (20–23h), mientras que Nieve/Hielo "
        "alcanza su mayor severidad media en franja diurna/mediodía (2.259)."
    )
    add_img(os.path.join(CHARTS_DIR, "11_anova_duracion_severidad.png"), "Figura 12. ANOVA Duración depurada según Severidad.")
    add_img(os.path.join(CHARTS_DIR, "12_anova_severidad_clima_franja.png"), "Figura 13. ANOVA Severidad por Clima e interacción Clima × Franja Horaria.")
    add_img(os.path.join(CHARTS_DIR, "13_anova_tukey_posthoc.png"), "Figura 14. Contrastes post-hoc Tukey-Kramer HSD.")

    # 7. Conclusiones
    add_h1("7. Conclusiones")
    for c in [
        "California lidera en volumen total (1.74M), Miami en zonas urbanas (186.8K) y Carolina del Sur en tasa ajustada por población (7,119 x 100k hab.).",
        "El riesgo vial alcanza su pico los viernes (17.68%) en franja vespertina (15:00–18:00h), con mayor proporción de gravedad en autopistas interestatales (32.44%).",
        "La lluvia (22.76% graves), nieve/hielo y conducción nocturna incrementan significativamente la severidad promedio (ANOVA factorial p < 1e-300).",
        "La auditoría Python + SQL + Power BI resolvió fallas de parseo de nanosegundos, corrigió el ranking Top 10 real de vías, depuró falsos positivos vehiculares y explicó la brecha media/mediana de duración."
    ]:
        doc.add_paragraph(c, style="List Bullet")

    docx_path = os.path.join(DOCS_DIR, "informe_tecnico.docx")
    doc.save(docx_path)
    print(f"[OK] Word generado: {docx_path}")


def _register_pdf_fonts():
    ttf_dir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    mapping = {
        "DejaVu": "DejaVuSans.ttf",
        "DejaVu-Bold": "DejaVuSans-Bold.ttf",
        "DejaVu-Italic": "DejaVuSans-Oblique.ttf",
        "DejaVu-BoldItalic": "DejaVuSans-BoldOblique.ttf",
        "DejaVuMono": "DejaVuSansMono.ttf",
    }
    loaded = True
    for font_name, filename in mapping.items():
        fpath = os.path.join(ttf_dir, filename)
        if not os.path.exists(fpath):
            loaded = False
            break
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, fpath))
    if loaded:
        pdfmetrics.registerFontFamily(
            "DejaVu",
            normal="DejaVu",
            bold="DejaVu-Bold",
            italic="DejaVu-Italic",
            boldItalic="DejaVu-BoldItalic",
        )
        return "DejaVu", "DejaVu-Bold", "DejaVu-Italic", "DejaVuMono"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"


def build_pdf_report(audit, summary, anova, dfs):
    font_reg, font_bold, font_ital, font_mono = _register_pdf_fonts()
    pdf_path = os.path.join(DOCS_DIR, "informe_tecnico.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=52,
        bottomMargin=44,
        title="Informe Técnico — Proyecto 3: Análisis de Accidentes de Tránsito en Zonas Urbanas",
        author="Proyecto 3 Data Analytics",
    )

    styles = getSampleStyleSheet()
    st_cover_tag = ParagraphStyle("CoverTag", fontName=font_bold, fontSize=11, leading=14, textColor=colors.HexColor("#0284c7"), alignment=TA_CENTER)
    st_cover_title = ParagraphStyle("CoverTitle", fontName=font_bold, fontSize=21, leading=26, textColor=colors.HexColor("#0f172a"), alignment=TA_CENTER, spaceAfter=10)
    st_cover_sub = ParagraphStyle("CoverSub", fontName=font_reg, fontSize=11.5, leading=16, textColor=colors.HexColor("#334155"), alignment=TA_CENTER, spaceAfter=16)
    st_h1 = ParagraphStyle("H1Custom", parent=styles["Heading1"], fontName=font_bold, fontSize=14.5, leading=18, textColor=colors.HexColor("#0369a1"), spaceBefore=12, spaceAfter=6, keepWithNext=True)
    st_h2 = ParagraphStyle("H2Custom", parent=styles["Heading2"], fontName=font_bold, fontSize=11.5, leading=15, textColor=colors.HexColor("#0f172a"), spaceBefore=9, spaceAfter=4, keepWithNext=True)
    st_body = ParagraphStyle("BodyCustom", fontName=font_reg, fontSize=9.4, leading=13.5, textColor=colors.HexColor("#1e293b"), alignment=TA_JUSTIFY, spaceAfter=5)
    st_bullet = ParagraphStyle("BulletCustom", fontName=font_reg, fontSize=9.3, leading=13, textColor=colors.HexColor("#1e293b"), leftIndent=14, firstLineIndent=-8, spaceAfter=3.5)
    st_cap = ParagraphStyle("CapCustom", fontName=font_ital, fontSize=8.3, leading=11, textColor=colors.HexColor("#475569"), alignment=TA_CENTER, spaceAfter=9)
    st_code = ParagraphStyle("CodeCustom", fontName=font_mono, fontSize=7.4, leading=10.2, textColor=colors.HexColor("#e2e8f0"), backColor=colors.HexColor("#0f172a"), leftIndent=8, rightIndent=8, spaceBefore=3, spaceAfter=6, borderPadding=6)
    st_th = ParagraphStyle("ThCell", fontName=font_bold, fontSize=7.9, leading=10, textColor=colors.white, alignment=TA_LEFT)
    st_td = ParagraphStyle("TdCell", fontName=font_reg, fontSize=7.8, leading=10, textColor=colors.HexColor("#1e293b"), alignment=TA_LEFT)

    story = []
    usable_w = A4[0] - 84  # ~511 pt

    def make_table(headers, rows, col_widths=None):
        data = [[Paragraph(html.escape(str(h)), st_th) for h in headers]]
        for r in rows:
            data.append([Paragraph(html.escape(str(c)), st_td) for c in r])
        if col_widths is None:
            col_widths = [usable_w / len(headers)] * len(headers)
        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 7))

    def add_figure(path, caption, max_w=488, max_h=270):
        if not os.path.exists(path):
            return
        png_buf, w_px, h_px = image_to_png_stream(path)
        scale = min(max_w / float(w_px), max_h / float(h_px))
        img = RLImage(png_buf, width=w_px * scale, height=h_px * scale)
        img.hAlign = "CENTER"
        story.append(KeepTogether([img, Spacer(1, 3), Paragraph(html.escape(caption), st_cap)]))

    def draw_header_footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.setLineWidth(0.6)
        canvas.line(42, A4[1] - 38, A4[0] - 42, A4[1] - 38)
        canvas.setFont(font_reg, 7.8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(42, A4[1] - 33, "Informe Técnico — Proyecto 3: Análisis de Accidentes de Tránsito en Zonas Urbanas")
        canvas.drawRightString(A4[0] - 42, A4[1] - 33, "Kaggle US Accidents + Censo EE.UU. 2023")
        canvas.line(42, 32, A4[0] - 42, 32)
        canvas.drawRightString(A4[0] - 42, 20, f"Página {doc_obj.page}")
        canvas.restoreState()

    aud = summary["auditoria"]
    s1 = anova["anova_duracion_severidad"]
    s2 = anova["anova_severidad_clima"]
    s3 = anova["anova_severidad_franja"]

    # Portada
    story.append(Spacer(1, 75))
    story.append(Paragraph("ENTREGABLE 1 · INFORME TÉCNICO", st_cover_tag))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Proyecto 3: Análisis de Accidentes de Tránsito en Zonas Urbanas (EE.UU., 2016–2023)", st_cover_title))
    story.append(Paragraph(
        "Integración de datos abiertos de siniestralidad vial con variables climáticas, de infraestructura y demográficas del Censo de Estados Unidos 2023",
        st_cover_sub,
    ))
    story.append(Spacer(1, 18))
    make_table(
        ["Dimensión del Proyecto", "Cobertura Verificada"],
        [
            ["Fuente Principal", "Kaggle US Accidents (US_Accidents_March23.csv) — 7,728,394 registros"],
            ["Enriquecimiento Demográfico", "Censo EE.UU. 2023 (50 estados + D.C., población, área, densidad)"],
            ["Período Analizado", f"{aud['fecha_inicio']}  →  {aud['fecha_fin']} ({aud['estados_cubiertos']} entidades, {fmt_int(aud['ciudades_cubiertas'])} ciudades)"],
            ["Stack Tecnológico", "Python 3.13, PyArrow, SQLite 3, PySpark, Power Query (M), Power BI (DAX), SciPy ANOVA"],
            ["Modelos Estadísticos", "3 ANOVA Unifactoriales + Factorial 2 Vías (Clima × Franja) + Tukey HSD + Kruskal-Wallis"],
        ],
        col_widths=[160, 351],
    )
    story.append(PageBreak())

    # 1. Objetivos específicos
    story.append(Paragraph("1. Objetivos del Proyecto", st_h1))
    story.append(Paragraph("1.1 Objetivo General", st_h2))
    story.append(Paragraph(
        "Integrar datos abiertos de accidentes de tránsito en zonas urbanas y corredores viales de Estados Unidos con variables climáticas, "
        "de infraestructura vial y demográficas, identificando patrones temporales, factores críticos de severidad y puntos geoespaciales de alta "
        "concentración mediante un flujo reproducible ETL + SQL + Power BI + ANOVA.",
        st_body,
    ))
    story.append(Paragraph("1.2 Objetivos Específicos", st_h2))
    for b in [
        f"Implementar un pipeline ETL híbrido (Python/PyArrow, PySpark, SQLite y Power Query M) sobre <b>{fmt_int(audit['total_raw_rows'])} registros</b>, corrigiendo timestamps con nanosegundos, aislando outliers &gt;24h y enriqueciendo con variables viales, vehiculares y poblacionales.",
        "Responder los 10 requerimientos analíticos de negocio mediante consultas SQL reproducibles y visualizaciones estadísticas en Python.",
        "Documentar y auditar las 8 vistas del tablero desarrollado en Power BI, explicar sus medidas DAX y detallar el código Power Query M.",
        "Evaluar estadísticamente mediante pruebas ANOVA unifactoriales, factoriales y post-hoc (Tukey-Kramer HSD / Kruskal-Wallis) la significancia y tamaño del efecto de severidad, clima y franja horaria.",
    ]:
        story.append(Paragraph(f"• {b}", st_bullet))

    # 2. Descripción del ETL
    story.append(Paragraph("2. Descripción del Proceso ETL e Implementación (Python, SQL, Power Query)", st_h1))
    story.append(Paragraph(
        f"El flujo ETL (<b>src/etl_us_accidents.py</b>) procesó por bloques de 500,000 filas los {fmt_int(audit['total_raw_rows'])} registros originales "
        f"(~3.06 GB), complementado con una implementación distribuida en <b>src/etl_pyspark.py</b> y su equivalente Power Query en <b>powerbi/power_query_etl.pq</b>. "
        f"Se normalizaron {fmt_int(audit['dotted_timestamps_fixed'])} marcas de tiempo con nanosegundos (.000000000), se imputaron {fmt_int(audit['nulls_weather'])} nulos climáticos a 'Otro' "
        f"y se separaron {fmt_int(audit['outliers_gt_24h'])} cierres extremos &gt;24 horas en <i>duration_clean_min</i> preservando <i>duration_raw_min</i> para auditar Power BI.",
        st_body,
    ))
    make_table(
        ["Hallazgo / Métrica de Auditoría ETL", "Cantidad Observada", "Decisión Técnica Aplicada"],
        [
            ["Registros brutos extraídos (CSV)", fmt_int(audit["total_raw_rows"]), "Lectura streaming por bloques de 500k registros sin muestreo destructivo."],
            ["Registros únicos tras deduplicación (ID)", fmt_int(audit["total_clean_rows"]), "0 duplicados; 100% de integridad por clave primaria."],
            ["Timestamps con nanosegundos (.000000000)", fmt_int(audit["dotted_timestamps_fixed"]), "Recorte a yyyy-MM-dd HH:mm:ss eliminando errores (Blank) en calendario."],
            ["Outliers extremos de duración (> 24h)", fmt_int(audit["outliers_gt_24h"]), "Preservación en duration_raw_min; depuración en duration_clean_min <= 1440."],
            ["Nulos originales en Weather_Condition", fmt_int(audit["nulls_weather"]), "Imputación semántica a 'Otro' dentro de 6 grupos estandarizados."],
            ["Menciones vehiculares válidas (NLP RE2)", fmt_int(dfs["veh_k"]["total_accidentes"].sum()), "Filtrado de falsos positivos toponímicos ('I-80 Bus', 'Van Ness Ave')."],
        ],
        col_widths=[180, 95, 236],
    )
    story.append(Paragraph("2.1 Extractos de Código ETL (Python, SQL y Power Query M)", st_h2))
    story.append(Paragraph(
        "# Python (src/etl_us_accidents.py) — Normalización temporal y depuración &lt;= 24h<br/>"
        "audit['dotted_timestamps_fixed'] += int(st_str.str.contains('.', regex=False).sum())<br/>"
        "start_dt = pd.to_datetime(st_str.str.slice(0, 19), format='%Y-%m-%d %H:%M:%S')<br/>"
        "dur_clean = dur_raw.mask(dur_raw &gt; 1440.0, np.nan)<br/><br/>"
        "-- SQL (sql/queries_analisis.sql) — Tasa demográfica x100k habitantes por estado<br/>"
        "SELECT a.state, d.state_name, COUNT(*) AS total, ROUND(COUNT(*)*100000.0/d.population_2023, 2) AS tasa_100k<br/>"
        "FROM accidents a LEFT JOIN dim_demographics d ON a.state = d.state GROUP BY a.state ORDER BY total DESC;<br/><br/>"
        "// Power Query M (powerbi/power_query_etl.pq) — Cruce demográfico Censo EE.UU.<br/>"
        "JoinDemografia = Table.NestedJoin(ConVehiculo, {'State'}, DemografiaTyped, {'State'}, 'DimDemo', JoinKind.LeftOuter)",
        st_code,
    ))

    # 3. Exploración de datos y 10 requerimientos
    story.append(Paragraph("3. Exploración de Datos y Respuesta a los 10 Requerimientos", st_h1))
    story.append(Paragraph("3.1 Estados, Ciudades y Tasa Demográfica (Requerimiento 1)", st_h2))
    story.append(Paragraph(
        "California lidera el volumen absoluto (1,741,433; 22.53%) seguida de Florida y Texas, mientras Miami (186,768), Houston y Los Ángeles encabezan "
        "las zonas urbanas. Al normalizar por población del Censo 2023, <b>Carolina del Sur (7,119.2 x 100k hab.)</b> y <b>Oregón (4,243.9 x 100k hab.)</b> exhiben las mayores tasas per cápita.",
        st_body,
    ))
    make_table(
        ["Estado", "Nombre", "Región", "Accidentes", "% Nac.", "Población 2023", "Tasa x 100k", "Sev."],
        [[r["state"], r["state_name"], r["region"], fmt_int(r["total_accidentes"]), f"{r['pct_nacional']}%", fmt_int(r["population_2023"]), f"{r['tasa_x_100k_hab']:,.1f}", r["severidad_promedio"]] for _, r in dfs["states"].head(10).iterrows()],
        col_widths=[42, 86, 56, 68, 44, 78, 62, 75],
    )
    add_figure(os.path.join(CHARTS_DIR, "01_top10_estados_y_ciudades.png"), "Figura 1. Top 10 estados y ciudades urbanas con mayor siniestralidad (Python).")
    add_figure(os.path.join(CHARTS_DIR, "02_demografia_tasa_y_regiones.png"), "Figura 2. Tasa demográfica por cada 100,000 habitantes y distribución regional.")

    story.append(Paragraph("3.2 Hora del Día y Días de la Semana Críticos (Requerimientos 2 y 6)", st_h2))
    story.append(Paragraph(
        "El patrón horario es bimodal laboral con pico máximo a las <b>07:00h (587,472 eventos)</b> y congestión vespertina sostenida entre 15:00 y 17:59h. "
        "Por día, el <b>Viernes (1,366,499; 17.68%)</b> lidera el volumen; los fines de semana suman 1,231,427 (15.93%) pero elevan la severidad media a 2.259 en domingo.",
        st_body,
    ))
    make_table(
        ["Día", "Tipo de Día", "Total Accidentes", "% Total", "Severidad Media"],
        [[r["day_name"], r["tipo_dia"], fmt_int(r["total_accidentes"]), f"{r['pct_total']}%", r["severidad_promedio"]] for _, r in dfs["day"].iterrows()],
        col_widths=[90, 110, 110, 95, 106],
    )
    add_figure(os.path.join(CHARTS_DIR, "03_patron_horario_y_semanal.png"), "Figura 3. Curva horaria bimodal y frecuencia por día de la semana.")
    add_figure(os.path.join(CHARTS_DIR, "04_heatmap_dia_hora.png"), "Figura 4. Mapa de calor de intensidad accidental (Día × Hora).")

    story.append(Paragraph("3.3 Severidad y Duración del Incidente (Requerimientos 3 y 7)", st_h2))
    story.append(Paragraph(
        f"Predomina la <b>Severidad 2 (79.67%)</b> seguida por Severidad 3 (16.81%) y Severidad 4 (2.65%). "
        f"La brecha entre media bruta (<b>{summary['media_global_bruta_min']:.1f} min</b>) y mediana (<b>{summary['mediana_global_bruta_min']:.1f} min</b>) confirma sesgo por outliers &gt;24h; "
        f"depurando a &lt;=24h la media es <b>{summary['media_global_depurada_min']:.1f} min</b> (máximo en Severidad 4: 185.9 min).",
        st_body,
    ))
    make_table(
        ["Sev.", "Total Accidentes", "% Total", "Dist. (mi)", "Media Bruta (min)", "Media Depurada (min)", "Mediana Dep. (min)"],
        [[int(r["severity"]), fmt_int(r["total_accidentes"]), f"{r['pct_total']}%", r["distancia_media_mi"], r["duracion_media_bruta_min"], r["duracion_media_depurada_min"], r["mediana_depurada_min"]] for _, r in dfs["sev"].iterrows()],
        col_widths=[36, 95, 55, 62, 85, 92, 86],
    )
    add_figure(os.path.join(CHARTS_DIR, "05_severidad_y_duracion.png"), "Figura 5. Distribución por severidad y contraste entre duración bruta, depurada y mediana.")

    story.append(Paragraph("3.4 Condiciones Climáticas (Requerimiento 4)", st_h2))
    make_table(
        ["Grupo Climático", "Total Accidentes", "% Total", "% Graves (Sev 3–4)", "Visibilidad (mi)", "Temp. (°F)"],
        [[r["weather_group"], fmt_int(r["total_accidentes"]), f"{r['pct_total']}%", f"{r['pct_graves']}%", r["visibilidad_media_mi"], r["temperatura_media_f"]] for _, r in dfs["weather"].iterrows()],
        col_widths=[100, 95, 65, 95, 80, 76],
    )
    add_figure(os.path.join(CHARTS_DIR, "06_clima_y_severidad.png"), "Figura 6. Frecuencia climática y proporción de severidad 1–4.")

    story.append(Paragraph("3.5 Tipos de Vía Más Peligrosos y Tendencias Temporales (Requerimientos 5 y 8)", st_h2))
    story.append(Paragraph(
        "Las <b>Autopistas / Interstates</b> concentran el <b>32.44% de eventos graves</b> (frente a 10.17% en calles urbanas), liderando el ranking real de vías I-95 N (78,430), "
        "I-95 S (74,528) e I-5 N (71,968). En tendencia anual, el volumen creció desde 2016 (410,821) hasta el pico histórico en <b>2022 (1,762,452)</b>, "
        "siendo <b>Diciembre (847,343; 10.96%)</b> el mes estacionalmente más crítico.",
        st_body,
    ))
    make_table(
        ["Tipo de Vía", "Total Accidentes", "% Total", "Severidad Media", "% Graves (Sev 3–4)"],
        [[r["road_type"], fmt_int(r["total_accidentes"]), f"{r['pct_total']}%", r["severidad_promedio"], f"{r['pct_graves']}%"] for _, r in dfs["road"].iterrows()],
        col_widths=[140, 100, 75, 95, 101],
    )
    add_figure(os.path.join(CHARTS_DIR, "07_tipos_via_y_top10_calles.png"), "Figura 7. Gravedad por tipo de vía y Top 10 vías específicas reales.")
    add_figure(os.path.join(CHARTS_DIR, "08_tendencias_anuales_y_mensuales.png"), "Figura 8. Evolución interanual 2016–2023 y estacionalidad mensual.")

    story.append(Paragraph("3.6 Tipo de Vehículo, Geoespacialidad y Correlación (Requerimientos 9 y 10)", st_h2))
    story.append(Paragraph(
        f"Sobre {fmt_int(dfs['veh_k']['total_accidentes'].sum())} menciones explícitas depuradas en <i>Description</i> (~0.88% del total; ~99.1% omiten el vehículo), "
        "<b>Automóvil / Multivehículo (45,195; 43.02% graves)</b> y <b>Camión / Tráiler (16,389; mayor severidad promedio = 2.521, 124.95 min)</b> dominan impacto y frecuencia.",
        st_body,
    ))
    make_table(
        ["Tipo de Vehículo (NLP)", "Accidentes", "% Identif.", "Sev. Prom.", "% Graves", "Dur. Media (min)"],
        [[r["vehicle_type"], fmt_int(r["total_accidentes"]), f"{r['pct_identificados']}%", r["severidad_promedio"], f"{r['pct_graves']}%", r["duracion_media_min"]] for _, r in dfs["veh_k"].iterrows()],
        col_widths=[145, 72, 68, 70, 70, 86],
    )
    add_figure(os.path.join(CHARTS_DIR, "09_tipos_de_vehiculo.png"), "Figura 9. Accidentes y severidad grave por tipo de vehículo identificado.")
    add_figure(os.path.join(CHARTS_DIR, "10_distribucion_geoespacial_hotspots.png"), "Figura 10. Densidad nacional y Top 300 hotspots críticos.")
    add_figure(os.path.join(CHARTS_DIR, "14_matriz_correlacion_exploratoria.png"), "Figura 11. Matriz de correlación exploratoria.")

    # 4. Visualizaciones Power BI
    story.append(Paragraph("4. Visualizaciones de Power BI y Auditoría del Tablero", st_h1))
    story.append(Paragraph(
        "El tablero finalizado en Power BI Desktop (<b>powerbi/dashboard_powerbi.html</b>) consolida 8 vistas interactivas, auditadas frente a Python y SQL:",
        st_body,
    ))
    for fname, cap in [
        ("01_frecuencia_estado_top10_ciudades.jpg", "Power BI Vista 1: Mapa estatal y Top 10 ciudades (Miami 186,768 líder)."),
        ("02_kpis_hora_dia_semana.jpg", "Power BI Vista 2: KPIs, patrón horario bimodal y semana (Viernes 1,366K; Sáb+Dom real = 1,231,427)."),
        ("03_severidad_clima_porcentaje.jpg", "Power BI Vista 3: Anillo de severidad (7728K) y barras 100% por clima."),
        ("04_accidentes_clima_estado.jpg", "Power BI Vista 4: Frecuencia climática exacta y tooltip estatal."),
        ("05_top10_vias_peligrosas.png", "Power BI Vista 5: Visual BI con orden alfabético descendente Zuni Rd SE (corregido en Python/SQL)."),
        ("06_duracion_promedio_severidad.png", "Power BI Vista 6: Duración media (444 min) vs mediana (75 min)."),
        ("07_tendencias_anuales_mensuales_mom.png", "Power BI Vista 7: Tendencias y Var MoM % (detección de fechas Blank por nanosegundos)."),
        ("08_mapa_geoespacial_severidad.jpg", "Power BI Vista 8: Mapa geoespacial por severidad 1–4."),
    ]:
        add_figure(os.path.join(PBI_DIR, fname), cap, max_w=465, max_h=245)

    # 5. Medidas DAX Explicadas
    story.append(Paragraph("5. Medidas DAX Explicadas", st_h1))
    make_table(
        ["Medida DAX", "Fórmula", "Explicación Funcional"],
        [
            ["Total Accidentes", "COUNTROWS(Accidents)", "Conteo base aditivo sensible a todos los filtros activos (7,728,394 / 8M)."],
            ["Accidentes FinDeSemana", "CALCULATE([Total Accidentes], WEEKDAY(Accidents[Start_Time], 2) IN {6, 7})", "Aísla sábados y domingos (1,231,427 reales; 15.93% del dataset)."],
            ["Accidentes YTD", "TOTALYTD([Total Accidentes], Dim_Calendario[Date])", "Acumulado anual hasta la fecha máxima del contexto activo (marzo 2023)."],
            ["Var MoM %", "DIVIDE([Total Accidentes] - [Acc. Mes Ant.], [Acc. Mes Ant.], 0)", "Variación porcentual mes a mes con DATEADD(..., -1, MONTH)."],
            ["Duración Prom. / Mediana", "AVERAGE(Accidents[Duracion_Min]) / MEDIAN(...)", "Contrasta sesgo por outliers >24h (444 min vs 75 min)."],
            ["Tasa x 100k Hab", "DIVIDE([Total Accidentes]*100000, MAX(Dim_Demo[Pop_2023]), 0)", "Normalización poblacional por estado frente al Censo EE.UU. 2023."],
        ],
        col_widths=[108, 200, 203],
    )

    # 6. Resultados ANOVA
    story.append(Paragraph("6. Resultados y Visualización del ANOVA", st_h1))
    story.append(Paragraph(
        f"Se ejecutaron 4 modelos ANOVA exactos sobre el universo completo depurado, complementados con <b>Welch ANOVA</b>, "
        f"prueba de homogeneidad de varianzas de <b>Levene</b>, verificación no paramétrica <b>Kruskal-Wallis H</b> y contrastes post-hoc <b>Tukey-Kramer HSD</b>. "
        f"En <i>Duración ~ Severidad</i> el tamaño del efecto resultó sustantivo (<b>η<super>2</super> = {s1['eta_cuadrado']:.4f}</b>; F = {s1['F_clasico']:,.2f}; los 6 pares Tukey significativos). "
        f"En el ANOVA factorial <i>Clima × Franja Horaria</i> la interacción resultó altamente significativa (F = 87.58, p &lt; 10<super>-300</super>): "
        "Lluvia agrava más de noche (20–23h: 2.279), mientras Nieve/Hielo alcanza su pico de severidad al mediodía (2.259).",
        st_body,
    ))
    make_table(
        ["Modelo ANOVA", "N Válido", "F Clásico", "p-valor", "Eta²", "F Welch", "Kruskal H"],
        [
            ["1. Duración (≤24h) ~ Severidad", fmt_int(s1["N"]), f"{s1['F_clasico']:,.2f}", "< 1e-300", f"{s1['eta_cuadrado']:.5f}", f"{s1['F_welch']:,.2f}", f"{s1['kruskal_H']:,.1f}"],
            ["2. Severidad ~ Clima", fmt_int(s2["N"]), f"{s2['F_clasico']:,.2f}", "< 1e-300", f"{s2['eta_cuadrado']:.5f}", f"{s2['F_welch']:,.2f}", f"{s2['kruskal_H']:,.1f}"],
            ["3. Severidad ~ Franja Horaria", fmt_int(s3["N"]), f"{s3['F_clasico']:,.2f}", "< 1e-300", f"{s3['eta_cuadrado']:.5f}", f"{s3['F_welch']:,.2f}", f"{s3['kruskal_H']:,.1f}"],
        ],
        col_widths=[145, 65, 65, 52, 54, 65, 65],
    )
    make_table(
        ["Fuente Factorial 2 Vías", "gl", "SS Tipo III", "MS", "F", "p-valor", "Eta Parcial²"],
        [[r["fuente"], fmt_int(r["df"]), f"{r['ss_tipo_iii']:,.2f}", f"{r['ms']:.4f}" if pd.notna(r["ms"]) else "-", f"{r['F']:,.2f}" if pd.notna(r["F"]) else "-", f"{r['p_valor']:.2e}" if pd.notna(r["p_valor"]) else "-", f"{r['eta_parcial_sq']:.6f}" if pd.notna(r["eta_parcial_sq"]) else "-"] for _, r in dfs["anova_2w"].iterrows()],
        col_widths=[160, 52, 78, 52, 55, 56, 58],
    )
    add_figure(os.path.join(CHARTS_DIR, "11_anova_duracion_severidad.png"), "Figura 12. ANOVA Duración depurada según Severidad (IC 95% y boxplots).", max_h=235)
    add_figure(os.path.join(CHARTS_DIR, "12_anova_severidad_clima_franja.png"), "Figura 13. ANOVA Severidad por Clima, Franja e interacción Clima × Franja.", max_h=235)
    add_figure(os.path.join(CHARTS_DIR, "13_anova_tukey_posthoc.png"), "Figura 14. Contrastes múltiples post-hoc Tukey-Kramer HSD.", max_h=235)

    # 7. Conclusiones
    story.append(Paragraph("7. Conclusiones y Recomendaciones", st_h1))
    for c in [
        "<b>Concentración geográfica y enfoque per cápita:</b> California (1.74M), Florida (880K) y Texas (583K) lideran en volumen bruto, pero Carolina del Sur (7,119 x 100k hab.) y Oregón (4,244 x 100k hab.) presentan la mayor incidencia relativa poblacional.",
        "<b>Ventana crítica operativa:</b> Los viernes (17.68%) entre las 15:00 y 18:00h sobre autopistas interestatales (I-95, I-5, I-10; 32.44% de eventos graves) concentran la máxima prioridad de gestión de tránsito.",
        "<b>Impacto climático e interacción horaria:</b> Lluvia (22.76% graves) y nieve/hielo (19.95% graves) incrementan significativamente la severidad promedio (p &lt; 10<super>-300</super>), interactuando con horarios nocturnos y diurnos.",
        "<b>Gobernanza analítica e higiene de datos:</b> La integración Python + SQL + Power BI corrigió fechas con nanosegundos, aisló outliers de duración &gt;24h (explicando media 444 vs mediana 75 min), resolvió el orden Top 10 real de vías y depuró falsos positivos de vehículos.",
    ]:
        story.append(Paragraph(f"• {c}", st_bullet))

    doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    print(f"[OK] PDF generado (ReportLab): {pdf_path}")


def build_pptx_and_script(audit, summary, anova, dfs):
    prs = Presentation()
    prs.slide_width = PptxInches(13.333)
    prs.slide_height = PptxInches(7.5)
    blank_layout = prs.slide_layouts[6]

    def fit_picture(slide, img_path, box_left, box_top, max_w, max_h):
        png_buf, w_px, h_px = image_to_png_stream(img_path)
        scale = min(max_w / float(w_px), max_h / float(h_px))
        w_in = w_px * scale
        h_in = h_px * scale
        left_in = box_left + (max_w - w_in) / 2.0
        top_in = box_top + (max_h - h_in) / 2.0
        slide.shapes.add_picture(png_buf, PptxInches(left_in), PptxInches(top_in), width=PptxInches(w_in), height=PptxInches(h_in))

    def add_slide(title_txt, subtitle_txt=None, bullets=None, img_path=None, notes=""):
        slide = prs.slides.add_slide(blank_layout)
        bg = slide.shapes.add_shape(1, PptxInches(0), PptxInches(0), PptxInches(13.333), PptxInches(1.1))
        bg.fill.solid()
        bg.fill.fore_color.rgb = PptxRGB(15, 23, 42)
        bg.line.fill.background()

        tb = slide.shapes.add_textbox(PptxInches(0.5), PptxInches(0.16), PptxInches(12.3), PptxInches(0.85))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title_txt
        p.font.size = PptxPt(23)
        p.font.bold = True
        p.font.color.rgb = PptxRGB(255, 255, 255)
        if subtitle_txt:
            p2 = tf.add_paragraph()
            p2.text = subtitle_txt
            p2.font.size = PptxPt(12.5)
            p2.font.color.rgb = PptxRGB(148, 163, 184)

        if bullets and img_path and os.path.exists(img_path):
            btb = slide.shapes.add_textbox(PptxInches(0.45), PptxInches(1.32), PptxInches(4.55), PptxInches(5.85))
            btf = btb.text_frame
            btf.word_wrap = True
            for idx, b in enumerate(bullets):
                bp = btf.paragraphs[0] if idx == 0 else btf.add_paragraph()
                bp.text = f"• {b}"
                bp.font.size = PptxPt(14)
                bp.space_after = PptxPt(10)
            fit_picture(slide, img_path, box_left=5.15, box_top=1.28, max_w=7.85, max_h=5.95)
        elif img_path and os.path.exists(img_path):
            fit_picture(slide, img_path, box_left=0.6, box_top=1.25, max_w=12.1, max_h=6.0)
        elif bullets:
            btb = slide.shapes.add_textbox(PptxInches(0.7), PptxInches(1.45), PptxInches(11.9), PptxInches(5.5))
            btf = btb.text_frame
            btf.word_wrap = True
            for idx, b in enumerate(bullets):
                bp = btf.paragraphs[0] if idx == 0 else btf.add_paragraph()
                bp.text = f"• {b}"
                bp.font.size = PptxPt(17.5)
                bp.space_after = PptxPt(14)

        if notes:
            slide.notes_slide.notes_text_frame.text = notes

    s1 = anova["anova_duracion_severidad"]
    s2 = anova["anova_severidad_clima"]
    top_st = dfs["states"].iloc[0]
    top_ct = dfs["cities"].iloc[0]
    top_rate = dfs["states"].sort_values("tasa_x_100k_hab", ascending=False).iloc[0]
    peak_hr = max(summary["por_hora"], key=lambda x: x["total_accidentes"])
    peak_dy = max(summary["por_dia"], key=lambda x: x["total_accidentes"])

    # 1. Portada
    add_slide(
        "Proyecto 3: Análisis de Accidentes de Tránsito en Zonas Urbanas",
        f"Dataset Kaggle US Accidents ({fmt_int(audit['total_raw_rows'])} registros, 2016–2023) + Censo Demográfico EE.UU.",
        bullets=[
            "Objetivo: Integrar datos abiertos de siniestralidad vial con variables climáticas, viales y demográficas.",
            "Stack Tecnológico: Python (Pandas, PyArrow, SciPy, Matplotlib/Seaborn), PySpark, SQLite, Power Query M y Power BI (DAX).",
            "Entregables: Pipeline ETL reproducible, 10 respuestas SQL/Python, tablero Power BI HTML, Informe PDF/Word y análisis ANOVA."
        ],
        notes="Buenos días/tardes. Presentamos el Proyecto 3 enfocado en el análisis de más de 7.7 millones de accidentes de tránsito en EE.UU."
    )

    # 2. ETL
    add_slide(
        "Arquitectura ETL y Calidad de Datos",
        "Procesamiento por bloques en Python/PyArrow, PySpark, SQLite y Power Query M",
        bullets=[
            f"Extracción: {fmt_int(audit['total_raw_rows'])} filas (3.06 GB) + Censo EE.UU. 2023 (50 estados + D.C.).",
            f"Limpieza temporal: {fmt_int(audit['dotted_timestamps_fixed'])} timestamps con nanosegundos (.000000000) normalizados.",
            f"Control de outliers: {fmt_int(audit['outliers_gt_24h'])} cierres >24h aislados en duration_clean_min.",
            "NLP RE2 sobre Description para tipo de vehículo filtrando falsos positivos ('I-80 Bus', 'Van Ness Ave')."
        ],
        notes="Explicar cómo resolvimos el reto de memoria con streaming de 500k registros y las decisiones clave de limpieza."
    )

    # 3. Req 1 Estados y Ciudades
    add_slide(
        "Req. 1: Frecuencia por Estado y Ciudad Urbana",
        "Líderes en volumen absoluto de accidentalidad (2016–2023)",
        bullets=[
            f"Estado #1 en volumen: {top_st['state_name']} ({fmt_int(top_st['total_accidentes'])}, {top_st['pct_nacional']}%).",
            "Florida (880K) y Texas (583K) completan el podio nacional.",
            f"Ciudad #1 urbana: {top_ct['city']}, {top_ct['state']} ({fmt_int(top_ct['total_accidentes'])}).",
            "Houston (169K) y Los Ángeles (156K) ocupan el segundo y tercer lugar urbano."
        ],
        img_path=os.path.join(CHARTS_DIR, "01_top10_estados_y_ciudades.png"),
        notes="Destacar el ranking por estado y por ciudad urbana y su coincidencia con el primer tablero de Power BI."
    )

    # 4. Demografía
    add_slide(
        "Enriquecimiento Demográfico: Tasa x 100k Habitantes",
        "Integración con población oficial del Censo de Estados Unidos 2023",
        bullets=[
            "El cruce demográfico corrige el sesgo de tamaño poblacional estatal.",
            f"Líder demográfico per cápita: {top_rate['state_name']} ({top_rate['tasa_x_100k_hab']:,.0f} x 100k hab.), seguida de CA y OR.",
            "La región Sur concentra el 44.19% de todos los incidentes nacionales."
        ],
        img_path=os.path.join(CHARTS_DIR, "02_demografia_tasa_y_regiones.png"),
        notes="Mostrar la gráfica de tasas por cada 100,000 habitantes y distribución por región censal."
    )

    # 5. Req 2 & 6 Horarios y Días
    add_slide(
        "Req. 2 y 6: Hora del Día y Días de la Semana Críticos",
        "Comportamiento bimodal laboral vs fin de semana",
        bullets=[
            f"Hora crítica nacional: {int(peak_hr['hour']):02d}:00h ({fmt_int(peak_hr['total_accidentes'])} eventos).",
            "Doble pico laboral: mañana (07–09h) y tarde (15–18h).",
            f"Día con más accidentes: {peak_dy['day_name']} ({fmt_int(peak_dy['total_accidentes'])}, {peak_dy['pct_total']}%).",
            "Fin de semana cae en volumen (15.9%), pero sube la severidad media (2.259 en domingo)."
        ],
        img_path=os.path.join(CHARTS_DIR, "03_patron_horario_y_semanal.png"),
        notes="Explicar cómo la congestión vespertina del viernes dispara la accidentalidad."
    )

    # 6. Req 3 & 7 Severidad y Duración
    add_slide(
        "Req. 3 y 7: Severidad y Duración del Incidente",
        "Impacto de outliers extremos: Media Bruta vs Mediana y Serie Depurada",
        bullets=[
            "Severidad 2 concentra el 79.67% de eventos; Severidad 3–4 representa 19.46%.",
            f"Media bruta global: {summary['media_global_bruta_min']:.1f} min vs Mediana: {summary['mediana_global_bruta_min']:.1f} min.",
            f"Media depurada (≤24h): {summary['media_global_depurada_min']:.1f} min (máx. en Sev 4: 185.9 min; Sev 3: 67.8 min)."
        ],
        img_path=os.path.join(CHARTS_DIR, "05_severidad_y_duracion.png"),
        notes="Enfatizar por qué usar la mediana (75 min) junto a la media depurada en reportes ejecutivos."
    )

    # 7. Req 4 Clima
    add_slide(
        "Req. 4: Relación con Condiciones Climáticas",
        "Exposición en clima despejado vs mayor gravedad bajo lluvia/nieve",
        bullets=[
            "Despejado (44.1%) y Nublado (40.9%) suman 85% por exposición vehicular diaria.",
            "Lluvia (22.76% graves) y Nieve/Hielo (19.95% graves) elevan la severidad frente a Despejado (16.91%).",
            "La visibilidad promedio cae de 9.85 mi a 2.85 mi bajo nieve/hielo."
        ],
        img_path=os.path.join(CHARTS_DIR, "06_clima_y_severidad.png"),
        notes="Contrastar frecuencia absoluta frente a tasa condicional de gravedad."
    )

    # 8. Req 5 Vías Peligrosas
    add_slide(
        "Req. 5: Tipos de Vía Más Peligrosos y Top 10 Calles",
        "Autopistas interestatales vs arterias urbanas y corrección BI",
        bullets=[
            "Autopistas / Interstates registran 32.44% de accidentes graves (vs 10.17% en calles urbanas).",
            "Top 10 vías reales: I-95 N (78,430), I-95 S (74,528), I-5 N (71,968) e I-10 E.",
            "Python/SQL corrigió el orden alfabético descendente del visual Power BI (Zuni Rd SE)."
        ],
        img_path=os.path.join(CHARTS_DIR, "07_tipos_via_y_top10_calles.png"),
        notes="Mencionar cómo el análisis Python/SQL corrigió el orden alfabético del gráfico Top 10 de Power BI."
    )

    # 9. Req 8 Tendencias Anuales y Mensuales
    add_slide(
        "Req. 8: Tendencias Anuales y Estacionalidad Mensual",
        "Crecimiento histórico 2016–2022 y pico estacional invernal",
        bullets=[
            "Crecimiento continuo de 410K (2016) hasta el récord histórico en 2022 (1,762,452).",
            "La severidad media cayó de 2.389 (2017) a 2.072 (2022) por mayor captura de eventos leves.",
            "Diciembre lidera la estacionalidad mensual (847,343; 10.96%), seguido de noviembre y enero."
        ],
        img_path=os.path.join(CHARTS_DIR, "08_tendencias_anuales_y_mensuales.png"),
        notes="Explicar la tendencia creciente hasta 2022, la cobertura parcial Q1 2023 y el pico del último trimestre."
    )

    # 10. Req 9 Vehículos
    add_slide(
        "Req. 9: Accidentes por Tipo de Vehículo Involucrado",
        "Extracción NLP sobre Description excluyendo toponimias viales",
        bullets=[
            "68,252 menciones vehiculares válidas extraídas tras excluir falsos positivos.",
            "Automóvil/Multivehículo (45,195; 43.0% graves) y Camión/Tráiler (16,389; mayor sev. media 2.521).",
            "Peatones (2,559), Autobuses (1,502) y Motocicletas (1,136; 14.9% graves) siguen en frecuencia."
        ],
        img_path=os.path.join(CHARTS_DIR, "09_tipos_de_vehiculo.png"),
        notes="Comentar con transparencia que ~99% de descripciones no nombran vehículo, y analizar el patrón en las 68K válidas."
    )

    # 11. Req 10 Geoespacial
    add_slide(
        "Req. 10: Distribución Geoespacial de Puntos Críticos",
        "Cuadrículas de densidad 0.1° × 0.1° y Top 300 hotspots críticos",
        bullets=[
            "Clústeres urbanos dominantes: Sur de California, Miami–Orlando, Houston–Dallas y corredor Noreste.",
            "Infraestructura crítica: 1.14M de incidentes cerca de semáforos y 874K en cruces peatonales.",
            "Permite georreferenciar cámaras y patrullaje preventivo en cuadrantes de máxima densidad."
        ],
        img_path=os.path.join(CHARTS_DIR, "10_distribucion_geoespacial_hotspots.png"),
        notes="Mostrar la concentración espacial de hotspots y su utilidad para planeación urbana."
    )

    # 12. Power BI & DAX
    add_slide(
        "Tablero Power BI y Medidas DAX",
        "8 vistas finalizadas, despliegue HTML interactivo y validación cruzada",
        bullets=[
            "Despliegue web completo en powerbi/dashboard_powerbi.html.",
            "DAX documentado: COUNTROWS, CALCULATE, TOTALYTD, DATEADD (MoM %), AVERAGE, MEDIAN.",
            "Auditoría transparente de slicers YTD, fechas con nanosegundos y ranking Top 10."
        ],
        img_path=os.path.join(PBI_DIR, "02_kpis_hora_dia_semana.jpg"),
        notes="Mostrar la interfaz Power BI terminada y explicar cómo DAX permite explorar dinámicamente."
    )

    # 13. ANOVA 1 Duración ~ Severidad
    add_slide(
        "ANOVA Unifactorial: Duración ~ Severidad",
        f"Validación paramétrica y no paramétrica sobre N = {fmt_int(s1['N'])} eventos",
        bullets=[
            f"F = {s1['F_clasico']:,.2f}, p < 1e-300, tamaño del efecto η² = {s1['eta_cuadrado']:.4f}.",
            f"Welch F = {s1['F_welch']:,.1f} y Kruskal-Wallis H = {s1['kruskal_H']:,.1f} confirman robustez.",
            "Todos los 6 pares en Tukey-Kramer HSD son significativos (Sev 4 = 185.9 min vs Sev 1 = 45.7 min)."
        ],
        img_path=os.path.join(CHARTS_DIR, "11_anova_duracion_severidad.png"),
        notes="Explicar que aquí el tamaño del efecto η² = 3.28% sí es sustantivo en minutos de cierre vial."
    )

    # 14. ANOVA Factorial & Tukey
    add_slide(
        "ANOVA Factorial: Severidad ~ Clima × Franja Horaria",
        f"Efecto clima F = {s2['F_clasico']:,.1f} e interacción significativa (F = 87.58, p < 1e-300)",
        bullets=[
            "Lluvia y Nieve/Hielo elevan la severidad media frente a Despejado y Niebla.",
            "Interacción cruzada: Lluvia y Nublado agravan más de noche (20–23h: 2.279).",
            "Nieve/Hielo presenta su mayor gravedad media al mediodía (2.259) por flujo diurno bajo tormenta."
        ],
        img_path=os.path.join(CHARTS_DIR, "12_anova_severidad_clima_franja.png"),
        notes="Resaltar la interacción cruzada mostrada en el panel derecho del gráfico ANOVA factorial."
    )

    # 15. Conclusiones
    add_slide(
        "Conclusiones y Recomendaciones Estratégicas",
        "Aportes para gestión de movilidad urbana y seguridad vial",
        bullets=[
            "Focalizar operativos de control y respuesta rápida los viernes entre 15:00 y 18:00h en autopistas interestatales.",
            "Activar señalización dinámica de velocidad ante lluvia en horarios nocturnos (20–23h) y nevadas diurnas.",
            "Adoptar mediana (75 min) + depuración de outliers (>24h) e índices por 100k hab. (ej. SC y OR) para planeación.",
            "Repositorio completo reproducible con código Python, PySpark, SQL, Power Query M, HTML, PDF, Word y PPTX."
        ],
        notes="Cerrar agradeciendo y abriendo espacio para preguntas del jurado o profesor."
    )

    pptx_path = os.path.join(DOCS_DIR, "presentacion_oral.pptx")
    prs.save(pptx_path)
    print(f"[OK] PowerPoint generado: {pptx_path}")

    guion = f"""# Guion para Presentación Oral — Proyecto 3 (15 diapositivas · Duración: 10–12 minutos)

## Diapositiva 1 · Portada y Contexto (0:40 min)
> *"Buenos días/tardes. Hoy presentamos el Proyecto 3: Análisis de Accidentes de Tránsito en Zonas Urbanas, integrando el dataset abierto de Kaggle US Accidents con {fmt_int(audit['total_raw_rows'])} registros (2016–2023) y datos demográficos del Censo EE.UU. 2023 mediante Python, PySpark, SQL, Power Query, Power BI y ANOVA."*

## Diapositiva 2 · Arquitectura ETL y Calidad de Datos (1:00 min)
> *"El primer reto fue el tamaño del CSV (~3.06 GB). Construimos un ETL por bloques de 500k filas en Python/PyArrow y su equivalente en PySpark y Power Query M. Corregimos {fmt_int(audit['dotted_timestamps_fixed'])} fechas con nanosegundos (.000000000), aislamos {fmt_int(audit['outliers_gt_24h'])} cierres atípicos mayores a 24 horas y filtramos falsos positivos toponímicos ('I-80 Bus', 'Van Ness Ave') al extraer tipos de vehículo."*

## Diapositivas 3 y 4 · Estados, Ciudades y Tasa Demográfica (1:20 min)
> *"En el Requerimiento 1, California ({fmt_int(top_st['total_accidentes'])} accidentes) y Miami ({fmt_int(top_ct['total_accidentes'])}) lideran en volumen bruto. Sin embargo, al normalizar por población del Censo, {top_rate['state_name']} ({top_rate['tasa_x_100k_hab']:,.0f} x 100k hab.) y Oregón muestran mayor riesgo relativo per cápita."*

## Diapositiva 5 · Patrones Horarios y Semanales (0:45 min)
> *"Para los Requerimientos 2 y 6, se observa una curva bimodal laboral con pico a las {int(peak_hr['hour']):02d}:00h y liderazgo del día {peak_dy['day_name']} ({peak_dy['pct_total']}%). En fin de semana cae el volumen (15.9%), pero aumenta la severidad promedio."*

## Diapositiva 6 · Severidad y Duración (0:50 min)
> *"En Severidad (Req. 3) domina el Nivel 2 con 79.67%. En Duración (Req. 7) explicamos por qué Power BI muestra media de 444 minutos vs mediana de 75 minutos: los cierres de varios días sesgan la media. Al depurar a <=24h, la media baja a 108 minutos, con máximo de 185.9 minutos en Severidad 4."*

## Diapositiva 7 · Clima y Severidad (0:40 min)
> *"En el Requerimiento 4, aunque el 85% de eventos ocurre con cielo despejado o nublado por mayor tráfico diario, la lluvia (22.76% graves) y la nieve/hielo (19.95% graves) elevan la severidad mientras la visibilidad cae por debajo de 3 millas en nieve/niebla."*

## Diapositiva 8 · Vías Peligrosas y Corrección Top 10 (0:45 min)
> *"En el Requerimiento 5, las autopistas interestatales concentran 32.44% de eventos graves frente a 10.17% en calles urbanas. El ranking real por volumen está encabezado por I-95 N, I-95 S e I-5 N, corrigiendo el orden alfabético descendente que mostraba una captura en Power BI."*

## Diapositivas 9 y 10 · Tendencias y Vehículos (1:10 min)
> *"En el Requerimiento 8 vimos crecimiento hasta el pico histórico de 2022 (1.76M) y pico estacional en diciembre (10.96%). En el Requerimiento 9 identificamos 68,252 menciones vehiculares en las descripciones: Automóvil/Multivehículo y Camión/Tráiler presentan la mayor gravedad (~40–43% graves y 125 min en camiones)."*

## Diapositivas 11 y 12 · Hotspots Geoespaciales y Power BI/DAX (1:10 min)
> *"En el Requerimiento 10 los clústeres de densidad 0.1° confirman focos críticos en California, Florida, Texas y el Noreste, con alta incidencia en semáforos e intersecciones. Todo esto se complementa con nuestro tablero Power BI finalizado, desplegado en HTML con todas sus medidas DAX explicadas."*

## Diapositivas 13 y 14 · Resultados ANOVA (1:15 min)
> *"Validamos nuestras hipótesis mediante ANOVA sobre millones de registros: la duración varía sustantivamente según severidad (F={s1['F_clasico']:,.1f}, η²={s1['eta_cuadrado']:.4f}, Tukey significativo en los 6 pares) y el ANOVA factorial Clima × Franja confirma una interacción significativa (F=87.58): la lluvia agrava más de noche (2.279) mientras la nieve impacta más al mediodía (2.259)."*

## Diapositiva 15 · Conclusiones (0:40 min)
> *"En conclusión, integrar datos abiertos con demografía, ETL auditado, SQL, Python, Power BI y ANOVA permite focalizar operativos viales los viernes por la tarde en autopistas interestatales y activar alertas dinámicas según clima y horario. Muchas gracias."*
"""
    guion_path = os.path.join(DOCS_DIR, "guion_presentacion_oral.md")
    with open(guion_path, "w", encoding="utf-8") as f:
        f.write(guion)
    print(f"[OK] Guion oral generado: {guion_path}")


def build_readme(audit, summary, anova, dfs):
    s1 = anova["anova_duracion_severidad"]
    s2 = anova["anova_severidad_clima"]
    s3 = anova["anova_severidad_franja"]
    aud = summary["auditoria"]
    top_st = dfs["states"].head(5)
    top_rate = dfs["states"].sort_values("tasa_x_100k_hab", ascending=False).head(3)
    top_ct = dfs["cities"].head(5)
    top_str = dfs["streets"].head(3)
    peak_hr = max(summary["por_hora"], key=lambda x: x["total_accidentes"])
    peak_dy = max(summary["por_dia"], key=lambda x: x["total_accidentes"])
    peak_yr = max(summary["anual"], key=lambda x: x["total_accidentes"])
    peak_mo = max(summary["mensual"], key=lambda x: x["total_accidentes"])

    readme = f"""# 🚦 Proyecto 3: Análisis de Accidentes de Tránsito en Zonas Urbanas (EE.UU., 2016–2023)

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](src/etl_us_accidents.py)
[![PySpark](https://img.shields.io/badge/PySpark-4.2-E25A1C?logo=apachespark&logoColor=white)](src/etl_pyspark.py)
[![SQLite](https://img.shields.io/badge/SQL-SQLite3-003B57?logo=sqlite&logoColor=white)](sql/queries_analisis.sql)
[![Power BI](https://img.shields.io/badge/Power%20BI-DAX%20%26%20M-F2C811?logo=powerbi&logoColor=black)](powerbi/dashboard_powerbi.html)
[![ANOVA](https://img.shields.io/badge/Stats-ANOVA%20%26%20Tukey-16A34A)](src/anova_analysis.py)

Análisis integral de **{fmt_int(audit['total_raw_rows'])} registros** de accidentes de tránsito en Estados Unidos ([Kaggle US Accidents](https://www.kaggle.com/datasets/sobhanmoosavi/us-accidents)) integrados con variables climáticas, de infraestructura vial y **datos demográficos del Censo de EE.UU. 2023**. Incluye pipeline ETL reproducible (Python/PyArrow, PySpark, SQL y Power Query M), dashboard Power BI desplegado en HTML, pruebas estadísticas ANOVA y todos los entregables documentales.

---

## 📁 Estructura del Repositorio

```text
├── assets/
│   ├── charts/                  # 14 gráficas analíticas y ANOVA generadas en Python (300 DPI)
│   └── powerbi/                 # 8 capturas del tablero finalizado en Power BI Desktop
├── data/
│   └── us_state_demographics.csv # Tabla demográfica Censo EE.UU. 2023 (población, área, densidad)
├── docs/
│   ├── informe_tecnico.md       # Informe técnico completo en Markdown
│   ├── informe_tecnico.html     # Versión web imprimible del informe técnico
│   ├── informe_tecnico.pdf      # Entregable 1 en PDF
│   ├── informe_tecnico.docx     # Entregable 1 en Word
│   ├── presentacion_oral.pptx   # Entregable 4: Diapositivas ejecutivas (15 slides)
│   └── guion_presentacion_oral.md # Guion detallado cronometrado para exposición oral
├── powerbi/
│   ├── dashboard_powerbi.html   # Entregable 2: Portal HTML interactivo del tablero Power BI
│   ├── power_query_etl.pq       # Entregable 3: Código Power Query (Lenguaje M) documentado
│   └── dax_measures.md          # Catálogo y explicación de medidas DAX
├── resultados/                  # Tablas CSV y resúmenes JSON exportados desde SQL y ANOVA
├── sql/
│   └── queries_analisis.sql     # Entregable 3: Consultas SQL completas para los 10 requerimientos
├── src/
│   ├── etl_us_accidents.py      # Pipeline ETL principal (Streaming Pandas + PyArrow + SQLite)
│   ├── etl_pyspark.py           # Pipeline ETL alternativo distribuido en PySpark / Spark SQL
│   ├── analysis_sql_and_charts.py # Ejecución SQL + generación de las gráficas en Python
│   ├── anova_analysis.py        # ANOVA Unifactorial, Factorial 2 Vías, Kruskal-Wallis y Tukey HSD
│   └── generate_deliverables.py # Generador automático de PDF, Word, PPTX, HTML y README
├── index.html                   # Portal HTML raíz de navegación de entregables
└── requirements.txt
```

---

## 📊 Resumen Ejecutivo y Auditoría ETL

| Indicador Clave | Resultado Real (Python + SQL) |
|---|---|
| **Total de registros procesados** | **{fmt_int(audit['total_raw_rows'])}** ({aud['estados_cubiertos']} estados + D.C., {fmt_int(aud['ciudades_cubiertas'])} ciudades) |
| **Período temporal cubierto** | `{aud['fecha_inicio']}` → `{aud['fecha_fin']}` ({fmt_int(audit['dotted_timestamps_fixed'])} timestamps con nanosegundos corregidos) |
| **Estado #1 (Volumen) / #1 (Tasa x 100k hab.)** | **{top_st.iloc[0]['state_name']}** ({fmt_int(top_st.iloc[0]['total_accidentes'])}) / **{top_rate.iloc[0]['state_name']}** ({top_rate.iloc[0]['tasa_x_100k_hab']:,.1f}) |
| **Ciudad urbana #1** | **{top_ct.iloc[0]['city']}, {top_ct.iloc[0]['state']}** ({fmt_int(top_ct.iloc[0]['total_accidentes'])}) |
| **Severidad dominante** | **Nivel 2 (79.67%)** · Eventos graves (Sev 3–4): **19.46%** |
| **Duración Media Bruta / Depurada (≤24h) / Mediana** | **{summary['media_global_bruta_min']:.1f} min** / **{summary['media_global_depurada_min']:.1f} min** / **{summary['mediana_global_bruta_min']:.1f} min** |
| **ANOVA Duración ~ Severidad** | **F = {s1['F_clasico']:,.2f}**, *p* < 1e-300, η² = {s1['eta_cuadrado']:.4f} |
| **ANOVA Severidad ~ Clima** | **F = {s2['F_clasico']:,.2f}**, *p* < 1e-300 (interacción Clima × Franja: F = 87.58) |
| **ANOVA Severidad ~ Franja Horaria** | **F = {s3['F_clasico']:,.2f}**, *p* < 1e-300 |

---

## 📈 Respuestas Analíticas y Gráficas de Python (10 Requerimientos + EDA + ANOVA)

### 1. Frecuencia por Estado, Ciudad y Tasa Demográfica (Req. 1)
- **Volumen estatal:** **California** (`{fmt_int(top_st.iloc[0]['total_accidentes'])}`, `22.53%`), **Florida** (`880,192`, `11.39%`) y **Texas** (`582,837`, `7.54%`) encabezan la carga absoluta.
- **Ciudades críticas:** **Miami, FL** (`{fmt_int(top_ct.iloc[0]['total_accidentes'])}`), **Houston, TX** (`{fmt_int(top_ct.iloc[1]['total_accidentes'])}`) y **Los Angeles, CA** (`{fmt_int(top_ct.iloc[2]['total_accidentes'])}`).
- **Tasa ajustada por población (Censo 2023):** **Carolina del Sur** (`{top_rate.iloc[0]['tasa_x_100k_hab']:,.0f}` x 100k hab.), **California** (`{top_rate.iloc[1]['tasa_x_100k_hab']:,.0f}`) y **Oregón** (`{top_rate.iloc[2]['tasa_x_100k_hab']:,.0f}`) lideran el riesgo per cápita; la región **Sur** suma el `44.19%` nacional.

![Top 10 Estados y Ciudades](assets/charts/01_top10_estados_y_ciudades.png)
![Demografía Tasa x 100k Hab y Regiones](assets/charts/02_demografia_tasa_y_regiones.png)

### 2. Hora del Día y Días de la Semana Críticos (Req. 2 y 6)
- **Hora pico:** Las **{int(peak_hr['hour']):02d}:00h** (`{fmt_int(peak_hr['total_accidentes'])}` eventos, `{peak_hr['pct_total']}%`), con patrón **bimodal laboral** (07–09h y 15–18h).
- **Día crítico:** El **{peak_dy['day_name']}** concentra el máximo (`{fmt_int(peak_dy['total_accidentes'])}`, `{peak_dy['pct_total']}%`), mientras el fin de semana (Sáb+Dom = `1,231,427`, `15.93%`) reduce frecuencia pero registra **mayor severidad media** (`2.259` domingo).

![Patrón Horario y Semanal](assets/charts/03_patron_horario_y_semanal.png)
![Mapa de Calor Día x Hora](assets/charts/04_heatmap_dia_hora.png)

### 3. Severidad y Duración del Incidente (Req. 3 y 7)
- **Severidad:** Nivel 2 (`79.67%`), Nivel 3 (`16.81%`), Nivel 4 (`2.65%`) y Nivel 1 (`0.87%`).
- **Duración:** La brecha entre **media bruta (`444.4 min`)** y **mediana (`74.8 min`)** responde a `{fmt_int(audit['outliers_gt_24h'])}` *outliers* `>24h`. Depurando `≤24h`, la media desciende a **`108.0 min`** (`185.9 min` en Sev. 4 vs `45.7 min` en Sev. 1).

![Severidad y Duración](assets/charts/05_severidad_y_duracion.png)

### 4. Relación con Condiciones Climáticas (Req. 4)
- Por volumen predominan **Despejado (`44.06%`)** y **Nublado (`40.94%`)**, pero la proporción de accidentes graves (`Sev 3–4`) sube en **Lluvia (`22.76%`)** y **Nieve/Hielo (`19.95%`)** (vs `16.91%` en Despejado) conforme cae la visibilidad (`< 3.1 mi` en Niebla/Nieve).

![Clima y Severidad](assets/charts/06_clima_y_severidad.png)

### 5. Tipos de Vía Más Peligrosos y Top 10 Calles Reales (Req. 5)
- **Autopistas / Interstates** agrupan el **`32.44%` de incidentes graves** (vs `10.17%` en calles urbanas).
- **Top 3 vías reales por volumen:** `{top_str.iloc[0]['street']}` (`{fmt_int(top_str.iloc[0]['total_accidentes'])}`), `{top_str.iloc[1]['street']}` (`{fmt_int(top_str.iloc[1]['total_accidentes'])}`) e `{top_str.iloc[2]['street']}` (`{fmt_int(top_str.iloc[2]['total_accidentes'])}`), corrigiendo el ordenamiento alfabético descendente (`Zuni Rd SE`) observado en Power BI.

![Tipos de Vía y Top 10 Calles](assets/charts/07_tipos_via_y_top10_calles.png)

### 6. Tendencias Anuales y Estacionalidad Mensual (Req. 8)
- Crecimiento sostenido desde **2016 (`410,821`)** hasta el máximo histórico de **{int(peak_yr['year'])} (`{fmt_int(peak_yr['total_accidentes'])}`)**, cerrando 2023 con Q1 parcial (`246,633`). Estacionalmente lidera **{peak_mo['month_name']} (`{fmt_int(peak_mo['total_accidentes'])}`, `{peak_mo['pct_total']}%`)**.

![Tendencias Anuales y Mensuales](assets/charts/08_tendencias_anuales_y_mensuales.png)

### 7. Accidentes por Tipo de Vehículo Involucrado — NLP sobre Description (Req. 9)
- Tras filtrar toponimias viales falsas (`"I-80 Bus"`, `"Van Ness Ave"`), se identificaron `68,252` menciones válidas: **Automóvil / Multivehículo (`45,195`; `43.02%` graves)** y **Camión / Tráiler (`16,389`; mayor severidad promedio `2.521` y `124.95 min`)** encabezan tanto volumen como impacto vial.

![Tipos de Vehículo](assets/charts/09_tipos_de_vehiculo.png)

### 8. Distribución Geoespacial de Puntos Críticos y Correlaciones (Req. 10 y EDA)
- Los clústeres de cuadrícula `0.1° × 0.1°` confirman alta densidad en **Sur de California, Miami–Orlando, Houston–Dallas y el corredor Noreste**, con fuerte concentración en semáforos (`1.14M`) y cruces peatonales (`874K`).

![Distribución Geoespacial](assets/charts/10_distribucion_geoespacial_hotspots.png)
![Matriz de Correlación](assets/charts/14_matriz_correlacion_exploratoria.png)

### 9. Resultados y Visualizaciones del Análisis ANOVA
- **Duración ~ Severidad:** `F = {s1['F_clasico']:,.2f}`, `p < 1e-300`, `η² = {s1['eta_cuadrado']:.4f}` (todos los pares significativos en Tukey HSD).
- **Severidad ~ Clima × Franja Horaria (Factorial 2 Vías):** Efectos principales e interacción altamente significativos (`F = 87.58`, `p < 1e-300`), destacando mayor severidad nocturna bajo lluvia (`2.279`) y diurna bajo nieve/hielo (`2.259`).

![ANOVA Duración vs Severidad](assets/charts/11_anova_duracion_severidad.png)
![ANOVA Severidad Clima y Franja](assets/charts/12_anova_severidad_clima_franja.png)
![ANOVA Tukey Post-Hoc](assets/charts/13_anova_tukey_posthoc.png)

---

## 📊 Tablero Power BI, DAX y Código ETL (Entregables 2 y 3)

- 🌐 **Despliegue Web HTML:** [`powerbi/dashboard_powerbi.html`](powerbi/dashboard_powerbi.html) (portal interactivo con las 8 vistas del tablero, medidas DAX, código M y visor Publish-to-Web).
- 📐 **Medidas DAX explicadas:** [`powerbi/dax_measures.md`](powerbi/dax_measures.md)
- ⚙️ **Script Power Query (M):** [`powerbi/power_query_etl.pq`](powerbi/power_query_etl.pq)
- 🗄️ **Consultas SQL analíticas:** [`sql/queries_analisis.sql`](sql/queries_analisis.sql)
- ⚡ **Pipeline ETL Python y PySpark:** [`src/etl_us_accidents.py`](src/etl_us_accidents.py) · [`src/etl_pyspark.py`](src/etl_pyspark.py)

<details>
<summary>🖼️ Ver las 8 capturas documentadas del Tablero Power BI Desktop</summary>

1. **Estado y Top 10 Ciudades:** ![Vista 1](assets/powerbi/01_frecuencia_estado_top10_ciudades.jpg)
2. **KPIs, Hora y Día de la Semana:** ![Vista 2](assets/powerbi/02_kpis_hora_dia_semana.jpg)
3. **Severidad y Clima al 100%:** ![Vista 3](assets/powerbi/03_severidad_clima_porcentaje.jpg)
4. **Accidentes por Clima y Estado:** ![Vista 4](assets/powerbi/04_accidentes_clima_estado.jpg)
5. **Top 10 Vías (Auditoría de ordenamiento):** ![Vista 5](assets/powerbi/05_top10_vias_peligrosas.png)
6. **Duración Promedio vs Mediana:** ![Vista 6](assets/powerbi/06_duracion_promedio_severidad.png)
7. **Tendencias Anuales/Mensuales y Var MoM %:** ![Vista 7](assets/powerbi/07_tendencias_anuales_mensuales_mom.png)
8. **Mapa Geoespacial de Severidad:** ![Vista 8](assets/powerbi/08_mapa_geoespacial_severidad.jpg)

</details>

---

## 📄 Entregables Documentales y Presentación Oral (Entregables 1 y 4)

- 📘 **Informe Técnico (PDF):** [`docs/informe_tecnico.pdf`](docs/informe_tecnico.pdf)
- 📝 **Informe Técnico (Word):** [`docs/informe_tecnico.docx`](docs/informe_tecnico.docx)
- 🌐 **Informe Técnico (HTML & Markdown):** [`docs/informe_tecnico.html`](docs/informe_tecnico.html) · [`docs/informe_tecnico.md`](docs/informe_tecnico.md)
- 🎤 **Presentación Oral (15 Slides PPTX & Guion):** [`docs/presentacion_oral.pptx`](docs/presentacion_oral.pptx) · [`docs/guion_presentacion_oral.md`](docs/guion_presentacion_oral.md)
- 🖥️ **Portal HTML Raíz:** [`index.html`](index.html)

---

## 🚀 Cómo Reproducir el Pipeline Completo

> **Nota sobre el CSV original:** Por superar el límite de 100 MB de GitHub (~3.06 GB), `US_Accidents_March23.csv` y los binarios generados están excluidos en `.gitignore`. Descarga el CSV desde [Kaggle US Accidents](https://www.kaggle.com/datasets/sobhanmoosavi/us-accidents) y ubícalo en `data/US_Accidents_March23.csv`.

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Ejecutar pipeline ETL (genera Parquet + base SQLite indexada)
python src/etl_us_accidents.py

# 3. Ejecutar consultas SQL y generar las gráficas en Python
python src/analysis_sql_and_charts.py

# 4. Ejecutar pruebas ANOVA y generar las gráficas estadísticas
python src/anova_analysis.py

# 5. (Opcional) Ejecutar versión distribuida en PySpark
python src/etl_pyspark.py

# 6. Regenerar todos los entregables (PDF, Word, PPTX, HTML, MD y README)
python src/generate_deliverables.py
```
"""
    readme_path = os.path.join(BASE_DIR, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme)
    print(f"[OK] README.md generado: {readme_path}")


def main():
    audit = load_json("00_etl_audit.json")
    summary = load_json("summary_analisis.json")
    anova = load_json("anova_summary.json")

    dfs = {
        "states": pd.read_csv(os.path.join(RES_DIR, "02_accidentes_por_estado_demografia.csv")),
        "cities": pd.read_csv(os.path.join(RES_DIR, "03_top15_ciudades.csv")),
        "day": pd.read_csv(os.path.join(RES_DIR, "06_accidentes_por_dia_semana.csv")),
        "sev": pd.read_csv(os.path.join(RES_DIR, "07_severidad_y_duracion.csv")),
        "weather": pd.read_csv(os.path.join(RES_DIR, "08_accidentes_por_clima.csv")),
        "road": pd.read_csv(os.path.join(RES_DIR, "09_tipos_via_peligrosos.csv")),
        "streets": pd.read_csv(os.path.join(RES_DIR, "09b_top12_vias_especificas.csv")),
        "poi": pd.read_csv(os.path.join(RES_DIR, "09c_infraestructura_vial.csv")),
        "year": pd.read_csv(os.path.join(RES_DIR, "10_tendencia_anual.csv")),
        "month": pd.read_csv(os.path.join(RES_DIR, "10b_estacionalidad_mensual.csv")),
        "veh": pd.read_csv(os.path.join(RES_DIR, "11_accidentes_por_vehiculo.csv")),
        "veh_k": pd.read_csv(os.path.join(RES_DIR, "11b_vehiculos_identificados.csv")),
        "anova_g1": pd.read_csv(os.path.join(RES_DIR, "anova1_grupos_duracion_severidad.csv")),
        "anova_g2": pd.read_csv(os.path.join(RES_DIR, "anova2_grupos_severidad_clima.csv")),
        "anova_t1": pd.read_csv(os.path.join(RES_DIR, "anova1_tukey_duracion_severidad.csv")),
        "anova_2w": pd.read_csv(os.path.join(RES_DIR, "anova4_factorial_clima_franja.csv")),
    }

    md_report = build_technical_markdown(audit, summary, anova, dfs)
    md_path = os.path.join(DOCS_DIR, "informe_tecnico.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"[OK] Informe Markdown generado: {md_path}")

    html_report = md_to_html(md_report, "Informe Técnico — Proyecto 3: US Accidents")
    html_path = os.path.join(DOCS_DIR, "informe_tecnico.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_report)
    print(f"[OK] Informe HTML generado: {html_path}")

    build_pdf_report(audit, summary, anova, dfs)
    build_docx_report(audit, summary, anova, dfs)
    build_pptx_and_script(audit, summary, anova, dfs)
    build_readme(audit, summary, anova, dfs)


if __name__ == "__main__":
    main()
