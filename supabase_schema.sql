-- ============================================================
-- Alegra AEO Dashboard — Supabase PostgreSQL Schema
-- v1.0 — March 2026
-- ============================================================
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- ── 1. Dashboard Tables (current) ────────────────────────────

CREATE TABLE IF NOT EXISTS metricas (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    batch_date      DATE NOT NULL,
    batch_month     TEXT NOT NULL,        -- '2026-03'
    batch_quarter   TEXT NOT NULL,        -- '2026-Q1'
    prompt_id       TEXT NOT NULL,
    country_id      TEXT NOT NULL,        -- 'MX','CO','DO','CR'
    product_category TEXT NOT NULL,
    funnel_stage    TEXT NOT NULL,         -- 'TOFU','MOFU','BOFU'
    source_producto_raw TEXT,
    prompt_text     TEXT NOT NULL,
    model_source    TEXT NOT NULL,         -- 'chatgpt_search','google_aio'
    num_replicates  INTEGER DEFAULT 3,
    num_success     INTEGER DEFAULT 0,
    mention_rate    NUMERIC(5,4),
    citation_rate   NUMERIC(5,4),
    consistency_score NUMERIC(6,2),
    avg_brand_mentions NUMERIC(6,2),
    avg_response_length NUMERIC(10,2),
    avg_rank_alegra NUMERIC(6,2),
    avg_pos_pct_alegra NUMERIC(6,4),
    ranks_alegra    TEXT,                  -- comma-separated: '1,1,2'
    eco_cites       INTEGER DEFAULT 0,
    ext_cites       INTEGER DEFAULT 0,
    total_cites     INTEGER DEFAULT 0,
    eco_share_pct   NUMERIC(6,2),
    top_brand       TEXT,
    top_brand_rank  NUMERIC(6,2),
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    -- Composite unique: one row per prompt × motor × batch
    UNIQUE(batch_id, prompt_id, model_source)
);

CREATE TABLE IF NOT EXISTS marcas (
    id                  BIGSERIAL PRIMARY KEY,
    batch_id            TEXT NOT NULL,
    batch_date          DATE NOT NULL,
    prompt_id           TEXT NOT NULL,
    country_id          TEXT NOT NULL,
    model_source        TEXT NOT NULL,
    funnel_stage        TEXT NOT NULL,
    product_category    TEXT NOT NULL,
    brand_name          TEXT NOT NULL,
    brand_rank_avg      NUMERIC(6,2),
    brand_presence_pct  NUMERIC(6,2),
    brand_mentions_total INTEGER DEFAULT 0,
    brand_ranks_by_rep  TEXT,             -- comma-separated: '2,4,4'
    is_top_brand        BOOLEAN DEFAULT FALSE,
    is_alegra           BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(batch_id, prompt_id, model_source, brand_name)
);

CREATE TABLE IF NOT EXISTS dominios (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    batch_date      DATE NOT NULL,
    prompt_id       TEXT NOT NULL,
    country_id      TEXT NOT NULL,
    model_source    TEXT NOT NULL,
    domain          TEXT NOT NULL,
    cite_count      INTEGER DEFAULT 0,
    is_ecosystem    BOOLEAN DEFAULT FALSE,
    ecosystem_brand TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(batch_id, prompt_id, model_source, domain)
);

CREATE TABLE IF NOT EXISTS respuestas (
    id                  BIGSERIAL PRIMARY KEY,
    batch_id            TEXT NOT NULL,
    prompt_id           TEXT NOT NULL,
    model_source        TEXT NOT NULL,
    replicate_id        INTEGER NOT NULL,
    raw_response_text   TEXT,
    raw_citations_json  TEXT,             -- JSON string
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(batch_id, prompt_id, model_source, replicate_id)
);

-- ── 2. Indexes for dashboard performance ─────────────────────

CREATE INDEX IF NOT EXISTS idx_metricas_batch     ON metricas(batch_id);
CREATE INDEX IF NOT EXISTS idx_metricas_country   ON metricas(country_id);
CREATE INDEX IF NOT EXISTS idx_metricas_funnel    ON metricas(funnel_stage);
CREATE INDEX IF NOT EXISTS idx_metricas_category  ON metricas(product_category);
CREATE INDEX IF NOT EXISTS idx_metricas_motor     ON metricas(model_source);
CREATE INDEX IF NOT EXISTS idx_metricas_date      ON metricas(batch_date);

CREATE INDEX IF NOT EXISTS idx_marcas_batch       ON marcas(batch_id);
CREATE INDEX IF NOT EXISTS idx_marcas_brand       ON marcas(brand_name);
CREATE INDEX IF NOT EXISTS idx_marcas_prompt      ON marcas(prompt_id, model_source);

CREATE INDEX IF NOT EXISTS idx_dominios_batch     ON dominios(batch_id);
CREATE INDEX IF NOT EXISTS idx_dominios_domain    ON dominios(domain);

CREATE INDEX IF NOT EXISTS idx_respuestas_lookup  ON respuestas(batch_id, prompt_id, model_source);

-- ── 3. Future Data Lake tables (empty, ready for Golden Stack) ──

-- Raw output from every API call (append-only log)
CREATE TABLE IF NOT EXISTS raw_output (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    run_ts          TIMESTAMPTZ NOT NULL,
    run_id          TEXT NOT NULL,
    replicate_id    INTEGER NOT NULL,
    prompt_id       TEXT NOT NULL,
    country_id      TEXT NOT NULL,
    location_code   INTEGER,
    product_category TEXT,
    funnel_stage    TEXT,
    source_producto_raw TEXT,
    prompt_text     TEXT NOT NULL,
    model_source    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'success',
    raw_response_text TEXT,
    raw_citations_json TEXT,
    output_file_id  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_batch ON raw_output(batch_id);
CREATE INDEX IF NOT EXISTS idx_raw_date  ON raw_output(run_ts);

-- Prompt catalog (Golden Stack Input)
CREATE TABLE IF NOT EXISTS catalogo_prompts (
    id              BIGSERIAL PRIMARY KEY,
    prompt_id       TEXT NOT NULL UNIQUE,
    country_id      TEXT NOT NULL,
    location_code   INTEGER,
    product_category TEXT NOT NULL,
    funnel_stage    TEXT NOT NULL,
    source_producto_raw TEXT,
    prompt_text     TEXT NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── 4. Row Level Security (RLS) ──────────────────────────────
-- For now, disable RLS since the dashboard uses a service key
-- Enable later when adding user authentication

ALTER TABLE metricas ENABLE ROW LEVEL SECURITY;
ALTER TABLE marcas ENABLE ROW LEVEL SECURITY;
ALTER TABLE dominios ENABLE ROW LEVEL SECURITY;
ALTER TABLE respuestas ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_output ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalogo_prompts ENABLE ROW LEVEL SECURITY;

-- Allow all operations for authenticated service role
CREATE POLICY "service_all" ON metricas FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON marcas FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON dominios FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON respuestas FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON raw_output FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON catalogo_prompts FOR ALL USING (true) WITH CHECK (true);

-- ── Done ─────────────────────────────────────────────────────
-- After running this, go to Settings → API to get your keys.
