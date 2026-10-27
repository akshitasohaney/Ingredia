import React from 'react';
import './Input.css';

function Input({ value, onChange, placeholder = '', type = 'text', ariaLabel }) {
  return (
    <input
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className="input"
      aria-label={ariaLabel}
    />
  );
}

export default Input;
