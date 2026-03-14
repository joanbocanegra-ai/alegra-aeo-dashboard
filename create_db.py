"""Creates the SQLite database with all AEO data for the Streamlit dashboard."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "aeo_data.db")

def create_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # --- Métricas table ---
    c.execute("""CREATE TABLE IF NOT EXISTS metricas (
        batch_id TEXT, batch_date TEXT, batch_month TEXT, batch_quarter TEXT,
        prompt_id TEXT, country_id TEXT, product_category TEXT, funnel_stage TEXT,
        source_producto_raw TEXT, prompt_text TEXT, model_source TEXT,
        num_replicates INTEGER, num_success INTEGER,
        mention_rate REAL, citation_rate REAL, consistency_score REAL,
        avg_brand_mentions REAL, avg_response_length REAL,
        avg_rank_alegra REAL, avg_pos_pct_alegra REAL,
        ranks_alegra TEXT,
        eco_cites INTEGER, ext_cites INTEGER, total_cites INTEGER, eco_share_pct REAL,
        top_brand TEXT, top_brand_rank REAL
    )""")

    metricas = [
        ("20260313T202040Z","2026-03-13","2026-03","2026-Q1","MX-001","MX","Branded","TOFU","Alegra",
         "¿Qué es Alegra y cómo funciona en México? evalúalo frente a 2 alternativas (p. ej., CONTPAQi y Aspel) para cumplir con el SAT. Incluye pros/contras, casos ideales y para quién NO conviene.",
         "chatgpt_search",3,3,1.00,1.00,100.0,12.3,6606,1.0,0.0,"1,1,1",5,5,10,50.0,"Alegra",1.0),
        ("20260313T202040Z","2026-03-13","2026-03","2026-Q1","MX-001","MX","Branded","TOFU","Alegra",
         "¿Qué es Alegra y cómo funciona en México? evalúalo frente a 2 alternativas (p. ej., CONTPAQi y Aspel) para cumplir con el SAT. Incluye pros/contras, casos ideales y para quién NO conviene.",
         "google_aio",3,3,1.00,1.00,100.0,17.0,7029,1.0,0.0,"1,1,1",15,40,55,27.0,"Alegra",1.0),
        ("20260313T202823Z","2026-03-13","2026-03","2026-Q1","MX-023","MX","Contabilidad","BOFU","Alegra contabilidad",
         "¿Cuáles son los programas de contabilidad más utilizados en México? y compáralos en una tabla (precio, SAT/CFDI, enfoque PYME vs empresa, pros/contras). Dame un top 5.",
         "chatgpt_search",3,3,1.00,0.00,100.0,1.0,2671,5.0,61.2,"5,5,5",0,11,11,0.0,"Aspel",1.0),
        ("20260313T202823Z","2026-03-13","2026-03","2026-Q1","MX-023","MX","Contabilidad","BOFU","Alegra contabilidad",
         "¿Cuáles son los programas de contabilidad más utilizados en México? y compáralos en una tabla (precio, SAT/CFDI, enfoque PYME vs empresa, pros/contras). Dame un top 5.",
         "google_aio",3,3,1.00,1.00,100.0,7.3,6631,4.7,27.5,"4,5,5",9,33,42,21.0,"CONTPAQi",1.0),
    ]
    c.executemany("INSERT INTO metricas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", metricas)

    # --- Marcas table ---
    c.execute("""CREATE TABLE IF NOT EXISTS marcas (
        batch_id TEXT, batch_date TEXT, prompt_id TEXT, country_id TEXT,
        model_source TEXT, funnel_stage TEXT, product_category TEXT,
        brand_name TEXT, brand_rank_avg REAL, brand_presence_pct REAL,
        brand_mentions_total INTEGER, brand_ranks_by_rep TEXT,
        is_top_brand INTEGER, is_alegra INTEGER
    )""")

    marcas = [
        ("20260313T202040Z","2026-03-13","MX-001","MX","chatgpt_search","TOFU","Branded","Alegra",1.0,100,37,"1,1,1",1,1),
        ("20260313T202040Z","2026-03-13","MX-001","MX","chatgpt_search","TOFU","Branded","CONTPAQi",2.0,100,21,"2,2,2",0,0),
        ("20260313T202040Z","2026-03-13","MX-001","MX","chatgpt_search","TOFU","Branded","Aspel",3.0,100,20,"3,3,3",0,0),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","TOFU","Branded","Alegra",1.0,100,51,"1,1,1",1,1),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","TOFU","Branded","Siigo",2.0,67,10,"2,2",0,0),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","TOFU","Branded","Aspel",3.0,100,42,"3,3,3",0,0),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","TOFU","Branded","CONTPAQi",3.3,100,44,"2,4,4",0,0),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","TOFU","Branded","Bind ERP",5.0,33,2,"5",0,0),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","TOFU","Branded","Odoo",6.0,33,2,"6",0,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","chatgpt_search","BOFU","Contabilidad","Aspel",1.0,100,9,"1,1,1",1,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","chatgpt_search","BOFU","Contabilidad","CONTPAQi",2.0,100,3,"2,2,2",0,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","chatgpt_search","BOFU","Contabilidad","Microsip",3.0,100,3,"3,3,3",0,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","chatgpt_search","BOFU","Contabilidad","Alegra",4.0,100,3,"4,4,4",0,1),
        ("20260313T202823Z","2026-03-13","MX-023","MX","chatgpt_search","BOFU","Contabilidad","Bind ERP",5.0,100,8,"5,5,5",0,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","BOFU","Contabilidad","CONTPAQi",1.0,100,45,"1,1,1",1,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","BOFU","Contabilidad","Aspel",2.0,100,31,"2,2,2",0,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","BOFU","Contabilidad","Contalink",3.3,100,6,"4,3,3",0,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","BOFU","Contabilidad","Alegra",4.3,100,22,"3,5,5",0,1),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","BOFU","Contabilidad","Miskuentas",4.3,100,5,"5,4,4",0,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","BOFU","Contabilidad","Bind ERP",6.5,67,18,"6,7",0,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","BOFU","Contabilidad","QuickBooks",6.7,100,9,"6,8,6",0,0),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","BOFU","Contabilidad","Siigo",7.0,33,2,"7",0,0),
    ]
    c.executemany("INSERT INTO marcas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", marcas)

    # --- Dominios table ---
    c.execute("""CREATE TABLE IF NOT EXISTS dominios (
        batch_id TEXT, batch_date TEXT, prompt_id TEXT, country_id TEXT,
        model_source TEXT, domain TEXT, cite_count INTEGER,
        is_ecosystem INTEGER, ecosystem_brand TEXT
    )""")

    dominios = [
        ("20260313T202040Z","2026-03-13","MX-001","MX","chatgpt_search","alegra.com",3,1,"Alegra"),
        ("20260313T202040Z","2026-03-13","MX-001","MX","chatgpt_search","ayuda.alegra.com",2,1,"Alegra"),
        ("20260313T202040Z","2026-03-13","MX-001","MX","chatgpt_search","iacontable.mx",3,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","chatgpt_search","portalerp.com.mx",1,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","chatgpt_search","es.wikipedia.org",1,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","alegra.com",6,1,"Alegra"),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","programascontabilidad.com",5,1,"Alegra"),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","ayuda.alegra.com",4,1,"Alegra"),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","youtube.com",12,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","vde-suite.com",3,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","tiktok.com",3,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","soyconta.com",3,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","comprapaq.mx",3,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","erpnubemexico.mx",2,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","ccb.org.co",2,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","integraprofesional.com",2,0,""),
        ("20260313T202040Z","2026-03-13","MX-001","MX","google_aio","iconet.com.mx",2,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","chatgpt_search","iacontable.mx",4,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","chatgpt_search","xepelin.com",3,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","chatgpt_search","moonflow.ai",2,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","chatgpt_search","sifo.com.mx",1,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","chatgpt_search","bind.com.mx",1,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","programascontabilidad.com",8,1,"Alegra"),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","novedades.alegra.com",1,1,"Alegra"),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","es.scribd.com",3,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","erpnubemexico.mx",3,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","contalink.com",3,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","soyconta.com",2,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","capterra.mx",2,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","vde-suite.com",2,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","youtube.com",2,0,""),
        ("20260313T202823Z","2026-03-13","MX-023","MX","google_aio","bind.com.mx",2,0,""),
    ]
    c.executemany("INSERT INTO dominios VALUES (?,?,?,?,?,?,?,?,?)", dominios)

    conn.commit()
    conn.close()
    print(f"Database created: {DB_PATH}")

if __name__ == "__main__":
    create_db()
