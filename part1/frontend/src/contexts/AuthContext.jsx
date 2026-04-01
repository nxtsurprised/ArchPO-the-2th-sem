import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authApi } from '../api/auth';

const AuthContext = createContext(null);

/**
 * Parse a JWT token payload without verification.
 */
function parseJwt(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    // Parse JWT immediately for roles/projects (no API call)
    const payload = parseJwt(token);
    if (!payload) {
      setUser(null);
      setLoading(false);
      return;
    }

    // Set preliminary user from JWT
    setUser({
      id: payload.sub,
      org_id: payload.org_id,
      roles: payload.roles || [],
      is_superadmin: payload.is_superadmin || false,
      // me endpoint fields filled below
      email: null,
      full_name: null,
    });

    // Fetch full profile from /me
    try {
      const response = await authApi.me();
      setUser((prev) => ({
        ...prev,
        ...response.data,
      }));
    } catch {
      // If /me fails it's not critical; we still have JWT data
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback(async (email, password) => {
    const response = await authApi.login(email, password);
    const { access_token, refresh_token } = response.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    await loadUser();
    return response.data;
  }, [loadUser]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore errors on logout
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  }, []);

  const isAuthenticated = !!user;

  /**
   * Get unique project IDs from the user's roles.
   */
  const getProjectIds = useCallback(() => {
    if (!user) return [];
    const ids = (user.roles || []).map((r) => r.project_id).filter(Boolean);
    return [...new Set(ids)];
  }, [user]);

  /**
   * Get the user's role info for a specific project.
   */
  const getRoleForProject = useCallback(
    (projectId) => {
      if (!user) return null;
      return (user.roles || []).find((r) => r.project_id === projectId) || null;
    },
    [user]
  );

  const value = {
    user,
    loading,
    isAuthenticated,
    login,
    logout,
    getProjectIds,
    getRoleForProject,
    parseJwt,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
