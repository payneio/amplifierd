import { fetchApi } from './client';
import type { Session, SessionMessage, CreateSessionRequest } from '@/types/api';

export const listSessions = (params?: {
  status?: string;
  profile_name?: string;
  limit?: number;
}) => {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.profile_name) searchParams.set('profile_name', params.profile_name);
  if (params?.limit) searchParams.set('limit', String(params.limit));

  const query = searchParams.toString();
  return fetchApi<Session[]>(`/api/v1/sessions/${query ? `?${query}` : ''}`);
};

export const getSession = (sessionId: string) =>
  fetchApi<Session>(`/api/v1/sessions/${sessionId}`);

export const createSession = (data: CreateSessionRequest) =>
  fetchApi<Session>('/api/v1/sessions/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const startSession = (sessionId: string) =>
  fetchApi<void>(`/api/v1/sessions/${sessionId}/start`, {
    method: 'POST',
  });

export const deleteSession = (sessionId: string) =>
  fetchApi<void>(`/api/v1/sessions/${sessionId}`, {
    method: 'DELETE',
  });

export const getTranscript = (sessionId: string, limit?: number) => {
  const query = limit ? `?limit=${limit}` : '';
  return fetchApi<SessionMessage[]>(
    `/api/v1/sessions/${sessionId}/transcript${query}`
  );
};

export const sendMessage = (
  sessionId: string,
  content: string
) =>
  fetchApi<void>(`/api/v1/sessions/${sessionId}/execute`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });

// Export SSE execution function for components that want streaming
export { executeWithSSE } from './sse';
