import { useState } from 'react';
import { ChevronDown, ChevronRight, RefreshCw, Plus, Edit, Trash2 } from 'lucide-react';
import { useCollections, useProfiles } from '../hooks/useCollections';
import { ProfileDetailModal } from './ProfileDetailModal';
import { ProfileForm } from './ProfileForm';
import { cn } from '@/lib/utils';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api';
import type { CreateProfileRequest, UpdateProfileRequest, ProfileDetails } from '@/types/api';

export function CollectionsWithProfiles() {
  const { collections, isLoading: collectionsLoading, syncCollections } = useCollections();
  const { profiles, isLoading: profilesLoading } = useProfiles();
  const queryClient = useQueryClient();
  const [expandedCollections, setExpandedCollections] = useState<Set<string>>(
    new Set(collections.map(c => c.identifier))
  );
  const [selectedProfile, setSelectedProfile] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ProfileDetails | null>(null);

  const isLoading = collectionsLoading || profilesLoading;

  const createMutation = useMutation({
    mutationFn: api.createProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      setIsCreating(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ name, data }: { name: string; data: UpdateProfileRequest }) =>
      api.updateProfile(name, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      setEditingProfile(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
    },
  });

  const handleEdit = async (profileName: string) => {
    const details = await api.getProfileDetails(profileName);
    if (!details.source.startsWith('local/')) {
      alert('Only local profiles can be edited');
      return;
    }
    setEditingProfile(details);
  };

  const handleDelete = (profileName: string, source: string) => {
    if (!source.startsWith('local/')) {
      alert('Only local profiles can be deleted');
      return;
    }
    if (confirm(`Delete profile "${profileName}"?`)) {
      deleteMutation.mutate(profileName);
    }
  };

  const toggleCollection = (identifier: string) => {
    setExpandedCollections(prev => {
      const next = new Set(prev);
      if (next.has(identifier)) {
        next.delete(identifier);
      } else {
        next.add(identifier);
      }
      return next;
    });
  };

  const profilesByCollection = new Map<string, typeof profiles>();
  for (const profile of profiles) {
    // Use the collectionId field directly instead of parsing the name
    const collectionId = profile.collectionId;
    if (collectionId) {
      if (!profilesByCollection.has(collectionId)) {
        profilesByCollection.set(collectionId, []);
      }
      profilesByCollection.get(collectionId)!.push(profile);
    }
  }

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Collections & Profiles</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setIsCreating(true)}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" />
              Create Profile
            </button>
            <button
              onClick={() => syncCollections.mutate(undefined)}
              disabled={syncCollections.isPending}
              className="flex items-center gap-2 px-4 py-2 border rounded-md hover:bg-accent disabled:opacity-50"
            >
              <RefreshCw className={cn("h-4 w-4", syncCollections.isPending && "animate-spin")} />
              {syncCollections.isPending ? 'Syncing...' : 'Sync'}
            </button>
          </div>
        </div>

        {collections.length === 0 ? (
          <div className="text-muted-foreground text-center py-8">
            No collections found
          </div>
        ) : (
          <div className="space-y-2">
            {collections.map((collection) => {
              const collectionProfiles = profilesByCollection.get(collection.identifier) || [];
              const isExpanded = expandedCollections.has(collection.identifier);

              return (
                <div
                  key={collection.identifier}
                  className="border rounded-lg overflow-hidden"
                >
                  <button
                    onClick={() => toggleCollection(collection.identifier)}
                    className="w-full flex items-center gap-2 p-4 hover:bg-accent transition-colors text-left"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-5 w-5 flex-shrink-0" />
                    ) : (
                      <ChevronRight className="h-5 w-5 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold">{collection.identifier}</h3>
                      <p className="text-sm text-muted-foreground truncate">
                        {collection.source}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {collectionProfiles.length} profile{collectionProfiles.length !== 1 ? 's' : ''}
                      </p>
                    </div>
                  </button>

                  {isExpanded && collectionProfiles.length > 0 && (
                    <div className="border-t bg-muted/30">
                      <div className="p-2 space-y-1">
                        {collectionProfiles.map((profile) => (
                          <div
                            key={profile.name}
                            className="flex items-start gap-2 px-4 py-3 rounded-md hover:bg-accent transition-colors group"
                          >
                            <button
                              onClick={() => setSelectedProfile(profile.name)}
                              className="flex-1 text-left"
                            >
                              <div className="font-medium text-sm">{profile.name}</div>
                              {profile.description && (
                                <div className="text-xs text-muted-foreground mt-1">
                                  {profile.description}
                                </div>
                              )}
                            </button>
                            {profile.source.startsWith('local/') && (
                              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                  onClick={() => handleEdit(profile.name)}
                                  className="p-1.5 hover:bg-background rounded-md"
                                  title="Edit profile"
                                >
                                  <Edit className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  onClick={() => handleDelete(profile.name, profile.source)}
                                  className="p-1.5 hover:bg-background rounded-md text-destructive"
                                  title="Delete profile"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {isExpanded && collectionProfiles.length === 0 && (
                    <div className="border-t p-4 text-sm text-muted-foreground text-center">
                      No profiles found for this collection
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <ProfileDetailModal
        profileName={selectedProfile}
        onClose={() => setSelectedProfile(null)}
        onEdit={(profile) => {
          setSelectedProfile(null);
          handleEdit(profile.name);
        }}
        onDelete={(name, source) => {
          setSelectedProfile(null);
          handleDelete(name, source);
        }}
      />

      {isCreating && (
        <ProfileForm
          isOpen={isCreating}
          onClose={() => setIsCreating(false)}
          onSubmit={(data) => createMutation.mutate(data as CreateProfileRequest)}
          mode="create"
        />
      )}

      {editingProfile && (
        <ProfileForm
          isOpen={!!editingProfile}
          onClose={() => setEditingProfile(null)}
          onSubmit={(data) =>
            updateMutation.mutate({
              name: editingProfile.name,
              data: data as UpdateProfileRequest,
            })
          }
          initialData={{
            name: editingProfile.name,
            version: editingProfile.version,
            description: editingProfile.description,
            providers: editingProfile.providers,
            tools: editingProfile.tools,
            hooks: editingProfile.hooks,
          }}
          mode="edit"
        />
      )}
    </>
  );
}
