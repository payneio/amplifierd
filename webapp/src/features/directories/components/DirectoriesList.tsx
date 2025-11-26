import { Folder, Plus } from 'lucide-react';
import { useDirectories } from '../hooks/useDirectories';

interface DirectoriesListProps {
  onSelectDirectory: (path: string) => void;
  selectedPath?: string;
}

export function DirectoriesList({ onSelectDirectory, selectedPath }: DirectoriesListProps) {
  const { directories, isLoading } = useDirectories();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading directories...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Amplified Directories</h2>
        <button className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-sm">
          <Plus className="h-4 w-4" />
          New
        </button>
      </div>

      {directories.length === 0 ? (
        <div className="text-muted-foreground text-center py-8">
          No amplified directories found
        </div>
      ) : (
        <div className="space-y-2">
          {directories.map((dir) => (
            <button
              key={dir.relative_path}
              onClick={() => onSelectDirectory(dir.relative_path)}
              className={`w-full text-left flex items-center gap-3 p-3 rounded-md transition-colors ${
                selectedPath === dir.relative_path
                  ? 'bg-primary/10 text-primary border border-primary'
                  : 'hover:bg-accent border border-transparent'
              }`}
            >
              <Folder className="h-4 w-4 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="font-medium truncate">{dir.relative_path}</div>
                {dir.default_profile && (
                  <div className="text-xs text-muted-foreground truncate">
                    Profile: {dir.default_profile}
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
