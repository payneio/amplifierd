import { BASE_URL } from './client';

export interface SSEMessage {
  event: string;
  data: unknown;
}

export interface SSEHandlers {
  onMessage: (message: SSEMessage) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

/**
 * Execute a message with SSE streaming support using POST
 */
export async function executeWithSSE(
  sessionId: string,
  content: string,
  handlers: SSEHandlers
): Promise<void> {
  const url = `${BASE_URL}/api/v1/sessions/${sessionId}/execute`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({ content }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let currentEvent = 'message';

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          handlers.onComplete?.();
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');

        // Keep the last potentially incomplete line in the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6);
            try {
              const parsed = JSON.parse(data);
              handlers.onMessage({
                event: currentEvent,
                data: parsed,
              });
            } catch {
              // If not JSON, treat as plain text
              handlers.onMessage({
                event: currentEvent,
                data: { content: data },
              });
            }
            currentEvent = 'message'; // Reset to default
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  } catch (error) {
    handlers.onError?.(error instanceof Error ? error : new Error(String(error)));
  }
}
