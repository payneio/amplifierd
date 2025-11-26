import { useProfiles } from '../hooks/useCollections';

export function ProfilesList() {
  const { profiles, isLoading } = useProfiles();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading profiles...</div>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Profiles</h2>

      {profiles.length === 0 ? (
        <div className="text-muted-foreground text-center py-8">
          No profiles found
        </div>
      ) : (
        <div className="grid gap-4">
          {profiles.map((profile) => (
            <div
              key={profile.name}
              className="border rounded-lg p-4 hover:bg-accent transition-colors"
            >
              <h3 className="font-semibold">{profile.name}</h3>
              {profile.description && (
                <p className="text-sm text-muted-foreground">{profile.description}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
