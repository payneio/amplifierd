import { Sparkles, Wrench, Bot } from 'lucide-react';
import type { CurrentActivity } from '../types/execution';

interface CurrentActivityIndicatorProps {
  activity: CurrentActivity | null;
}

export function CurrentActivityIndicator({ activity }: CurrentActivityIndicatorProps) {
  console.log('[CurrentActivityIndicator] Rendering with activity:', activity);
  if (!activity) return null;

  const truncateArgs = (args?: Record<string, unknown>): string => {
    if (!args) return '';
    const argsString = JSON.stringify(args);
    return argsString.length > 100 ? `${argsString.slice(0, 97)}...` : argsString;
  };

  const getIcon = () => {
    switch (activity.type) {
      case 'thinking':
        return <Sparkles className="h-3 w-3 text-muted-foreground" />;
      case 'tool':
        return <Wrench className="h-3 w-3 text-muted-foreground" />;
      case 'subagent':
        return <Bot className="h-3 w-3 text-purple-500" />;
    }
  };

  const getContent = () => {
    switch (activity.type) {
      case 'thinking':
        return (
          <span className="text-xs text-muted-foreground">Thinking...</span>
        );
      case 'tool':
        return (
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-muted-foreground">
              Calling: <span className="font-medium">{activity.toolName}</span>
            </span>
            {activity.args && (
              <span className="text-[10px] text-muted-foreground/70 font-mono">
                Arguments: {truncateArgs(activity.args)}
              </span>
            )}
          </div>
        );
      case 'subagent':
        return (
          <div className="flex items-center gap-1">
            <span className="text-xs text-purple-600 dark:text-purple-400">
              Running: <span className="font-medium">{activity.subAgentName}</span>
            </span>
          </div>
        );
    }
  };

  return (
    <div className="flex items-start gap-2 px-3 py-2 border-l-2 border-muted-foreground/20 bg-muted/30 rounded-sm animate-pulse">
      <div className="shrink-0 pt-0.5">
        {getIcon()}
      </div>
      <div className="flex-1 min-w-0">
        {getContent()}
      </div>
    </div>
  );
}
