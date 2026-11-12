// ============================================================================
// PROYECTO 3: Análisis de Accidentes de Tránsito en Zonas Urbanas (US Accidents)
// Script Power Query (Lenguaje M) - ETL y Modelado en Power BI
// ============================================================================
// Descripción:
//   1. Extracción desde el dataset Kaggle (US_Accidents_March23.csv) y tabla
//      demográfica complementaria (us_state_demographics.csv).
//   2. Limpieza de tipos, normalización de fechas/horas (Start_Time, End_Time)
//      y cálculo de duración del incidente en minutos.
//   3. Agrupación climática estandarizada al español (Despejado, Nublado,
//      Lluvia, Niebla, Nieve/Hielo, Otro) coincidente con las vistas del .pbix.
//   4. Clasificación de tipo de vía (Autopista/Interstate, Avenida/Blvd,
//      Calle Urbana, Carretera/Highway, Camino/Road, Otros) y extracción básica
//      de categoría de vehículo desde Description.
//   5. Enriquecimiento demográfico por State (Population_2023, Región, Densidad).
// ============================================================================

let
    // ------------------------------------------------------------------------
    // FASE 1: EXTRACCIÓN (Ajustar RutaBase según entorno local)
    // ------------------------------------------------------------------------
    RutaDatos = "data\US_Accidents_March23.csv",
    RutaDemografia = "data\us_state_demographics.csv",

    OrigenRaw = Csv.Document(
        File.Contents(RutaDatos),
        [Delimiter = ",", Columns = 46, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Encabezados = Table.PromoteHeaders(OrigenRaw, [PromoteAllScalars = true]),

    // ------------------------------------------------------------------------
    // FASE 2: SELECCIÓN Y TIPADO ESTRICTO
    // ------------------------------------------------------------------------
    ColumnasSeleccionadas = Table.SelectColumns(
        Encabezados,
        {
            "ID", "Source", "Severity", "Start_Time", "End_Time",
            "Start_Lat", "Start_Lng", "Distance(mi)", "Description",
            "Street", "City", "County", "State", "Zipcode", "Timezone",
            "Temperature(F)", "Humidity(%)", "Pressure(in)",
            "Visibility(mi)", "Wind_Speed(mph)", "Precipitation(in)",
            "Weather_Condition", "Crossing", "Junction", "Railway",
            "Roundabout", "Stop", "Traffic_Signal", "Sunrise_Sunset"
        }
    ),

    TiposCambiados = Table.TransformColumnTypes(
        ColumnasSeleccionadas,
        {
            {"ID", type text},
            {"Source", type text},
            {"Severity", Int64.Type},
            {"Start_Time", type datetime},
            {"End_Time", type datetime},
            {"Start_Lat", type number},
            {"Start_Lng", type number},
            {"Distance(mi)", type number},
            {"Description", type text},
            {"Street", type text},
            {"City", type text},
            {"County", type text},
            {"State", type text},
            {"Timezone", type text},
            {"Temperature(F)", type number},
            {"Humidity(%)", type number},
            {"Pressure(in)", type number},
            {"Visibility(mi)", type number},
            {"Wind_Speed(mph)", type number},
            {"Precipitation(in)", type number},
            {"Weather_Condition", type text},
            {"Sunrise_Sunset", type text}
        },
        "en-US"
    ),

    // Eliminar posibles registros sin Start_Time o State válidos y duplicados por ID
    SinNulosCriticos = Table.SelectRows(
        TiposCambiados,
        each [ID] <> null and [Start_Time] <> null and [State] <> null and [State] <> ""
    ),
    SinDuplicados = Table.Distinct(SinNulosCriticos, {"ID"}),

    // ------------------------------------------------------------------------
    // FASE 3: VARIABLES TEMPORALES Y DURACIÓN DEL INCIDENTE
    // ------------------------------------------------------------------------
    ConFecha = Table.AddColumn(SinDuplicados, "Fecha", each DateTime.Date([Start_Time]), type date),
    ConAnio = Table.AddColumn(ConFecha, "Anio", each Date.Year([Fecha]), Int64.Type),
    ConMesNum = Table.AddColumn(ConAnio, "Mes_Num", each Date.Month([Fecha]), Int64.Type),
    ConMesNombre = Table.AddColumn(
        ConMesNum,
        "Mes_Nombre",
        each Date.MonthName([Fecha], "es-ES"),
        type text
    ),
    ConHora = Table.AddColumn(ConMesNombre, "Hora", each Time.Hour(DateTime.Time([Start_Time])), Int64.Type),
    ConHoraMinuto = Table.AddColumn(
        ConHora,
        "Hora_Dia_Time",
        each #time(Time.Hour(DateTime.Time([Start_Time])), Time.Minute(DateTime.Time([Start_Time])), 0),
        type time
    ),
    ConDiaSemana = Table.AddColumn(
        ConHoraMinuto,
        "Dia_Semana",
        each Date.DayOfWeekName([Fecha], "es-ES"),
        type text
    ),
    ConDiaOrden = Table.AddColumn(
        ConDiaSemana,
        "Dia_Semana_Orden",
        each Date.DayOfWeek([Fecha], Day.Sunday) + 1,
        Int64.Type
    ),
    ConEsFinDeSemana = Table.AddColumn(
        ConDiaOrden,
        "Es_Fin_De_Semana",
        each if [Dia_Semana_Orden] = 1 or [Dia_Semana_Orden] = 7 then 1 else 0,
        Int64.Type
    ),

    // Duración en minutos (bruta para auditoría y filtrada <= 1440 min para análisis limpio)
    ConDuracionMin = Table.AddColumn(
        ConEsFinDeSemana,
        "Duracion_Min",
        each
            let
                diff = Duration.TotalMinutes([End_Time] - [Start_Time])
            in
                if diff >= 0 then Number.Round(diff, 2) else null,
        type number
    ),

    // ------------------------------------------------------------------------
    // FASE 4: AGRUPACIÓN CLIMÁTICA (6 CATEGORÍAS ESTANDARIZADAS EN ESPAÑOL)
    // ------------------------------------------------------------------------
    ConClimaGrupo = Table.AddColumn(
        ConDuracionMin,
        "Clima_Grupo",
        each
            let
                w = Text.Lower(Text.Trim(if [Weather_Condition] = null then "" else [Weather_Condition]))
            in
                if w = "" then "Otro"
                else if Text.Contains(w, "snow") or Text.Contains(w, "ice") or Text.Contains(w, "sleet")
                     or Text.Contains(w, "hail") or Text.Contains(w, "wintry") or Text.Contains(w, "freezing") then "Nieve/Hielo"
                else if Text.Contains(w, "rain") or Text.Contains(w, "drizzle") or Text.Contains(w, "shower")
                     or Text.Contains(w, "thunder") or Text.Contains(w, "t-storm") or Text.Contains(w, "storm") then "Lluvia"
                else if Text.Contains(w, "fog") or Text.Contains(w, "mist") or Text.Contains(w, "haze")
                     or Text.Contains(w, "smoke") or Text.Contains(w, "dust") or Text.Contains(w, "ash") then "Niebla"
                else if Text.Contains(w, "cloud") or Text.Contains(w, "overcast") then "Nublado"
                else if Text.Contains(w, "clear") or Text.Contains(w, "fair") then "Despejado"
                else "Otro",
        type text
    ),

    // ------------------------------------------------------------------------
    // FASE 5: CLASIFICACIÓN DE TIPO DE VÍA Y TIPO DE VEHÍCULO (DESDE DESCRIPTION)
    // ------------------------------------------------------------------------
    ConTipoVia = Table.AddColumn(
        ConClimaGrupo,
        "Tipo_Via",
        each
            let
                s = Text.Upper(Text.Trim(if [Street] = null then "" else [Street]))
            in
                if s = "" then "Sin dato"
                else if Text.Contains(s, "I-") or Text.Contains(s, "INTERSTATE") or Text.Contains(s, "FWY")
                     or Text.Contains(s, "EXPY") or Text.Contains(s, "PKWY") or Text.Contains(s, "TPKE") then "Autopista / Interstate"
                else if Text.Contains(s, "US-") or Text.Contains(s, "HWY") or Text.Contains(s, "SR-")
                     or Text.Contains(s, "RT-") or Text.Contains(s, "STATE ROUTE") then "Carretera / Highway"
                else if Text.Contains(s, "BLVD") or Text.Contains(s, "AVE") then "Avenida / Boulevard"
                else if Text.Contains(s, "ST") or Text.Contains(s, "RD") or Text.Contains(s, "DR")
                     or Text.Contains(s, "LN") or Text.Contains(s, "WAY") then "Calle / Vía Urbana"
                else "Otra Vía",
        type text
    ),

    ConVehiculo = Table.AddColumn(
        ConTipoVia,
        "Tipo_Vehiculo",
        each
            let
                d = Text.Lower(if [Description] = null then "" else [Description])
            in
                if Text.Contains(d, "suv") or Text.Contains(d, "minivan") or Text.Contains(d, "pickup")
                   or Text.Contains(d, "cargo van") or Text.Contains(d, "van involved") then "SUV / Van / Pickup"
                else if Text.Contains(d, "semi") or Text.Contains(d, "tractor") or Text.Contains(d, "18-wheeler")
                   or Text.Contains(d, "tanker") or Text.Contains(d, "trailer")
                   or (Text.Contains(d, "truck") and not Text.Contains(d, "truck route") and not Text.Contains(d, "truck stop")) then "Camión / Tráiler"
                else if Text.Contains(d, "motorcycle") or Text.Contains(d, "motorbike") or Text.Contains(d, "scooter") then "Motocicleta"
                else if Text.Contains(d, "school bus") or Text.Contains(d, "transit bus") or Text.Contains(d, "city bus")
                   or Text.Contains(d, "bus involved") or Text.Contains(d, "bus accident") then "Autobús"
                else if Text.Contains(d, "bicycle") or Text.Contains(d, "bicyclist") or Text.Contains(d, "cyclist") then "Bicicleta"
                else if Text.Contains(d, "pedestrian") then "Peatón involucrado"
                else if Text.Contains(d, "multi-vehicle") or Text.Contains(d, "multivehicle") or Text.Contains(d, "vehicle involved")
                   or Text.Contains(d, "car fire") or Text.Contains(d, "car accident") or Text.Contains(d, "sedan") then "Automóvil / Multivehículo"
                else "No especificado",
        type text
    ),

    // ------------------------------------------------------------------------
    // FASE 6: INTEGRACIÓN DEMOGRÁFICA (CENSO EE.UU. POR ESTADO)
    // ------------------------------------------------------------------------
    DemografiaRaw = Csv.Document(
        File.Contents(RutaDemografia),
        [Delimiter = ",", Columns = 6, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    DemografiaHeaders = Table.PromoteHeaders(DemografiaRaw, [PromoteAllScalars = true]),
    DemografiaTyped = Table.TransformColumnTypes(
        DemografiaHeaders,
        {
            {"State", type text},
            {"State_Name", type text},
            {"Region", type text},
            {"Population_2023", Int64.Type},
            {"Area_SqMi", Int64.Type},
            {"Density_Per_SqMi", type number}
        },
        "en-US"
    ),

    JoinDemografia = Table.NestedJoin(
        ConVehiculo, {"State"},
        DemografiaTyped, {"State"},
        "DimDemografia", JoinKind.LeftOuter
    ),
    ExpandDemografia = Table.ExpandTableColumn(
        JoinDemografia,
        "DimDemografia",
        {"State_Name", "Region", "Population_2023", "Density_Per_SqMi"},
        {"State_Name", "Region", "Population_2023", "Density_Per_SqMi"}
    )
in
    ExpandDemografia
