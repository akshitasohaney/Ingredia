/**
 * Explainable, informational review scoring for the ingredient UI.
 * This is not a medical safety determination or concentration estimate.
 */
export function getIngredientReview(ingredient, profile = {}) {
  const { suitableForProfile = false, cautionForProfile = false } = profile;
  const confidence = ingredient.confidence_score;
  let score = confidence == null ? 55 : 65 + (confidence * 20);
  const signals = [];

  if (confidence == null) {
    signals.push({ tone: 'neutral', text: 'Evidence coverage is not available.' });
  } else if (confidence >= 0.75) {
    signals.push({ tone: 'good', text: `Evidence coverage: ${Math.round(confidence * 100)}%.` });
  } else {
    signals.push({ tone: 'neutral', text: `Evidence coverage: ${Math.round(confidence * 100)}%.` });
  }

  if (ingredient.is_concern) {
    score -= 24;
    signals.push({ tone: 'warn', text: ingredient.concern_reason || 'A formulation review flag is present.' });
  }
  if (ingredient.is_allergen) {
    score -= 18;
    signals.push({ tone: 'warn', text: 'Marked as a potential allergen.' });
  }
  if (ingredient.is_fragrance) {
    score -= 12;
    signals.push({ tone: 'warn', text: 'Contains fragrance-related information.' });
  }
  if (cautionForProfile) {
    score -= 20;
    signals.push({ tone: 'warn', text: 'May need extra consideration for your selected profile.' });
  } else if (suitableForProfile) {
    score += 8;
    signals.push({ tone: 'good', text: 'May suit your selected profile.' });
  }

  score = Math.round(Math.max(0, Math.min(100, score)));
  const band = score >= 75
    ? { label: 'Favourable review', tone: 'good' }
    : score >= 50
      ? { label: 'Review details', tone: 'neutral' }
      : { label: 'Use caution', tone: 'warn' };

  return { score, band, signals };
}

export function getFormulaReview(ingredients, profileForIngredient) {
  if (!ingredients.length) return null;
  const reviews = ingredients.map((ingredient) =>
    getIngredientReview(ingredient, profileForIngredient(ingredient))
  );
  const score = Math.round(reviews.reduce((total, review) => total + review.score, 0) / reviews.length);
  return { score, band: score >= 75 ? 'Favourable review' : score >= 50 ? 'Review details' : 'Use caution' };
}
