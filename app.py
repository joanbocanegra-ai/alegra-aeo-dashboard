import os, sqlite3, math
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, html, dcc, callback, Output, Input, State, ctx, dash_table

# ── DB ────────────────────────────────────────────────────────────────
# Dual mode: Supabase (PostgreSQL) in production, SQLite for local dev
DATABASE_URL = os.environ.get("DATABASE_URL")

_pg_engine = None
def _get_engine():
    global _pg_engine
    if _pg_engine is None:
        from sqlalchemy import create_engine
        _pg_engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=5,
            pool_recycle=300,
            connect_args={"connect_timeout": 30},
        )
    return _pg_engine

def load_data():
    _empty_resp = pd.DataFrame(columns=["batch_id","prompt_id","model_source","replicate_id","raw_response_text","raw_citations_json"])
    try:
        if DATABASE_URL:
            engine = _get_engine()
            with engine.connect() as conn:
                met = pd.read_sql("SELECT * FROM metricas", conn)
                mar = pd.read_sql("SELECT * FROM marcas", conn)
                dom = pd.read_sql("SELECT * FROM dominios", conn)
                try:
                    resp = pd.read_sql("SELECT * FROM respuestas", conn)
                except Exception:
                    resp = _empty_resp
        else:
            from init_db import init_db
            init_db()
            conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "aeo_data.db"))
            met = pd.read_sql("SELECT * FROM metricas", conn)
            mar = pd.read_sql("SELECT * FROM marcas", conn)
            dom = pd.read_sql("SELECT * FROM dominios", conn)
            try:
                resp = pd.read_sql("SELECT * FROM respuestas", conn)
            except Exception:
                resp = _empty_resp
            conn.close()
        dom["cite_count"] = pd.to_numeric(dom["cite_count"], errors="coerce").fillna(0).astype(int)
        dom["is_ecosystem"] = dom["is_ecosystem"].apply(lambda v: v in (1, True, "1"))
        return met, mar, dom, resp
    except Exception as e:
        print(f"[load_data] ERROR conectando a DB: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), _empty_resp

import time as _time
_data_cache = {}
_CACHE_TTL  = 1800   # segundos — recarga datos cada 30 min automáticamente

def get_data():
    now = _time.monotonic()
    expired = _data_cache.get('loaded_at', 0) + _CACHE_TTL < now
    if not _data_cache or expired:
        met, mar, dom, resp = load_data()
        if met.empty:
            # No cachear estado de error → próximo request reintentará automáticamente
            return met, mar, dom, resp
        _data_cache['MET']       = met
        _data_cache['MAR']       = mar
        _data_cache['DOM']       = dom
        _data_cache['RESP']      = resp
        _data_cache['ok']        = True
        _data_cache['loaded_at'] = now
    return _data_cache['MET'], _data_cache['MAR'], _data_cache['DOM'], _data_cache['RESP']

# ── Constants ─────────────────────────────────────────────────────────
ML = {"chatgpt_search": "ChatGPT", "google_aio": "AI Overview"}
MC = {"chatgpt_search": "#2DD4BF", "google_aio": "#60A5FA"}
BC = {
    # ── Tier 0 ────────────────────────────────────────────────────────
    "Alegra":        "#2DD4BF", "CONTPAQi":    "#60A5FA", "Aspel":       "#FBBF24",
    "QuickBooks":    "#A78BFA", "Bind ERP":    "#F87171", "Microsip":    "#FB923C",
    "Miskuentas":   "#F472B6", "Contalink":   "#34D399", "Siigo":       "#818CF8",
    "Xero":          "#13B5EA", "Holded":      "#E879F9", "Odoo":        "#A3A3A3",
    # ── MX ────────────────────────────────────────────────────────────
    "Factura.com":   "#22D3EE", "Facturama":   "#4ADE80", "SIFO":        "#FCD34D",
    "EdiFactMx":     "#6EE7B7", "Facturador SAT": "#FCA5A5", "Facturaly": "#C4B5FD",
    "Zoho Books":    "#EC4899", "Sage":        "#0891B2", "Heru":        "#10B981",
    "Autofactura":   "#8B5CF6", "ClickBalance": "#7C3AED",
    "SICAR":         "#F59E0B", "Pulpos":      "#38BDF8", "Eleventa":    "#A3E635",
    "ManagementPro": "#E11D48", "MyBusiness":  "#7DD3FC", "Contadigital": "#94A3B8",
    "ALPHA ERP":     "#D97706", "Contafy":     "#6D28D9", "Sinube":      "#059669",
    "SAP":           "#0070F2", "NetSuite":    "#F05A28",
    # ── CO ────────────────────────────────────────────────────────────
    "Vendty":        "#06B6D4", "World Office": "#3B82F6", "Helisa":     "#EF4444",
    "Cuenti":        "#14B8A6", "ContaPyme":   "#F59E0B", "Treinta":     "#6366F1",
    "Siesa":         "#84CC16", "TNS":         "#64748B", "Buk":         "#0EA5E9",
    "Nominapp":      "#D946EF", "Factorial":   "#FB7185", "Loggro":      "#FDE68A",
    "Aliaddo":       "#A7F3D0", "Softland ERP": "#CBD5E1",
    # ── DO ────────────────────────────────────────────────────────────
    "FacturandoRD":  "#F43F5E", "ProVenta":    "#7C3AED",
    # ── CR ────────────────────────────────────────────────────────────
    "GTI":           "#A855F7", "Qupos":       "#10B981", "PROCOM":      "#F97316",
    "Facturele":     "#E879F9",
}
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#94A3B8", family="Inter", size=11),
    margin=dict(t=40, b=40, l=50, r=20),
    xaxis=dict(gridcolor="#1e2d44", zerolinecolor="#1e2d44"),
    yaxis=dict(gridcolor="#1e2d44", zerolinecolor="#1e2d44"),
)

# ── Helpers ───────────────────────────────────────────────────────────
def make_options(series, label_map=None):
    vals = sorted(series.dropna().unique())
    opts = [{"label": "Todos", "value": ""}]
    for v in vals:
        opts.append({"label": (label_map or {}).get(v, v), "value": v})
    return opts


COUNTRY_LABELS = {"CO": "Colombia", "DO": "República Dominicana", "CR": "Costa Rica", "MX": "México"}
MONTH_LABELS = {
    "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic",
}

def ensure_batch_time_cols(df):
    if df is None or len(df) == 0:
        return df
    df = df.copy()
    if "batch_month" not in df.columns or df["batch_month"].isna().all():
        if "batch_date" in df.columns:
            bd = pd.to_datetime(df["batch_date"], errors="coerce")
            df["batch_month"] = bd.dt.strftime("%Y-%m")
        elif "batch_id" in df.columns:
            df["batch_month"] = df["batch_id"].astype(str).str[:6].apply(
                lambda s: f"{s[:4]}-{s[4:6]}" if len(s) >= 6 else None
            )
    return df

def format_period_label(period):
    if not period:
        return "Último mes disponible"
    try:
        year, month = str(period).split("-")
        return f"{MONTH_LABELS.get(month, month)} {year}"
    except Exception:
        return str(period)

def format_batch_label(batch_id, country_id=None, include_country=False):
    from datetime import datetime
    if not batch_id:
        return "Más reciente"
    try:
        dt = datetime.strptime(str(batch_id)[:15], "%Y%m%dT%H%M%S")
        label = f"{dt.day:02d} {MONTH_LABELS.get(dt.strftime('%m'), dt.strftime('%m'))} {dt.strftime('%H:%M')}"
    except Exception:
        label = str(batch_id)
    if include_country and country_id:
        return f"{country_id} · {label}"
    return label

def make_period_options(met, country=""):
    met = ensure_batch_time_cols(met)
    if len(met) == 0:
        return [{"label": "Último mes disponible", "value": ""}]
    base = met.copy()
    if country:
        base = base[base["country_id"] == country]
    if len(base) == 0 or "batch_month" not in base.columns:
        return [{"label": "Último mes disponible", "value": ""}]
    periods = sorted(base["batch_month"].dropna().astype(str).unique(), reverse=True)
    opts = [{"label": "Último mes disponible", "value": ""}]
    opts.extend({"label": format_period_label(p), "value": p} for p in periods)
    return opts

def make_run_options(met, country="", period=""):
    met = ensure_batch_time_cols(met)
    if len(met) == 0 or "batch_id" not in met.columns:
        return [{"label": "Más reciente", "value": ""}]
    base = met.copy()
    if country:
        base = base[base["country_id"] == country]
    if period:
        base = base[base["batch_month"] == period]
    if len(base) == 0:
        return [{"label": "Más reciente", "value": ""}]
    run_meta = (
        base.groupby("batch_id", as_index=False)
        .agg(country_id=("country_id", "first"), batch_date=("batch_date", "first"))
        .sort_values("batch_id", ascending=False)
    )
    include_country = not bool(country)
    opts = [{"label": "Más reciente", "value": ""}]
    for _, row in run_meta.iterrows():
        opts.append({
            "label": format_batch_label(row["batch_id"], row.get("country_id"), include_country=include_country),
            "value": row["batch_id"]
        })
    return opts

def resolve_effective_period_and_batch(met, country="", period="", run=""):
    met = ensure_batch_time_cols(met)
    if len(met) == 0:
        return None, None, 0, met
    base = met.copy()
    if country:
        base = base[base["country_id"] == country]
    if len(base) == 0:
        return None, None, 0, base
    periods = sorted(base["batch_month"].dropna().astype(str).unique(), reverse=True) if "batch_month" in base.columns else []
    effective_period = period if period and period in periods else (periods[0] if periods else None)
    if effective_period:
        base = base[base["batch_month"] == effective_period]
    runs = sorted(base["batch_id"].dropna().astype(str).unique(), reverse=True)
    effective_batch = run if run and run in runs else (runs[0] if runs else None)
    return effective_period, effective_batch, len(runs), base

def kpi_card(label, value, color, sub, tooltip=""):
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(value, className="kpi-value", style={"color": color}),
        html.Div(sub, className="kpi-sub"),
    ]
    if tooltip:
        children.append(
            html.Div(
                dcc.Markdown(tooltip, dangerously_allow_html=False),
                className="kpi-tooltip",
            )
        )
    return html.Div(className="kpi-card", children=children)

def hex_to_rgba(h, a):
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"

# ── App ───────────────────────────────────────────────────────────────
app = Dash(__name__, title="Alegra AEO — Golden Stack", suppress_callback_exceptions=True)
server = app.server  # for deployment

@server.route("/healthz")
def healthz():
    if _data_cache and not _data_cache.get('ok', True):
        return {"status": "db_error"}, 503
    return {"status": "ok"}, 200

app.index_string = '''<!DOCTYPE html>
<html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#0B1120;--surface:#111827;--card:#1a2234;--border:#2a3550;--text:#F1F5F9;--muted:#94A3B8;--dim:#64748B;--teal:#2DD4BF;--blue:#60A5FA;--amber:#FBBF24;--green:#34D399;--red:#F87171;--orange:#FB923C;--purple:#A78BFA;--pink:#F472B6;
/* Override Dash system CSS variables for dark theme */
--Dash-Fill-Inverse-Strong:#1a2234;--Dash-Fill-Interactive-Strong:#2DD4BF;--Dash-Fill-Interactive-Weak:rgba(45,212,191,0.08);--Dash-Text-Primary:#F1F5F9;--Dash-Text-Secondary:rgba(241,245,249,0.7);--Dash-Text-Weak:#94A3B8;--Dash-Stroke-Strong:#2a3550;--Dash-Stroke-Weak:rgba(42,53,80,0.5);--Dash-Fill-Primary-Hover:rgba(45,212,191,0.12);--Dash-Fill-Primary-Active:rgba(45,212,191,0.2);--Dash-Shading-Weak:rgba(0,0,0,0.3)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
#react-entry-point{min-height:100vh}
._dash-app-content{display:flex;min-height:100vh}
.app-root{display:flex;min-height:100vh;width:100%}
.sidebar{width:220px;background:var(--surface);border-right:1px solid var(--border);padding:20px 14px;flex-shrink:0;position:sticky;top:0;height:100vh;overflow-y:auto}
.main{flex:1;padding:20px 28px;max-width:1300px}
.sidebar-title{font-size:15px;font-weight:700;margin-bottom:2px}
.sidebar-sub{font-size:11px;color:var(--muted);margin-bottom:18px}
.filter-group{margin-bottom:14px}
.filter-label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin-bottom:5px}
.sidebar-divider{border:none;border-top:1px solid var(--border);margin:14px 0}
.sidebar-info{font-size:10px;color:var(--dim);line-height:1.6}
.header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}
.header h1{font-size:20px;font-weight:700;margin-bottom:2px}
.header-sub{font-size:11px;color:var(--muted)}
.header-badges{display:flex;gap:6px;margin-top:6px}
.badge{padding:3px 10px;border-radius:12px;font-size:10px;font-weight:600}
.section-label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin:24px 0 10px 0}
.kpi-row{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}
.kpi-card{position:relative;background:linear-gradient(135deg,var(--card),#1e2a3f);border:1px solid var(--border);border-radius:12px;padding:14px 12px;text-align:center;transition:border-color .2s}
.kpi-card:hover{border-color:#475569}
.kpi-label{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:3px}
.kpi-value{font-size:24px;font-weight:800;letter-spacing:-.02em;line-height:1.1}
.kpi-sub{font-size:9px;color:var(--dim);margin-top:3px}
.kpi-tooltip{display:none;position:absolute;bottom:calc(100% + 10px);left:50%;transform:translateX(-50%);background:#0d1829;border:1px solid #334155;border-radius:10px;padding:11px 14px;font-size:11px;color:#CBD5E1;line-height:1.55;width:230px;text-align:left;z-index:9999;pointer-events:none;box-shadow:0 8px 32px rgba(0,0,0,.6);white-space:normal}
.kpi-tooltip b{color:#F1F5F9;font-weight:600}
.kpi-tooltip p{margin:0;padding:0}
.kpi-tooltip::after{content:'';position:absolute;top:100%;left:50%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#334155}
.kpi-card:hover .kpi-tooltip{display:block}
.chart-row{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.chart-box{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px;overflow:hidden}
.chart-half{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.leader-list{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;max-height:400px;overflow-y:auto}
.leader-row{display:flex;justify-content:space-between;align-items:center;padding:9px 12px;border-bottom:1px solid var(--border)}
.leader-row:last-child{border-bottom:none}
.overall-leader{margin-top:14px;padding:12px 16px;border-radius:10px;border:1px solid var(--teal);background:rgba(45,212,191,0.05)}
.table-wrap{max-height:320px;overflow-y:auto;border:1px solid var(--border);border-radius:10px}
.insight-row{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.insight-box{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.insight-title{font-size:11px;font-weight:700;margin-bottom:5px}
.insight-body{font-size:11px;color:var(--muted);line-height:1.6}
.footer{text-align:center;font-size:10px;color:var(--dim);margin-top:28px;padding-top:14px;border-top:1px solid var(--border)}
.footer a{color:var(--dim)}
/* ── Dash Dropdown (new Radix-based component) ── */
.dash-dropdown{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:6px!important;color:var(--text)!important;font-size:12px!important;padding:6px 10px!important;cursor:pointer!important;width:100%!important}
.dash-dropdown:hover{border-color:var(--teal)!important}
.dash-dropdown[data-state="open"]{border-color:var(--teal)!important;box-shadow:0 0 0 1px var(--teal)!important}
.dash-dropdown .dash-dropdown-value,.dash-dropdown .dash-dropdown-value-item,.dash-dropdown .dash-dropdown-value-item span{color:var(--text)!important;font-weight:500!important;font-size:12px!important}
.dash-dropdown .dash-dropdown-trigger-icon{color:var(--muted)!important}
/* Dropdown menu/popover */
[data-radix-popper-content-wrapper]{z-index:9999!important}
.dash-dropdown-options,.dash-options-list{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:8px!important;box-shadow:0 8px 24px rgba(0,0,0,0.4)!important;overflow:hidden!important}
.dash-options-list-option,.dash-dropdown-option{background:var(--card)!important;color:var(--text)!important;padding:8px 12px!important;cursor:pointer!important;font-size:12px!important;border:none!important;transition:background .1s!important}
.dash-options-list-option:hover,.dash-dropdown-option:hover{background:var(--surface)!important;color:var(--teal)!important}
.dash-options-list-option.selected,.dash-dropdown-option.selected{background:rgba(45,212,191,0.12)!important;color:var(--teal)!important;font-weight:600!important}
.dash-options-list-option input[type="radio"]{accent-color:var(--teal)!important}
/* Legacy Select dropdowns (fallback) */
.Select-control,.Select-menu-outer{background:var(--card)!important;border-color:var(--border)!important;color:var(--text)!important;font-size:12px!important}
.Select-value-label,.Select-value{color:var(--text)!important}
.Select-option{background:var(--card)!important;color:var(--text)!important}
.Select-option.is-focused{background:var(--surface)!important;color:var(--teal)!important}
.Select-option.is-selected{background:var(--border)!important;color:var(--teal)!important;font-weight:600!important}
/* ── Dash DataTable ── */
/* Override Dash internal --hover variable (default #fdfdfd = near-white, causes invisible rows on dark theme) */
.dash-spreadsheet-inner{--hover:rgba(45,212,191,0.10)!important}
.dash-spreadsheet-inner tr{--hover:rgba(45,212,191,0.10)!important}
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th{background:var(--surface)!important;color:var(--muted)!important;border-bottom:2px solid var(--border)!important;font-size:9px!important;text-transform:uppercase;letter-spacing:.05em;font-weight:600}
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td{background:var(--card)!important;color:var(--text)!important;border-bottom:1px solid var(--border)!important;font-size:11px!important}
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner tr:hover{background-color:rgba(45,212,191,0.08)!important}
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner tr:hover td{background:rgba(45,212,191,0.08)!important;color:var(--text)!important}
/* Selected/focused cell overrides — must beat Dash inline styles */
td.dash-cell.focused,td.dash-cell.cell--selected.focused{background:rgba(45,212,191,0.15)!important;color:var(--text)!important;outline:1px solid var(--teal)!important;box-shadow:none!important;border-color:var(--teal)!important}
td.dash-cell.cell--selected{background:rgba(45,212,191,0.08)!important;color:var(--text)!important}
td.dash-cell.focused .dash-cell-value,td.dash-cell.cell--selected .dash-cell-value{color:var(--text)!important;background:transparent!important}
input.dash-cell-value,div.dash-cell-value{color:var(--text)!important;background:transparent!important}
/* Ensure all cell content is visible in every state */
td.dash-cell:hover,td.dash-cell:hover .dash-cell-value,
td.dash-cell:focus,td.dash-cell:focus .dash-cell-value,
td.dash-cell:focus-within,td.dash-cell:focus-within .dash-cell-value,
td.dash-cell:active,td.dash-cell:active .dash-cell-value{color:var(--text)!important;background:transparent!important}
.dash-spreadsheet-inner td.dash-cell[style]{color:var(--text)!important}
/* Override Dash input-active state (cell enters edit mode on click) */
.input-active.dash-cell-value,.dash-cell-value.focused,.dash-cell-value.unfocused{color:var(--text)!important;background:transparent!important;caret-color:var(--teal)!important}
/* Nuclear override: any td anywhere in table must have readable text */
.dash-spreadsheet-container td,.dash-spreadsheet-container td *,.dash-spreadsheet-container td div,.dash-spreadsheet-container td span,.dash-spreadsheet-container td input{color:var(--text)!important}
.dash-spreadsheet-container td input::selection{background:var(--teal)!important;color:var(--bg)!important}
/* Rows: full-row hover highlight — override TR *and* TD to prevent white bleed-through */
.dash-spreadsheet-container tr:hover{background-color:rgba(45,212,191,0.06)!important}
.dash-spreadsheet-container tr:hover td{background:rgba(45,212,191,0.06)!important}
/* Kill Dash built-in :not(.cell--selected) tr:hover rule */
.dash-spreadsheet-inner :not(.cell--selected) tr:hover{background-color:rgba(45,212,191,0.08)!important}
@media(max-width:1100px){.kpi-row{grid-template-columns:repeat(3,1fr)}.chart-row,.insight-row{grid-template-columns:1fr}.chart-half{grid-template-columns:1fr}.sidebar{display:none}}
/* Drill-down panel */
.drill-panel{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-top:14px}
.drill-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--border)}
.drill-header-left{flex:1}
.drill-header-top{display:flex;align-items:center;gap:10px;margin-bottom:6px;flex-wrap:wrap}
.drill-prompt-text{font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:4px}
.drill-meta{font-size:10px;color:var(--dim)}
.drill-close{background:none;border:1px solid var(--border);color:var(--muted);padding:5px 14px;border-radius:6px;cursor:pointer;font-size:11px;font-family:Inter,sans-serif;white-space:nowrap}
.drill-close:hover{background:var(--surface);color:var(--text)}
.drill-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px}
@media(max-width:1100px){.drill-grid{grid-template-columns:1fr}}
.drill-col{min-width:0}
.drill-col-title{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--border)}
.drill-metric-row{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid rgba(42,53,80,0.4)}
.drill-metric-row:last-child{border-bottom:none}
.drill-metric-label{font-size:11px;color:var(--muted)}
.drill-metric-value{font-size:13px;font-weight:700;color:var(--teal)}
.drill-brand-row{display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:1px solid rgba(42,53,80,0.4);font-size:11px}
.drill-brand-row:last-child{border-bottom:none}
.drill-brand-trophy{font-size:13px;width:18px;text-align:center;flex-shrink:0}
.drill-brand-name{font-weight:600;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.drill-brand-rank{font-weight:700;color:var(--text);white-space:nowrap}
.drill-brand-info{font-size:10px;color:var(--dim);white-space:nowrap}
.drill-dom-header{display:flex;gap:16px;margin-bottom:10px;font-size:11px}
.drill-dom-header-item{display:flex;flex-direction:column}
.drill-dom-header-label{font-size:10px;color:var(--dim);font-weight:600;text-transform:uppercase;letter-spacing:.06em}
.drill-dom-header-value{font-size:14px;font-weight:700}
.drill-dom-section-title{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin:10px 0 6px 0}
.drill-dom-chips{display:flex;flex-wrap:wrap;gap:5px}
.domain-chip{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:20px;font-size:10px;font-weight:500;background:rgba(26,34,52,0.8);border:1px solid var(--border)}
.domain-chip.eco{border-color:var(--teal);color:var(--teal)}
.domain-chip.ext{border-color:var(--dim);color:var(--muted)}
.domain-chip .chip-count{font-weight:700}
/* Response viewer */
.drill-response-section{margin-top:18px;padding-top:16px;border-top:1px solid var(--border)}
.drill-response-title{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin-bottom:10px}
.drill-rep-tabs{display:flex;gap:6px;margin-bottom:12px}
.drill-rep-tab{padding:5px 14px;border-radius:6px;font-size:10px;font-weight:600;cursor:pointer;border:1px solid var(--border);background:transparent;color:var(--muted);font-family:Inter,sans-serif;transition:all .15s}
.drill-rep-tab:hover{background:var(--surface);color:var(--text)}
.drill-rep-tab.active{background:var(--teal);color:var(--bg);border-color:var(--teal)}
.drill-response-box{background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:16px 18px;max-height:400px;overflow-y:auto;font-size:11px;line-height:1.7;color:var(--muted);white-space:pre-wrap;word-wrap:break-word}
.drill-response-box::-webkit-scrollbar{width:6px}
.drill-response-box::-webkit-scrollbar-track{background:var(--bg)}
.drill-response-box::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.drill-response-len{font-size:9px;color:var(--dim);margin-top:6px;text-align:right}
</style></head><body>{%app_entry%}{%config%}{%scripts%}{%renderer%}</body></html>'''

# ── Layout ────────────────────────────────────────────────────────────
def serve_layout():
    MET, MAR, DOM, RESP = get_data()
    db_ok = not MET.empty
    error_banner = html.Div(
        "⚠️  No se pudo conectar a la base de datos. Recarga la página en unos segundos para reintentar.",
        style={
            "background": "#7f1d1d", "color": "#fca5a5", "padding": "10px 20px",
            "textAlign": "center", "fontSize": "12px", "fontWeight": "600",
            "borderBottom": "1px solid #991b1b", "letterSpacing": ".02em"
        }
    ) if not db_ok else None
    return html.Div(className="app-root", children=[
    error_banner,
    html.Aside(className="sidebar", children=[
        html.Div("\U0001f4ca Alegra AEO", className="sidebar-title"),
        html.Div("Golden Stack Dashboard", className="sidebar-sub"),
        html.Hr(className="sidebar-divider"),
        html.Div(className="filter-group", children=[
            html.Div("País", className="filter-label"),
            dcc.Dropdown(id="f-pais", options=make_options(MET["country_id"]),
                         value="", clearable=False, searchable=False),
        ]),
        html.Div(className="filter-group", children=[
            html.Div("Funnel", className="filter-label"),
            dcc.Dropdown(id="f-funnel", options=make_options(MET["funnel_stage"]),
                         value="", clearable=False, searchable=False),
        ]),
        html.Div(className="filter-group", children=[
            html.Div("Categoría", className="filter-label"),
            dcc.Dropdown(id="f-cat", options=make_options(MET["product_category"]),
                         value="", clearable=False, searchable=False),
        ]),
        html.Div(className="filter-group", children=[
            html.Div("Motor", className="filter-label"),
            dcc.Dropdown(id="f-motor", options=make_options(MET["model_source"], ML),
                         value="", clearable=False, searchable=False),
        ]),
        html.Div(className="filter-group", children=[
            html.Div("Mes", className="filter-label"),
            dcc.Dropdown(id="f-period", options=make_period_options(MET),
                         value="", clearable=False, searchable=False),
        ]),
        html.Div(className="filter-group", children=[
            html.Div("Corrida", className="filter-label"),
            dcc.Dropdown(id="f-run", options=[{"label": "Más reciente", "value": ""}],
                         value="", clearable=False, searchable=False),
        ]),
        html.Hr(className="sidebar-divider"),
        html.Div(id="sidebar-info", className="sidebar-info"),
    ]),
    html.Main(className="main", id="main-content", children=[
        # Header
        html.Div(className="header", children=[
            html.Div([
                html.H1("Alegra AEO \u2014 Golden Stack"),
                html.Div(id="header-sub", className="header-sub"),
            ]),
            html.Div(id="header-badges", className="header-badges"),
        ]),
        # KPIs
        html.Div("Promedios Globales", className="section-label"),
        html.Div(id="kpi-row", className="kpi-row"),
        # Comparativo por Motor
        html.Div("Comparativo por Motor", className="section-label"),
        html.Div(className="chart-row", children=[
            html.Div(className="chart-box", children=[dcc.Graph(id="chart-mr", config={"displayModeBar": False})]),
            html.Div(className="chart-box", children=[dcc.Graph(id="chart-pos", config={"displayModeBar": False})]),
            html.Div(className="chart-box", children=[dcc.Graph(id="chart-eco", config={"displayModeBar": False})]),
        ]),
        # Brand Ranking
        html.Div("Ranking de Marcas Competidoras", className="section-label"),
        html.Div(className="chart-half", children=[
            html.Div(className="chart-box", children=[dcc.Graph(id="chart-brands", config={"displayModeBar": False})]),
            html.Div([
                html.Div("Marca Líder por Prompt \u00d7 Motor", style={"fontSize": "12px", "fontWeight": "600", "marginBottom": "8px"}),
                html.Div(id="leader-list", className="leader-list"),
                html.Div(id="overall-leader"),
            ]),
        ]),
        # Brand detail table
        html.Div("Marcas Mencionadas por Prompt", className="section-label"),
        html.Div(className="table-wrap", children=[
            dash_table.DataTable(
                id="brand-table",
                columns=[
                    {"name": "Prompt", "id": "prompt_id"},
                    {"name": "Motor", "id": "motor"},
                    {"name": "Marca", "id": "brand_name"},
                    {"name": "Rank Avg", "id": "rank_avg"},
                    {"name": "Presencia %", "id": "presence"},
                    {"name": "Menciones", "id": "brand_mentions_total"},
                    {"name": "Ranks por Réplica", "id": "brand_ranks_by_rep"},
                ],
                style_header={"backgroundColor": "#111827", "color": "#94A3B8", "fontWeight": "600",
                              "fontSize": "9px", "textTransform": "uppercase", "letterSpacing": "0.05em",
                              "borderBottom": "2px solid #2a3550"},
                style_cell={"backgroundColor": "#1a2234", "color": "#F1F5F9", "border": "1px solid #2a3550",
                            "fontSize": "11px", "fontFamily": "Inter", "padding": "6px 8px", "textAlign": "left"},
                style_data_conditional=[
                    {"if": {"filter_query": '{is_alegra} eq 1'}, "backgroundColor": "rgba(45,212,191,0.08)", "fontWeight": "600"},
                    {"if": {"state": "selected"}, "backgroundColor": "rgba(45,212,191,0.1)", "color": "#F1F5F9", "border": "1px solid #2DD4BF"},
                    {"if": {"state": "active"}, "backgroundColor": "rgba(45,212,191,0.15)", "color": "#F1F5F9", "border": "1px solid #2DD4BF"},
                ],
                css=[{"selector": ".dash-spreadsheet-inner", "rule": "--hover: rgba(45,212,191,0.10) !important;"},
                     {"selector": ".dash-spreadsheet-inner tr", "rule": "--hover: rgba(45,212,191,0.10) !important;"},
                     {"selector": "tr:hover", "rule": "background-color: rgba(45,212,191,0.08) !important;"},
                     {"selector": "tr:hover td", "rule": "background: rgba(45,212,191,0.08) !important; color: #F1F5F9 !important;"},
                     {"selector": "td.dash-cell", "rule": "color: #F1F5F9 !important;"},
                     {"selector": ".dash-cell-value", "rule": "color: inherit !important; background: transparent !important;"},
                     {"selector": "td.focused", "rule": "background: rgba(45,212,191,0.15) !important; color: #F1F5F9 !important;"},
                     {"selector": "td.cell--selected", "rule": "background: rgba(45,212,191,0.1) !important; color: #F1F5F9 !important;"},
                ],
                page_size=50, style_table={"overflowY": "auto", "maxHeight": "320px"},
            ),
        ]),
        # Prompt detail table
        html.Div("Detalle por Prompt", className="section-label"),
        html.Div(className="table-wrap", children=[
            dash_table.DataTable(
                id="prompt-table",
                columns=[
                    {"name": "ID", "id": "prompt_id"},
                    {"name": "Prompt", "id": "prompt_short"},
                    {"name": "Funnel", "id": "funnel_stage"},
                    {"name": "Categoría", "id": "product_category"},
                    {"name": "Motor", "id": "motor"},
                    {"name": "Mention", "id": "mention_rate"},
                    {"name": "Citation", "id": "citation_rate"},
                    {"name": "Consist.", "id": "consistency_score"},
                    {"name": "Pos. Avg", "id": "avg_rank_alegra"},
                    {"name": "Eco Share", "id": "eco_share_pct"},
                    {"name": "Citas", "id": "total_cites"},
                ],
                style_header={"backgroundColor": "#111827", "color": "#94A3B8", "fontWeight": "600",
                              "fontSize": "9px", "textTransform": "uppercase", "letterSpacing": "0.05em",
                              "borderBottom": "2px solid #2a3550"},
                style_cell={"backgroundColor": "#1a2234", "color": "#F1F5F9", "border": "1px solid #2a3550",
                            "fontSize": "11px", "fontFamily": "Inter", "padding": "6px 8px", "textAlign": "left"},
                style_data_conditional=[
                    {"if": {"state": "selected"}, "backgroundColor": "rgba(45,212,191,0.1)", "color": "#F1F5F9", "border": "1px solid #2DD4BF"},
                    {"if": {"state": "active"}, "backgroundColor": "rgba(45,212,191,0.15)", "color": "#F1F5F9", "border": "1px solid #2DD4BF"},
                ],
                css=[{"selector": ".dash-spreadsheet-inner", "rule": "--hover: rgba(45,212,191,0.10) !important;"},
                     {"selector": ".dash-spreadsheet-inner tr", "rule": "--hover: rgba(45,212,191,0.10) !important;"},
                     {"selector": "tr:hover", "rule": "background-color: rgba(45,212,191,0.08) !important;"},
                     {"selector": "tr:hover td", "rule": "background: rgba(45,212,191,0.08) !important; color: #F1F5F9 !important;"},
                     {"selector": "td.dash-cell", "rule": "color: #F1F5F9 !important;"},
                     {"selector": ".dash-cell-value", "rule": "color: inherit !important; background: transparent !important;"},
                     {"selector": "td.focused", "rule": "background: rgba(45,212,191,0.15) !important; color: #F1F5F9 !important; outline: 1px solid #2DD4BF !important;"},
                     {"selector": "td.cell--selected", "rule": "background: rgba(45,212,191,0.1) !important; color: #F1F5F9 !important;"},
                ],
                page_size=50, style_table={"overflowY": "auto", "maxHeight": "320px"},
            ),
        ]),
        # Store for prompt-table row keys (survives callback timing issues)
        dcc.Store(id="prompt-table-keys", data=[]),
        # Drill-down panel (hidden by default, shown on row click)
        html.Div(id="drill-panel", className="drill-panel", style={"display": "none"}, children=[
            html.Div(style={"display": "flex", "justifyContent": "flex-end", "marginBottom": "0px"}, children=[
                html.Button("Cerrar", id="drill-close-btn", className="drill-close"),
            ]),
            html.Div(id="drill-panel-content"),
        ]),
        # Domain maps
        html.Div("Mapa de Dominios Citados", className="section-label"),
        html.Div(className="chart-half", children=[
            html.Div(className="chart-box", children=[
                html.Div(id="eco-dom-title", style={"fontSize": "12px", "fontWeight": "600", "marginBottom": "6px"}),
                dcc.Graph(id="chart-eco-doms", config={"displayModeBar": False}),
            ]),
            html.Div(className="chart-box", children=[
                html.Div(id="ext-dom-title", style={"fontSize": "12px", "fontWeight": "600", "marginBottom": "6px"}),
                dcc.Graph(id="chart-ext-doms", config={"displayModeBar": False}),
            ]),
        ]),
        # Insights
        html.Div("Insights", className="section-label"),
        html.Div(id="insight-row", className="insight-row"),
        # Footer
        html.Div(className="footer", children=[
            html.Span(id="footer-batch"),
            " \u00b7 Arquitectura Dual (OpenAI + DataForSEO) \u00b7 ",
            html.A("Created with Perplexity Computer", href="https://www.perplexity.ai/computer", target="_blank"),
        ]),
    ]),
    ])

app.layout = serve_layout

# ── Dropdowns reactivos ───────────────────────────────────────────────
@callback(
    Output("f-period", "options"),
    Output("f-period", "value"),
    Input("f-pais", "value"),
    State("f-period", "value"),
)
def update_period_dropdown(pais, current_period):
    MET, _, _, _ = get_data()
    opts = make_period_options(MET, pais)
    valid = {o["value"] for o in opts}
    value = current_period if current_period in valid and current_period != "" else ""
    return opts, value

@callback(
    Output("f-run", "options"),
    Output("f-run", "value"),
    Input("f-pais", "value"),
    Input("f-period", "value"),
    State("f-run", "value"),
)
def update_run_dropdown(pais, period, current_run):
    MET, _, _, _ = get_data()
    opts = make_run_options(MET, pais, period)
    valid = {o["value"] for o in opts}
    value = current_run if current_run in valid and current_run != "" else ""
    return opts, value

# ── Callback ──────────────────────────────────────────────────────────
@callback(
    Output("header-sub", "children"),
    Output("header-badges", "children"),
    Output("sidebar-info", "children"),
    Output("footer-batch", "children"),
    Output("kpi-row", "children"),
    Output("chart-mr", "figure"),
    Output("chart-pos", "figure"),
    Output("chart-eco", "figure"),
    Output("chart-brands", "figure"),
    Output("leader-list", "children"),
    Output("overall-leader", "children"),
    Output("brand-table", "data"),
    Output("prompt-table", "data"),
    Output("eco-dom-title", "children"),
    Output("chart-eco-doms", "figure"),
    Output("ext-dom-title", "children"),
    Output("chart-ext-doms", "figure"),
    Output("insight-row", "children"),
    Output("prompt-table-keys", "data"),
    Input("f-pais", "value"),
    Input("f-funnel", "value"),
    Input("f-cat", "value"),
    Input("f-motor", "value"),
    Input("f-period", "value"),
    Input("f-run", "value"),
)
def update_dashboard(pais, funnel, cat, motor, period, run):
    MET, MAR, DOM, RESP = get_data()
    MET = ensure_batch_time_cols(MET)

    effective_period, effective_batch, period_run_count, period_base = resolve_effective_period_and_batch(
        MET, pais, period, run
    )

    # ── Filter ────────────────────────────────────────────────────────
    fm = MET.copy()
    fb = MAR.copy()
    if pais:
        fm = fm[fm["country_id"] == pais]
        fb = fb[fb["country_id"] == pais]
    if funnel:
        fm = fm[fm["funnel_stage"] == funnel]
        fb = fb[fb["funnel_stage"] == funnel]
    if cat:
        fm = fm[fm["product_category"] == cat]
        fb = fb[fb["product_category"] == cat]
    if motor:
        fm = fm[fm["model_source"] == motor]
        fb = fb[fb["model_source"] == motor]
    if effective_batch:
        fm = fm[fm["batch_id"] == effective_batch]
        fb = fb[fb["batch_id"] == effective_batch]

    # Filter dominios by batch first, then by keys present in filtered metricas
    fd_base = DOM[DOM["batch_id"] == effective_batch] if effective_batch else DOM.copy()
    keys = set(fm["prompt_id"] + "|" + fm["model_source"])
    fd = fd_base[fd_base.apply(lambda r: f"{r['prompt_id']}|{r['model_source']}" in keys, axis=1)]

    period_label = format_period_label(effective_period)
    batch_label = format_batch_label(effective_batch, pais, include_country=False)
    n = len(fm)
    empty_fig = go.Figure().update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter", size=11), height=320)

    if n == 0:
        empty = "Sin datos para los filtros seleccionados."
        period_info = period_label if effective_period else "Sin período"
        return (empty, [], f"País: {COUNTRY_LABELS.get(pais, pais) if pais else 'Todos'} · {period_info}",
                f"{period_info} · {batch_label}", [],
                empty_fig, empty_fig, empty_fig, empty_fig, [], [],
                [], [], "", empty_fig, "", empty_fig, [], [])

    # ── Header ────────────────────────────────────────────────────────
    country_label = COUNTRY_LABELS.get(pais, pais) if pais else "Todos los países"
    t_ok = int(fm["num_success"].sum())
    t_r = int(fm["num_replicates"].sum())
    runs_msg = (
        f"mostrando corrida más reciente de {period_run_count} disponibles"
        if period_run_count > 1 and not run else
        (f"corrida seleccionada · {period_run_count} disponibles" if period_run_count > 1 else "1 corrida disponible")
    )
    header_sub = f"Dashboard MVP · {country_label} · {period_label} · {runs_msg} · {n} prompt×motor"
    header_badges = [
        html.Span(f"● {t_ok}/{t_r} OK", className="badge",
                  style={"background": "#34D39922", "color": "#34D399"}),
        html.Span(country_label, className="badge",
                  style={"background": "#60A5FA22", "color": "#60A5FA"}),
    ]
    if effective_batch:
        header_badges.append(
            html.Span(format_batch_label(effective_batch, pais, include_country=False), className="badge",
                      style={"background": "#FBBF2422", "color": "#FBBF24"})
        )
    if period_run_count > 1:
        header_badges.append(
            html.Span(f"{period_run_count} corridas en el mes", className="badge",
                      style={"background": "#FB923C22", "color": "#FB923C"})
        )
    sidebar_info = f"País: {country_label}\nMes: {period_label}\nCorrida efectiva: {format_batch_label(effective_batch, pais, include_country=False)}\nArquitectura Dual"
    footer_batch = f"{country_label} · {period_label} · {format_batch_label(effective_batch, pais, include_country=False)}"

    # ── KPIs ──────────────────────────────────────────────────────────
    avg_mr = fm["mention_rate"].mean()
    avg_cr = fm["citation_rate"].mean()
    avg_cs = (fm["mention_rate"] >= 0.67).mean() * 100 if len(fm) else 0
    avg_rk = fm["avg_rank_alegra"].mean()
    eco_t = int(fm["eco_cites"].sum())
    tot_t = int(fm["total_cites"].sum())
    eco_pct = (eco_t / tot_t * 100) if tot_t > 0 else 0
    n_prompts = fm["prompt_id"].nunique()

    # Brand aggregation
    b_agg = fb.groupby("brand_name").agg(
        rank_sum=("brand_rank_avg", "sum"),
        count=("brand_rank_avg", "count"),
        mentions=("brand_mentions_total", "sum"),
    ).reset_index()
    b_agg["weighted_pos"]  = b_agg["rank_sum"] / b_agg["count"]
    n_combos               = len(fm)
    b_agg["coverage_pct"]  = (b_agg["count"] / n_combos * 100).round(1)
    b_agg = b_agg.sort_values(
        ["weighted_pos", "coverage_pct", "mentions"],
        ascending=[True, False, False]
    )

    # KPI "Marca Líder" — lógica jerárquica: primero persistencia, luego posición
    # Cohorte persistente en cascada: 50% → 30% → 15% → sin líder
    # Dentro del cohorte: weighted_pos asc, coverage_pct desc, mentions desc
    def _find_leader(agg):
        for threshold in (50, 30, 15):
            cohort = agg[agg["coverage_pct"] >= threshold].sort_values(
                ["weighted_pos", "coverage_pct", "mentions"],
                ascending=[True, False, False]
            )
            if len(cohort):
                return cohort.iloc[0], threshold
        return None, None

    top_b, _leader_threshold = _find_leader(b_agg)
    if top_b is not None:
        _leader_sub = f"Pos. #{top_b['weighted_pos']:.1f} · {top_b['coverage_pct']:.0f}% presencia"
    else:
        _leader_sub = "Sin cohorte persistente"

    kpis = [
        kpi_card("Mention Rate", f"{round(avg_mr * 100)}%", "#2DD4BF", f"Promedio {n} combos",
            tooltip=(
                "**¿Qué mide?** Porcentaje de réplicas donde Alegra es mencionada "
                "en la respuesta del modelo.\n\n"
                "**Cálculo:** promedio de `mention_rate` sobre todos los combos "
                "prompt × motor activos. Cada combo corre 3 réplicas; "
                "mention_rate = réplicas con mención / 3.\n\n"
                f"**Base:** {n} combos prompt × motor en el filtro actual."
            )),
        kpi_card("Citation Rate", f"{round(avg_cr * 100)}%", "#60A5FA", "Marca citada como fuente",
            tooltip=(
                "**¿Qué mide?** Porcentaje de réplicas donde un dominio del "
                "ecosistema Alegra (alegra.com, ayuda.alegra.com, etc.) aparece "
                "citado como fuente por el modelo.\n\n"
                "**Diferencia con Mention Rate:** Alegra puede ser *mencionada* "
                "en texto sin ser *citada* como enlace fuente. Citation Rate "
                "mide autoridad percibida, no solo mención."
            )),
        kpi_card("Consistency", f"{round(avg_cs)}%", "#FBBF24", "Combos con \u22652/3 r\xe9plicas",
            tooltip=(
                "**¿Qué mide?** Porcentaje de combos prompt × motor donde Alegra "
                "aparece en **al menos 2 de 3 réplicas** (mention_rate ≥ 0.67).\n\n"
                "**Por qué importa:** los LLMs son no deterministas. Si solo "
                "aparecemos en 1/3 réplicas, la mención es ruido. "
                "Consistency mide cuán *estable* es nuestra presencia.\n\n"
                "**Interpretación:** 100% = Alegra aparece en ≥2/3 réplicas "
                "en todos los prompts del filtro."
            )),
        kpi_card("Alegra Pos. Avg", f"#{avg_rk:.1f}", "#FB923C", "Rank ponderado Alegra",
            tooltip=(
                "**¿Qué mide?** Posición promedio de Alegra en los rankings "
                "generados por el modelo, considerando solo los combos donde "
                "Alegra es mencionada.\n\n"
                "**Escala:** #1 = primera marca mencionada. Menor número = "
                "mejor posición.\n\n"
                "**Nota:** si Alegra no aparece en un combo, ese combo "
                "no entra en el promedio."
            )),
        kpi_card("Marca Líder", top_b["brand_name"] if top_b is not None else "\u2014", "#F472B6",
                 _leader_sub,
            tooltip=(
                "**¿Qué mide?** La marca con mayor presencia y mejor posición "
                "dentro del cohorte persistente del filtro actual.\n\n"
                "**Lógica jerárquica:**\n"
                "1. Cohorte ≥50% presencia → gana la de mejor posición\n"
                "2. Si no hay, cohorte ≥30% → ídem\n"
                "3. Si no hay, cohorte ≥15% → ídem\n"
                "4. Si nadie llega al 15%, no hay Marca Líder\n\n"
                "**Presencia** = % de combos donde la marca aparece al menos una vez."
            )),
        kpi_card("Eco Share", f"{round(eco_pct)}%", "#34D399", f"{eco_t}/{tot_t} citas ecosistema",
            tooltip=(
                "**¿Qué mide?** Porcentaje de citas totales que apuntan al "
                "ecosistema Alegra vs. todos los dominios citados.\n\n"
                "**Ecosistema Alegra:** alegra.com, ayuda.alegra.com, "
                "blog.alegra.com y dominios relacionados.\n\n"
                f"**En este filtro:** {eco_t} citas ecosistema de {tot_t} totales. "
                "Mayor Eco Share = los modelos perciben a Alegra como "
                "fuente de autoridad en el tema."
            )),
    ]

    # ── Chart 1: Mention & Citation by Motor ──────────────────────────
    mg = fm.groupby("model_source").agg(mr=("mention_rate", "mean"), cr=("citation_rate", "mean")).reset_index()
    fig_mr = go.Figure()
    fig_mr.add_trace(go.Bar(
        name="Mention Rate", x=mg["model_source"].map(ML), y=mg["mr"],
        marker_color=mg["model_source"].map(MC).tolist(),
        text=mg["mr"].apply(lambda v: f"{round(v*100)}%"), textposition="outside",
        textfont=dict(size=13, color="#F1F5F9"),
    ))
    fig_mr.add_trace(go.Bar(
        name="Citation Rate", x=mg["model_source"].map(ML), y=mg["cr"],
        marker_color=mg["model_source"].apply(lambda m: hex_to_rgba(MC.get(m, "#999"), 0.5)).tolist(),
        text=mg["cr"].apply(lambda v: f"{round(v*100)}%"), textposition="outside",
        textfont=dict(size=13, color="#F1F5F9"),
    ))
    fig_mr.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter", size=11),
        barmode="group", height=320,
        title=dict(text="Mention & Citation Rate", font=dict(size=13, color="#F1F5F9")),
        xaxis=dict(gridcolor="#1e2d44", zerolinecolor="#1e2d44"),
        yaxis=dict(range=[0, 1.2], tickvals=[0, 0.25, 0.5, 0.75, 1.0],
                   ticktext=["0%", "25%", "50%", "75%", "100%"],
                   gridcolor="#1e2d44", zerolinecolor="#1e2d44"),
        legend=dict(orientation="h", y=1.15, font=dict(size=10)),
        margin=dict(t=50, b=40, l=50, r=20))

    # ── Chart 2: Position by prompt ───────────────────────────────────
    prompts = fm["prompt_id"].unique().tolist()
    motors = fm["model_source"].unique().tolist()
    fig_pos = go.Figure()
    for m in motors:
        mf = fm[fm["model_source"] == m]
        vals = []
        texts = []
        for p in prompts:
            row = mf[mf["prompt_id"] == p]
            v = row["avg_rank_alegra"].values[0] if len(row) else None
            vals.append(v)
            texts.append(f"#{v:.1f}" if v is not None else "")
        fig_pos.add_trace(go.Bar(
            name=ML.get(m, m), orientation="h", y=prompts, x=vals,
            marker_color=MC.get(m, "#999"),
            text=texts, textposition="outside", textfont=dict(size=12, color="#F1F5F9"),
        ))
    fig_pos.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter", size=11),
        barmode="group", height=320,
        title=dict(text="Posición Promedio de Alegra", font=dict(size=13, color="#F1F5F9")),
        xaxis=dict(range=[0, 7], dtick=1, tickvals=[1, 2, 3, 4, 5, 6, 7],
                   title=dict(text="Posición (menor = mejor)", font=dict(size=10)),
                   gridcolor="#1e2d44", zerolinecolor="#1e2d44"),
        yaxis=dict(type="category", categoryorder="array", categoryarray=list(reversed(prompts)),
                   title="", gridcolor="#1e2d44", zerolinecolor="#1e2d44"),
        legend=dict(orientation="h", y=1.15, font=dict(size=10)),
        margin=dict(t=50, b=50, l=80, r=60))

    # ── Chart 3: Eco share pie ────────────────────────────────────────
    eco_tot = int(fd[fd["is_ecosystem"]]["cite_count"].sum())
    ext_tot = int(fd[~fd["is_ecosystem"]]["cite_count"].sum())
    fig_eco = go.Figure(go.Pie(
        labels=["Ecosistema", "Externas"], values=[eco_tot, ext_tot],
        marker=dict(colors=["#2DD4BF", "#64748B"]), hole=0.6,
        textinfo="label+percent", textposition="outside",
        textfont=dict(size=12, color="#F1F5F9"),
        outsidetextfont=dict(size=11, color="#94A3B8"),
    ))
    fig_eco.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter", size=11),
        height=320, showlegend=False,
        title=dict(text="Share de Citas", font=dict(size=13, color="#F1F5F9")),
        margin=dict(t=50, b=30, l=30, r=30))

    # ── Chart 4: Brand ranking ────────────────────────────────────────
    max_pos = b_agg["weighted_pos"].max() if len(b_agg) else 1

    # Color: presencia >= 15% → color de marca completo
    #        < 15%  → gris neutro (sin identidad de marca)
    def _bar_color(row):
        if row["coverage_pct"] >= 15:
            return BC.get(row["brand_name"], "#64748B")
        return "rgba(100,116,139,0.28)"

    bar_colors = b_agg.apply(_bar_color, axis=1).tolist()

    fig_brands = go.Figure(go.Bar(
        orientation="h",
        y=b_agg["brand_name"], x=b_agg["weighted_pos"],
        marker_color=bar_colors,
        text=b_agg.apply(
            lambda r: f"#{r['weighted_pos']:.1f} · {r['coverage_pct']:.0f}% presencia", axis=1
        ),
        textposition="outside", textfont=dict(size=11, color="#94A3B8"),
        customdata=b_agg[["coverage_pct", "count", "mentions"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Posición promedio: #%{x:.1f}<br>"
            "Presencia: %{customdata[0]:.0f}% (%{customdata[1]} combos)<br>"
            "Menciones totales: %{customdata[2]}<extra></extra>"
        ),
    ))
    fig_brands.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter", size=11),
        height=max(300, len(b_agg) * 42 + 60),
        title=dict(
            text="Posición Promedio por Marca · % Presencia en prompts<br><sup style='color:#64748B;font-size:10px'>Marcas con baja presencia aparecen atenuadas</sup>",
            font=dict(size=13, color="#F1F5F9")
        ),
        margin=dict(t=65, b=30, l=110, r=80),
        xaxis=dict(range=[0, max_pos + 3], title=dict(text="Posición (menor = mejor)", font=dict(size=10)),
                   gridcolor="#1e2d44", zerolinecolor="#1e2d44"),
        yaxis=dict(autorange="reversed", title="", tickfont=dict(size=12),
                   gridcolor="#1e2d44", zerolinecolor="#1e2d44"))

    # ── Leader list ───────────────────────────────────────────────────
    leader_items = []
    for _, r in fm.iterrows():
        ml = ML.get(r["model_source"], r["model_source"])
        mc = MC.get(r["model_source"], "#999")
        bc = BC.get(r["top_brand"], "#64748B")
        leader_items.append(html.Div(className="leader-row", children=[
            html.Div([
                html.Span(r["prompt_id"], style={"fontSize": "12px", "fontWeight": "600"}),
                html.Span(ml, style={"background": f"{mc}22", "color": mc,
                          "padding": "2px 7px", "borderRadius": "4px",
                          "fontSize": "9px", "fontWeight": "600", "marginLeft": "7px"}),
            ]),
            html.Div([
                html.Span("Líder: ", style={"fontSize": "9px", "color": "var(--muted)"}),
                html.Span(r["top_brand"], style={"background": f"{bc}22", "color": bc,
                          "padding": "2px 7px", "borderRadius": "4px",
                          "fontSize": "10px", "fontWeight": "600"}),
                html.Span(f" #{r['top_brand_rank']:.1f}",
                          style={"fontWeight": "700", "color": bc, "fontSize": "11px"}),
            ]),
        ]))

    # Overall leader — usa el mismo top_b con umbral de elegibilidad
    overall = []
    if top_b is not None:
        ldr = top_b
        lc = BC.get(ldr["brand_name"], "#64748B")
        overall = [html.Div(className="overall-leader", children=[
            html.Div("Marca Líder Ponderada (Todos los filtros)",
                     style={"fontSize": "9px", "fontWeight": "600", "textTransform": "uppercase",
                            "letterSpacing": "0.06em", "color": "var(--muted)", "marginBottom": "5px"}),
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "8px"}, children=[
                html.Span("\U0001f3c6", style={"fontSize": "16px"}),
                html.Span(ldr["brand_name"], style={"fontSize": "16px", "fontWeight": "700", "color": lc}),
                html.Span([
                    "Pos. ponderada ",
                    html.Strong(f"#{ldr['weighted_pos']:.1f}", style={"color": "var(--text)"}),
                ], style={"fontSize": "12px", "color": "var(--muted)"}),
            ]),
            html.Div(f"{int(ldr['count'])}/{n} combinaciones \u00b7 {int(ldr['mentions'])} menciones totales",
                     style={"fontSize": "10px", "color": "var(--dim)", "marginTop": "3px"}),
        ])]

    # ── Brand table data ──────────────────────────────────────────────
    brand_data = []
    for _, r in fb.iterrows():
        brand_data.append({
            "prompt_id": r["prompt_id"],
            "motor": ML.get(r["model_source"], r["model_source"]),
            "brand_name": r["brand_name"],
            "rank_avg": f"#{r['brand_rank_avg']:.1f}",
            "presence": f"{r['brand_presence_pct']}%",
            "brand_mentions_total": r["brand_mentions_total"],
            "brand_ranks_by_rep": r["brand_ranks_by_rep"],
            "is_alegra": r["is_alegra"],
        })

    # ── Prompt table data ─────────────────────────────────────────────
    prompt_data = []
    for _, r in fm.iterrows():
        pt = r["prompt_text"]
        prompt_data.append({
            "prompt_id": r["prompt_id"],
            "prompt_short": pt[:80] + "\u2026" if len(pt) > 80 else pt,
            "funnel_stage": r["funnel_stage"],
            "product_category": r["product_category"],
            "motor": ML.get(r["model_source"], r["model_source"]),
            "mention_rate": f"{r['mention_rate']:.2f}",
            "citation_rate": f"{r['citation_rate']:.2f}",
            "consistency_score": f"{r['consistency_score']:.0f}",
            "avg_rank_alegra": f"#{r['avg_rank_alegra']:.1f}",
            "eco_share_pct": f"{r['eco_share_pct']:.0f}%",
            "total_cites": int(r["total_cites"]),
        })

    # ── Domain charts ─────────────────────────────────────────────────
    eco_doms = fd[fd["is_ecosystem"]].groupby("domain")["cite_count"].sum().sort_values(ascending=False)
    ext_doms = fd[~fd["is_ecosystem"]].groupby("domain")["cite_count"].sum().sort_values(ascending=False).head(10)

    eco_total = int(eco_doms.sum())
    ext_total = int(ext_doms.sum())

    eco_title = f"Ecosistema Alegra ({eco_total} citas)"
    ext_title = f"Fuentes Externas Top 10 ({ext_total} citas)"

    def domain_bar(series, color):
        if series.empty:
            return go.Figure().update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94A3B8", family="Inter", size=11), height=150,
                annotations=[dict(text="Sin citas", showarrow=False, font=dict(color="#FBBF24", size=11))])
        max_v = int(series.max())
        dtk = max(1, math.ceil(max_v / 5))
        fig = go.Figure(go.Bar(
            orientation="h", y=series.index.tolist(), x=series.values.tolist(),
            marker_color=color,
            text=[str(int(v)) for v in series.values],
            textposition="outside", textfont=dict(size=11, color="#F1F5F9"),
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94A3B8", family="Inter", size=11),
            height=max(150, len(series) * 45 + 50),
            margin=dict(t=10, b=30, l=200, r=40),
            xaxis=dict(range=[0, max_v + max(2, math.ceil(max_v * 0.2))],
                       dtick=dtk, rangemode="tozero",
                       title=dict(text="Citas", font=dict(size=10)),
                       gridcolor="#1e2d44", zerolinecolor="#1e2d44"),
            yaxis=dict(autorange="reversed", title="", tickfont=dict(size=11),
                       gridcolor="#1e2d44", zerolinecolor="#1e2d44"))
        return fig

    fig_eco_doms = domain_bar(eco_doms, "#2DD4BF")
    fig_ext_doms = domain_bar(ext_doms, "#64748B")

    # ── Insights ──────────────────────────────────────────────────────
    ac = fm[fm["model_source"] == "chatgpt_search"]
    aa = fm[fm["model_source"] == "google_aio"]
    avg_c = f"{ac['avg_rank_alegra'].mean():.1f}" if len(ac) else "\u2014"
    avg_a = f"{aa['avg_rank_alegra'].mean():.1f}" if len(aa) else "\u2014"

    n_cite = ac[ac["citation_rate"] == 0]["prompt_id"].tolist()
    branded_leaders = fm[fm["product_category"] == "Branded"]["top_brand"].unique().tolist()
    generic_leaders = fm[fm["product_category"] != "Branded"]["top_brand"].unique().tolist()

    insights = [
        html.Div(className="insight-box", children=[
            html.Div("Posición de Alegra", className="insight-title", style={"color": "#FB923C"}),
            html.Div(className="insight-body", children=[
                f"ChatGPT: posición #{avg_c}. " if len(ac) else "",
                f"AI Overview: #{avg_a}. " if len(aa) else "",
                "En Branded la marca alcanza el #1. En genéricos BOFU cae a #4-5 por detrás de CONTPAQi y Aspel.",
            ]),
        ]),
        html.Div(className="insight-box", children=[
            html.Div("Marca líder por segmento", className="insight-title", style={"color": "#F472B6"}),
            html.Div(className="insight-body", children=[
                f"Branded: {', '.join(str(x) for x in branded_leaders if pd.notna(x))} lidera(n). " if branded_leaders else "",
                f"Genérico: {', '.join(str(x) for x in generic_leaders if pd.notna(x))} lidera(n). " if generic_leaders else "",
                "CONTPAQi domina los prompts genéricos BOFU en AI Overview. Alegra necesita estrategia para escalar posición orgánica.",
            ]),
        ]),
        html.Div(className="insight-box", children=[
            html.Div("Oportunidad competitiva", className="insight-title", style={"color": "#2DD4BF"}),
            html.Div(className="insight-body", children=[
                f"ChatGPT no cita a Alegra en: {', '.join(n_cite)}. " if n_cite else "",
                "programascontabilidad.com es la fuente del ecosistema más citada por AI Overview \u2014 pero ChatGPT la ignora. Priorizar contenido linkeable desde fuentes terceras.",
            ]),
        ]),
    ]

    # Build row-key list for drill-down (includes batch_id to avoid cross-batch mixing)
    prompt_keys = [
        {
            "prompt_id": r["prompt_id"],
            "model_source": r["model_source"],
            "batch_id": r.get("batch_id", None),
        }
        for _, r in fm.iterrows()
    ]

    return (header_sub, header_badges, sidebar_info, footer_batch, kpis,
            fig_mr, fig_pos, fig_eco, fig_brands, leader_items, overall,
            brand_data, prompt_data, eco_title, fig_eco_doms, ext_title, fig_ext_doms,
            insights, prompt_keys)


# ── Drill-down callback: OPEN on row click ──────────────────────────
_ML_REV = {v: k for k, v in ML.items()}

@callback(
    Output("drill-panel-content", "children"),
    Output("drill-panel", "style"),
    Input("prompt-table", "active_cell"),
    State("prompt-table-keys", "data"),
    State("f-pais", "value"),
    State("f-funnel", "value"),
    State("f-cat", "value"),
    State("f-motor", "value"),
    State("f-period", "value"),
    State("f-run", "value"),
    prevent_initial_call=True,
)
def drill_open(active_cell, keys_data, pais, funnel, cat, motor, period, run):
    MET, MAR, DOM, RESP = get_data()
    hidden = {"display": "none"}

    if not active_cell:
        return [], hidden

    row_idx = active_cell["row"]

    # Try keys_data first (populated by dcc.Store — includes batch_id)
    if keys_data and row_idx < len(keys_data):
        key = keys_data[row_idx]
        prompt_id = key.get("prompt_id", "")
        model_source = key.get("model_source", "")
        row_batch = key.get("batch_id", None)
    else:
        # Fallback: reconstruct row order from current filters using the effective run
        MET = ensure_batch_time_cols(MET)
        _, resolved_batch, _, _ = resolve_effective_period_and_batch(MET, pais, period, run)
        row_batch = resolved_batch

        fm = MET.copy()
        if pais:
            fm = fm[fm["country_id"] == pais]
        if funnel:
            fm = fm[fm["funnel_stage"] == funnel]
        if cat:
            fm = fm[fm["product_category"] == cat]
        if motor:
            fm = fm[fm["model_source"] == motor]
        if row_batch:
            fm = fm[fm["batch_id"] == row_batch]
        if row_idx >= len(fm):
            return [], hidden
        row = fm.iloc[row_idx]
        prompt_id = row["prompt_id"]
        model_source = row["model_source"]
        row_batch = row.get("batch_id", None)

    effective_batch = row_batch or run

    # Look up full metric row — filter by effective_batch to avoid cross-batch mixing
    met_base = MET[MET["batch_id"] == effective_batch] if effective_batch else MET
    met_row = met_base[(met_base["prompt_id"] == prompt_id) & (met_base["model_source"] == model_source)]
    if met_row.empty:
        return [], hidden
    m = met_row.iloc[0]

    # Brand data for this prompt+motor
    mar_base = MAR[MAR["batch_id"] == effective_batch] if effective_batch else MAR
    brands = mar_base[(mar_base["prompt_id"] == prompt_id) & (mar_base["model_source"] == model_source)].copy()
    brands = brands.sort_values("brand_rank_avg")

    # Domain data for this prompt+motor
    dom_base = DOM[DOM["batch_id"] == effective_batch] if effective_batch else DOM
    doms = dom_base[(dom_base["prompt_id"] == prompt_id) & (dom_base["model_source"] == model_source)].copy()
    eco_doms = doms[doms["is_ecosystem"]].sort_values("cite_count", ascending=False)
    ext_doms = doms[~doms["is_ecosystem"]].sort_values("cite_count", ascending=False)

    motor_display = ML.get(model_source, model_source)
    motor_color = MC.get(model_source, "#60A5FA")

    # ── Header ────────────────────────────────────────────────────────
    top_brand = m["top_brand"] if pd.notna(m.get("top_brand")) else "—"
    top_brand_color = BC.get(top_brand, "#64748B")

    header = html.Div(className="drill-header", children=[
        html.Div(className="drill-header-left", children=[
            html.Div(className="drill-header-top", children=[
                html.Span(prompt_id, style={"fontWeight": "700", "fontSize": "14px"}),
                html.Span(motor_display, style={
                    "background": f"{motor_color}22", "color": motor_color,
                    "padding": "3px 10px", "borderRadius": "6px",
                    "fontSize": "10px", "fontWeight": "600",
                }),
                html.Span([
                    "Marca líder: ",
                    html.Span(top_brand, style={"color": top_brand_color, "fontWeight": "700"}),
                ], style={"fontSize": "11px", "color": "var(--muted)"}),
            ]),
            html.Div(m.get("prompt_text", ""), className="drill-prompt-text"),
            html.Div(
                f"Funnel: {m.get('funnel_stage', '—')} · Cat: {m.get('product_category', '—')} · Producto: {m.get('source_producto_raw', '—')}",
                className="drill-meta",
            ),
        ]),
    ])

    # ── Column 1: Métricas AEO ────────────────────────────────────────
    def metric_row(label, value):
        return html.Div(className="drill-metric-row", children=[
            html.Span(label, className="drill-metric-label"),
            html.Span(value, className="drill-metric-value"),
        ])

    avg_rank = m["avg_rank_alegra"]
    avg_pos_pct = m.get("avg_pos_pct_alegra", 0)
    avg_mentions = m.get("avg_brand_mentions", 0)

    col1 = html.Div(className="drill-col", children=[
        html.Div("Métricas AEO", className="drill-col-title"),
        metric_row("Mention Rate", f"{m['mention_rate']:.0%}"),
        metric_row("Citation Rate", f"{m['citation_rate']:.0%}"),
        metric_row("Consistency Score", "Consistente" if m["mention_rate"] >= 0.67 else "Inconsistente"),
        metric_row("Posición promedio", f"#{avg_rank:.1f}"),
        metric_row("Posición % texto", f"{avg_pos_pct:.1f}%"),
        metric_row("Menciones promedio", f"{avg_mentions}"),
    ])

    # ── Column 2: Ranking de Marcas ───────────────────────────────────
    brand_rows = []
    for i, (_, b) in enumerate(brands.iterrows()):
        trophy = "🏆" if i < 3 else ""
        bname = b["brand_name"]
        bcolor = BC.get(bname, "#64748B")
        rank_val = b["brand_rank_avg"]
        presence = b.get("brand_presence_pct", 0)
        mentions = b.get("brand_mentions_total", 0)

        brand_rows.append(html.Div(className="drill-brand-row", children=[
            html.Span(trophy, className="drill-brand-trophy"),
            html.Span(bname, className="drill-brand-name", style={"color": bcolor}),
            html.Span(f"#{rank_val:.1f}", className="drill-brand-rank"),
            html.Span(f"({mentions} mencs, {presence}%)", className="drill-brand-info"),
        ]))

    col2 = html.Div(className="drill-col", children=[
        html.Div(f"Ranking de Marcas ({len(brands)})", className="drill-col-title"),
        *brand_rows,
    ])

    # ── Column 3: Dominios Citados ────────────────────────────────────
    eco_count = int(eco_doms["cite_count"].sum()) if not eco_doms.empty else 0
    ext_count = int(ext_doms["cite_count"].sum()) if not ext_doms.empty else 0
    total_cites = eco_count + ext_count
    eco_pct = f"{eco_count / total_cites * 100:.0f}%" if total_cites > 0 else "0%"

    eco_chips = []
    for _, d in eco_doms.iterrows():
        eco_chips.append(html.Span(className="domain-chip eco", children=[
            html.Span(d["domain"]),
            html.Span(f"×{int(d['cite_count'])}", className="chip-count"),
        ]))

    ext_chips = []
    for _, d in ext_doms.head(10).iterrows():
        ext_chips.append(html.Span(className="domain-chip ext", children=[
            html.Span(d["domain"]),
            html.Span(f"×{int(d['cite_count'])}", className="chip-count"),
        ]))

    col3 = html.Div(className="drill-col", children=[
        html.Div(f"Dominios Citados ({eco_count + ext_count})", className="drill-col-title"),
        html.Div(className="drill-dom-header", children=[
            html.Div(className="drill-dom-header-item", children=[
                html.Span("Ecosistema", className="drill-dom-header-label"),
                html.Span(f"{eco_count} ({eco_pct})", className="drill-dom-header-value",
                          style={"color": "var(--teal)"}),
            ]),
            html.Div(className="drill-dom-header-item", children=[
                html.Span("Externos", className="drill-dom-header-label"),
                html.Span(str(ext_count), className="drill-dom-header-value",
                          style={"color": "var(--muted)"}),
            ]),
        ]),
        html.Div("ECOSISTEMA", className="drill-dom-section-title"),
        html.Div(className="drill-dom-chips", children=eco_chips) if eco_chips else html.Div(
            "Sin citas ecosistema", style={"fontSize": "10px", "color": "var(--dim)"}),
        html.Div("EXTERNOS TOP", className="drill-dom-section-title"),
        html.Div(className="drill-dom-chips", children=ext_chips) if ext_chips else html.Div(
            "Sin citas externas", style={"fontSize": "10px", "color": "var(--dim)"}),
    ])

    # ── Response section ──────────────────────────────────────────────
    resp_base = RESP[RESP["batch_id"] == effective_batch] if effective_batch else RESP
    resps = resp_base[
        (resp_base["prompt_id"] == prompt_id) &
        (resp_base["model_source"] == model_source)
    ].copy()
    resps = resps.sort_values("replicate_id")

    response_section = []
    if not resps.empty:
        tabs = []
        for _, rr in resps.iterrows():
            rep_id = int(rr["replicate_id"])
            txt = rr["raw_response_text"] or ""
            tabs.append(dcc.Tab(
                label=f"Réplica {rep_id}",
                value=f"rep-{rep_id}",
                style={"backgroundColor": "var(--card)", "color": "var(--muted)",
                       "border": "1px solid var(--border)", "borderRadius": "6px 6px 0 0",
                       "padding": "6px 14px", "fontSize": "10px", "fontWeight": "600",
                       "fontFamily": "Inter, sans-serif"},
                selected_style={"backgroundColor": "var(--teal)", "color": "var(--bg)",
                                "border": "1px solid var(--teal)", "borderRadius": "6px 6px 0 0",
                                "padding": "6px 14px", "fontSize": "10px", "fontWeight": "600",
                                "fontFamily": "Inter, sans-serif"},
                children=[
                    html.Div(className="drill-response-box", children=txt),
                    html.Div(f"{len(txt):,} caracteres", className="drill-response-len"),
                ],
            ))

        response_section = [html.Div(className="drill-response-section", children=[
            html.Div(f"Respuesta Completa del Modelo — {motor_display}", className="drill-response-title"),
            dcc.Tabs(tabs, value="rep-1",
                     style={"height": "auto"},
                     parent_style={"height": "auto"}),
        ])]

    content = html.Div(children=[
        header,
        html.Div(className="drill-grid", children=[col1, col2, col3]),
        *response_section,
    ])

    return content, {"display": "block"}


# ── Drill-down callback: CLOSE on button click ──────────────────────
@callback(
    Output("drill-panel", "style", allow_duplicate=True),
    Input("drill-close-btn", "n_clicks"),
    prevent_initial_call=True,
)
def drill_close(n):
    return {"display": "none"}


# ── Drill-down callback: CLOSE when filters change ───────────────────
# Evita que el panel muestre un detalle viejo bajo un contexto nuevo
@callback(
    Output("drill-panel", "style", allow_duplicate=True),
    Input("f-pais",   "value"),
    Input("f-funnel", "value"),
    Input("f-cat",    "value"),
    Input("f-motor",  "value"),
    Input("f-period", "value"),
    Input("f-run",    "value"),
    prevent_initial_call=True,
)
def drill_close_on_filter_change(*_):
    return {"display": "none"}


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 8050)))




