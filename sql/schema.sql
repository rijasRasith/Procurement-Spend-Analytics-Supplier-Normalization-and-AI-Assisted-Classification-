CREATE TABLE IF NOT EXISTS raw_payments (
    row_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_name     TEXT,
    voucher_number  TEXT,
    amount          REAL,
    check_date      TEXT,
    department_name TEXT,
    contract_number TEXT
);

CREATE TABLE IF NOT EXISTS cleaned_payments (
    row_id              INTEGER PRIMARY KEY,
    vendor_name         TEXT,
    voucher_number      TEXT,
    amount              REAL,
    check_date          TEXT,
    department_name     TEXT,
    contract_number     TEXT,
    is_maverick         INTEGER,
    dq_flag             TEXT,
    normalized_vendor   TEXT,
    supplier_id         TEXT,
    canonical_vendor    TEXT,
    l1_category         TEXT,
    l2_category         TEXT,
    l3_category         TEXT,
    classification_method TEXT,
    llm_confidence      TEXT
);

CREATE TABLE IF NOT EXISTS supplier_master (
    supplier_id     TEXT PRIMARY KEY,
    canonical_name  TEXT NOT NULL,
    raw_variants    TEXT,
    transaction_count INTEGER,
    total_spend     REAL
);

CREATE TABLE IF NOT EXISTS classification_cache (
    cache_key       TEXT PRIMARY KEY,
    l1_category     TEXT,
    l2_category     TEXT,
    l3_category     TEXT,
    confidence      TEXT,
    reason          TEXT,
    model_version   TEXT,
    prompt_version  TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS data_quality_report (
    rule_name       TEXT,
    rows_affected   INTEGER,
    rows_removed    INTEGER,
    rows_flagged    INTEGER,
    example         TEXT
);

CREATE TABLE IF NOT EXISTS spend_analysis_summary (
    metric_name     TEXT PRIMARY KEY,
    metric_value    TEXT
);

CREATE INDEX IF NOT EXISTS idx_cleaned_supplier ON cleaned_payments(supplier_id);
CREATE INDEX IF NOT EXISTS idx_cleaned_dept ON cleaned_payments(department_name);
CREATE INDEX IF NOT EXISTS idx_cleaned_date ON cleaned_payments(check_date);
CREATE INDEX IF NOT EXISTS idx_cleaned_l2 ON cleaned_payments(l2_category);
CREATE INDEX IF NOT EXISTS idx_cleaned_maverick ON cleaned_payments(is_maverick);
