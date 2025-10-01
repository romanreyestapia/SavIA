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
    Toma un DataFrame de ventas, lo pre-procesa, llama a la IA con datos agregados,
    y muestra el gráfico y el análisis de texto.
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
    
    # --- 💡 CAMBIO CRÍTICO: Pre-procesamiento de datos ANTES de llamar a la IA ---
    # Calculamos los totales mensuales nosotros mismos.
    df_historico_mensual = df_ventas.set_index("Fecha").resample("M").sum().reset_index()
    df_historico_mensual["Fecha"] = df_historico_mensual["Fecha"].dt.strftime('%Y-%m')
    df_historico_mensual = df_historico_mensual.rename(columns={"Ventas": "Total_Ventas_Mensual"})

    # Creamos un string limpio y resumido para la IA.
    datos_mensuales_string = df_historico_mensual.to_string(index=False)

    prompt = f"""
    # ROL Y PERSONALIDAD
    Eres SavIA, un socio estratégico y un aliado para el dueño de la PyME. Tu objetivo es empoderarlo.
    Tu tono debe ser colaborativo, cálido y alentador. Dirígete al usuario por su nombre: '{nombre_usuario}'.

    # MISIÓN
    Analiza los siguientes **totales de ventas mensuales** para {nombre_usuario}. Ya he procesado los datos diarios por ti.
    ---
    {datos_mensuales_string}
    ---

    Tu misión es realizar un análisis profundo basado en estos totales mensuales y presentar los resultados usando exactamente los siguientes títulos en formato Markdown:

    **1. Análisis de Tendencia General:** Describe la tendencia que observas en estos totales mensuales.
    **2. Pronóstico de Ventas:** Basado en la tendencia de los totales mensuales, genera la tabla de pronóstico para los próximos 3 meses. Los montos deben ser coherentes con la escala de los datos históricos. IMPORTANTE: Todos los montos deben ser números enteros y usar un punto (.) como separador de miles (ej: 2.719.847).
    **3. Insights Accionables (El Consejo del Socio):** Encabeza esta sección con '### 💡 ¡Hemos Encontrado Oportunidades para Ti, {nombre_usuario}!'. Proporciona un insight accionable basado en la tendencia general que has observado.

    ---
    # FORMATO DE SALIDA OBLIGATORIO
    Añade el bloque JSON. IMPORTANTE: Los valores de "Venta" deben ser enteros y SIN separador de miles en el JSON (ej: 2719847).
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

        texto_analisis = texto_respuesta.split("```json")[0].strip()

        separador_insights = f"### 💡 ¡Hemos Encontrado Oportunidades para Ti, {nombre_usuario}!"
        partes_del_analisis = texto_analisis.split(separador_insights, 1)

        if len(partes_del_analisis) == 2:
            parte_general, parte_insights = partes_del_analisis
            st.subheader("📊 Análisis General de tus Ventas")
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
            
            # Reutilizamos el DataFrame mensual que ya calculamos
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

