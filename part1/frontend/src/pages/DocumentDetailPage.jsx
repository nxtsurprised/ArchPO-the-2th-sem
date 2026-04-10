import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { catalogApi } from '../api/catalog';
import { workflowApi } from '../api/workflow';
import { generationApi } from '../api/generation';
import { pmiApi } from '../api/pmi';
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
  const [template, setTemplate] = useState(null);
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

  // fnTasks: { [functionId]: { taskId, status, error } }
  const [fnTasks, setFnTasks] = useState({});
  // pmiRunTasks: { [functionId]: { taskId, status, verdict, steps_total, steps_passed, error } }
  const [pmiRunTasks, setPmiRunTasks] = useState({});

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
      if (res.data.template_id) {
        try {
          const tplRes = await catalogApi.getTemplate(res.data.template_id);
          setTemplate(tplRes.data);
        } catch {
          // шаблон недоступен — продолжаем без него
        }
      }
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
      let job = jobRes.data; // сохраняем весь объект, включая поле error
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

  const handleDraftFunction = async (fn) => {
    const fnId = fn.id;
    setFnTasks((prev) => ({ ...prev, [fnId]: { status: 'running', taskId: null, error: null } }));
    try {
      const res = await pmiApi.draftFunction(docId, projectId, fn);
      const taskId = res.data.task_id;
      setFnTasks((prev) => ({ ...prev, [fnId]: { status: 'running', taskId, error: null } }));

      for (let i = 0; i < 120; i++) {
        await new Promise((r) => setTimeout(r, 5000));
        const statusRes = await pmiApi.getFunctionTask(taskId);
        const task = statusRes.data;
        if (task.status === 'done') {
          setFnTasks((prev) => ({ ...prev, [fnId]: { status: 'done', taskId, error: null } }));
          await load();
          return;
        }
        if (task.status === 'failed') {
          setFnTasks((prev) => ({ ...prev, [fnId]: { status: 'failed', taskId, error: task.error } }));
          return;
        }
      }
      setFnTasks((prev) => ({ ...prev, [fnId]: { status: 'failed', taskId, error: 'Превышено время ожидания' } }));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      let errorMsg;
      if (typeof detail === 'string') {
        errorMsg = detail;
      } else if (Array.isArray(detail)) {
        errorMsg = detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
      } else if (err?.response?.status === 502 || err?.response?.status === 503) {
        errorMsg = 'PMI-агент недоступен. Убедитесь, что сервис запущен (ollama + pmi-agent).';
      } else if (!err?.response) {
        errorMsg = 'Нет связи с сервером. Проверьте, что все контейнеры запущены.';
      } else {
        errorMsg = `Ошибка ${err?.response?.status || ''}: ${JSON.stringify(detail || err?.response?.data || 'неизвестная ошибка')}`;
      }
      setFnTasks((prev) => ({
        ...prev,
        [fnId]: { status: 'failed', taskId: null, error: errorMsg },
      }));
    }
  };

  const handleRunPMI = async (fn, targetUrl) => {
    const fnId = fn.id;
    setPmiRunTasks((prev) => ({ ...prev, [fnId]: { status: 'running', taskId: null, verdict: null, error: null } }));
    try {
      const res = await pmiApi.runPMI(projectId, fn, targetUrl);
      const taskId = res.data.task_id;
      setPmiRunTasks((prev) => ({ ...prev, [fnId]: { status: 'running', taskId, verdict: null, error: null } }));

      for (let i = 0; i < 120; i++) {
        await new Promise((r) => setTimeout(r, 5000));
        const statusRes = await pmiApi.getPMITaskStatus(taskId);
        const task = statusRes.data;
        if (task.status === 'done' || task.status === 'failed') {
          setPmiRunTasks((prev) => ({
            ...prev,
            [fnId]: {
              status: task.status,
              taskId,
              verdict: task.verdict || null,
              steps_total: task.steps_total,
              steps_passed: task.steps_passed,
              pmi_section: task.pmi_section || null,
              error: task.error || null,
            },
          }));
          if (task.status === 'done') await load();
          return;
        }
      }
      setPmiRunTasks((prev) => ({ ...prev, [fnId]: { status: 'failed', taskId, verdict: null, error: 'Превышено время ожидания' } }));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      let errorMsg;
      if (typeof detail === 'string') {
        errorMsg = detail;
      } else if (err?.response?.status === 502 || err?.response?.status === 503) {
        errorMsg = 'PMI-агент недоступен.';
      } else if (!err?.response) {
        errorMsg = 'Нет связи с сервером.';
      } else {
        errorMsg = `Ошибка ${err?.response?.status || ''}: ${JSON.stringify(detail || err?.response?.data || '')}`;
      }
      setPmiRunTasks((prev) => ({ ...prev, [fnId]: { status: 'failed', taskId: null, verdict: null, error: errorMsg } }));
    }
  };

  const formatGenerateError = (msg) => {
    if (!msg) return msg;
    if (msg.startsWith('Missing required fields:')) {
      return 'Не все обязательные поля заполнены. Нажмите «Редактировать» и заполните поля, отмеченные *.';
    }
    return msg;
  };

  if (loading) return <Spinner center />;
  if (error) return <ErrorMessage error={error} onRetry={load} />;
  if (!doc) return null;

  return (
    <div>
      {/* Breadcrumb + Back */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => navigate(`/projects/${projectId}?tab=documents`)}
          style={{ flexShrink: 0 }}
        >
          ← Назад
        </button>
        <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
          <Link to="/">Проекты</Link>
          {' / '}
          <Link to={`/projects/${projectId}?tab=documents`}>Документы</Link>
          {' / '}
          <span>{doc.name}</span>
        </div>
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
      {generateError && <div className="mb-16"><ErrorMessage error={formatGenerateError(generateError)} /></div>}

      {downloadUrl && (
        <div style={{ background: 'var(--color-primary-light)', border: '1px solid #bfdbfe', borderRadius: 6, padding: '10px 14px', fontSize: 13, marginBottom: 16 }}>
          Файл готов:{' '}
          <a href={downloadUrl} download={`${doc.name || 'document'}.docx`} style={{ fontWeight: 600 }}>
            Скачать документ
          </a>
        </div>
      )}

      {/* Sections editor */}
      {template ? (
        <TemplateSectionEditor
          template={template}
          sections={sections}
          editing={editing && isEditable && canEdit}
          isEditable={isEditable}
          canEdit={canEdit}
          onStartEdit={() => setEditing(true)}
          onChange={(secNum, newData) =>
            setSections((prev) => ({ ...prev, [secNum]: newData }))
          }
        />
      ) : (
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
              <div className="empty-state-text">Шаблон не выбран — разделы недоступны</div>
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
        </div>
      )}

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

      {/* PMI agent panel — только для документов типа pmi */}
      {doc.type === 'pmi' && (
        <PmiFunctionsPanel
          projectId={projectId}
          docId={docId}
          pmiResults={(doc.data?.sections?.pmi_results) || {}}
          fnTasks={fnTasks}
          pmiRunTasks={pmiRunTasks}
          onDraft={handleDraftFunction}
          onRun={handleRunPMI}
        />
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

// ─── Template-aware section editor ───────────────────────────────────────────

function TemplateSectionEditor({ template, sections, editing, isEditable, canEdit, onStartEdit, onChange }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 className="section-title" style={{ margin: 0 }}>Содержание документа</h2>
        {!isEditable && (
          <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
            Документ доступен только для просмотра
          </span>
        )}
      </div>
      {template.sections.map((section) => (
        <TemplateSectionBlock
          key={section.number}
          section={section}
          data={sections[section.number] || {}}
          editing={editing}
          onChange={(newData) => onChange(section.number, newData)}
        />
      ))}
    </div>
  );
}

function TemplateSectionBlock({ section, data, editing, onChange }) {
  const source = section.source || 'manual';

  return (
    <div className="card">
      <h3 style={{ fontWeight: 600, fontSize: 15, marginBottom: 14, color: 'var(--color-text)' }}>
        {section.number}. {section.title}
      </h3>

      {source === 'manual' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {(section.fields || []).map((field) => (
            <TemplateFieldEditor
              key={field.key}
              field={field}
              value={data[field.key] ?? ''}
              editing={editing}
              onChange={(val) => onChange({ ...data, [field.key]: val })}
            />
          ))}
        </div>
      )}

      {source === 'functions' && (
        <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', padding: '8px 0' }}>
          Раздел формируется автоматически из справочника функций проекта
        </div>
      )}

      {source === 'subsystems' && (
        <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', padding: '8px 0' }}>
          Раздел формируется автоматически из подсистем проекта
        </div>
      )}

      {source === 'static' && (
        <div style={{ fontSize: 14, whiteSpace: 'pre-wrap', color: 'var(--color-text)' }}>
          {section.static_content}
        </div>
      )}
    </div>
  );
}

function TemplateFieldEditor({ field, value, editing, onChange }) {
  const isRequired = field.required;
  const isEmpty = !value || (typeof value === 'string' && !value.trim());

  return (
    <div className="form-group">
      <label className="form-label">
        {field.label}
        {isRequired && <span style={{ color: 'var(--color-danger)', marginLeft: 4 }}>*</span>}
      </label>
      {editing ? (
        <textarea
          className="form-input form-textarea"
          rows={field.type === 'textarea' || field.type === 'list' ? 4 : 2}
          value={typeof value === 'object' ? JSON.stringify(value, null, 2) : (value || '')}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.type === 'list' ? 'Каждый пункт с новой строки' : ''}
        />
      ) : (
        <div style={{
          fontSize: 14,
          whiteSpace: 'pre-wrap',
          color: isEmpty ? 'var(--color-text-secondary)' : 'var(--color-text)',
          minHeight: 20,
        }}>
          {isEmpty
            ? (isRequired ? '⚠ Обязательное поле не заполнено' : 'Не заполнено')
            : (typeof value === 'object' ? JSON.stringify(value, null, 2) : value)
          }
        </div>
      )}
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

// ─── PMI Functions Panel ──────────────────────────────────────────────────────

function PmiFunctionsPanel({ projectId, docId, pmiResults, fnTasks, pmiRunTasks, onDraft, onRun }) {
  const [functions, setFunctions] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [targetUrl, setTargetUrl] = useState(
    () => localStorage.getItem('pmi_target_url') || ''
  );

  useEffect(() => {
    catalogApi.getFunctions({ project_id: projectId, per_page: 100 })
      .then((res) => setFunctions(res.data.items || []))
      .catch(() => setLoadError('Не удалось загрузить список функций'));
  }, [projectId]);

  const handleUrlChange = (e) => {
    setTargetUrl(e.target.value);
    localStorage.setItem('pmi_target_url', e.target.value);
  };

  if (loadError) return (
    <div className="card" style={{ marginTop: 16 }}>
      <div style={{ color: 'var(--color-danger)', fontSize: 13 }}>{loadError}</div>
    </div>
  );

  if (!functions) return null;

  if (functions.length === 0) return (
    <div className="card" style={{ marginTop: 16 }}>
      <h2 className="section-title" style={{ margin: '0 0 8px' }}>ПМИ-агент</h2>
      <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
        В проекте нет функций. Добавьте функции в справочник, чтобы составить методику испытаний.
      </div>
    </div>
  );

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h2 className="section-title" style={{ margin: '0 0 4px' }}>ПМИ-агент</h2>
      <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 12 }}>
        «Составить» — черновик методики без запуска тестов. «Запустить ПМИ» — полное автотестирование через браузер.
      </p>

      {/* URL стенда */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <label style={{ fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', color: 'var(--color-text-secondary)' }}>
          URL стенда:
        </label>
        <input
          className="form-input"
          style={{ flex: 1, fontSize: 13, padding: '4px 8px' }}
          type="url"
          placeholder="https://example.com"
          value={targetUrl}
          onChange={handleUrlChange}
        />
        {!targetUrl && (
          <span style={{ fontSize: 12, color: 'var(--color-warning, #f59e0b)', whiteSpace: 'nowrap' }}>
            Требуется для «Запустить ПМИ»
          </span>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {functions.map((fn) => (
          <PmiFunctionRow
            key={fn.id}
            fn={fn}
            result={pmiResults[fn.id] || null}
            task={fnTasks[fn.id] || null}
            runTask={pmiRunTasks[fn.id] || null}
            targetUrl={targetUrl}
            onDraft={() => onDraft(fn)}
            onRun={() => onRun(fn, targetUrl)}
          />
        ))}
      </div>
    </div>
  );
}

function PmiFunctionRow({ fn, result, task, runTask, targetUrl, onDraft, onRun }) {
  const [expanded, setExpanded] = useState(false);
  const [expandedRun, setExpandedRun] = useState(false);

  const isDrafting = task?.status === 'running';
  const isDraftFailed = task?.status === 'failed';
  const isRunning = runTask?.status === 'running';
  const isRunFailed = runTask?.status === 'failed';

  const draftVerdict = result?.verdict;
  const runVerdict = runTask?.verdict;

  const verdictStyle = (v) => ({
    fontSize: 12, fontWeight: 600, marginLeft: 8,
    color: v === 'соответствует' ? 'var(--status-approved)'
      : v === 'не соответствует' ? 'var(--color-danger)'
      : 'var(--color-text-secondary)',
  });

  return (
    <div style={{ border: '1px solid var(--color-border)', borderRadius: 6, overflow: 'hidden' }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'var(--color-bg)', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <span style={{ fontWeight: 500, fontSize: 14 }}>{fn.code} — {fn.name}</span>
          {draftVerdict && <span style={verdictStyle(draftVerdict)}>{draftVerdict}</span>}
          {runVerdict && (
            <span style={{ ...verdictStyle(runVerdict), marginLeft: draftVerdict ? 4 : 8 }}>
              [{runVerdict}]
            </span>
          )}
          {runTask?.steps_total > 0 && (
            <span style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginLeft: 8 }}>
              {runTask.steps_passed ?? '?'}/{runTask.steps_total} шагов
            </span>
          )}
        </div>

        {/* Draft controls */}
        {result && (
          <button className="btn btn-secondary btn-sm" onClick={() => setExpanded((v) => !v)}>
            {expanded ? 'Свернуть' : 'Методика'}
          </button>
        )}
        <button
          className="btn btn-secondary btn-sm"
          onClick={onDraft}
          disabled={isDrafting || isRunning}
          title="Составить черновик методики (без запуска тестов)"
        >
          {isDrafting ? <><Spinner size={12} /> Составление…</> : result ? 'Пересоставить' : 'Составить'}
        </button>

        {/* Run PMI controls */}
        {runTask && (runTask.status === 'done' || runTask.status === 'failed') && (
          <button className="btn btn-secondary btn-sm" onClick={() => setExpandedRun((v) => !v)}>
            {expandedRun ? 'Свернуть' : 'Результат'}
          </button>
        )}
        <button
          className="btn btn-primary btn-sm"
          onClick={onRun}
          disabled={isDrafting || isRunning || !targetUrl}
          title={!targetUrl ? 'Укажите URL стенда выше' : 'Запустить полное автотестирование через браузер'}
        >
          {isRunning ? <><Spinner size={12} /> Тестирование…</> : runTask?.status === 'done' ? 'Перезапустить ПМИ' : 'Запустить ПМИ'}
        </button>
      </div>

      {/* Draft error */}
      {isDraftFailed && (
        <div style={{ padding: '6px 14px', background: '#fef2f2', fontSize: 12, color: 'var(--color-danger)' }}>
          Ошибка составления: {task.error}
        </div>
      )}

      {/* Run error */}
      {isRunFailed && (
        <div style={{ padding: '6px 14px', background: '#fef2f2', fontSize: 12, color: 'var(--color-danger)' }}>
          Ошибка испытания: {runTask.error}
        </div>
      )}

      {/* Draft result */}
      {expanded && result && (
        <div style={{ padding: '12px 14px', borderTop: '1px solid var(--color-border)', fontSize: 13 }}>
          <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 6 }}>ЧЕРНОВИК МЕТОДИКИ</div>
          <PmiSectionView section={result} />
        </div>
      )}

      {/* Full run result */}
      {expandedRun && runTask?.pmi_section && (
        <div style={{ padding: '12px 14px', borderTop: '1px solid var(--color-border)', fontSize: 13, background: 'var(--color-bg-secondary, #f9fafb)' }}>
          <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 6 }}>РЕЗУЛЬТАТЫ ИСПЫТАНИЯ</div>
          <PmiSectionView section={runTask.pmi_section} />
        </div>
      )}
    </div>
  );
}

function PmiSectionView({ section }) {
  const rows = [
    { label: 'Цель', value: section.test_objective },
    { label: 'Метод', value: section.method },
    { label: 'Наблюдения', value: section.observations },
    { label: 'Рекомендация', value: section.recommendation },
  ];

  const scenarios = section.scenarios || [];
  const defects = section.defects || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map(({ label, value }) => value ? (
        <div key={label}>
          <span style={{ fontWeight: 600, color: 'var(--color-text-secondary)', fontSize: 12 }}>{label}: </span>
          <span style={{ whiteSpace: 'pre-wrap' }}>{value}</span>
        </div>
      ) : null)}
      {scenarios.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, color: 'var(--color-text-secondary)', fontSize: 12, marginBottom: 4 }}>Сценарии:</div>
          {scenarios.map((s, i) => (
            <div key={i} style={{ paddingLeft: 12, color: 'var(--color-text-secondary)', marginBottom: 2 }}>• {s}</div>
          ))}
        </div>
      )}
      {defects.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, color: 'var(--color-danger)', fontSize: 12, marginBottom: 4 }}>Дефекты:</div>
          {defects.map((d, i) => (
            <div key={i} style={{ paddingLeft: 12, color: 'var(--color-danger)', marginBottom: 2 }}>• {d}</div>
          ))}
        </div>
      )}
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
