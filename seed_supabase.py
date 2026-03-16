"""
Seed Supabase with existing SQLite data.
Run once after creating the schema in Supabase SQL Editor.

Usage:
  export DATABASE_URL="postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
  python seed_supabase.py
"""
import os, sys, sqlite3, json
import psycopg2
from psycopg2.extras import execute_values

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("ERROR: Set DATABASE_URL environment variable first.")
    print('  export DATABASE_URL="postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres"')
    sys.exit(1)

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "aeo_data.db")

def migrate():
    # Connect to SQLite
    lite = sqlite3.connect(SQLITE_PATH)
    lite.row_factory = sqlite3.Row

    # Connect to Supabase (PostgreSQL)
    pg = psycopg2.connect(DB_URL)
    cur = pg.cursor()

    # ── Migrate metricas ──
    rows = [dict(r) for r in lite.execute("SELECT * FROM metricas").fetchall()]
    if rows:
        cols = [c for c in rows[0].keys()]
        sql = f"""INSERT INTO metricas ({','.join(cols)})
                  VALUES %s
                  ON CONFLICT (batch_id, prompt_id, model_source) DO NOTHING"""
        template = "(" + ",".join([f"%({c})s" for c in cols]) + ")"
        execute_values(cur, sql, rows, template=template, page_size=100)
        print(f"  metricas: {len(rows)} rows migrated")

    # ── Migrate marcas ──
    rows = [dict(r) for r in lite.execute("SELECT * FROM marcas").fetchall()]
    for r in rows:
        r['is_top_brand'] = bool(r.get('is_top_brand', 0))
        r['is_alegra'] = bool(r.get('is_alegra', 0))
    if rows:
        cols = [c for c in rows[0].keys()]
        sql = f"""INSERT INTO marcas ({','.join(cols)})
                  VALUES %s
                  ON CONFLICT (batch_id, prompt_id, model_source, brand_name) DO NOTHING"""
        template = "(" + ",".join([f"%({c})s" for c in cols]) + ")"
        execute_values(cur, sql, rows, template=template, page_size=100)
        print(f"  marcas: {len(rows)} rows migrated")

    # ── Migrate dominios ──
    rows = [dict(r) for r in lite.execute("SELECT * FROM dominios").fetchall()]
    for r in rows:
        r['is_ecosystem'] = bool(r.get('is_ecosystem', 0))
    if rows:
        cols = [c for c in rows[0].keys()]
        sql = f"""INSERT INTO dominios ({','.join(cols)})
                  VALUES %s
                  ON CONFLICT (batch_id, prompt_id, model_source, domain) DO NOTHING"""
        template = "(" + ",".join([f"%({c})s" for c in cols]) + ")"
        execute_values(cur, sql, rows, template=template, page_size=100)
        print(f"  dominios: {len(rows)} rows migrated")

    # ── Migrate respuestas ──
    rows = [dict(r) for r in lite.execute("SELECT * FROM respuestas").fetchall()]
    if rows:
        cols = [c for c in rows[0].keys()]
        sql = f"""INSERT INTO respuestas ({','.join(cols)})
                  VALUES %s
                  ON CONFLICT (batch_id, prompt_id, model_source, replicate_id) DO NOTHING"""
        template = "(" + ",".join([f"%({c})s" for c in cols]) + ")"
        execute_values(cur, sql, rows, template=template, page_size=100)
        print(f"  respuestas: {len(rows)} rows migrated")

    pg.commit()
    cur.close()
    pg.close()
    lite.close()
    print("\nMigration complete!")

if __name__ == "__main__":
    print("Migrating SQLite → Supabase ...")
    migrate()
