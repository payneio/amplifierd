import { useParams, useNavigate } from 'react-router';
import { ArrowLeft, Play } from 'lucide-react';
import { useSession } from '../hooks/useSession';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api';

export function SessionView() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  if (!sessionId) {
    return <div>No session ID provided</div>;
  }

  const { session, transcript, isLoading, startSession } = useSession(sessionId);

  const sendMessage = useMutation({
    mutationFn: (content: string) => api.sendMessage(sessionId, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcript', sessionId] });
    },
  });

  const handleSend = (message: string) => {
    sendMessage.mutate(message);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">Loading session...</div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">Session not found</div>
      </div>
    );
  }

  const needsStart = session.status === 'CREATED';

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b p-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-xl font-bold">Session: {sessionId}</h1>
            <p className="text-sm text-muted-foreground">
              Profile: {session.profile_name} • Status: {session.status}
            </p>
          </div>
          {needsStart && (
            <button
              onClick={() => startSession.mutate(undefined)}
              disabled={startSession.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              {startSession.isPending ? 'Starting...' : 'Start Session'}
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <MessageList messages={transcript} />

      {/* Input */}
      <MessageInput
        onSend={handleSend}
        disabled={needsStart || sendMessage.isPending}
      />
    </div>
  );
}
