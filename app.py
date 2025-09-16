# app.py

import streamlit as st
import pandas as pd
import google.generativeai as genai
import io

# --- CONFIGURACIÓN DE LA PÁGINA Y LA API ---

# Título de la aplicación que se verá en el navegador
st.set_page_config(page_title="SavIA - Pronóstico de Ventas", page_icon="Logo savIA.png")

# Consejo de socio: NUNCA escribas tu API Key directamente en el código.
# Usaremos los "Secrets" de Streamlit.
# Cuando despliegues la app, configurarás este valor en la plataforma.
# Mostramos el logo en la barra lateral
#st.sidebar.image("Logo savIA.png", width=100)
#st.sidebar.title("SavIA")

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
    
    datos_string = df_ventas.to_csv(index=False)

    # --- INICIO DE LA MODIFICACIÓN ---
    # Reemplazaremos el prompt antiguo por este, mucho más detallado y exigente.

    prompt = f"""
    Eres SavIA, un analista de datos de élite, especializado en encontrar insights accionables para PYMES. Tu tono es el de un socio estratégico, claro y directo.

    Analiza los siguientes datos históricos de ventas en formato CSV:
    ---
    {datos_string}
    ---
    
    Tu misión es realizar un análisis profundo siguiendo estrictamente estos 5 pasos:

    1.  **Análisis de Tendencia General:** Describe en una frase la tendencia general de las ventas en el periodo completo (ej: crecimiento constante, decrecimiento, estancamiento).

    2.  **Detección de Patrones Semanales:** Compara las ventas promedio de los días de semana (lunes-jueves) contra las ventas promedio del fin de semana (viernes-sábado). Cuantifica la diferencia en porcentaje si existe un patrón claro.

    3.  **Identificación de Anomalías:** Busca días o periodos cortos con ventas inusualmente altas o bajas que no sigan el patrón semanal. Menciona las fechas aproximadas si las encuentras.

    4.  **Pronóstico de Ventas:** Genera un pronóstico de ventas para los próximos 3 meses. Presenta este pronóstico en una tabla clara en formato Markdown con las columnas 'Mes a Pronosticar' y 'Venta Estimada'.

    5.  **Insights Accionables (Basados en EVIDENCIA):** Basándote **exclusivamente** en tus hallazgos de los puntos 2 (patrones semanales) y 3 (anomalías), proporciona dos (2) insights accionables y específicos para el dueño del negocio. No des consejos genéricos de inventario. Cada insight debe estar directamente ligado a la evidencia que encontraste.
    """
    # --- FIN DE LA MODIFICACIÓN ---

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Ocurrió un error al contactar con el modelo de IA: {e}")
        return None


# --- INTERFAZ DE USUARIO (LO QUE VE EL CLIENTE) ---

# --- TÍTULO PRINCIPAL CON LOGO ---

# Creamos dos columnas. El valor [1, 4] significa que la columna del título
# será 4 veces más ancha que la del logo. Puedes jugar con estos números.
col1, col2 = st.columns([1, 4])

# Usamos un bloque "with" para decirle a Streamlit qué va en cada columna.
with col1:
    st.image("Logo savIA.png", width=100) # Ajusta el ancho a tu gusto

with col2:
    st.title("SavIA")
    # Para el subtítulo, usamos st.markdown para darle un estilo diferente
    st.markdown("#### Tu Socio de Análisis de Datos")


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