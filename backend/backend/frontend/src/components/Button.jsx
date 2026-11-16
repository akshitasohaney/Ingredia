import React from 'react';
import './Button.css';

function Button({ children, onClick, type = 'button', variant = 'primary', className = '' }) {
  return (
    <button
      type={type}
      onClick={onClick}
      className={`btn btn-${variant} ${className}`.trim()}
    >
      {children}
    </button>
  );
}

export default Button;
