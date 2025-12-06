import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Brain, ChevronDown, ChevronRight } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import type { ThinkingBlock } from '@/features/session/types/execution';

interface ThinkingViewerProps {
  thinking: ThinkingBlock[];
  inline?: boolean;
  defaultExpanded?: boolean;
}

export function ThinkingViewer({
  thinking,
  inline = false,
  defaultExpanded = false,
}: ThinkingViewerProps) {
  const [isOpen, setIsOpen] = useState(defaultExpanded);

  if (thinking.length === 0) {
    return null;
  }

  const blockCount = thinking.length;
  const sortedThinking = [...thinking].sort((a, b) => a.timestamp - b.timestamp);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div
        className={`rounded-lg border ${
          inline
            ? 'bg-muted/50 border-muted-foreground/20'
            : 'bg-background border-border'
        }`}
      >
        {/* Collapsed header */}
        <CollapsibleTrigger className="w-full">
          <div
            className={`flex items-center gap-2 p-3 hover:bg-accent/50 transition-colors ${
              inline ? 'text-sm' : ''
            }`}
          >
            <Brain className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="text-muted-foreground font-medium">
              Thinking {blockCount > 1 && `(${blockCount} blocks)`}
            </span>
            <div className="flex-1" />
            {isOpen ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        </CollapsibleTrigger>

        {/* Expanded content */}
        <CollapsibleContent>
          <div
            className={`border-t border-muted-foreground/20 ${
              inline ? 'p-3' : 'p-4'
            } space-y-4`}
          >
            {sortedThinking.map((block, idx) => (
              <div key={block.id} className="space-y-2">
                {/* Timestamp - only show in panel mode or if multiple blocks */}
                {(!inline || blockCount > 1) && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-mono">
                      {new Date(block.timestamp).toLocaleTimeString()}
                    </span>
                    {blockCount > 1 && (
                      <span className="text-muted-foreground/60">
                        Block {idx + 1} of {blockCount}
                      </span>
                    )}
                  </div>
                )}

                {/* Thinking content */}
                <div
                  className={`prose prose-sm dark:prose-invert max-w-none text-muted-foreground ${
                    inline ? 'prose-xs' : ''
                  }`}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      // Style code blocks with monospace font
                      code: ({ className, children, ...props }) => {
                        const isInline = !className;
                        return isInline ? (
                          <code
                            className="bg-muted px-1 py-0.5 rounded font-mono text-xs"
                            {...props}
                          >
                            {children}
                          </code>
                        ) : (
                          <code
                            className={`${className} font-mono text-xs`}
                            {...props}
                          >
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {block.content}
                  </ReactMarkdown>
                </div>

                {/* Separator between blocks */}
                {idx < blockCount - 1 && (
                  <div className="border-t border-muted-foreground/10 pt-2" />
                )}
              </div>
            ))}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
