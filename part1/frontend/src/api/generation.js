import client from './client';

export const generationApi = {
  generateDocument(documentId) {
    return client.post(`/api/generation/documents/${documentId}/generate`);
  },

  getDownloadUrl(documentId) {
    return client.get(`/api/generation/documents/${documentId}/download-url`);
  },
};
