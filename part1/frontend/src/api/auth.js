import client from './client';

export const authApi = {
  login(email, password) {
    return client.post('/api/auth/login', { email, password });
  },

  logout() {
    return client.post('/api/auth/logout');
  },

  me() {
    return client.get('/api/auth/me');
  },

  getProjects(params = {}) {
    return client.get('/api/auth/projects', { params });
  },
};
