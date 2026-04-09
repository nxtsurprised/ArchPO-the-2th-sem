import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { workflowApi } from '../api/workflow';
import Spinner from '../components/Spinner';
import ErrorMessage from '../components/ErrorMessage';
import StatusBadge from '../components/StatusBadge';

const APPROVAL_TYPE_LABELS = {
  tz_final: 'Финальное согласование ТЗ',
  nmck_final: 'Финальное согласование НМЦК',
  review: 'Рецензирование',
};

const DECISION_LABELS = {
  approve: 'Утвердить',
  reject: 'Отклонить',
  revision: 'На доработку',
  review: 'Рецензия',
};

const ROLE_LABELS = {
  pm: 'Менеджер проекта',
  analyst: 'Аналитик',
  admin: 'Администратор',
  superadmin: 'Системный администратор',
};

const SIDE_LABELS = {
  customer: 'Заказчик',
  contractor: 'Подрядчик',
};

const DECISION_STATUS_MAP = {
  approve: 'approved',
  reject: 'rejected',
  revision: 'revision',
  review: 'review',
};

export default function ApprovalDetailPage() {
  const { id: projectId, approvalId } = useParams();
  const navigate = useNavigate();
  const { user, getRoleForProject } = useAuth();

  const [approval, setApproval] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState('');

  // Decision modal state
  const [decisionModal, setDecisionModal] = useState(null); // 'approve' | 'reject' | 'revision' | 'review' | null
  const [comment, setComment] = useState('');

  const roleInfo = getRoleForProject(projectId);
  const userRole = roleInfo?.role;
  const userId = user?.id;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await workflowApi.getApproval(approvalId);
      setApproval(res.data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [approvalId]);

  useEffect(() => {
    load();
  }, [load]);

  // ── Derived state ─────────────────────────────────────────────────────────────

  const isFinished = approval && ['approved', 'rejected', 'cancelled'].includes(approval.status);
  const isPending = approval?.status === 'pending';
  const isRevision = approval?.status === 'revision';

  // Find the active round
  const activeRound = approval?.rounds?.find(
    (r) => r.status === 'active' && r.round_number === approval.current_round
  );

  // Has the current user already decided (non-review) this round?
  const myDecision = activeRound?.decisions?.find(
    (d) => d.user_id === userId && d.decision_type !== 'review'
  );
  const myReview = activeRound?.decisions?.find(
    (d) => d.user_id === userId && d.decision_type === 'review'
  );

  // Permission checks
  // When status is 'revision', the backend auto-creates a new round on the first decide() call,
  // so we allow binding decisions in revision state too.
  const canMakeBindingDecision =
    (isPending || isRevision) &&
    !myDecision &&
    (userRole === 'pm' || user?.is_superadmin);

  const canReview =
    (isPending || isRevision) &&
    !myReview &&
    approval?.type !== 'nmck_final' &&
    (userRole === 'pm' || userRole === 'analyst' || user?.is_superadmin);

  const canRevoke =
    isPending &&
    !!myDecision &&
    (userRole === 'pm' || user?.is_superadmin);

  const canCancel =
    (isPending || isRevision) &&
    (userRole === 'pm' || userRole === 'admin' || user?.is_superadmin);

  // ── Actions ───────────────────────────────────────────────────────────────────

  const handleDecision = async () => {
    if (!decisionModal) return;
    setActionLoading(true);
    setActionError('');
    try {
      await workflowApi.decide(approvalId, decisionModal, comment || undefined);
      setDecisionModal(null);
      setComment('');
      await load();
    } catch (err) {
      setActionError(
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Ошибка при принятии решения'
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevoke = async () => {
    setActionLoading(true);
    setActionError('');
    try {
      await workflowApi.revoke(approvalId);
      await load();
    } catch (err) {
      setActionError(
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Ошибка при отзыве решения'
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    setActionLoading(true);
    setActionError('');
    try {
      await workflowApi.cancel(approvalId);
      await load();
    } catch (err) {
      setActionError(
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Ошибка при отмене согласования'
      );
    } finally {
      setActionLoading(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────────

  if (loading) return <Spinner center />;
  if (error) return <ErrorMessage error={error} onRetry={load} />;
  if (!approval) return null;

  const rounds = [...(approval.rounds || [])].sort((a, b) => a.round_number - b.round_number);

  return (
    <div>
      {/* Breadcrumb */}
      <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 8 }}>
        <Link to="/">Проекты</Link>
        {' / '}
        <Link to={`/projects/${projectId}?tab=approvals`}>Согласования</Link>
        {' / '}
        Согласование
      </div>

      {/* Header */}
      <div className="page-header" style={{ alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">
            {APPROVAL_TYPE_LABELS[approval.type] || approval.type}
          </h1>
          <p className="page-subtitle" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <StatusBadge status={approval.status} />
            <span>Раунд {approval.current_round}</span>
            {approval.is_locked && (
              <span style={{ color: 'var(--status-pending)', fontSize: 12, fontWeight: 600 }}>
                🔒 Документ заблокирован
              </span>
            )}
          </p>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {canMakeBindingDecision && (
            <>
              <button
                className="btn btn-primary"
                onClick={() => { setDecisionModal('approve'); setComment(''); setActionError(''); }}
                disabled={actionLoading}
              >
                Утвердить
              </button>
              <button
                className="btn"
                style={{ background: 'var(--status-revision)', color: '#fff', border: 'none' }}
                onClick={() => { setDecisionModal('revision'); setComment(''); setActionError(''); }}
                disabled={actionLoading}
              >
                На доработку
              </button>
              <button
                className="btn btn-danger"
                onClick={() => { setDecisionModal('reject'); setComment(''); setActionError(''); }}
                disabled={actionLoading}
              >
                Отклонить
              </button>
            </>
          )}
          {canReview && (
            <button
              className="btn btn-secondary"
              onClick={() => { setDecisionModal('review'); setComment(''); setActionError(''); }}
              disabled={actionLoading}
            >
              Оставить рецензию
            </button>
          )}
          {canRevoke && (
            <button
              className="btn btn-secondary"
              onClick={handleRevoke}
              disabled={actionLoading}
            >
              {actionLoading ? 'Отзыв...' : 'Отозвать решение'}
            </button>
          )}
          {canCancel && (
            <button
              className="btn btn-secondary"
              style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}
              onClick={handleCancel}
              disabled={actionLoading}
            >
              {actionLoading ? 'Отмена...' : 'Отменить согласование'}
            </button>
          )}
        </div>
      </div>

      {isRevision && (
        <div style={{ background: '#fefce8', border: '1px solid #fde68a', borderRadius: 6, padding: '10px 14px', fontSize: 13, color: '#92400e', marginBottom: 16 }}>
          Документ отправлен на доработку. После исправлений примите решение — автоматически откроется раунд {(approval.current_round ?? 0) + 1}.
        </div>
      )}

      {actionError && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          {actionError}
        </div>
      )}

      {/* Info block */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="grid-2" style={{ gap: 16 }}>
          <div>
            <div className="form-label">Документ</div>
            <div style={{ fontFamily: 'monospace', fontSize: 13 }}>
              <Link to={`/projects/${projectId}/documents/${approval.document_id}`}>
                {approval.document_id}
              </Link>
            </div>
          </div>
          <div>
            <div className="form-label">Тип согласования</div>
            <div>{APPROVAL_TYPE_LABELS[approval.type] || approval.type}</div>
          </div>
          <div>
            <div className="form-label">Инициатор</div>
            <div style={{ fontFamily: 'monospace', fontSize: 13 }}>
              {approval.initiated_by}
              <span style={{ color: 'var(--color-text-secondary)', marginLeft: 6 }}>
                ({SIDE_LABELS[approval.initiated_by_side] || approval.initiated_by_side})
              </span>
            </div>
          </div>
          <div>
            <div className="form-label">Создано</div>
            <div style={{ fontSize: 13 }}>
              {approval.created_at
                ? new Date(approval.created_at).toLocaleString('ru-RU')
                : '—'}
            </div>
          </div>
        </div>
      </div>

      {/* Rounds history */}
      <h2 className="section-title">История раундов</h2>

      {rounds.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-text">Раундов пока нет</div>
        </div>
      ) : (
        rounds.map((round) => (
          <RoundCard
            key={round.id}
            round={round}
            userId={userId}
            isActive={round.id === activeRound?.id}
          />
        ))
      )}

      {/* Decision modal */}
      {decisionModal && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 440 }}>
            <h3 className="modal-title">
              {DECISION_LABELS[decisionModal]}
            </h3>

            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="form-label">
                Комментарий{decisionModal === 'revision' ? ' (обязателен)' : ' (необязателен)'}
              </label>
              <textarea
                className="form-input form-textarea"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Введите комментарий..."
                rows={4}
                autoFocus
              />
            </div>

            {actionError && (
              <div className="alert alert-error" style={{ marginBottom: 12 }}>
                {actionError}
              </div>
            )}

            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => { setDecisionModal(null); setActionError(''); }}
                disabled={actionLoading}
              >
                Отмена
              </button>
              <button
                className={`btn ${decisionModal === 'reject' ? 'btn-danger' : 'btn-primary'}`}
                onClick={handleDecision}
                disabled={actionLoading || (decisionModal === 'revision' && !comment.trim())}
              >
                {actionLoading ? 'Сохранение...' : 'Подтвердить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Round Card ────────────────────────────────────────────────────────────────

function RoundCard({ round, userId, isActive }) {
  const decisions = round.decisions || [];
  const nonReview = decisions.filter((d) => d.decision_type !== 'review');
  const reviews = decisions.filter((d) => d.decision_type === 'review');

  return (
    <div
      className="card"
      style={{
        marginBottom: 16,
        borderLeft: `4px solid ${isActive ? 'var(--color-primary)' : 'var(--color-border)'}`,
      }}
    >
      {/* Round header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 15 }}>
          Раунд {round.round_number}
          {isActive && (
            <span style={{ marginLeft: 10, fontSize: 12, color: 'var(--color-primary)', fontWeight: 400 }}>
              (активный)
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <StatusBadge status={round.status} />
          {round.final_decision && (
            <StatusBadge status={round.final_decision} />
          )}
        </div>
      </div>

      {/* Dates */}
      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 12 }}>
        Начат: {new Date(round.started_at).toLocaleString('ru-RU')}
        {round.completed_at && (
          <> &middot; Завершён: {new Date(round.completed_at).toLocaleString('ru-RU')}</>
        )}
      </div>

      {/* Binding decisions */}
      {nonReview.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div className="form-label" style={{ marginBottom: 6 }}>Решения</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {nonReview.map((d) => (
              <DecisionRow key={d.id} decision={d} isMine={d.user_id === userId} />
            ))}
          </div>
        </div>
      )}

      {/* Reviews */}
      {reviews.length > 0 && (
        <div>
          <div className="form-label" style={{ marginBottom: 6 }}>Рецензии</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {reviews.map((d) => (
              <DecisionRow key={d.id} decision={d} isMine={d.user_id === userId} />
            ))}
          </div>
        </div>
      )}

      {decisions.length === 0 && (
        <div style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
          Решений пока нет
        </div>
      )}
    </div>
  );
}

// ─── Decision Row ──────────────────────────────────────────────────────────────

function DecisionRow({ decision, isMine }) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        alignItems: 'flex-start',
        padding: '8px 12px',
        borderRadius: 6,
        background: isMine ? 'var(--color-bg)' : 'transparent',
        border: '1px solid var(--color-border)',
      }}
    >
      <div style={{ flexShrink: 0 }}>
        <StatusBadge status={DECISION_STATUS_MAP[decision.decision_type] || decision.decision_type} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 2 }}>
          <span style={{ fontWeight: 600 }}>{ROLE_LABELS[decision.user_role] || decision.user_role}</span>
          {' · '}
          <span>{SIDE_LABELS[decision.user_side] || decision.user_side}</span>
          {isMine && (
            <span style={{ marginLeft: 6, color: 'var(--color-primary)', fontWeight: 600 }}>
              (вы)
            </span>
          )}
          <span style={{ float: 'right' }}>
            {new Date(decision.decided_at).toLocaleString('ru-RU')}
          </span>
        </div>
        {decision.comment && (
          <div style={{ fontSize: 13, color: 'var(--color-text)', marginTop: 4 }}>
            {decision.comment}
          </div>
        )}
      </div>
    </div>
  );
}
