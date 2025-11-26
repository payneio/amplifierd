import { BASE_URL } from './client';

export interface SSEHandlers {
  onMessage: (data: unknown) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
}

export function createSSEConnection(
  endpoint: string,
  handlers: SSEHandlers
): { eventSource: EventSource; cleanup: () => void } {
  const url = `${BASE_URL}${endpoint}`;

  const eventSource = new EventSource(url);

  eventSource.onopen = () => {
    handlers.onOpen?.();
  };

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handlers.onMessage(data);
    } catch (error) {
      console.error('Failed to parse SSE message:', error);
    }
  };

  eventSource.onerror = (error) => {
    handlers.onError?.(error);
  };

  const cleanup = () => {
    eventSource.close();
  };

  return { eventSource, cleanup };
}
