# ==============================================================================
# PROYECTO 3: Análisis de Accidentes de Tránsito en Zonas Urbanas (US Accidents)
# Pipeline ETL Alternativo con PySpark y Spark SQL
# ==============================================================================
# Uso:
#   python src/etl_pyspark.py
#   python src/etl_pyspark.py --data-path data/US_Accidents_March23.csv --output-dir resultados/pyspark
# ==============================================================================

import argparse
import csv
import os
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, BooleanType
)


def parse_args():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    parser = argparse.ArgumentParser(description="ETL PySpark - US Accidents")
    parser.add_argument(
        "--data-path",
        default=os.path.join(base_dir, "data", "US_Accidents_March23.csv"),
        help="Ruta al archivo CSV de US Accidents",
    )
    parser.add_argument(
        "--demo-path",
        default=os.path.join(base_dir, "data", "us_state_demographics.csv"),
        help="Ruta al archivo CSV de demografía por estado",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(base_dir, "resultados", "pyspark"),
        help="Carpeta de salida CSV",
    )
    return parser.parse_args()


def crear_spark_session():
    spark = (
        SparkSession.builder
        .appName("Proyecto3_US_Accidents_ETL")
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "16")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    print(f"[OK] SparkSession iniciada (Spark {spark.version})")
    return spark


def extraer_datos(spark, data_path, demo_path):
    schema_acc = StructType([
        StructField("ID", StringType(), True),
        StructField("Source", StringType(), True),
        StructField("Severity", IntegerType(), True),
        StructField("Start_Time", StringType(), True),
        StructField("End_Time", StringType(), True),
        StructField("Start_Lat", DoubleType(), True),
        StructField("Start_Lng", DoubleType(), True),
        StructField("End_Lat", DoubleType(), True),
        StructField("End_Lng", DoubleType(), True),
        StructField("Distance(mi)", DoubleType(), True),
        StructField("Description", StringType(), True),
        StructField("Street", StringType(), True),
        StructField("City", StringType(), True),
        StructField("County", StringType(), True),
        StructField("State", StringType(), True),
        StructField("Zipcode", StringType(), True),
        StructField("Country", StringType(), True),
        StructField("Timezone", StringType(), True),
        StructField("Airport_Code", StringType(), True),
        StructField("Weather_Timestamp", StringType(), True),
        StructField("Temperature(F)", DoubleType(), True),
        StructField("Wind_Chill(F)", DoubleType(), True),
        StructField("Humidity(%)", DoubleType(), True),
        StructField("Pressure(in)", DoubleType(), True),
        StructField("Visibility(mi)", DoubleType(), True),
        StructField("Wind_Direction", StringType(), True),
        StructField("Wind_Speed(mph)", DoubleType(), True),
        StructField("Precipitation(in)", DoubleType(), True),
        StructField("Weather_Condition", StringType(), True),
        StructField("Amenity", BooleanType(), True),
        StructField("Bump", BooleanType(), True),
        StructField("Crossing", BooleanType(), True),
        StructField("Give_Way", BooleanType(), True),
        StructField("Junction", BooleanType(), True),
        StructField("No_Exit", BooleanType(), True),
        StructField("Railway", BooleanType(), True),
        StructField("Roundabout", BooleanType(), True),
        StructField("Station", BooleanType(), True),
        StructField("Stop", BooleanType(), True),
        StructField("Traffic_Calming", BooleanType(), True),
        StructField("Traffic_Signal", BooleanType(), True),
        StructField("Turning_Loop", BooleanType(), True),
        StructField("Sunrise_Sunset", StringType(), True),
        StructField("Civil_Twilight", StringType(), True),
        StructField("Nautical_Twilight", StringType(), True),
        StructField("Astronomical_Twilight", StringType(), True),
    ])

    df_raw = (
        spark.read.format("csv")
        .option("header", "true")
        .option("escape", '"')
        .schema(schema_acc)
        .load(data_path)
    )

    df_demo = (
        spark.read.format("csv")
        .option("header", "true")
        .option("inferSchema", "true")
        .load(demo_path)
    )
    return df_raw, df_demo


def transformar_y_enriquecer(df_raw, df_demo):
    # Limpieza de IDs, normalización de timestamps con nanosegundos (.000000000)
    df = (
        df_raw
        .filter(F.col("ID").isNotNull() & F.col("State").isNotNull())
        .dropDuplicates(["ID"])
        .withColumn("start_ts", F.to_timestamp(F.substring("Start_Time", 1, 19), "yyyy-MM-dd HH:mm:ss"))
        .withColumn("end_ts", F.to_timestamp(F.substring("End_Time", 1, 19), "yyyy-MM-dd HH:mm:ss"))
        .withColumn(
            "duration_raw_min",
            F.when(
                (F.col("end_ts").isNotNull()) & (F.col("start_ts").isNotNull()) & (F.col("end_ts") >= F.col("start_ts")),
                F.round((F.unix_timestamp("end_ts") - F.unix_timestamp("start_ts")) / 60.0, 2)
            ).otherwise(None)
        )
        .withColumn(
            "duration_clean_min",
            F.when(F.col("duration_raw_min") <= 1440.0, F.col("duration_raw_min")).otherwise(None)
        )
        .withColumn("year", F.year("start_ts"))
        .withColumn("month", F.month("start_ts"))
        .withColumn("hour", F.hour("start_ts"))
        .withColumn("day_of_week_num", F.dayofweek("start_ts"))
        .withColumn("weather_group", F.when(
            F.col("Weather_Condition").isin("Fair", "Clear"), "Despejado"
        ).when(
            F.col("Weather_Condition").isin("Mostly Cloudy", "Cloudy", "Partly Cloudy", "Overcast"), "Nublado"
        ).when(
            F.lower(F.col("Weather_Condition")).rlike("rain|drizzle|shower|thunder|t-storm|storm"), "Lluvia"
        ).when(
            F.lower(F.col("Weather_Condition")).rlike("fog|mist|haze|smoke|dust"), "Niebla"
        ).when(
            F.lower(F.col("Weather_Condition")).rlike("snow|ice|sleet|hail|wintry|freezing"), "Nieve/Hielo"
        ).otherwise("Otro"))
        .withColumn(
            "road_type",
            F.when(F.upper(F.col("Street")).rlike(r"\bI-\d+|INTERSTATE|FWY|EXPY|PKWY|TPKE"), "Autopista / Interstate")
            .when(F.upper(F.col("Street")).rlike(r"\bUS-\d+|\bSR-\d+|HWY|HIGHWAY|STATE ROUTE"), "Carretera / Highway")
            .when(F.upper(F.col("Street")).rlike(r"\bBLVD\b|\bAVE\b"), "Avenida / Boulevard")
            .when(F.upper(F.col("Street")).rlike(r"\bST\b|\bRD\b|\bDR\b|\bLN\b|\bWAY\b"), "Calle / Vía Urbana")
            .otherwise("Otra Vía")
        )
        .withColumn(
            "vehicle_kw",
            F.lower(F.regexp_extract(
                F.coalesce(F.col("Description"), F.lit("")),
                r"\b(suv|minivan|pickup|cargo van|van involved|semi|tractor|18-wheeler|tanker|trailer|truck|motorcycle|motorbike|scooter|school bus|transit bus|city bus|bus involved|bus accident|bicycle|bicyclist|cyclist|pedestrian|multi-?vehicle|car fire|car involved|car accident|sedan|vehicle involved|vehicle fire)\b",
                1
            ))
        )
        .withColumn(
            "vehicle_type",
            F.when(F.col("vehicle_kw").isin("suv", "minivan", "pickup", "cargo van", "van involved"), "SUV / Van / Pickup")
            .when(F.col("vehicle_kw").isin("semi", "tractor", "18-wheeler", "tanker", "trailer", "truck"), "Camión / Tráiler")
            .when(F.col("vehicle_kw").isin("motorcycle", "motorbike", "scooter"), "Motocicleta")
            .when(F.col("vehicle_kw").isin("school bus", "transit bus", "city bus", "bus involved", "bus accident"), "Autobús")
            .when(F.col("vehicle_kw").isin("bicycle", "bicyclist", "cyclist"), "Bicicleta")
            .when(F.col("vehicle_kw") == "pedestrian", "Peatón involucrado")
            .when(F.col("vehicle_kw") != "", "Automóvil / Multivehículo")
            .otherwise("No especificado")
        )
    )

    # Enriquecimiento demográfico por State (Left Join)
    df_enriched = df.join(F.broadcast(df_demo), on="State", how="left")
    return df_enriched


def exportar_spark_csv(df_spark, filename, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    rows = [r.asDict() for r in df_spark.collect()]
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=df_spark.columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[EXPORTADO Spark] {path}")


def main():
    args = parse_args()
    spark = crear_spark_session()
    df_raw, df_demo = extraer_datos(spark, args.data_path, args.demo_path)
    df_enriched = transformar_y_enriquecer(df_raw, df_demo)
    df_enriched.createOrReplaceTempView("accidents_enriched")

    # Consulta Spark SQL + Ventana: Top vía peligrosa por estado
    top_estados = spark.sql("""
        SELECT
            State,
            State_Name,
            Region,
            Population_2023,
            COUNT(*) AS total_accidentes,
            ROUND(COUNT(*) * 100000.0 / MAX(Population_2023), 2) AS tasa_x_100k_hab,
            ROUND(AVG(Severity), 3) AS severidad_promedio
        FROM accidents_enriched
        GROUP BY State, State_Name, Region, Population_2023
        ORDER BY total_accidentes DESC
        LIMIT 15
    """)
    exportar_spark_csv(top_estados, "spark_top15_estados_demografia.csv", args.output_dir)

    # Window function: Top 1 ciudad crítica por cada Región censal
    win_region = Window.partitionBy("Region").orderBy(F.col("total_accidentes").desc())
    top_ciudad_region = (
        df_enriched.filter(F.col("Region").isNotNull() & F.col("City").isNotNull())
        .groupBy("Region", "State", "City")
        .agg(F.count("*").alias("total_accidentes"))
        .withColumn("rank_regional", F.rank().over(win_region))
        .filter(F.col("rank_regional") <= 3)
        .orderBy("Region", "rank_regional")
    )
    exportar_spark_csv(top_ciudad_region, "spark_top3_ciudades_por_region.csv", args.output_dir)

    spark.stop()
    print("[OK] Pipeline PySpark finalizado.")


if __name__ == "__main__":
    main()
