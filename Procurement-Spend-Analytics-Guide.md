# Implementation Guide: Procurement Spend Analytics (Supplier Normalization and AI-Assisted Classification)

Repo name: **Procurement-Spend-Analytics-Supplier-Normalization-Classification**
Effort: about 8 to 10 days at 2 to 3 hours per day.
Tools: Python (Pandas, fuzzy matching library), MySQL, Excel, Power BI, one LLM API (OpenAI, Claude, or Gemini), Git/GitHub.

This guide says what to build, in what order, and how to know each step is done. It contains no code, so you write and understand every part yourself.

---

## 1. What you are building

A spend analytics workflow like the one a procurement analytics team runs for a customer:

1. Take raw, messy purchase data (purchase orders and invoices).
2. Cleanse and validate it.
3. Normalize supplier names and consolidate duplicates.
4. Classify every transaction into a spend taxonomy, using rules plus an LLM for hard cases.
5. Analyze spend to find savings opportunities: maverick spend, fragmented spend, and supplier concentration.
6. Present the results in a dashboard and a short management summary.

**Business problem (use in interviews):** Procurement teams cannot see where money goes because supplier names are inconsistent, categories are missing, and data is dirty. Clean, classified spend data lets them consolidate suppliers, negotiate better, and stop off-contract buying.

---

## 2. Resume claims this project must make true

| Resume claim | What proves it |
|---|---|
| Cleansed and validated a public procurement spend dataset (POs and invoices) with a data quality report | Cleaning scripts and a written report of issues found and fixed |
| Normalized supplier names with rules and fuzzy matching, found duplicates, built a supplier master | Supplier master table with a mapping from raw to clean names |
| Designed a multi-level spend taxonomy; classified with rules plus LLM; measured accuracy on a hand-labeled sample | Taxonomy file, classified output, labeled sample, accuracy figure |
| Flagged maverick spend, fragmented spend, and supplier concentration | Analysis outputs with counts and values |
| Power BI dashboard and management-ready summary | Dashboard file, screenshots, one-page summary |

If you skip a step, remove the matching words from the resume.

---

## 3. Learn the domain first (Day 1)

Write a one-page notes file in your own words covering:

- **Source-to-Pay flow:** requisition, approval, purchase order (PO), goods receipt, invoice, three-way match, payment.
- **Spend analytics terms:** spend cube, taxonomy (for example a UNSPSC-style category hierarchy), supplier normalization, supplier consolidation, tail spend.
- **Opportunity types:**
  - **Maverick spend:** buying outside the approved process, such as invoices with no PO.
  - **Fragmented spend:** the same category bought from many suppliers or by many units, losing volume discounts.
  - **Supplier concentration:** too much spend with few suppliers, creating dependency risk.
  - **Duplicate suppliers:** the same company recorded under different names or IDs.
- **Data quality problems typical in spend data:** missing categories, inconsistent supplier names, duplicate invoices, negative or zero amounts, mixed currencies, wrong dates.

**Done when:** you can explain each term to a non-technical person in two sentences.

---

## 4. Choose and understand the dataset (Day 1 to 2)

- Pick a **public procurement spend dataset**: open government, city council, or public-body spending files that list supplier, amount, date, department, and a description or category. Check the license and cite the source in the README.
- Choose one with at least tens of thousands of rows so classification and normalization are meaningful, and with real messiness (inconsistent supplier names).
- If it lacks PO numbers, document how you will define "PO-backed" versus "non-PO" spend. For example, use a PO reference field if present, or a transaction type or description field. If nothing exists, add a clearly labeled synthetic PO flag using a fixed random seed and state this in the README. Be honest about it.
- Write a **data dictionary**: each column, meaning, type, and observed problems.
- Profile the data: row count, missing values per column, number of unique suppliers, amount distribution, date range, currencies.

**Done when:** the data dictionary and profiling summary exist.

---

## 5. Build phases

### Phase 1: Repo setup and data loading (Day 2)

- Create the repo with folders: raw data, processed data, notebooks or scripts, SQL, outputs, docs, dashboard.
- Keep raw data untouched; every change happens in later stages and is reproducible by running scripts in order.
- Load the raw data into a MySQL table so you can also run SQL checks.

**Done when:** raw data is loaded and counts match the source file.

### Phase 2: Data cleansing and validation (Days 2 to 4)

Build a repeatable cleansing step covering:

- **Standardization:** trim spaces, fix casing, unify date formats, unify currency and number formats.
- **Missing values:** decide per column whether to fill, flag, or drop, and record the reason.
- **Duplicates:** detect exact duplicate transactions and likely duplicate invoices (same supplier, amount, and date or invoice number).
- **Invalid values:** negative or zero amounts, future dates, impossible values. Flag them rather than silently deleting; separate genuine credit notes from errors where you can tell.
- **Outliers:** identify unusually large transactions and review them.

Produce a **data quality report** with counts before and after each rule (rows affected, rows removed, rows flagged) and examples. Save a log of every rule applied.

**Done when:** a cleaned dataset exists, and the report lists each issue type with its count and how you handled it.

### Phase 3: Supplier normalization and duplicate detection (Days 4 to 6)

- **Step 1, rule-based cleanup:** lowercase, remove punctuation, remove legal suffixes (Ltd, Limited, Inc, LLC, and similar), standardize abbreviations, strip extra words and branch details.
- **Step 2, fuzzy matching:** compare cleaned names with a similarity score, group names above a threshold, and review borderline pairs manually. Use blocking (for example, compare only names sharing the first letters or a token) so matching stays fast on large data.
- **Step 3, choose a canonical name** for each group and build a **supplier master table**: supplier ID, canonical name, list of raw name variants, number of transactions, total spend.
- **Validate:** manually check a sample of 50 groups and record how many were correct merges, wrong merges, or missed merges. Tune the threshold using this check and note the trade-off between over-merging and under-merging.
- Report how many raw supplier names collapsed into how many unique suppliers.

**Done when:** every transaction has a normalized supplier ID, and you have a documented accuracy check of the matching.

### Phase 4: Spend taxonomy and classification (Days 6 to 8)

**Taxonomy**
- Design a **three-level hierarchy** (for example, Level 1: Goods or Services; Level 2: IT, Facilities, Professional Services, Logistics, and so on; Level 3: more specific categories). Aim for roughly 6 to 10 Level 2 and 20 to 40 Level 3 categories, based on what the data actually contains.
- Save it as a clear file with category names and short definitions.

**Rule-based classification**
- Build keyword and supplier-based rules that map descriptions and known suppliers to categories.
- Record what share of spend and rows the rules classify, and what remains unclassified.

**LLM-assisted classification**
- For unclassified or ambiguous rows, send the description, supplier, and the taxonomy list to an LLM and ask for a category from the fixed list, with a confidence level and short reason.
- Keep cost low: classify unique description and supplier combinations only, cache results, and process in batches.
- Constrain output to the taxonomy (reject answers not in the list) and send low-confidence rows to an "Unclassified, needs review" bucket.
- Record the model name and prompt version.

**Accuracy measurement**
- Hand-label a random sample of about 100 to 150 transactions with the correct category.
- Report accuracy for rules only, LLM only, and the combined approach, and list the most common errors.

**Done when:** every transaction has a category (or a review flag), and you have an accuracy table with a short error analysis.

### Phase 5: Spend analysis (Days 8 to 9)

Using SQL and Python, produce:

- **Spend overview:** total spend, number of transactions and suppliers, spend by category, by department or business unit, by month.
- **Top suppliers and Pareto:** share of spend held by the top 10 and top 20 suppliers; how many suppliers make up 80 percent of spend.
- **Supplier concentration:** per-category share of the top supplier or a concentration index.
- **Fragmented spend:** categories with many suppliers and low spend per supplier, which are consolidation candidates.
- **Maverick spend:** value and share of transactions without a PO, by department and category.
- **Duplicate-supplier impact:** spend sitting in suppliers that were merged, showing the benefit of normalization.
- **Anomalies:** unusual spikes, repeated invoices, and unusually large payments.
- **Opportunity sizing:** for two or three opportunities, make a simple, clearly labeled assumption-based savings estimate (for example, consolidating a fragmented category and assuming a modest discount). State assumptions clearly and call it an estimate.

**Done when:** each analysis has a saved table, and you can state the three most important findings with numbers.

### Phase 6: Excel working file (Day 9)

- Build one Excel workbook with a summary sheet, pivot tables (spend by category, supplier, department), lookup formulas linking the supplier master, and one Power Query step that loads and cleans a sheet.
- Purpose: show practical Excel skills the JD lists.

**Done when:** the workbook opens cleanly and its pivot totals match your SQL totals.

### Phase 7: Power BI dashboard (Days 9 to 10)

Pages to build:
1. **Executive overview:** total spend, suppliers, categories, trend.
2. **Category analysis:** drill from Level 1 to Level 3, with supplier breakdown.
3. **Supplier analysis:** Pareto chart, top suppliers, concentration, duplicate suppliers merged.
4. **Opportunities:** maverick spend, fragmented categories, anomalies.
5. **Data quality:** share of classified spend, unclassified spend, issues fixed.

Add filters for department, category, and date. Save screenshots and the dashboard file.

**Done when:** a non-technical viewer can find the top savings opportunity in under a minute.

### Phase 8: Management summary and documentation (Day 10)

- **One-page management summary:** three to four findings with numbers, recommended actions, estimated impact (labeled as an estimate), and assumptions and limitations.
- **README:** problem statement, dataset source and license, data dictionary link, how to run each step, key results, accuracy tables, dashboard screenshots, limitations (for example synthetic PO flag if used, accuracy measured on a small sample), and future work.
- Keep commits small and clear.

**Done when:** a stranger could reproduce your outputs and understand your findings from the README alone.

---

## 6. Numbers to record for the resume

Keep a results notes file as you go and record:

- Rows loaded, rows after cleansing, rows flagged or removed, and the count of each issue type
- Raw supplier names versus unique suppliers after normalization, and the manual check accuracy
- Taxonomy size (levels and categories)
- Share of rows and spend classified by rules, by the LLM, and left for review
- Classification accuracy on the hand-labeled sample (rules, LLM, combined)
- Top 10 and top 20 supplier share of spend, and number of suppliers making up 80 percent of spend
- Maverick spend value and percent
- Fragmented categories identified and an estimated opportunity (with assumptions)
- LLM cost or number of calls, to show efficiency

---

## 7. Final checklist

- [ ] Dataset documented with source, license, and data dictionary
- [ ] Cleansing rules and data quality report complete
- [ ] Supplier master built and manually validated
- [ ] Taxonomy defined and documented
- [ ] Rules plus LLM classification working, with accuracy on a hand-labeled sample
- [ ] Spend analysis tables produced, including maverick, fragmented, concentration, anomalies
- [ ] Excel workbook with pivots, lookups, and Power Query
- [ ] Power BI dashboard with screenshots
- [ ] One-page management summary
- [ ] README complete, with limitations stated honestly
- [ ] Real numbers recorded for the resume bullets

---

## 8. Interview preparation

Prepare short answers for:

- **Business problem:** why spend visibility is hard and what clean, classified data enables.
- **Your contribution:** each phase in one sentence.
- **How you verified quality:** data quality report, manual check of supplier groups, hand-labeled classification sample.

Be ready for these questions:
- What is maverick spend, and how did you detect it with your data?
- What is the Source-to-Pay process, and where does spend data come from?
- How did you choose the fuzzy matching threshold, and what are the risks of over-merging?
- Why combine rules with an LLM instead of using an LLM alone? (Cost, consistency, auditability, accuracy on obvious cases.)
- How do you stop an LLM from inventing categories?
- How accurate was classification, and what were the common errors?
- How would you handle the same supplier with different tax IDs or addresses?
- What would you do with unclassified spend?
- How did you size savings, and how reliable is that estimate?
- Which dashboard view would you show a Chief Procurement Officer first, and why?
- How could AI tools like ChatGPT, Gemini, or Copilot help with data quality checks and documentation in this work?
- What would you improve next? (Use item master data and contract data, add currency conversion, train a supervised classifier from reviewed labels, add supplier risk data.)
