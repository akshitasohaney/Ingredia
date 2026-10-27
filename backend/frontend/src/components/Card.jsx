import React from 'react';
import './Card.css';

function Card({ children, className = '' }) {
  return <div className={`card ${className}`.trim()}>{children}</div>;
}

export default Card;
