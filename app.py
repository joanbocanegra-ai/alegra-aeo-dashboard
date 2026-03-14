import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import os

# ── Config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Alegra AEO — Golden Stack",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = os.path.join(os.path.dirname(__file__), "aeo_data.db")

TEAL = "#2DD4BF"
BLUE = "#60A5FA"
AMBER = "#FBBF24"
GREEN = "#34D399"
RED = "#F87171"
ORANGE = "#FB923C"
PURPLE = "#A78BFA"
PINK = "#F472B6"

MOTOR_COLORS = {"chatgpt_search": TEAL, "google_aio": BLUE}
MOTOR_LABELS = {"chatgpt_search": "ChatGPT", "google_aio": "AI Overview"}

BRAND_COLORS = {
    "Alegra": TEAL, "CONTPAQi": BLUE, "Aspel": AMBER,
    "QuickBooks": PURPLE, "Bind ERP": RED, "Microsip": ORANGE,
    "Miskuentas": PINK, "Contalink": GREEN, "Siigo": "#818CF8", "Odoo": "#A3A3A3",
}

# ── Theme CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    [data-testid="stSidebar"] { background: #111827; }
    [data-testid="stSidebar"] * { color: #F1F5F9 !important; }
    .kpi-card {
        background: linear-gradient(135deg, #1a2234, #1e2a3f);
        border: 1px solid #2a3550; border-radius: 12px;
        padding: 18px 20px; text-align: center;
    }
    .kpi-label { font-size: 11px; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.06em; color: #94A3B8; margin-bottom: 4px; }
    .kpi-value { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; line-height: 1; }
    .kpi-sub { font-size: 11px; color: #64748B; margin-top: 4px; }
    .section-label { font-size: 11px; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.08em; color: #64748B; margin: 20px 0 8px 0; }
    div[data-testid="stMetric"] { background: #1a2234; border: 1px solid #2a3550;
        border-radius: 10px; padding: 12px 16px; }
    .insight-box {
        background: #1a2234; border: 1px solid #2a3550; border-radius: 10px;
        padding: 16px 20px; margin-bottom: 12px;
    }
    .insight-title { font-size: 12px; font-weight: 600; margin-bottom: 6px; }
    .insight-body { font-size: 13px; color: #94A3B8; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    metricas = pd.read_sql("SELECT * FROM metricas", conn)
    marcas = pd.read_sql("SELECT * FROM marcas", conn)
    dominios = pd.read_sql("SELECT * FROM dominios", conn)
    conn.close()
    return metricas, marcas, dominios

metricas, marcas, dominios = load_data()

# ── Sidebar filters ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Alegra AEO")
    st.markdown("**Golden Stack Dashboard**")
    st.markdown("---")

    paises = ["Todos"] + sorted(metricas["country_id"].unique().tolist())
    sel_pais = st.selectbox("País", paises, index=0)

    funnels = ["Todos"] + sorted(metricas["funnel_stage"].unique().tolist())
    sel_funnel = st.selectbox("Funnel", funnels, index=0)

    cats = ["Todas"] + sorted(metricas["product_category"].unique().tolist())
    sel_cat = st.selectbox("Categoría", cats, index=0)

    motores = ["Todos"] + sorted(metricas["model_source"].unique().tolist())
    sel_motor = st.selectbox("Motor", motores, index=0,
                             format_func=lambda x: MOTOR_LABELS.get(x, x))

    st.markdown("---")
    st.markdown(f"<div style='font-size:10px;color:#64748B'>Batch: {metricas['batch_date'].iloc[0]}<br>Arquitectura Dual</div>", unsafe_allow_html=True)

# ── Filter data ─────────────────────────────────────────────
def apply_filters(df):
    if sel_pais != "Todos":
        df = df[df["country_id"] == sel_pais]
    if sel_funnel != "Todos":
        df = df[df["funnel_stage"] == sel_funnel]
    if sel_cat != "Todas":
        df = df[df["product_category"] == sel_cat]
    if sel_motor != "Todos":
        df = df[df["model_source"] == sel_motor]
    return df

fm = apply_filters(metricas)
fb = apply_filters(marcas)
fd = apply_filters(dominios)

# ── Header ──────────────────────────────────────────────────
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("## Alegra AEO — Golden Stack")
    st.caption(f"Dashboard MVP · Batch {metricas['batch_date'].iloc[0]} · {len(fm)} prompt×motor")
with c2:
    st.markdown(f"""
    <div style='text-align:right;padding-top:10px'>
        <span style='background:{GREEN}22;color:{GREEN};padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600'>
            ● {metricas['num_success'].sum()}/{metricas['num_replicates'].sum()} OK
        </span>
        <span style='background:{BLUE}22;color:{BLUE};padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600;margin-left:6px'>MX</span>
    </div>
    """, unsafe_allow_html=True)

# ── KPIs ────────────────────────────────────────────────────
if len(fm) == 0:
    st.warning("Sin datos para los filtros seleccionados")
    st.stop()

avg_mr = fm["mention_rate"].mean()
avg_cr = fm["citation_rate"].mean()
avg_rank = fm["avg_rank_alegra"].mean()
eco_t = fm["eco_cites"].sum()
total_t = fm["total_cites"].sum()
eco_pct = (eco_t / total_t * 100) if total_t > 0 else 0
n_prompts = fm["prompt_id"].nunique()

# Top brand weighted
brand_agg = fb.groupby("brand_name")["brand_rank_avg"].mean().sort_values()
top_brand = brand_agg.index[0] if len(brand_agg) > 0 else "—"
top_brand_rank = brand_agg.iloc[0] if len(brand_agg) > 0 else 0

st.markdown('<div class="section-label">Promedios Globales</div>', unsafe_allow_html=True)
k1, k2, k3, k4, k5, k6 = st.columns(6)

def kpi_html(label, value, color, sub=""):
    return f"""<div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color:{color}">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>"""

k1.markdown(kpi_html("Mention Rate", f"{avg_mr*100:.0f}%", TEAL, f"Promedio {len(fm)} combos"), unsafe_allow_html=True)
k2.markdown(kpi_html("Citation Rate", f"{avg_cr*100:.0f}%", BLUE, "Marca citada como fuente"), unsafe_allow_html=True)
k3.markdown(kpi_html("Alegra Pos. Avg", f"#{avg_rank:.1f}", ORANGE, "Rank ponderado Alegra"), unsafe_allow_html=True)
k4.markdown(kpi_html("Marca Líder", top_brand, PINK, f"Pos. ponderada #{top_brand_rank:.1f}"), unsafe_allow_html=True)
k5.markdown(kpi_html("Eco Share", f"{eco_pct:.0f}%", GREEN, f"{eco_t}/{total_t} citas ecosistema"), unsafe_allow_html=True)
k6.markdown(kpi_html("Prompts", str(n_prompts), AMBER, f"{len(fm)} prompt×motor"), unsafe_allow_html=True)

# ── Charts row ──────────────────────────────────────────────
st.markdown('<div class="section-label">Comparativo por Motor</div>', unsafe_allow_html=True)
ch1, ch2, ch3 = st.columns(3)

with ch1:
    motor_agg = fm.groupby("model_source").agg(
        mention=("mention_rate", "mean"),
        citation=("citation_rate", "mean")
    ).reset_index()
    motor_agg["motor_label"] = motor_agg["model_source"].map(MOTOR_LABELS)
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(name="Mention Rate", x=motor_agg["motor_label"], y=motor_agg["mention"],
                          marker_color=[MOTOR_COLORS.get(m, "#999") for m in motor_agg["model_source"]],
                          text=[f"{v*100:.0f}%" for v in motor_agg["mention"]], textposition="outside"))
    fig1.add_trace(go.Bar(name="Citation Rate", x=motor_agg["motor_label"], y=motor_agg["citation"],
                          marker_color=[f"rgba({int(MOTOR_COLORS.get(m, '#999999')[1:3],16)},{int(MOTOR_COLORS.get(m, '#999999')[3:5],16)},{int(MOTOR_COLORS.get(m, '#999999')[5:7],16)},0.5)" for m in motor_agg["model_source"]],
                          text=[f"{v*100:.0f}%" for v in motor_agg["citation"]], textposition="outside"))
    fig1.update_layout(title="Mention & Citation Rate", barmode="group",
                       yaxis=dict(range=[0, 1.15], tickformat=".0%"),
                       template="plotly_dark", height=320, margin=dict(t=40, b=20),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       legend=dict(orientation="h", yanchor="top", y=1.12, font=dict(size=10)))
    st.plotly_chart(fig1, use_container_width=True)

with ch2:
    pos_data = fm[["prompt_id", "model_source", "avg_rank_alegra"]].copy()
    pos_data["motor_label"] = pos_data["model_source"].map(MOTOR_LABELS)
    fig2 = px.bar(pos_data, y="prompt_id", x="avg_rank_alegra", color="motor_label",
                  barmode="group", orientation="h",
                  color_discrete_map={"ChatGPT": TEAL, "AI Overview": BLUE},
                  text=pos_data["avg_rank_alegra"].apply(lambda x: f"#{x:.1f}"))
    fig2.update_layout(title="Posición Promedio de Alegra", template="plotly_dark",
                       height=320, margin=dict(t=40, b=20),
                       xaxis=dict(range=[0, 6], title="Posición"),
                       yaxis=dict(title=""),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       legend=dict(orientation="h", yanchor="top", y=1.12, title="", font=dict(size=10)))
    st.plotly_chart(fig2, use_container_width=True)

with ch3:
    eco_total = fd[fd["is_ecosystem"] == 1]["cite_count"].sum() if len(fd) > 0 else 0
    ext_total = fd[fd["is_ecosystem"] == 0]["cite_count"].sum() if len(fd) > 0 else 0
    fig3 = go.Figure(go.Pie(
        labels=["Ecosistema Alegra", "Fuentes Externas"],
        values=[eco_total, ext_total],
        marker=dict(colors=[TEAL, "#64748B"]),
        hole=0.6, textinfo="label+percent", textfont=dict(size=11)
    ))
    fig3.update_layout(title="Share de Citas", template="plotly_dark",
                       height=320, margin=dict(t=40, b=20),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       showlegend=False)
    st.plotly_chart(fig3, use_container_width=True)

# ── Brand ranking ───────────────────────────────────────────
