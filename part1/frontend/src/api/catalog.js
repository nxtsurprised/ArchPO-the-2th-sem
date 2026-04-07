import client from './client';

export const catalogApi = {
  // Subsystems
  getSubsystems(projectId) {
    return client.get('/api/catalog/subsystems', { params: { project_id: projectId } });
  },

  createSubsystem(data) {
    return client.post('/api/catalog/subsystems', data);
  },

  updateSubsystem(id, data) {
    return client.put(`/api/catalog/subsystems/${id}`, data);
  },

  deleteSubsystem(id) {
    return client.delete(`/api/catalog/subsystems/${id}`);
  },

  // Functions
  getFunctions(params = {}) {
    return client.get('/api/catalog/functions', { params });
  },

  getFunction(id) {
    return client.get(`/api/catalog/functions/${id}`);
  },

  createFunction(data) {
    return client.post('/api/catalog/functions', data);
  },

  updateFunction(id, data) {
    return client.put(`/api/catalog/functions/${id}`, data);
  },

  deleteFunction(id) {
    return client.delete(`/api/catalog/functions/${id}`);
  },

  // Documents
  getDocuments(params = {}) {
    return client.get('/api/catalog/documents', { params });
  },

  getDocument(id) {
    return client.get(`/api/catalog/documents/${id}`);
  },

  createDocument(data) {
    return client.post('/api/catalog/documents', data);
  },

  updateDocument(id, data) {
    return client.put(`/api/catalog/documents/${id}`, data);
  },

  deleteDocument(id) {
    return client.delete(`/api/catalog/documents/${id}`);
  },

  // Templates
  getTemplates(params = {}) {
    return client.get('/api/catalog/templates', { params });
  },

  getTemplate(id) {
    return client.get(`/api/catalog/templates/${id}`);
  },
};
