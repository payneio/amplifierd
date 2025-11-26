import { fetchApi } from './client';
import type { Profile } from '@/types/api';

export const listProfiles = () =>
  fetchApi<Profile[]>('/api/v1/profiles');

export const getProfile = (name: string) =>
  fetchApi<Profile>(`/api/v1/profiles/${name}`);
