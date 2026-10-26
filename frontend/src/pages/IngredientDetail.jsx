import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import Loader from '../components/Loader.jsx';
import { getIngredient } from '../api.js';
import './IngredientDetail.css';

function IngredientDetail() {
  const { id } = useParams();
  const [ing, setIng] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  function load() {
    setLoading(true);
    setError(null);
    getIngredient(id)
      .then(setIng)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [id]);

  if (loading) return <div className="id-page"><Loader /></div>;
  if (error) return (
    <div className="id-page id-page--error">
      <p>Could not load ingredient: <strong>{error}</strong></p>
      <button className="btn btn-secondary" onClick={load}>Retry</button>
    </div>
  );
  if (!ing) return null;

  const suitableList = (ing.suitable_for ?? '').split(',').map(s => s.trim()).filter(Boolean);
  const cautionList  = (ing.caution_for  ?? '').split(',').map(s => s.trim()).filter(Boolean);
  const aliasesList  = (ing.aliases      ?? '').split(',').map(s => s.trim()).filter(Boolean);

  function confidenceLabel(score) {
    if (score == null) return { label: 'Evidence unknown', cls: 'pill--unknown' };
    if (score >= 0.9)  return { label: `High confidence (${Math.round(score * 100)}%)`, cls: 'pill--high' };
    if (score >= 0.75) return { label: `Moderate confidence (${Math.round(score * 100)}%)`, cls: 'pill--medium' };
    return { label: `Limited evidence (${Math.round(score * 100)}%)`, cls: 'pill--low' };
  }

  const conf = confidenceLabel(ing.confidence_score);

  return (
    <main className="id-page">
      <nav className="id-breadcrumb">
        <Link to="/">Home</Link>
        <span>›</span>
        <span>Ingredient</span>
        <span>›</span>
        <span>{ing.name}</span>
      </nav>

      <header className="id-header">
        <div>
          {ing.function && <div className="id-header__fn">{ing.function}</div>}
          <h1 className="id-header__name">{ing.name}</h1>
          {ing.inci_name && ing.inci_name !== ing.name && (
            <p className="id-header__inci">INCI: {ing.inci_name}</p>
          )}
          {aliasesList.length > 0 && (
            <p className="id-header__aliases">Also known as: {aliasesList.join(', ')}</p>
          )}
        </div>
        <div className="id-header__badges">
          <span className={`pill ${conf.cls}`}>{conf.label}</span>
          {ing.is_fragrance && <span className="pill pill--warn">Fragrance</span>}
          {ing.is_allergen  && <span className="pill pill--warn">Allergen</span>}
        </div>
      </header>

      <div className="id-body">
        {ing.description && (
          <section className="id-section">
            <h2>How it works</h2>
            <p>{ing.description}</p>
          </section>
        )}

        {ing.evidence_summary && (
          <section className="id-section">
            <h2>Evidence summary</h2>
            <p>{ing.evidence_summary}</p>
            {ing.evidence_source && (
              <p className="id-source">Source: {ing.evidence_source}</p>
            )}
          </section>
        )}

        <div className="id-cols">
          {suitableList.length > 0 && (
            <section className="id-section id-section--good">
              <h2>May suit</h2>
              <ul>
                {suitableList.map(s => <li key={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</li>)}
              </ul>
            </section>
          )}

          {cautionList.length > 0 && (
            <section className="id-section id-section--warn">
              <h2>Caution for</h2>
              <ul>
                {cautionList.map(s => <li key={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</li>)}
              </ul>
            </section>
          )}
        </div>

        <div className="id-disclaimer">
          <strong>Note:</strong> Ingredient presence alone cannot determine a product's safety or
          suitability. Concentration, formulation context, individual sensitivities, and exposure
          all matter. This information is not medical advice.
        </div>
      </div>
    </main>
  );
}

export default IngredientDetail;
