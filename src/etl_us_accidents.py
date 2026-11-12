# ==============================================================================
# PROYECTO 3: Análisis de Accidentes de Tránsito en Zonas Urbanas (US Accidents)
# Pipeline ETL Principal: Python (Pandas + PyArrow + SQLite)
# ==============================================================================
# Fases:
#   1. Extracción por bloques (streaming 500k filas) desde US_Accidents_March23.csv
#      y carga de la tabla demográfica us_state_demographics.csv (Censo EE.UU.).
#   2. Limpieza y normalización: deduplicación por ID, parseo de timestamps con
#      precisión de nanosegundos (.000000000), tratamiento de nulos y detección
#      de outliers extremos de duración (> 24 horas).
#   3. Enriquecimiento y derivación: variables temporales, grupos climáticos en
#      español, clasificación de vías, extracción NLP/RE2 de tipo de vehículo
#      desde Description (filtrando falsos positivos como 'I-80 Bus' o 'Van Ness')
#      e integración demográfica por estado.
#   4. Carga analítica: almacenamiento columnar en Parquet y base de datos
#      relacional SQLite (data/us_accidents.db) con índices optimizados para SQL.
# ==============================================================================

import json
import os
import sqlite3
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_CSV = os.path.join(BASE_DIR, "data", "US_Accidents_March23.csv")
DEMO_CSV = os.path.join(BASE_DIR, "data", "us_state_demographics.csv")
PARQUET_OUT = os.path.join(BASE_DIR, "data", "us_accidents_clean.parquet")
SQLITE_OUT = os.path.join(BASE_DIR, "data", "us_accidents.db")
AUDIT_JSON = os.path.join(BASE_DIR, "resultados", "00_etl_audit.json")
AUDIT_CSV = os.path.join(BASE_DIR, "resultados", "00_etl_audit.csv")

USE_COLS = [
    "ID", "Source", "Severity", "Start_Time", "End_Time",
    "Start_Lat", "Start_Lng", "Distance(mi)", "Description",
    "Street", "City", "County", "State",
    "Temperature(F)", "Humidity(%)", "Visibility(mi)",
    "Wind_Speed(mph)", "Precipitation(in)", "Weather_Condition",
    "Crossing", "Junction", "Railway", "Roundabout",
    "Station", "Stop", "Traffic_Signal", "Sunrise_Sunset",
]

MONTH_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# Orden de semana coincidente con Power BI (1=Domingo .. 7=Sábado)
# pandas dt.dayofweek devuelve 0=Lunes .. 6=Domingo -> ((dow + 1) % 7) + 1
DAY_ES = {
    1: "Domingo", 2: "Lunes", 3: "Martes", 4: "Miércoles",
    5: "Jueves", 6: "Viernes", 7: "Sábado",
}


def clasificar_clima(series_weather: pd.Series) -> pd.Series:
    """Agrupación semántica de Weather_Condition en 6 categorías en español."""
    arr = pa.array(series_weather.fillna("").astype(str))
    is_empty = pc.equal(arr, "")
    is_snow = pc.match_substring_regex(arr, r"(?i)(snow|ice|sleet|hail|wintry|freezing)")
    is_rain = pc.match_substring_regex(arr, r"(?i)(rain|drizzle|shower|thunder|t-storm|storm)")
    is_fog = pc.match_substring_regex(arr, r"(?i)(fog|mist|haze|smoke|dust|ash)")
    is_cloud = pc.match_substring_regex(arr, r"(?i)(cloud|overcast)")
    is_clear = pc.match_substring_regex(arr, r"(?i)(clear|fair)")

    conds = [
        is_empty.to_numpy(zero_copy_only=False),
        is_snow.to_numpy(zero_copy_only=False),
        is_rain.to_numpy(zero_copy_only=False),
        is_fog.to_numpy(zero_copy_only=False),
        is_cloud.to_numpy(zero_copy_only=False),
        is_clear.to_numpy(zero_copy_only=False),
    ]
    choices = ["Otro", "Nieve/Hielo", "Lluvia", "Niebla", "Nublado", "Despejado"]
    return pd.Series(np.select(conds, choices, default="Otro"), index=series_weather.index)


def clasificar_tipo_via(series_street: pd.Series) -> pd.Series:
    """Clasifica el tipo de vía usando patrones RE2 en C++ sobre Street."""
    arr = pa.array(series_street.fillna("").astype(str))
    is_empty = pc.equal(arr, "")
    is_interstate = pc.match_substring_regex(arr, r"(?i)\b(I-\d+|INTERSTATE|FWY|FREEWAY|EXPY|EXPRESSWAY|PKWY|PARKWAY|TPKE|TURNPIKE)\b")
    is_highway = pc.match_substring_regex(arr, r"(?i)\b(US-\d+|SR-\d+|STATE ROUTE|STATE HWY|HWY|HIGHWAY|RT-\d+|COUNTY RD|CR-\d+)\b")
    is_blvd = pc.match_substring_regex(arr, r"(?i)\b(BLVD|BOULEVARD|AVE|AVENUE)\b")
    is_urban = pc.match_substring_regex(arr, r"(?i)\b(ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|PL|CIR)\b")

    conds = [
        is_empty.to_numpy(zero_copy_only=False),
        is_interstate.to_numpy(zero_copy_only=False),
        is_highway.to_numpy(zero_copy_only=False),
        is_blvd.to_numpy(zero_copy_only=False),
        is_urban.to_numpy(zero_copy_only=False),
    ]
    choices = [
        "Sin dato",
        "Autopista / Interstate",
        "Carretera / Highway",
        "Avenida / Boulevard",
        "Calle / Vía Urbana",
    ]
    return pd.Series(np.select(conds, choices, default="Otra Vía"), index=series_street.index)


def extraer_tipo_vehiculo(series_desc: pd.Series) -> pd.Series:
    """
    Extrae el tipo de vehículo involucrado desde Description mediante PyArrow RE2.
    Filtra falsos positivos comunes en nombres de vías de EE.UU. (p. ej. 'I-80 Bus',
    'Van Ness Ave', 'Van Buren St', 'Auto Mall Pkwy', 'Truck Route').
    """
    arr = pa.array(series_desc.fillna("").astype(str))

    is_suv_van = pc.match_substring_regex(
        arr, r"(?i)\b(suv|minivan|pickup|pickup truck|cargo van|sprinter|van involved|van fire|van overturned)\b"
    )
    is_truck = pc.and_not(
        pc.match_substring_regex(arr, r"(?i)\b(semi|tractor|18-wheeler|tanker|trailer|big rig|box truck|dump truck|truck)\b"),
        pc.match_substring_regex(arr, r"(?i)\b(truck route|truck stop|truck plaza|truck center|trailer park|pickup truck)\b"),
    )
    is_moto = pc.match_substring_regex(arr, r"(?i)\b(motorcycle|motorbike|moped|scooter)\b")
    is_bus = pc.match_substring_regex(
        arr, r"(?i)\b(school bus|transit bus|city bus|charter bus|shuttle bus|bus involved|bus accident|bus crash)\b"
    )
    is_bike = pc.match_substring_regex(arr, r"(?i)\b(bicycle|bicyclist|cyclist)\b")
    is_ped = pc.match_substring_regex(arr, r"(?i)\bpedestrian\b")
    is_car = pc.match_substring_regex(
        arr,
        r"(?i)\b(multi-?vehicle|multivehicle|two-?vehicle|three-?vehicle|multiple vehicles|car accident|car crash|car fire|car involved|a car|sedan|coupe|hatchback|vehicle involved|vehicle fire|overturned vehicle|disabled vehicle|stalled vehicle)\b",
    )

    conds = [
        is_truck.to_numpy(zero_copy_only=False),
        is_moto.to_numpy(zero_copy_only=False),
        is_bus.to_numpy(zero_copy_only=False),
        is_bike.to_numpy(zero_copy_only=False),
        is_ped.to_numpy(zero_copy_only=False),
        is_suv_van.to_numpy(zero_copy_only=False),
        is_car.to_numpy(zero_copy_only=False),
    ]
    choices = [
        "Camión / Tráiler",
        "Motocicleta",
        "Autobús",
        "Bicicleta",
        "Peatón involucrado",
        "SUV / Van / Pickup",
        "Automóvil / Multivehículo",
    ]
    return pd.Series(np.select(conds, choices, default="No especificado"), index=series_desc.index)


def asignar_franja_horaria(series_hour: pd.Series) -> pd.Series:
    conds = [
        (series_hour >= 0) & (series_hour < 6),
        (series_hour >= 6) & (series_hour < 10),
        (series_hour >= 10) & (series_hour < 15),
        (series_hour >= 15) & (series_hour < 20),
        (series_hour >= 20) & (series_hour <= 23),
    ]
    choices = [
        "1. Madrugada (00-05h)",
        "2. Pico Mañana (06-09h)",
        "3. Mediodía (10-14h)",
        "4. Pico Tarde (15-19h)",
        "5. Noche (20-23h)",
    ]
    return pd.Series(np.select(conds, choices, default="Sin dato"), index=series_hour.index)


def crear_esquema_sqlite(conn: sqlite3.Connection, demo_df: pd.DataFrame):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS accidents")
    cur.execute("DROP TABLE IF EXISTS dim_demographics")

    cur.execute("""
        CREATE TABLE dim_demographics (
            state TEXT PRIMARY KEY,
            state_name TEXT,
            region TEXT,
            population_2023 INTEGER,
            area_sqmi INTEGER,
            density_per_sqmi REAL
        )
    """)

    cur.execute("""
        CREATE TABLE accidents (
            id TEXT,
            source TEXT,
            severity INTEGER,
            start_time TEXT,
            end_time TEXT,
            year INTEGER,
            month INTEGER,
            month_name TEXT,
            year_month TEXT,
            hour INTEGER,
            day_of_week_num INTEGER,
            day_name TEXT,
            is_weekend INTEGER,
            time_slot TEXT,
            duration_raw_min REAL,
            duration_clean_min REAL,
            distance_mi REAL,
            start_lat REAL,
            start_lng REAL,
            street TEXT,
            road_type TEXT,
            city TEXT,
            county TEXT,
            state TEXT,
            temperature_f REAL,
            humidity_pct REAL,
            visibility_mi REAL,
            wind_speed_mph REAL,
            precipitation_in REAL,
            weather_raw TEXT,
            weather_group TEXT,
            sunrise_sunset TEXT,
            traffic_signal INTEGER,
            junction INTEGER,
            crossing INTEGER,
            stop INTEGER,
            station INTEGER,
            railway INTEGER,
            roundabout INTEGER,
            vehicle_type TEXT
        )
    """)
    demo_cols = demo_df.rename(columns={
        "State": "state",
        "State_Name": "state_name",
        "Region": "region",
        "Population_2023": "population_2023",
        "Area_SqMi": "area_sqmi",
        "Density_Per_SqMi": "density_per_sqmi",
    })
    demo_cols.to_sql("dim_demographics", conn, if_exists="append", index=False)
    conn.commit()


def crear_indices_sqlite(conn: sqlite3.Connection):
    cur = conn.cursor()
    indices = [
        "CREATE INDEX idx_acc_state ON accidents(state)",
        "CREATE INDEX idx_acc_severity ON accidents(severity)",
        "CREATE INDEX idx_acc_weather ON accidents(weather_group)",
        "CREATE INDEX idx_acc_ym ON accidents(year, month)",
        "CREATE INDEX idx_acc_hour ON accidents(hour)",
        "CREATE INDEX idx_acc_day ON accidents(day_of_week_num)",
        "CREATE INDEX idx_acc_road ON accidents(road_type)",
        "CREATE INDEX idx_acc_veh ON accidents(vehicle_type)",
    ]
    for idx_sql in indices:
        cur.execute(idx_sql)
    conn.commit()


def run_etl():
    t0 = time.time()
    os.makedirs(os.path.join(BASE_DIR, "resultados"), exist_ok=True)
    if os.path.exists(PARQUET_OUT):
        os.remove(PARQUET_OUT)
    if os.path.exists(SQLITE_OUT):
        os.remove(SQLITE_OUT)

    print("=== FASE 1: Extracción y preparación ===")
    demo_df = pd.read_csv(DEMO_CSV)
    print(f"[OK] Demografía cargada: {len(demo_df)} estados/territorios (Censo EE.UU. 2023)")

    conn = sqlite3.connect(SQLITE_OUT)
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -256000")
    crear_esquema_sqlite(conn, demo_df)

    audit = {
        "total_raw_rows": 0,
        "total_clean_rows": 0,
        "duplicates_removed": 0,
        "dotted_timestamps_fixed": 0,
        "invalid_timestamps": 0,
        "negative_durations": 0,
        "outliers_gt_24h": 0,
        "nulls_street": 0,
        "nulls_city": 0,
        "nulls_weather": 0,
        "nulls_temperature": 0,
        "nulls_visibility": 0,
    }

    seen_ids = set()
    parquet_writer = None
    chunk_size = 500_000

    print("=== FASE 2 y 3: Streaming ETL (bloques de 500,000 registros) ===")
    for i, chunk in enumerate(pd.read_csv(RAW_CSV, usecols=USE_COLS, chunksize=chunk_size)):
        c_t0 = time.time()
        audit["total_raw_rows"] += len(chunk)

        # Conteo de nulos en crudo
        audit["nulls_street"] += int(chunk["Street"].isna().sum())
        audit["nulls_city"] += int(chunk["City"].isna().sum())
        audit["nulls_weather"] += int(chunk["Weather_Condition"].isna().sum())
        audit["nulls_temperature"] += int(chunk["Temperature(F)"].isna().sum())
        audit["nulls_visibility"] += int(chunk["Visibility(mi)"].isna().sum())

        # Deduplicación global incremental por ID
        mask_new = ~chunk["ID"].isin(seen_ids)
        if not mask_new.all():
            audit["duplicates_removed"] += int((~mask_new).sum())
            chunk = chunk[mask_new].copy()
        seen_ids.update(chunk["ID"].tolist())

        # Normalización de timestamps (soporta nanosegundos .000000000)
        st_str = chunk["Start_Time"].astype(str)
        et_str = chunk["End_Time"].astype(str)
        audit["dotted_timestamps_fixed"] += int(st_str.str.contains(".", regex=False).sum())

        start_dt = pd.to_datetime(st_str.str.slice(0, 19), format="%Y-%m-%d %H:%M:%S", errors="coerce")
        end_dt = pd.to_datetime(et_str.str.slice(0, 19), format="%Y-%m-%d %H:%M:%S", errors="coerce")
        audit["invalid_timestamps"] += int(start_dt.isna().sum())

        dur_raw = (end_dt - start_dt).dt.total_seconds() / 60.0
        neg_mask = dur_raw < 0
        audit["negative_durations"] += int(neg_mask.sum())
        dur_raw = dur_raw.mask(neg_mask, np.nan).round(2)

        outlier_mask = dur_raw > 1440.0
        audit["outliers_gt_24h"] += int(outlier_mask.sum())
        dur_clean = dur_raw.mask(outlier_mask, np.nan)

        dow_num = ((start_dt.dt.dayofweek + 1) % 7) + 1  # 1=Domingo..7=Sábado

        out = pd.DataFrame({
            "id": chunk["ID"].astype(str),
            "source": chunk["Source"].fillna("Sin dato").astype(str),
            "severity": chunk["Severity"].astype("int8"),
            "start_time": start_dt.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_dt.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "year": start_dt.dt.year.astype("Int16"),
            "month": start_dt.dt.month.astype("Int8"),
            "month_name": start_dt.dt.month.map(MONTH_ES).fillna("Sin dato"),
            "year_month": start_dt.dt.strftime("%Y-%m"),
            "hour": start_dt.dt.hour.astype("Int8"),
            "day_of_week_num": dow_num.astype("Int8"),
            "day_name": dow_num.map(DAY_ES).fillna("Sin dato"),
            "is_weekend": dow_num.isin([1, 7]).astype("int8"),
            "time_slot": asignar_franja_horaria(start_dt.dt.hour.fillna(-1)),
            "duration_raw_min": dur_raw.astype("float32"),
            "duration_clean_min": dur_clean.astype("float32"),
            "distance_mi": pd.to_numeric(chunk["Distance(mi)"], errors="coerce").round(3).astype("float32"),
            "start_lat": pd.to_numeric(chunk["Start_Lat"], errors="coerce").round(5).astype("float32"),
            "start_lng": pd.to_numeric(chunk["Start_Lng"], errors="coerce").round(5).astype("float32"),
            "street": chunk["Street"].fillna("Sin dato").astype(str).str.strip(),
            "road_type": clasificar_tipo_via(chunk["Street"]),
            "city": chunk["City"].fillna("Sin dato").astype(str).str.strip(),
            "county": chunk["County"].fillna("Sin dato").astype(str).str.strip(),
            "state": chunk["State"].fillna("Sin dato").astype(str).str.strip(),
            "temperature_f": pd.to_numeric(chunk["Temperature(F)"], errors="coerce").astype("float32"),
            "humidity_pct": pd.to_numeric(chunk["Humidity(%)"], errors="coerce").astype("float32"),
            "visibility_mi": pd.to_numeric(chunk["Visibility(mi)"], errors="coerce").astype("float32"),
            "wind_speed_mph": pd.to_numeric(chunk["Wind_Speed(mph)"], errors="coerce").astype("float32"),
            "precipitation_in": pd.to_numeric(chunk["Precipitation(in)"], errors="coerce").astype("float32"),
            "weather_raw": chunk["Weather_Condition"].fillna("Sin dato").astype(str).str.strip(),
            "weather_group": clasificar_clima(chunk["Weather_Condition"]),
            "sunrise_sunset": chunk["Sunrise_Sunset"].fillna("Sin dato").astype(str),
            "traffic_signal": chunk["Traffic_Signal"].fillna(False).astype("int8"),
            "junction": chunk["Junction"].fillna(False).astype("int8"),
            "crossing": chunk["Crossing"].fillna(False).astype("int8"),
            "stop": chunk["Stop"].fillna(False).astype("int8"),
            "station": chunk["Station"].fillna(False).astype("int8"),
            "railway": chunk["Railway"].fillna(False).astype("int8"),
            "roundabout": chunk["Roundabout"].fillna(False).astype("int8"),
            "vehicle_type": extraer_tipo_vehiculo(chunk["Description"]),
        })

        audit["total_clean_rows"] += len(out)

        # Escritura incremental a Parquet
        table = pa.Table.from_pandas(out, preserve_index=False)
        if parquet_writer is None:
            parquet_writer = pq.ParquetWriter(PARQUET_OUT, table.schema, compression="snappy")
        parquet_writer.write_table(table)

        # Carga rápida a SQLite con executemany en transacción única
        cols_list = list(out.columns)
        placeholders = ",".join(["?"] * len(cols_list))
        insert_sql = f"INSERT INTO accidents ({','.join(cols_list)}) VALUES ({placeholders})"
        col_arrays = []
        for col_name in cols_list:
            s_col = out[col_name]
            if pd.api.types.is_integer_dtype(s_col):
                if s_col.isna().any():
                    col_arrays.append([None if pd.isna(v) else int(v) for v in s_col.tolist()])
                else:
                    col_arrays.append(s_col.astype(int).tolist())
            elif pd.api.types.is_float_dtype(s_col):
                # En sqlite3 Python, NaN se inserta como NULL o float; normalizamos NaN -> None
                vals = s_col.astype(float).tolist()
                col_arrays.append([None if (v != v) else v for v in vals])
            else:
                col_arrays.append([None if pd.isna(v) else str(v) for v in s_col.tolist()])
        conn.execute("BEGIN")
        conn.executemany(insert_sql, zip(*col_arrays))
        conn.commit()

        print(f"  [Bloque {i+1:02d}] {audit['total_clean_rows']:,} filas procesadas ({time.time()-c_t0:.1f}s)")

    if parquet_writer is not None:
        parquet_writer.close()

    print("=== FASE 4: Creación de índices analíticos en SQLite ===")
    idx_t0 = time.time()
    crear_indices_sqlite(conn)
    conn.close()
    print(f"[OK] Índices SQLite creados en {time.time()-idx_t0:.1f}s")

    audit["elapsed_seconds"] = round(time.time() - t0, 2)
    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)
    pd.DataFrame([audit]).to_csv(AUDIT_CSV, index=False)

    print(f"\n[COMPLETADO] ETL finalizado en {audit['elapsed_seconds']}s")
    print(f"  -> Parquet: {PARQUET_OUT}")
    print(f"  -> SQLite:  {SQLITE_OUT}")
    print(f"  -> Audit:   {AUDIT_JSON}")


if __name__ == "__main__":
    run_etl()
