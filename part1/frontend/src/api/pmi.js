import client from './client';

export const pmiApi = {
  draftFunction: (documentId, projectId, fn) =>
    client.post('/api/pmi/draft-function', {
      document_id: documentId,
      project_id: projectId,
      function_id: fn.id,
      function_name: fn.name,
      function_description: fn.description || '',
      acceptance_criteria: fn.acceptance_criteria || [],
    }),

  getFunctionTask: (taskId) => client.get(`/api/pmi/function-tasks/${taskId}`),
};
