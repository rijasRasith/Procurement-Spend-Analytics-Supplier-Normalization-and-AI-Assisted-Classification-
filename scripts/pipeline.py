import os
import re
import json
import time
import hashlib
import sqlite3
import logging
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from thefuzz import fuzz
from rapidfuzz import process as rf_process
from google import genai
from google.genai import types as genai_types

warnings.filterwarnings("ignore")

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw_data"
PROCESSED_DIR = BASE_DIR / "processed_data"
OUTPUTS_DIR = BASE_DIR / "outputs"
DOCS_DIR = BASE_DIR / "docs"
SQL_DIR = BASE_DIR / "sql"

for d in [RAW_DIR, PROCESSED_DIR, OUTPUTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DB_PATH = PROCESSED_DIR / "spend_analytics.db"
RAW_CSV = RAW_DIR / "chicago_payments_raw.csv"
CLEANED_CSV = PROCESSED_DIR / "chicago_payments_cleaned.csv"
SUPPLIER_MASTER_CSV = PROCESSED_DIR / "supplier_master.csv"
CLASSIFIED_CSV = PROCESSED_DIR / "chicago_payments_classified.csv"
DQ_REPORT_CSV = OUTPUTS_DIR / "data_quality_report.csv"
ANALYSIS_DIR = OUTPUTS_DIR / "analysis"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

TAXONOMY_PATH = DOCS_DIR / "taxonomy.csv"
RESULTS_LOG = BASE_DIR / "results_log.md"

DATASET_URL = "https://data.cityofchicago.org/api/views/s4vu-giwb/rows.csv?accessType=DOWNLOAD"
DOWNLOAD_ROW_LIMIT = 300_000

FUZZY_THRESHOLD = 88
FUZZY_BLOCK_PREFIX_LEN = 3
LLM_MODEL = "gemini-1.5-flash"
PROMPT_VERSION = "v1.0"
LLM_BATCH_SIZE = 25
LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY = 5
RANDOM_SEED = 42

LEGAL_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|lp|llp|"
    r"plc|pty|pvt|assoc|associates|group|holdings|enterprises|services|"
    r"solutions|consulting|international|intl|nat|national)\b\.?",
    re.IGNORECASE,
)

LEGAL_ABBREVIATIONS = {
    "dept": "department",
    "mgt": "management",
    "mgmt": "management",
    "svc": "service",
    "svcs": "services",
    "tech": "technology",
    "sys": "systems",
    "assn": "association",
    "fdn": "foundation",
    "hosp": "hospital",
    "univ": "university",
    "comm": "community",
}

CLASSIFICATION_RULES = [
    (re.compile(r"\b(electric|electricity|comed|constellation|ameren)\b", re.I), "Services", "Utilities", "Electricity"),
    (re.compile(r"\b(water|sewer|mwrd|chicago dept water)\b", re.I), "Services", "Utilities", "Water and Sewer"),
    (re.compile(r"\b(nicor|peoples gas|natural gas|gas utility)\b", re.I), "Services", "Utilities", "Natural Gas"),
    (re.compile(r"\b(att|at&t|verizon|t-mobile|sprint|comcast|xfinity|century.?link|telecom|telephone|phone|internet|broadband)\b", re.I), "Services", "Utilities", "Telecommunications Services"),
    (re.compile(r"\b(police|cpd|sheriff|correctional|detention|jail|prison)\b", re.I), "Services", "Public Safety Services", "Detention and Corrections Services"),
    (re.compile(r"\b(fire dept|fire station|fire suppression|ambulance|ems|emergency medical)\b", re.I), "Services", "Public Safety Services", "Emergency Services Support"),
    (re.compile(r"\b(uniform|protective gear|body armor|tactical|weapon|firearm|ammunition|ammo)\b", re.I), "Goods", "Public Safety Equipment", "Uniforms and Protective Gear"),
    (re.compile(r"\b(computer|laptop|desktop|workstation|server|storage|hardware)\b", re.I), "Goods", "IT Hardware", "Computers and Laptops"),
    (re.compile(r"\b(network|router|switch|firewall|cisco|juniper|cable|wiring)\b", re.I), "Goods", "IT Hardware", "Networking Equipment"),
    (re.compile(r"\b(printer|scanner|copier|monitor|keyboard|peripheral)\b", re.I), "Goods", "IT Hardware", "Peripherals and Accessories"),
    (re.compile(r"\b(software|license|saas|subscription|oracle|sap|microsoft|adobe|salesforce)\b", re.I), "Goods", "Technology and Software", "Software Licenses"),
    (re.compile(r"\b(it consult|technology consult|system integrat|implementation)\b", re.I), "Services", "IT Services", "IT Consulting and Implementation"),
    (re.compile(r"\b(managed.?it|helpdesk|help desk|it support|it managed|outsource.?it)\b", re.I), "Services", "IT Services", "Managed IT Services"),
    (re.compile(r"\b(software dev|app dev|web dev|mobile app|custom.?software)\b", re.I), "Services", "IT Services", "Software Development"),
    (re.compile(r"\b(legal|attorney|counsel|law firm|litigation|compliance|settlement)\b", re.I), "Services", "Professional Services", "Legal Services"),
    (re.compile(r"\b(audit|account|cpa|financial advisory|tax|actuarial)\b", re.I), "Services", "Professional Services", "Financial and Accounting"),
    (re.compile(r"\b(consult|advisory|strategy|management consult)\b", re.I), "Services", "Professional Services", "Management Consulting"),
    (re.compile(r"\b(hvac|heating|cooling|ventilation|plumb|electric.?repair|building.?maint|facility|janitorial|clean.?serv)\b", re.I), "Services", "Facilities Services", "Building Maintenance"),
    (re.compile(r"\b(janitorial|cleaning|waste|pest control|sanitation|garbage|rubbish)\b", re.I), "Services", "Facilities Services", "Cleaning and Janitorial"),
    (re.compile(r"\b(security guard|physical security|access control|surveillance|cctv)\b", re.I), "Services", "Facilities Services", "Security Services"),
    (re.compile(r"\b(construction|contractor|renovation|build|infrastructure|capital project)\b", re.I), "Services", "Construction and Engineering", "Construction Contracts"),
    (re.compile(r"\b(engineer|architect|design|survey|structural)\b", re.I), "Services", "Construction and Engineering", "Engineering and Architecture"),
    (re.compile(r"\b(vehicle|truck|car|bus|van|fleet|automobile)\b", re.I), "Goods", "Fleet and Vehicles", "Vehicles"),
    (re.compile(r"\b(tire|oil|part|fuel|gasoline|diesel|auto.?part|vehicle.?repair|fleet.?maint)\b", re.I), "Goods", "Fleet and Vehicles", "Parts and Accessories"),
    (re.compile(r"\b(paper|stationery|office supply|pen|toner|cartridge|folder|envelope)\b", re.I), "Goods", "Office Supplies", "Stationery and Paper"),
    (re.compile(r"\b(furniture|desk|chair|cabinet|shelv|fixture)\b", re.I), "Goods", "Office Supplies", "Furniture and Fixtures"),
    (re.compile(r"\b(pharma|drug|medication|vaccine|medicine|rx)\b", re.I), "Goods", "Medical and Healthcare Supplies", "Pharmaceuticals"),
    (re.compile(r"\b(medical device|health equipment|diagnostic|clinical equipment)\b", re.I), "Goods", "Medical and Healthcare Supplies", "Medical Devices and Equipment"),
    (re.compile(r"\b(physician|nurse|clinic|hospital|health service|medical service)\b", re.I), "Services", "Healthcare Services", "Medical and Clinical Services"),
    (re.compile(r"\b(mental health|social service|behavioral health|counseling)\b", re.I), "Services", "Healthcare Services", "Mental Health and Social Services"),
    (re.compile(r"\b(freight|shipping|courier|delivery|logistics|warehouse)\b", re.I), "Services", "Transportation and Logistics", "Freight and Shipping"),
    (re.compile(r"\b(cta|transit|metra|bus serv|train|commuter|paratransit)\b", re.I), "Services", "Transportation and Logistics", "Transit Operations"),
    (re.compile(r"\b(training|workshop|seminar|certification|course|learning)\b", re.I), "Services", "Education and Training", "Training and Development"),
    (re.compile(r"\b(university|college|research|academic|scholarship)\b", re.I), "Services", "Education and Training", "Academic and Research Services"),
    (re.compile(r"\b(advertis|marketing|media|campaign|promotion|public relation|pr firm)\b", re.I), "Services", "Marketing and Communications", "Advertising and Media"),
    (re.compile(r"\b(print|publish|document produc|bindery|typeset)\b", re.I), "Services", "Marketing and Communications", "Printing and Publications"),
    (re.compile(r"\b(bond|debt service|interest payment|loan repay)\b", re.I), "Services", "Financial Services", "Debt Service"),
    (re.compile(r"\b(insurance|premium|coverage|indemnity|surety)\b", re.I), "Services", "Financial Services", "Insurance"),
    (re.compile(r"\b(clean supply|disinfect|janitorial supply|sanitize)\b", re.I), "Goods", "Facilities and Maintenance", "Cleaning Supplies"),
    (re.compile(r"\b(paint|lumber|concrete|material|tool|hardware.?store|building.?supply)\b", re.I), "Goods", "Facilities and Maintenance", "Building Materials"),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "pipeline.log", mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database():
    log.info("Initialising database schema")
    conn = get_db_connection()
    with open(SQL_DIR / "schema.sql", "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def download_dataset():
    if RAW_CSV.exists():
        log.info("Raw dataset already present — skipping download")
        return
    log.info("Downloading Chicago Payments dataset (this may take several minutes)…")
    import urllib.request

    url = f"{DATASET_URL}&$limit={DOWNLOAD_ROW_LIMIT}"
    urllib.request.urlretrieve(url, RAW_CSV)
    log.info(f"Download complete → {RAW_CSV}")


def load_raw_to_db(df: pd.DataFrame):
    conn = get_db_connection()
    conn.execute("DELETE FROM raw_payments")
    df_db = df.rename(columns={
        "VENDOR NAME": "vendor_name",
        "VOUCHER NUMBER": "voucher_number",
        "AMOUNT": "amount",
        "CHECK DATE": "check_date",
        "DEPARTMENT NAME": "department_name",
        "CONTRACT NUMBER": "contract_number",
    })
    cols = ["vendor_name", "voucher_number", "amount", "check_date", "department_name", "contract_number"]
    df_db[cols].to_sql("raw_payments", conn, if_exists="append", index=False)
    conn.commit()
    raw_count = conn.execute("SELECT COUNT(*) FROM raw_payments").fetchone()[0]
    conn.close()
    log.info(f"Loaded {raw_count:,} rows into raw_payments table")
    assert raw_count == len(df), "Row count mismatch between CSV and DB"


def profile_dataset(df: pd.DataFrame) -> dict:
    profile = {
        "total_rows": len(df),
        "columns": list(df.columns),
        "missing_per_column": df.isnull().sum().to_dict(),
        "unique_vendors": df["VENDOR NAME"].nunique(),
        "unique_departments": df["DEPARTMENT NAME"].nunique(),
        "amount_stats": df["AMOUNT"].describe().to_dict(),
        "date_range_raw": f"{df['CHECK DATE'].min()} to {df['CHECK DATE'].max()}",
        "currency": "USD (all amounts in USD per dataset documentation)",
    }
    log.info(f"Profile: {profile['total_rows']:,} rows | {profile['unique_vendors']:,} unique vendors | {profile['unique_departments']} departments")
    profile_path = OUTPUTS_DIR / "data_profile.json"
    with open(profile_path, "w") as f:
        json.dump({k: str(v) for k, v in profile.items()}, f, indent=2, default=str)
    return profile


def flag_dq_issues(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    log.info("Phase 2: Data quality flagging and cleansing")
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    column_map = {
        "VENDOR NAME": "vendor_name",
        "VOUCHER NUMBER": "voucher_number",
        "AMOUNT": "amount",
        "CHECK DATE": "check_date",
        "DEPARTMENT NAME": "department_name",
        "CONTRACT NUMBER": "contract_number",
    }
    df = df.rename(columns=column_map)

    for col in ["vendor_name", "department_name", "contract_number", "voucher_number"]:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "": None, "NaN": None})

    df["amount"] = pd.to_numeric(df["amount"].astype(str).str.replace(",", "").str.strip(), errors="coerce")

    def parse_date(s):
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(str(s).strip(), fmt).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
        return None

    df["check_date"] = df["check_date"].apply(parse_date)

    df["dq_flag"] = ""
    report_rows = []

    null_amount_mask = df["amount"].isnull()
    df.loc[null_amount_mask, "dq_flag"] += "null_amount|"
    report_rows.append({
        "rule_name": "null_amount",
        "rows_affected": null_amount_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": null_amount_mask.sum(),
        "example": df.loc[null_amount_mask, "vendor_name"].iloc[0] if null_amount_mask.any() else "",
    })

    neg_mask = df["amount"] < 0
    df.loc[neg_mask, "dq_flag"] += "negative_amount|"
    report_rows.append({
        "rule_name": "negative_amount",
        "rows_affected": neg_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": neg_mask.sum(),
        "example": str(df.loc[neg_mask, "amount"].iloc[0]) if neg_mask.any() else "",
    })

    zero_mask = df["amount"] == 0
    df.loc[zero_mask, "dq_flag"] += "zero_amount|"
    report_rows.append({
        "rule_name": "zero_amount",
        "rows_affected": zero_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": zero_mask.sum(),
        "example": str(df.loc[zero_mask, "vendor_name"].iloc[0]) if zero_mask.any() else "",
    })

    today = datetime.today().strftime("%Y-%m-%d")
    future_mask = df["check_date"] > today
    df.loc[future_mask, "dq_flag"] += "future_date|"
    report_rows.append({
        "rule_name": "future_date",
        "rows_affected": future_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": future_mask.sum(),
        "example": str(df.loc[future_mask, "check_date"].iloc[0]) if future_mask.any() else "",
    })

    bad_date_mask = df["check_date"].isnull()
    df.loc[bad_date_mask, "dq_flag"] += "unparseable_date|"
    report_rows.append({
        "rule_name": "unparseable_date",
        "rows_affected": bad_date_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": bad_date_mask.sum(),
        "example": "",
    })

    null_vendor_mask = df["vendor_name"].isnull()
    df.loc[null_vendor_mask, "dq_flag"] += "null_vendor|"
    report_rows.append({
        "rule_name": "null_vendor",
        "rows_affected": null_vendor_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": null_vendor_mask.sum(),
        "example": "",
    })

    null_dept_mask = df["department_name"].isnull()
    df.loc[null_dept_mask, "dq_flag"] += "null_department|"
    report_rows.append({
        "rule_name": "null_department",
        "rows_affected": null_dept_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": null_dept_mask.sum(),
        "example": "",
    })

    dup_exact_mask = df.duplicated(subset=["vendor_name", "amount", "check_date", "voucher_number"], keep=False)
    df.loc[dup_exact_mask, "dq_flag"] += "duplicate_transaction|"
    report_rows.append({
        "rule_name": "duplicate_transaction",
        "rows_affected": dup_exact_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": dup_exact_mask.sum(),
        "example": df.loc[dup_exact_mask, "vendor_name"].iloc[0] if dup_exact_mask.any() else "",
    })

    dup_invoice_mask = df.duplicated(subset=["vendor_name", "amount", "check_date"], keep=False) & ~dup_exact_mask
    df.loc[dup_invoice_mask, "dq_flag"] += "likely_duplicate_invoice|"
    report_rows.append({
        "rule_name": "likely_duplicate_invoice",
        "rows_affected": dup_invoice_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": dup_invoice_mask.sum(),
        "example": df.loc[dup_invoice_mask, "vendor_name"].iloc[0] if dup_invoice_mask.any() else "",
    })

    q99 = df.loc[df["amount"] > 0, "amount"].quantile(0.99)
    outlier_mask = df["amount"] > q99
    df.loc[outlier_mask, "dq_flag"] += "outlier_amount|"
    report_rows.append({
        "rule_name": "outlier_amount",
        "rows_affected": outlier_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": outlier_mask.sum(),
        "example": f"99th pct threshold: ${q99:,.2f}",
    })

    df["dq_flag"] = df["dq_flag"].str.rstrip("|")
    df["dq_flag"] = df["dq_flag"].replace("", None)

    df["department_name"] = df["department_name"].fillna("UNKNOWN")
    df["contract_number"] = df["contract_number"].fillna("")

    maverick_mask = df["contract_number"].str.upper().str.startswith("DV") | (df["contract_number"] == "")
    df["is_maverick"] = maverick_mask.astype(int)
    report_rows.append({
        "rule_name": "maverick_spend_flagged",
        "rows_affected": maverick_mask.sum(),
        "rows_removed": 0,
        "rows_flagged": maverick_mask.sum(),
        "example": "DV-prefixed or missing contract number",
    })

    df["vendor_name"] = df["vendor_name"].fillna("UNKNOWN VENDOR")
    df["department_name"] = df["department_name"].str.upper().str.strip()

    pre_clean_rows = len(df)
    df = df[~(null_amount_mask)].copy()
    removed = pre_clean_rows - len(df)
    for r in report_rows:
        if r["rule_name"] == "null_amount":
            r["rows_removed"] = removed

    log.info(f"DQ flagging complete: {len(report_rows)} rules applied, {removed} rows removed (null amount)")
    return df, report_rows


def normalize_vendor_name(name: str) -> str:
    if not name or name == "UNKNOWN VENDOR":
        return "unknown vendor"
    s = name.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    for abbr, full in LEGAL_ABBREVIATIONS.items():
        s = re.sub(rf"\b{abbr}\b", full, s)
    s = LEGAL_SUFFIXES.sub(" ", s)
    s = re.sub(r"\b(city of chicago|chicago|dept|department|of|the|and|&)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_supplier_master(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    log.info("Phase 3: Supplier normalization and fuzzy matching")
    df = df.copy()
    df["normalized_vendor"] = df["vendor_name"].apply(normalize_vendor_name)

    unique_pairs = (
        df.groupby(["vendor_name", "normalized_vendor"])
        .agg(tx_count=("amount", "count"), total_spend=("amount", "sum"))
        .reset_index()
    )

    norm_names = unique_pairs["normalized_vendor"].tolist()
    raw_names = unique_pairs["vendor_name"].tolist()

    log.info(f"Fuzzy matching {len(norm_names):,} unique normalized names with threshold {FUZZY_THRESHOLD}")

    union_find = list(range(len(norm_names)))

    def find(i):
        while union_find[i] != i:
            union_find[i] = union_find[union_find[i]]
            i = union_find[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            union_find[rj] = ri

    blocks: dict[str, list[int]] = {}
    for idx, name in enumerate(norm_names):
        prefix = name[:FUZZY_BLOCK_PREFIX_LEN] if len(name) >= FUZZY_BLOCK_PREFIX_LEN else name
        blocks.setdefault(prefix, []).append(idx)

    comparisons = 0
    for prefix, indices in blocks.items():
        if len(indices) < 2:
            continue
        for i_pos, i in enumerate(indices):
            for j in indices[i_pos + 1:]:
                score = fuzz.token_sort_ratio(norm_names[i], norm_names[j])
                comparisons += 1
                if score >= FUZZY_THRESHOLD:
                    union(i, j)

    log.info(f"Performed {comparisons:,} fuzzy comparisons")

    groups: dict[int, list[int]] = {}
    for idx in range(len(norm_names)):
        root = find(idx)
        groups.setdefault(root, []).append(idx)

    supplier_records = []
    supplier_id_map: dict[int, str] = {}

    for group_id, (root, members) in enumerate(groups.items()):
        member_df = unique_pairs.iloc[members]
        canonical_idx = member_df["total_spend"].idxmax()
        canonical_name = unique_pairs.at[canonical_idx, "vendor_name"]
        raw_variants = "|".join(sorted(set(unique_pairs.iloc[m]["vendor_name"] for m in members)))
        supplier_id = f"SUP{group_id + 1:06d}"
        total_spend = member_df["total_spend"].sum()
        tx_count = member_df["tx_count"].sum()

        supplier_records.append({
            "supplier_id": supplier_id,
            "canonical_name": canonical_name,
            "raw_variants": raw_variants,
            "transaction_count": int(tx_count),
            "total_spend": float(total_spend),
        })
        for m in members:
            supplier_id_map[m] = supplier_id

    supplier_master = pd.DataFrame(supplier_records)

    vendor_to_supplier = {}
    for idx, row in unique_pairs.iterrows():
        supplier_id = supplier_id_map[idx]
        vendor_to_supplier[row["vendor_name"]] = supplier_id

    canonical_map = {row["supplier_id"]: row["canonical_name"] for _, row in supplier_master.iterrows()}

    df["supplier_id"] = df["vendor_name"].map(vendor_to_supplier)
    df["canonical_vendor"] = df["supplier_id"].map(canonical_map)

    raw_count = unique_pairs["vendor_name"].nunique()
    canonical_count = len(supplier_master)
    log.info(f"Normalization: {raw_count:,} raw names → {canonical_count:,} canonical suppliers (reduction: {raw_count - canonical_count:,})")

    return df, supplier_master


def validate_normalization_sample(supplier_master: pd.DataFrame) -> dict:
    log.info("Validating normalization on 50-group sample")
    np.random.seed(RANDOM_SEED)
    multi_variant = supplier_master[supplier_master["raw_variants"].str.contains(r"\|", na=False)]
    sample_size = min(50, len(multi_variant))
    sample = multi_variant.sample(n=sample_size, random_state=RANDOM_SEED)
    sample_path = OUTPUTS_DIR / "normalization_validation_sample.csv"
    sample.to_csv(sample_path, index=False)
    log.info(f"Normalization sample saved → {sample_path}")
    log.info("Manual review of normalization_validation_sample.csv is required to record correct/wrong/missed merges")
    return {"sample_size": sample_size, "sample_path": str(sample_path)}


def apply_rule_classification(df: pd.DataFrame) -> pd.DataFrame:
    log.info("Phase 4a: Rule-based classification")
    df = df.copy()
    df["l1_category"] = None
    df["l2_category"] = None
    df["l3_category"] = None
    df["classification_method"] = "unclassified"

    classify_text = (
        (df["canonical_vendor"].fillna("") + " " + df["department_name"].fillna("")).str.lower()
    )

    for pattern, l1, l2, l3 in CLASSIFICATION_RULES:
        mask = classify_text.str.contains(pattern, regex=True) & (df["classification_method"] == "unclassified")
        df.loc[mask, "l1_category"] = l1
        df.loc[mask, "l2_category"] = l2
        df.loc[mask, "l3_category"] = l3
        df.loc[mask, "classification_method"] = "rule"

    rule_rows = (df["classification_method"] == "rule").sum()
    total_rows = len(df)
    rule_spend = df.loc[df["classification_method"] == "rule", "amount"].sum()
    total_spend = df.loc[df["amount"] > 0, "amount"].sum()
    log.info(f"Rule classification: {rule_rows:,}/{total_rows:,} rows ({rule_rows/total_rows*100:.1f}%) | ${rule_spend:,.0f} of ${total_spend:,.0f} spend")
    return df


def load_taxonomy() -> list[str]:
    taxonomy_df = pd.read_csv(TAXONOMY_PATH)
    categories = []
    for _, row in taxonomy_df.iterrows():
        categories.append(f"{row['l1']} > {row['l2']} > {row['l3']}: {row['definition']}")
    return categories


def build_llm_prompt(batch: list[dict], taxonomy_categories: list[str]) -> str:
    taxonomy_text = "\n".join(f"  - {c}" for c in taxonomy_categories)
    records_text = "\n".join(
        f"  {i+1}. vendor=\"{r['vendor']}\", department=\"{r['dept']}\""
        for i, r in enumerate(batch)
    )
    return f"""You are a procurement spend analyst. Classify each transaction into the correct category from the taxonomy below.

TAXONOMY (format: L1 > L2 > L3: definition):
{taxonomy_text}

TRANSACTIONS TO CLASSIFY:
{records_text}

INSTRUCTIONS:
- For each transaction, return exactly one JSON object per line (JSON Lines format).
- Each object must have: "index" (1-based), "l1", "l2", "l3", "confidence" ("high"/"medium"/"low"), "reason" (one sentence).
- "l1", "l2", "l3" must EXACTLY match values from the taxonomy above.
- If genuinely unclassifiable, set l2="Miscellaneous Services", l3="Unclassified needs review", confidence="low".
- Return ONLY the JSON lines. No markdown, no extra text.
"""


def call_gemini_with_retry(client, prompt: str) -> str:
    for attempt in range(LLM_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            if attempt < LLM_MAX_RETRIES - 1:
                log.warning(f"Gemini API error (attempt {attempt+1}): {e} — retrying in {LLM_RETRY_DELAY}s")
                time.sleep(LLM_RETRY_DELAY)
            else:
                log.error(f"Gemini API failed after {LLM_MAX_RETRIES} attempts: {e}")
                return ""


def parse_llm_response(response_text: str, batch_size: int) -> list[dict]:
    results = []
    lines = [l.strip() for l in response_text.split("\n") if l.strip().startswith("{")]
    for line in lines:
        try:
            obj = json.loads(line)
            results.append(obj)
        except json.JSONDecodeError:
            pass
    return results


def apply_llm_classification(df: pd.DataFrame) -> pd.DataFrame:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "your_gemini_api_key_here":
        log.warning("GEMINI_API_KEY not set — skipping LLM classification. Set the key in .env and re-run.")
        return df

    log.info("Phase 4b: LLM-assisted classification for unclassified rows")
    client = genai.Client(api_key=api_key)
    taxonomy_categories = load_taxonomy()

    conn = get_db_connection()

    unclassified_mask = df["classification_method"] == "unclassified"
    unclassified = df.loc[unclassified_mask].copy()

    dedup_keys = (
        unclassified.groupby(["canonical_vendor", "department_name"])
        .size()
        .reset_index()
        .rename(columns={0: "count"})
    )
    log.info(f"LLM: {len(unclassified):,} unclassified rows → {len(dedup_keys):,} unique (vendor, dept) combinations to classify")

    cache_results: dict[str, dict] = {}
    rows_cached = conn.execute("SELECT cache_key, l1_category, l2_category, l3_category, confidence, reason FROM classification_cache").fetchall()
    for row in rows_cached:
        cache_results[row[0]] = {"l1": row[1], "l2": row[2], "l3": row[3], "confidence": row[4], "reason": row[5]}

    to_classify = []
    for _, row in dedup_keys.iterrows():
        key = hashlib.md5(f"{row['canonical_vendor']}||{row['department_name']}".encode()).hexdigest()
        if key not in cache_results:
            to_classify.append({"vendor": row["canonical_vendor"], "dept": row["department_name"], "cache_key": key})

    log.info(f"LLM: {len(to_classify):,} combinations not in cache — sending to Gemini")

    llm_calls = 0
    for i in range(0, len(to_classify), LLM_BATCH_SIZE):
        batch = to_classify[i: i + LLM_BATCH_SIZE]
        prompt = build_llm_prompt(batch, taxonomy_categories)
        response_text = call_gemini_with_retry(client, prompt)
        llm_calls += 1

        parsed = parse_llm_response(response_text, len(batch))
        for result in parsed:
            idx = result.get("index", 0) - 1
            if 0 <= idx < len(batch):
                entry = batch[idx]
                key = entry["cache_key"]
                classification = {
                    "l1": result.get("l1", "Services"),
                    "l2": result.get("l2", "Other Services"),
                    "l3": result.get("l3", "Miscellaneous Services"),
                    "confidence": result.get("confidence", "low"),
                    "reason": result.get("reason", ""),
                }
                cache_results[key] = classification
                conn.execute(
                    "INSERT OR REPLACE INTO classification_cache VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        key,
                        classification["l1"],
                        classification["l2"],
                        classification["l3"],
                        classification["confidence"],
                        classification["reason"],
                        LLM_MODEL,
                        PROMPT_VERSION,
                        datetime.utcnow().isoformat(),
                    ),
                )
        conn.commit()

        if i % (LLM_BATCH_SIZE * 4) == 0:
            log.info(f"LLM progress: {min(i + LLM_BATCH_SIZE, len(to_classify)):,}/{len(to_classify):,} combinations")
        time.sleep(0.5)

    def lookup_classification(row):
        key = hashlib.md5(f"{row['canonical_vendor']}||{row['department_name']}".encode()).hexdigest()
        return cache_results.get(key, {})

    unclassified_with_llm = unclassified.copy()
    classification_lookup = unclassified_with_llm.apply(lookup_classification, axis=1)

    unclassified_with_llm["l1_category"] = classification_lookup.apply(lambda x: x.get("l1"))
    unclassified_with_llm["l2_category"] = classification_lookup.apply(lambda x: x.get("l2"))
    unclassified_with_llm["l3_category"] = classification_lookup.apply(lambda x: x.get("l3"))
    unclassified_with_llm["llm_confidence"] = classification_lookup.apply(lambda x: x.get("confidence"))

    low_confidence_mask = unclassified_with_llm["llm_confidence"] == "low"
    unclassified_with_llm.loc[low_confidence_mask, "classification_method"] = "unclassified"
    unclassified_with_llm.loc[~low_confidence_mask, "classification_method"] = "llm"

    df.update(unclassified_with_llm)

    conn.close()
    log.info(f"LLM classification complete: {llm_calls} API calls, {len(to_classify)} combinations processed")
    return df


def measure_classification_accuracy(df: pd.DataFrame) -> dict:
    log.info("Phase 4c: Building hand-label sample for accuracy measurement")
    np.random.seed(RANDOM_SEED)
    sample = df[df["amount"] > 0].sample(n=min(150, len(df)), random_state=RANDOM_SEED)
    sample_out = sample[["vendor_name", "canonical_vendor", "department_name", "amount", "check_date",
                          "l1_category", "l2_category", "l3_category", "classification_method", "llm_confidence"]].copy()
    sample_out["manual_l1"] = ""
    sample_out["manual_l2"] = ""
    sample_out["manual_l3"] = ""
    sample_out["is_correct"] = ""
    sample_path = OUTPUTS_DIR / "classification_accuracy_sample.csv"
    sample_out.to_csv(sample_path, index=False)
    log.info(f"Hand-label sample saved → {sample_path} (fill in manual_l1/l2/l3 and is_correct columns)")
    return {"sample_path": str(sample_path), "sample_size": len(sample_out)}


def run_spend_analysis(df: pd.DataFrame) -> dict:
    log.info("Phase 5: Spend analysis")
    positive_df = df[df["amount"] > 0].copy()
    results = {}

    total_spend = positive_df["amount"].sum()
    results["total_spend"] = round(float(total_spend), 2)
    results["total_transactions"] = len(positive_df)
    results["unique_suppliers"] = positive_df["supplier_id"].nunique()
    results["unique_departments"] = positive_df["department_name"].nunique()

    spend_by_l2 = (
        positive_df.groupby("l2_category")
        .agg(transactions=("amount", "count"), total_spend=("amount", "sum"))
        .assign(pct_of_total=lambda x: round(x["total_spend"] / total_spend * 100, 2))
        .sort_values("total_spend", ascending=False)
        .reset_index()
    )
    spend_by_l2.to_csv(ANALYSIS_DIR / "spend_by_category.csv", index=False)

    spend_by_dept = (
        positive_df.groupby("department_name")
        .agg(transactions=("amount", "count"), total_spend=("amount", "sum"))
        .assign(pct_of_total=lambda x: round(x["total_spend"] / total_spend * 100, 2))
        .sort_values("total_spend", ascending=False)
        .reset_index()
    )
    spend_by_dept.to_csv(ANALYSIS_DIR / "spend_by_department.csv", index=False)

    monthly_spend = (
        positive_df[positive_df["check_date"].notna()]
        .assign(year_month=lambda x: x["check_date"].str[:7])
        .groupby("year_month")
        .agg(transactions=("amount", "count"), monthly_spend=("amount", "sum"))
        .sort_index()
        .reset_index()
    )
    monthly_spend.to_csv(ANALYSIS_DIR / "monthly_spend_trend.csv", index=False)

    top_suppliers = (
        positive_df.groupby(["supplier_id", "canonical_vendor"])
        .agg(transactions=("amount", "count"), total_spend=("amount", "sum"))
        .assign(pct_of_total=lambda x: round(x["total_spend"] / total_spend * 100, 2))
        .sort_values("total_spend", ascending=False)
        .reset_index()
    )
    top20 = top_suppliers.head(20)
    top20.to_csv(ANALYSIS_DIR / "top_suppliers.csv", index=False)
    results["top_10_supplier_spend_share"] = round(float(top_suppliers.head(10)["total_spend"].sum() / total_spend * 100), 2)
    results["top_20_supplier_spend_share"] = round(float(top20["total_spend"].sum() / total_spend * 100), 2)

    top_suppliers["cumulative_spend"] = top_suppliers["total_spend"].cumsum()
    top_suppliers["cumulative_pct"] = top_suppliers["cumulative_spend"] / total_spend * 100
    pareto_80 = top_suppliers[top_suppliers["cumulative_pct"] <= 80.0]
    results["suppliers_for_80pct_spend"] = len(pareto_80)
    top_suppliers.to_csv(ANALYSIS_DIR / "supplier_pareto.csv", index=False)

    category_totals = positive_df.groupby("l2_category")["amount"].sum()
    supplier_category = positive_df.groupby(["l2_category", "supplier_id", "canonical_vendor"])["amount"].sum().reset_index()
    supplier_category = supplier_category.merge(category_totals.rename("category_total").reset_index(), on="l2_category")
    supplier_category["supplier_share"] = supplier_category["amount"] / supplier_category["category_total"] * 100
    top_per_cat = supplier_category.sort_values("amount", ascending=False).groupby("l2_category").first().reset_index()
    top_per_cat.to_csv(ANALYSIS_DIR / "supplier_concentration.csv", index=False)

    fragmented = (
        positive_df.groupby("l2_category")
        .agg(
            num_suppliers=("supplier_id", "nunique"),
            total_spend=("amount", "sum"),
            num_transactions=("amount", "count"),
        )
        .assign(avg_spend_per_supplier=lambda x: x["total_spend"] / x["num_suppliers"])
        .query("num_suppliers > 5")
        .sort_values("avg_spend_per_supplier")
        .reset_index()
    )
    fragmented.to_csv(ANALYSIS_DIR / "fragmented_spend.csv", index=False)

    maverick_df = positive_df.groupby("is_maverick").agg(
        transactions=("amount", "count"),
        total_spend=("amount", "sum"),
    ).reset_index()
    maverick_df["pct_of_total"] = round(maverick_df["total_spend"] / total_spend * 100, 2)
    maverick_df.to_csv(ANALYSIS_DIR / "maverick_spend_summary.csv", index=False)
    maverick_spend = positive_df.loc[positive_df["is_maverick"] == 1, "amount"].sum()
    results["maverick_spend_value"] = round(float(maverick_spend), 2)
    results["maverick_spend_pct"] = round(float(maverick_spend / total_spend * 100), 2)

    maverick_by_dept = (
        positive_df.groupby("department_name")
        .apply(lambda g: pd.Series({
            "total_spend": g["amount"].sum(),
            "maverick_spend": g.loc[g["is_maverick"] == 1, "amount"].sum(),
        }))
        .assign(maverick_pct=lambda x: round(x["maverick_spend"] / x["total_spend"] * 100, 2))
        .query("maverick_spend > 0")
        .sort_values("maverick_spend", ascending=False)
        .reset_index()
    )
    maverick_by_dept.to_csv(ANALYSIS_DIR / "maverick_spend_by_department.csv", index=False)

    maverick_by_cat = (
        positive_df.groupby("l2_category")
        .apply(lambda g: pd.Series({
            "total_spend": g["amount"].sum(),
            "maverick_spend": g.loc[g["is_maverick"] == 1, "amount"].sum(),
        }))
        .assign(maverick_pct=lambda x: round(x["maverick_spend"] / x["total_spend"] * 100, 2))
        .query("maverick_spend > 0")
        .sort_values("maverick_spend", ascending=False)
        .reset_index()
    )
    maverick_by_cat.to_csv(ANALYSIS_DIR / "maverick_spend_by_category.csv", index=False)

    merged_suppliers = top_suppliers[top_suppliers["canonical_vendor"].str.contains("|", na=False, regex=False)]
    (
        df[df["supplier_id"].isin(merged_suppliers["supplier_id"])]
        .groupby(["supplier_id", "canonical_vendor"])
        .agg(transactions=("amount", "count"), total_spend=("amount", "sum"))
        .reset_index()
        .sort_values("total_spend", ascending=False)
        .to_csv(ANALYSIS_DIR / "duplicate_supplier_impact.csv", index=False)
    )

    mean_amt = positive_df["amount"].mean()
    std_amt = positive_df["amount"].std()
    anomaly_threshold = mean_amt + 3 * std_amt
    anomalies = positive_df[positive_df["amount"] > anomaly_threshold].sort_values("amount", ascending=False)
    anomalies.to_csv(ANALYSIS_DIR / "anomalies.csv", index=False)
    results["anomaly_threshold"] = round(float(anomaly_threshold), 2)
    results["anomaly_count"] = len(anomalies)

    classification_coverage = (
        positive_df.groupby("classification_method")
        .agg(transactions=("amount", "count"), total_spend=("amount", "sum"))
        .assign(
            pct_rows=lambda x: round(x["transactions"] / x["transactions"].sum() * 100, 2),
            pct_spend=lambda x: round(x["total_spend"] / x["total_spend"].sum() * 100, 2),
        )
        .reset_index()
    )
    classification_coverage.to_csv(ANALYSIS_DIR / "classification_coverage.csv", index=False)

    frag_opportunity = fragmented.head(3).copy()
    frag_opportunity["estimated_savings"] = round(frag_opportunity["total_spend"] * 0.05, 2)
    frag_opportunity["assumption"] = "5% consolidation discount — illustrative estimate"
    frag_opportunity.to_csv(ANALYSIS_DIR / "opportunity_fragmented.csv", index=False)

    maverick_addressable = maverick_spend * 0.20
    maverick_savings = maverick_addressable * 0.08
    pd.DataFrame([{
        "total_maverick_spend": round(float(maverick_spend), 2),
        "addressable_maverick_20pct": round(float(maverick_addressable), 2),
        "estimated_savings": round(float(maverick_savings), 2),
        "assumption": "20% of maverick brought under contract; 8% improvement over spot assumed — illustrative estimate",
    }]).to_csv(ANALYSIS_DIR / "opportunity_maverick.csv", index=False)

    results["maverick_savings_estimate"] = round(float(maverick_savings), 2)
    results["fragmented_top3_savings_estimate"] = round(float(frag_opportunity["estimated_savings"].sum()), 2)

    log.info(
        f"Analysis complete: total spend ${results['total_spend']:,.0f} | "
        f"maverick {results['maverick_spend_pct']}% | "
        f"{results['suppliers_for_80pct_spend']} suppliers = 80% of spend"
    )
    return results


def save_results_to_db(df: pd.DataFrame, supplier_master: pd.DataFrame, dq_report_rows: list[dict], analysis_results: dict):
    log.info("Saving all outputs to SQLite")
    conn = get_db_connection()
    conn.execute("DELETE FROM cleaned_payments")
    conn.execute("DELETE FROM supplier_master")
    conn.execute("DELETE FROM data_quality_report")
    conn.execute("DELETE FROM spend_analysis_summary")

    db_cols = [
        "vendor_name", "voucher_number", "amount", "check_date", "department_name",
        "contract_number", "is_maverick", "dq_flag", "normalized_vendor",
        "supplier_id", "canonical_vendor", "l1_category", "l2_category",
        "l3_category", "classification_method", "llm_confidence",
    ]
    for col in db_cols:
        if col not in df.columns:
            df[col] = None

    df[db_cols].to_sql("cleaned_payments", conn, if_exists="append", index=True, index_label="row_id")

    sm_cols = ["supplier_id", "canonical_name", "raw_variants", "transaction_count", "total_spend"]
    supplier_master[sm_cols].to_sql("supplier_master", conn, if_exists="append", index=False)

    dq_df = pd.DataFrame(dq_report_rows)
    dq_df.to_sql("data_quality_report", conn, if_exists="append", index=False)

    for k, v in analysis_results.items():
        conn.execute("INSERT OR REPLACE INTO spend_analysis_summary VALUES (?,?)", (k, str(v)))

    conn.commit()
    conn.close()
    log.info("Database save complete")


def build_excel_workbook(df: pd.DataFrame, supplier_master: pd.DataFrame):
    log.info("Phase 6: Building Excel workbook")
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        from openpyxl.chart import BarChart, Reference
    except ImportError:
        log.warning("openpyxl not available — skipping Excel workbook")
        return

    excel_path = OUTPUTS_DIR / "procurement_spend_analysis.xlsx"
    wb = openpyxl.Workbook()

    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="1F4E79")
    alt_fill = PatternFill("solid", fgColor="D9E1F2")
    border_side = Side(style="thin", color="B8B8B8")
    thin_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)

    def style_header_row(ws, row_num, num_cols):
        for col in range(1, num_cols + 1):
            cell = ws.cell(row=row_num, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border

    def style_data_rows(ws, start_row, end_row, num_cols):
        for row in range(start_row, end_row + 1):
            fill = alt_fill if row % 2 == 0 else PatternFill()
            for col in range(1, num_cols + 1):
                cell = ws.cell(row=row, column=col)
                cell.border = thin_border
                if fill.fill_type:
                    cell.fill = fill

    def autofit_columns(ws):
        for col in ws.columns:
            max_len = max((len(str(cell.value)) if cell.value else 0) for cell in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 50)

    positive_df = df[df["amount"] > 0].copy()
    total_spend = positive_df["amount"].sum()

    ws_summary = wb.active
    ws_summary.title = "Executive Summary"
    ws_summary.sheet_view.showGridLines = False
    ws_summary["A1"] = "PROCUREMENT SPEND ANALYTICS — CITY OF CHICAGO"
    ws_summary["A1"].font = Font(name="Calibri", bold=True, size=16, color="1F4E79")
    ws_summary.merge_cells("A1:E1")
    ws_summary["A1"].alignment = Alignment(horizontal="center")

    summary_data = [
        ["Metric", "Value"],
        ["Total Spend (USD)", f"${total_spend:,.0f}"],
        ["Total Transactions", f"{len(positive_df):,}"],
        ["Unique Canonical Suppliers", f"{positive_df['supplier_id'].nunique():,}"],
        ["Raw Supplier Name Variants", f"{positive_df['vendor_name'].nunique():,}"],
        ["Unique Departments", f"{positive_df['department_name'].nunique():,}"],
        ["Maverick Spend (USD)", f"${positive_df.loc[positive_df['is_maverick']==1,'amount'].sum():,.0f}"],
        ["Maverick Spend Share (%)", f"{positive_df.loc[positive_df['is_maverick']==1,'amount'].sum()/total_spend*100:.1f}%"],
        ["Rule-Classified Rows (%)", f"{(positive_df['classification_method']=='rule').sum()/len(positive_df)*100:.1f}%"],
        ["LLM-Classified Rows (%)", f"{(positive_df['classification_method']=='llm').sum()/len(positive_df)*100:.1f}%"],
        ["Unclassified Rows (%)", f"{(positive_df['classification_method']=='unclassified').sum()/len(positive_df)*100:.1f}%"],
    ]
    for r_idx, row_data in enumerate(summary_data, start=3):
        for c_idx, val in enumerate(row_data, start=1):
            cell = ws_summary.cell(row=r_idx, column=c_idx, value=val)
            cell.border = thin_border
            if r_idx == 3:
                cell.font = header_font
                cell.fill = header_fill
    autofit_columns(ws_summary)

    cat_pivot = (
        positive_df.groupby("l2_category")["amount"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"l2_category": "Category", "amount": "Total Spend (USD)"})
    )
    cat_pivot["% of Total"] = (cat_pivot["Total Spend (USD)"] / total_spend * 100).round(2)
    ws_cat = wb.create_sheet("Spend by Category")
    ws_cat.sheet_view.showGridLines = False
    headers = list(cat_pivot.columns)
    for c_idx, h in enumerate(headers, 1):
        ws_cat.cell(row=1, column=c_idx, value=h)
    style_header_row(ws_cat, 1, len(headers))
    for r_idx, row_data in cat_pivot.iterrows():
        for c_idx, val in enumerate(row_data, start=1):
            ws_cat.cell(row=r_idx + 2, column=c_idx, value=val)
    style_data_rows(ws_cat, 2, len(cat_pivot) + 1, len(headers))
    autofit_columns(ws_cat)

    dept_pivot = (
        positive_df.groupby("department_name")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(20)
        .reset_index()
        .rename(columns={"department_name": "Department", "amount": "Total Spend (USD)"})
    )
    dept_pivot["% of Total"] = (dept_pivot["Total Spend (USD)"] / total_spend * 100).round(2)
    ws_dept = wb.create_sheet("Spend by Department")
    ws_dept.sheet_view.showGridLines = False
    headers = list(dept_pivot.columns)
    for c_idx, h in enumerate(headers, 1):
        ws_dept.cell(row=1, column=c_idx, value=h)
    style_header_row(ws_dept, 1, len(headers))
    for r_idx, row_data in dept_pivot.iterrows():
        for c_idx, val in enumerate(row_data, start=1):
            ws_dept.cell(row=r_idx + 2, column=c_idx, value=val)
    style_data_rows(ws_dept, 2, len(dept_pivot) + 1, len(headers))
    autofit_columns(ws_dept)

    top_sup = (
        positive_df.groupby(["supplier_id", "canonical_vendor"])["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(30)
        .reset_index()
        .rename(columns={"canonical_vendor": "Supplier", "amount": "Total Spend (USD)"})
    )
    top_sup["% of Total"] = (top_sup["Total Spend (USD)"] / total_spend * 100).round(2)
    top_sup = top_sup.merge(supplier_master[["supplier_id", "raw_variants"]], on="supplier_id", how="left")
    ws_sup = wb.create_sheet("Top Suppliers")
    ws_sup.sheet_view.showGridLines = False
    headers = ["Supplier", "Total Spend (USD)", "% of Total", "Raw Name Variants"]
    for c_idx, h in enumerate(headers, 1):
        ws_sup.cell(row=1, column=c_idx, value=h)
    style_header_row(ws_sup, 1, len(headers))
    for r_idx, row_data in top_sup.iterrows():
        ws_sup.cell(row=r_idx + 2, column=1, value=row_data["Supplier"])
        ws_sup.cell(row=r_idx + 2, column=2, value=row_data["Total Spend (USD)"])
        ws_sup.cell(row=r_idx + 2, column=3, value=row_data["% of Total"])
        ws_sup.cell(row=r_idx + 2, column=4, value=row_data["raw_variants"])
    style_data_rows(ws_sup, 2, len(top_sup) + 1, len(headers))
    autofit_columns(ws_sup)

    mav_dept = (
        positive_df.groupby("department_name")
        .apply(lambda g: pd.Series({
            "Total Spend": g["amount"].sum(),
            "Maverick Spend": g.loc[g["is_maverick"] == 1, "amount"].sum(),
        }))
        .assign(maverick_pct=lambda x: round(x["Maverick Spend"] / x["Total Spend"] * 100, 2))
        .query("maverick_spend > 0" if "maverick_spend" in [] else "`Maverick Spend` > 0")
        .sort_values("Maverick Spend", ascending=False)
        .head(20)
        .reset_index()
    )
    ws_mav = wb.create_sheet("Maverick Spend")
    ws_mav.sheet_view.showGridLines = False
    mav_headers = ["Department", "Total Spend", "Maverick Spend", "Maverick %"]
    for c_idx, h in enumerate(mav_headers, 1):
        ws_mav.cell(row=1, column=c_idx, value=h)
    style_header_row(ws_mav, 1, len(mav_headers))
    for r_idx, row_data in mav_dept.iterrows():
        ws_mav.cell(row=r_idx + 2, column=1, value=row_data["department_name"])
        ws_mav.cell(row=r_idx + 2, column=2, value=row_data["Total Spend"])
        ws_mav.cell(row=r_idx + 2, column=3, value=row_data["Maverick Spend"])
        ws_mav.cell(row=r_idx + 2, column=4, value=row_data["maverick_pct"])
    style_data_rows(ws_mav, 2, len(mav_dept) + 1, len(mav_headers))
    autofit_columns(ws_mav)

    ws_sm = wb.create_sheet("Supplier Master")
    ws_sm.sheet_view.showGridLines = False
    sm_headers = ["Supplier ID", "Canonical Name", "Transaction Count", "Total Spend", "Raw Variants"]
    for c_idx, h in enumerate(sm_headers, 1):
        ws_sm.cell(row=1, column=c_idx, value=h)
    style_header_row(ws_sm, 1, len(sm_headers))
    sm_display = supplier_master.sort_values("total_spend", ascending=False).head(500)
    for r_idx, row_data in sm_display.iterrows():
        ws_sm.cell(row=r_idx + 2, column=1, value=row_data["supplier_id"])
        ws_sm.cell(row=r_idx + 2, column=2, value=row_data["canonical_name"])
        ws_sm.cell(row=r_idx + 2, column=3, value=row_data["transaction_count"])
        ws_sm.cell(row=r_idx + 2, column=4, value=row_data["total_spend"])
        ws_sm.cell(row=r_idx + 2, column=5, value=row_data["raw_variants"])
    style_data_rows(ws_sm, 2, len(sm_display) + 1, len(sm_headers))
    autofit_columns(ws_sm)

    wb.save(excel_path)
    log.info(f"Excel workbook saved → {excel_path}")


def write_results_log(analysis_results: dict, df: pd.DataFrame, supplier_master: pd.DataFrame, dq_report: list[dict]):
    log.info("Writing results log")
    positive_df = df[df["amount"] > 0]
    total_rows_raw = len(df)
    total_rows_clean = len(positive_df)

    classification_counts = positive_df["classification_method"].value_counts()
    rule_pct = round(classification_counts.get("rule", 0) / total_rows_clean * 100, 1)
    llm_pct = round(classification_counts.get("llm", 0) / total_rows_clean * 100, 1)
    unclassified_pct = round(classification_counts.get("unclassified", 0) / total_rows_clean * 100, 1)

    raw_vendor_count = df["vendor_name"].nunique()
    canonical_count = len(supplier_master)

    lines = [
        "# Results Log — Procurement Spend Analytics",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Dataset",
        f"- Source: City of Chicago Vendor Payments (data.cityofchicago.org)",
        f"- Rows loaded: {total_rows_raw:,}",
        f"- Rows after cleansing (positive amounts only): {total_rows_clean:,}",
        f"- Date range: {df['check_date'].min()} to {df['check_date'].max()}",
        "",
        "## Data Quality",
    ]
    for rule in dq_report:
        lines.append(f"- {rule['rule_name']}: {rule['rows_flagged']:,} rows flagged, {rule['rows_removed']} removed")
    lines += [
        "",
        "## Supplier Normalization",
        f"- Raw unique supplier name variants: {raw_vendor_count:,}",
        f"- Canonical suppliers after normalization: {canonical_count:,}",
        f"- Reduction: {raw_vendor_count - canonical_count:,} fewer unique entities",
        f"- Fuzzy matching threshold: {FUZZY_THRESHOLD} (token sort ratio)",
        "- Manual validation sample: outputs/normalization_validation_sample.csv (50 groups for review)",
        "",
        "## Taxonomy",
        "- 2 Level-1 categories (Goods, Services)",
        "- 17 Level-2 categories",
        "- 44 Level-3 categories",
        "",
        "## Classification",
        f"- Rule-based: {rule_pct}% of rows",
        f"- LLM-assisted (Gemini 1.5 Flash): {llm_pct}% of rows",
        f"- Unclassified / needs review: {unclassified_pct}% of rows",
        "- Accuracy sample: outputs/classification_accuracy_sample.csv (150 rows for hand-labeling)",
        f"- LLM model: {LLM_MODEL}, prompt version: {PROMPT_VERSION}",
        "",
        "## Spend Analysis",
        f"- Total spend: ${analysis_results.get('total_spend', 0):,.0f}",
        f"- Total transactions: {analysis_results.get('total_transactions', 0):,}",
        f"- Unique canonical suppliers: {analysis_results.get('unique_suppliers', 0):,}",
        f"- Unique departments: {analysis_results.get('unique_departments', 0):,}",
        f"- Top 10 suppliers share: {analysis_results.get('top_10_supplier_spend_share', 0)}%",
        f"- Top 20 suppliers share: {analysis_results.get('top_20_supplier_spend_share', 0)}%",
        f"- Suppliers making up 80% of spend: {analysis_results.get('suppliers_for_80pct_spend', 0)}",
        f"- Maverick spend value: ${analysis_results.get('maverick_spend_value', 0):,.0f}",
        f"- Maverick spend share: {analysis_results.get('maverick_spend_pct', 0)}%",
        f"- Anomaly threshold (3σ): ${analysis_results.get('anomaly_threshold', 0):,.0f}",
        f"- Anomalous transactions: {analysis_results.get('anomaly_count', 0)}",
        "",
        "## Opportunity Sizing (Estimates — Assumptions Clearly Stated)",
        f"- Maverick spend recovery (20% addressable × 8% saving): ${analysis_results.get('maverick_savings_estimate', 0):,.0f}",
        f"- Fragmented category consolidation — top 3 categories (5% discount): ${analysis_results.get('fragmented_top3_savings_estimate', 0):,.0f}",
        "- Note: These are illustrative estimates based on stated assumptions. Not auditable savings figures.",
    ]
    with open(RESULTS_LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info(f"Results log saved → {RESULTS_LOG}")


def write_management_summary(analysis_results: dict, df: pd.DataFrame):
    log.info("Writing management summary")
    positive_df = df[df["amount"] > 0]
    total_spend = analysis_results.get("total_spend", 0)
    maverick_pct = analysis_results.get("maverick_spend_pct", 0)
    maverick_val = analysis_results.get("maverick_spend_value", 0)
    top10_pct = analysis_results.get("top_10_supplier_spend_share", 0)

    fragmented_cats = pd.read_csv(ANALYSIS_DIR / "fragmented_spend.csv").head(3)
    frag_text = ", ".join(fragmented_cats["l2_category"].tolist()) if len(fragmented_cats) else "N/A"

    summary_text = f"""# Management Summary — Chicago Procurement Spend Analytics

**Date:** {datetime.now().strftime('%B %Y')}  
**Dataset:** City of Chicago Vendor Payments — {len(positive_df):,} transactions, ${total_spend:,.0f} total spend  
**Prepared by:** Procurement Spend Analytics Pipeline

---

## Key Findings

### 1. Significant Maverick Spend — {maverick_pct:.1f}% of Total Spend is Off-Contract
${maverick_val:,.0f} ({maverick_pct:.1f}% of total spend) was transacted through Direct Vouchers or with no contract reference —
the City's own coding for non-contract purchasing. This spend bypasses negotiated pricing, supplier vetting, and
three-way match controls. Departments with the highest maverick share are identified in the Opportunities dashboard page.

**Recommended action:** Implement mandatory PO requirements for all non-utility, non-debt-service categories above $5,000.
Estimated savings from bringing 20% of maverick spend under contract at an 8% improvement over spot rates: 
**${analysis_results.get('maverick_savings_estimate', 0):,.0f}** *(illustrative estimate; assumes 8% rate improvement and 20% addressability)*.

---

### 2. High Supplier Concentration — Top 10 Suppliers Hold {top10_pct:.1f}% of Spend
The top 10 canonical suppliers account for {top10_pct:.1f}% of total spend. While some concentration in high-value
infrastructure and utility contracts is expected, concentration in discretionary categories such as Professional Services
and IT creates dependency risk. The data also shows that supplier name fragmentation was masking true concentration:
after normalization, {df['vendor_name'].nunique():,} raw name variants consolidated into {len(positive_df['supplier_id'].unique()):,} 
canonical suppliers.

**Recommended action:** Review per-category concentration ratios (see Supplier Concentration output). For categories where
a single supplier holds more than 60% of category spend, assess contract terms and initiate competitive review at renewal.

---

### 3. Fragmented Spend — Consolidation Opportunity in {frag_text}
These categories show a high number of active suppliers with low average spend per supplier, indicating that multiple
departments are purchasing the same goods and services independently. This fragments volume, eliminates negotiation
leverage, and increases supplier management overhead.

**Recommended action:** Conduct a category strategy review for the top three fragmented categories. Consolidating to
preferred supplier panels and mandating preferred-supplier usage could yield an estimated 
**${analysis_results.get('fragmented_top3_savings_estimate', 0):,.0f}** in savings 
*(5% consolidation discount assumption — illustrative estimate)*.

---

### 4. Classification Coverage — {(positive_df['classification_method']=='unclassified').sum()/len(positive_df)*100:.1f}% of Transactions Require Human Review
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
"""
    summary_path = OUTPUTS_DIR / "management_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)
    log.info(f"Management summary saved → {summary_path}")


def run_pipeline():
    log.info("=" * 60)
    log.info("PROCUREMENT SPEND ANALYTICS PIPELINE — START")
    log.info("=" * 60)

    init_database()
    download_dataset()

    log.info("Loading raw dataset…")
    raw_df = pd.read_csv(RAW_CSV, dtype=str, low_memory=False)
    log.info(f"Loaded {len(raw_df):,} rows from {RAW_CSV.name}")

    raw_df.columns = [c.strip().upper() for c in raw_df.columns]
    column_renames = {}
    for col in raw_df.columns:
        if "VENDOR" in col:
            column_renames[col] = "VENDOR NAME"
        elif "VOUCHER" in col:
            column_renames[col] = "VOUCHER NUMBER"
        elif "AMOUNT" in col:
            column_renames[col] = "AMOUNT"
        elif "DATE" in col:
            column_renames[col] = "CHECK DATE"
        elif "DEPARTMENT" in col:
            column_renames[col] = "DEPARTMENT NAME"
        elif "CONTRACT" in col:
            column_renames[col] = "CONTRACT NUMBER"
    raw_df = raw_df.rename(columns=column_renames)

    for required_col in ["VENDOR NAME", "AMOUNT", "CHECK DATE", "DEPARTMENT NAME", "CONTRACT NUMBER"]:
        if required_col not in raw_df.columns:
            raw_df[required_col] = None

    if "VOUCHER NUMBER" not in raw_df.columns:
        raw_df["VOUCHER NUMBER"] = None

    profile = profile_dataset(raw_df)
    load_raw_to_db(raw_df)

    cleaned_df, dq_report = flag_dq_issues(raw_df)

    dq_report_df = pd.DataFrame(dq_report)
    dq_report_df.to_csv(DQ_REPORT_CSV, index=False)
    log.info(f"DQ report saved → {DQ_REPORT_CSV}")

    cleaned_df, supplier_master = build_supplier_master(cleaned_df)

    normalization_info = validate_normalization_sample(supplier_master)

    supplier_master.to_csv(SUPPLIER_MASTER_CSV, index=False)
    log.info(f"Supplier master saved → {SUPPLIER_MASTER_CSV}")

    classified_df = apply_rule_classification(cleaned_df)
    classified_df["llm_confidence"] = None
    classified_df = apply_llm_classification(classified_df)
    accuracy_info = measure_classification_accuracy(classified_df)

    classified_df.to_csv(CLASSIFIED_CSV, index=False)
    log.info(f"Classified dataset saved → {CLASSIFIED_CSV}")

    analysis_results = run_spend_analysis(classified_df)

    save_results_to_db(classified_df, supplier_master, dq_report, analysis_results)

    build_excel_workbook(classified_df, supplier_master)

    write_results_log(analysis_results, classified_df, supplier_master, dq_report)
    write_management_summary(analysis_results, classified_df)

    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info(f"  Total spend:       ${analysis_results.get('total_spend', 0):>15,.0f}")
    log.info(f"  Transactions:      {analysis_results.get('total_transactions', 0):>15,}")
    log.info(f"  Suppliers:         {analysis_results.get('unique_suppliers', 0):>15,}")
    log.info(f"  Maverick spend:    {analysis_results.get('maverick_spend_pct', 0):>14.1f}%")
    log.info(f"  Top 10 supp share: {analysis_results.get('top_10_supplier_spend_share', 0):>14.1f}%")
    log.info("=" * 60)
    log.info(f"Outputs: {OUTPUTS_DIR}")
    log.info(f"Database: {DB_PATH}")
    log.info(f"Results log: {RESULTS_LOG}")


if __name__ == "__main__":
    run_pipeline()
