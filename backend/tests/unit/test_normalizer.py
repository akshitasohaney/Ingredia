import pytest
from app.nlp.normalizer import normalize_text, split_ingredients, process_raw

@pytest.mark.parametrize(
    "input_text,expected",
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("Water", "water"),
        ("  Water  ", "water"),
        ("Water, Glycerin", "water, glycerin"),
        ("Water / Glycerin", "water / glycerin"),
        ("Water‑Glycerin", "water glycerin"),
        ("Water (Aqua)", "water (aqua)"),
        ("Water, (Aqua) / Glycerin", "water, (aqua) / glycerin"),
    ]
)
def test_normalize_text(input_text, expected):
    assert normalize_text(input_text) == expected

def test_split_ingredients():
    assert split_ingredients("water, glycerin") == ["water", "glycerin"]
    assert split_ingredients("water / glycerin") == ["water", "glycerin"]
    assert split_ingredients("water (aqua, mineral) / glycerin") == ["water (aqua, mineral)", "glycerin"]
    assert split_ingredients("a, b / c, d") == ["a", "b", "c", "d"]

def test_process_raw():
    raw = "Water (Aqua), Glycerin / Propylene‑Glycol"
    tokens = process_raw(raw)
    assert tokens == ["water (aqua)", "glycerin", "propylene glycol"]
