"""Pure-Python implementation of Ingredia ingredient scoring."""


def ingredient_score(values: list[float]) -> dict[str, float | str]:
    """Return the same aggregate scores and bands as ``ingredient_score.m``.

    Values must be finite numeric scores in the inclusive range zero through one.
    """
    if not values:
        raise ValueError("At least one score is required.")
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in values):
        raise ValueError("Scores must be numbers.")
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("Scores must be between 0 and 1.")

    mean_score = sum(values) / len(values)
    risk_band = "low" if mean_score < 0.34 else "moderate" if mean_score < 0.67 else "high"
    return {
        "mean_score": mean_score,
        "normalized_score": 100 * mean_score,
        "risk_band": risk_band,
    }
