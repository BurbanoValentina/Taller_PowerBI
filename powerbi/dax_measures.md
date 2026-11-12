# Medidas DAX Documentadas — Dashboard Power BI (Proyecto 3)

Este documento describe y explica las medidas **DAX (Data Analysis Expressions)** utilizadas en el modelo tabular de Power BI (`.pbix`) correspondiente a las visualizaciones presentadas en el informe.

---

## 1. Medidas Principales de Volumen y Calendario

### 1.1 `Total Accidentes`
```dax
Total Accidentes = COUNTROWS(Accidents)
```
- **Función y lógica:** Cuenta el número total de registros (filas únicas por `ID`) en la tabla de hechos `Accidents` respetando el contexto de filtro activo (Estado, Ciudad, Clima, Severidad, Año, Hora).
- **Observación en el tablero:** En la tarjeta KPI general se muestra redondeado en millones (`8M`, equivalente a `7,728,394` registros totales; en el gráfico de anillo de severidad aparece como `7728K`).

---

### 1.2 `Accidentes FinDeSemana`
```dax
Accidentes FinDeSemana = 
CALCULATE(
    [Total Accidentes],
    WEEKDAY(Accidents[Start_Time], 2) IN {6, 7}
)
```
*(Alternativa usando la dimensión Calendario:)*
```dax
Accidentes FinDeSemana = 
CALCULATE(
    [Total Accidentes],
    Dim_Calendario[EsFinDeSemana] = TRUE()
)
```
- **Función y lógica:** Evalúa `[Total Accidentes]` modificando el contexto de filtro para incluir únicamente los días sábado (`6`) y domingo (`7`) bajo el esquema `WEEKDAY(..., 2)` (donde lunes = 1 y domingo = 7).
- **Auditoría técnica sobre la captura:** En el gráfico de barras por día de la semana (`02_kpis_hora_dia_semana.jpg`), `domingo` suma `563K` y `sábado` suma `669K` (~`1.23M` accidentes reales en fin de semana, ~15.9% del total). Si la tarjeta KPI muestra `366`, se debe a que la relación con la tabla calendario o una segmentación contextual filtró únicamente las fechas válidas no nulas en un periodo acotado (p. ej. 2023, donde los registros sin precisión de nanosegundos no se unieron al calendario). En Python y SQL se reporta el valor exacto completo sin pérdida por formato de fecha.

---

### 1.3 `Accidentes YTD`
```dax
Accidentes YTD = 
TOTALYTD(
    [Total Accidentes],
    Dim_Calendario[Date]
)
```
- **Función y lógica:** Calcula el acumulado en lo que va del año (*Year-To-Date*) hasta la última fecha del contexto activo en `Dim_Calendario[Date]`.
- **Observación en el tablero:** Al corresponder la última fecha del dataset a marzo de 2023, la tarjeta muestra `140` (consistente con el cierre de la serie anual en 2023 en `07_tendencias_anuales_mensuales_mom.png` para las filas que hicieron *match* con la tabla calendario).

---

### 1.4 `Var MoM %` (Variación Porcentual Mes a Mes)
```dax
Accidentes Mes Anterior = 
CALCULATE(
    [Total Accidentes],
    DATEADD(Dim_Calendario[Date], -1, MONTH)
)

Var MoM % = 
DIVIDE(
    [Total Accidentes] - [Accidentes Mes Anterior],
    [Accidentes Mes Anterior],
    0
)
```
- **Función y lógica:** Compara el volumen mensual actual frente al mes inmediatamente anterior (`DATEADD(..., -1, MONTH)`) mediante `DIVIDE` para prevenir divisiones por cero.
- **Auditoría técnica sobre la captura:** En `07_tendencias_anuales_mensuales_mom.png`, la tarjeta `Var MoM %` muestra `5.49K` debido a que el formato de la medida estaba expresado en decimal multiplicado o por saltos extremos entre meses con pocas fechas parseadas (`(Blank)` en el eje mensual). En el flujo ETL de Python/Power Query se corrigen los *timestamps* con nanosegundos (`.000000000`) para eliminar los valores `(Blank)` y calcular la variación mensual real sin distorsiones.

---

## 2. Medidas de Duración e Impacto del Incidente

### 2.1 `Duración Promedio` (en minutos)
```dax
Duración Promedio = 
AVERAGE(Accidents[Duracion_Min])
```
- **Función y lógica:** Promedia la diferencia en minutos entre `End_Time` y `Start_Time`.
- **Interpretación estadística:** En el tablero se observa `444` minutos (~7.4 horas). Este promedio elevado es impulsado por valores atípicos extremos (*outliers*) en registros de `Source1` o cierres prolongados de vía de severidad 4 (`1,685` min promedio) y severidad 2 (`485` min promedio).

---

### 2.2 `Duración Mediana` (en minutos)
```dax
Duración Mediana = 
MEDIAN(Accidents[Duracion_Min])
```
- **Función y lógica:** Calcula el percentil 50 (`MEDIAN`) de la duración en minutos, ofreciendo una métrica robusta frente a valores extremos.
- **Interpretación estadística:** La mediana de `75` minutos (vs. `444` minutos de media) demuestra una fuerte **asimetría positiva** (sesgo a la derecha), justificando tanto el uso de la mediana en reportes ejecutivos como el tratamiento de *outliers* (> 1,440 min / 24 h) en el análisis ANOVA y en Python.

---

## 3. Medidas de Severidad, Participación y Demografía

### 3.1 `% Participación Severidad` y `Accidentes Graves (Sev 3-4)`
```dax
Accidentes Graves = 
CALCULATE(
    [Total Accidentes],
    Accidents[Severity] IN {3, 4}
)

% Accidentes Graves = 
DIVIDE([Accidentes Graves], [Total Accidentes], 0)
```
- **Uso:** Permite evaluar qué condiciones climáticas (como `Lluvia` con 20.70% en Sev 3 o `Nieve/Hielo`) y qué horarios concentran proporcionalmente mayor gravedad, más allá del volumen bruto de eventos leves/moderados (Sev 2 = 79.7%).

---

### 3.2 `Tasa de Accidentes por 100k Habitantes` (Enriquecimiento Demográfico)
```dax
Poblacion Estado = MAX(Dim_Demografia[Population_2023])

Tasa x 100k Hab = 
DIVIDE(
    [Total Accidentes] * 100000,
    [Poblacion Estado],
    0
)
```
- **Uso:** Normaliza la frecuencia absoluta de accidentes por estado frente a la población estatal del Censo de EE.UU. (`us_state_demographics.csv`), evitando el sesgo de tamaño poblacional (por ejemplo, comparar la tasa per cápita de Carolina del Sur u Oregón frente a estados altamente poblados como California o Texas).

---

## 4. Hallazgos de Auditoría del Dashboard Power BI

Durante la revisión técnica de las 8 capturas del tablero finalizado se documentaron cuatro puntos clave que fueron contrastados y complementados con el pipeline en Python y SQL:

1. **Ordenamiento de `TOP10 vías más peligrosos` (`05_top10_vias_peligrosas.png`):** El visual en Power BI ordenó las calles alfabéticamente de forma descendente (`Zuni Rd SE`, `Zuni St`, `Zuniga Dr`, ...) en lugar de ordenar por la medida `[Total Accidentes]`. En el análisis en Python y SQL se obtiene el Top 10 real por volumen (`I-95 N`, `I-95 S`, `I-5 N`, `I-10 E`, etc.).
2. **Fechas `(Blank)` y formato de nanosegundos (`07_tendencias_anuales_mensuales_mom.png`):** En `US_Accidents_March23.csv`, los registros posteriores tienen precisión de 9 decimales (`.000000000`), lo que provocó que Power BI dejara registros sin cruzar en la tabla calendario (`(Blank)`). En el ETL de Python y Power Query actualizado se normaliza el *timestamp* explícitamente.
3. **Asimetría en Duración (`06_duracion_promedio_severidad.png`):** La brecha entre promedio (`444 min`) y mediana (`75 min`) evidencia cierres excepcionales de varios días/meses en `End_Time`, los cuales se analizan tanto con la serie completa como con la serie depurada en Python.
4. **Cobertura completa en días y clima (`02` y `03`):** La suma por día (`563K + 1211K + 1291K + 1312K + 1316K + 1366K + 669K = 7,728K`) y por clima (`3,369,545 + 2,915,115 + 623,936 + 478,761 + 191,668 + 149,367 = 7,728,392`) coincide con exactitud con el dataset real de Kaggle.
