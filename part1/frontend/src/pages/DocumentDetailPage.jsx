import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { catalogApi } from '../api/catalog';
import { workflowApi } from '../api/workflow';
import { generationApi } from '../api/generation';
import { useAuth } from '../contexts/AuthContext';
import Spinner from '../components/Spinner';
import ErrorMessage from '../components/ErrorMessage';
import StatusBadge from '../components/StatusBadge';

const EDITABLE_STATUSES = ['draft', 'revision'];

const DOC_TYPE_LABELS = {
  tz: 'Техническое задание',
  chtz: 'Частное техническое задание',
  pmi: 'Программа и методика испытаний',
  nmck: 'НМЦК',
};

export default function DocumentDetailPage() {
  const { id: projectId, docId } = useParams();
  const { getRoleForProject, user } = useAuth();
  const navigate = useNavigate();

  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [editing, setEditing] = useState(false);
  const [sections, setSections] = useState({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [showSubmitModal, setShowSubmitModal] = useState(false);

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState('');
  const [downloadUrl, setDownloadUrl] = useState(null);

  const roleInfo = getRoleForProject(projectId);
  const userRole = roleInfo?.role;
  const canEdit = ['pm', 'analyst', 'admin'].includes(userRole) || user?.is_superadmin;
  const canSubmit = ['pm', 'admin'].includes(userRole) || user?.is_superadmin;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await catalogApi.getDocument(docId);
      setDoc(res.data);
      setSections(res.data.data?.sections || {});
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [docId]);

  useEffect(() => { load(); }, [load]);

  const isEditable = doc && EDITABLE_STATUSES.includes(doc.status);

  const handleSave = async () => {
    setSaving(true);
    setSaveError('');
    setSaveSuccess(false);
    try {
      const res = await catalogApi.updateDocument(docId, { data: { sections } });
      setDoc(res.data);
      setSections(res.data.data?.sections || sections);
      setEditing(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setSaveError(err?.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setSections(doc.data?.sections || {});
    setSaveError('');
    setEditing(false);
  };

  const handleSubmitForApproval = async () => {
    setSubmitting(true);
    setSubmitError('');
    const approvalTypeMap = { tz: 'tz_final', chtz: 'tz_final', pmi: 'tz_final', nmck: 'nmck_final' };
    const approvalType = approvalTypeMap[doc.type] || 'tz_final';
    try {
      await workflowApi.createApproval({
        document_id: docId,
        project_id: projectId,
        type: approvalType,
      });
      setShowSubmitModal(false);
      setSubmitSuccess(true);
      // Refresh document (status might change)
      await load();
      setTimeout(() => setSubmitSuccess(false), 4000);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setSubmitError(typeof detail === 'string' ? detail : 'Ошибка при отправке на согласование');
    } finally {
      setSubmitting(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setGenerateError('');
    setDownloadUrl(null);
    try {
      // 1. Запускаем job
      const jobRes = await generationApi.createJob(docId, 'docx');
      const jobId = jobRes.data.job_id;

      // 2. Ждём завершения (polling до 60 секунд)
      let job = { status: jobRes.data.status };
      for (let i = 0; i < 60 && !['completed', 'failed'].includes(job.status); i++) {
        await new Promise((r) => setTimeout(r, 1000));
        const statusRes = await generationApi.getJob(jobId);
        job = statusRes.data;
      }

      if (job.status !== 'completed') {
        setGenerateError(job.error || 'Генерация не завершилась в отведённое время');
        return;
      }

      // 3. Скачиваем файл
      const blobRes = await generationApi.downloadJob(jobId);
      const blob = new Blob([blobRes.data]);
      const url = URL.createObjectURL(blob);
      setDownloadUrl(url);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setGenerateError(
        typeof detail === 'string' ? detail :
        Array.isArray(detail) ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ') :
        'Ошибка генерации документа'
      );
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <Spinner center />;
  if (error) return <ErrorMessage error={error} onRetry={load} />;
  if (!doc) return null;

  return (
    <div>
      {/* Breadcrumb */}
      <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 16 }}>
        <Link to="/">Проекты</Link>
        {' / '}
        <Link to={`/projects/${projectId}?tab=documents`}>Документы</Link>
        {' / '}
        <span>{doc.name}</span>
      </div>

      {/* Page header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">{doc.name}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6, flexWrap: 'wrap' }}>
            {doc.status && <StatusBadge status={doc.status} />}
            {doc.type && (
              <span style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                {DOC_TYPE_LABELS[doc.type] || doc.type}
              </span>
            )}
            {doc.created_at && (
              <span style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                Создан: {new Date(doc.created_at).toLocaleDateString('ru-RU')}
              </span>
            )}
          </div>
        </div>
        <div className="actions-row">
          {canEdit && isEditable && !editing && (
            <button className="btn btn-secondary" onClick={() => setEditing(true)}>
              Редактировать
            </button>
          )}
          {editing && (
            <>
              <button className="btn btn-secondary" onClick={handleCancelEdit} disabled={saving}>
                Отмена
              </button>
              <button className="btn btn-success" onClick={handleSave} disabled={saving}>
                {saving ? 'Сохранение...' : 'Сохранить'}
              </button>
            </>
          )}
          {canSubmit && isEditable && !editing && (
            <button className="btn btn-primary" onClick={() => setShowSubmitModal(true)}>
              Отправить на согласование
            </button>
          )}
          <button className="btn btn-secondary" onClick={handleGenerate} disabled={generating}>
            {generating ? 'Генерация...' : 'Сгенерировать файл'}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {saveSuccess && (
        <div style={{ background: 'var(--status-approved-bg)', border: '1px solid #bbf7d0', borderRadius: 6, padding: '10px 14px', color: 'var(--status-approved)', fontSize: 13, marginBottom: 16 }}>
          Документ успешно сохранён
        </div>
      )}
      {submitSuccess && (
        <div style={{ background: 'var(--status-approved-bg)', border: '1px solid #bbf7d0', borderRadius: 6, padding: '10px 14px', color: 'var(--status-approved)', fontSize: 13, marginBottom: 16 }}>
          Документ отправлен на согласование
        </div>
      )}
      {saveError && <div className="mb-16"><ErrorMessage error={saveError} /></div>}
      {generateError && <div className="mb-16"><ErrorMessage error={generateError} /></div>}

      {downloadUrl && (
        <div style={{ background: 'var(--color-primary-light)', border: '1px solid #bfdbfe', borderRadius: 6, padding: '10px 14px', fontSize: 13, marginBottom: 16 }}>
          Файл готов:{' '}
          <a href={downloadUrl} download={`${doc.name || 'document'}.docx`} style={{ fontWeight: 600 }}>
            Скачать документ
          </a>
        </div>
      )}

      {/* Sections editor */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 className="section-title" style={{ margin: 0 }}>Содержание документа</h2>
          {!isEditable && (
            <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
              Документ доступен только для просмотра
            </span>
          )}
        </div>

        {Object.keys(sections).length === 0 ? (
          <div className="empty-state" style={{ padding: '32px 0' }}>
            <div className="empty-state-icon">&#128196;</div>
            <div className="empty-state-text">Разделы не заполнены</div>
            {isEditable && canEdit && !editing && (
              <button className="btn btn-primary btn-sm" style={{ marginTop: 12 }} onClick={() => setEditing(true)}>
                Добавить разделы
              </button>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {Object.entries(sections).map(([sectionKey, sectionValue]) => (
              <SectionField
                key={sectionKey}
                sectionKey={sectionKey}
                value={sectionValue}
                editing={editing && isEditable && canEdit}
                onChange={(newVal) => setSections((prev) => ({ ...prev, [sectionKey]: newVal }))}
              />
            ))}
          </div>
        )}

        {/* Add section button when editing */}
        {editing && isEditable && (
          <AddSectionButton
            existingKeys={Object.keys(sections)}
            onAdd={(key) => setSections((prev) => ({ ...prev, [key]: '' }))}
          />
        )}
      </div>

      {/* Submit for approval modal */}
      {showSubmitModal && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 400 }}>
            <h3 className="modal-title">Отправить на согласование?</h3>
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: 8 }}>
              Документ <strong>«{doc.name}»</strong> будет отправлен на согласование. После отправки редактирование будет недоступно.
            </p>
            {submitError && (
              <div style={{ color: 'var(--color-danger)', fontSize: 13, marginBottom: 8 }}>{submitError}</div>
            )}
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowSubmitModal(false)} disabled={submitting}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={handleSubmitForApproval} disabled={submitting}>
                {submitting ? 'Отправка...' : 'Отправить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer info */}
      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 16 }}>
        ID документа: <span style={{ fontFamily: 'monospace' }}>{doc.id}</span>
        {doc.template_id && (
          <span style={{ marginLeft: 16 }}>
            Шаблон: <span style={{ fontFamily: 'monospace' }}>{doc.template_id}</span>
          </span>
        )}
      </div>
    </div>
  );
}

function SectionField({ sectionKey, value, editing, onChange }) {
  const isObject = value !== null && typeof value === 'object' && !Array.isArray(value);
  const isArray = Array.isArray(value);

  const label = sectionKey
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

  if (editing) {
    const displayValue = isObject || isArray ? JSON.stringify(value, null, 2) : String(value ?? '');

    const handleChange = (raw) => {
      if (isObject || isArray) {
        try {
          onChange(JSON.parse(raw));
        } catch {
          onChange(raw); // keep raw string if not valid JSON yet
        }
      } else {
        onChange(raw);
      }
    };

    return (
      <div className="form-group">
        <label className="form-label">{label}</label>
        <textarea
          className="form-input form-textarea"
          rows={isObject || isArray ? 6 : 3}
          value={displayValue}
          onChange={(e) => handleChange(e.target.value)}
          style={{ fontFamily: isObject || isArray ? 'monospace' : 'inherit' }}
        />
      </div>
    );
  }

  // View mode
  const displayValue = isObject || isArray
    ? JSON.stringify(value, null, 2)
    : String(value ?? '');

  return (
    <div>
      <div style={{ fontWeight: 600, fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary)', marginBottom: 6 }}>
        {label}
      </div>
      <div
        style={{
          fontSize: 14,
          whiteSpace: 'pre-wrap',
          fontFamily: isObject || isArray ? 'monospace' : 'inherit',
          background: isObject || isArray ? 'var(--color-bg)' : 'transparent',
          padding: isObject || isArray ? '10px 12px' : 0,
          borderRadius: isObject || isArray ? 6 : 0,
          border: isObject || isArray ? '1px solid var(--color-border)' : 'none',
          color: displayValue ? 'var(--color-text)' : 'var(--color-text-secondary)',
        }}
      >
        {displayValue || 'Не заполнено'}
      </div>
    </div>
  );
}

function AddSectionButton({ existingKeys, onAdd }) {
  const [showInput, setShowInput] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [err, setErr] = useState('');

  const handle = () => {
    const key = newKey.trim().replace(/\s+/g, '_').toLowerCase();
    if (!key) { setErr('Введите ключ раздела'); return; }
    if (existingKeys.includes(key)) { setErr('Раздел с таким ключом уже существует'); return; }
    onAdd(key);
    setNewKey('');
    setShowInput(false);
    setErr('');
  };

  if (!showInput) {
    return (
      <div style={{ marginTop: 16 }}>
        <button className="btn btn-secondary btn-sm" onClick={() => setShowInput(true)}>
          + Добавить раздел
        </button>
      </div>
    );
  }

  return (
    <div style={{ marginTop: 16, display: 'flex', gap: 8, alignItems: 'flex-start', flexWrap: 'wrap' }}>
      <div style={{ flex: 1, minWidth: 200 }}>
        <input
          className="form-input"
          placeholder="Ключ раздела (например: introduction)"
          value={newKey}
          onChange={(e) => { setNewKey(e.target.value); setErr(''); }}
          onKeyDown={(e) => e.key === 'Enter' && handle()}
          autoFocus
        />
        {err && <div style={{ color: 'var(--color-danger)', fontSize: 12, marginTop: 4 }}>{err}</div>}
      </div>
      <button className="btn btn-primary btn-sm" onClick={handle}>Добавить</button>
      <button className="btn btn-secondary btn-sm" onClick={() => { setShowInput(false); setErr(''); }}>Отмена</button>
    </div>
  );
}
