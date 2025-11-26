import { fetchApi } from './client';
import type { AmplifiedDirectory, AmplifiedDirectoryCreate, ListDirectoriesResponse } from '@/types/api';

export const listDirectories = () =>
  fetchApi<ListDirectoriesResponse>('/amplified-directories');

export const getDirectory = (relativePath: string) =>
  fetchApi<AmplifiedDirectory>(`/amplified-directories/${relativePath}`);

export const createDirectory = (data: AmplifiedDirectoryCreate) =>
  fetchApi<AmplifiedDirectory>('/amplified-directories', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updateDirectory = (
  relativePath: string,
  data: Partial<AmplifiedDirectoryCreate>
) =>
  fetchApi<AmplifiedDirectory>(`/amplified-directories/${relativePath}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const deleteDirectory = (
  relativePath: string,
  removeMarker: boolean = false
) =>
  fetchApi<void>(
    `/amplified-directories/${relativePath}?remove_marker=${removeMarker}`,
    { method: 'DELETE' }
  );
