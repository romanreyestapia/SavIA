# --------------------------------------------------
# IMPORTS
# --------------------------------------------------
import streamlit as st
import pandas as pd
import altair as alt
import json
import re
import time
from datetime import timedelta

from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

# Nueva librería Gemini (OFICIAL)
from google import genai
from google.genai.types import GenerateContentConfig


# --------------------------------------------------
# CONFIG STREAMLIT
# --------------------------------------------------
st.set_page_config(
    page_title="SavIA - Análisis Inteligente para PYMEs",
    page_icon="📊",
    layout="centered"
)

# --------------------------------------------------
# CONFIG IA
# --------------------------------------------------
USE_IA = True
IA_TIMEOUT_SECONDS = 20  # ⏱️ control duro

try:
    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    USE_IA = False
    st.warning("⚠️ IA no configurada. Se usará solo el modelo base.")


# --------------------------------------------------
# FUNCIONES BASELINE (MODELO LOCAL)
# --------------------------------------------------
def generar_baseline(df):
    df_m = (
        df.set_index("Fecha")
        .resample("ME")
        .sum()
        .reset_index()
    )

    df_m["t"] = range(len(df_m))
    X = df_m[["t"]]
    y = df_m["Ventas"]

    model = LinearRegression()
    model.fit(X, y)

    t_futuro = [[len(df_m) + i] for i in range(1, 4)]
    pred = model.predict(t_futuro).round(0).astype(int)

    fechas = pd.date_range(
        start=df_m["Fecha"].max() + pd.offsets.MonthEnd(1),
        periods=3,
        freq="ME"
    )

    return pd.DataFrame({
        "Fecha": fechas,
        "Pronóstico": pred
    })


# --------------------------------------------------
# IA CON TIMEOUT
# --------------------------------------------------
def llamar_ia_con_timeout(prompt):
    start = time.time()

    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt,
        config=GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=800
        )
    )

    if time.time() - start > IA_TIMEOUT_SECONDS:
        raise TimeoutError("IA excedió el tiempo máximo")

    return response.text


# --------------------------------------------------
# FUNCIÓN PRINCIPAL
# --------------------------------------------------
def analizar_datos(df, nombre):
    st.info(f"📊 Analizando datos para {nombre}...")

    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)

    # ---------------- HISTÓRICO
    df_hist = (
        df.set_index("Fecha")
        .resample("ME")
        .sum()
        .reset_index()
    )

    # ---------------- BASELINE
    df_baseline = generar_baseline(df)

    # ---------------- IA (opcional)
    analisis_ia = None

    if USE_IA:
        prompt = f"""
Eres SavIA, un analista experto para pymes.

Datos mensuales:
{df_hist[['Fecha','Ventas']].to_string(index=False)}

Entrega:
1. Tendencia general
2. Riesgos
3. Oportunidades
"""

        try:
            analisis_ia = llamar_ia_con_timeout(prompt)
        except Exception:
            analisis_ia = None

    # ---------------- UI
    st.subheader("📈 Ventas históricas")
    st.dataframe(df_hist)

    st.subheader("🔮 Pronóstico (Baseline)")
    st.dataframe(df_baseline)

    if analisis_ia:
        st.subheader("🤖 Análisis SavIA (IA)")
        st.markdown(analisis_ia)
    else:
        st.warning("⚠️ IA no disponible. Mostrando solo pronóstico base.")

    # ---------------- GRÁFICO
    df_plot = pd.concat([
        df_hist.rename(columns={"Ventas": "Monto"}).assign(Tipo="Histórico"),
        df_baseline.rename(columns={"Pronóstico": "Monto"}).assign(Tipo="Pronóstico")
    ])

    chart = alt.Chart(df_plot).mark_line(point=True).encode(
        x="Fecha:T",
        y="Monto:Q",
        color="Tipo:N",
        tooltip=["Fecha:T", "Monto:Q", "Tipo:N"]
    ).interactive()

    st.altair_chart(chart, use_container_width=True)


# --------------------------------------------------
# INTERFAZ
# --------------------------------------------------
st.title("SavIA")
st.markdown("### Tu socio inteligente en análisis de datos para PYMEs")

nombre = st.text_input("Nombre o negocio:", "Marcos")

archivo = st.file_uploader(
    "Sube tu archivo CSV (Fecha, Ventas)",
    type=["csv"]
)

if archivo:
    try:
        df = pd.read_csv(archivo, delimiter=";", encoding="utf-8-sig")
        if df.shape[1] == 1:
            archivo.seek(0)
            df = pd.read_csv(archivo, delimiter=",", encoding="utf-8-sig")

        df.columns = df.columns.str.strip().str.title()

        if "Fecha" not in df.columns or "Ventas" not in df.columns:
            st.error("El CSV debe tener columnas 'Fecha' y 'Ventas'")
        else:
            st.success("Archivo cargado correctamente")
            st.dataframe(df.head())

            if st.button("✨ Generar análisis"):
                analizar_datos(df, nombre)

    except Exception as e:
        st.error(f"Error procesando archivo: {e}")

