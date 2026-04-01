import React, { useState } from 'react';
import { NavLink, Link, useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

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

export default function Layout({ children }) {
  const { user, logout, getRoleForProject } = useAuth();
  const { id: projectId } = useParams();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const roleInfo = projectId ? getRoleForProject(projectId) : null;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--color-bg)' }}>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.3)',
            zIndex: 99,
          }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        style={{
          width: 'var(--sidebar-width)',
          background: 'var(--color-white)',
          borderRight: '1px solid var(--color-border)',
          display: 'flex',
          flexDirection: 'column',
          position: 'fixed',
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 100,
          transform: sidebarOpen ? 'translateX(0)' : undefined,
          transition: 'transform 0.2s',
          overflowY: 'auto',
        }}
      >
        {/* Logo */}
        <div
          style={{
            padding: '16px',
            borderBottom: '1px solid var(--color-border)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              background: 'var(--color-primary)',
              borderRadius: 8,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontWeight: 700,
              fontSize: 14,
              flexShrink: 0,
            }}
          >
            СУД
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13 }}>Система управления</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>документами</div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '12px 0' }}>
          <div style={{ padding: '4px 12px 8px', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary)' }}>
            Навигация
          </div>

          <SidebarLink to="/" exact>
            Мои проекты
          </SidebarLink>

          {projectId && (
            <>
              <div style={{ padding: '12px 12px 4px', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary)', marginTop: 4 }}>
                Проект
              </div>
              <SidebarLink to={`/projects/${projectId}`} exact>
                Обзор
              </SidebarLink>
              <SidebarLink to={`/projects/${projectId}?tab=functions`}>
                Функции
              </SidebarLink>
              <SidebarLink to={`/projects/${projectId}?tab=documents`}>
                Документы
              </SidebarLink>
              <SidebarLink to={`/projects/${projectId}?tab=approvals`}>
                Согласования
              </SidebarLink>
              <SidebarLink to={`/projects/${projectId}?tab=tasks`}>
                Мои задачи
              </SidebarLink>
            </>
          )}
        </nav>

        {/* User info */}
        <div
          style={{
            padding: '12px 16px',
            borderTop: '1px solid var(--color-border)',
          }}
        >
          {user && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2 }}>
                {user.full_name || user.email || 'Пользователь'}
              </div>
              {user.email && user.full_name && (
                <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 4 }}>
                  {user.email}
                </div>
              )}
              {roleInfo && (
                <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
                  {ROLE_LABELS[roleInfo.role] || roleInfo.role}
                  {roleInfo.side ? ` · ${SIDE_LABELS[roleInfo.side] || roleInfo.side}` : ''}
                </div>
              )}
              {user.is_superadmin && (
                <span
                  style={{
                    display: 'inline-block',
                    padding: '1px 8px',
                    background: '#f5f3ff',
                    color: '#7c3aed',
                    borderRadius: 4,
                    fontSize: 11,
                    fontWeight: 600,
                    marginTop: 4,
                  }}
                >
                  Суперадмин
                </span>
              )}
            </div>
          )}
          <button
            onClick={handleLogout}
            className="btn btn-secondary"
            style={{ width: '100%', justifyContent: 'center' }}
          >
            Выйти
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div
        style={{
          flex: 1,
          marginLeft: 'var(--sidebar-width)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: '100vh',
        }}
      >
        {/* Header */}
        <header
          style={{
            height: 'var(--header-height)',
            background: 'var(--color-white)',
            borderBottom: '1px solid var(--color-border)',
            display: 'flex',
            alignItems: 'center',
            padding: '0 24px',
            gap: 16,
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            style={{
              display: 'none',
              background: 'none',
              border: 'none',
              fontSize: 20,
              cursor: 'pointer',
              padding: 4,
            }}
            className="mobile-menu-btn"
          >
            &#9776;
          </button>
          <div style={{ flex: 1 }} />
          {user && (
            <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
              {user.full_name || user.email}
            </div>
          )}
        </header>

        {/* Page content */}
        <main style={{ flex: 1, padding: '24px', maxWidth: '1200px', width: '100%' }}>
          {children}
        </main>
      </div>
    </div>
  );
}

function SidebarLink({ to, children, exact }) {
  return (
    <NavLink
      to={to}
      end={exact}
      style={({ isActive }) => ({
        display: 'block',
        padding: '8px 16px',
        color: isActive ? 'var(--color-primary)' : 'var(--color-text)',
        background: isActive ? 'var(--color-primary-light)' : 'transparent',
        fontWeight: isActive ? 600 : 400,
        fontSize: 14,
        borderRadius: 6,
        margin: '1px 8px',
        textDecoration: 'none',
        transition: 'background 0.1s, color 0.1s',
      })}
    >
      {children}
    </NavLink>
  );
}
