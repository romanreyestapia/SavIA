# app.py

import streamlit as st
import pandas as pd
import google.generativeai as genai
import io

# --- CONFIGURACIÓN DE LA PÁGINA Y LA API ---

# Título de la aplicación que se verá en el navegador
st.set_page_config(page_title="SavIA - Pronóstico de Ventas", page_icon="💡")

# Consejo de socio: NUNCA escribas tu API Key directamente en el código.
# Usaremos los "Secrets" de Streamlit.
# Cuando despliegues la app, configurarás este valor en la plataforma.
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Error al configurar la API de Google. Por favor, asegúrate de que la clave API esté configurada correctamente en los secretos de Streamlit.")
    st.stop()


# --- FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---

def generar_pronostico(df_ventas):
    """
    Toma un DataFrame de ventas, prepara el prompt y llama a la API de Gemini.
    """
    st.info("Procesando los datos y consultando a la IA... Esto puede tardar un momento.")
    
    # Convertimos el DataFrame a un string CSV para el prompt
    # Esto es más ligero que pasar un JSON gigante.
    datos_string = df_ventas.to_csv(index=False)

    # El "cerebro" de nuestra aplicación: el prompt
    # Aquí le decimos a la IA quién es y qué queremos que haga.
    prompt = f"""
    Eres SavIA, un analista de datos experto en pronósticos de ventas para PYMES.
    Tu rol es actuar como un socio estratégico que ayuda a los dueños de negocios a tomar mejores decisiones.

    Basado en los siguientes datos históricos de ventas en formato CSV:
    ---
    {datos_string}
    ---
    
    Por favor, realiza las siguientes tareas:
    1.  **Análisis de Tendencia:** Describe brevemente la tendencia principal que observas en los datos (crecimiento, decrecimiento, estacionalidad, etc.).
    2.  **Pronóstico de Ventas:** Genera un pronóstico de ventas para los próximos 3 meses. Presenta este pronóstico en una tabla clara en formato Markdown. La tabla debe tener dos columnas: 'Mes a Pronosticar' y 'Venta Estimada'.
    3.  **Insight Accionable:** Proporciona un insight o recomendación clave y accionable basada en el pronóstico. Por ejemplo, si se espera una alta demanda, recomienda preparar inventario.

    Tu respuesta debe ser profesional, clara y directa. Usa un tono amigable y de apoyo.
    """

    try:
        model = genai.GenerativeModel('gemini-1.0-pro')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Ocurrió un error al contactar con el modelo de IA: {e}")
        return None


# --- INTERFAZ DE USUARIO (LO QUE VE EL CLIENTE) ---

st.title("💡 SavIA: Tu Socio de Análisis de Datos")
st.header("MVP: Pronóstico de Ventas con IA")
st.write("Sube tu archivo de ventas en formato CSV para obtener un pronóstico para los próximos 3 meses.")

# Componente para subir el archivo
archivo_cargado = st.file_uploader(
    "Selecciona tu archivo CSV", 
    type=['csv'],
    help="El archivo debe tener dos columnas: 'Fecha' y 'Ventas'"
)

if archivo_cargado is not None:
    try:
        # Usamos Pandas para leer el archivo CSV
        df = pd.read_csv(archivo_cargado)
        
        st.success("¡Archivo cargado exitosamente!")
        st.write("**Vista Previa de tus Datos:**")
        st.dataframe(df.head()) # Muestra las primeras 5 filas

        # Botón para iniciar el análisis
        if st.button("✨ Generar Pronóstico"):
            with st.spinner('SavIA está pensando...'):
                resultado_ia = generar_pronostico(df)
            
            if resultado_ia:
                st.subheader("📈 Aquí está tu Análisis y Pronóstico")
                # Usamos st.markdown para que interprete el formato (negritas, tablas, etc.)
                st.markdown(resultado_ia)

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}. Asegúrate de que tenga las columnas 'Fecha' y 'Ventas'.")