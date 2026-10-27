import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import Loader from '../components/Loader.jsx';
import { getScanReview, patchScanIngredient, confirmScan } from '../api.js';
import './ScanReview.css';

function ScanReview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [scan, setScan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirming, setConfirming] = useState(false);

  function load() {
    setLoading(true);
    setError(null);
    getScanReview(id)
      .then(setScan)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [id]);

  async function handleAccept(si) {
    try {
      const updated = await patchScanIngredient(scan.id, si.id, true);
      setScan(updated);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleReject(si) {
    try {
      const updated = await patchScanIngredient(scan.id, si.id, false);
      setScan(updated);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleConfirm() {
    setConfirming(true);
    try {
      await confirmScan(scan.id);
      // Navigate to the linked product's risk analysis if available
      if (scan.product_id) {
        navigate(`/product/${scan.product_id}/risk`);
      } else {
        // Navigate to a generic analysis of accepted ingredients
        navigate(`/scan/review/${id}/analysis`);
      }
    } catch (e) {
      setError(e.message);
      setConfirming(false);
    }
  }

  if (loading) return <div className="rev-page"><Loader /></div>;
  if (error) return (
    <div className="rev-page rev-page--error">
      <p>Error: <strong>{error}</strong></p>
      <button className="btn btn-secondary" onClick={load}>Retry</button>
    </div>
  );
  if (!scan) return null;

  const items = scan.scan_ingredients ?? [];
  const accepted   = items.filter(i => i.user_accepted === true);
  const rejected   = items.filter(i => i.user_accepted === false);
  const pending    = items.filter(i => i.user_accepted === null);
  const highConf   = items.filter(i => i.user_accepted === null && (i.match_confidence ?? 0) >= 0.95);
  const needReview = items.filter(i => i.user_accepted === null && (i.match_confidence ?? 0) < 0.95 && i.candidate_ingredient_id != null);
  const unmatched  = items.filter(i => i.candidate_ingredient_id == null);

  const canConfirm = accepted.length > 0;

  return (
    <main className="rev-page">
      <nav className="rev-breadcrumb">
        <Link to="/">Home</Link>
        <span>›</span>
        <Link to="/scan">Scan</Link>
        <span>›</span>
        <span>Review</span>
      </nav>

      <header className="rev-header">
        <div>
          <h1 className="rev-title">Review extracted ingredients</h1>
          <p className="rev-sub">
            OCR confidence: {scan.ocr_confidence != null
              ? `${Math.round(scan.ocr_confidence * 100)}%`
              : 'N/A'
            }
            {' · '}Status: <strong>{scan.review_status.replace('_', ' ')}</strong>
          </p>
        </div>
        <button
          className="btn btn-primary rev-confirm-btn"
          onClick={handleConfirm}
          disabled={!canConfirm || confirming}
        >
          {confirming ? 'Confirming…' : 'Confirm & analyse →'}
        </button>
      </header>

      {/* Stats bar */}
      <div className="rev-stats">
        <div className="rev-stat"><strong>{items.length}</strong> total</div>
        <div className="rev-stat rev-stat--ok"><strong>{accepted.length}</strong> accepted</div>
        <div className="rev-stat rev-stat--warn"><strong>{needReview.length}</strong> need review</div>
        <div className="rev-stat rev-stat--mute"><strong>{rejected.length}</strong> rejected</div>
        <div className="rev-stat rev-stat--mute"><strong>{unmatched.length}</strong> unmatched</div>
      </div>

      {error && <div className="rev-error">{error}</div>}

      {/* OCR raw text */}
      {scan.ocr_raw_text && (
        <details className="rev-raw">
          <summary>View raw OCR text</summary>
          <pre>{scan.ocr_raw_text}</pre>
        </details>
      )}

      {/* Auto-accepted (high confidence) */}
      {highConf.length > 0 && (
        <section className="rev-section">
          <h2 className="rev-section__title">
            High-confidence matches <span className="rev-count">({highConf.length})</span>
          </h2>
          <p className="rev-section__hint">
            Confidence ≥ 95 % — automatically matched. You can still reject any.
          </p>
          {highConf.map(si => (
            <div key={si.id} className="rev-item rev-item--high">
              <div className="rev-item__tokens">
                <span className="rev-item__raw">{si.raw_token}</span>
                <span className="rev-item__arrow">→</span>
                <span className="rev-item__match">{si.ingredient?.name ?? si.normalized_token}</span>
                {si.ingredient?.function && <span className="rev-item__fn">{si.ingredient.function}</span>}
              </div>
              <div className="rev-item__actions">
                <span className="rev-conf">{Math.round((si.match_confidence ?? 0) * 100)}%</span>
                <button className="rev-btn rev-btn--accept active" onClick={() => handleAccept(si)}>✓ Accept</button>
                <button className="rev-btn rev-btn--reject" onClick={() => handleReject(si)}>✕ Reject</button>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Need review */}
      {needReview.length > 0 && (
        <section className="rev-section">
          <h2 className="rev-section__title">
            Review required <span className="rev-count">({needReview.length})</span>
          </h2>
          <p className="rev-section__hint">
            Confidence below 95 % — please accept or reject each match.
          </p>
          {needReview.map(si => (
            <div key={si.id} className="rev-item rev-item--review">
              <div className="rev-item__tokens">
                <span className="rev-item__raw">{si.raw_token}</span>
                <span className="rev-item__arrow">→</span>
                <span className="rev-item__match">{si.ingredient?.name ?? si.normalized_token}</span>
                {si.ingredient?.function && <span className="rev-item__fn">{si.ingredient.function}</span>}
              </div>
              <div className="rev-item__actions">
                <span className="rev-conf rev-conf--warn">{Math.round((si.match_confidence ?? 0) * 100)}%</span>
                <button className="rev-btn rev-btn--accept" onClick={() => handleAccept(si)}>✓ Accept</button>
                <button className="rev-btn rev-btn--reject" onClick={() => handleReject(si)}>✕ Reject</button>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Unmatched */}
      {unmatched.length > 0 && (
        <section className="rev-section">
          <h2 className="rev-section__title rev-section__title--warn">
            Reference review needed <span className="rev-count">({unmatched.length})</span>
          </h2>
          <p className="rev-section__hint">
            These label ingredients are not yet in the reference library. Accept one to keep it in your analysis with a clear “reference pending” note, or reject it if it is not an ingredient.
          </p>
          {unmatched.map(si => (
            <div key={si.id} className="rev-item rev-item--unmatched">
              <span className="rev-item__raw">{si.raw_token}</span>
              <div className="rev-item__actions">
                <span className="rev-unmatched-label">Reference pending</span>
                <button className="rev-btn rev-btn--accept" onClick={() => handleAccept(si)}>✓ Include</button>
                <button className="rev-btn rev-btn--reject" onClick={() => handleReject(si)}>✕ Reject</button>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Accepted */}
      {accepted.length > 0 && (
        <section className="rev-section">
          <h2 className="rev-section__title rev-section__title--ok">
            Accepted <span className="rev-count">({accepted.length})</span>
          </h2>
          {accepted.map(si => (
            <div key={si.id} className="rev-item rev-item--accepted">
              <div className="rev-item__tokens">
                <span className="rev-item__raw">{si.raw_token}</span>
                <span className="rev-item__arrow">→</span>
                <span className="rev-item__match">{si.ingredient?.name ?? si.normalized_token}</span>
              </div>
              <button className="rev-btn rev-btn--reject" onClick={() => handleReject(si)}>✕ Remove</button>
            </div>
          ))}
        </section>
      )}

      {/* Rejected */}
      {rejected.length > 0 && (
        <section className="rev-section rev-section--dim">
          <h2 className="rev-section__title">
            Rejected <span className="rev-count">({rejected.length})</span>
          </h2>
          {rejected.map(si => (
            <div key={si.id} className="rev-item rev-item--rejected">
              <span className="rev-item__raw">{si.raw_token}</span>
              <button className="rev-btn rev-btn--accept" onClick={() => handleAccept(si)}>↩ Restore</button>
            </div>
          ))}
        </section>
      )}

      <div className="rev-bottom">
        {!canConfirm && (
          <p className="rev-bottom__hint">Accept at least one ingredient before confirming.</p>
        )}
        <button
          className="btn btn-primary"
          onClick={handleConfirm}
          disabled={!canConfirm || confirming}
        >
          {confirming ? 'Confirming…' : 'Confirm & analyse →'}
        </button>
      </div>
    </main>
  );
}

export default ScanReview;
