"""
seed_data.py – populate the database with sample skincare ingredients and products
for development/testing. Run once: python seed_data.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.models.ingredient import Ingredient
from app.models.product import Product, ProductIngredient

INGREDIENTS = [
    dict(name="Aqua", inci_name="Aqua", aliases="Water,Eau",
         function="Solvent", description="Purified water used as the base solvent for many cosmetic formulations.",
         evidence_summary="A standard cosmetic solvent with no ingredient-specific skin risk at normal topical use.",
         evidence_source="Cosmetic Ingredient Review reference data",
         confidence_score=0.99, suitable_for="oily,dry,combination,normal,sensitive",
         caution_for="", is_fragrance=0, is_allergen=0),
    dict(name="Niacinamide", inci_name="Niacinamide", aliases="Vitamin B3,Nicotinamide",
         function="Brightening, Pore-minimizing", description="Water-soluble vitamin that improves skin tone, reduces pore appearance, and strengthens the skin barrier.",
         evidence_summary="Strong clinical evidence for improving hyperpigmentation and barrier function at 2-10% concentrations.",
         evidence_source="Journal of Cosmetic Dermatology, 2021",
         confidence_score=0.92, suitable_for="oily,combination,normal,sensitive",
         caution_for="", is_fragrance=0, is_allergen=0),
    dict(name="Hyaluronic Acid", inci_name="Sodium Hyaluronate", aliases="HA,Sodium Hyaluronate,Hyaluron",
         function="Humectant", description="Draws moisture into the skin and helps retain it. Works across multiple molecular weights.",
         evidence_summary="Well-evidenced humectant. Most effective when applied on damp skin and sealed with an occlusive.",
         evidence_source="Dermatology Research and Practice, 2020",
         confidence_score=0.95, suitable_for="oily,dry,combination,normal,sensitive",
         caution_for="", is_fragrance=0, is_allergen=0),
    dict(name="Retinol", inci_name="Retinol", aliases="Vitamin A,All-trans-retinol",
         function="Anti-aging, Cell turnover", description="Vitamin A derivative that increases cell turnover and stimulates collagen production.",
         evidence_summary="Strong evidence for reducing fine lines and improving texture. Can cause irritation, especially in early use.",
         evidence_source="British Journal of Dermatology, 2019",
         confidence_score=0.90, suitable_for="normal,combination,oily",
         caution_for="sensitive,dry,rosacea,eczema,pregnancy", is_fragrance=0, is_allergen=0),
    dict(name="Glycerin", inci_name="Glycerin", aliases="Glycerol,Glycerine",
         function="Humectant", description="Attracts and retains moisture. One of the most well-studied skin moisturizers.",
         evidence_summary="Highly effective humectant with an excellent safety profile.",
         evidence_source="CIR Expert Panel, 2014",
         confidence_score=0.98, suitable_for="oily,dry,combination,normal,sensitive",
         caution_for="", is_fragrance=0, is_allergen=0),
    dict(name="Salicylic Acid", inci_name="Salicylic Acid", aliases="BHA,Beta Hydroxy Acid",
         function="Exfoliant, Keratolytic", description="Oil-soluble acid that penetrates pores to exfoliate and unclog them.",
         evidence_summary="Effective for acne and oily skin. Can be drying. FDA-approved OTC acne ingredient at 0.5-2%.",
         evidence_source="FDA Monograph; JAAD, 2018",
         confidence_score=0.93, suitable_for="oily,combination,acne-prone",
         caution_for="dry,sensitive,aspirin-sensitive individuals", is_fragrance=0, is_allergen=0),
    dict(name="Vitamin C", inci_name="Ascorbic Acid", aliases="L-Ascorbic Acid,Ascorbic Acid,Ascorbate",
         function="Antioxidant, Brightening", description="Potent antioxidant that brightens skin tone and protects against UV damage.",
         evidence_summary="Strong evidence for brightening; stability varies by derivative. Most effective L-AA at pH <3.5.",
         evidence_source="Nutrients, 2017; CIR 2005",
         confidence_score=0.88, suitable_for="normal,combination,oily",
         caution_for="sensitive,rosacea", is_fragrance=0, is_allergen=0),
    dict(name="Ceramide NP", inci_name="Ceramide NP", aliases="Ceramide 3,Ceramide",
         function="Barrier repair, Emollient", description="Lipid molecule naturally found in skin. Reinforces the skin barrier and reduces water loss.",
         evidence_summary="Good evidence for improving barrier function, especially in eczema-prone skin.",
         evidence_source="Journal of Investigative Dermatology, 2016",
         confidence_score=0.91, suitable_for="dry,sensitive,normal,combination",
         caution_for="", is_fragrance=0, is_allergen=0),
    dict(name="Fragrance", inci_name="Parfum", aliases="Parfum,Fragrance mix,Scent",
         function="Masking, Aesthetic", description="Added scent. Can be a complex mixture of dozens of undisclosed chemicals.",
         evidence_summary="Common sensitiser. EU restricts 26 allergens at labelling levels. No therapeutic benefit.",
         evidence_source="SCCS Opinion 2012; EU Cosmetics Regulation",
         confidence_score=0.85, suitable_for="",
         caution_for="sensitive,rosacea,eczema,allergy-prone", is_fragrance=1, is_allergen=1),
    dict(name="Dimethicone", inci_name="Dimethicone", aliases="Polydimethylsiloxane,Silicone",
         function="Emollient, Film-former", description="Silicone that creates a smooth, protective layer on skin and improves spreadability.",
         evidence_summary="Well-tolerated by most skin types. Non-comedogenic at typical use levels.",
         evidence_source="CIR Expert Panel, 2003",
         confidence_score=0.96, suitable_for="dry,normal,combination,sensitive",
         caution_for="", is_fragrance=0, is_allergen=0),
    dict(name="Zinc Oxide", inci_name="Zinc Oxide", aliases="ZnO",
         function="Sunscreen, Anti-inflammatory", description="Mineral UV filter that reflects and scatters UV radiation.",
         evidence_summary="Broad-spectrum UV protection. Recommended for sensitive skin. Non-irritating.",
         evidence_source="FDA Sunscreen Monograph; AAD Guidelines",
         confidence_score=0.97, suitable_for="oily,dry,combination,normal,sensitive",
         caution_for="", is_fragrance=0, is_allergen=0),
    dict(name="Sodium Lauryl Sulfate", inci_name="Sodium Lauryl Sulfate", aliases="SLS,Sodium Dodecyl Sulfate",
         function="Surfactant, Emulsifier", description="Strong anionic surfactant used as a cleanser and foaming agent.",
         evidence_summary="Known skin irritant at higher concentrations. May disrupt barrier in sensitive/eczema-prone skin.",
         evidence_source="Contact Dermatitis, 2016; CIR",
         confidence_score=0.88, suitable_for="",
         caution_for="sensitive,dry,eczema,rosacea", is_fragrance=0, is_allergen=0),
    dict(name="Shea Butter", inci_name="Butyrospermum Parkii Butter", aliases="Butyrospermum Parkii,Shea",
         function="Emollient, Moisturiser", description="Rich plant butter containing fatty acids and vitamins. Softens and protects skin.",
         evidence_summary="Good emollient with anti-inflammatory properties. Well tolerated by most.",
         evidence_source="AOCS, 2010; Phytotherapy Research",
         confidence_score=0.87, suitable_for="dry,normal,combination,sensitive",
         caution_for="tree nut allergy (rare)", is_fragrance=0, is_allergen=0),
    dict(name="Alpha Arbutin", inci_name="Alpha-Arbutin", aliases="Arbutin,α-Arbutin",
         function="Brightening, Depigmenting", description="Inhibits tyrosinase to reduce melanin production. More stable than hydroquinone.",
         evidence_summary="Moderate evidence for hyperpigmentation reduction at 1-2%. Fewer side effects than hydroquinone.",
         evidence_source="Journal of Pharmacological Sciences, 2009",
         confidence_score=0.82, suitable_for="normal,combination,oily,dry,sensitive",
         caution_for="", is_fragrance=0, is_allergen=0),
    dict(name="Lactic Acid", inci_name="Lactic Acid", aliases="AHA,Alpha Hydroxy Acid",
         function="Exfoliant, Humectant", description="Alpha hydroxy acid that exfoliates and simultaneously attracts moisture.",
         evidence_summary="Gentler than glycolic acid. Effective for textural improvement. Photosensitising — use SPF.",
         evidence_source="Dermatological Surgery, 1998; CIR",
         confidence_score=0.90, suitable_for="normal,combination,dry",
         caution_for="sensitive,sunburn-prone — always use SPF", is_fragrance=0, is_allergen=0),
    dict(name="Phenoxyethanol", inci_name="Phenoxyethanol", aliases="Euxyl",
         function="Preservative", description="Synthetic preservative that prevents microbial growth in cosmetic formulations.",
         evidence_summary="Safe at up to 1% (EU limit). Rare sensitiser. Generally well tolerated.",
         evidence_source="SCCS Opinion 2016; CIR 2016",
         confidence_score=0.89, suitable_for="oily,dry,combination,normal",
         caution_for="sensitive (rare reactions)", is_fragrance=0, is_allergen=0),
]

PRODUCTS = [
    dict(name="Daily Moisturising Barrier Cream", brand="Ingredia Lab", product_type="Moisturiser",
         intended_use="Daily hydration and barrier support for all skin types.",
         notes="Formulated without fragrance. Suitable for morning and evening use.",
         ingredients=["Glycerin", "Ceramide NP", "Hyaluronic Acid", "Dimethicone", "Phenoxyethanol"]),
    dict(name="10% Niacinamide + 1% Zinc Serum", brand="Ingredia Lab", product_type="Serum",
         intended_use="Pore minimising and blemish control for oily and combination skin.",
         notes="Avoid combining with pure Vitamin C at the same time of day.",
         ingredients=["Niacinamide", "Zinc Oxide", "Glycerin", "Hyaluronic Acid", "Phenoxyethanol"]),
    dict(name="Retinol 0.5% Night Cream", brand="Ingredia Lab", product_type="Treatment",
         intended_use="Anti-aging and skin renewal. Evening use only.",
         notes="Start with 2-3 nights per week. Always use SPF during the day.",
         ingredients=["Retinol", "Ceramide NP", "Shea Butter", "Glycerin", "Phenoxyethanol"]),
    dict(name="Brightening Vitamin C 15% Serum", brand="Ingredia Lab", product_type="Serum",
         intended_use="Morning antioxidant protection and brightening.",
         notes="Store in a cool, dark place. Contains L-Ascorbic Acid.",
         ingredients=["Vitamin C", "Alpha Arbutin", "Hyaluronic Acid", "Glycerin", "Phenoxyethanol"]),
    dict(name="Gentle Resurfacing Exfoliant", brand="Ingredia Lab", product_type="Exfoliant",
         intended_use="Mild chemical exfoliation 2-3x per week.",
         notes="Contains AHA — use SPF the following morning.",
         ingredients=["Lactic Acid", "Glycerin", "Hyaluronic Acid", "Phenoxyethanol"]),
    dict(name="Clarifying BHA Toner", brand="Ingredia Lab", product_type="Toner",
         intended_use="Unclogs pores and controls excess oil for acne-prone skin.",
         notes="Not recommended for dry or sensitive skin types.",
         ingredients=["Salicylic Acid", "Niacinamide", "Glycerin", "Phenoxyethanol"]),
    dict(name="Mineral SPF 50 Sunscreen", brand="Ingredia Lab", product_type="Sunscreen",
         intended_use="Broad-spectrum UVA/UVB protection for daily use.",
         notes="Suitable for sensitive skin. Reef-safe formula.",
         ingredients=["Zinc Oxide", "Dimethicone", "Glycerin", "Phenoxyethanol"]),
    dict(name="Rich Repair Night Balm", brand="Ingredia Lab", product_type="Moisturiser",
         intended_use="Intensive overnight barrier repair for dry and sensitive skin.",
         notes="Contains shea butter. Tree nut allergy — see caution.",
         ingredients=["Shea Butter", "Ceramide NP", "Glycerin", "Dimethicone", "Phenoxyethanol"]),
]


def seed():
    init_db()
    db = SessionLocal()
    try:
        # Only seed if tables are empty
        if db.query(Ingredient).count() > 0:
            print("Database already has ingredients — skipping seed.")
            return

        # Insert ingredients
        ing_map: dict[str, Ingredient] = {}
        for data in INGREDIENTS:
            ing = Ingredient(**data)
            db.add(ing)
            db.flush()
            ing_map[data["name"]] = ing

        # Insert products
        for p_data in PRODUCTS:
            ing_names = p_data.pop("ingredients")
            product = Product(**p_data)
            db.add(product)
            db.flush()
            for pos, ing_name in enumerate(ing_names, start=1):
                ing = ing_map.get(ing_name)
                if ing:
                    pi = ProductIngredient(
                        product_id=product.id,
                        ingredient_id=ing.id,
                        position=pos,
                        raw_name=ing_name,
                    )
                    db.add(pi)

        db.commit()
        print(f"Seeded {len(INGREDIENTS)} ingredients and {len(PRODUCTS)} products.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
