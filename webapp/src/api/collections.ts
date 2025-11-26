import { fetchApi } from './client';
import type { Collection, SyncCollectionsResponse } from '@/types/api';

export const listCollections = () =>
  fetchApi<Collection[]>('/api/v1/collections');

export const getCollection = (identifier: string) =>
  fetchApi<Collection>(`/api/v1/collections/${identifier}`);

export const syncCollections = (params?: {
  force_refresh?: boolean;
  auto_compile?: boolean;
  force_compile?: boolean;
}) => {
  const searchParams = new URLSearchParams();
  if (params?.force_refresh) searchParams.set('force_refresh', 'true');
  if (params?.auto_compile !== undefined) searchParams.set('auto_compile', String(params.auto_compile));
  if (params?.force_compile) searchParams.set('force_compile', 'true');

  const query = searchParams.toString();
  return fetchApi<SyncCollectionsResponse>(
    `/api/v1/collections/sync${query ? `?${query}` : ''}`
  );
};
