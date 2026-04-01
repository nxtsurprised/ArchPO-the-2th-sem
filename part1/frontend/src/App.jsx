import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import ProjectsPage from './pages/ProjectsPage';
import ProjectPage from './pages/ProjectPage';
import FunctionDetailPage from './pages/FunctionDetailPage';
import DocumentDetailPage from './pages/DocumentDetailPage';
import ApprovalDetailPage from './pages/ApprovalDetailPage';

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout>
              <ProjectsPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id"
        element={
          <ProtectedRoute>
            <Layout>
              <ProjectPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id/functions/:funcId"
        element={
          <ProtectedRoute>
            <Layout>
              <FunctionDetailPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id/documents/:docId"
        element={
          <ProtectedRoute>
            <Layout>
              <DocumentDetailPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id/approvals/:approvalId"
        element={
          <ProtectedRoute>
            <Layout>
              <ApprovalDetailPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
