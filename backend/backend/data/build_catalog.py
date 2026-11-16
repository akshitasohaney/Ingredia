"""Build Ingredia's searchable catalogue from the research files in ``uploads``.

The import is deliberately conservative: a California Safe Cosmetics report means
that a chemical was reported in a product; it does *not* establish that a product
is unsafe.  The source-specific details are retained in auxiliary tables so the
API can provide provenance instead of flattening away important context.

Run from the repository root:
    python data/build_catalog.py
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "uploads"
DB_PATH = UPLOADS / "ingredia.db"
REPORT_PATH = ROOT / "data" / "eda_report.json"


def text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    value = str(value).strip()
    return value or None


def key(value: object) -> str:
    """Stable search key that preserves letters, digits and INCI punctuation."""
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def clean_name(value: object) -> str | None:
    value = text(value)
    if not value or key(value) in {"", "may contain", "unknown", "nan", "none"}:
        return None
    return value[:256]


def split_ingredients(raw: object) -> list[str]:
    raw = text(raw)
    if not raw:
        return []
    raw = re.sub(r"\bmay contain\b.*", "", raw, flags=re.I)
    parts = re.split(r"[,;\n]|\s{2,}", raw)
    return [name for part in parts if (name := clean_name(part))]


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS catalog_sources (
            source TEXT PRIMARY KEY, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            row_count INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ingredient_regulations (
            id INTEGER PRIMARY KEY, ingredient_id INTEGER NOT NULL,
            jurisdiction TEXT, list_ref TEXT, status TEXT, product_type TEXT,
            max_concentration TEXT, condition_text TEXT, source_url TEXT,
            UNIQUE(ingredient_id, jurisdiction, list_ref, status, product_type),
            FOREIGN KEY(ingredient_id) REFERENCES ingredients(id)
        );
        CREATE TABLE IF NOT EXISTS product_chemical_reports (
            id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, source_record_id TEXT NOT NULL,
            chemical_name TEXT NOT NULL, cas_number TEXT, category TEXT, subcategory TEXT,
            reported_date TEXT, discontinued_date TEXT,
            UNIQUE(source_record_id, chemical_name),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS research_articles (
            pmid TEXT PRIMARY KEY, title TEXT, abstract TEXT, url TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_products_name_brand ON products(name, brand);
        CREATE INDEX IF NOT EXISTS ix_product_chemicals_product ON product_chemical_reports(product_id);
        CREATE INDEX IF NOT EXISTS ix_ingredient_regulations_ingredient ON ingredient_regulations(ingredient_id);
        """
    )


def existing_lookup(conn: sqlite3.Connection, table: str) -> dict[str, int]:
    return {key(name): ident for ident, name in conn.execute(f"SELECT id, name FROM {table}") if key(name)}


def get_ingredient(conn: sqlite3.Connection, lookup: dict[str, int], name: str,
                   *, function: str | None = None, aliases: str | None = None,
                   is_fragrance: int = 0, is_allergen: int = 0,
                   caution: str | None = None) -> int:
    normalized = key(name)
    if not normalized:
        raise ValueError("Ingredient name is empty")
    ingredient_id = lookup.get(normalized)
    if ingredient_id:
        conn.execute(
            "UPDATE ingredients SET function=COALESCE(function, ?), aliases=COALESCE(aliases, ?), "
            "is_fragrance=MAX(is_fragrance, ?), is_allergen=MAX(is_allergen, ?), caution_for=COALESCE(caution_for, ?) WHERE id=?",
            (function, aliases, is_fragrance, is_allergen, caution, ingredient_id),
        )
        return ingredient_id
    cur = conn.execute(
        "INSERT INTO ingredients (name, inci_name, aliases, function, description, evidence_summary, evidence_source, confidence_score, suitable_for, caution_for, is_fragrance, is_allergen) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, name, aliases, function, "Imported cosmetic-ingredient record.",
         "See linked source records; presence alone does not determine safety.",
         "Ingredia integrated research catalogue", 0.65, None, caution, is_fragrance, is_allergen),
    )
    lookup[normalized] = cur.lastrowid
    return cur.lastrowid


def get_product(conn: sqlite3.Connection, lookup: dict[str, int], name: str,
                brand: str | None, product_type: str | None, notes: str | None) -> int:
    product_key = key(f"{brand or ''} {name}")
    product_id = lookup.get(product_key)
    if product_id:
        return product_id
    cur = conn.execute(
        "INSERT INTO products (name, brand, product_type, intended_use, notes) VALUES (?, ?, ?, ?, ?)",
        (name[:256], brand[:128] if brand else None,
         product_type[:128] if product_type else None, product_type, notes),
    )
    lookup[product_key] = cur.lastrowid
    return cur.lastrowid


def link(conn: sqlite3.Connection, product_id: int, ingredient_id: int, position: int, raw_name: str) -> None:
    exists = conn.execute(
        "SELECT 1 FROM product_ingredients WHERE product_id=? AND ingredient_id=? AND raw_name=?",
        (product_id, ingredient_id, raw_name),
    ).fetchone()
    if not exists:
        conn.execute("INSERT INTO product_ingredients (product_id, ingredient_id, position, raw_name) VALUES (?, ?, ?, ?)",
                     (product_id, ingredient_id, position, raw_name[:256]))


def import_catalog() -> dict[str, int]:
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    ingredients = existing_lookup(conn, "ingredients")
    products = {key(f"{brand or ''} {name}"): ident for ident, name, brand in conn.execute("SELECT id, name, brand FROM products")}
    counts: Counter[str] = Counter()

    # CureSkin is the richest ingredient-level source and provides the primary flags.
    cureskin = pd.read_csv(UPLOADS / "cureskin_ingredient_flags.csv")
    for row in cureskin.itertuples(index=False):
        name = clean_name(row.display_name) or clean_name(row.inci_name)
        if not name:
            continue
        flags = []
        if getattr(row, "fa_trigger", 0) == 1: flags.append("fungal-acne trigger")
        if getattr(row, "pregnancy_caution", 0) == 1: flags.append("pregnancy caution")
        if text(getattr(row, "alcohol_type", None)): flags.append(f"alcohol: {row.alcohol_type}")
        get_ingredient(conn, ingredients, name, function=text(row.function), aliases=text(row.inci_name),
                       is_fragrance=int(getattr(row, "fragrance", 0) == 1),
                       is_allergen=int(getattr(row, "eu_allergen", 0) == 1),
                       caution=", ".join(flags) or None)
        counts["cureskin_ingredients"] += 1

    # INCIDB contains regulatory and formulation context. Ignore parser-residual names.
    inci = pd.read_parquet(UPLOADS / "incidb" / "ingredients.parquet")
    inci_ids: dict[int, int] = {}
    for row in inci.itertuples(index=False):
        name = clean_name(row.inci_name)
        if not name or name.startswith("("):
            continue
        inci_ids[int(row.ingredient_id)] = get_ingredient(
            conn, ingredients, name, function=text(row.functions), aliases=text(row.cas_number),
            is_allergen=int(getattr(row, "is_common_allergen", 0) == 1),
            caution="fungal-acne trigger" if getattr(row, "is_fungal_acne_trigger", 0) == 1 else None,
        )
        counts["incidb_ingredients"] += 1

    regulations = pd.read_parquet(UPLOADS / "incidb" / "regulatory_status.parquet")
    for row in regulations.itertuples(index=False):
        ingredient_id = inci_ids.get(int(row.ingredient_id))
        if not ingredient_id:
            name = clean_name(row.inci_name)
            if not name: continue
            ingredient_id = get_ingredient(conn, ingredients, name, aliases=text(row.cas))
        conn.execute("INSERT OR IGNORE INTO ingredient_regulations (ingredient_id,jurisdiction,list_ref,status,product_type,max_concentration,condition_text,source_url) VALUES (?,?,?,?,?,?,?,?)",
                     (ingredient_id, text(row.jurisdiction), text(row.list_ref), text(row.status), text(row.product_type), text(row.max_concentration), text(row.condition_text), text(row.source_url)))
        counts["regulatory_records"] += 1

    brands = pd.read_parquet(UPLOADS / "incidb" / "brands.parquet").set_index("brand_id")["name"].to_dict()
    inci_products = pd.read_parquet(UPLOADS / "incidb" / "products.parquet")
    for row in inci_products.itertuples(index=False):
        name = clean_name(row.name)
        if not name: continue
        product_id = get_product(conn, products, name, text(brands.get(row.brand_id)), text(row.obf_categories_tags), "INCIDB")
        for position, raw in enumerate(split_ingredients(row.raw_ingredient_text), 1):
            link(conn, product_id, get_ingredient(conn, ingredients, raw), position, raw)
        counts["incidb_products"] += 1

    obf = pd.read_csv(UPLOADS / "open_beauty_facts_products.csv", dtype={"code": str})
    for row in obf.itertuples(index=False):
        name = clean_name(row.product_name)
        if not name: continue
        product_id = get_product(conn, products, name, text(row.brands), text(row.categories), f"Open Beauty Facts barcode: {row.code}")
        raw_ingredients = text(row.ingredients_text) or (text(row.ingredients_tags) or "").replace("en:", "")
        for position, raw in enumerate(split_ingredients(raw_ingredients), 1):
            link(conn, product_id, get_ingredient(conn, ingredients, raw), position, raw)
        counts["open_beauty_products"] += 1

    # Stream the large California file. Each row remains a report with its dates/category.
    for chunk in pd.read_csv(UPLOADS / "california_chemicals_in_cosmetics.csv", chunksize=10_000, low_memory=False):
        for row in chunk.itertuples(index=False):
            name, chemical = clean_name(row.ProductName), clean_name(row.ChemicalName)
            if not name or not chemical: continue
            product_id = get_product(conn, products, name, text(row.BrandName), text(row.PrimaryCategory), "California Safe Cosmetics Program report")
            ingredient_id = get_ingredient(conn, ingredients, chemical, aliases=text(row.CasNumber))
            link(conn, product_id, ingredient_id, 9999, chemical)
            conn.execute("INSERT OR IGNORE INTO product_chemical_reports (product_id,source_record_id,chemical_name,cas_number,category,subcategory,reported_date,discontinued_date) VALUES (?,?,?,?,?,?,?,?)",
                         (product_id, str(row.CDPHId), chemical, text(row.CasNumber), text(row.PrimaryCategory), text(row.SubCategory), text(row.MostRecentDateReported), text(row.DiscontinuedDate)))
            counts["california_reports"] += 1

    research = pd.read_csv(UPLOADS / "pubmed_ingredient_research.csv")
    for row in research.itertuples(index=False):
        conn.execute("INSERT OR REPLACE INTO research_articles (pmid,title,abstract,url) VALUES (?,?,?,?)",
                     (str(row.pmid), text(row.title), text(row.abstract), text(row.url)))
        counts["pubmed_articles"] += 1

    source_rows = {"cureskin": len(cureskin), "incidb_products": len(inci_products), "open_beauty_facts": len(obf), "california": counts["california_reports"], "pubmed": len(research)}
    for source, row_count in source_rows.items():
        conn.execute("INSERT OR REPLACE INTO catalog_sources (source, row_count) VALUES (?, ?)", (source, row_count))
    conn.commit()
    report = {
        "source_rows": source_rows, "imported_rows": dict(counts),
        "catalog": {
            "ingredients": conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0],
            "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "product_ingredient_links": conn.execute("SELECT COUNT(*) FROM product_ingredients").fetchone()[0],
            "california_reports": conn.execute("SELECT COUNT(*) FROM product_chemical_reports").fetchone()[0],
            "regulatory_records": conn.execute("SELECT COUNT(*) FROM ingredient_regulations").fetchone()[0],
        },
    }
    conn.close()
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(import_catalog(), indent=2))
