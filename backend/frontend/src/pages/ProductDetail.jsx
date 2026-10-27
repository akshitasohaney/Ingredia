import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import Loader from '../components/Loader.jsx';
import { getProduct } from '../api.js';
import './ProductDetail.css';

function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getProduct(id)
      .then(setProduct)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="pd-page"><Loader /></div>;

  if (error) return (
    <div className="pd-page pd-page--error">
      <p>Could not load product: <strong>{error}</strong></p>
      <button className="btn btn-secondary" onClick={() => { setError(null); setLoading(true); getProduct(id).then(setProduct).catch(e => setError(e.message)).finally(() => setLoading(false)); }}>
        Retry
      </button>
      <Link to="/" className="btn btn-primary" style={{ marginLeft: 12 }}>Home</Link>
    </div>
  );

  if (!product) return null;

  return (
    <main className="pd-page">
      <nav className="pd-breadcrumb">
        <Link to="/">Home</Link>
        <span>›</span>
        <Link to={`/search?query=${encodeURIComponent(product.brand ?? product.name)}`}>
          {product.brand ?? 'Products'}
        </Link>
        <span>›</span>
        <span>{product.name}</span>
      </nav>

      <header className="pd-header">
        <div className="pd-header__info">
          {product.product_type && <div className="pd-header__type">{product.product_type}</div>}
          <h1 className="pd-header__name">{product.name}</h1>
          {product.brand && <p className="pd-header__brand">{product.brand}</p>}
          {product.intended_use && <p className="pd-header__use">{product.intended_use}</p>}
          {product.notes && <p className="pd-header__notes">{product.notes}</p>}
        </div>

        {/* CTA */}
        <div className="pd-header__actions">
          <button
            className="btn btn-primary pd-analyze-btn"
            onClick={() => navigate(`/product/${id}/risk`)}
          >
            Analyse Ingredients
          </button>
          <span className="pd-analyze-hint">
            Evidence-based breakdown of all {product.product_ingredients?.length ?? 0} ingredients
          </span>
        </div>
      </header>

      {/* Ingredient list preview */}
      <section className="pd-ingredients">
        <h2 className="pd-section-title">
          Ingredients ({product.product_ingredients?.length ?? 0})
        </h2>
        <p className="pd-ing-note">
          Listed in the order they appear on the label. Position indicates listing
          sequence only — it does not imply concentration.
        </p>

        {(!product.product_ingredients || product.product_ingredients.length === 0) ? (
          <p className="pd-empty">No ingredients recorded for this product.</p>
        ) : (
          <div className="pd-ing-list">
            {product.product_ingredients.map((pi) => {
              const ing = pi.ingredient;
              return (
                <Link
                  key={pi.id}
                  to={ing ? `/ingredient/${ing.id}` : '#'}
                  className={`pd-ing-row ${!ing ? 'pd-ing-row--unmatched' : ''}`}
                >
                  <div className="pd-ing-row__left">
                    <span className="pd-ing-row__pos">{pi.position ?? '—'}</span>
                    <div>
                      <span className="pd-ing-row__name">
                        {ing ? ing.name : (pi.raw_name ?? 'Unknown')}
                      </span>
                      {ing?.function && (
                        <span className="pd-ing-row__fn">{ing.function}</span>
                      )}
                    </div>
                  </div>
                  <div className="pd-ing-row__right">
                    {ing?.is_fragrance && <span className="pill pill--warn">Fragrance</span>}
                    {ing?.is_allergen && <span className="pill pill--warn">Allergen</span>}
                    {!ing && <span className="pill pill--unknown">Unidentified</span>}
                    {ing && <span className="pd-ing-row__arrow">→</span>}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      <div className="pd-bottom-cta">
        <button
          className="btn btn-primary"
          onClick={() => navigate(`/product/${id}/risk`)}
        >
          Full ingredient analysis →
        </button>
      </div>
    </main>
  );
}

export default ProductDetail;
