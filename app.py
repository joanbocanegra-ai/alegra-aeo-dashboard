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

# Hide Streamlit chrome for a clean full-screen experience
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

metricas_json = metricas.to_json(orient='records', force_ascii=False)
marcas_json = marcas.to_json(orient='records', force_ascii=False)
dominios_json = dominios.to_json(orient='records', force_ascii=False)

# ── Full interactive HTML dashboard ─────────────────────────
html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0B1120; --surface: #111827; --card: #1a2234; --border: #2a3550;
    --text: #F1F5F9; --muted: #94A3B8; --dim: #64748B;
    --teal: #2DD4BF; --blue: #60A5FA; --amber: #FBBF24; --green: #34D399;
    --red: #F87171; --orange: #FB923C; --purple: #A78BFA; --pink: #F472B6;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Inter',system-ui,sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }}
  .app {{ display:flex; min-height:100vh; }}
  .sidebar {{ width:220px; background:var(--surface); border-right:1px solid var(--border); padding:20px 14px; flex-shrink:0; position:sticky; top:0; height:100vh; overflow-y:auto; }}
  .main {{ flex:1; padding:20px 28px; max-width:1300px; }}
  .sidebar-title {{ font-size:15px; font-weight:700; margin-bottom:2px; }}
  .sidebar-sub {{ font-size:11px; color:var(--muted); margin-bottom:18px; }}
  .filter-group {{ margin-bottom:14px; }}
  .filter-label {{ font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:var(--dim); margin-bottom:5px; }}
  .filter-select {{ width:100%; background:var(--card); color:var(--text); border:1px solid var(--border); border-radius:8px; padding:7px 9px; font-size:12px; font-family:inherit; cursor:pointer; appearance:auto; }}
  .filter-select:focus {{ outline:none; border-color:var(--teal); }}
  .sidebar-divider {{ border:none; border-top:1px solid var(--border); margin:14px 0; }}
  .sidebar-info {{ font-size:10px; color:var(--dim); line-height:1.6; }}
  .header {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px; }}
  .header h1 {{ font-size:20px; font-weight:700; margin-bottom:2px; }}
  .header-sub {{ font-size:11px; color:var(--muted); }}
  .header-badges {{ display:flex; gap:6px; margin-top:6px; }}
  .badge {{ padding:3px 10px; border-radius:12px; font-size:10px; font-weight:600; }}
  .section-label {{ font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:var(--dim); margin:24px 0 10px 0; }}
  .kpi-row {{ display:grid; grid-template-columns:repeat(6,1fr); gap:10px; }}
  .kpi-card {{ background:linear-gradient(135deg,var(--card),#1e2a3f); border:1px solid var(--border); border-radius:12px; padding:14px 12px; text-align:center; }}
  .kpi-label {{ font-size:9px; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; color:var(--muted); margin-bottom:3px; }}
  .kpi-value {{ font-size:24px; font-weight:800; letter-spacing:-0.02em; line-height:1.1; }}
  .kpi-sub {{ font-size:9px; color:var(--dim); margin-top:3px; }}
  .chart-row {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
  .chart-box {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px; overflow:hidden; }}
  .chart-half {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
  .leader-list {{ background:var(--card); border:1px solid var(--border); border-radius:12px; overflow:hidden; }}
  .leader-row {{ display:flex; justify-content:space-between; align-items:center; padding:9px 12px; border-bottom:1px solid var(--border); }}
  .leader-row:last-child {{ border-bottom:none; }}
  .overall-leader {{ margin-top:14px; padding:12px 16px; border-radius:10px; border:1px solid var(--teal); background:rgba(45,212,191,0.05); }}
  .data-table {{ width:100%; border-collapse:collapse; font-size:11px; }}
  .data-table th {{ background:var(--surface); padding:7px 8px; text-align:left; font-weight:600; font-size:9px; text-transform:uppercase; letter-spacing:0.05em; color:var(--muted); border-bottom:2px solid var(--border); position:sticky; top:0; }}
  .data-table td {{ padding:6px 8px; border-bottom:1px solid var(--border); }}
  .data-table tr:hover td {{ background:rgba(45,212,191,0.04); }}
  .data-table tr.is-alegra td {{ background:rgba(45,212,191,0.08); font-weight:600; }}
  .table-wrap {{ max-height:320px; overflow-y:auto; border:1px solid var(--border); border-radius:10px; }}
  .insight-row {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }}
  .insight-box {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 16px; }}
  .insight-title {{ font-size:11px; font-weight:700; margin-bottom:5px; }}
  .insight-body {{ font-size:11px; color:var(--muted); line-height:1.6; }}
  .footer {{ text-align:center; font-size:10px; color:var(--dim); margin-top:28px; padding-top:14px; border-top:1px solid var(--border); }}
  .footer a {{ color:var(--dim); }}
  @media (max-width:1100px) {{
    .kpi-row {{ grid-template-columns:repeat(3,1fr); }}
    .chart-row,.insight-row {{ grid-template-columns:1fr; }}
    .chart-half {{ grid-template-columns:1fr; }}
    .sidebar {{ display:none; }}
  }}
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="sidebar-title">📊 Alegra AEO</div>
    <div class="sidebar-sub">Golden Stack Dashboard</div>
    <hr class="sidebar-divider">
    <div class="filter-group"><div class="filter-label">País</div><select class="filter-select" id="f-pais"><option value="">Todos</option></select></div>
    <div class="filter-group"><div class="filter-label">Funnel</div><select class="filter-select" id="f-funnel"><option value="">Todos</option></select></div>
    <div class="filter-group"><div class="filter-label">Categoría</div><select class="filter-select" id="f-cat"><option value="">Todas</option></select></div>
    <div class="filter-group"><div class="filter-label">Motor</div><select class="filter-select" id="f-motor"><option value="">Todos</option></select></div>
    <hr class="sidebar-divider">
    <div class="sidebar-info" id="sidebar-info"></div>
  </aside>
  <main class="main" id="main-content">
    <div class="header">
      <div><h1>Alegra AEO — Golden Stack</h1><div class="header-sub" id="header-sub"></div></div>
      <div class="header-badges" id="header-badges"></div>
    </div>
    <div class="section-label">Promedios Globales</div>
    <div class="kpi-row" id="kpi-row"></div>
    <div class="section-label">Comparativo por Motor</div>
    <div class="chart-row">
      <div class="chart-box"><div id="chart-mr"></div></div>
      <div class="chart-box"><div id="chart-pos"></div></div>
      <div class="chart-box"><div id="chart-eco"></div></div>
    </div>
    <div class="section-label">Ranking de Marcas Competidoras</div>
    <div class="chart-half">
      <div class="chart-box"><div id="chart-brands"></div></div>
      <div>
        <div style="font-size:12px;font-weight:600;margin-bottom:8px">Marca Líder por Prompt × Motor</div>
        <div class="leader-list" id="leader-list"></div>
        <div id="overall-leader"></div>
      </div>
    </div>
    <div class="section-label">Marcas Mencionadas por Prompt</div>
    <div class="table-wrap"><table class="data-table" id="brand-table"><thead><tr>
      <th>Prompt</th><th>Motor</th><th>Marca</th><th>Rank Avg</th><th>Presencia %</th><th>Menciones</th><th>Ranks por Réplica</th>
    </tr></thead><tbody></tbody></table></div>
    <div class="section-label">Detalle por Prompt</div>
    <div class="table-wrap"><table class="data-table" id="prompt-table"><thead><tr>
      <th>ID</th><th>Prompt</th><th>Funnel</th><th>Categoría</th><th>Motor</th><th>Mention</th><th>Citation</th><th>Consist.</th><th>Pos. Avg</th><th>Eco Share</th><th>Citas</th>
    </tr></thead><tbody></tbody></table></div>
    <div class="section-label">Mapa de Dominios Citados</div>
    <div class="chart-half">
      <div class="chart-box"><div style="font-size:12px;font-weight:600;margin-bottom:6px" id="eco-dom-title"></div><div id="chart-eco-doms"></div></div>
      <div class="chart-box"><div style="font-size:12px;font-weight:600;margin-bottom:6px" id="ext-dom-title"></div><div id="chart-ext-doms"></div></div>
    </div>
    <div class="section-label">Insights</div>
    <div class="insight-row" id="insight-row"></div>
    <div class="footer">Batch <span id="footer-batch"></span> · Arquitectura Dual (OpenAI + DataForSEO) · <a href="https://www.perplexity.ai/computer" target="_blank">Created with Perplexity Computer</a></div>
  </main>
</div>

<script>
const metricas = {metricas_json};
const marcas = {marcas_json};
const dominios = {dominios_json};
const ML = {{"chatgpt_search":"ChatGPT","google_aio":"AI Overview"}};
const MC = {{"chatgpt_search":"#2DD4BF","google_aio":"#60A5FA"}};
const BC = {{"Alegra":"#2DD4BF","CONTPAQi":"#60A5FA","Aspel":"#FBBF24","QuickBooks":"#A78BFA","Bind ERP":"#F87171","Microsip":"#FB923C","Miskuentas
