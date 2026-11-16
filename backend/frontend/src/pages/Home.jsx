import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './Home.css';

function Home() {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  function handleSearch(e) {
    e.preventDefault();
    const q = query.trim();
    if (q) navigate(`/search?query=${encodeURIComponent(q)}`);
  }

  return (
    <main className="home">
      {/* Hero */}
      <section className="home-hero">
        <div className="home-hero__tag">Evidence-based ingredient intelligence</div>
        <h1 className="home-hero__headline">
          Know what's<br />in your skincare.
        </h1>
        <p className="home-hero__sub">
          Ingredia analyses the ingredient lists of skincare products and gives you
          clear, evidence-backed information — not marketing language.
        </p>

        {/* Product search */}
        <form className="home-search" onSubmit={handleSearch}>
          <input
            className="home-search__input"
            type="search"
            placeholder="Search by product name or brand…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search products"
          />
          <button className="btn btn-primary home-search__btn" type="submit">
            Search
          </button>
        </form>
      </section>

      {/* Two entry paths */}
      <section className="home-paths">
        <div className="home-paths__card" onClick={() => navigate('/search?query=')}>
          <div className="home-paths__icon">⌕</div>
          <h2>Search a product</h2>
          <p>Find a product by name or brand and view its full ingredient breakdown.</p>
          <span className="btn btn-secondary">Browse products</span>
        </div>

        <div className="home-paths__divider">or</div>

        <div className="home-paths__card" onClick={() => navigate('/scan')}>
          <div className="home-paths__icon">◻</div>
          <h2>Scan a label</h2>
          <p>Upload a photo of a product label and let Ingredia extract and analyse the ingredients.</p>
          <span className="btn btn-secondary">Upload image</span>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="home-disclaimer">
        <p>
          <strong>Important:</strong> Ingredient presence alone does not determine
          product safety or suitability. Concentration, formulation context,
          individual sensitivities, and exposure all matter. Ingredia provides
          informational analysis only — not medical or dermatological advice.
        </p>
      </section>
    </main>
  );
}

export default Home;
