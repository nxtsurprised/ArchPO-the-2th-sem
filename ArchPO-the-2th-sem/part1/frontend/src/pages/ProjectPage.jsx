import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link, useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { catalogApi } from '../api/catalog';
import { workflowApi } from '../api/workflow';
import Spinner from '../components/Spinner';
import ErrorMessage from '../components/ErrorMessage';
import StatusBadge from '../components/StatusBadge';

const TABS = [
  { key: 'dashboard', label: 'Обзор' },
  { key: 'functions', label: 'Функции' },
  { key: 'documents', label: 'Документы' },
  { key: 'approvals', label: 'Согласования' },
  { key: 'tasks', label: 'Мои задачи' },
];

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

const DOC_TYPE_LABELS = {
  tz: 'Техническое задание',
  chtz: 'Частное техническое задание',
  pmi: 'Программа и методика испытаний',
  nmck: 'НМЦК',
};

const APPROVAL_TYPE_LABELS = {
  tz_final: 'Финальное согласование ТЗ',
  nmck_final: 'Финальное согласование НМЦК',
  review: 'Рецензирование',
  standard: 'Стандартное согласование',
};

export default function ProjectPage() {
  const { id: projectId } = useParams();
  const { getRoleForProject, user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const activeTab = searchParams.get('tab') || 'dashboard';

  const roleInfo = getRoleForProject(projectId);
  const userRole = roleInfo?.role;
  const canEdit = ['pm', 'analyst', 'admin'].includes(userRole) || user?.is_superadmin;
  const canManageDocuments = ['pm', 'admin'].includes(userRole) || user?.is_superadmin;

  const setTab = (tab) => {
    setSearchParams({ tab });
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 4 }}>
            <Link to="/">Проекты</Link> / Проект
          </div>
          <h1 className="page-title">
            Проект{' '}
            <span style={{ fontFamily: 'monospace', fontSize: 16 }}>
              {projectId.slice(0, 12)}...
            </span>
          </h1>
          {roleInfo && (
            <p className="page-subtitle">
              Роль: {roleInfo.role} &middot; Сторона: {roleInfo.side}
            </p>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`tab-btn${activeTab === tab.key ? ' active' : ''}`}
            onClick={() => setTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'dashboard' && <DashboardTab projectId={projectId} />}
      {activeTab === 'functions' && (
        <FunctionsTab projectId={projectId} canEdit={canEdit} />
      )}
      {activeTab === 'documents' && (
        <DocumentsTab projectId={projectId} canManage={canManageDocuments} />
      )}
      {activeTab === 'approvals' && <ApprovalsTab projectId={projectId} />}
      {activeTab === 'tasks' && <MyTasksTab projectId={projectId} />}
    </div>
  );
}

// ─── Dashboard Tab ────────────────────────────────────────────────────────────

function DashboardTab({ projectId }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await workflowApi.getDashboard(projectId);
      setStats(res.data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [projectId]);

  if (loading) return <Spinner center />;
  if (error) return <ErrorMessage error={error} onRetry={load} />;
  if (!stats) return null;

  const items = [
    { key: 'total', label: 'Всего согласований', value: stats.total ?? 0, color: 'var(--color-primary)' },
    { key: 'pending', label: 'На согласовании', value: stats.pending ?? 0, color: 'var(--status-pending)' },
    { key: 'approved', label: 'Утверждено', value: stats.approved ?? 0, color: 'var(--status-approved)' },
    { key: 'rejected', label: 'Отклонено', value: stats.rejected ?? 0, color: 'var(--status-rejected)' },
    { key: 'revision', label: 'На доработке', value: stats.revision ?? 0, color: 'var(--status-revision)' },
  ];

  return (
    <div>
      <h2 className="section-title">Статистика по согласованиям</h2>
      <div className="stats-grid">
        {items.map((item) => (
          <div key={item.key} className="stat-card">
            <div className="stat-value" style={{ color: item.color }}>
              {item.value}
            </div>
            <div className="stat-label">{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Functions Tab ────────────────────────────────────────────────────────────

function FunctionsTab({ projectId, canEdit }) {
  const [functions, setFunctions] = useState([]);
  const [subsystems, setSubsystems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [subsystemFilter, setSubsystemFilter] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [deleteId, setDeleteId] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const searchTimer = useRef(null);

  const load = useCallback(async (q = '', subsystemId = '') => {
    setLoading(true);
    setError(null);
    try {
      const [fnRes, subRes] = await Promise.all([
        catalogApi.getFunctions({ project_id: projectId, q: q || undefined, subsystem_id: subsystemId || undefined }),
        catalogApi.getSubsystems(projectId),
      ]);
      setFunctions(fnRes.data.items || []);
      setSubsystems(subRes.data.items || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const handleSearch = (val) => {
    setSearch(val);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => load(val, subsystemFilter), 400);
  };

  const handleSubsystemFilter = (val) => {
    setSubsystemFilter(val);
    load(search, val);
  };

  const handleDelete = async (id) => {
    setDeleting(true);
    try {
      await catalogApi.deleteFunction(id);
      setDeleteId(null);
      load(search, subsystemFilter);
    } catch (err) {
      alert('Ошибка удаления: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setDeleting(false);
    }
  };

  const subsystemMap = Object.fromEntries(subsystems.map((s) => [s.id, s]));

  return (
    <div>
      <div className="page-header">
        <h2 className="section-title" style={{ margin: 0 }}>Функции системы</h2>
        {canEdit && (
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            + Добавить функцию
          </button>
        )}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          className="form-input"
          style={{ maxWidth: 280 }}
          placeholder="Поиск по названию или коду..."
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
        />
        <select
          className="form-select"
          style={{ maxWidth: 200 }}
          value={subsystemFilter}
          onChange={(e) => handleSubsystemFilter(e.target.value)}
        >
          <option value="">Все подсистемы</option>
          {subsystems.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <Spinner center />
      ) : error ? (
        <ErrorMessage error={error} onRetry={() => load(search, subsystemFilter)} />
      ) : functions.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">&#9883;</div>
          <div className="empty-state-text">Функции не найдены</div>
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Код</th>
                <th>Наименование</th>
                <th>Подсистема</th>
                <th>Категория</th>
                <th>Приоритет</th>
                <th>Статус</th>
                {canEdit && <th>Действия</th>}
              </tr>
            </thead>
            <tbody>
              {functions.map((fn) => (
                <tr key={fn.id}>
                  <td>
                    <span style={{ fontFamily: 'monospace', fontSize: 13 }}>{fn.code}</span>
                  </td>
                  <td>
                    <Link to={`/projects/${projectId}/functions/${fn.id}`} style={{ fontWeight: 500 }}>
                      {fn.name}
                    </Link>
                  </td>
                  <td style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
                    {subsystemMap[fn.subsystem_id]?.name || '—'}
                  </td>
                  <td style={{ fontSize: 13 }}>
                    {CATEGORY_LABELS[fn.category] || fn.category || '—'}
                  </td>
                  <td>
                    {fn.priority ? <StatusBadge status={fn.priority} customLabel={PRIORITY_LABELS[fn.priority] || fn.priority} /> : '—'}
                  </td>
                  <td>
                    {fn.status ? <StatusBadge status={fn.status} /> : '—'}
                  </td>
                  {canEdit && (
                    <td>
                      <div className="actions-row">
                        <Link to={`/projects/${projectId}/functions/${fn.id}`} className="btn btn-secondary btn-sm">
                          Открыть
                        </Link>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => setDeleteId(fn.id)}
                        >
                          Удалить
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Function Modal */}
      {showModal && (
        <AddFunctionModal
          projectId={projectId}
          subsystems={subsystems}
          onClose={() => setShowModal(false)}
          onSuccess={() => {
            setShowModal(false);
            load(search, subsystemFilter);
          }}
        />
      )}

      {/* Delete Confirm */}
      {deleteId && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 380 }}>
            <h3 className="modal-title">Удалить функцию?</h3>
            <p style={{ color: 'var(--color-text-secondary)' }}>
              Это действие необратимо. Функция будет удалена вместе со всеми связанными данными.
            </p>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setDeleteId(null)} disabled={deleting}>
                Отмена
              </button>
              <button className="btn btn-danger" onClick={() => handleDelete(deleteId)} disabled={deleting}>
                {deleting ? 'Удаление...' : 'Удалить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AddFunctionModal({ projectId, subsystems, onClose, onSuccess }) {
  const [form, setForm] = useState({
    code: '',
    name: '',
    category: '',
    priority: '',
    description: '',
    subsystem_id: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.code.trim() || !form.name.trim()) {
      setError('Код и наименование обязательны');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await catalogApi.createFunction({
        project_id: projectId,
        ...form,
        subsystem_id: form.subsystem_id || undefined,
        category: form.category || undefined,
        priority: form.priority || undefined,
      });
      onSuccess();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(
        typeof detail === 'string' ? detail :
        Array.isArray(detail) ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ') :
        'Ошибка создания функции'
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h3 className="modal-title">Добавить функцию</h3>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Код *</label>
                <input
                  className="form-input"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="F-001"
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
                placeholder="Название функции"
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
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Краткое описание функции..."
              />
            </div>

            {error && (
              <div style={{ color: 'var(--color-danger)', fontSize: 13 }}>{error}</div>
            )}
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              Отмена
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Сохранение...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Documents Tab ────────────────────────────────────────────────────────────

function DocumentsTab({ projectId, canManage }) {
  const [documents, setDocuments] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [typeFilter, setTypeFilter] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [deleteId, setDeleteId] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async (type = '') => {
    setLoading(true);
    setError(null);
    try {
      const [docRes, tplRes] = await Promise.all([
        catalogApi.getDocuments({ project_id: projectId, type: type || undefined }),
        catalogApi.getTemplates(),
      ]);
      setDocuments(docRes.data.items || []);
      setTemplates(tplRes.data.items || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (id) => {
    setDeleting(true);
    try {
      await catalogApi.deleteDocument(id);
      setDeleteId(null);
      load(typeFilter);
    } catch (err) {
      alert('Ошибка удаления: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h2 className="section-title" style={{ margin: 0 }}>Документы проекта</h2>
        {canManage && (
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            + Создать документ
          </button>
        )}
      </div>

      <div style={{ marginBottom: 16 }}>
        <select
          className="form-select"
          style={{ maxWidth: 200 }}
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); load(e.target.value); }}
        >
          <option value="">Все типы</option>
          <option value="tz">Техническое задание</option>
          <option value="chtz">Частное техническое задание</option>
          <option value="pmi">Программа и методика испытаний</option>
          <option value="nmck">НМЦК</option>
        </select>
      </div>

      {loading ? (
        <Spinner center />
      ) : error ? (
        <ErrorMessage error={error} onRetry={() => load(typeFilter)} />
      ) : documents.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">&#128196;</div>
          <div className="empty-state-text">Документы не найдены</div>
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Наименование</th>
                <th>Тип</th>
                <th>Статус</th>
                <th>Дата создания</th>
                {canManage && <th>Действия</th>}
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <Link to={`/projects/${projectId}/documents/${doc.id}`} style={{ fontWeight: 500 }}>
                      {doc.name}
                    </Link>
                  </td>
                  <td style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                    {DOC_TYPE_LABELS[doc.type] || doc.type || '—'}
                  </td>
                  <td>
                    {doc.status ? <StatusBadge status={doc.status} /> : '—'}
                  </td>
                  <td style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                    {doc.created_at ? new Date(doc.created_at).toLocaleDateString('ru-RU') : '—'}
                  </td>
                  {canManage && (
                    <td>
                      <div className="actions-row">
                        <Link to={`/projects/${projectId}/documents/${doc.id}`} className="btn btn-secondary btn-sm">
                          Открыть
                        </Link>
                        <button className="btn btn-danger btn-sm" onClick={() => setDeleteId(doc.id)}>
                          Удалить
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <CreateDocumentModal
          projectId={projectId}
          templates={templates}
          onClose={() => setShowModal(false)}
          onSuccess={() => { setShowModal(false); load(typeFilter); }}
        />
      )}

      {deleteId && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 380 }}>
            <h3 className="modal-title">Удалить документ?</h3>
            <p style={{ color: 'var(--color-text-secondary)' }}>
              Документ будет удалён безвозвратно.
            </p>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setDeleteId(null)} disabled={deleting}>Отмена</button>
              <button className="btn btn-danger" onClick={() => handleDelete(deleteId)} disabled={deleting}>
                {deleting ? 'Удаление...' : 'Удалить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CreateDocumentModal({ projectId, templates, onClose, onSuccess }) {
  const [form, setForm] = useState({ name: '', type: '', template_id: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const filteredTemplates = form.type
    ? templates.filter((t) => t.type === form.type)
    : templates;

  const handleTypeChange = (type) => {
    setForm({ ...form, type, template_id: '' });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { setError('Введите наименование документа'); return; }
    if (!form.type) { setError('Выберите тип документа'); return; }
    setSaving(true);
    setError('');
    try {
      await catalogApi.createDocument({
        project_id: projectId,
        name: form.name,
        type: form.type || undefined,
        template_id: form.template_id || undefined,
      });
      onSuccess();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(
        typeof detail === 'string' ? detail :
        Array.isArray(detail) ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ') :
        'Ошибка создания документа'
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h3 className="modal-title">Создать документ</h3>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="form-group">
              <label className="form-label">Наименование *</label>
              <input
                className="form-input"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Название документа"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Тип *</label>
              <select className="form-select" value={form.type} onChange={(e) => handleTypeChange(e.target.value)}>
                <option value="" disabled>Выберите тип</option>
                <option value="tz">Техническое задание</option>
                <option value="chtz">Частное техническое задание</option>
                <option value="pmi">Программа и методика испытаний</option>
                <option value="nmck">НМЦК</option>
              </select>
            </div>
            {filteredTemplates.length > 0 && (
              <div className="form-group">
                <label className="form-label">Шаблон</label>
                <select className="form-select" value={form.template_id} onChange={(e) => setForm({ ...form, template_id: e.target.value })}>
                  <option value="">Без шаблона</option>
                  {filteredTemplates.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
            )}
            {form.type && filteredTemplates.length === 0 && (
              <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                Шаблоны для этого типа документа не найдены
              </div>
            )}
            {error && <div style={{ color: 'var(--color-danger)', fontSize: 13 }}>{error}</div>}
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>Отмена</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Approvals Tab ────────────────────────────────────────────────────────────

function ApprovalsTab({ projectId }) {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');

  const load = useCallback(async (status = '') => {
    setLoading(true);
    setError(null);
    try {
      const res = await workflowApi.getApprovals({ project_id: projectId, status: status || undefined });
      setApprovals(res.data.items || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div className="page-header">
        <h2 className="section-title" style={{ margin: 0 }}>Согласования</h2>
      </div>

      <div style={{ marginBottom: 16 }}>
        <select
          className="form-select"
          style={{ maxWidth: 200 }}
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); load(e.target.value); }}
        >
          <option value="">Все статусы</option>
          <option value="pending">На согласовании</option>
          <option value="approved">Утверждено</option>
          <option value="rejected">Отклонено</option>
          <option value="revision">На доработке</option>
          <option value="cancelled">Отменено</option>
        </select>
      </div>

      {loading ? (
        <Spinner center />
      ) : error ? (
        <ErrorMessage error={error} onRetry={() => load(statusFilter)} />
      ) : approvals.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">&#9989;</div>
          <div className="empty-state-text">Согласований не найдено</div>
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Документ</th>
                <th>Тип</th>
                <th>Статус</th>
                <th>Раунд</th>
                <th>Дата создания</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {approvals.map((a) => (
                <tr key={a.id}>
                  <td style={{ fontSize: 13, fontFamily: 'monospace' }}>
                    {a.document_id?.slice(0, 8)}...
                  </td>
                  <td style={{ fontSize: 13 }}>{APPROVAL_TYPE_LABELS[a.type] || a.type || '—'}</td>
                  <td><StatusBadge status={a.status} /></td>
                  <td style={{ fontSize: 13 }}>{a.current_round ?? '—'}</td>
                  <td style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                    {a.created_at ? new Date(a.created_at).toLocaleDateString('ru-RU') : '—'}
                  </td>
                  <td>
                    <Link to={`/projects/${projectId}/approvals/${a.id}`} className="btn btn-secondary btn-sm">
                      Открыть
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── My Tasks Tab ─────────────────────────────────────────────────────────────

function MyTasksTab({ projectId }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await workflowApi.getMyTasks(projectId);
      setTasks(res.data.items || res.data || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div className="page-header">
        <h2 className="section-title" style={{ margin: 0 }}>Мои задачи</h2>
      </div>
      <p style={{ color: 'var(--color-text-secondary)', marginBottom: 16, fontSize: 13 }}>
        Согласования, ожидающие вашего решения
      </p>

      {loading ? (
        <Spinner center />
      ) : error ? (
        <ErrorMessage error={error} onRetry={load} />
      ) : tasks.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">&#127881;</div>
          <div className="empty-state-text">Нет задач, ожидающих вашего решения</div>
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Документ</th>
                <th>Тип</th>
                <th>Статус</th>
                <th>Раунд</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((a) => (
                <tr key={a.approval_id}>
                  <td style={{ fontSize: 13, fontFamily: 'monospace' }}>
                    {a.document_id?.slice(0, 8)}...
                  </td>
                  <td style={{ fontSize: 13 }}>{APPROVAL_TYPE_LABELS[a.type] || a.type || '—'}</td>
                  <td><StatusBadge status={a.status} /></td>
                  <td style={{ fontSize: 13 }}>{a.current_round ?? '—'}</td>
                  <td>
                    <Link to={`/projects/${projectId}/approvals/${a.approval_id}`} className="btn btn-primary btn-sm">
                      Рассмотреть
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
