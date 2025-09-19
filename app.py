# app.py

import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
import re
import json
import altair as alt

# --- CONFIGURACIÓN DE LA PÁGINA Y LA API ---

# Título de la aplicación que se verá en el navegador
st.set_page_config(
    page_title="SavIA - Pronóstico de Ventas", page_icon="Logo savIA.png"
)

# Consejo de socio: NUNCA escribas tu API Key directamente en el código.
# Usaremos los "Secrets" de Streamlit.
# Cuando despliegues la app, configurarás este valor en la plataforma.
# Mostramos el logo en la barra lateral
# st.sidebar.image("Logo savIA.png", width=100)
# st.sidebar.title("SavIA")

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error(
        "Error al configurar la API de Google. Por favor, asegúrate de que la clave API esté configurada correctamente en los secretos de Streamlit."
    )
    st.stop()


# --- FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---


def generar_pronostico(df_ventas):
    """
    Toma un DataFrame de ventas, llama a la IA, procesa la respuesta
    y muestra tanto el gráfico como el análisis de texto.
    """


    st.info("Procesando los datos y consultando a la IA... Esto puede tardar un momento.")

    # Asegurarnos de que la columna 'Fecha' sea del tipo datetime
    df_ventas["Fecha"] = pd.to_datetime(df_ventas["Fecha"], dayfirst=True)

    datos_string = df_ventas.to_csv(index=False)

    # --- INICIO DEL NUEVO PROMPT ---
    prompt = f"""
        Eres SavIA, un analista de datos de élite, especializado en encontrar insights accionables para PYMES. Tu tono es el de un socio estratégico, claro y directo.

        Analiza los siguientes datos históricos de ventas en formato CSV:
        ---
        {datos_string}
        ---
        
        Tu misión es realizar un análisis profundo siguiendo estrictamente estos 5 pasos:
        1.  **Análisis de Tendencia General:** Describe en una frase la tendencia general de las ventas en el periodo completo.
        2.  **Detección de Patrones Semanales:** Compara las ventas promedio de los días de semana (lunes-jueves) contra las ventas promedio del fin de semana (viernes-sábado). Cuantifica la diferencia en porcentaje si existe un patrón claro.
        3.  **Identificación de Anomalías:** Busca días o periodos cortos con ventas inusualmente altas o bajas que no sigan el patrón semanal. Menciona las fechas aproximadas si las encuentras.
        4.  **Pronóstico de Ventas:** Genera un pronóstico de ventas para los próximos 3 meses. Presenta este pronóstico en una tabla clara en formato Markdown con las columnas 'Mes a Pronosticar' y 'Venta Estimada'.
        5.  **Insights Accionables (Basados en EVIDENCIA):** Basándote exclusivamente en tus hallazgos de los puntos 2 y 3, proporciona dos (2) insights accionables y específicos.

        ---
        **Formato de Salida Obligatorio:**
        Después de todo tu análisis de texto, y sin añadir ninguna palabra introductoria extra, añade un bloque de código JSON limpio con los datos del pronóstico. La estructura debe ser la siguiente:
        ```json
        {{
        "pronostico_json": [
            {{"Mes": "2025-12", "Venta": 15000.50}},
            {{"Mes": "2026-01", "Venta": 16000.00}},
            {{"Mes": "2026-02", "Venta": 17500.75}}
        ]
        }}
        ```
        """
    # --- FIN DEL NUEVO PROMPT ---

    try:
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        response = model.generate_content(prompt)

        # --- NUEVO CÓDIGO PARA PROCESAR Y GRAFICAR ---
        texto_respuesta = response.text

        # 1. Extraer el bloque JSON del texto
        json_block_match = re.search(
            r"```json\n({.*?})\n```", texto_respuesta, re.DOTALL)

        if json_block_match:
            json_string = json_block_match.group(1)
            datos_pronostico = json.loads(json_string)

            # 2. Preparar los DataFrames para el gráfico
            df_pronostico = pd.DataFrame(datos_pronostico["pronostico_json"])
            df_pronostico["Fecha"] = pd.to_datetime(df_pronostico["Mes"])
            df_pronostico = df_pronostico.rename(columns={"Venta": "Pronóstico"})

            # Agrupar ventas históricas por mes
            df_historico_mensual = (
                df_ventas.set_index("Fecha").resample("M").sum().reset_index()
            )
            df_historico_mensual = df_historico_mensual.rename(
                columns={"Ventas": "Ventas Históricas"}
            )

            # 3. Unir y preparar los datos para el gráfico en español
            st.subheader("📈 Gráfico de Ventas Históricas y Pronóstico")

            df_completo = pd.merge(df_historico_mensual, df_pronostico, on='Fecha', how='outer')

# Reorganizamos la tabla para que Altair la entienda mejor
            df_para_grafico = df_completo.melt(id_vars='Fecha', var_name='Leyenda', value_name='Monto')

# 4. Crear el gráfico con Altair y títulos en español
            chart = alt.Chart(df_para_grafico).mark_line().encode(
                x=alt.X('Fecha:T', title='Mes'),
                y=alt.Y('Monto:Q', title='Monto de Venta ($)'),
                color=alt.Color('Leyenda:N', title='Métrica'),
                tooltip=[alt.Tooltip('Fecha:T', title='Mes'), alt.Tooltip('Monto:Q', title='Monto', format='$,.2f'), alt.Tooltip('Leyenda:N', title='Métrica')]
            ).interactive()

# 5. Mostrar el gráfico en Streamlit
            st.altair_chart(chart, use_container_width=True)
# --- INICIO DEL CÓDIGO AÑADIDO ---
# Después de mostrar el gráfico, extraemos y mostramos el análisis de texto.
            st.subheader("📊 Análisis y Recomendaciones")

# Dividimos la respuesta de la IA en el punto donde empieza el JSON
# y nos quedamos con la primera parte (el texto).
            texto_analisis = texto_respuesta.split("```json")[0]
            st.markdown(texto_analisis)
# --- FIN DEL CÓDIGO AÑADIDO ---                

        else:
            # Si no encontramos el JSON, mostramos la respuesta completa como antes
            st.subheader("📊 Análisis y Recomendaciones")
            st.markdown(texto_respuesta)

    except Exception as e:
        st.error(
            f"Ocurrió un error al contactar con el modelo de IA o procesar la respuesta: {e}"
        )
        return None

# --- FIN DE LA MODIFICACIÓN ---




# --- INTERFAZ DE USUARIO (LO QUE VE EL CLIENTE) ---

# --- TÍTULO PRINCIPAL CON LOGO ---

# Creamos dos columnas. El valor [1, 4] significa que la columna del título
# será 4 veces más ancha que la del logo. Puedes jugar con estos números.
col1, col2 = st.columns([1, 4])

# Usamos un bloque "with" para decirle a Streamlit qué va en cada columna.
with col1:
    st.image("Logo savIA.png", width=100)  # Ajusta el ancho a tu gusto

with col2:
    st.title("SavIA")
    # Para el subtítulo, usamos st.markdown para darle un estilo diferente
    st.markdown("#### Tu Socio de Análisis de Datos")


st.header("MVP: Pronóstico de Ventas con IA")
st.write(
    "Sube tu archivo de ventas en formato CSV para obtener un pronóstico para los próximos 3 meses."
)

# Componente para subir el archivo
archivo_cargado = st.file_uploader(
    "Selecciona tu archivo CSV",
    type=["csv"],
    help="El archivo debe tener dos columnas: 'Fecha' y 'Ventas'",
)

if archivo_cargado is not None:
    try:
        # Usamos Pandas para leer el archivo CSV
       # Primero, intentamos leer el CSV asumiendo que el separador es un punto y coma (;)
        # que es muy común en sistemas configurados en español.
        # El encoding='utf-8-sig' ayuda a eliminar caracteres invisibles al inicio del archivo.
        df = pd.read_csv(archivo_cargado, delimiter=';', encoding='utf-8-sig')

        # Si después de leerlo, el resultado es una tabla con una sola columna,
        # significa que el separador probablemente era una coma.
        if df.shape[1] == 1:
            # 'rebobinamos' el archivo para leerlo desde el principio de nuevo
            archivo_cargado.seek(0)
            df = pd.read_csv(archivo_cargado, delimiter=',', encoding='utf-8-sig')
        
        # Como medida de seguridad final, limpiamos los nombres de las columnas
        # para que sean consistentes.
        df.columns = df.columns.str.strip() # Quita espacios al inicio/final (ej: " Fecha " -> "Fecha")
        df.columns = df.columns.str.title() # Convierte a formato Título (ej: "fecha" -> "Fecha")

        st.success("¡Archivo cargado exitosamente!")
        st.write("**Vista Previa de tus Datos:**")
        st.dataframe(df.head())  # Muestra las primeras 5 filas

        # Botón para iniciar el análisis
        if st.button("✨ Generar Pronóstico"):
            with st.spinner("SavIA está pensando..."):
                resultado_ia = generar_pronostico(df)

            if resultado_ia:
                st.subheader("📈 Aquí está tu Análisis y Pronóstico")
                # Usamos st.markdown para que interprete el formato (negritas, tablas, etc.)
                st.markdown(resultado_ia)

    except Exception as e:
        st.error(
            f"Error al procesar el archivo: {e}. Asegúrate de que tenga las columnas 'Fecha' y 'Ventas'."
        )
