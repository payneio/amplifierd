import { useState } from 'react';
import { DirectoriesList } from './DirectoriesList';
import { SessionsList } from './SessionsList';

export function DirectoriesPage() {
  const [selectedPath, setSelectedPath] = useState<string>();

  return (
    <div className="container mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-3xl font-bold mb-2">Amplified Directories</h1>
        <p className="text-muted-foreground">
          Browse directories and manage sessions
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        <DirectoriesList
          onSelectDirectory={setSelectedPath}
          selectedPath={selectedPath}
        />

        {selectedPath && (
          <SessionsList directoryPath={selectedPath} />
        )}
      </div>
    </div>
  );
}
