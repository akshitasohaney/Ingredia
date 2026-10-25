"""Ingredia NLP package — normalisation, synonym lookup, fuzzy matching."""

from app.nlp.normalizer import normalize_text, process_raw, split_ingredients
from app.nlp.synonym_matcher import SynonymIndex
from app.nlp.fuzzy_matcher import FuzzyMatcher, FuzzyMatch
from app.nlp.ingredient_linker import IngredientLinker, LinkResult

__all__ = [
    "normalize_text",
    "process_raw",
    "split_ingredients",
    "SynonymIndex",
    "FuzzyMatcher",
    "FuzzyMatch",
    "IngredientLinker",
    "LinkResult",
]
