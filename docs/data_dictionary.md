# Data Dictionary — City of Chicago Vendor Payments

**Source:** City of Chicago Open Data Portal  
**Dataset:** Payments  
**URL:** https://data.cityofchicago.org/Administration-Finance/Payments/s4vu-giwb  
**License:** Public Domain (City of Chicago Open Data)  
**Downloaded:** Full dataset via API export

---

## Original Columns

| Column | API Field | Type | Description | Observed Issues |
|---|---|---|---|---|
| VENDOR NAME | vendor_name | Text | Name of the vendor or payee receiving the payment | Inconsistent casing, abbreviations, punctuation; same entity recorded under multiple names |
| VOUCHER NUMBER | voucher_number | Text | Unique identifier for the payment voucher | Mostly unique; some apparent duplicates observed |
| AMOUNT | amount | Numeric | Dollar amount of the payment | Includes negative values (likely credit notes or reversals); zero-value entries present |
| CHECK DATE | check_date | Text | Date the payment or check was issued | Stored as text; inconsistent date formats; some future or implausible dates |
| DEPARTMENT NAME | department_name | Text | City department responsible for the expenditure | Inconsistent naming; some blank entries |
| CONTRACT NUMBER | contract_number | Text | Associated contract identifier. Values prefixed with "DV" indicate a Direct Voucher — spend not tied to a formal signed contract (e.g. utilities, legal settlements) | Many DV-prefixed values; used as maverick-spend proxy |

---

## Derived / Engineered Columns

| Column | Description |
|---|---|
| is_maverick | Boolean flag: True when contract_number starts with "DV" or is null/blank. Used as a proxy for spend outside formal contract (maverick spend). Documented as synthetic because the dataset has no true PO reference field. |
| normalized_vendor | Rule-cleaned vendor name (lowercased, punctuation removed, legal suffixes stripped) used as input to fuzzy matching |
| supplier_id | Foreign key linking each transaction to the supplier master table |
| canonical_vendor | The chosen canonical name for the matched supplier group |
| l1_category | Level-1 spend category (Goods / Services) |
| l2_category | Level-2 spend category (e.g. IT, Facilities, Professional Services) |
| l3_category | Level-3 spend category (specific sub-category) |
| classification_method | How the category was assigned: "rule", "llm", or "unclassified" |
| llm_confidence | Confidence level returned by the LLM ("high", "medium", "low") — null for rule-classified rows |
| dq_flag | Pipe-separated list of data quality flags applied to the row (e.g. "negative_amount|duplicate_invoice") |

---

## Maverick Spend Definition (Documented Assumption)

The Chicago payments dataset does not contain a PO number field. "Maverick spend" is approximated by the `CONTRACT NUMBER` field:

- Rows where `contract_number` starts with `"DV"` are classified as **Direct Vouchers** — the City of Chicago's own designation for non-contract spend.  
- Rows where `contract_number` is null or blank are also flagged as maverick.  
- All other rows (contract number present and not DV-prefixed) are treated as contract-backed spend.

This definition is disclosed in the README and in the management summary as an approximation. It is not a synthetic random flag; it is derived from the dataset's own contract-type coding.

---

## Known Data Quality Issues (pre-cleaning)

| Issue | Estimated Prevalence |
|---|---|
| Inconsistent vendor name casing / punctuation | Widespread |
| Duplicate transactions (same voucher / same vendor + amount + date) | Small percentage |
| Negative amounts (credit notes or reversals) | Present — flagged, not removed |
| Zero-amount transactions | Present — flagged |
| Missing department name | Small percentage |
| Missing contract number | Present — treated as maverick |
| Mixed or malformed date strings | Present in older records |
