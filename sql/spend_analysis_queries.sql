-- ============================================================
-- Spend Analytics Queries — City of Chicago Payments
-- Run against: processed_data/spend_analytics.db
-- ============================================================

-- 1. SPEND OVERVIEW
-- ---------------------------------------------------------

-- 1a. Total spend, transaction count, and unique supplier count
SELECT
    COUNT(*)                                                AS total_transactions,
    COUNT(DISTINCT supplier_id)                             AS unique_suppliers,
    COUNT(DISTINCT department_name)                         AS unique_departments,
    ROUND(SUM(amount), 2)                                   AS total_spend,
    ROUND(AVG(amount), 2)                                   AS avg_transaction,
    ROUND(MIN(amount), 2)                                   AS min_amount,
    ROUND(MAX(amount), 2)                                   AS max_amount
FROM cleaned_payments
WHERE amount > 0;

-- 1b. Spend by Level-2 category (descending)
SELECT
    l2_category,
    COUNT(*)                                                AS transactions,
    COUNT(DISTINCT supplier_id)                             AS suppliers,
    ROUND(SUM(amount), 2)                                   AS total_spend,
    ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 2) AS pct_of_total
FROM cleaned_payments
WHERE amount > 0
GROUP BY l2_category
ORDER BY total_spend DESC;

-- 1c. Monthly spend trend
SELECT
    SUBSTR(check_date, 1, 7)                                AS year_month,
    COUNT(*)                                                AS transactions,
    ROUND(SUM(amount), 2)                                   AS monthly_spend
FROM cleaned_payments
WHERE amount > 0 AND check_date IS NOT NULL
GROUP BY year_month
ORDER BY year_month;

-- 1d. Spend by department (top 20)
SELECT
    department_name,
    COUNT(*)                                                AS transactions,
    ROUND(SUM(amount), 2)                                   AS total_spend,
    ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 2) AS pct_of_total
FROM cleaned_payments
WHERE amount > 0
GROUP BY department_name
ORDER BY total_spend DESC
LIMIT 20;

-- 2. TOP SUPPLIERS AND PARETO ANALYSIS
-- ---------------------------------------------------------

-- 2a. Top 20 suppliers by total spend
SELECT
    canonical_vendor,
    COUNT(*)                                                AS transactions,
    ROUND(SUM(amount), 2)                                   AS total_spend,
    ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 2) AS pct_of_total
FROM cleaned_payments
WHERE amount > 0
GROUP BY supplier_id, canonical_vendor
ORDER BY total_spend DESC
LIMIT 20;

-- 2b. Pareto: cumulative share — find supplier rank where cumulative spend >= 80%
WITH ranked AS (
    SELECT
        canonical_vendor,
        ROUND(SUM(amount), 2)                               AS total_spend,
        ROW_NUMBER() OVER (ORDER BY SUM(amount) DESC)       AS rnk
    FROM cleaned_payments
    WHERE amount > 0
    GROUP BY supplier_id, canonical_vendor
),
cumulative AS (
    SELECT
        canonical_vendor,
        total_spend,
        rnk,
        ROUND(100.0 * SUM(total_spend) OVER (ORDER BY rnk) /
              SUM(total_spend) OVER (), 2)                  AS cumulative_pct
    FROM ranked
)
SELECT *
FROM cumulative
WHERE cumulative_pct <= 85 OR rnk <= 5
ORDER BY rnk;

-- 3. SUPPLIER CONCENTRATION PER CATEGORY
-- ---------------------------------------------------------

-- 3a. Top supplier share within each Level-2 category
WITH category_totals AS (
    SELECT l2_category, ROUND(SUM(amount), 2) AS category_total
    FROM cleaned_payments WHERE amount > 0
    GROUP BY l2_category
),
supplier_in_category AS (
    SELECT
        l2_category,
        canonical_vendor,
        supplier_id,
        ROUND(SUM(amount), 2)                               AS supplier_spend
    FROM cleaned_payments WHERE amount > 0
    GROUP BY l2_category, supplier_id, canonical_vendor
),
ranked_in_category AS (
    SELECT
        sc.*,
        ct.category_total,
        ROW_NUMBER() OVER (PARTITION BY sc.l2_category ORDER BY sc.supplier_spend DESC) AS rnk_in_cat
    FROM supplier_in_category sc
    JOIN category_totals ct ON sc.l2_category = ct.l2_category
)
SELECT
    l2_category,
    canonical_vendor                                        AS top_supplier,
    supplier_spend,
    category_total,
    ROUND(100.0 * supplier_spend / category_total, 2)       AS top_supplier_share_pct
FROM ranked_in_category
WHERE rnk_in_cat = 1
ORDER BY top_supplier_share_pct DESC;

-- 4. FRAGMENTED SPEND ANALYSIS
-- ---------------------------------------------------------

-- 4a. Categories with many suppliers and low average spend per supplier
SELECT
    l2_category,
    COUNT(DISTINCT supplier_id)                             AS num_suppliers,
    ROUND(SUM(amount), 2)                                   AS total_spend,
    ROUND(SUM(amount) / COUNT(DISTINCT supplier_id), 2)     AS avg_spend_per_supplier,
    COUNT(*)                                                AS num_transactions
FROM cleaned_payments
WHERE amount > 0
GROUP BY l2_category
HAVING COUNT(DISTINCT supplier_id) > 5
ORDER BY avg_spend_per_supplier ASC
LIMIT 15;

-- 5. MAVERICK SPEND ANALYSIS
-- ---------------------------------------------------------

-- 5a. Maverick spend total and share
SELECT
    is_maverick,
    COUNT(*)                                                AS transactions,
    ROUND(SUM(amount), 2)                                   AS total_spend,
    ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 2) AS pct_of_total
FROM cleaned_payments
WHERE amount > 0
GROUP BY is_maverick;

-- 5b. Maverick spend by department
SELECT
    department_name,
    COUNT(*)                                                AS maverick_transactions,
    ROUND(SUM(amount), 2)                                   AS maverick_spend,
    ROUND(100.0 * SUM(CASE WHEN is_maverick = 1 THEN amount ELSE 0 END) /
          NULLIF(SUM(amount), 0), 2)                        AS maverick_pct
FROM cleaned_payments
WHERE amount > 0
GROUP BY department_name
HAVING SUM(CASE WHEN is_maverick = 1 THEN amount ELSE 0 END) > 0
ORDER BY maverick_spend DESC
LIMIT 20;

-- 5c. Maverick spend by category
SELECT
    l2_category,
    COUNT(*)                                                AS maverick_transactions,
    ROUND(SUM(amount), 2)                                   AS maverick_spend,
    ROUND(100.0 * SUM(CASE WHEN is_maverick = 1 THEN amount ELSE 0 END) /
          NULLIF(SUM(amount), 0), 2)                        AS maverick_pct
FROM cleaned_payments
WHERE amount > 0
GROUP BY l2_category
ORDER BY maverick_spend DESC;

-- 6. DUPLICATE SUPPLIER IMPACT
-- ---------------------------------------------------------

-- Spend that was originally fragmented across multiple raw names but now
-- consolidated under a single canonical supplier after normalization.
SELECT
    sm.canonical_name,
    sm.transaction_count,
    ROUND(sm.total_spend, 2)                                AS total_spend,
    sm.raw_variants
FROM supplier_master sm
WHERE sm.raw_variants LIKE '%|%'
ORDER BY sm.total_spend DESC
LIMIT 30;

-- 7. ANOMALIES
-- ---------------------------------------------------------

-- 7a. Unusually large single transactions (above the 99th percentile)
WITH stats AS (
    SELECT AVG(amount) AS mu, AVG(amount * amount) - AVG(amount) * AVG(amount) AS var
    FROM cleaned_payments WHERE amount > 0
)
SELECT
    p.vendor_name,
    p.canonical_vendor,
    p.department_name,
    p.check_date,
    ROUND(p.amount, 2)                                      AS amount,
    p.voucher_number,
    p.l2_category
FROM cleaned_payments p
WHERE p.amount > (SELECT mu + 3 * SQRT(var) FROM stats)
  AND p.amount > 0
ORDER BY p.amount DESC
LIMIT 50;

-- 7b. Flagged rows summary (data quality flags)
SELECT
    dq_flag,
    COUNT(*)                                                AS row_count,
    ROUND(SUM(amount), 2)                                   AS total_value
FROM cleaned_payments
WHERE dq_flag IS NOT NULL AND dq_flag != ''
GROUP BY dq_flag
ORDER BY row_count DESC;

-- 8. CLASSIFICATION COVERAGE
-- ---------------------------------------------------------

SELECT
    classification_method,
    COUNT(*)                                                AS transactions,
    ROUND(SUM(amount), 2)                                   AS total_spend,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)      AS pct_rows,
    ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 2) AS pct_spend
FROM cleaned_payments
WHERE amount > 0
GROUP BY classification_method;

-- 9. OPPORTUNITY SIZING ESTIMATES
-- ---------------------------------------------------------

-- 9a. Fragmented category consolidation opportunity
-- Assumption: consolidating to 30% fewer suppliers in fragmented categories
-- yields an estimated 5% price reduction on consolidated volume.
-- These are illustrative estimates — assumptions stated explicitly.
WITH fragmented AS (
    SELECT
        l2_category,
        COUNT(DISTINCT supplier_id)                         AS num_suppliers,
        ROUND(SUM(amount), 2)                               AS category_spend
    FROM cleaned_payments
    WHERE amount > 0
    GROUP BY l2_category
    HAVING COUNT(DISTINCT supplier_id) > 10
)
SELECT
    l2_category,
    num_suppliers,
    category_spend,
    ROUND(category_spend * 0.05, 2)                         AS estimated_savings,
    '5% consolidation discount assumption on fragmented category' AS assumption
FROM fragmented
ORDER BY estimated_savings DESC;

-- 9b. Maverick spend recovery opportunity
-- Assumption: bringing 20% of maverick spend into contract coverage
-- at an assumed 8% savings versus spot pricing.
SELECT
    ROUND(SUM(CASE WHEN is_maverick = 1 THEN amount ELSE 0 END), 2)     AS total_maverick_spend,
    ROUND(SUM(CASE WHEN is_maverick = 1 THEN amount ELSE 0 END) * 0.20, 2) AS addressable_maverick,
    ROUND(SUM(CASE WHEN is_maverick = 1 THEN amount ELSE 0 END) * 0.20 * 0.08, 2) AS estimated_savings,
    '20% of maverick brought under contract; 8% price improvement assumed' AS assumption
FROM cleaned_payments
WHERE amount > 0;
