import type { Asset, MatchStatus, Project, ScriptSegment, VideoStructure } from '../shared/types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export interface AnalysisJob {
  job_id: string;
}

export interface AnalysisStatus {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  stage: string;
  result?: VideoStructure;
  error?: string | null;
}

export interface StructureActionResponse {
  action: 'undo' | 'redo';
  available: boolean;
  structure: VideoStructure;
}

export interface AssetAnalyzeResponse {
  asset_id: string;
  analysis: Record<string, unknown>;
}

export interface AssetMatchResponse {
  matches: Array<{ asset_id: string; segment_id: string; score: number; status: MatchStatus }>;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const init: RequestInit = { ...options };
  const isFormData = init.body instanceof FormData;

  if (init.body && !isFormData) {
    init.headers = { 'Content-Type': 'application/json', ...(init.headers ?? {}) };
  }

  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new ApiError(await extractErrorMessage(response), response.status);
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload.detail === 'string') return payload.detail;
    if (Array.isArray(payload.detail) && payload.detail[0]?.msg) return payload.detail[0].msg;
  } catch {
    // Fall through to generic message.
  }
  return `Request failed with status ${response.status}`;
}

export const api = {
  listProjects: () => request<Project[]>('/api/v1/projects'),
  createProject: (payload: { name: string; description: string }) =>
    request<Project>('/api/v1/projects', { method: 'POST', body: JSON.stringify(payload) }),
  getProject: (projectId: string) => request<Project>(`/api/v1/projects/${projectId}`),
  deleteProject: (projectId: string) => request<void>(`/api/v1/projects/${projectId}`, { method: 'DELETE' }),
  startAnalysis: (file: File, projectId?: string) => {
    const form = new FormData();
    form.append('video', file);
    if (projectId) form.append('project_id', projectId);
    return request<AnalysisJob>('/api/v1/analyze', { method: 'POST', body: form });
  },
  getAnalysis: (jobId: string) => request<AnalysisStatus>(`/api/v1/analyze/${jobId}`),
  analyzeAsset: (projectId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<AssetAnalyzeResponse>(`/api/v1/assets/analyze/${projectId}`, { method: 'POST', body: form });
  },
  listAssets: (projectId: string) => request<Asset[]>(`/api/v1/assets/${projectId}`),
  matchAssets: (projectId: string) => request<AssetMatchResponse>(`/api/v1/assets/${projectId}/match`),
  getStructure: (projectId: string) => request<VideoStructure>(`/api/v1/structure/${projectId}`),
  replaceStructure: (projectId: string, structure: VideoStructure) =>
    request<VideoStructure>(`/api/v1/structure/${projectId}`, { method: 'PUT', body: JSON.stringify(structure) }),
  addSegment: (projectId: string, segment: Partial<ScriptSegment>) =>
    request<VideoStructure>(`/api/v1/structure/${projectId}/segment`, { method: 'POST', body: JSON.stringify(segment) }),
  updateSegment: (projectId: string, segmentId: string, changes: Partial<ScriptSegment>) =>
    request<VideoStructure>(`/api/v1/structure/${projectId}/segment/${segmentId}`, { method: 'PUT', body: JSON.stringify(changes) }),
  deleteSegment: (projectId: string, segmentId: string) =>
    request<VideoStructure>(`/api/v1/structure/${projectId}/segment/${segmentId}`, { method: 'DELETE' }),
  reorderSegments: (projectId: string, order: string[]) =>
    request<VideoStructure>(`/api/v1/structure/${projectId}/reorder`, { method: 'PUT', body: JSON.stringify({ order }) }),
  undo: (projectId: string) => request<StructureActionResponse>(`/api/v1/structure/${projectId}/undo`, { method: 'POST' }),
  redo: (projectId: string) => request<StructureActionResponse>(`/api/v1/structure/${projectId}/redo`, { method: 'POST' }),
  resetStructure: (projectId: string) => request<VideoStructure>(`/api/v1/structure/${projectId}/reset`, { method: 'POST' }),
};
