import React from 'react';
import { Accordion } from '@/components/ui/accordion';
import type { Turn } from '../types/execution';
import { TurnItem } from './TurnItem';

interface TurnsListProps {
  turns: Turn[];
}

export function TurnsList({ turns }: TurnsListProps) {
  // Default to last turn expanded
  const [expandedTurns, setExpandedTurns] = React.useState<string[]>(() => {
    if (turns.length > 0) {
      return [turns[turns.length - 1].id];
    }
    return [];
  });

  // Auto-expand new active turns
  React.useEffect(() => {
    const activeTurn = turns.find((turn) => turn.status === 'active');
    if (activeTurn && !expandedTurns.includes(activeTurn.id)) {
      setExpandedTurns((prev) => [...prev, activeTurn.id]);
    }
  }, [turns, expandedTurns]);

  if (turns.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-8">
        No turns yet. Send a message to start.
      </div>
    );
  }

  return (
    <Accordion
      type="multiple"
      value={expandedTurns}
      onValueChange={setExpandedTurns}
      className="w-full"
    >
      {turns.map((turn, index) => (
        <TurnItem key={turn.id} turn={turn} turnNumber={index + 1} />
      ))}
    </Accordion>
  );
}
