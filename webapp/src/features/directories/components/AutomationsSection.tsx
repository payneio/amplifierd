/**
 * AutomationsSection - Demo UI for workflow automation
 *
 * This is a demonstration component with mock data and simulated execution.
 * No backend integration - for UI preview only.
 */
import { useState, useEffect } from "react";
import { formatDistanceToNow } from "date-fns";
import {
  CheckCircle,
  XCircle,
  Loader2,
  Play,
  Trash2,
  Plus,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type WorkflowStatus = "never_run" | "running" | "success" | "failed";

// Demo configuration constants
const DEMO_EXECUTION_DELAY_MS = 2000;
const DEMO_SUCCESS_RATE = 0.8;

// Status display configuration
const STATUS_CONFIG = {
  success: { icon: CheckCircle, text: "Success", className: "text-green-600", animate: false },
  failed: { icon: XCircle, text: "Failed", className: "text-red-600", animate: false },
  running: { icon: Loader2, text: "Running", className: "text-blue-600", animate: true },
  never_run: { icon: null, text: "Never run", className: "text-gray-500", animate: false },
} as const;

interface Workflow {
  id: string;
  name: string;
  description: string;
  status: WorkflowStatus;
  last_run?: string;
  schedule?: string;
}

const INITIAL_WORKFLOWS: Workflow[] = [
  {
    id: "1",
    name: "Daily Summary Email",
    description:
      "Generates a comprehensive daily summary of project activities and sends via email",
    status: "success",
    last_run: new Date().toISOString(),
    schedule: "Daily at 9:00 AM",
  },
  {
    id: "2",
    name: "Lead Dossier Generator",
    description:
      "Creates detailed dossiers for new customer leads including background research",
    status: "never_run",
    schedule: "On specific event",
  },
  {
    id: "3",
    name: "Weekly Performance Review",
    description:
      "Analyzes project performance metrics and generates insights report",
    status: "failed",
    last_run: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    schedule: "Weekly on Mondays",
  },
];

interface AutomationsSectionProps {
  directoryPath: string; // Reserved for backend integration
  onRunningCountChange?: (count: number) => void; // Callback when running workflow count changes
}

export function AutomationsSection({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  directoryPath, // Reserved for backend integration
  onRunningCountChange,
}: AutomationsSectionProps) {
  const [workflows, setWorkflows] = useState<Workflow[]>(INITIAL_WORKFLOWS);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [workflowToDelete, setWorkflowToDelete] = useState<string | null>(null);

  // Track running workflow count and notify parent
  useEffect(() => {
    const runningCount = workflows.filter((w) => w.status === "running").length;
    onRunningCountChange?.(runningCount);
  }, [workflows, onRunningCountChange]);

  const handleRunWorkflow = (workflowId: string) => {
    setWorkflows((prev) =>
      prev.map((w) =>
        w.id === workflowId
          ? { ...w, status: "running" as WorkflowStatus }
          : w
      )
    );

    setTimeout(() => {
      const success = Math.random() < DEMO_SUCCESS_RATE;
      setWorkflows((prev) =>
        prev.map((w) =>
          w.id === workflowId
            ? {
                ...w,
                status: (success ? "success" : "failed") as WorkflowStatus,
                last_run: new Date().toISOString(),
              }
            : w
        )
      );
    }, DEMO_EXECUTION_DELAY_MS);
  };

  const handleAddWorkflow = (workflow: Omit<Workflow, "id" | "status">) => {
    const newWorkflow: Workflow = {
      ...workflow,
      id: crypto.randomUUID(),
      status: "never_run",
    };
    setWorkflows((prev) => [...prev, newWorkflow]);
    setIsAddDialogOpen(false);
  };

  const handleDeleteWorkflow = (workflowId: string) => {
    setWorkflows((prev) => prev.filter((w) => w.id !== workflowId));
    setWorkflowToDelete(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          onClick={() => setIsAddDialogOpen(true)}
          className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent text-sm"
        >
          <Plus className="h-4 w-4" />
          Add Workflow
        </button>
      </div>

      {workflows.length === 0 ? (
        <div className="border rounded-lg p-8 text-center text-muted-foreground">
          No workflows configured. Add your first automation to get started.
        </div>
      ) : (
        <div className="space-y-4">
          {workflows.map((workflow) => (
            <WorkflowCard
              key={workflow.id}
              workflow={workflow}
              onRun={handleRunWorkflow}
              onDelete={(id) => setWorkflowToDelete(id)}
            />
          ))}
        </div>
      )}

      <AddWorkflowDialog
        open={isAddDialogOpen}
        onOpenChange={setIsAddDialogOpen}
        onAdd={handleAddWorkflow}
      />

      <Dialog
        open={workflowToDelete !== null}
        onOpenChange={(open) => !open && setWorkflowToDelete(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Workflow</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this workflow? This action cannot
              be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button
              onClick={() => setWorkflowToDelete(null)}
              className="px-3 py-2 border rounded-md hover:bg-accent text-sm"
            >
              Cancel
            </button>
            <button
              onClick={() =>
                workflowToDelete && handleDeleteWorkflow(workflowToDelete)
              }
              className="px-3 py-2 bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/90 text-sm"
            >
              Delete
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

interface WorkflowCardProps {
  workflow: Workflow;
  onRun: (id: string) => void;
  onDelete: (id: string) => void;
}

function WorkflowCard({ workflow, onRun, onDelete }: WorkflowCardProps) {
  const config = STATUS_CONFIG[workflow.status];
  const Icon = config.icon;
  const statusDisplay = {
    icon: Icon ? <Icon className={`h-4 w-4 ${config.animate ? 'animate-spin' : ''}`} /> :
                 <div className="h-4 w-4 rounded-full border-2 border-gray-500" />,
    text: config.text,
    className: config.className,
  };

  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h4 className="font-semibold truncate">{workflow.name}</h4>
            <div className={`flex items-center gap-1 text-sm ${statusDisplay.className}`}>
              {statusDisplay.icon}
              <span>{statusDisplay.text}</span>
            </div>
          </div>
          <p className="text-sm text-muted-foreground mb-3">
            {workflow.description}
          </p>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            {workflow.schedule && (
              <div>
                <span className="font-medium">Schedule:</span> {workflow.schedule}
              </div>
            )}
            {workflow.last_run && (
              <div>
                <span className="font-medium">Last run:</span>{" "}
                {formatDistanceToNow(new Date(workflow.last_run), {
                  addSuffix: true,
                })}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => onRun(workflow.id)}
            disabled={workflow.status === "running"}
            className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play className="h-4 w-4" />
            Run
          </button>
          <button
            onClick={() => onDelete(workflow.id)}
            disabled={workflow.status === "running"}
            className="flex items-center gap-2 px-3 py-2 border border-destructive text-destructive rounded-md hover:bg-destructive/10 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

interface AddWorkflowDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (workflow: Omit<Workflow, "id" | "status">) => void;
}

function AddWorkflowDialog({
  open,
  onOpenChange,
  onAdd,
}: AddWorkflowDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [schedule, setSchedule] = useState("Manual only");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !description.trim()) return;

    onAdd({
      name: name.trim(),
      description: description.trim(),
      schedule: schedule === "Manual only" ? undefined : schedule,
    });

    setName("");
    setDescription("");
    setSchedule("Manual only");
  };

  const handleCancel = () => {
    setName("");
    setDescription("");
    setSchedule("Manual only");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Workflow</DialogTitle>
          <DialogDescription>
            Create a new automation workflow for this project
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label htmlFor="name" className="text-sm font-medium">
                Workflow Name
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="e.g., Daily Report Generator"
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="description" className="text-sm font-medium">
                Description
              </label>
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full px-3 py-2 border rounded-md min-h-[80px] resize-y"
                placeholder="Describe what this workflow does..."
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="schedule" className="text-sm font-medium">
                Schedule
              </label>
              <select
                id="schedule"
                value={schedule}
                onChange={(e) => setSchedule(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value="Manual only">Manual only</option>
                <option value="Daily at 9:00 AM">Daily at 9:00 AM</option>
                <option value="Weekly on Mondays">Weekly on Mondays</option>
                <option value="On specific event">On specific event</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={handleCancel}
              className="px-3 py-2 border rounded-md hover:bg-accent text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-sm"
            >
              Add Workflow
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
