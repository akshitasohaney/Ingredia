import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import Loader from '../components/Loader.jsx';
import { listProducts, searchProducts } from '../api.js';
import './ProductSearchResults.css';

function ProductSearchResults() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('query') || '';
  const [inputVal, setInputVal] = useState(query);
  const navigate = useNavigate();

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const loadProducts = query ? () => searchProducts(query) : () => listProducts();
    loadProducts()
      .then(setProducts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [query]);

  function handleSearch(e) {
    e.preventDefault();
    const q = inputVal.trim();
    if (q) navigate(`/search?query=${encodeURIComponent(q)}`);
  }

  return (
    <main className="sr-page">
      <div className="sr-header">
        <h1 className="sr-title">
          {query ? `Results for "${query}"` : 'Product Search'}
        </h1>

        {/* Inline search to refine */}
        <form className="sr-refine" onSubmit={handleSearch}>
          <input
            className="sr-refine__input"
            type="search"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Refine search…"
            aria-label="Refine search"
          />
          <button className="btn btn-secondary sr-refine__btn" type="submit">
            Search
          </button>
        </form>
      </div>

      {loading && (
        <div className="sr-state">
          <Loader />
          <p>Searching…</p>
        </div>
      )}

      {error && (
        <div className="sr-state sr-state--error">
          <p>Could not load results: <strong>{error}</strong></p>
          <button className="btn btn-secondary" onClick={() => navigate(`/search?query=${encodeURIComponent(query)}`)}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && products.length === 0 && (
        <div className="sr-state">
          <p>{query ? <>No products found for "<strong>{query}</strong>".</> : 'No products are available yet.'}</p>
          <p className="sr-state__hint">
            Try a different name or brand, or{' '}
            <Link to="/scan">upload a label image</Link>.
          </p>
        </div>
      )}

      {!loading && !error && (
        <div className="sr-grid">
          {products.map((p) => (
            <Link key={p.id} to={`/product/${p.id}`} className="sr-card">
              <div className="sr-card__type">{p.product_type ?? 'Product'}</div>
              <h2 className="sr-card__name">{p.name}</h2>
              {p.brand && <p className="sr-card__brand">{p.brand}</p>}
              {p.intended_use && (
                <p className="sr-card__use">{p.intended_use}</p>
              )}
              <span className="sr-card__cta">View analysis →</span>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}

export default ProductSearchResults;
