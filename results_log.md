# Results Log — Procurement Spend Analytics

Generated: 2026-10-13 15:57

## Dataset
- Source: City of Chicago Vendor Payments (data.cityofchicago.org)
- Rows loaded: 472,616
- Rows after cleansing (positive amounts only): 472,182
- Date range: 2022-01-03 to 2026-10-09

## Data Quality
- null_amount: 0 rows flagged, 0 removed
- negative_amount: 422 rows flagged, 0 removed
- zero_amount: 12 rows flagged, 0 removed
- future_date: 0 rows flagged, 0 removed
- unparseable_date: 116,619 rows flagged, 0 removed
- null_vendor: 0 rows flagged, 0 removed
- null_department: 287,348 rows flagged, 0 removed
- duplicate_transaction: 25,452 rows flagged, 0 removed
- likely_duplicate_invoice: 13,761 rows flagged, 0 removed
- outlier_amount: 4,722 rows flagged, 0 removed
- maverick_spend_flagged: 232,150 rows flagged, 0 removed

## Supplier Normalization
- Raw unique supplier name variants: 76,481
- Canonical suppliers after normalization: 72,552
- Reduction: 3,929 fewer unique entities
- Fuzzy matching threshold: 88 (token sort ratio)
- Manual validation sample: outputs/normalization_validation_sample.csv (50 groups for review)

## Taxonomy
- 2 Level-1 categories (Goods, Services)
- 17 Level-2 categories
- 44 Level-3 categories

## Classification
- Rule-based: 16.2% of rows
- LLM-assisted (Gemini 1.5 Flash): 0.0% of rows
- Unclassified / needs review: 83.8% of rows
- Accuracy sample: outputs/classification_accuracy_sample.csv (150 rows for hand-labeling)
- LLM model: gemini-1.5-flash, prompt version: v1.0

## Spend Analysis
- Total spend: $119,147,424,568
- Total transactions: 472,182
- Unique canonical suppliers: 72,552
- Unique departments: 64
- Top 10 suppliers share: 23.48%
- Top 20 suppliers share: 31.7%
- Suppliers making up 80% of spend: 378
- Maverick spend value: $21,091,866,414
- Maverick spend share: 17.7%
- Anomaly threshold (3σ): $9,935,234
- Anomalous transactions: 1879

## Opportunity Sizing (Estimates — Assumptions Clearly Stated)
- Maverick spend recovery (20% addressable × 8% saving): $337,469,863
- Fragmented category consolidation — top 3 categories (5% discount): $29,861,625
- Note: These are illustrative estimates based on stated assumptions. Not auditable savings figures.