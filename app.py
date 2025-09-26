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


# Reemplaza tu función generar_pronostico completa por esta:
def generar_pronostico(df_ventas, nombre_usuario="Emprendedor"):
    """
    Toma un DataFrame de ventas y el nombre del usuario, llama a la IA, procesa la respuesta
    y muestra tanto el gráfico como el análisis de texto.
    """
    # --- DICCIONARIOS DE LOCALIZACIÓN PARA EL GRÁFICO ---
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
    datos_string = df_ventas.to_csv(index=False)

    # --- PROMPT FINAL CON PERSONALIZACIÓN Y FORMATO DE NÚMEROS ---
    prompt = f"""
    # ROL Y PERSONALIDAD
    Eres SavIA, un socio estratégico y un aliado para el dueño de la PyME. Tu objetivo es empoderarlo.
    Tu tono debe ser colaborativo, cálido y alentador. Dirígete al usuario por su nombre: '{nombre_usuario}'.

    # MISIÓN
    Analiza los siguientes datos de ventas para {nombre_usuario}. Sigue estrictamente estos pasos:

    **Paso 0 - Entendimiento de Escala:** Suma las ventas diarias para obtener el total de cada mes histórico. Usa estos totales como base para tu pronóstico mensual.

    **Paso 1 - Análisis de Tendencia General:** Usando los totales mensuales, describe la tendencia general.

    **Paso 2 - Detección de Patrones Semanales:** Compara ventas de semana vs. fin de semana.

    **Paso 3 - Identificación de Anomalías:** Busca días con ventas inusuales.

    **Paso 4 - Pronóstico de Ventas:** Genera la tabla de pronóstico. IMPORTANTE: Todos los montos deben ser números enteros y usar un punto (.) como separador de miles (ej: 75.400).

    **Paso 5 - Insights Accionables:** Encabeza esta sección con '### 💡 ¡Hemos Encontrado Oportunidades para Ti, {nombre_usuario}!'.

    ---
    # FORMATO DE SALIDA OBLIGATORIO
    Añade el bloque JSON. IMPORTANTE: Los valores de "Venta" deben ser enteros y sin separador de miles en el JSON (ej: 75400).
    ```json
    {{
      "pronostico_json": [
        {{"Mes": "2025-12", "Venta": 15000}},
        {{"Mes": "2026-01", "Venta": 16000}},
        {{"Mes": "2026-02", "Venta": 17500}}
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

            # INICIO DE LA CORRECCIÓN ---
            # Definimos 'texto_analisis' PRIMERO.
            #  Dividimos la respuesta de la IA para obtener solo el análisis de texto y quitamos espacios extra
            texto_analisis = texto_respuesta.split("```json")[0].strip()

            # La señal que usaremos para dividir
            separador_insights = "### 💡 ¡Hemos Encontrado Oportunidades para Ti!"

            # Intentamos dividir el texto usando el separador. Esto creará una lista de "partes".
            partes_del_analisis = texto_analisis.split(separador_insights, 1)

            # Verificamos si la división fue exitosa (si la lista tiene 2 partes)
            if len(partes_del_analisis) == 2:
                # Si fue exitosa, la primera parte es el análisis general y la segunda son los insights.
                parte_general = partes_del_analisis[0]
                parte_insights = partes_del_analisis[1]

                # Mostramos la parte del análisis general
                st.subheader("📊 Análisis General de tus Ventas")
                st.markdown(parte_general)

                # Mostramos la sección de insights de forma destacada
                st.subheader("💡 ¡Hemos Encontrado Oportunidades para Ti!")
                st.markdown(parte_insights)

            else:
                # Si la división falló (solo obtuvimos 1 parte), no rompemos la app.
                # Simplemente mostramos el análisis completo como antes.
                st.subheader("📊 Análisis y Recomendaciones")
                st.markdown(texto_analisis)

            # --- FIN DEL BLOQUE DE CÓDIGO DEFENSIVO ---

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
            # ... (código anterior que prepara df_para_grafico)

            base = alt.Chart(df_para_grafico).encode(
                x=alt.X('Fecha:T', title='Mes', axis=alt.Axis(format='%b %Y')),
                y=alt.Y('Monto:Q', title='Monto de Venta ($)'),
                color=alt.Color('Leyenda:N', title='Métrica', scale=alt.Scale(domain=['Ventas Históricas', 'Pronóstico'], range=['#1f77b4', '#ff7f0e'])),
                tooltip=[alt.Tooltip('Fecha:T', title='Mes', format='%B de %Y'), alt.Tooltip('Monto:Q', title='Monto', format='$,.0f'), alt.Tooltip('Leyenda:N', title='Métrica')]
            )

            linea_historica = base.transform_filter(alt.datum.Leyenda == 'Ventas Históricas').mark_line(point=True)
            linea_pronostico = base.transform_filter(alt.datum.Leyenda == 'Pronóstico').mark_line(point=True, strokeDash=[5,5])

            # --- INICIO DE LA MODIFICACIÓN ---
            # Obtenemos la última fecha con datos históricos para dibujar la línea
            ultima_fecha_historica = df_historico_mensual['Fecha'].max()

            # Creamos la línea vertical (regla) en esa fecha
            linea_vertical = alt.Chart(pd.DataFrame({'fecha': [ultima_fecha_historica]})).mark_rule(color='gray', strokeWidth=1.5, strokeDash=[3,3]).encode(
                x='fecha:T'
            )
            # --- FIN DE LA MODIFICACIÓN ---

            # Unimos las dos líneas Y la nueva regla vertical en un solo gráfico
            chart = (linea_historica + linea_pronostico + linea_vertical).interactive()

            st.altair_chart(chart, use_container_width=True)

            # Código Nuevo (el reemplazo)
            # Dividimos la respuesta de la IA para obtener solo el análisis de texto
            texto_analisis = texto_respuesta.split("```json")[0]

            # La señal que buscará nuestro código
            separador_insights = "### 💡 ¡Hemos Encontrado Oportunidades para Ti!"

            # Verificamos si la señal de insights está en la respuesta
            if separador_insights in texto_analisis:
                # Dividimos el análisis en dos partes: antes y después de la señal
                parte_general, parte_insights = texto_analisis.split(separador_insights, 1)

                # Mostramos la parte del análisis general
                st.subheader("📊 Análisis General de tus Ventas")
                st.markdown(parte_general)

                # Mostramos la sección de insights de forma destacada
                st.subheader("💡 ¡Hemos Encontrado Oportunidades para Ti!")
                st.markdown(parte_insights)

            else:
                # Si por alguna razón la IA no usó el separador, mostramos todo como antes
                st.subheader("📊 Análisis y Recomendaciones")
                st.markdown(texto_analisis)

        else:
            # Si no encontramos el JSON, mostramos la respuesta completa como antes
            st.subheader("📊 Análisis y Recomendaciones")
            st.markdown(texto_respuesta)

    except Exception as e:
        st.error(
            f"Ocurrió un error al contactar con el modelo de IA o procesar la respuesta: {e}"
        )
        return None

    return None

# --- FIN DE LA MODIFICACIÓN ---
