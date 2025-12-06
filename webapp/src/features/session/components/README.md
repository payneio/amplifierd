# Execution Panel Components

Implementation of the execution trace panel as specified in `@working/improving-session-affordance.md`.

## Components

### ExecutionPanel
Main container for the execution trace panel.

**Features:**
- Desktop: Right-side slide-in panel (fixed, 384px width)
- Mobile: Bottom sheet with swipe gestures
- Toggle button when closed
- Overlay on mobile for dismissal

**Props:**
- `executionState: ExecutionState` - Current execution state with turns and metrics
- `isOpen: boolean` - Panel open/closed state
- `onClose: () => void` - Callback to close the panel

### TurnsList
Accordion list of all turns in the session.

**Features:**
- Accordion with multiple turns expandable
- Auto-expands active turns
- Shows turn number and user message preview
- Displays tool count badge

**Props:**
- `turns: Turn[]` - Array of turns to display

### TurnItem
Individual turn display within the accordion.

**Features:**
- Live duration updates for active turns
- Status indicator (waiting, active, completed, error)
- Expandable to show tools and thinking blocks
- Full user message display when expanded

**Props:**
- `turn: Turn` - Turn data to display
- `turnNumber: number` - Turn sequence number

### ToolTraceList
List of tools executed in a turn.

**Features:**
- Maps over tools array
- Empty state message
- Renders ToolCallItem for each tool

**Props:**
- `tools: ToolCall[]` - Array of tools to display

### ToolCallItem
Individual tool call display.

**Features:**
- Status icon with color coding:
  - ⏳ Starting (gray)
  - 🔄 Running (blue, animated spinner)
  - ✓ Completed (green)
  - ❌ Error (red)
  - ⚡ Sub-agent (purple with badge)
- Duration display in milliseconds
- Expandable details section with:
  - Arguments (formatted JSON)
  - Result (first line summary with "Show Full Result" button)
  - Error message (if error)
- Special styling for sub-agents (purple accent)

**Props:**
- `tool: ToolCall` - Tool data to display

### MetricsSummary
Session-wide metrics display.

**Features:**
- Grid layout with 4 metrics:
  - 🔧 Total Tools
  - ⏱️ Average Duration
  - 🧠 Thinking Blocks
  - 🏆 Longest Tool (name and duration)
- Color-coded icons
- Responsive grid (2 columns)

**Props:**
- `metrics: SessionMetrics` - Session metrics to display

## Usage Example

```tsx
import { ExecutionPanel } from '@/features/session/components/ExecutionPanel';
import { useExecutionState } from '@/features/session/hooks/useExecutionState';

function SessionView() {
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const executionState = useExecutionState(sessionId);

  return (
    <div>
      {/* Session content */}

      <ExecutionPanel
        executionState={executionState}
        isOpen={isPanelOpen}
        onClose={() => setIsPanelOpen(false)}
      />
    </div>
  );
}
```

## Styling

All components use:
- Tailwind CSS for styling
- Lucide React for icons
- Radix UI primitives (accordion, collapsible)
- Custom CSS animations for accordion (in `src/index.css`)

## Responsive Design

**Desktop (md+):**
- Side panel slides in from right
- Fixed width (384px)
- Toggle button on right edge when closed

**Mobile (<md):**
- Bottom sheet with handle for swipe
- Max height 80vh
- Floating toggle button (bottom-right)
- Dark overlay when open

## Accessibility

- Keyboard navigation supported via Radix UI
- ARIA labels on buttons
- Semantic HTML structure
- Focus management in accordions

## Type Safety

All components are fully typed with TypeScript using types from:
- `@/features/session/types/execution.ts`

## Dependencies

```json
{
  "@radix-ui/react-accordion": "^1.2.12",
  "@radix-ui/react-collapsible": "^1.1.12",
  "lucide-react": "^0.516.0"
}
```
