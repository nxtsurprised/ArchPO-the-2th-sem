import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { authApi } from '../api/auth';
import Spinner from '../components/Spinner';
import ErrorMessage from '../components/ErrorMessage';
import StatusBadge from '../components/StatusBadge';

const ROLE_LABELS = {
  pm: 'Менеджер проекта',
  analyst: 'Аналитик',
  admin: 'Администратор',
  approver: 'Согласующий',
};

const SIDE_LABELS = {
  customer: 'Заказчик',
  contractor: 'Исполнитель',
};

export default function ProjectsPage() {
  const { user, getProjectIds } = useAuth();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      if (user?.is_superadmin) {
        // Superadmin: fetch all projects from auth service
        const res = await authApi.getProjects();
        setProjects(res.data.items || []);
      } else {
        // Regular user: build project list from JWT roles
        const roles = user?.roles || [];
        const rolesByProjectId = {};
        roles.forEach((r) => {
          if (r.project_id) {
            if (!rolesByProjectId[r.project_id]) {
              rolesByProjectId[r.project_id] = [];
            }
            rolesByProjectId[r.project_id].push(r);
          }
        });

        const projectList = Object.entries(rolesByProjectId).map(([projectId, projectRoles]) => ({
          id: projectId,
          name: null,
          code: null,
          status: null,
          roles: projectRoles,
        }));
        setProjects(projectList);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      loadProjects();
    }
  }, [user]);

  if (loading) return <Spinner center />;
  if (error) return <ErrorMessage error={error} onRetry={loadProjects} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Мои проекты</h1>
          <p className="page-subtitle">
            {user?.is_superadmin
              ? 'Все проекты системы'
              : `Проекты, в которых вы участвуете (${projects.length})`}
          </p>
        </div>
      </div>

      {projects.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">&#128194;</div>
          <div className="empty-state-text">
            {user?.is_superadmin
              ? 'В системе нет проектов'
              : 'Вы не участвуете ни в одном проекте'}
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '16px', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} isSuperAdmin={user?.is_superadmin} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project, isSuperAdmin }) {
  const roles = project.roles || [];

  return (
    <Link
      to={`/projects/${project.id}`}
      style={{ textDecoration: 'none', color: 'inherit' }}
    >
      <div
        className="card"
        style={{
          transition: 'box-shadow 0.15s, border-color 0.15s',
          cursor: 'pointer',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)';
          e.currentTarget.style.borderColor = 'var(--color-primary)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = '';
          e.currentTarget.style.borderColor = 'var(--color-border)';
        }}
      >
        {/* Header row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 2 }} className="truncate">
              {project.name || `Проект ${project.id.slice(0, 8)}...`}
            </div>
            {project.code && (
              <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', fontFamily: 'monospace' }}>
                {project.code}
              </div>
            )}
          </div>
          {project.status && <StatusBadge status={project.status} />}
        </div>

        {/* ID */}
        <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 12, fontFamily: 'monospace' }}>
          ID: {project.id}
        </div>

        {/* Roles */}
        {!isSuperAdmin && roles.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {roles.map((r, idx) => (
              <span
                key={idx}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '3px 10px',
                  background: 'var(--color-primary-light)',
                  color: 'var(--color-primary)',
                  borderRadius: 9999,
                  fontSize: 12,
                  fontWeight: 500,
                }}
              >
                {ROLE_LABELS[r.role] || r.role}
                {r.side && (
                  <span style={{ opacity: 0.7 }}>
                    &middot; {SIDE_LABELS[r.side] || r.side}
                  </span>
                )}
              </span>
            ))}
          </div>
        )}

        {isSuperAdmin && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {project.customer_org_id && (
              <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
                Заказчик: {project.customer_org_id}
              </span>
            )}
            {project.contractor_org_id && (
              <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
                Исполнитель: {project.contractor_org_id}
              </span>
            )}
          </div>
        )}

        {/* Arrow */}
        <div style={{ marginTop: 12, color: 'var(--color-primary)', fontSize: 13, fontWeight: 500 }}>
          Открыть проект &rarr;
        </div>
      </div>
    </Link>
  );
}
