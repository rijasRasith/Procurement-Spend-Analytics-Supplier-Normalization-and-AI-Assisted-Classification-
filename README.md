# Procurement Spend Analytics — Supplier Normalization and AI-Assisted Classification

A complete procurement spend analytics workflow built on the City of Chicago Vendor Payments public dataset.
The pipeline ingests raw payment data, cleanses and validates it, normalises supplier names using rule-based
cleaning and fuzzy matching, classifies every transaction into a three-level spend taxonomy using keyword
rules and a Gemini LLM, and analyses spend to surface maverick spend, fragmented categories, and supplier
concentration. Outputs include a cleaned SQLite database, a supplier master, analysis tables, an Excel
workbook, and a management summary.

---

## Dataset

| Property | Detail |
|---|---|
| **Source** | City of Chicago Open Data Portal |
| **Dataset** | Payments (Vendor Payments) |
| **URL** | https://data.cityofchicago.org/Administration-Finance/Payments/s4vu-giwb |
| **License** | Public Domain — City of Chicago Open Data |
| **Columns** | VENDOR NAME, VOUCHER NUMBER, AMOUNT, CHECK DATE, DEPARTMENT NAME, CONTRACT NUMBER |

The dataset lists every payment made by City of Chicago departments to vendors. CONTRACT NUMBER values
prefixed with "DV" denote Direct Vouchers — the City's own designation for non-contract spend such as
utilities, debt service, and legal settlements. This field is used as the maverick-spend proxy because
the dataset contains no PO reference field. This approximation is documented in `docs/data_dictionary.md`
and acknowledged in the management summary.

---

## Project Structure

```
├── raw_data/                        # Untouched source CSV (downloaded by pipeline)
├── processed_data/
│   ├── spend_analytics.db           # SQLite database (all pipeline stages)
│   ├── chicago_payments_cleaned.csv # Cleansed dataset with DQ flags
│   ├── chicago_payments_classified.csv # Fully classified dataset
│   └── supplier_master.csv          # Canonical supplier list with raw name variants
├── outputs/
│   ├── data_quality_report.csv      # Rule-by-rule DQ counts
│   ├── data_profile.json            # Dataset profile (rows, missings, stats)
│   ├── normalization_validation_sample.csv  # 50 groups for manual accuracy check
│   ├── classification_accuracy_sample.csv   # 150 rows for hand-labeling
│   ├── procurement_spend_analysis.xlsx      # Excel workbook with pivot tables
│   ├── management_summary.md        # One-page management findings
│   └── analysis/
│       ├── spend_by_category.csv
│       ├── spend_by_department.csv
│       ├── monthly_spend_trend.csv
│       ├── top_suppliers.csv
│       ├── supplier_pareto.csv
│       ├── supplier_concentration.csv
│       ├── fragmented_spend.csv
│       ├── maverick_spend_summary.csv
│       ├── maverick_spend_by_department.csv
│       ├── maverick_spend_by_category.csv
│       ├── duplicate_supplier_impact.csv
│       ├── anomalies.csv
│       ├── classification_coverage.csv
│       ├── opportunity_fragmented.csv
│       └── opportunity_maverick.csv
├── sql/
│   ├── schema.sql                   # SQLite table and index definitions
│   └── spend_analysis_queries.sql   # Analytical SQL queries (run ad hoc)
├── docs/
│   ├── data_dictionary.md           # Column definitions, derived fields, known issues
│   ├── taxonomy.csv                 # Three-level spend taxonomy (2 L1, 17 L2, 44 L3)
│   └── domain_notes.md              # Source-to-Pay and spend analytics domain notes
├── scripts/
│   └── pipeline.py                  # Main end-to-end pipeline script
├── results_log.md                   # Key numbers for resume and interview prep
├── pipeline.log                     # Runtime log (generated on each run)
├── .env                             # API keys — not committed to version control
└── README.md
```

---

## How to Run

### 1. Install dependencies

```bash
pip install pandas numpy thefuzz rapidfuzz python-Levenshtein google-generativeai openpyxl xlsxwriter python-dotenv
```

### 2. Configure Gemini API key

Edit `.env` and replace the placeholder:

```
GEMINI_API_KEY=your_actual_api_key_here
```

Get a free key at https://aistudio.google.com/app/apikey

If you omit the key the pipeline will still run — LLM classification is skipped and those rows remain
in the "unclassified" bucket. All other phases complete normally.

### 3. Run the pipeline

```bash
cd scripts
python pipeline.py
```

The pipeline runs all phases in order:

| Step | What happens |
|---|---|
| Init | Creates SQLite schema and output folders |
| Download | Downloads the Chicago Payments CSV (~300,000 rows) if not already present |
| Profile | Counts rows, missings, unique vendors, amount distribution |
| Load to DB | Inserts raw data into `raw_payments` table for SQL validation |
| DQ Flagging | Applies 10 data quality rules; produces `data_quality_report.csv` |
| Normalization | Rule cleans, then fuzzy-matches vendor names; builds supplier master |
| Classification | Keyword rules first; Gemini LLM for unclassified rows; results cached |
| Analysis | Produces 15 analysis CSV files covering all opportunity types |
| DB Save | Writes cleaned + classified data and supplier master to SQLite |
| Excel | Builds multi-sheet Excel workbook with formatted pivot tables |
| Reports | Writes `results_log.md` and `management_summary.md` |

### 4. Run ad hoc SQL queries

```bash
sqlite3 processed_data/spend_analytics.db < sql/spend_analysis_queries.sql
```

Or open the database in DB Browser for SQLite and run queries from `sql/spend_analysis_queries.sql`.

---

## Key Results

> Numbers are populated into `results_log.md` after the first run.

| Metric | Value |
|---|---|
| Rows loaded | (from results_log.md) |
| Rows after cleansing | (from results_log.md) |
| Raw supplier name variants | (from results_log.md) |
| Canonical suppliers after normalization | (from results_log.md) |
| Rule-classified share | (from results_log.md) |
| LLM-classified share | (from results_log.md) |
| Maverick spend share | (from results_log.md) |
| Top 10 supplier spend share | (from results_log.md) |
| Suppliers for 80% of spend | (from results_log.md) |

---

## Taxonomy

The spend taxonomy is defined in `docs/taxonomy.csv`. It has:

- **2 Level-1 categories:** Goods, Services
- **17 Level-2 categories:** IT Hardware, Office Supplies, Fleet and Vehicles, Public Safety Equipment,
  Facilities and Maintenance, Medical and Healthcare Supplies, Technology and Software, IT Services,
  Professional Services, Facilities Services, Public Safety Services, Healthcare Services,
  Transportation and Logistics, Utilities, Construction and Engineering, Education and Training,
  Marketing and Communications, Financial Services, Other Services
- **44 Level-3 categories**

---

## Accuracy and Validation

### Supplier Normalization
- Fuzzy matching uses `thefuzz` token sort ratio with a threshold of 88.
- A 50-group sample is saved to `outputs/normalization_validation_sample.csv` for manual review.
- Fill in the manual review column to record correct merges, wrong merges, and missed merges.
- The threshold of 88 was chosen to minimise wrong merges (over-merging risk) at the cost of some missed
  merges that could be caught with address or identifier matching.

### Classification Accuracy
- A 150-row random sample is saved to `outputs/classification_accuracy_sample.csv`.
- Open the file, fill in `manual_l1`, `manual_l2`, `manual_l3`, and `is_correct` columns.
- Accuracy = correct rows / total sample rows.
- Compute separately for rule-classified and LLM-classified rows to identify which method performs better
  on which categories.

---

## Limitations

1. **Maverick spend proxy:** No PO reference exists in the dataset. DV-prefixed and blank contract numbers
   are used as an approximation. Some DV payments (utilities, debt service) are legitimately off-contract
   and inflate the maverick figure. Further filtering by category would sharpen this.
2. **Savings estimates** in `management_summary.md` and `sql/spend_analysis_queries.sql` are illustrative
   and assumption-based. They are clearly labelled as estimates throughout.
3. **Normalization accuracy** is validated on a 50-row sample. Edge cases (subsidiaries, DBA names,
   brand names) may not be caught.
4. **LLM classification** is subject to model drift. Results are cached in SQLite to ensure reproducibility.
   The model name and prompt version are recorded per cached result.
5. **Classification accuracy** is measured on a 150-row sample — statistically modest. Reported accuracy
   carries confidence intervals that should be considered when citing the figure.
6. **Currency:** All amounts are in USD as published. No multi-currency conversion is needed for this dataset.

---

## Future Improvements

- Integrate contract data and item master to enable true three-way match simulation.
- Add supplier risk data (D&B, OFAC) to the supplier master.
- Train a supervised classifier on the reviewed hand-labeled sample.
- Add address and tax ID matching to catch subsidiaries not caught by name matching alone.
- Extend to multi-currency datasets with daily FX conversion.
- Automate monthly refresh via scheduled pipeline run.

---

## Interview Reference

See `docs/domain_notes.md` for explanations of Source-to-Pay, maverick spend, fragmented spend,
supplier concentration, and data quality patterns.

See `results_log.md` after running the pipeline for numbers to cite in resume bullets and interview answers.
