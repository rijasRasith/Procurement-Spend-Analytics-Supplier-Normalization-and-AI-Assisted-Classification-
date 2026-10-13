# Management Summary — Chicago Procurement Spend Analytics

**Date:** October 2026  
**Dataset:** City of Chicago Vendor Payments — 472,182 transactions, $119,147,424,568 total spend  
**Prepared by:** Procurement Spend Analytics Pipeline

---

## Key Findings

### 1. Significant Maverick Spend — 17.7% of Total Spend is Off-Contract
$21,091,866,414 (17.7% of total spend) was transacted through Direct Vouchers or with no contract reference —
the City's own coding for non-contract purchasing. This spend bypasses negotiated pricing, supplier vetting, and
three-way match controls. Departments with the highest maverick share are identified in the Opportunities dashboard page.

**Recommended action:** Implement mandatory PO requirements for all non-utility, non-debt-service categories above $5,000.
Estimated savings from bringing 20% of maverick spend under contract at an 8% improvement over spot rates: 
**$337,469,863** *(illustrative estimate; assumes 8% rate improvement and 20% addressability)*.

---

### 2. High Supplier Concentration — Top 10 Suppliers Hold 23.5% of Spend
The top 10 canonical suppliers account for 23.5% of total spend. While some concentration in high-value
infrastructure and utility contracts is expected, concentration in discretionary categories such as Professional Services
and IT creates dependency risk. The data also shows that supplier name fragmentation was masking true concentration:
after normalization, 76,481 raw name variants consolidated into 72,552 
canonical suppliers.

**Recommended action:** Review per-category concentration ratios (see Supplier Concentration output). For categories where
a single supplier holds more than 60% of category spend, assess contract terms and initiate competitive review at renewal.

---

### 3. Fragmented Spend — Consolidation Opportunity in Public Safety Equipment, Office Supplies, Public Safety Services
These categories show a high number of active suppliers with low average spend per supplier, indicating that multiple
departments are purchasing the same goods and services independently. This fragments volume, eliminates negotiation
leverage, and increases supplier management overhead.

**Recommended action:** Conduct a category strategy review for the top three fragmented categories. Consolidating to
preferred supplier panels and mandating preferred-supplier usage could yield an estimated 
**$29,861,625** in savings 
*(5% consolidation discount assumption — illustrative estimate)*.

---

### 4. Classification Coverage — 83.8% of Transactions Require Human Review
The combined rule-and-LLM classification system categorised the majority of spend. A residual share remains in the 
"Unclassified — needs review" bucket, representing spend that does not match any pattern in the current taxonomy or
for which the LLM returned low confidence. This spend should be reviewed and used to extend the rule set for future runs.

---

## Assumptions and Limitations

- **Maverick spend proxy:** The dataset has no PO reference field. DV-prefixed and blank contract numbers are used as a
  maverick proxy. This is the City's own designation; however, some DV payments (utilities, debt service) are legitimately
  off-contract and would require further filtering.
- **Savings estimates** are illustrative. They use stated discount and addressability assumptions and are not auditable
  savings figures. A rigorous savings case requires contract data, pricing benchmarks, and stakeholder validation.
- **Supplier normalization accuracy** was validated on a 50-group sample. The matching threshold was set at 88 (token sort 
  ratio) to balance over-merging risk against under-merging. Some false merges or missed merges may remain.
- **Classification accuracy** was measured on a 150-row hand-labeled sample. See outputs/classification_accuracy_sample.csv
  for detailed results.
- **Currency:** All amounts are in USD as published by the City of Chicago.

---

## Recommended Next Steps

1. Extend the ruleset using the unclassified review bucket to improve classification coverage.
2. Integrate contract expiry and pricing data to enable true savings baselining.
3. Add currency conversion for any multi-currency datasets in future.
4. Train a supervised classifier using the reviewed hand-labeled sample as training data.
5. Add supplier risk data (D&B or equivalent) to the supplier master to surface concentration risk.
