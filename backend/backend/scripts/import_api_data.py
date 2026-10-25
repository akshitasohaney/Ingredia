#!/usr/bin/env python
"""Import API-ready CSV files into the Ingredia backend.

Expected files in the uploads directory (backend/uploads/):
    api_ingredients.csv
    api_ingredient_aliases.csv
    api_products.csv
    api_product_ingredients.csv

Real CSV column mapping (from actual file inspection):
  api_ingredients.csv:
      ingredient_id, inci_name, cosing_matched, cosing_ref_no, cas_number,
      ec_number, functions, chemical_description, cosing_restriction,
      cosing_update_date, annex_ii, annex_iii, annex_iv, annex_v, annex_vi,
      is_common_allergen, allergen_source, comedogenic_rating,
      is_fungal_acne_trigger, rating_source

  api_ingredient_aliases.csv:
      raw_name, canonical_name, method, confidence, ingredient_id,
      part_index, split_rule

  api_products.csv:
      product_id, brand_id, barcode_ean, name, obf_categories_tags,
      raw_ingredient_text, created_at

  api_product_ingredients.csv:
      product_id, ingredient_id, position_index, concentration_percentage

The script:
  * Checks which files exist and reports missing ones.
  * Maps inci_name -> Ingredient.canonical_name.
  * Maps functions -> function_tags (pipe/comma delimited).
  * Stores annex_ii..annex_vi as extra_data["annex_flags"] (all non-null flags).
  * Preserves cosing_*, chemical_description, allergen/comedogenic fields in extra_data.
  * Maintains a deterministic source_id->local_id mapping for FK resolution.
  * Resolves aliases via ingredient_id (not name lookup).
  * Handles blank canonical names as validation failures (skipped with reason).
  * Parses concentration_percentage safely: missing/invalid -> None, never 0.
  * Reports per-file: source_rows, inserted, updated, unchanged, skipped,
    rejected (with row number + reason), failed counts.
  * Wraps each file's inserts in a single transaction with rollback on error.
  * Running twice produces zero inserted/updated on second pass (idempotent).
"""

import csv
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

# Ensure the backend package is importable when run from the repository root
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.ingredient import Ingredient, IngredientAlias  # noqa: E402
from app.models.product import Product, ProductIngredient  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Columns handled by dedicated model fields for Ingredient
_INGREDIENT_MAPPED_COLS = {
    "ingredient_id",
    "inci_name",
    "cas_number",
    "ec_number",
    "functions",
}

# All annex columns – collected into extra_data["annex_flags"]
_ANNEX_COLS = {"annex_ii", "annex_iii", "annex_iv", "annex_v", "annex_vi"}

# Columns that go into extra_data["cosing"]
_COSING_COLS = {
    "cosing_matched",
    "cosing_ref_no",
    "cosing_restriction",
    "cosing_update_date",
}

# Columns that go into extra_data["allergen_info"]
_ALLERGEN_COLS = {
    "is_common_allergen",
    "allergen_source",
    "comedogenic_rating",
    "is_fungal_acne_trigger",
    "rating_source",
}

# Columns handled by dedicated model fields for Product
_PRODUCT_MAPPED_COLS = {
    "product_id",
    "name",
    "barcode_ean",
}

# Columns handled by dedicated model fields for ProductIngredient
_PI_MAPPED_COLS = {
    "product_id",
    "ingredient_id",
    "position_index",
    "concentration_percentage",
}

# Columns handled by dedicated model fields for IngredientAlias
_ALIAS_MAPPED_COLS = {
    "raw_name",
    "canonical_name",
    "method",
    "confidence",
    "ingredient_id",
    "part_index",
    "split_rule",
}

# ---------------------------------------------------------------------------
# Per-file report structure
# ---------------------------------------------------------------------------

def _new_file_report(filename: str) -> dict[str, Any]:
    return {
        "file": filename,
        "source_rows": 0,
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "rejected": [],   # list of {"row": int, "reason": str}
        "failed": 0,
    }


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _opt_str(v: str) -> str | None:
    """Strip whitespace; return None for empty strings."""
    v = v.strip()
    return v if v else None


def _opt_float_safe(v: str, row_num: int) -> tuple[float | None, str | None]:
    """
    Parse a float safely.
    Returns (value, error_reason).
    Missing/empty -> (None, None).
    Invalid non-empty -> (None, "<reason>").
    Never returns 0 for missing values.
    """
    v = v.strip()
    if not v:
        return None, None
    try:
        return float(v), None
    except ValueError:
        return None, f"row {row_num}: invalid float {v!r}"


def _parse_function_tags(raw: str) -> list[str] | None:
    """
    Parse the 'functions' column into a list of tags.

    Handles:
    - JSON list: '["emollient", "humectant"]'
    - Pipe-separated: 'Emollient|Humectant'
    - Comma-separated: 'Emollient, Humectant'
    - Single value: 'Emollient'
    """
    raw = raw.strip()
    if not raw:
        return None
    # JSON list
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(t).strip() for t in parsed if str(t).strip()]
        except json.JSONDecodeError:
            pass
    # Pipe-separated (primary delimiter in real data)
    if "|" in raw:
        return [t.strip() for t in raw.split("|") if t.strip()]
    # Comma-separated
    return [t.strip() for t in raw.split(",") if t.strip()]


def _collect_annex_flags(row: dict[str, str]) -> list[str]:
    """
    Return a list of every annex column that has a non-empty value.
    Preserves all flags (annex_ii through annex_vi).
    """
    flags = []
    for col in sorted(_ANNEX_COLS):
        val = _opt_str(row.get(col, ""))
        if val:
            flags.append(col)  # e.g. "annex_ii"
    return flags


def _collect_cosing(row: dict[str, str]) -> dict[str, str]:
    """Return non-empty cosing_* fields as a dict."""
    result: dict[str, str] = {}
    for col in _COSING_COLS:
        val = _opt_str(row.get(col, ""))
        if val is not None:
            result[col] = val
    return result


def _collect_allergen_info(row: dict[str, str]) -> dict[str, str]:
    """Return non-empty allergen/comedogenic fields as a dict."""
    result: dict[str, str] = {}
    for col in _ALLERGEN_COLS:
        val = _opt_str(row.get(col, ""))
        if val is not None:
            result[col] = val
    return result


# ---------------------------------------------------------------------------
# Per-entity import functions
# ---------------------------------------------------------------------------

def _import_ingredients(
    path: Path,
    session: Session,
) -> tuple[dict[str, Any], dict[str, int]]:
    """
    Import api_ingredients.csv.

    Returns:
        (report, source_id_to_local_id)
        source_id_to_local_id maps the CSV 'ingredient_id' string to
        the local DB primary key.
    """
    report = _new_file_report(path.name)
    source_id_map: dict[str, int] = {}  # csv ingredient_id -> local DB id

    with path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row_num, row in enumerate(rdr, start=2):  # row 1 = header
            report["source_rows"] += 1
            source_id = _opt_str(row.get("ingredient_id", ""))
            canonical = _opt_str(row.get("inci_name", ""))

            # Validate: blank canonical name is a hard skip
            if not canonical:
                report["skipped"] += 1
                report["rejected"].append({
                    "row": row_num,
                    "reason": f"blank inci_name (source ingredient_id={source_id!r})",
                })
                continue

            # Build extra_data
            extra: dict[str, Any] = {}

            if source_id:
                extra["source_id"] = source_id

            cosing = _collect_cosing(row)
            if cosing:
                extra["cosing"] = cosing

            chem_desc = _opt_str(row.get("chemical_description", ""))
            if chem_desc:
                extra["chemical_description"] = chem_desc

            annex_flags = _collect_annex_flags(row)
            if annex_flags:
                extra["annex_flags"] = annex_flags

            allergen_info = _collect_allergen_info(row)
            if allergen_info:
                extra["allergen_info"] = allergen_info

            function_tags = _parse_function_tags(row.get("functions", ""))
            # Store as JSON string (model field is Text)
            function_tags_json = json.dumps(function_tags) if function_tags else None

            # Check for existing record by canonical_name (unique constraint)
            existing = (
                session.query(Ingredient)
                .filter(Ingredient.canonical_name == canonical)
                .first()
            )

            if existing:
                # Update if anything changed
                changed = False
                if existing.cas_number != _opt_str(row.get("cas_number", "")):
                    existing.cas_number = _opt_str(row.get("cas_number", ""))
                    changed = True
                if existing.ec_number != _opt_str(row.get("ec_number", "")):
                    existing.ec_number = _opt_str(row.get("ec_number", ""))
                    changed = True
                if existing.function_tags != function_tags_json:
                    existing.function_tags = function_tags_json
                    changed = True
                # Merge extra_data (preserve existing keys not in new data)
                merged_extra = dict(existing.extra_data or {})
                merged_extra.update(extra)
                if merged_extra != (existing.extra_data or {}):
                    existing.extra_data = merged_extra
                    changed = True

                if changed:
                    report["updated"] += 1
                else:
                    report["unchanged"] += 1

                if source_id:
                    source_id_map[source_id] = existing.id
            else:
                ingredient = Ingredient(
                    canonical_name=canonical,
                    cas_number=_opt_str(row.get("cas_number", "")),
                    ec_number=_opt_str(row.get("ec_number", "")),
                    function_tags=function_tags_json,
                    extra_data=extra if extra else None,
                )
                session.add(ingredient)
                session.flush()  # get the auto-generated id
                if source_id:
                    source_id_map[source_id] = ingredient.id
                report["inserted"] += 1

    return report, source_id_map


def _import_aliases(
    path: Path,
    session: Session,
    source_id_map: dict[str, int],
) -> dict[str, Any]:
    """Import api_ingredient_aliases.csv, resolving via source ingredient_id."""
    report = _new_file_report(path.name)

    with path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row_num, row in enumerate(rdr, start=2):
            report["source_rows"] += 1
            raw_name = _opt_str(row.get("raw_name", ""))
            source_id = _opt_str(row.get("ingredient_id", ""))

            if not raw_name:
                report["skipped"] += 1
                report["rejected"].append({
                    "row": row_num,
                    "reason": "blank raw_name",
                })
                continue

            # Resolve ingredient via source_id map (deterministic, no ambiguous name lookup)
            if not source_id:
                report["rejected"].append({
                    "row": row_num,
                    "reason": f"missing ingredient_id for alias {raw_name!r}",
                })
                continue

            local_ingredient_id = source_id_map.get(source_id)
            if local_ingredient_id is None:
                report["rejected"].append({
                    "row": row_num,
                    "reason": (
                        f"ingredient_id={source_id!r} not found in source_id_map "
                        f"(ingredient may have been skipped) for alias {raw_name!r}"
                    ),
                })
                continue

            # Check for existing alias to ensure idempotency
            existing = (
                session.query(IngredientAlias)
                .filter(
                    IngredientAlias.ingredient_id == local_ingredient_id,
                    IngredientAlias.alias == raw_name,
                )
                .first()
            )
            if existing:
                report["unchanged"] += 1
                continue

            # Build extra_data from unmapped columns
            extra: dict[str, Any] = {}
            for col, val in row.items():
                if col not in _ALIAS_MAPPED_COLS:
                    v = _opt_str(val)
                    if v is not None:
                        extra[col] = v
            # Also preserve mapped metadata not in dedicated fields
            for col in ("canonical_name", "part_index", "split_rule"):
                v = _opt_str(row.get(col, ""))
                if v:
                    extra[col] = v

            method = _opt_str(row.get("method", "")) or "common"
            confidence_raw = row.get("confidence", "").strip()
            confidence: float | None = None
            if confidence_raw:
                try:
                    confidence = float(confidence_raw)
                except ValueError:
                    pass

            alias_obj = IngredientAlias(
                ingredient_id=local_ingredient_id,
                alias=raw_name,
                alias_type=method,  # use 'method' as alias_type
                extra_data={**extra, "confidence": confidence} if confidence is not None else (extra or None),
            )
            session.add(alias_obj)
            report["inserted"] += 1

    return report


def _import_products(
    path: Path,
    session: Session,
) -> tuple[dict[str, Any], dict[str, int]]:
    """
    Import api_products.csv.

    Returns:
        (report, source_product_id_to_local_id)
    """
    report = _new_file_report(path.name)
    product_source_map: dict[str, int] = {}

    with path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row_num, row in enumerate(rdr, start=2):
            report["source_rows"] += 1
            name = _opt_str(row.get("name", ""))
            source_product_id = _opt_str(row.get("product_id", ""))

            if not name:
                report["skipped"] += 1
                report["rejected"].append({
                    "row": row_num,
                    "reason": f"blank name (source product_id={source_product_id!r})",
                })
                continue

            barcode = _opt_str(row.get("barcode_ean", ""))

            # Build extra_data: preserve all unmapped/extra columns
            extra: dict[str, Any] = {}
            if source_product_id:
                extra["source_id"] = source_product_id
            for col, val in row.items():
                if col not in _PRODUCT_MAPPED_COLS:
                    v = _opt_str(val)
                    if v is not None:
                        extra[col] = v

            # Idempotency: look up by barcode if present, else by source_id in extra_data
            existing: Product | None = None
            if barcode:
                existing = (
                    session.query(Product)
                    .filter(Product.barcode == barcode)
                    .first()
                )
            if existing is None and source_product_id:
                # Fallback: look for a product with matching source_id in extra_data
                # This is a linear scan but acceptable for small datasets
                existing = (
                    session.query(Product)
                    .filter(Product.extra_data["source_id"].as_string() == source_product_id)
                    .first()
                )

            if existing:
                changed = False
                if existing.name != name:
                    existing.name = name
                    changed = True
                if barcode and existing.barcode != barcode:
                    existing.barcode = barcode
                    changed = True
                merged_extra = dict(existing.extra_data or {})
                merged_extra.update(extra)
                if merged_extra != (existing.extra_data or {}):
                    existing.extra_data = merged_extra
                    changed = True
                if changed:
                    report["updated"] += 1
                else:
                    report["unchanged"] += 1
                if source_product_id:
                    product_source_map[source_product_id] = existing.id
            else:
                product = Product(
                    name=name,
                    barcode=barcode,
                    extra_data=extra if extra else None,
                )
                session.add(product)
                session.flush()
                if source_product_id:
                    product_source_map[source_product_id] = product.id
                report["inserted"] += 1

    return report, product_source_map


def _import_product_ingredients(
    path: Path,
    session: Session,
    product_source_map: dict[str, int],
    ingredient_source_map: dict[str, int],
) -> dict[str, Any]:
    """Import api_product_ingredients.csv."""
    report = _new_file_report(path.name)

    with path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row_num, row in enumerate(rdr, start=2):
            report["source_rows"] += 1
            source_product_id = _opt_str(row.get("product_id", ""))
            source_ingredient_id = _opt_str(row.get("ingredient_id", ""))
            position_raw = _opt_str(row.get("position_index", ""))

            if not source_product_id:
                report["rejected"].append({
                    "row": row_num,
                    "reason": "missing product_id",
                })
                continue

            local_product_id = product_source_map.get(source_product_id)
            if local_product_id is None:
                report["rejected"].append({
                    "row": row_num,
                    "reason": f"source product_id={source_product_id!r} not in product map",
                })
                continue

            # ingredient_id is nullable in the model
            local_ingredient_id: int | None = None
            if source_ingredient_id:
                local_ingredient_id = ingredient_source_map.get(source_ingredient_id)
                if local_ingredient_id is None:
                    # Not an error — ingredient may have been skipped (e.g. blank name)
                    # Store with NULL ingredient_id and note in extra_data
                    pass  # local_ingredient_id stays None

            # Parse position
            try:
                position = int(position_raw) if position_raw else 0
            except ValueError:
                position = 0

            # Parse concentration_percentage safely — never coerce missing to 0
            conc_raw = row.get("concentration_percentage", "").strip()
            concentration: float | None = None
            if conc_raw:
                try:
                    concentration = float(conc_raw)
                except ValueError:
                    report["rejected"].append({
                        "row": row_num,
                        "reason": f"invalid concentration_percentage {conc_raw!r}",
                    })
                    # Do NOT skip the row — insert with NULL concentration

            # Idempotency: check if this link already exists
            existing_pi = (
                session.query(ProductIngredient)
                .filter(
                    ProductIngredient.product_id == local_product_id,
                    ProductIngredient.position == position,
                )
                .first()
            )
            if existing_pi:
                report["unchanged"] += 1
                continue

            # Build extra_data
            extra: dict[str, Any] = {}
            if source_ingredient_id and local_ingredient_id is None:
                extra["unresolved_source_ingredient_id"] = source_ingredient_id
            if concentration is not None:
                extra["concentration_percentage"] = concentration
            for col, val in row.items():
                if col not in _PI_MAPPED_COLS:
                    v = _opt_str(val)
                    if v is not None:
                        extra[col] = v

            pi = ProductIngredient(
                product_id=local_product_id,
                ingredient_id=local_ingredient_id,
                raw_name="",  # not in this CSV; model requires non-null
                position=position,
                match_method=None,
                match_confidence=None,
                extra_data=extra if extra else None,
            )
            session.add(pi)
            report["inserted"] += 1

    return report


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_import(
    uploads_dir: Path | str | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """
    Import the four API CSV files.

    Parameters
    ----------
    uploads_dir:
        Directory containing the four CSV files.
        Defaults to settings.uploads_dir.
    db:
        Optional external Session.  When provided the caller is responsible
        for commit/rollback.  When None, the function manages its own session.

    Returns
    -------
    A dict with keys:
        "files": list of per-file report dicts
        "missing_files": list of missing CSV filenames
        "total_inserted", "total_updated", "total_unchanged",
        "total_skipped", "total_rejected", "total_failed"
    """
    settings = get_settings()
    uploads_dir = Path(uploads_dir) if uploads_dir else settings.uploads_dir

    required = {
        "ingredients": uploads_dir / "api_ingredients.csv",
        "aliases": uploads_dir / "api_ingredient_aliases.csv",
        "products": uploads_dir / "api_products.csv",
        "product_ingredients": uploads_dir / "api_product_ingredients.csv",
    }
    missing = [name for name, p in required.items() if not p.is_file()]

    summary: dict[str, Any] = {
        "files": [],
        "missing_files": missing,
        "total_inserted": 0,
        "total_updated": 0,
        "total_unchanged": 0,
        "total_skipped": 0,
        "total_rejected": 0,
        "total_failed": 0,
    }

    if missing:
        return summary

    external_session = db is not None
    session = db if external_session else SessionLocal()

    try:
        # 1. Ingredients
        ingr_report, source_id_map = _import_ingredients(
            required["ingredients"], session
        )
        summary["files"].append(ingr_report)

        # 2. Aliases (depends on ingredient source_id_map)
        alias_report = _import_aliases(
            required["aliases"], session, source_id_map
        )
        summary["files"].append(alias_report)

        # 3. Products
        prod_report, product_source_map = _import_products(
            required["products"], session
        )
        summary["files"].append(prod_report)

        # 4. Product-ingredient links
        pi_report = _import_product_ingredients(
            required["product_ingredients"],
            session,
            product_source_map,
            source_id_map,
        )
        summary["files"].append(pi_report)

        if not external_session:
            session.commit()

    except Exception:
        if not external_session:
            session.rollback()
        summary["total_failed"] += 1
        raise
    finally:
        if not external_session:
            session.close()

    # Aggregate totals
    for frep in summary["files"]:
        summary["total_inserted"] += frep["inserted"]
        summary["total_updated"] += frep["updated"]
        summary["total_unchanged"] += frep["unchanged"]
        summary["total_skipped"] += frep["skipped"]
        summary["total_rejected"] += len(frep["rejected"])

    return summary


if __name__ == "__main__":
    result = run_import()
    print(json.dumps(result, indent=2))
