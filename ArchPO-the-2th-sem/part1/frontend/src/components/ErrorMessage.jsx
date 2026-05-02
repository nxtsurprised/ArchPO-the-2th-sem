import React from 'react';

export default function ErrorMessage({ error, onRetry }) {
  let message = 'Произошла ошибка';

  if (typeof error === 'string') {
    message = error;
  } else if (error?.response?.data?.detail) {
    const detail = error.response.data.detail;
    if (typeof detail === 'string') {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
    } else {
      message = JSON.stringify(detail);
    }
  } else if (error?.message) {
    message = error.message;
  }

  return (
    <div
      style={{
        background: '#fef2f2',
        border: '1px solid #fecaca',
        borderRadius: '8px',
        padding: '16px',
        color: '#dc2626',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
      }}
    >
      <span style={{ fontSize: '18px', flexShrink: 0 }}>&#9888;</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 500, marginBottom: onRetry ? '8px' : 0 }}>{message}</div>
        {onRetry && (
          <button
            onClick={onRetry}
            style={{
              background: 'none',
              border: 'none',
              color: '#dc2626',
              textDecoration: 'underline',
              cursor: 'pointer',
              padding: 0,
              fontSize: '13px',
            }}
          >
            Попробовать снова
          </button>
        )}
      </div>
    </div>
  );
}
