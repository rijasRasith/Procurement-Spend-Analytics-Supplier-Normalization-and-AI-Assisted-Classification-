# Procurement Domain Notes

## Source-to-Pay (S2P) Flow

The Source-to-Pay process covers the complete journey from identifying a need to
making the final payment. A requisitioner raises a **purchase requisition** describing
what is needed and for how much. After internal approval, a **purchase order (PO)** is
issued to the chosen supplier — this is the legally binding commitment. When goods
arrive or services are completed the recipient logs a **goods receipt (GR)**. The
supplier then submits an **invoice**. In a **three-way match**, the accounts payable
system checks that the PO, GR, and invoice all agree on quantity and price before
authorising **payment**. Invoices arriving without a matching PO bypass this control
and represent potential maverick or off-contract spend.

---

## Key Spend Analytics Terms

**Spend cube:** A multi-dimensional view of spend data with dimensions such as
supplier, category, department, time period, and geography. Analysts slice and dice
the cube to answer questions like "how much did Finance spend on IT services last
quarter?"

**Taxonomy:** A structured hierarchy of spend categories. A typical three-level
taxonomy looks like: Level 1 (Goods / Services) → Level 2 (IT, Facilities,
Professional Services) → Level 3 (Software Licenses, HVAC Maintenance, Legal
Counsel). Consistent taxonomy enables cross-department and cross-supplier comparisons.

**Supplier normalization:** The process of reconciling variant spellings, abbreviations,
and aliases of the same supplier into a single canonical record. Without it, spend with
one vendor appears split across many fake "suppliers."

**Supplier consolidation:** Using the insights from normalized spend data to reduce
the number of active suppliers in a category, concentrating volume with fewer vendors
to unlock volume discounts and reduce administration overhead.

**Tail spend:** The long tail of small-value, low-frequency transactions that collectively
represent a meaningful share of total spend but individually receive little attention.
Often a source of hidden maverick and fragmented spend.

---

## Spend Opportunity Types

**Maverick spend:** Purchasing that occurs outside the approved process — most
commonly invoices that arrive without a corresponding purchase order. It bypasses
negotiated pricing, supplier vetting, and audit controls. Detection: flag transactions
where the contract or PO reference is absent or coded as a direct voucher.

**Fragmented spend:** The same category of goods or services purchased from a large
number of different suppliers, often by different departments acting independently.
This destroys volume leverage and creates duplicated supplier management effort.
Detection: identify categories with high supplier counts and low average spend per
supplier.

**Supplier concentration:** The opposite risk — too large a share of total spend or
a critical category concentrated with one or two suppliers. A supplier failure or price
increase would have a disproportionate impact. Detection: compute each supplier's
share within each category and flag categories where the top supplier exceeds a
concentration threshold.

**Duplicate suppliers:** The same legal entity recorded under different names, tax IDs,
or addresses in the system of record. Spend appears dispersed when it is not, hiding
true concentration and blocking consolidation negotiations. Detection: fuzzy name
matching combined with address or identifier matching.

---

## Common Data Quality Problems in Spend Data

| Problem | Impact |
|---|---|
| Missing or inconsistent categories | Cannot classify spend; analytics incomplete |
| Inconsistent supplier names | Inflates unique supplier count; hides true concentration |
| Duplicate invoices | Overstates spend; risk of double payment |
| Negative or zero amounts | Distorts totals; may be credits, reversals, or errors |
| Mixed currencies | Amounts incomparable without conversion rates |
| Wrong or future dates | Corrupts time-series analysis |
| Missing PO references | Cannot detect maverick spend accurately |
| Duplicate transactions | Same as duplicate invoices but at transaction level |
