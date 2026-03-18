#!/usr/bin/env python3
"""
run_batch.py — Golden Stack Orchestrator
Lee prompts desde Google Sheets, ejecuta ChatGPT y Google AI Overview,
guarda CSV de respaldo y sube métricas a Supabase.

Uso:
    python run_batch.py                          # todos los prompts activos
    python run_batch.py --country MX             # solo un país
    python run_batch.py --priority P1            # solo prioridad P1
    python run_batch.py --dry-run                # muestra prompts sin ejecutar APIs
    python run_batch.py --country MX --priority P1 --dry-run

Variables de entorno requeridas:
    OPENAI_API_KEY              — API key de OpenAI
    DATAFORSEO_LOGIN            — Login DataForSEO (ej: growth@alegra.com)
    DATAFORSEO_PASSWORD         — Password DataForSEO
    DATABASE_URL                — Connection string Supabase (puerto 6543)
    GOOGLE_SERVICE_ACCOUNT_JSON — Ruta al JSON de la cuenta de servicio de Google
                                  (opcional: si no se define, se omite la actualización del Sheet)
"""

import os, sys, csv, json, time, argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

# ── Configuración ─────────────────────────────────────────────────────────────

SHEET_ID   = "1nkxU-gHNJbY7SKbBrv4huxePlAT4CZ5KJX4Z3F7pUSE"
SHEET_URL  = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"

OPENAI_MODEL      = "gpt-4o-search-preview"
DATAFORSEO_BASE   = "https://api.dataforseo.com"
DATAFORSEO_ENDPOINT = "/v3/serp/google/ai_mode/live/advanced"

# Delay entre llamadas API (segundos) para evitar rate limits
DELAY_OPENAI      = 3
DELAY_DATAFORSEO  = 2

# Columnas del CSV de output (16 columnas estándar Golden Stack)
OUTPUT_COLS = [
    "batch_id", "run_ts", "run_id", "replicate_id",
    "prompt_id", "country_id", "location_code", "product_category",
    "funnel_stage", "source_producto_raw", "prompt_text",
    "model_source", "status", "raw_response_text",
    "raw_citations_json", "outputFileId"
]


# ── Lectura del Golden Stack desde Google Sheets ──────────────────────────────

def load_golden_stack(country=None, priority=None) -> pd.DataFrame:
    """Lee el catálogo de prompts desde Google Sheets y aplica filtros."""
    print(f"Cargando Golden Stack desde Google Sheets...")
    try:
        df = pd.read_csv(SHEET_URL, dtype=str)
        df.columns = [c.strip() for c in df.columns]
    except Exception as e:
        print(f"ERROR cargando el Sheet: {e}")
        sys.exit(1)

    total = len(df)

    # Filtrar activos
    if 'is_active' in df.columns:
        df = df[df['is_active'].str.upper().isin(['TRUE', '1', 'YES', 'SI', 'SÍ'])]

    # Filtros opcionales
    if country:
        df = df[df['country_iso'].str.upper() == country.upper()]
    if priority:
        df = df[df['priority'].str.upper() == priority.upper()]

    print(f"  {total} prompts en el catálogo → {len(df)} activos con los filtros aplicados")
    return df.reset_index(drop=True)


# ── API OpenAI (ChatGPT con web search) ──────────────────────────────────────

def call_openai(prompt_text: str, api_key: str) -> dict:
    """
    Llama a gpt-4o-search-preview con web_search_options.
    Retorna {'status': 'success'|'error', 'text': str, 'citations': list}
    Nota: gpt-4o-search-preview NO soporta el parámetro temperature.
    """
    import openai
    client = openai.OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            web_search_options={},
            messages=[{"role": "user", "content": prompt_text}]
        )

        message = response.choices[0].message
        text    = message.content or ""

        # Extraer citaciones de las anotaciones
        citations = []
        if hasattr(message, 'annotations') and message.annotations:
            for ann in message.annotations:
                if ann.type == "url_citation":
                    uc = ann.url_citation
                    citations.append({
                        "title": getattr(uc, 'title', ''),
                        "url":   getattr(uc, 'url', ''),
                    })

        return {"status": "success", "text": text, "citations": citations}

    except Exception as e:
        return {"status": "error", "text": str(e), "citations": []}


# ── API DataForSEO (Google AI Overview) ──────────────────────────────────────

def call_dataforseo(prompt_text: str, location_code: str,
                    language_code: str, device: str,
                    login: str, password: str) -> dict:
    """
    Llama a DataForSEO /v3/serp/google/ai_mode/live/advanced.
    Retorna {'status': 'success'|'error', 'text': str, 'citations': list}
    """
    url  = DATAFORSEO_BASE + DATAFORSEO_ENDPOINT
    payload = [{
        "keyword":       prompt_text,
        "location_code": int(location_code),
        "language_code": language_code or "es",
        "device":        device or "desktop",
        "os":            "windows",
    }]

    try:
        resp = requests.post(
            url,
            auth=HTTPBasicAuth(login, password),
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()

        # Navegar la estructura de respuesta de DataForSEO
        tasks = data.get("tasks", [])
        if not tasks or tasks[0].get("status_code") != 20000:
            msg = tasks[0].get("status_message", "unknown") if tasks else "no tasks"
            return {"status": "error", "text": f"DataForSEO error: {msg}", "citations": []}

        results = tasks[0].get("result", [])
        if not results:
            return {"status": "error", "text": "no results", "citations": []}

        items = results[0].get("items", [])
        ai_text    = ""
        citations  = []

        for item in items:
            if item.get("type") == "ai_overview":
                # Texto del AI Overview
                ai_text = item.get("text", "") or item.get("description", "") or ""

                # Citaciones / referencias
                refs = item.get("references", []) or item.get("items", [])
                for ref in refs:
                    domain = ""
                    source_url = ref.get("source", ref.get("url", ""))
                    if source_url:
                        try:
                            from urllib.parse import urlparse
                            domain = urlparse(source_url).netloc.lower()
                            if domain.startswith("www."):
                                domain = domain[4:]
                        except Exception:
                            pass
                    citations.append({
                        "title":  ref.get("title", ""),
                        "url":    source_url,
                        "domain": domain,
                    })
                break  # solo el primer ai_overview

        if not ai_text:
            return {"status": "no_aio", "text": "", "citations": []}

        return {"status": "success", "text": ai_text, "citations": citations}

    except Exception as e:
        return {"status": "error", "text": str(e), "citations": []}


# ── Ejecución de batch ────────────────────────────────────────────────────────

def run_batch(df: pd.DataFrame, dry_run: bool = False) -> tuple[str, list]:
    """
    Ejecuta el batch completo.
    Retorna (batch_id, lista de filas de output)
    """
    # Credenciales
    openai_key   = os.environ.get("OPENAI_API_KEY")
    dfs_login    = os.environ.get("DATAFORSEO_LOGIN")
    dfs_password = os.environ.get("DATAFORSEO_PASSWORD")

    if not dry_run:
        missing = []
        if not openai_key:   missing.append("OPENAI_API_KEY")
        if not dfs_login:    missing.append("DATAFORSEO_LOGIN")
        if not dfs_password: missing.append("DATAFORSEO_PASSWORD")
        if missing:
            print(f"ERROR: Faltan variables de entorno: {', '.join(missing)}")
            sys.exit(1)

    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows     = []

    total_prompts = len(df)
    total_calls   = sum(
        (int(row.get('run_chatgpt', '0').upper() in ['TRUE','1','YES']) +
         int(row.get('run_ai_overview', '0').upper() in ['TRUE','1','YES'])) *
        int(row.get('n_replicates', '3'))
        for _, row in df.iterrows()
    )

    print(f"\nbatch_id: {batch_id}")
    print(f"Prompts a ejecutar: {total_prompts}")
    print(f"Llamadas API estimadas: {total_calls}")

    if dry_run:
        print("\n[DRY RUN] Prompts que se ejecutarían:\n")
        for _, row in df.iterrows():
            motors = []
            if row.get('run_chatgpt', '').upper() in ['TRUE', '1', 'YES']:
                motors.append('chatgpt_search')
            if row.get('run_ai_overview', '').upper() in ['TRUE', '1', 'YES']:
                motors.append('google_aio')
            print(f"  {row['prompt_id']} [{row.get('country_iso','')}] {row.get('funnel_stage','')} "
                  f"× {row.get('n_replicates','3')} réplicas × {motors}")
        return batch_id, []

    call_count = 0

    for idx, row in df.iterrows():
        prompt_id        = row['prompt_id']
        country_id       = row.get('country_iso', row.get('country_id', ''))
        location_code    = row.get('location_code', '2484')
        language_code    = row.get('language_code', 'es')
        device           = row.get('device', 'desktop')
        funnel_stage     = row.get('funnel_stage', '')
        product_category = row.get('product_category', '')
        source_raw       = row.get('source_producto_raw', '')
        prompt_text      = row.get('prompt_text', '')
        n_rep            = int(row.get('n_replicates', '3'))

        run_chatgpt     = row.get('run_chatgpt', 'TRUE').upper() in ['TRUE', '1', 'YES']
        run_ai_overview = row.get('run_ai_overview', 'TRUE').upper() in ['TRUE', '1', 'YES']

        print(f"\n[{idx+1}/{total_prompts}] {prompt_id} — {prompt_text[:70]}...")

        # ── ChatGPT ──────────────────────────────────────────────────────────
        if run_chatgpt:
            for rep in range(1, n_rep + 1):
                run_id  = f"{prompt_id}-chatgpt_search-{batch_id}-r{rep:02d}"
                run_ts  = datetime.now(timezone.utc).isoformat()
                call_count += 1
                print(f"  → ChatGPT réplica {rep}/{n_rep}  (llamada #{call_count})")

                result = call_openai(prompt_text, openai_key)

                rows.append({
                    "batch_id":            batch_id,
                    "run_ts":              run_ts,
                    "run_id":              run_id,
                    "replicate_id":        rep,
                    "prompt_id":           prompt_id,
                    "country_id":          country_id,
                    "location_code":       location_code,
                    "product_category":    product_category,
                    "funnel_stage":        funnel_stage,
                    "source_producto_raw": source_raw,
                    "prompt_text":         prompt_text,
                    "model_source":        "chatgpt_search",
                    "status":              result["status"],
                    "raw_response_text":   result["text"],
                    "raw_citations_json":  json.dumps(result["citations"], ensure_ascii=False),
                    "outputFileId":        "",
                })

                if result["status"] == "error":
                    print(f"     ERROR: {result['text'][:100]}")
                else:
                    print(f"     OK — {len(result['text'])} chars, {len(result['citations'])} citas")

                if rep < n_rep:
                    time.sleep(DELAY_OPENAI)

        # ── Google AI Overview ────────────────────────────────────────────────
        if run_ai_overview:
            for rep in range(1, n_rep + 1):
                run_id  = f"{prompt_id}-google_aio-{batch_id}-r{rep:02d}"
                run_ts  = datetime.now(timezone.utc).isoformat()
                call_count += 1
                print(f"  → Google AIO réplica {rep}/{n_rep}  (llamada #{call_count})")

                result = call_dataforseo(
                    prompt_text, location_code, language_code, device,
                    dfs_login, dfs_password
                )

                rows.append({
                    "batch_id":            batch_id,
                    "run_ts":              run_ts,
                    "run_id":              run_id,
                    "replicate_id":        rep,
                    "prompt_id":           prompt_id,
                    "country_id":          country_id,
                    "location_code":       location_code,
                    "product_category":    product_category,
                    "funnel_stage":        funnel_stage,
                    "source_producto_raw": source_raw,
                    "prompt_text":         prompt_text,
                    "model_source":        "google_aio",
                    "status":              result["status"],
                    "raw_response_text":   result["text"],
                    "raw_citations_json":  json.dumps(result["citations"], ensure_ascii=False),
                    "outputFileId":        "",
                })

                if result["status"] == "error":
                    print(f"     ERROR: {result['text'][:100]}")
                elif result["status"] == "no_aio":
                    print(f"     Sin AI Overview para este prompt/país")
                else:
                    print(f"     OK — {len(result['text'])} chars, {len(result['citations'])} citas")

                if rep < n_rep:
                    time.sleep(DELAY_DATAFORSEO)

    return batch_id, rows


# ── Detectar y deshabilitar AIO en Sheet ─────────────────────────────────────

def find_no_aio_prompts(rows: list) -> list:
    """
    Retorna lista de prompt_ids donde TODAS las réplicas de google_aio
    devolvieron status 'no_aio'.
    """
    from collections import defaultdict
    aio_rows = [r for r in rows if r["model_source"] == "google_aio"]
    by_prompt = defaultdict(list)
    for r in aio_rows:
        by_prompt[r["prompt_id"]].append(r["status"])

    to_disable = []
    for prompt_id, statuses in by_prompt.items():
        if statuses and all(s == "no_aio" for s in statuses):
            to_disable.append(prompt_id)
    return to_disable


def disable_aio_in_sheet(prompt_ids: list):
    """
    Actualiza run_ai_overview = FALSE en el Google Sheet para los prompt_ids dados.
    Requiere la variable de entorno GOOGLE_SERVICE_ACCOUNT_JSON con la ruta al JSON.
    """
    if not prompt_ids:
        return

    sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_path:
        print("\nAVISO: GOOGLE_SERVICE_ACCOUNT_JSON no definida.")
        print(f"  Marca manualmente run_ai_overview=FALSE para: {prompt_ids}")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds  = Credentials.from_service_account_file(sa_path, scopes=scopes)
        gc     = gspread.authorize(creds)
        ws     = gc.open_by_key(SHEET_ID).sheet1

        # Leer encabezados para encontrar las columnas correctas
        headers = ws.row_values(1)
        try:
            col_prompt_id = headers.index("prompt_id") + 1
            col_run_aio   = headers.index("run_ai_overview") + 1
        except ValueError as e:
            print(f"  ERROR: columna no encontrada en el Sheet: {e}")
            return

        # Leer todos los prompt_ids del sheet
        all_prompt_ids = ws.col_values(col_prompt_id)

        updated = []
        for prompt_id in prompt_ids:
            try:
                row_num = all_prompt_ids.index(prompt_id) + 1  # 1-indexed
                ws.update_cell(row_num, col_run_aio, "FALSE")
                updated.append(prompt_id)
            except ValueError:
                print(f"  AVISO: prompt_id '{prompt_id}' no encontrado en el Sheet")

        if updated:
            print(f"\n  Sheet actualizado — run_ai_overview=FALSE para: {updated}")

    except ImportError:
        print("\nAVISO: gspread no instalado. Ejecuta: pip install gspread google-auth")
        print(f"  Marca manualmente run_ai_overview=FALSE para: {prompt_ids}")
    except Exception as e:
        print(f"\nERROR actualizando el Sheet: {e}")
        print(f"  Marca manualmente run_ai_overview=FALSE para: {prompt_ids}")


# ── Guardar CSV de respaldo ───────────────────────────────────────────────────

def save_csv(batch_id: str, rows: list) -> str:
    """Guarda el output crudo como CSV de respaldo."""
    filename = f"golden-stack-output-{batch_id}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLS, delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV guardado: {filename}")
    return filename


# ── Procesar y subir a Supabase ───────────────────────────────────────────────

def upload_to_supabase(csv_path: str):
    """Reutiliza la lógica de update_db.py para subir a Supabase."""
    script_dir = Path(__file__).parent
    update_db_path = script_dir / "update_db.py"

    if not update_db_path.exists():
        print("ERROR: update_db.py no encontrado. Sube el CSV manualmente con:")
        print(f"  python update_db.py {csv_path}")
        return

    import importlib.util
    spec = importlib.util.spec_from_file_location("update_db", update_db_path)
    update_db = importlib.util.load_from_spec(spec)
    spec.loader.exec_module(update_db)
    update_db.main([csv_path])


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Golden Stack Orchestrator")
    parser.add_argument("--country",  help="Filtrar por país (ej: MX, CO, DO, CR)")
    parser.add_argument("--priority", help="Filtrar por prioridad (ej: P1, P2, P3)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Muestra los prompts sin ejecutar las APIs")
    parser.add_argument("--no-upload", action="store_true",
                        help="Guarda CSV pero no sube a Supabase")
    args = parser.parse_args()

    # 1. Cargar prompts
    df = load_golden_stack(country=args.country, priority=args.priority)

    if len(df) == 0:
        print("No hay prompts que procesar con los filtros indicados.")
        sys.exit(0)

    # 2. Ejecutar batch
    batch_id, rows = run_batch(df, dry_run=args.dry_run)

    if args.dry_run or not rows:
        return

    # 3. Guardar CSV de respaldo
    csv_path = save_csv(batch_id, rows)

    # 4. Subir a Supabase
    if not args.no_upload:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            print("\nAVISO: DATABASE_URL no definida. Sube el CSV manualmente:")
            print(f"  python update_db.py {csv_path}")
        else:
            print("\nSubiendo a Supabase...")
            upload_to_supabase(csv_path)
    else:
        print(f"\nCSV listo. Para subir a Supabase:")
        print(f"  python update_db.py {csv_path}")

    # 5. Deshabilitar AIO en Sheet para prompts que nunca generaron AI Overview
    no_aio_prompts = find_no_aio_prompts(rows)
    if no_aio_prompts:
        print(f"\nPrompts con 0/3 réplicas AIO: {no_aio_prompts}")
        print("Actualizando run_ai_overview=FALSE en el Sheet...")
        disable_aio_in_sheet(no_aio_prompts)
    else:
        print("\nTodos los prompts generaron al menos 1 AI Overview. No hay cambios en el Sheet.")

    print(f"\n✓ Batch {batch_id} completado. {len(rows)} filas procesadas.")


if __name__ == "__main__":
    main()
