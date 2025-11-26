import { useEffect } from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import { DirectoriesList } from './DirectoriesList';
import { SessionsList } from './SessionsList';

export function DirectoriesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const selectedPath = searchParams.get('path') || undefined;

  // Save current URL to sessionStorage for nav link persistence
  useEffect(() => {
    const fullPath = location.pathname + location.search;
    sessionStorage.setItem('lastDirectoriesUrl', fullPath);
  }, [location]);

  const handleSelectDirectory = (path: string) => {
    setSearchParams({ path });
  };

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
          onSelectDirectory={handleSelectDirectory}
          selectedPath={selectedPath}
        />

        {selectedPath && (
          <SessionsList directoryPath={selectedPath} />
        )}
      </div>
    </div>
  );
}
