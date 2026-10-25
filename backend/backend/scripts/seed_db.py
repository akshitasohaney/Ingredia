#!/usr/bin/env python
"""
Seed script — populates the Ingredia database from the three reference files
in the data/ directory:

  - data/inci_master.csv      → ingredients table
  - data/synonyms.json        → ingredient_aliases table
  - data/concerns_seed.csv    → ingredient_concerns table

Run from the backend/ directory:
    python -m scripts.seed_db          (after adding scripts/ to PYTHONPATH)

Or directly:
    PYTHONPATH=e:/Ingredia/backend python e:/Ingredia/backend/scripts/seed_db.py

The script is idempotent: it skips any ingredient that already exists
(matching by canonical_name) and skips any alias/concern already attached
to that ingredient. Safe to re-run after data file updates.
"""

import csv
import json
import sys
from pathlib import Path

# Ensure the backend package is importable regardless of CWD
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.ingredient import Ingredient, IngredientAlias, IngredientConcern

DATA_DIR = BACKEND_DIR / "data"
INCI_CSV = DATA_DIR / "inci_master.csv"
SYNONYMS_JSON = DATA_DIR / "synonyms.json"
CONCERNS_CSV = DATA_DIR / "concerns_seed.csv"


def _parse_optional_float(value: str) -> float | None:
    """Return float or None for empty strings."""
    value = value.strip()
    return float(value) if value else None


def _parse_optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def _parse_optional_str(value: str) -> str | None:
    value = value.strip()
    return value if value else None


def seed_ingredients(db) -> dict[str, int]:
    """
    Load inci_master.csv into the ingredients table.
    Returns a mapping of canonical_name → ingredient.id for downstream use.
    """
    name_to_id: dict[str, int] = {}

    with INCI_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        created = skipped = 0

        for row in reader:
            canonical_name = row["canonical_name"].strip()
            if not canonical_name:
                continue

            existing = (
                db.query(Ingredient)
                .filter(Ingredient.canonical_name == canonical_name)
                .first()
            )
            if existing:
                name_to_id[canonical_name] = existing.id
                skipped += 1
                continue

            ing = Ingredient(
                canonical_name=canonical_name,
                cas_number=_parse_optional_str(row.get("cas_number", "")),
                ec_number=_parse_optional_str(row.get("ec_number", "")),
                function_tags=_parse_optional_str(row.get("function_tags", "")),
                hazard_score=_parse_optional_float(row.get("hazard_score", "")),
                hazard_basis=_parse_optional_str(row.get("hazard_basis", "")),
                data_completeness=row.get("data_completeness", "none").strip(),
                ewg_score=_parse_optional_int(row.get("ewg_score", "")),
                eu_annex_status=_parse_optional_str(row.get("eu_annex_status", "")),
            )
            db.add(ing)
            db.flush()  # Populate ing.id before recording it
            name_to_id[canonical_name] = ing.id
            created += 1

        db.commit()

    print(f"  ingredients: {created} created, {skipped} skipped")
    return name_to_id


def seed_aliases(db, name_to_id: dict[str, int]) -> None:
    """
    Load synonyms.json into ingredient_aliases.
    Each key is a lowercase alias; each value is the canonical_name.
    """
    with SYNONYMS_JSON.open(encoding="utf-8") as f:
        synonyms: dict[str, str] = json.load(f)

    created = skipped = unmapped = 0

    for alias_raw, canonical in synonyms.items():
        ingredient_id = name_to_id.get(canonical)
        if ingredient_id is None:
            print(f"    WARNING: synonym '{alias_raw}' → '{canonical}' not in DB; skipping")
            unmapped += 1
            continue

        already = (
            db.query(IngredientAlias)
            .filter(
                IngredientAlias.ingredient_id == ingredient_id,
                IngredientAlias.alias == alias_raw,
            )
            .first()
        )
        if already:
            skipped += 1
            continue

        db.add(
            IngredientAlias(
                ingredient_id=ingredient_id,
                alias=alias_raw,
                alias_type="common",  # Default; can be refined per-row if needed
            )
        )
        created += 1

    db.commit()
    print(f"  aliases: {created} created, {skipped} skipped, {unmapped} unmapped")


def seed_concerns(db, name_to_id: dict[str, int]) -> None:
    """
    Load concerns_seed.csv into ingredient_concerns.
    source_name is mandatory — rows without it are skipped with a warning.
    """
    with CONCERNS_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        created = skipped = unmapped = 0

        for row in reader:
            canonical_name = row["canonical_name"].strip()
            source_name = row.get("source_name", "").strip()

            if not source_name:
                print(
                    f"    WARNING: concern for '{canonical_name}' has no source_name; skipping"
                )
                skipped += 1
                continue

            ingredient_id = name_to_id.get(canonical_name)
            if ingredient_id is None:
                print(
                    f"    WARNING: concern for '{canonical_name}' not in DB; skipping"
                )
                unmapped += 1
                continue

            # Idempotency: skip if same ingredient + concern_type + source_name exists
            already = (
                db.query(IngredientConcern)
                .filter(
                    IngredientConcern.ingredient_id == ingredient_id,
                    IngredientConcern.concern_type == row["concern_type"].strip(),
                    IngredientConcern.source_name == source_name,
                )
                .first()
            )
            if already:
                skipped += 1
                continue

            db.add(
                IngredientConcern(
                    ingredient_id=ingredient_id,
                    concern_type=row["concern_type"].strip(),
                    severity=row["severity"].strip(),
                    summary=row["summary"].strip(),
                    source_name=source_name,
                    source_url=_parse_optional_str(row.get("source_url", "")),
                    population_context=_parse_optional_str(
                        row.get("population_context", "")
                    ),
                )
            )
            created += 1

        db.commit()

    print(f"  concerns: {created} created, {skipped} skipped, {unmapped} unmapped")


def main() -> None:
    print("=== Ingredia seed script ===")
    db = SessionLocal()
    try:
        print("Seeding ingredients...")
        name_to_id = seed_ingredients(db)

        print("Seeding aliases...")
        seed_aliases(db, name_to_id)

        print("Seeding concerns...")
        seed_concerns(db, name_to_id)

        print("Done.")
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
