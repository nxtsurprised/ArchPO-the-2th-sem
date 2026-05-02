import client from './client';

export const generationApi = {
  createJob(documentId, format = 'docx') {
    return client.post('/api/generation/jobs', { document_id: documentId, format });
  },

  getJob(jobId) {
    return client.get(`/api/generation/jobs/${jobId}`);
  },

  downloadJob(jobId) {
    return client.get(`/api/generation/jobs/${jobId}/download`, { responseType: 'blob' });
  },

  listDocumentFiles(documentId) {
    return client.get(`/api/generation/documents/${documentId}/files`);
  },
};
