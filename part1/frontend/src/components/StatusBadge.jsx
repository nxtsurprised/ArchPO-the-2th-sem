import React from 'react';

const STATUS_MAP = {
  pending: { label: 'На согласовании', color: 'var(--status-pending)', bg: 'var(--status-pending-bg)' },
  approved: { label: 'Утверждён', color: 'var(--status-approved)', bg: 'var(--status-approved-bg)' },
  rejected: { label: 'Отклонён', color: 'var(--status-rejected)', bg: 'var(--status-rejected-bg)' },
  revision: { label: 'На доработке', color: 'var(--status-revision)', bg: 'var(--status-revision-bg)' },
  cancelled: { label: 'Отменён', color: 'var(--status-cancelled)', bg: 'var(--status-cancelled-bg)' },
  draft: { label: 'Черновик', color: 'var(--status-draft)', bg: 'var(--status-draft-bg)' },
  review: { label: 'На рассмотрении', color: 'var(--status-review)', bg: 'var(--status-review-bg)' },
  active: { label: 'Активен', color: 'var(--status-approved)', bg: 'var(--status-approved-bg)' },
  inactive: { label: 'Неактивен', color: 'var(--status-cancelled)', bg: 'var(--status-cancelled-bg)' },
  // function priorities
  high: { label: 'Высокий', color: 'var(--status-rejected)', bg: 'var(--status-rejected-bg)' },
  medium: { label: 'Средний', color: 'var(--status-pending)', bg: 'var(--status-pending-bg)' },
  low: { label: 'Низкий', color: 'var(--status-approved)', bg: 'var(--status-approved-bg)' },
};

export default function StatusBadge({ status, customLabel }) {
  const key = (status || '').toLowerCase();
  const info = STATUS_MAP[key] || {
    label: customLabel || status || 'Неизвестно',
    color: 'var(--status-cancelled)',
    bg: 'var(--status-cancelled-bg)',
  };

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 10px',
        borderRadius: '9999px',
        fontSize: '12px',
        fontWeight: 600,
        color: info.color,
        background: info.bg,
        whiteSpace: 'nowrap',
      }}
    >
      {customLabel || info.label}
    </span>
  );
}
