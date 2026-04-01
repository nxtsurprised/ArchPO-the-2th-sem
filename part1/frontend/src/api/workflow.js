import client from './client';

export const workflowApi = {
  getApprovals(params = {}) {
    return client.get('/api/workflow/approvals', { params });
  },

  createApproval(data) {
    return client.post('/api/workflow/approvals', data);
  },

  getApproval(id) {
    return client.get(`/api/workflow/approvals/${id}`);
  },

  decide(id, decision, comment) {
    return client.post(`/api/workflow/approvals/${id}/decide`, { decision, comment });
  },

  revoke(id) {
    return client.post(`/api/workflow/approvals/${id}/revoke`);
  },

  cancel(id) {
    return client.post(`/api/workflow/approvals/${id}/cancel`);
  },

  getHistory(id) {
    return client.get(`/api/workflow/approvals/${id}/history`);
  },

  getDashboard(projectId) {
    return client.get('/api/workflow/dashboard', { params: { project_id: projectId } });
  },

  getMyTasks(projectId) {
    return client.get('/api/workflow/my-tasks', { params: { project_id: projectId } });
  },
};
