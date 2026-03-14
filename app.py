import streamlit as st
import sqlite3
import pandas as pd
import json
import os

st.set_page_config(
    page_title="Alegra AEO — Golden Stack",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide Streamlit chrome for clean full-screen experience
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding:0 !important; max-width:100% !important;}
    [data-testid="stAppViewContainer"] {padding:0 !important;}
    iframe {border:none !important;}
</style>
""", unsafe_allow_html=True)

# ── Load data from SQLite ───────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "aeo_data.db")

@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    metricas = pd.read_sql("SELECT * FROM metricas", conn)
    marcas = pd.read_sql("SELECT * FROM marcas", conn)
    dominios = pd.read_sql("SELECT * FROM dominios", conn)
    conn.close()
    return metricas, marcas, dominios

metricas, marcas, dominios = load_data()

metricas_json = metricas.to_json(orient="records", force_ascii=False)
marcas_json = marcas.to_json(orient="records", force_ascii=False)
dominios_json = dominios.to_json(orient="records", force_ascii=False)

# ── Load HTML template and inject data ──────────────────────
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")
with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
    html_template = f.read()

html_content = (
    html_template
    .replace("/*__METRICAS_JSON__*/", metricas_json)
    .replace("/*__MARCAS_JSON__*/", marcas_json)
    .replace("/*__DOMINIOS_JSON__*/", dominios_json)
)

st.components.v1.html(html_content, height=3200, scrolling=True)
