import { useState } from 'react';
import { Plus, Edit, Trash2 } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useProfiles } from '../hooks/useCollections';
import { ProfileDetailModal } from './ProfileDetailModal';
import { ProfileForm } from './ProfileForm';
import * as api from '@/api/profiles';
import type { CreateProfileRequest, UpdateProfileRequest, ProfileDetails } from '@/types/api';

export function ProfilesList() {
  const { profiles, isLoading } = useProfiles();
  const queryClient = useQueryClient();
  const [selectedProfile, setSelectedProfile] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ProfileDetails | null>(null);

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

  const handleDelete = (profileName: string, source: string) => {
    if (!source.startsWith('local/')) {
      alert('Only local profiles can be deleted');
      return;
    }
    if (confirm(`Delete profile "${profileName}"?`)) {
      deleteMutation.mutate(profileName);
    }
  };

  const handleEdit = (profile: ProfileDetails) => {
    if (!profile.source.startsWith('local/')) {
      alert('Only local profiles can be edited');
      return;
    }
    setEditingProfile(profile);
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading profiles...</div>;
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">Profiles</h2>
          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            Create Profile
          </button>
        </div>

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
                <div className="flex items-start justify-between">
                  <button
                    onClick={() => setSelectedProfile(profile.name)}
                    className="flex-1 text-left"
                  >
                    <h3 className="font-semibold">{profile.name}</h3>
                    {profile.description && (
                      <p className="text-sm text-muted-foreground">{profile.description}</p>
                    )}
                    <p className="text-xs text-muted-foreground mt-1">
                      Source: {profile.source}
                    </p>
                  </button>
                  {profile.source.startsWith('local/') && (
                    <div className="flex gap-2 ml-4">
                      <button
                        onClick={async () => {
                          const details = await api.getProfileDetails(profile.name);
                          handleEdit(details);
                        }}
                        className="p-2 hover:bg-background rounded-md"
                        title="Edit profile"
                      >
                        <Edit className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(profile.name, profile.source)}
                        className="p-2 hover:bg-background rounded-md text-destructive"
                        title="Delete profile"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <ProfileDetailModal
        profileName={selectedProfile}
        onClose={() => setSelectedProfile(null)}
        onEdit={(profile) => {
          setSelectedProfile(null);
          handleEdit(profile);
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
