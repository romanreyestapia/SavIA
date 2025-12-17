# ==================================================
# SavIA - MVP Pronóstico de Ventas con IA + Baseline
# ==================================================

import streamlit as st
import pandas as pd
import google.generativeai as genai
import re
import json
import altair as alt
import numpy as np
from sklearn.linear_model import LinearRegression

# --------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# --------------------------------------------------

st.set_page_config(
    page_title="SavIA - Pronóstico de Ventas",
    page_icon="Logo savIA.png"
)

# --------------------------------------------------
# CONFIGURACIÓN SEGURA API KEY
# --------------------------------------------------

if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ API Key de Google no configurada en st.secrets")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --------------------------------------------------
# FUNCIÓN BASELINE (REGRESIÓN LINEAL)
# --------------------------------------------------

def calcular_pronostico_baseline(df_ventas, meses_a_predecir=3):
    df_mensual = (
        df_ventas
        .set_index("Fecha")
        .resample("M")
        .sum()
        .reset_index()
    )

    df_mensual["t"] = np.arange(len(df_mensual))

    X = df_mensual[["t"]]
    y = df_mensual["Ventas"]

    modelo = LinearRegression()
    modelo.fit(X, y)

    futuros_t = np.arange(len(df_mensual), len(df_mensual) + meses_a_predecir)
    predicciones = modelo.predict(futuros_t.reshape(-1, 1))

    fechas_futuras = pd.date_range(
        start=df_mensual["Fecha"].max() + pd.offsets.MonthEnd(1),
        periods=meses_a_predecir,
        freq="M"
    )

    df_pronostico = pd.DataFrame({
        "Mes": fechas_futuras.strftime("%Y-%m"),
        "Pronostico_Baseline": predicciones.round(0).astype(int)
    })

    return df_pronostico

# --------------------------------------------------
# LLAMADA A GEMINI CON CACHE (CONTROL DE CUOTA)
# --------------------------------------------------

@st.cache_data(show_spinner=False)
def llamar_a_gemini(prompt):
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text

# --------------------------------------------------
# FUNCIÓN PRINCIPAL
# --------------------------------------------------

def generar_pronostico(df_ventas, nombre_usuario):
    


    st.info(f"📊 Analizando datos para {nombre_usuario}...")

    df_ventas["Fecha"] = pd.to_datetime(df_ventas["Fecha"], dayfirst=True)

    # ------------------------
    # RESUMEN MENSUAL
    # ------------------------

    df_mensual = (
        df_ventas
        .set_index("Fecha")
        .resample("M")
        .sum()
        .reset_index()
    )

    df_mensual["Fecha"] = df_mensual["Fecha"].dt.strftime("%Y-%m")
    df_mensual = df_mensual.rename(columns={"Ventas": "Total_Ventas_Mensual"})
    datos_mensuales_string = df_mensual.to_string(index=False)

    # ------------------------
    # BASELINE
    # ------------------------

    df_baseline = calcular_pronostico_baseline(df_ventas)
    baseline_string = df_baseline.to_string(index=False)

    # ------------------------
    # PATRONES POR DÍA
    # ------------------------

    df_ventas["Dia_Semana_en"] = df_ventas["Fecha"].dt.day_name()
    dias_map = {
        "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
        "Thursday": "Jueves", "Friday": "Viernes",
        "Saturday": "Sábado", "Sunday": "Domingo"
    }

    df_ventas["Dia_Semana"] = df_ventas["Dia_Semana_en"].map(dias_map)
    ventas_por_dia = df_ventas.groupby("Dia_Semana")["Ventas"].mean().round(0)
    resumen_diario_string = ventas_por_dia.to_string()

    # ------------------------
    # ANOMALÍAS
    # ------------------------

    media = df_ventas["Ventas"].mean()
    std = df_ventas["Ventas"].std()
    umbral = media + 1.5 * std

    picos = df_ventas[df_ventas["Ventas"] > umbral]

    if not picos.empty:
        picos["Fecha_str"] = picos["Fecha"].dt.strftime("%d-%m-%Y")
        anomalias_string = picos[["Fecha_str", "Ventas"]].to_string(index=False)
    else:
        anomalias_string = "No se detectaron picos relevantes."

    # ------------------------
    # PROMPT
    # ------------------------

    prompt = f"""
Eres SavIA, socio estratégico de una PyME.
Habla claro, cercano y profesional.
Dirígete al usuario como {nombre_usuario}.

RESUMEN 1: Ventas Mensuales Históricas
{datos_mensuales_string}

RESUMEN 1B: Pronóstico Base Estadístico
{baseline_string}

RESUMEN 2: Promedio de Ventas por Día
{resumen_diario_string}

RESUMEN 3: Anomalías
{anomalias_string}

Entrega:
1. Análisis de tendencia
2. Análisis de anomalías
3. Pronóstico coherente con el baseline
4. 2–3 insights accionables

Incluye un bloque JSON:
```json
{{
  "pronostico_json": [
    {{"Mes": "2025-10", "Venta": 2800000}},
    {{"Mes": "2025-11", "Venta": 2900000}},
    {{"Mes": "2025-12", "Venta": 3000000}}
  ]
}}
"""
# Baseline siempre disponible (fallback seguro)
    df_baseline = calcular_pronostico_baseline(df_ventas)
try:
    texto_respuesta = llamar_a_gemini(prompt)

    texto_analisis = texto_respuesta.split("```json")[0]
    st.markdown(texto_analisis)

    match = re.search(r"```json\n({.*?})\n```", texto_respuesta, re.DOTALL)

    if match:
        datos = json.loads(match.group(1))
        df_pronostico = pd.DataFrame(datos["pronostico_json"])
        df_pronostico["Fecha"] = pd.to_datetime(df_pronostico["Mes"])
        df_pronostico = df_pronostico.rename(columns={"Venta": "Pronóstico"})

        df_hist = (
            df_ventas
            .set_index("Fecha")
            .resample("M")
            .sum()
            .reset_index()
            .rename(columns={"Ventas": "Ventas Históricas"})
        )

        df_final = pd.merge(df_hist, df_pronostico, on="Fecha", how="outer")
        df_plot = df_final.melt("Fecha", var_name="Tipo", value_name="Monto")

        chart = alt.Chart(df_plot).mark_line(point=True).encode(
            x="Fecha:T",
            y="Monto:Q",
            color="Tipo:N",
            tooltip=["Fecha:T", "Monto:Q", "Tipo:N"]
        )

        st.altair_chart(chart, use_container_width=True)

except Exception:
    st.warning(
        "⚠️ No fue posible contactar la IA. "
        "Se muestra el pronóstico base estadístico."
    )
    
#--------------------------------------------------
#NTERFAZ DE USUARIO
#--------------------------------------------------
col1, col2 = st.columns([1, 4])

with col1:
    st.image("Logo savIA.png", width=100)

with col2:
    st.title("SavIA")
st.markdown("### Tu socio de análisis de datos")

nombre_usuario = st.text_input("Nombre del negocio:", "Emprendedor")

archivo = st.file_uploader("Sube tu archivo CSV", type=["csv"])

df = None

if archivo:
    df = pd.read_csv(archivo, delimiter=";", encoding="utf-8-sig")

    if df.shape[1] == 1:
        archivo.seek(0)
        df = pd.read_csv(archivo, delimiter=",", encoding="utf-8-sig")

    # 👇 TODO lo que toca df va aquí
    df.columns = df.columns.str.strip().str.title()

    st.success("Archivo cargado correctamente")
    st.dataframe(df.head())


if "ejecutado" not in st.session_state:
    st.session_state.ejecutado = False

if st.button("✨ Generar Pronóstico", disabled=st.session_state.ejecutado):
    st.session_state.ejecutado = True
    generar_pronostico(df, nombre_usuario)
