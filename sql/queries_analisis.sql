-- ============================================================================
-- PROYECTO 3: Análisis de Accidentes de Tránsito en Zonas Urbanas (US Accidents)
-- Consultas SQL Analíticas (SQLite 3 / Compatible SQL Estándar)
-- Base de datos generada por el ETL: data/us_accidents.db
-- Tablas:
--   * accidents        (Tabla de hechos enriquecida, ~7.73M registros)
--   * dim_demographics (Dimensión demográfica Censo EE.UU. por Estado)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- AUDITORÍA GENERAL: Conteo total, rango temporal y calidad de datos
-- ----------------------------------------------------------------------------
SELECT
    COUNT(*) AS total_registros,
    COUNT(DISTINCT state) AS estados_cubiertos,
    COUNT(DISTINCT city) AS ciudades_cubiertas,
    MIN(start_time) AS fecha_inicio,
    MAX(start_time) AS fecha_fin,
    SUM(CASE WHEN weather_raw = 'Sin dato' THEN 1 ELSE 0 END) AS sin_clima_reportado,
    SUM(CASE WHEN duration_raw_min > 1440 THEN 1 ELSE 0 END) AS outliers_duracion_gt_24h
FROM accidents;

-- ----------------------------------------------------------------------------
-- REQ 1: Frecuencia de accidentes por estado y ciudad (+ tasa demográfica)
-- ----------------------------------------------------------------------------
-- 1A. Top 15 estados por volumen total y tasa por cada 100,000 habitantes
SELECT
    a.state,
    d.state_name,
    d.region,
    d.population_2023,
    d.density_per_sqmi,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_nacional,
    ROUND(COUNT(*) * 100000.0 / d.population_2023, 2) AS tasa_x_100k_hab,
    ROUND(AVG(a.severity), 3) AS severidad_promedio
FROM accidents a
LEFT JOIN dim_demographics d ON a.state = d.state
GROUP BY a.state, d.state_name, d.region, d.population_2023, d.density_per_sqmi
ORDER BY total_accidentes DESC
LIMIT 15;

-- 1B. Top 15 ciudades con mayor frecuencia de accidentes urbanos
SELECT
    city,
    state,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_nacional,
    ROUND(AVG(severity), 3) AS severidad_promedio,
    SUM(CASE WHEN severity >= 3 THEN 1 ELSE 0 END) AS accidentes_graves_s3_s4
FROM accidents
WHERE city IS NOT NULL AND city <> 'Sin dato'
GROUP BY city, state
ORDER BY total_accidentes DESC
LIMIT 15;

-- 1C. Resumen demográfico por Región del Censo (South, West, Midwest, Northeast)
SELECT
    d.region,
    COUNT(DISTINCT a.state) AS num_estados,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_accidentes,
    SUM(DISTINCT d.population_2023) AS poblacion_regional,
    ROUND(AVG(a.severity), 3) AS severidad_promedio
FROM accidents a
INNER JOIN dim_demographics d ON a.state = d.state
GROUP BY d.region
ORDER BY total_accidentes DESC;

-- ----------------------------------------------------------------------------
-- REQ 2: Hora del día con mayor accidentalidad (y ciclo día/noche)
-- ----------------------------------------------------------------------------
-- 2A. Distribución horaria (00h a 23h)
SELECT
    hour AS hora_del_dia,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_total,
    ROUND(AVG(severity), 3) AS severidad_promedio,
    SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) AS accidentes_graves
FROM accidents
WHERE hour IS NOT NULL
GROUP BY hour
ORDER BY hour ASC;

-- 2B. Franjas horarias y comparación Día vs Noche (Sunrise_Sunset)
SELECT
    sunrise_sunset AS ciclo_luz,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_total,
    ROUND(AVG(severity), 3) AS severidad_promedio,
    ROUND(AVG(duration_clean_min), 2) AS duracion_media_depurada_min
FROM accidents
GROUP BY sunrise_sunset
ORDER BY total_accidentes DESC;

-- ----------------------------------------------------------------------------
-- REQ 3: Análisis por severidad del accidente (Niveles 1 a 4)
-- ----------------------------------------------------------------------------
SELECT
    severity,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_total,
    ROUND(AVG(distance_mi), 3) AS distancia_media_mi,
    ROUND(AVG(duration_raw_min), 2) AS duracion_media_bruta_min,
    ROUND(AVG(duration_clean_min), 2) AS duracion_media_depurada_min
FROM accidents
GROUP BY severity
ORDER BY severity ASC;

-- ----------------------------------------------------------------------------
-- REQ 4: Relación con condiciones climáticas
-- ----------------------------------------------------------------------------
-- 4A. Distribución por grupo climático estandarizado y tasa de gravedad (Sev 3-4)
SELECT
    weather_group AS clima_grupo,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_total,
    SUM(CASE WHEN severity = 1 THEN 1 ELSE 0 END) AS sev_1,
    SUM(CASE WHEN severity = 2 THEN 1 ELSE 0 END) AS sev_2,
    SUM(CASE WHEN severity = 3 THEN 1 ELSE 0 END) AS sev_3,
    SUM(CASE WHEN severity = 4 THEN 1 ELSE 0 END) AS sev_4,
    ROUND(SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_graves_s3_s4,
    ROUND(AVG(visibility_mi), 2) AS visibilidad_promedio_mi,
    ROUND(AVG(temperature_f), 2) AS temperatura_promedio_f
FROM accidents
GROUP BY weather_group
ORDER BY total_accidentes DESC;

-- 4B. Top 12 condiciones climáticas específicas (Weather_Condition original)
SELECT
    weather_raw,
    weather_group,
    COUNT(*) AS total_accidentes,
    ROUND(AVG(severity), 3) AS severidad_promedio
FROM accidents
WHERE weather_raw <> 'Sin dato'
GROUP BY weather_raw, weather_group
ORDER BY total_accidentes DESC
LIMIT 12;

-- ----------------------------------------------------------------------------
-- REQ 5: Tipos de vía más peligrosos e infraestructura vial
-- ----------------------------------------------------------------------------
-- 5A. Clasificación por tipo de vía (Autopista, Carretera, Avenida, Calle Urbana)
SELECT
    road_type AS tipo_via,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_total,
    ROUND(AVG(severity), 3) AS severidad_promedio,
    ROUND(SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_graves_s3_s4,
    ROUND(AVG(distance_mi), 3) AS distancia_media_mi
FROM accidents
GROUP BY road_type
ORDER BY total_accidentes DESC;

-- 5B. Top 15 vías específicas reales por volumen (corrige orden alfabético en BI)
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
LIMIT 15;

-- 5C. Presencia de elementos de infraestructura vial (POI booleanos)
SELECT
    SUM(traffic_signal) AS con_semaforo,
    SUM(junction) AS con_interseccion,
    SUM(crossing) AS con_cruce_peatonal,
    SUM(stop) AS con_senal_pare,
    SUM(station) AS cerca_estacion,
    SUM(railway) AS cruce_ferroviario,
    SUM(roundabout) AS glorieta
FROM accidents;

-- ----------------------------------------------------------------------------
-- REQ 6: Días de la semana con más incidentes (y Laboral vs Fin de Semana)
-- ----------------------------------------------------------------------------
SELECT
    day_of_week_num,
    day_name,
    CASE WHEN is_weekend = 1 THEN 'Fin de Semana' ELSE 'Día Laboral' END AS tipo_dia,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_total,
    ROUND(AVG(severity), 3) AS severidad_promedio
FROM accidents
GROUP BY day_of_week_num, day_name, is_weekend
ORDER BY day_of_week_num ASC;

-- ----------------------------------------------------------------------------
-- REQ 7: Promedio y distribución de duración del incidente (bruta vs depurada)
-- ----------------------------------------------------------------------------
SELECT
    severity,
    COUNT(*) AS total_accidentes,
    ROUND(AVG(duration_raw_min), 2) AS duracion_media_bruta_min,
    ROUND(AVG(duration_clean_min), 2) AS duracion_media_depurada_min,
    ROUND(MIN(duration_clean_min), 2) AS min_depurada_min,
    ROUND(MAX(duration_clean_min), 2) AS max_depurada_min
FROM accidents
GROUP BY severity
ORDER BY severity ASC;

-- ----------------------------------------------------------------------------
-- REQ 8: Tendencias anuales y mensuales (+ variación MoM)
-- ----------------------------------------------------------------------------
-- 8A. Tendencia anual (2016 - 2023)
SELECT
    year,
    COUNT(*) AS total_accidentes,
    ROUND(AVG(severity), 3) AS severidad_promedio,
    SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) AS accidentes_graves
FROM accidents
WHERE year IS NOT NULL
GROUP BY year
ORDER BY year ASC;

-- 8B. Estacionalidad mensual agregada (Enero a Diciembre)
SELECT
    month,
    month_name,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_total,
    ROUND(AVG(severity), 3) AS severidad_promedio
FROM accidents
WHERE month IS NOT NULL
GROUP BY month, month_name
ORDER BY month ASC;

-- 8C. Serie temporal mensual (YYYY-MM) con variación MoM % mediante función ventana LAG()
WITH mensual AS (
    SELECT
        year_month,
        COUNT(*) AS total_accidentes
    FROM accidents
    WHERE year_month IS NOT NULL
    GROUP BY year_month
)
SELECT
    year_month,
    total_accidentes,
    LAG(total_accidentes) OVER (ORDER BY year_month) AS mes_anterior,
    ROUND(
        (total_accidentes - LAG(total_accidentes) OVER (ORDER BY year_month)) * 100.0
        / NULLIF(LAG(total_accidentes) OVER (ORDER BY year_month), 0),
        2
    ) AS var_mom_pct
FROM mensual
ORDER BY year_month ASC;

-- ----------------------------------------------------------------------------
-- REQ 9: Accidentes por tipo de vehículo involucrado (extraído de Description)
-- ----------------------------------------------------------------------------
SELECT
    vehicle_type,
    COUNT(*) AS total_accidentes,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accidents), 2) AS pct_sobre_total,
    ROUND(AVG(severity), 3) AS severidad_promedio,
    ROUND(SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_graves_s3_s4,
    ROUND(AVG(duration_clean_min), 2) AS duracion_media_min
FROM accidents
GROUP BY vehicle_type
ORDER BY total_accidentes DESC;

-- ----------------------------------------------------------------------------
-- REQ 10: Distribución geoespacial de puntos críticos (Celdas 0.1° x 0.1°)
-- ----------------------------------------------------------------------------
SELECT
    ROUND(start_lat, 1) AS lat_bin,
    ROUND(start_lng, 1) AS lng_bin,
    state,
    MAX(city) AS ciudad_referencia,
    COUNT(*) AS total_accidentes,
    SUM(CASE WHEN severity IN (3, 4) THEN 1 ELSE 0 END) AS accidentes_graves,
    ROUND(AVG(severity), 3) AS severidad_promedio
FROM accidents
WHERE start_lat IS NOT NULL AND start_lng IS NOT NULL
GROUP BY lat_bin, lng_bin, state
ORDER BY total_accidentes DESC
LIMIT 25;
