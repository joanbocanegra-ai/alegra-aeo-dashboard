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
                          marker_color=[MOTOR_COLORS.get(m, "#999") + "88" for m in motor_agg["model_source"]],
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
st.markdown('<div class="section-label">Ranking de Marcas Competidoras</div>', unsafe_allow_html=True)
br1, br2 = st.columns(2)

with br1:
    brand_weighted = fb.groupby("brand_name").agg(
        pos_ponderada=("brand_rank_avg", "mean"),
        menciones=("brand_mentions_total", "sum"),
        apariciones=("brand_rank_avg", "count")
    ).sort_values("pos_ponderada").reset_index()

    colors = [BRAND_COLORS.get(b, "#64748B") for b in brand_weighted["brand_name"]]
    fig_br = go.Figure(go.Bar(
        y=brand_weighted["brand_name"], x=brand_weighted["pos_ponderada"],
        orientation="h", marker_color=colors,
        text=[f"#{v:.1f}" for v in brand_weighted["pos_ponderada"]],
        textposition="outside"
    ))
    fig_br.update_layout(title="Posición Promedio por Marca (Ponderada)",
                         template="plotly_dark", height=380, margin=dict(t=40, b=20, l=100),
                         xaxis=dict(range=[0, max(brand_weighted["pos_ponderada"]) + 1.5], title="Posición"),
                         yaxis=dict(autorange="reversed", title=""),
                         paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_br, use_container_width=True)

with br2:
    st.markdown("##### Marca Líder por Prompt × Motor")
    for _, row in fm.iterrows():
        motor_label = MOTOR_LABELS.get(row["model_source"], row["model_source"])
        motor_color = MOTOR_COLORS.get(row["model_source"], "#999")
        top_b = row["top_brand"]
        top_c = BRAND_COLORS.get(top_b, "#64748B")
        st.markdown(f"""
        <div style='display:flex;justify-content:space-between;align-items:center;
            padding:10px 14px;border-bottom:1px solid #2a3550'>
            <div>
                <strong style='font-size:13px'>{row['prompt_id']}</strong>
                <span style='background:{motor_color}22;color:{motor_color};padding:2px 8px;
                    border-radius:4px;font-size:10px;font-weight:600;margin-left:8px'>{motor_label}</span>
            </div>
            <div>
                <span style='font-size:11px;color:#94A3B8'>Líder:</span>
                <span style='background:{top_c}22;color:{top_c};padding:2px 8px;
                    border-radius:4px;font-size:11px;font-weight:600;margin-left:4px'>{top_b}</span>
                <span style='font-size:12px;font-weight:700;color:{top_c};margin-left:4px'>#{row["top_brand_rank"]:.1f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Overall leader
    if len(brand_weighted) > 0:
        ldr = brand_weighted.iloc[0]
        ldr_c = BRAND_COLORS.get(ldr["brand_name"], "#64748B")
        st.markdown(f"""
        <div style='margin-top:16px;padding:14px 18px;background:{TEAL}0D;border:1px solid {TEAL};border-radius:10px'>
            <div style='font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#94A3B8;margin-bottom:6px'>
                Marca Líder Ponderada (Todos los filtros)</div>
            <div style='display:flex;align-items:center;gap:10px'>
                <span style='font-size:18px'>🏆</span>
                <span style='font-size:18px;font-weight:700;color:{ldr_c}'>{ldr["brand_name"]}</span>
                <span style='font-size:13px;color:#94A3B8'>Pos. ponderada
                    <strong style='color:#F1F5F9'>#{ldr["pos_ponderada"]:.1f}</strong></span>
            </div>
            <div style='font-size:11px;color:#64748B;margin-top:4px'>
                {int(ldr["apariciones"])}/{len(fm)} combinaciones · {int(ldr["menciones"])} menciones totales</div>
        </div>
        """, unsafe_allow_html=True)

# ── Brand detail table ──────────────────────────────────────
st.markdown('<div class="section-label">Marcas Mencionadas por Prompt</div>', unsafe_allow_html=True)

brand_display = fb[["prompt_id", "model_source", "brand_name", "brand_rank_avg",
                     "brand_presence_pct", "brand_mentions_total", "brand_ranks_by_rep", "is_alegra"]].copy()
brand_display["Motor"] = brand_display["model_source"].map(MOTOR_LABELS)
brand_display = brand_display.rename(columns={
    "prompt_id": "Prompt", "brand_name": "Marca", "brand_rank_avg": "Rank Avg",
    "brand_presence_pct": "Presencia %", "brand_mentions_total": "Menciones",
    "brand_ranks_by_rep": "Ranks por Réplica"
})

def highlight_alegra(row):
    if row.get("is_alegra", 0) == 1:
        return [f"background-color: {TEAL}15; font-weight: 600"] * len(row)
    return [""] * len(row)

st.dataframe(
    brand_display[["Prompt", "Motor", "Marca", "Rank Avg", "Presencia %", "Menciones", "Ranks por Réplica"]]
        .style.apply(highlight_alegra, axis=1)
        .format({"Rank Avg": "#{:.1f}", "Presencia %": "{:.0f}%"}),
    use_container_width=True, height=400
)

# ── Prompt detail table ─────────────────────────────────────
st.markdown('<div class="section-label">Detalle por Prompt</div>', unsafe_allow_html=True)

prompt_display = fm[["prompt_id", "prompt_text", "funnel_stage", "product_category",
                      "model_source", "mention_rate", "citation_rate", "consistency_score",
                      "avg_rank_alegra", "eco_share_pct", "total_cites"]].copy()
prompt_display["Motor"] = prompt_display["model_source"].map(MOTOR_LABELS)
prompt_display = prompt_display.rename(columns={
    "prompt_id": "ID", "prompt_text": "Prompt", "funnel_stage": "Funnel",
    "product_category": "Categoría", "mention_rate": "Mention",
    "citation_rate": "Citation", "consistency_score": "Consist.",
    "avg_rank_alegra": "Pos. Avg", "eco_share_pct": "Eco Share",
    "total_cites": "Citas"
})
st.dataframe(
    prompt_display[["ID", "Prompt", "Funnel", "Categoría", "Motor",
                     "Mention", "Citation", "Consist.", "Pos. Avg", "Eco Share", "Citas"]]
        .style.format({"Mention": "{:.2f}", "Citation": "{:.2f}", "Consist.": "{:.0f}",
                       "Pos. Avg": "#{:.1f}", "Eco Share": "{:.0f}%"})
        .background_gradient(subset=["Mention"], cmap="Greens", vmin=0, vmax=1)
        .background_gradient(subset=["Citation"], cmap="Blues", vmin=0, vmax=1),
    use_container_width=True, height=250
)

# ── Domain map ──────────────────────────────────────────────
st.markdown('<div class="section-label">Mapa de Dominios Citados</div>', unsafe_allow_html=True)
dm1, dm2 = st.columns(2)

with dm1:
    eco_doms = fd[fd["is_ecosystem"] == 1].groupby("domain")["cite_count"].sum().sort_values(ascending=False).reset_index()
    eco_total = eco_doms["cite_count"].sum()
    st.markdown(f"##### Ecosistema Alegra ({eco_total} citas)")
    if len(eco_doms) > 0:
        fig_eco = go.Figure(go.Bar(
            x=eco_doms["cite_count"], y=eco_doms["domain"], orientation="h",
            marker_color=TEAL, text=eco_doms["cite_count"], textposition="outside"
        ))
        fig_eco.update_layout(template="plotly_dark", height=200, margin=dict(t=10, b=10, l=180),
                              xaxis=dict(title="Citas"), yaxis=dict(autorange="reversed", title=""),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_eco, use_container_width=True)
    else:
        st.info("Sin citas del ecosistema en esta selección")

with dm2:
    ext_doms = fd[fd["is_ecosystem"] == 0].groupby("domain")["cite_count"].sum().sort_values(ascending=False).head(10).reset_index()
    ext_total = fd[fd["is_ecosystem"] == 0]["cite_count"].sum()
    st.markdown(f"##### Fuentes Externas Top 10 ({ext_total} citas)")
    if len(ext_doms) > 0:
        fig_ext = go.Figure(go.Bar(
            x=ext_doms["cite_count"], y=ext_doms["domain"], orientation="h",
            marker_color="#64748B", text=ext_doms["cite_count"], textposition="outside"
        ))
        fig_ext.update_layout(template="plotly_dark", height=300, margin=dict(t=10, b=10, l=180),
                              xaxis=dict(title="Citas"), yaxis=dict(autorange="reversed", title=""),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_ext, use_container_width=True)

# ── Insights ────────────────────────────────────────────────
st.markdown('<div class="section-label">Insights</div>', unsafe_allow_html=True)
ins1, ins2, ins3 = st.columns(3)

# Compute insights dynamically
alegra_chatgpt = fm[fm["model_source"] == "chatgpt_search"]["avg_rank_alegra"]
alegra_aio = fm[fm["model_source"] == "google_aio"]["avg_rank_alegra"]
no_cite = fm[(fm["model_source"] == "chatgpt_search") & (fm["citation_rate"] == 0)]["prompt_id"].tolist()
branded_leaders = fm[fm["product_category"] == "Branded"]["top_brand"].unique().tolist()
generic_leaders = fm[fm["product_category"] != "Branded"]["top_brand"].unique().tolist()

with ins1:
    st.markdown(f"""<div class="insight-box">
        <div class="insight-title" style="color:{ORANGE}">Posición de Alegra</div>
        <div class="insight-body">
            {'ChatGPT: posición <strong>#' + f'{alegra_chatgpt.mean():.1f}</strong>. ' if len(alegra_chatgpt) > 0 else ''}
            {'AI Overview: <strong>#' + f'{alegra_aio.mean():.1f}</strong>. ' if len(alegra_aio) > 0 else ''}
            En Branded la marca alcanza el #1. En genéricos BOFU cae a #4-5 por detrás de CONTPAQi y Aspel.
        </div></div>""", unsafe_allow_html=True)

with ins2:
    st.markdown(f"""<div class="insight-box">
        <div class="insight-title" style="color:{PINK}">Marca líder por segmento</div>
        <div class="insight-body">
            {'<strong>Branded:</strong> ' + ', '.join(branded_leaders) + ' lidera(n). ' if branded_leaders else ''}
            {'<strong>Genérico:</strong> ' + ', '.join(generic_leaders) + ' lidera(n). ' if generic_leaders else ''}
            CONTPAQi domina los prompts genéricos BOFU en AI Overview. Alegra necesita estrategia para escalar posición orgánica.
        </div></div>""", unsafe_allow_html=True)

with ins3:
    st.markdown(f"""<div class="insight-box">
        <div class="insight-title" style="color:{TEAL}">Oportunidad competitiva</div>
        <div class="insight-body">
            {'ChatGPT no cita a Alegra en: <strong>' + ', '.join(no_cite) + '</strong>. ' if no_cite else ''}
            programascontabilidad.com es la fuente del ecosistema más citada por AI Overview — pero ChatGPT la ignora. Priorizar contenido linkeable desde fuentes terceras.
        </div></div>""", unsafe_allow_html=True)

# ── Footer ──────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;font-size:11px;color:#64748B'>"
    f"Batch {metricas['batch_date'].iloc[0]} · Arquitectura Dual (OpenAI + DataForSEO) · "
    f"<a href='https://www.perplexity.ai/computer' target='_blank' style='color:#64748B'>Created with Perplexity Computer</a>"
    f"</div>", unsafe_allow_html=True
)
