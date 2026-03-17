#!/usr/bin/env python3
"""
update_db.py — Golden Stack CSV → Supabase
Procesa el output crudo (16 columnas TSV) e inserta en:
  metricas, marcas, dominios, respuestas

Uso:
    python update_db.py archivo1.csv [archivo2.csv ...]
    python update_db.py --folder /ruta/a/carpeta/

Requiere: DATABASE_URL como variable de entorno (connection string de Supabase, puerto 6543)
"""

import os, sys, re, json, glob
import pandas as pd
from datetime import datetime, date
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import execute_values


# ── Dominios del ecosistema Alegra ───────────────────────────────────────────
ECOSYSTEM_DOMAINS = {
    'alegra.com':                'Alegra',
    'blog.alegra.com':           'Alegra',
    'ayuda.alegra.com':          'Alegra',
    'novedades.alegra.com':      'Alegra',
    'siemprealdia.co':           'Alegra',
    'programascontabilidad.com': 'Alegra',
}

# ── Marcas a rastrear (regex case-insensitive) ────────────────────────────────
BRAND_PATTERNS = {
    'Alegra':     r'\balegra\b',
    'CONTPAQi':   r'\bcontpaqi\b',
    'Aspel':      r'\baspel\b',
    'Microsip':   r'\bmicrosip\b',
    'Bind ERP':   r'\bbind[\s\-]?erp\b',
    'QuickBooks': r'\bquickbooks\b',
    'Miskuentas': r'\bmiskuentas\b',
    'Xero':       r'\bxero\b',
    'Holded':     r'\bholded\b',
    'Contalink':  r'\bcontalink\b',
    'Siigo':      r'\bsiigo\b',
}

ALEGRA_BRAND = 'Alegra'


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_domain(url: str) -> str:
    """Extrae el dominio base de una URL."""
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc.split('?')[0].split('#')[0]
    except Exception:
        return ''


def is_ecosystem(domain: str) -> tuple:
    """Retorna (True, brand) si el dominio pertenece al ecosistema Alegra."""
    domain = domain.lower()
    if domain in ECOSYSTEM_DOMAINS:
        return True, ECOSYSTEM_DOMAINS[domain]
    # Subdominios de alegra.com
    if domain.endswith('.alegra.com') or domain == 'alegra.com':
        return True, 'Alegra'
    return False, ''


def parse_citations(raw: str) -> list:
    """
    Parsea raw_citations_json.
    El TSV tiene comillas dobles escapadas (estándar CSV): "" → "
    """
    if not raw or (isinstance(raw, float)):
        return []
    # pandas puede dejar el valor como string con "" interiores
    try:
        return json.loads(raw)
    except Exception:
        try:
            cleaned = raw.replace('""', '"')
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1]
            return json.loads(cleaned)
        except Exception:
            return []


def parse_batch_date(batch_id: str) -> date:
    try:
        return datetime.strptime(batch_id[:8], '%Y%m%d').date()
    except Exception:
        return date.today()


def batch_month(batch_id: str) -> str:
    d = parse_batch_date(batch_id)
    return d.strftime('%Y-%m')


def batch_quarter(batch_id: str) -> str:
    d = parse_batch_date(batch_id)
    q = (d.month - 1) // 3 + 1
    return f'{d.year}-Q{q}'


def detect_brands(text: str) -> dict:
    """
    Detecta marcas en el texto de respuesta.
    Retorna {brand: posicion_primera_aparicion} para calcular rankings.
    """
    if not text:
        return {}
    text_l = text.lower()
    found = {}
    for brand, pattern in BRAND_PATTERNS.items():
        m = re.search(pattern, text_l)
        if m:
            found[brand] = m.start()
    return found


# ── Procesamiento de grupo (batch × prompt × motor) ──────────────────────────

def process_group(group_df: pd.DataFrame) -> dict:
    rows = group_df.to_dict('records')
    r0 = rows[0]

    batch_id        = r0['batch_id']
    prompt_id       = r0['prompt_id']
    model_source    = r0['model_source']
    country_id      = r0['country_id']
    product_category = r0['product_category']
    funnel_stage    = r0['funnel_stage']
    source_raw      = r0.get('source_producto_raw', '') or ''
    prompt_text     = r0['prompt_text']

    bdate   = parse_batch_date(batch_id)
    bmonth  = batch_month(batch_id)
    bqtr    = batch_quarter(batch_id)

    successful = [r for r in rows if r.get('status') == 'success']
    num_replicates = len(rows)
    num_success    = len(successful)

    # ── RESPUESTAS ────────────────────────────────────────────────────────────
    respuestas_list = []
    for r in rows:
        respuestas_list.append({
            'batch_id':           batch_id,
            'prompt_id':          prompt_id,
            'model_source':       model_source,
            'replicate_id':       int(r['replicate_id']),
            'raw_response_text':  r.get('raw_response_text', '') or '',
            'raw_citations_json': r.get('raw_citations_json', '') or '',
        })

    # ── DETECCIÓN DE MARCAS POR RÉPLICA ───────────────────────────────────────
    # rank_maps[i] = {brand: rank} para la réplica i (rank basado en orden de aparición)
    rank_maps = []
    for r in successful:
        found = detect_brands(r.get('raw_response_text', '') or '')
        sorted_brands = sorted(found.items(), key=lambda x: x[1])
        rank_map = {brand: idx + 1 for idx, (brand, _) in enumerate(sorted_brands)}
        rank_maps.append(rank_map)

    all_brands = set(b for rm in rank_maps for b in rm)

    # ── MÉTRICAS DE ALEGRA ────────────────────────────────────────────────────
    alegra_mentions = 0
    alegra_ranks    = []

    for i, r in enumerate(successful):
        text = r.get('raw_response_text', '') or ''
        if re.search(r'\balegra\b', text, re.IGNORECASE):
            alegra_mentions += 1
        if i < len(rank_maps) and ALEGRA_BRAND in rank_maps[i]:
            alegra_ranks.append(rank_maps[i][ALEGRA_BRAND])

    mention_rate      = round(alegra_mentions / num_success, 4) if num_success else 0.0
    consistency_score = round(alegra_mentions / num_success * 100, 2) if num_success else 0.0
    avg_rank_alegra   = round(sum(alegra_ranks) / len(alegra_ranks), 2) if alegra_ranks else None
    avg_pos_pct_alegra = (
        round(avg_rank_alegra / len(all_brands), 4)
        if avg_rank_alegra and all_brands else None
    )

    # ── MARCAS (agregadas) ────────────────────────────────────────────────────
    marcas_list = []
    top_brand_name = None
    top_brand_rank = float('inf')

    for brand in all_brands:
        ranks = [rm[brand] for rm in rank_maps if brand in rm]
        rank_avg = round(sum(ranks) / len(ranks), 2) if ranks else None
        presence_pct = round(len(ranks) / num_success * 100, 2) if num_success else 0.0

        marcas_list.append({
            'batch_id':            batch_id,
            'batch_date':          bdate,
            'prompt_id':           prompt_id,
            'country_id':          country_id,
            'model_source':        model_source,
            'funnel_stage':        funnel_stage,
            'product_category':    product_category,
            'brand_name':          brand,
            'brand_rank_avg':      rank_avg,
            'brand_presence_pct':  presence_pct,
            'brand_mentions_total': len(ranks),
            'brand_ranks_by_rep':  json.dumps(ranks),
            'is_top_brand':        False,   # se actualiza después
            'is_alegra':           (brand == ALEGRA_BRAND),
        })

        if rank_avg and rank_avg < top_brand_rank:
            top_brand_rank = rank_avg
            top_brand_name = brand

    # Marcar top brand
    for m in marcas_list:
        m['is_top_brand'] = (m['brand_name'] == top_brand_name)

    # ── DOMINIOS Y CITACIONES ─────────────────────────────────────────────────
    domain_counts = {}   # domain → total_cites (sumado a través de réplicas)

    for r in successful:
        citations = parse_citations(r.get('raw_citations_json', ''))
        for cit in citations:
            # google_aio tiene campo 'domain'; chatgpt_search solo tiene 'url'
            domain = (cit.get('domain', '') or '').lower().strip()
            if not domain:
                domain = extract_domain(cit.get('url', '') or '')
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

    total_cites = sum(domain_counts.values())

    # citation_rate: % de réplicas donde al menos un dominio ecosistema es citado
    eco_cites_total = 0
    ext_cites_total = 0
    citation_rate_replicas = 0

    for r in successful:
        citations = parse_citations(r.get('raw_citations_json', ''))
        replica_has_eco = False
        for cit in citations:
            domain = (cit.get('domain', '') or '').lower().strip()
            if not domain:
                domain = extract_domain(cit.get('url', '') or '')
            eco, _ = is_ecosystem(domain)
            if eco:
                replica_has_eco = True
        if replica_has_eco:
            citation_rate_replicas += 1

    citation_rate = round(citation_rate_replicas / num_success, 4) if num_success else 0.0

    dominios_list = []
    for domain, cnt in domain_counts.items():
        eco, eco_brand = is_ecosystem(domain)
        if eco:
            eco_cites_total += cnt
        else:
            ext_cites_total += cnt

        dominios_list.append({
            'batch_id':       batch_id,
            'batch_date':     bdate,
            'prompt_id':      prompt_id,
            'country_id':     country_id,
            'model_source':   model_source,
            'domain':         domain,
            'cite_count':     cnt,
            'is_ecosystem':   eco,
            'ecosystem_brand': eco_brand if eco else None,
        })

    eco_share_pct = round(eco_cites_total / total_cites * 100, 2) if total_cites else 0.0

    avg_brand_mentions = (
        round(sum(len(rm) for rm in rank_maps) / len(rank_maps), 2)
        if rank_maps else 0.0
    )
    avg_response_length = (
        round(sum(len(r.get('raw_response_text', '') or '') for r in successful) / num_success, 2)
        if num_success else 0.0
    )

    # ── MÉTRICAS (fila agregada) ───────────────────────────────────────────────
    metrica = {
        'batch_id':            batch_id,
        'batch_date':          bdate,
        'batch_month':         bmonth,
        'batch_quarter':       bqtr,
        'prompt_id':           prompt_id,
        'country_id':          country_id,
        'product_category':    product_category,
        'funnel_stage':        funnel_stage,
        'source_producto_raw': source_raw,
        'prompt_text':         prompt_text,
        'model_source':        model_source,
        'num_replicates':      num_replicates,
        'num_success':         num_success,
        'mention_rate':        mention_rate,
        'citation_rate':       citation_rate,
        'consistency_score':   consistency_score,
        'avg_brand_mentions':  avg_brand_mentions,
        'avg_response_length': avg_response_length,
        'avg_rank_alegra':     avg_rank_alegra,
        'avg_pos_pct_alegra':  avg_pos_pct_alegra,
        'ranks_alegra':        json.dumps(alegra_ranks),
        'eco_cites':           eco_cites_total,
        'ext_cites':           ext_cites_total,
        'total_cites':         total_cites,
        'eco_share_pct':       eco_share_pct,
        'top_brand':           top_brand_name,
        'top_brand_rank':      round(top_brand_rank, 2) if top_brand_rank != float('inf') else None,
    }

    return {
        'metrica':    metrica,
        'marcas':     marcas_list,
        'dominios':   dominios_list,
        'respuestas': respuestas_list,
    }


# ── Inserción a Supabase ──────────────────────────────────────────────────────

def upsert_table(cur, table: str, rows: list, conflict_cols: list):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    vals = [[r[c] for c in cols] for r in rows]
    conflict = ', '.join(conflict_cols)
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s "
        f"ON CONFLICT ({conflict}) DO NOTHING"
    )
    execute_values(cur, sql, vals)
    return len(vals)


def insert_to_supabase(conn, results: list):
    cur = conn.cursor()

    all_metricas  = [r['metrica']    for r in results]
    all_marcas    = [m for r in results for m in r['marcas']]
    all_dominios  = [d for r in results for d in r['dominios']]
    all_respuestas = [resp for r in results for resp in r['respuestas']]

    n_met  = upsert_table(cur, 'metricas',  all_metricas,  ['batch_id', 'prompt_id', 'model_source'])
    n_mar  = upsert_table(cur, 'marcas',    all_marcas,    ['batch_id', 'prompt_id', 'model_source', 'brand_name'])
    n_dom  = upsert_table(cur, 'dominios',  all_dominios,  ['batch_id', 'prompt_id', 'model_source', 'domain'])
    n_resp = upsert_table(cur, 'respuestas', all_respuestas, ['batch_id', 'prompt_id', 'model_source', 'replicate_id'])

    conn.commit()
    cur.close()

    print(f"  metricas:   {n_met} filas")
    print(f"  marcas:     {n_mar} filas")
    print(f"  dominios:   {n_dom} filas")
    print(f"  respuestas: {n_resp} filas")


# ── Main ──────────────────────────────────────────────────────────────────────

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep='\t', dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    return df


def main(csv_paths: list):
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERROR: Define DATABASE_URL con el connection string de Supabase (puerto 6543).")
        sys.exit(1)

    print(f"Procesando {len(csv_paths)} archivo(s)...\n")

    all_results = []

    for path in csv_paths:
        print(f"Leyendo: {path}")
        try:
            df = load_csv(path)
        except Exception as e:
            print(f"  ERROR al leer: {e}")
            continue

        print(f"  {len(df)} filas encontradas")
        groups = df.groupby(['batch_id', 'prompt_id', 'model_source'], sort=False)

        for (batch_id, prompt_id, model_source), group_df in groups:
            print(f"  → {batch_id} / {prompt_id} / {model_source}  ({len(group_df)} réplicas)")
            try:
                result = process_group(group_df)
                all_results.append(result)
                m = result['metrica']
                print(f"     mention_rate={m['mention_rate']}  "
                      f"citation_rate={m['citation_rate']}  "
                      f"consistency={m['consistency_score']}  "
                      f"top_brand={m['top_brand']}")
            except Exception as e:
                print(f"     ERROR procesando grupo: {e}")
                import traceback; traceback.print_exc()

    if not all_results:
        print("\nNo se procesaron grupos. Revisa los archivos CSV.")
        sys.exit(1)

    print(f"\nConectando a Supabase...")
    try:
        conn = psycopg2.connect(db_url)
    except Exception as e:
        print(f"ERROR de conexión: {e}")
        sys.exit(1)

    print(f"Insertando {len(all_results)} grupos en Supabase...")
    insert_to_supabase(conn, all_results)
    conn.close()

    print("\n✓ Completado. Recarga el dashboard para ver los datos reales.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    paths = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--folder':
            i += 1
            paths.extend(sorted(glob.glob(os.path.join(sys.argv[i], '*.csv'))))
        else:
            paths.append(arg)
        i += 1

    if not paths:
        print("No se encontraron archivos CSV.")
        sys.exit(1)

    main(paths)
