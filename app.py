# app.py

import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
import re
import json
import altair as alt

# --- CONFIGURACIÓN DE LA PÁGINA Y LA API ---

st.set_page_config(
    page_title="SavIA - Pronóstico de Ventas", page_icon="Logo savIA.png"
)

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error(
        f"Error al configurar la API de Google. Por favor, asegúrate de que la clave API esté configurada correctamente en los secretos de Streamlit. Detalle: {e}"
    )
    st.stop()


# --- FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---
def generar_pronostico(df_ventas, nombre_usuario="Emprendedor"):
    """
    Toma un DataFrame de ventas, lo pre-procesa en resúmenes mensuales y diarios,
    llama a la IA con ambos resúmenes, y muestra el gráfico y el análisis.
    """
    es_locale = {
        "dateTime": "%A, %e de %B de %Y, %H:%M:%S", "date": "%d/%m/%Y", "time": "%H:%M:%S",
        "periods": ["AM", "PM"], "days": ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"],
        "shortDays": ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"],
        "months": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
        "shortMonths": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    }
    es_number_locale = {
        "decimal": ",", "thousands": ".", "grouping": [3], "currency": ["$", ""]
    }
    alt.renderers.set_embed_options(timeFormatLocale=es_locale, numberFormatLocale=es_number_locale)
    
    st.info(f"Preparando el análisis para {nombre_usuario}... Esto puede tardar un momento.")
    
    df_ventas["Fecha"] = pd.to_datetime(df_ventas["Fecha"], dayfirst=True)
    
    # --- 💡 CAMBIO LÓGICO: Pre-procesamiento de TRES resúmenes ---
    
    # RESUMEN 1: Totales mensuales (para el pronóstico y la tendencia general)
    df_historico_mensual = df_ventas.set_index("Fecha").resample("M").sum().reset_index()
    df_historico_mensual["Fecha"] = df_historico_mensual["Fecha"].dt.strftime('%Y-%m')
    df_historico_mensual = df_historico_mensual.rename(columns={"Ventas": "Total_Ventas_Mensual"})
    datos_mensuales_string = df_historico_mensual.to_string(index=False)

    # RESUMEN 2: Patrones por día de la semana (para los insights de patrones)
    df_ventas['Dia_Semana_en'] = df_ventas['Fecha'].dt.day_name()
    dias_map = {
        'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
        'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df_ventas['Dia_Semana'] = df_ventas['Dia_Semana_en'].map(dias_map)
    dias_ordenados = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    ventas_por_dia = df_ventas.groupby('Dia_Semana')['Ventas'].mean().round(0).reindex(dias_ordenados)
    resumen_diario_string = ventas_por_dia.to_string()

    # RESUMEN 3: Detección de Anomalías (para el análisis de eventos)
    media_ventas = df_ventas['Ventas'].mean()
    std_ventas = df_ventas['Ventas'].std()
    # Definimos umbral de anomalía como ventas 1.5 desviaciones estándar sobre la media
    umbral_anomalia = media_ventas + 1.5 * std_ventas
    picos_venta = df_ventas[df_ventas['Ventas'] > umbral_anomalia].nlargest(5, 'Ventas')
    
    if not picos_venta.empty:
        anomalias_string = "Se detectaron los siguientes días con picos de venta notables:\n"
        picos_venta['Fecha_str'] = picos_venta['Fecha'].dt.strftime('%d de %B')
        anomalias_string += picos_venta[['Fecha_str', 'Ventas']].to_string(index=False, header=False)
    else:
        anomalias_string = "No se detectaron picos de venta estadísticamente significativos en este periodo."

    # --- 💡 CAMBIO CRÍTICO: Traducción manual de los días de la semana ---
    # Obtenemos el nombre del día en inglés (que siempre funciona)
    df_ventas['Dia_Semana_en'] = df_ventas['Fecha'].dt.day_name()
    # Creamos un diccionario para traducir
    dias_map = {
        'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
        'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    # Aplicamos la traducción para crear la columna en español
    df_ventas['Dia_Semana'] = df_ventas['Dia_Semana_en'].map(dias_map)
    
    ventas_por_dia = df_ventas.groupby('Dia_Semana')['Ventas'].mean().round(0).sort_values(ascending=False)
    resumen_diario_string = ventas_por_dia.to_string()

    prompt = f"""
    # ROL Y PERSONALIDAD
    Eres SavIA, un socio estratégico y un aliado para el dueño de la PyME. Tu objetivo es empoderarlo.
    Tu tono debe ser colaborativo, cálido y alentador. Dirígete al usuario por su nombre: '{nombre_usuario}'.

    # MISIÓN
    He pre-procesado los datos para ti en tres resúmenes. Tu misión es analizar cada uno para su propósito específico.

    **Resumen 1: Totales Mensuales (para el pronóstico y la tendencia)**
    ---
    {datos_mensuales_string}
    ---

    **Resumen 2: Promedio de Ventas por Día de la Semana (para los patrones)**
    ---
    {resumen_diario_string}
    ---

    **Resumen 3: Días con Picos de Venta Notables (para las anomalías)**
    ---
    {anomalias_string}
    ---

    Ahora, presenta los resultados usando **exactamente** los siguientes títulos en formato Markdown:

    **1. Análisis de Tendencia General:** Basado **únicamente en el Resumen 1**, describe la tendencia que observas en los totales mensuales.

    **2. Análisis de Anomalías:** Basado **únicamente en el Resumen 3**, comenta sobre los días con picos de venta. Si se detectaron, sugiere qué pudo haberlos causado (ej: eventos, promociones exitosas, fechas especiales).

    **3. Pronóstico de Ventas:** Basado **únicamente en el Resumen 1**, genera la tabla de pronóstico para los próximos 3 meses. Los montos deben ser coherentes con la escala de los datos mensuales. IMPORTANTE: Todos los montos deben ser números enteros y usar un punto (.) como separador de miles (ej: 2.719.847).

    **4. Insights Accionables (El Consejo del Socio):** Encabeza esta sección con '### 💡 ¡Hemos Encontrado Oportunidades para Ti, {nombre_usuario}!'. Basado **en el Resumen 2 y 3**, proporciona un insight accionable. No te limites a la recomendación general; ofrécele al usuario **2 o 3 ideas concretas de campañas de marketing o acciones de bajo a mediano costo**. Por ejemplo: "Viendo que los sábados son tu día más fuerte, podrías implementar una campaña de 'Sábado Gigante' en Instagram con un descuento flash que solo dure 3 horas para generar urgencia y atraer más clientes ese día."

    # FORMATO DE SALIDA OBLIGATORIO
    Añade el bloque JSON. Los valores de "Venta" deben ser enteros y SIN separador de miles en el JSON (ej: 2719847).
    ```json
    {{
      "pronostico_json": [
        {{"Mes": "2025-10", "Venta": 2800000}},
        {{"Mes": "2025-11", "Venta": 2900000}},
        {{"Mes": "2025-12", "Venta": 3000000}}
      ]
    }}
    ```
    """
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        texto_respuesta = response.text

        # ... (El resto del código para mostrar el texto y el gráfico se mantiene igual) ...
        # ... (No necesita cambios ya que la lógica de parseo es la misma) ...

        texto_analisis = texto_respuesta.split("```json")[0].strip()
        separador_insights = f"### 💡 ¡Hemos Encontrado Oportunidades para Ti, {nombre_usuario}!"
        partes_del_analisis = texto_analisis.split(separador_insights, 1)

        if len(partes_del_analisis) == 2:
            parte_general, parte_insights = partes_del_analisis
            st.subheader("📊 Análisis General y Pronóstico")
            st.markdown(parte_general)
            st.subheader(f"💡 ¡Hemos Encontrado Oportunidades para Ti, {nombre_usuario}!")
            st.markdown(parte_insights)
        else:
            st.subheader("📊 Análisis y Recomendaciones")
            st.markdown(texto_analisis)

        json_block_match = re.search(r"```json\n({.*?})\n```", texto_respuesta, re.DOTALL)
        if json_block_match:
            json_string = json_block_match.group(1)
            datos_pronostico = json.loads(json_string)
            
            df_pronostico = pd.DataFrame(datos_pronostico["pronostico_json"])
            df_pronostico["Fecha"] = pd.to_datetime(df_pronostico["Mes"])
            df_pronostico = df_pronostico.rename(columns={"Venta": "Pronóstico"})
            
            df_historico_mensual_para_grafico = df_ventas.set_index("Fecha").resample("M").sum().reset_index()
            df_historico_mensual_para_grafico = df_historico_mensual_para_grafico.rename(columns={"Ventas": "Ventas Históricas"})

            st.subheader("📈 Gráfico de Ventas Históricas y Pronóstico")
            df_completo = pd.merge(df_historico_mensual_para_grafico, df_pronostico, on="Fecha", how="outer")
            df_para_grafico = df_completo.melt(id_vars="Fecha", var_name="Leyenda", value_name="Monto")

            base = alt.Chart(df_para_grafico).encode(
                x=alt.X("Fecha:T", title="Mes", axis=alt.Axis(format="%b %Y")),
                y=alt.Y("Monto:Q", title="Monto de Venta ($)"),
                color=alt.Color("Leyenda:N", title="Métrica", scale=alt.Scale(domain=["Ventas Históricas", "Pronóstico"], range=["#1f77b4", "#ff7f0e"])),
                tooltip=[alt.Tooltip("Fecha:T", title="Mes", format="%B de %Y"), alt.Tooltip("Monto:Q", title="Monto", format="$,.0f"), alt.Tooltip("Leyenda:N", title="Métrica")]
            )

            linea_historica = base.transform_filter(alt.datum.Leyenda == "Ventas Históricas").mark_line(point=True)
            linea_pronostico = base.transform_filter(alt.datum.Leyenda == "Pronóstico").mark_line(point=True, strokeDash=[5, 5])
            
            ultima_fecha_historica = df_historico_mensual_para_grafico["Fecha"].max()
            linea_vertical = alt.Chart(pd.DataFrame({"fecha": [ultima_fecha_historica]})).mark_rule(color="gray", strokeWidth=1.5, strokeDash=[3, 3]).encode(x="fecha:T")
            
            chart = (linea_historica + linea_pronostico + linea_vertical).interactive()
            st.altair_chart(chart, use_container_width=True)
            
    except Exception as e:
        st.error(f"Ocurrió un error al contactar con el modelo de IA o procesar la respuesta: {e}")
        return None

# --- INTERFAZ DE USUARIO (LO QUE VE EL CLIENTE) ---
col1, col2 = st.columns([1, 4])

with col1:
    st.image("Logo savIA.png", width=100)

with col2:
    st.title("SavIA")
    st.markdown("#### Tu Socio de Análisis de Datos")

nombre_usuario = st.text_input("Escribe tu nombre o el de tu negocio:", "Emprendedor")

st.header("MVP: Pronóstico de Ventas con IA")
st.write(
    "Sube tu archivo de ventas en formato CSV para obtener un pronóstico para los próximos 3 meses."
)

archivo_cargado = st.file_uploader(
    "Selecciona tu archivo CSV",
    type=["csv"],
    help="El archivo debe tener dos columnas: 'Fecha' y 'Ventas'",
)

if archivo_cargado is not None:
    try:
        df = pd.read_csv(archivo_cargado, delimiter=';', encoding='utf-8-sig')
        if df.shape[1] == 1:
            archivo_cargado.seek(0)
            df = pd.read_csv(archivo_cargado, delimiter=',', encoding='utf-8-sig')
        
        df.columns = df.columns.str.strip()
        df.columns = df.columns.str.title()

        st.success("¡Archivo cargado exitosamente!")
        st.write("**Vista Previa de tus Datos:**")
        st.dataframe(df.head())

        if st.button("✨ Generar Pronóstico"):
            with st.spinner(f"SavIA está pensando, {nombre_usuario}..."):
                generar_pronostico(df, nombre_usuario)

    except Exception as e:
        st.error(
            f"Error al procesar el archivo: {e}. Asegúrate de que tenga las columnas 'Fecha' y 'Ventas'."
        )


