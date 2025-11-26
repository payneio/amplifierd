import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api';

export function useCollections() {
  const queryClient = useQueryClient();

  const collections = useQuery({
    queryKey: ['collections'],
    queryFn: api.listCollections,
  });

  const syncCollections = useMutation({
    mutationFn: (params?: Parameters<typeof api.syncCollections>[0]) =>
      api.syncCollections(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
    },
  });

  return {
    collections: collections.data ?? [],
    isLoading: collections.isLoading,
    error: collections.error,
    syncCollections,
  };
}

export function useProfiles() {
  const profiles = useQuery({
    queryKey: ['profiles'],
    queryFn: api.listProfiles,
  });

  return {
    profiles: profiles.data ?? [],
    isLoading: profiles.isLoading,
    error: profiles.error,
  };
}
