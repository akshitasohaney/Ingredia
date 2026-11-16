import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import Loader from '../components/Loader.jsx';
import { getFormulaReview, getIngredientReview } from '../utils/ingredientAnalysis.js';
import { getRiskAnalysis, getScanAnalysis } from '../api.js';
import './RiskAnalysis.css';

const SKIN_TYPES = ['Oily', 'Dry', 'Combination', 'Normal', 'Sensitive'];
const SKIN_CONCERNS = ['Acne', 'Dryness', 'Redness', 'Pigmentation', 'Fine lines', 'Rosacea', 'Eczema'];
const SENSITIVITIES = ['Fragrance', 'Essential oils', 'Sulfates', 'Tree nuts', 'Aspirin'];

function ConfidencePill({ score }) {
  if (score == null) return <span className="pill pill--unknown">Evidence unknown</span>;
  if (score >= 0.9) return <span className="pill pill--high">High confidence ({Math.round(score * 100)}%)</span>;
  if (score >= 0.75) return <span className="pill pill--medium">Moderate confidence ({Math.round(score * 100)}%)</span>;
  return <span className="pill pill--low">Limited evidence ({Math.round(score * 100)}%)</span>;
}

function skinTypeKey(s) { return s.toLowerCase(); }

function ingredientMatchesProfile(ing, skinType, concerns, sensitivities) {
  const suitable = (ing.suitable_for ?? '').toLowerCase().split(',').map(s => s.trim());
  const caution = (ing.caution_for ?? '').toLowerCase();
  const suitableForProfile = skinType ? suitable.includes(skinTypeKey(skinType)) : true;
  const cautionForProfile = skinType ? caution.includes(skinTypeKey(skinType)) : false;

  // Check concerns
  const concernMatch = concerns.some(c => caution.includes(c.toLowerCase()));

  // Check sensitivities
  const sensitivityMatch = sensitivities.some(s => {
    if (s === 'Fragrance') return ing.is_fragrance;
    return caution.includes(s.toLowerCase());
  });

  return { suitableForProfile, cautionForProfile: cautionForProfile || concernMatch || sensitivityMatch };
}

function IngredientCard({ ing, skinType, concerns, sensitivities }) {
  const [open, setOpen] = useState(false);
  const review = getIngredientReview(ing, ingredientMatchesProfile(ing, skinType, concerns, sensitivities));
  const scoreLabel = (
    <span className={`review-score review-score--${review.band.tone}`} title="Informational review score; not a medical safety rating">
      <strong>{review.score}</strong><span>/100</span> {review.band.label}
    </span>
  );

  const { suitableForProfile, cautionForProfile } = ingredientMatchesProfile(ing, skinType, concerns, sensitivities);

  let profileTag = null;
  if (skinType || concerns.length > 0 || sensitivities.length > 0) {
    if (cautionForProfile) {
      profileTag = <span className="ing-tag ing-tag--caution">⚠ Caution for your profile</span>;
    } else if (suitableForProfile) {
      profileTag = <span className="ing-tag ing-tag--suited">✓ May suit your profile</span>;
    }
  }

  return (
    <div className={`ing-card ${ing.is_concern ? 'ing-card--concern' : ''} ${cautionForProfile ? 'ing-card--caution' : ''}`}>
      <button className="ing-card__header" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <div className="ing-card__left">
          <span className="ing-card__name">{ing.name}</span>
          {ing.function && <span className="ing-card__fn">{ing.function}</span>}
        </div>
        <div className="ing-card__right">
          {ing.is_fragrance && <span className="pill pill--warn">Fragrance</span>}
          {ing.is_allergen && <span className="pill pill--warn">Allergen</span>}
          {profileTag}
          {scoreLabel}
          <span className="ing-card__chevron">{open ? '▲' : '▼'}</span>
        </div>
      </button>

      {open && (
        <div className="ing-card__body">
          {ing.description && (
            <div className="ing-detail-row">
              <h4>How it works</h4>
              <p>{ing.description}</p>
            </div>
          )}

          {ing.suitable_for && (
            <div className="ing-detail-row">
              <h4>May suit</h4>
              <p>{ing.suitable_for.split(',').map(s => s.trim()).filter(Boolean).join(' · ')}</p>
            </div>
          )}

          {ing.caution_for && (
            <div className="ing-detail-row ing-detail-row--warn">
              <h4>Caution for</h4>
              <p>{ing.caution_for}</p>
            </div>
          )}

          {ing.concern_reason && (
            <div className="ing-detail-row ing-detail-row--warn">
              <h4>Concern note</h4>
              <p>{ing.concern_reason}</p>
            </div>
          )}

          <div className="ingredient-review-detail">
            <div>
              <span className="ingredient-review-detail__label">Ingredient review score</span>
              <strong className={`ingredient-review-detail__score ingredient-review-detail__score--${review.band.tone}`}>{review.score}/100</strong>
            </div>
            <ul>{review.signals.map((signal, index) => (
              <li key={index} className={`review-signal review-signal--${signal.tone}`}>{signal.text}</li>
            ))}</ul>
          </div>

          {ing.evidence_summary && (
            <div className="ing-detail-row">
              <h4>Evidence summary</h4>
              <p>{ing.evidence_summary}</p>
            </div>
          )}

          <div className="ing-detail-footer">
            <ConfidencePill score={ing.confidence_score} />
            {ing.evidence_source && (
              <span className="ing-source">Source: {ing.evidence_source}</span>
            )}
          </div>

          <p className="ing-concentration-note">
            ℹ Ingredient order indicates listing sequence only. Concentration cannot be determined from position alone.
          </p>
        </div>
      )}
    </div>
  );
}

function RiskAnalysis({ isScanAnalysis = false }) {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Personal profile
  const [skinType, setSkinType] = useState('');
  const [concerns, setConcerns] = useState([]);
  const [sensitivities, setSensitivities] = useState([]);

  // Filters
  const [filterConcern, setFilterConcern] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const loadAnalysis = isScanAnalysis ? getScanAnalysis : getRiskAnalysis;
    loadAnalysis(id)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, isScanAnalysis]);

  function toggleConcern(c) {
    setConcerns(prev => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]);
  }
  function toggleSensitivity(s) {
    setSensitivities(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);
  }

  if (loading) return <div className="ra-page"><Loader /></div>;
  if (error) return (
    <div className="ra-page ra-page--error">
      <p>Analysis failed: <strong>{error}</strong></p>
      <button className="btn btn-secondary" onClick={() => { const loadAnalysis = isScanAnalysis ? getScanAnalysis : getRiskAnalysis; setError(null); setLoading(true); loadAnalysis(id).then(setData).catch(e => setError(e.message)).finally(() => setLoading(false)); }}>
        Retry
      </button>
      <Link to="/" className="btn btn-primary" style={{ marginLeft: 12 }}>Home</Link>
    </div>
  );
  if (!data) return null;

  const fragranceIngs = data.ingredients.filter(i => i.is_fragrance);
  const allergenIngs = data.ingredients.filter(i => i.is_allergen);
  const concernIngs = data.ingredients.filter(i => i.is_concern);
  const clearIngs = data.ingredients.filter(i => !i.is_concern);

  const profileCautionIngs = data.ingredients.filter(i =>
    ingredientMatchesProfile(i, skinType, concerns, sensitivities).cautionForProfile
  );
  const profileSuitedIngs = data.ingredients.filter(i => {
    const { suitableForProfile, cautionForProfile } = ingredientMatchesProfile(i, skinType, concerns, sensitivities);
    return suitableForProfile && !cautionForProfile;
  });

  const hasProfile = skinType || concerns.length > 0 || sensitivities.length > 0;

  const filteredIngredients = filterConcern
    ? data.ingredients.filter(i => i.is_concern || ingredientMatchesProfile(i, skinType, concerns, sensitivities).cautionForProfile)
    : data.ingredients;

  const formulaReview = getFormulaReview(
    data.ingredients,
    (ingredient) => ingredientMatchesProfile(ingredient, skinType, concerns, sensitivities)
  );

  return (
    <main className="ra-page">
      {/* Breadcrumb */}
      <nav className="ra-breadcrumb">
        <Link to="/">Home</Link>
        <span>›</span>
        <Link to={isScanAnalysis ? `/scan/review/${id}` : `/product/${id}`}>{isScanAnalysis ? 'Review' : 'Product'}</Link>
        <span>›</span>
        <span>Analysis</span>
      </nav>

      {/* Product overview */}
      <header className="ra-header">
        <div>
          {data.product_type && <div className="ra-header__type">{data.product_type}</div>}
          <h1 className="ra-header__name">{data.product_name}</h1>
          {data.brand && <p className="ra-header__brand">{data.brand}</p>}
          {data.intended_use && <p className="ra-header__use">{data.intended_use}</p>}
        </div>
        <div className="ra-header__stats">
          <div className="ra-stat">
            <div className="ra-stat__num">{data.ingredient_count}</div>
            <div className="ra-stat__label">Ingredients</div>
          </div>
          <div className="ra-stat">
            <div className="ra-stat__num">{concernIngs.length}</div>
            <div className="ra-stat__label">Flagged</div>
          {formulaReview && (
            <div className="ra-stat ra-stat--score">
              <div className="ra-stat__num">{formulaReview.score}</div>
              <div className="ra-stat__label">Formula review</div>
            </div>
          )}
          </div>
          {data.unidentified_count > 0 && (
            <div className="ra-stat">
              <div className="ra-stat__num">{data.unidentified_count}</div>
              <div className="ra-stat__label">Unidentified</div>
            </div>
          )}
        </div>
      </header>

      {/* Disclaimer */}
      <div className="ra-disclaimer">
        <strong>Note:</strong> {data.disclaimer}
      </div>

      <div className="ra-body">
        {/* Sidebar: Profile + Summary */}
        <aside className="ra-sidebar">
          {/* Personal skin profile */}
          <section className="ra-panel">
            <h2 className="ra-panel__title">Your skin profile</h2>
            <p className="ra-panel__hint">Optional. Personalises ingredient notes for your skin.</p>

            <div className="profile-section">
              <label className="profile-label">Skin type</label>
              <div className="profile-chips">
                {SKIN_TYPES.map(t => (
                  <button
                    key={t}
                    className={`chip ${skinType === t ? 'chip--active' : ''}`}
                    onClick={() => setSkinType(s => s === t ? '' : t)}
                  >{t}</button>
                ))}
              </div>
            </div>

            <div className="profile-section">
              <label className="profile-label">Concerns</label>
              <div className="profile-chips">
                {SKIN_CONCERNS.map(c => (
                  <button
                    key={c}
                    className={`chip ${concerns.includes(c) ? 'chip--active' : ''}`}
                    onClick={() => toggleConcern(c)}
                  >{c}</button>
                ))}
              </div>
            </div>

            <div className="profile-section">
              <label className="profile-label">Known sensitivities</label>
              <div className="profile-chips">
                {SENSITIVITIES.map(s => (
                  <button
                    key={s}
                    className={`chip ${sensitivities.includes(s) ? 'chip--active' : ''}`}
                    onClick={() => toggleSensitivity(s)}
                  >{s}</button>
                ))}
              </div>
            </div>

            {hasProfile && (
              <p className="profile-disclaimer">
                Profile matching is based on available ingredient data and is informational only.
                It does not constitute dermatological advice.
              </p>
            )}
          </section>

          {/* Formula summary */}
          <section className="ra-panel">
            <h2 className="ra-panel__title">Formula summary</h2>

            {hasProfile && profileSuitedIngs.length > 0 && (
              <div className="summary-block summary-block--good">
                <h3>Potentially beneficial for your profile</h3>
                <ul>{profileSuitedIngs.map(i => <li key={i.ingredient_id}>{i.name}</li>)}</ul>
              </div>
            )}

            {hasProfile && profileCautionIngs.length > 0 && (
              <div className="summary-block summary-block--warn">
                <h3>Caution for your profile</h3>
                <ul>{profileCautionIngs.map(i => <li key={i.ingredient_id}>{i.name}</li>)}</ul>
              </div>
            )}

            {fragranceIngs.length > 0 && (
              <div className="summary-block summary-block--note">
                <h3>Fragrance / potential allergens</h3>
                <ul>{fragranceIngs.map(i => <li key={i.ingredient_id}>{i.name}</li>)}</ul>
              </div>
            )}

            {clearIngs.length > 0 && !hasProfile && (
              <div className="summary-block summary-block--good">
                <h3>No flags raised</h3>
                <ul>{clearIngs.map(i => <li key={i.ingredient_id}>{i.name}</li>)}</ul>
              </div>
            )}

            {concernIngs.length > 0 && (
              <div className="summary-block summary-block--warn">
                <h3>Flagged ingredients</h3>
                <ul>{concernIngs.map(i => (
                  <li key={i.ingredient_id}>
                    <strong>{i.name}</strong>
                    {i.concern_reason && ` — ${i.concern_reason}`}
                  </li>
                ))}</ul>
              </div>
            )}
            {formulaReview && (
              <div className="formula-review">
                <div className="formula-review__score">{formulaReview.score}<span>/100</span></div>
                <div><h3>{formulaReview.band}</h3><p>Average of the ingredient review scores shown here. It reflects available evidence and flags, not concentration or clinical safety.</p></div>
              </div>
            )}


            {data.unidentified_count > 0 && (
              <div className="summary-block summary-block--note">
                <h3>{data.unidentified_count} ingredient{data.unidentified_count > 1 ? 's' : ''} need a reference record</h3>
                <p>{isScanAnalysis
                  ? 'They are included in this analysis with a clear reference-pending note.'
                  : 'These ingredients were not found in the database and could not be analysed.'}
                </p>
              </div>
            )}
          </section>
        </aside>

        {/* Main: Ingredient breakdown */}
        <section className="ra-main">
          <div className="ra-main__toolbar">
            <h2 className="ra-main__title">Ingredient breakdown</h2>
            <label className="ra-filter">
              <input
                type="checkbox"
                checked={filterConcern}
                onChange={e => setFilterConcern(e.target.checked)}
              />
              Show flagged only
            </label>
          </div>

          <p className="ra-main__count">
            {filteredIngredients.length} of {data.ingredient_count} ingredients shown
          </p>

          <div className="ra-ingredients">
            {filteredIngredients.map((ing) => (
              <IngredientCard
                key={ing.ingredient_id}
                ing={ing}
                skinType={skinType}
                concerns={concerns}
                sensitivities={sensitivities}
              />
            ))}
            {filteredIngredients.length === 0 && (
              <p className="ra-empty">No ingredients match the current filter.</p>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

export default RiskAnalysis;
