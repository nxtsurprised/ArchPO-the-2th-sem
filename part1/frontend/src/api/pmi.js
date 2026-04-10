import client from './client';

export const pmiApi = {
  // Полный прогон: план + Playwright-тесты + результаты
  runForDocument: (documentId, projectId, targetUrl) =>
    client.post('/api/pmi/run-for-document', {
      document_id: documentId,
      project_id: projectId,
      target_url: targetUrl,
    }),

  getDocTask: (taskId) => client.get(`/api/pmi/doc-tasks/${taskId}`),

  // Черновой режим: только план + методика (без запуска тестов)
  draftForDocument: (documentId, projectId) =>
    client.post('/api/pmi/draft-for-document', {
      document_id: documentId,
      project_id: projectId,
    }),

  getDraftTask: (taskId) => client.get(`/api/pmi/draft-tasks/${taskId}`),
};
