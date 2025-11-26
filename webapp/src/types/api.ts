export interface Collection {
  identifier: string;
  source: string;
  version?: string;
  description?: string;
  last_synced?: string;
  profiles?: string[];
  metadata?: Record<string, unknown>;
}

export interface Profile {
  name: string;
  description?: string;
  base_profile?: string;
  settings?: Record<string, unknown>;
  context_files?: string[];
  metadata?: Record<string, unknown>;
}

export interface AmplifiedDirectory {
  path: string;
  relative_path: string;
  default_profile?: string;
  metadata?: Record<string, unknown>;
  is_amplified: boolean;
}

export interface AmplifiedDirectoryCreate {
  path: string;
  default_profile?: string;
  metadata?: Record<string, unknown>;
  create_marker?: boolean;
}

export interface Session {
  session_id: string;
  profile_name: string;
  status: 'CREATED' | 'ACTIVE' | 'COMPLETED' | 'FAILED' | 'TERMINATED';
  created_at: string;
  started_at?: string;
  completed_at?: string;
  parent_session_id?: string;
  settings_overrides?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface SessionMessage {
  role: string;
  content: string;
  timestamp: string;
  agent?: string;
  token_count?: number;
  metadata?: Record<string, unknown>;
}

export interface CreateSessionRequest {
  profile_name: string;
  parent_session_id?: string;
  settings_overrides?: Record<string, unknown>;
}

export interface SyncCollectionsResponse {
  collections: Record<string, string>;
  modules: Record<string, unknown>;
}

export interface ListDirectoriesResponse {
  directories: AmplifiedDirectory[];
  total: number;
}
