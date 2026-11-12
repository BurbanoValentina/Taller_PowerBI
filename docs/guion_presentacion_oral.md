# Guion para Presentación Oral — Proyecto 3 (15 diapositivas · Duración: 10–12 minutos)

## Diapositiva 1 · Portada y Contexto (0:40 min)
> *"Buenos días/tardes. Hoy presentamos el Proyecto 3: Análisis de Accidentes de Tránsito en Zonas Urbanas, integrando el dataset abierto de Kaggle US Accidents con 7,728,394 registros (2016–2023) y datos demográficos del Censo EE.UU. 2023 mediante Python, PySpark, SQL, Power Query, Power BI y ANOVA."*

## Diapositiva 2 · Arquitectura ETL y Calidad de Datos (1:00 min)
> *"El primer reto fue el tamaño del CSV (~3.06 GB). Construimos un ETL por bloques de 500k filas en Python/PyArrow y su equivalente en PySpark y Power Query M. Corregimos 743,166 fechas con nanosegundos (.000000000), aislamos 34,981 cierres atípicos mayores a 24 horas y filtramos falsos positivos toponímicos ('I-80 Bus', 'Van Ness Ave') al extraer tipos de vehículo."*

## Diapositivas 3 y 4 · Estados, Ciudades y Tasa Demográfica (1:20 min)
> *"En el Requerimiento 1, California (1,741,433 accidentes) y Miami (186,768) lideran en volumen bruto. Sin embargo, al normalizar por población del Censo, South Carolina (7,119 x 100k hab.) y Oregón muestran mayor riesgo relativo per cápita."*

## Diapositiva 5 · Patrones Horarios y Semanales (0:45 min)
> *"Para los Requerimientos 2 y 6, se observa una curva bimodal laboral con pico a las 07:00h y liderazgo del día Viernes (17.68%). En fin de semana cae el volumen (15.9%), pero aumenta la severidad promedio."*

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
> *"Validamos nuestras hipótesis mediante ANOVA sobre millones de registros: la duración varía sustantivamente según severidad (F=86,966.7, η²=0.0328, Tukey significativo en los 6 pares) y el ANOVA factorial Clima × Franja confirma una interacción significativa (F=87.58): la lluvia agrava más de noche (2.279) mientras la nieve impacta más al mediodía (2.259)."*

## Diapositiva 15 · Conclusiones (0:40 min)
> *"En conclusión, integrar datos abiertos con demografía, ETL auditado, SQL, Python, Power BI y ANOVA permite focalizar operativos viales los viernes por la tarde en autopistas interestatales y activar alertas dinámicas según clima y horario. Muchas gracias."*
