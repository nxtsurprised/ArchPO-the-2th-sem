import React from 'react';

const spinnerStyle = {
  display: 'inline-block',
  width: '24px',
  height: '24px',
  border: '3px solid #e5e7eb',
  borderTop: '3px solid #1a56db',
  borderRadius: '50%',
  animation: 'spin 0.7s linear infinite',
};

const containerStyle = {
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  padding: '40px',
};

// Inject keyframes once
if (typeof document !== 'undefined' && !document.getElementById('spinner-style')) {
  const style = document.createElement('style');
  style.id = 'spinner-style';
  style.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
  document.head.appendChild(style);
}

export default function Spinner({ size = 24, center = false }) {
  const style = {
    ...spinnerStyle,
    width: `${size}px`,
    height: `${size}px`,
  };

  if (center) {
    return (
      <div style={containerStyle}>
        <div style={style} />
      </div>
    );
  }

  return <div style={style} />;
}
