const BASE = '/api/v1';

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`${resp.status}: ${text.slice(0, 300)}`);
  }
  return resp.json();
}

export const getHealth = () => request('/health').catch(() => null);
export const getPlugins = () => request('/plugins');
export const getSources = () => request('/sources');
export const getIncidents = (limit = 100) => request(`/incidents?limit=${limit}`);
export const approveIncident = (id, approve, approver = 'operator') =>
  request(`/incidents/${id}/approve`, { method: 'POST', body: JSON.stringify({ approve, approver }) });
export const rollbackIncident = (id, actor = 'operator') =>
  request(`/incidents/${id}/rollback`, { method: 'POST', body: JSON.stringify({ actor }) });
export const chat = (message, sourceId = null) =>
  request('/chat', { method: 'POST', body: JSON.stringify({ message, source_id: sourceId }) });
export const explainSource = (sourceId) => request(`/sources/${sourceId}/explain`);
export const retrainModels = () => request('/models/retrain', { method: 'POST', body: '{}' });
