import React, { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import './Header.css';

function Header() {
  const [q, setQ] = useState('');
  const navigate = useNavigate();

  function handleSearch(e) {
    e.preventDefault();
    const query = q.trim();
    if (query) { navigate(`/search?query=${encodeURIComponent(query)}`); setQ(''); }
  }

  return (
    <header className="site-header">
      <div className="site-header__inner">
        {/* Logo */}
        <Link to="/" className="site-header__logo">
          Ingredia
        </Link>

        {/* Nav */}
        <nav className="site-header__nav">
          <NavLink to="/" end className={({ isActive }) => `hdr-link${isActive ? ' hdr-link--active' : ''}`}>
            Home
          </NavLink>
          <NavLink to="/search" className={({ isActive }) => `hdr-link${isActive ? ' hdr-link--active' : ''}`}>
            Products
          </NavLink>
          <NavLink to="/scan" className={({ isActive }) => `hdr-link${isActive ? ' hdr-link--active' : ''}`}>
            Scan label
          </NavLink>
        </nav>

        {/* Inline quick search */}
        <form className="site-header__search" onSubmit={handleSearch}>
          <input
            className="site-header__search-input"
            type="search"
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search products…"
            aria-label="Quick product search"
          />
        </form>
      </div>
    </header>
  );
}

export default Header;
