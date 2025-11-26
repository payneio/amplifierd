import { CollectionsList } from './CollectionsList';
import { ProfilesList } from './ProfilesList';

export function CollectionsPage() {
  return (
    <div className="container mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-3xl font-bold mb-2">Collections & Profiles</h1>
        <p className="text-muted-foreground">
          Manage your amplifier collections and profiles
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        <CollectionsList />
        <ProfilesList />
      </div>
    </div>
  );
}
