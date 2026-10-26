import React from 'react';
import { Link } from 'react-router-dom';
import './Footer.css';

function Footer() {
  return (
    <footer className="site-footer">
      <div className="container">
        <p>© 2026 Ingredia. All rights reserved.</p>
        <nav className="footer-nav">
          <Link to="/privacy" className="footer-link">Privacy</Link>
          <Link to="/terms" className="footer-link">Terms</Link>
        </nav>
      </div>
    </footer>
  );
}

export default Footer;
