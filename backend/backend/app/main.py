# backend/app/main.py
"""
FastAPI entry point for the Ingredia backend.

* Includes the API routers (`/api/v1/scans`, `/api/v1/products`, `/api/v1/ingredients`).
* Calls `init_db()` on startup so the SQLite dev DB is ready.
* Exposes the `app` object that `uvicorn` or the test client uses.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import SessionLocal, init_db
from app.models.ingredient import Ingredient
from app.models.product import Product, ProductIngredient

# Import routers
from app.routers import scans, products, health, ingredients, matlab  # noqa
from app.services.matlab_service import matlab_service

def on_startup() -> None:
    """Create tables if they do not exist (dev convenience)."""
    init_db()
    # Add common label ingredients and starter products to databases created
    # before the catalogue was expanded. Existing user data is never replaced.
    reference_ingredients = [
        ("Aqua", "Water,Eau", "Solvent"),
        ("Cyclopentasiloxane", "Cyclomethicone,D5", "Volatile silicone"),
        ("Dimethicone", "Polydimethylsiloxane,Silicone", "Emollient, film-former"),
        ("Dimethiconol", "Dimethicone polymer", "Silicone conditioning agent"),
        ("Palmitic Acid", "Hexadecanoic Acid", "Fatty acid, emollient"),
        ("Stearic Acid", "Octadecanoic Acid", "Fatty acid, thickener"),
        ("Titanium Dioxide", "CI 77891,TiO2", "Mineral UV filter, opacifier"),
        ("Isohexadecane", "", "Emollient, solvent"),
        ("Ethylhexyl Methoxycinnamate", "Octinoxate,EHMC", "UV filter"),
        ("Aluminum Starch Octenylsuccinate", "Aluminium Starch Octenylsuccinate", "Absorbent, texture enhancer"),
        ("Triethanolamine", "TEA", "pH adjuster"),
        ("Butylene Glycol", "1,3-Butylene Glycol", "Humectant, solvent"),
        ("Caprylyl Glycol", "1,2-Octanediol", "Humectant, preservative booster"),
        ("Cetyl Alcohol", "1-Hexadecanol", "Fatty alcohol, emollient"),
        ("Cetearyl Alcohol", "Cetostearyl Alcohol", "Fatty alcohol, thickener"),
        ("Glyceryl Stearate", "Glycerol Stearate", "Emulsifier, emollient"),
        ("PEG-100 Stearate", "Polyoxyethylene Stearate", "Emulsifier"),
        ("Carbomer", "Carbopol", "Gel thickener"),
        ("Disodium EDTA", "EDTA", "Chelating agent"),
        ("Tocopherol", "Vitamin E", "Antioxidant"),
        ("Panthenol", "Provitamin B5", "Humectant, skin-conditioning agent"),
        ("Allantoin", "", "Skin protectant, soothing agent"),
        ("Sodium PCA", "", "Humectant"),
        ("Isododecane", "", "Volatile emollient, solvent"),
        ("Polysorbate 20", "Tween 20", "Solubiliser, emulsifier"),
        ("Sodium Benzoate", "", "Preservative"),
        ("Potassium Sorbate", "", "Preservative"),
        ("Citric Acid", "", "pH adjuster"),
        ("Sodium Carbonate", "Soda Ash", "pH adjuster"),
        ("Sodium Sulfate", "", "Viscosity control"),
    ]
    starter_products = [
        ("Hydrating Daily Face Wash", "Ingredia Lab", "Cleanser", ["Aqua", "Glycerin", "Panthenol", "Sodium Benzoate"]),
        ("Silk Finish Primer", "Ingredia Lab", "Primer", ["Cyclopentasiloxane", "Dimethicone", "Dimethiconol", "Isohexadecane"]),
        ("Sheer Mineral Fluid SPF 30", "Ingredia Lab", "Sunscreen", ["Aqua", "Titanium Dioxide", "Dimethicone", "Aluminum Starch Octenylsuccinate"]),
        ("Lightweight Gel Moisturiser", "Ingredia Lab", "Moisturiser", ["Aqua", "Butylene Glycol", "Sodium PCA", "Carbomer", "Panthenol"]),
        ("Vitamin E Comfort Cream", "Ingredia Lab", "Moisturiser", ["Aqua", "Glyceryl Stearate", "Cetearyl Alcohol", "Tocopherol", "Allantoin"]),
        ("Velvet Matte Sunscreen SPF 50", "Ingredia Lab", "Sunscreen", ["Ethylhexyl Methoxycinnamate", "Titanium Dioxide", "Isohexadecane", "Dimethicone"]),
        ("Soothing Barrier Lotion", "Ingredia Lab", "Body lotion", ["Aqua", "Glycerin", "Panthenol", "Cetyl Alcohol", "Allantoin"]),
        ("Fresh Makeup Setting Mist", "Ingredia Lab", "Setting spray", ["Aqua", "Butylene Glycol", "Polysorbate 20", "Disodium EDTA"]),
    ]
    db = SessionLocal()
    try:
        for name, aliases, function in reference_ingredients:
            if not db.query(Ingredient).filter(Ingredient.name == name).first():
                db.add(Ingredient(
                    name=name, inci_name=name, aliases=aliases, function=function,
                    description=f"Common cosmetic ingredient used primarily as a {function.lower()}.",
                    evidence_summary="Reference entry available. Product safety also depends on concentration and formulation.",
                    evidence_source="Ingredia reference library", confidence_score=0.75,
                    suitable_for="oily,dry,combination,normal,sensitive", caution_for="",
                    is_fragrance=0, is_allergen=0,
                ))
        db.flush()
        ingredients = {item.name: item for item in db.query(Ingredient).all()}
        for name, brand, product_type, ingredient_names in starter_products:
            if db.query(Product).filter(Product.name == name, Product.brand == brand).first():
                continue
            product = Product(name=name, brand=brand, product_type=product_type,
                              intended_use=f"Everyday {product_type.lower()} use.",
                              notes="Ingredient information is provided for review and is not medical advice.")
            db.add(product)
            db.flush()
            for position, ingredient_name in enumerate(ingredient_names, start=1):
                ingredient = ingredients.get(ingredient_name)
                if ingredient:
                    db.add(ProductIngredient(product_id=product.id, ingredient_id=ingredient.id,
                                             position=position, raw_name=ingredient_name))
        db.commit()
    finally:
        db.close()


def on_shutdown() -> None:
    """Release MATLAB if it was started."""
    matlab_service.close()
app = FastAPI(
    title="Ingredia Backend",
    description="API for ingredient OCR/NLP pipelines and product‑risk analysis.",
    version="0.2.0",
    on_startup=[on_startup],
    on_shutdown=[on_shutdown],
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow the Vite dev server and preview to call the API.
# Tighten allow_origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router,       prefix="/api/v1")
app.include_router(products.router,     prefix="/api/v1")
app.include_router(ingredients.router,  prefix="/api/v1")
app.include_router(scans.router,        prefix="/api/v1")
app.include_router(matlab.router,       prefix="/api/v1")
