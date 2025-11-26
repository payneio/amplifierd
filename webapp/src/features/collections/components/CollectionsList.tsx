import { RefreshCw } from 'lucide-react';
import { useCollections } from '../hooks/useCollections';
import { cn } from '@/lib/utils';

export function CollectionsList() {
  const { collections, isLoading, syncCollections } = useCollections();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading collections...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Collections</h2>
        <button
          onClick={() => syncCollections.mutate(undefined)}
          disabled={syncCollections.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
        >
          <RefreshCw className={cn("h-4 w-4", syncCollections.isPending && "animate-spin")} />
          {syncCollections.isPending ? 'Syncing...' : 'Sync All'}
        </button>
      </div>

      {collections.length === 0 ? (
        <div className="text-muted-foreground text-center py-8">
          No collections found
        </div>
      ) : (
        <div className="grid gap-4">
          {collections.map((collection) => (
            <div
              key={collection.identifier}
              className="border rounded-lg p-4 hover:bg-accent transition-colors"
            >
              <h3 className="font-semibold">{collection.identifier}</h3>
              <p className="text-sm text-muted-foreground">{collection.source}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
