import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { catalogApi } from '../api/catalog';
import { useAuth } from '../contexts/AuthContext';
import Spinner from '../components/Spinner';
import ErrorMessage from '../components/ErrorMessage';
import StatusBadge from '../components/StatusBadge';

const CATEGORY_LABELS = {
  main: 'Основная',
  auxiliary: 'Вспомогательная',
  service: 'Сервисная',
};

const PRIORITY_LABELS = {
  high: 'Высокий',
  medium: 'Средний',
  low: 'Низкий',
};

export default function FunctionDetailPage() {
  const { id: projectId, funcId } = useParams();
  const { getRoleForProject, user } = useAuth();
  const navigate = useNavigate();

  const [fn, setFn] = useState(null);
  const [subsystems, setSubsystems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  const roleInfo = getRoleForProject(projectId);
  const userRole = roleInfo?.role;
  const canEdit = ['pm', 'analyst', 'admin'].includes(userRole) || user?.is_superadmin;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [fnRes, subRes] = await Promise.all([
        catalogApi.getFunction(funcId),
        catalogApi.getSubsystems(projectId),
      ]);
      setFn(fnRes.data);
      setSubsystems(subRes.data.items || []);
      setForm({
        code: fnRes.data.code || '',
        name: fnRes.data.name || '',
        category: fnRes.data.category || '',
        priority: fnRes.data.priority || '',
        description: fnRes.data.description || '',
        subsystem_id: fnRes.data.subsystem_id || '',
      });
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [funcId, projectId]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!form.code.trim() || !form.name.trim()) {
      setSaveError('Код и наименование обязательны');
      return;
    }
    setSaving(true);
    setSaveError('');
    try {
      const res = await catalogApi.updateFunction(funcId, {
        ...form,
        subsystem_id: form.subsystem_id || undefined,
        category: form.category || undefined,
        priority: form.priority || undefined,
      });
      setFn(res.data);
      setEditing(false);
    } catch (err) {
      setSaveError(err?.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (!fn) return;
    setForm({
      code: fn.code || '',
      name: fn.name || '',
      category: fn.category || '',
      priority: fn.priority || '',
      description: fn.description || '',
      subsystem_id: fn.subsystem_id || '',
    });
    setSaveError('');
    setEditing(false);
  };

  if (loading) return <Spinner center />;
  if (error) return <ErrorMessage error={error} onRetry={load} />;
  if (!fn) return null;

  const subsystemMap = Object.fromEntries(subsystems.map((s) => [s.id, s]));
  const subsystem = subsystemMap[fn.subsystem_id];

  return (
    <div>
      {/* Breadcrumb */}
      <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 16 }}>
        <Link to="/">Проекты</Link>
        {' / '}
        <Link to={`/projects/${projectId}?tab=functions`}>Функции</Link>
        {' / '}
        <span>{fn.code} — {fn.name}</span>
      </div>

      {/* Page header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">{fn.name}</h1>
          <p className="page-subtitle" style={{ fontFamily: 'monospace' }}>{fn.code}</p>
        </div>
        <div className="actions-row">
          {!editing && (
            <button className="btn btn-secondary" onClick={() => navigate(`/projects/${projectId}?tab=functions`)}>
              ← Назад к функциям
            </button>
          )}
          {canEdit && !editing && (
            <button className="btn btn-primary" onClick={() => setEditing(true)}>
              Редактировать
            </button>
          )}
          {editing && (
            <>
              <button className="btn btn-secondary" onClick={handleCancel} disabled={saving}>
                Отмена
              </button>
              <button className="btn btn-success" onClick={handleSave} disabled={saving}>
                {saving ? 'Сохранение...' : 'Сохранить'}
              </button>
            </>
          )}
        </div>
      </div>

      {saveError && (
        <div className="mb-16">
          <ErrorMessage error={saveError} />
        </div>
      )}

      {/* Main info card */}
      <div className="card mb-16">
        <h2 className="section-title">Основная информация</h2>

        {editing ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Код *</label>
                <input
                  className="form-input"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Подсистема</label>
                <select
                  className="form-select"
                  value={form.subsystem_id}
                  onChange={(e) => setForm({ ...form, subsystem_id: e.target.value })}
                >
                  <option value="">Не указана</option>
                  {subsystems.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Наименование *</label>
              <input
                className="form-input"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Категория</label>
                <select
                  className="form-select"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                >
                  <option value="">Не указана</option>
                  <option value="main">Основная</option>
                  <option value="auxiliary">Вспомогательная</option>
                  <option value="service">Сервисная</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Приоритет</label>
                <select
                  className="form-select"
                  value={form.priority}
                  onChange={(e) => setForm({ ...form, priority: e.target.value })}
                >
                  <option value="">Не указан</option>
                  <option value="high">Высокий</option>
                  <option value="medium">Средний</option>
                  <option value="low">Низкий</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Описание</label>
              <textarea
                className="form-input form-textarea"
                rows={4}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
          </div>
        ) : (
          <div className="detail-grid">
            <div className="detail-field">
              <span className="detail-field-label">Код</span>
              <span className="detail-field-value font-mono">{fn.code}</span>
            </div>
            <div className="detail-field">
              <span className="detail-field-label">Подсистема</span>
              <span className="detail-field-value">{subsystem?.name || '—'}</span>
            </div>
            <div className="detail-field" style={{ gridColumn: '1 / -1' }}>
              <span className="detail-field-label">Наименование</span>
              <span className="detail-field-value">{fn.name}</span>
            </div>
            <div className="detail-field">
              <span className="detail-field-label">Категория</span>
              <span className="detail-field-value">{CATEGORY_LABELS[fn.category] || fn.category || '—'}</span>
            </div>
            <div className="detail-field">
              <span className="detail-field-label">Приоритет</span>
              <span className="detail-field-value">
                {fn.priority ? (
                  <StatusBadge
                    status={fn.priority}
                    customLabel={PRIORITY_LABELS[fn.priority] || fn.priority}
                  />
                ) : '—'}
              </span>
            </div>
            <div className="detail-field">
              <span className="detail-field-label">Статус</span>
              <span className="detail-field-value">
                {fn.status ? <StatusBadge status={fn.status} /> : '—'}
              </span>
            </div>
            <div className="detail-field" style={{ gridColumn: '1 / -1' }}>
              <span className="detail-field-label">Описание</span>
              <span className="detail-field-value" style={{ whiteSpace: 'pre-wrap' }}>
                {fn.description || <span style={{ color: 'var(--color-text-secondary)' }}>Не указано</span>}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Cost params */}
      {fn.cost_params && Object.keys(fn.cost_params).length > 0 && (
        <div className="card mb-16">
          <h2 className="section-title">Стоимостные параметры</h2>
          <div className="detail-grid">
            {Object.entries(fn.cost_params).map(([key, value]) => (
              <div key={key} className="detail-field">
                <span className="detail-field-label">{key}</span>
                <span className="detail-field-value">{String(value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Additional fields if they exist */}
      {fn.requirements && (
        <div className="card mb-16">
          <h2 className="section-title">Требования</h2>
          {Array.isArray(fn.requirements) ? (
            <ul style={{ paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {fn.requirements.map((req, i) => (
                <li key={i} style={{ fontSize: 14 }}>{typeof req === 'string' ? req : JSON.stringify(req)}</li>
              ))}
            </ul>
          ) : (
            <p style={{ fontSize: 14, whiteSpace: 'pre-wrap' }}>{String(fn.requirements)}</p>
          )}
        </div>
      )}

      {/* ID */}
      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 8 }}>
        ID функции: <span style={{ fontFamily: 'monospace' }}>{fn.id}</span>
      </div>
    </div>
  );
}
