import type {
  AnalysisSample,
  Asset,
  Capabilities,
  FinalScript,
  FinalScriptStyle,
  MaterialGap,
  MatchStatus,
  Project,
  ProjectBrief,
  RenderResolution,
  RenderStatus,
  RenderVersion,
  ResultVersionsResponse,
  ScriptSegment,
  VideoStructure,
} from '../shared/types';

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

export interface GapListResponse {
  gaps: MaterialGap[];
}

export interface GapFixResponse {
  gap_id: string;
  status: 'open' | 'fixed';
  updated_structure?: VideoStructure;
  assets?: Asset[];
  gaps?: MaterialGap[];
}

export interface GapFixAllResponse {
  fixed_count: number;
  details: GapFixResponse[];
  gaps: MaterialGap[];
  updated_structure?: VideoStructure;
  assets?: Asset[];
}

export interface RenderJobResponse {
  job_id: string;
}

export interface RenderProgressResponse {
  status: Exclude<RenderStatus, 'idle'>;
  progress: number;
  output_url?: string | null;
  error?: string | null;
  warnings: string[];
}

export type UploadProgressCallback = (percent: number) => void;

export function uploadWithProgress(
  url: string,
  formData: FormData,
  onProgress: UploadProgressCallback,
): Promise<AnalysisJob> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    });
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new ApiError(body.detail || xhr.statusText, xhr.status));
        } catch {
          reject(new ApiError(xhr.statusText, xhr.status));
        }
      }
    });
    xhr.addEventListener('error', () => reject(new ApiError('Network error', 0)));
    xhr.send(formData);
  });
}

const RETRYABLE_STATUSES = new Set([429, 502, 503, 504]);
const MAX_RETRIES = 2;
const RETRY_BASE_DELAY_MS = 1000;

function shouldRetry(method: string, status: number): boolean {
  if (!RETRYABLE_STATUSES.has(status)) return false;
  // Non-idempotent methods only retry on rate-limit or service-unavailable.
  if (method !== 'GET' && method !== 'HEAD' && status !== 429 && status !== 503) return false;
  return true;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const init: RequestInit = { ...options };
  const isFormData = init.body instanceof FormData;
  const method = (init.method ?? 'GET').toUpperCase();

  if (init.body && !isFormData) {
    init.headers = { 'Content-Type': 'application/json', ...(init.headers ?? {}) };
  }

  // Include API key when configured.
  const apiKey = (globalThis as Record<string, unknown>).__structforge_api_key as string | undefined;
  if (apiKey) {
    init.headers = { 'X-API-Key': apiKey, ...(init.headers ?? {}) };
  }

  let lastError: ApiError | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const response = await fetch(`${API_BASE_URL}${path}`, init);

    if (response.ok) {
      if (response.status === 204) return undefined as T;
      const text = await response.text();
      return (text ? JSON.parse(text) : undefined) as T;
    }

    const errorMessage = await extractErrorMessage(response);
    const error = new ApiError(errorMessage, response.status);

    // ── LLM Outage detection ──
    // When the backend returns 503 with the "llm_unavailable" error code,
    // the core AI engine is down. Show the interruption panel immediately
    // rather than treating this as a generic error toast.
    if (response.status === 503) {
      try {
        const body = await response.clone().json().catch(() => ({}));
        if (body?.error === 'llm_unavailable') {
          // Dynamically import store to avoid circular dependency
          const { useAppStore } = await import('../store');
          useAppStore.getState().setLLMOutage({
            operation: _inferOperation(path, method),
            error: (body?.message as string) || 'LLM 服务不可用',
            suggestion: (body?.suggestion as string) || '',
            retryable: body?.retryable !== false,
          });
        }
      } catch {
        // If parsing fails, fall through to normal error handling
      }
    }

    if (attempt < MAX_RETRIES && shouldRetry(method, response.status)) {
      const delay = RETRY_BASE_DELAY_MS * Math.pow(2, attempt);
      await new Promise((resolve) => setTimeout(resolve, delay));
      lastError = error;
      continue;
    }

    throw error;
  }

  throw lastError ?? new ApiError('Request failed', 0);
}

function _inferOperation(path: string, method: string): string {
  if (path.includes('/analyze')) return '视频分析';
  if (path.includes('/migrate') && method === 'POST') return '脚本迁移';
  if (path.includes('/nl-edit')) return '自然语言编辑';
  if (path.includes('/optimize') && method === 'POST') return '流水线优化';
  if (path.includes('/audit')) return '爆款审计';
  if (path.includes('/structure')) return '结构编辑';
  return 'AI 处理';
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
  getCapabilities: () => request<Capabilities>('/api/v1/capabilities'),
  listProjects: () => request<Project[]>('/api/v1/projects'),
  createProject: (payload: { name: string; description: string; brief?: ProjectBrief }) =>
    request<Project>('/api/v1/projects', { method: 'POST', body: JSON.stringify(payload) }),
  getProject: (projectId: string) => request<Project>(`/api/v1/projects/${projectId}`),
  updateProject: (projectId: string, payload: { name?: string; description?: string; brief?: ProjectBrief }) =>
    request<Project>(`/api/v1/projects/${projectId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteProject: (projectId: string) => request<void>(`/api/v1/projects/${projectId}`, { method: 'DELETE' }),
  startAnalysis: (file: File, projectId?: string) => {
    const form = new FormData();
    form.append('video', file);
    if (projectId) form.append('project_id', projectId);
    return request<AnalysisJob>('/api/v1/analyze', { method: 'POST', body: form });
  },
  getAnalysis: (jobId: string) => request<AnalysisStatus>(`/api/v1/analyze/${jobId}`),
  listAnalysisSamples: (projectId: string) => request<AnalysisSample[]>(`/api/v1/analyze/project/${projectId}/samples`),
  selectAnalysisReference: (projectId: string, jobId: string) =>
    request<AnalysisSample>(`/api/v1/analyze/project/${projectId}/reference/${jobId}`, { method: 'PUT' }),
  analyzeAsset: (projectId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<AssetAnalyzeResponse>(`/api/v1/assets/analyze/${projectId}`, { method: 'POST', body: form });
  },
  listAssets: (projectId: string) => request<Asset[]>(`/api/v1/assets/${projectId}`),
  matchAssets: (projectId: string) => request<AssetMatchResponse>(`/api/v1/assets/${projectId}/match`),
  listGaps: (projectId: string) => request<GapListResponse>(`/api/v1/gaps/${projectId}`),
  fixGap: (projectId: string, gapId: string, strategy: string) =>
    request<GapFixResponse>(`/api/v1/gaps/${projectId}/fix`, { method: 'POST', body: JSON.stringify({ gap_id: gapId, strategy }) }),
  fixAllGaps: (projectId: string) => request<GapFixAllResponse>(`/api/v1/gaps/${projectId}/fix-all`, { method: 'POST' }),
  migrateScript: (projectId: string, style: FinalScriptStyle = 'default') =>
    request<FinalScript>(`/api/v1/migrate/${projectId}`, { method: 'POST', body: JSON.stringify({ style }) }),
  migrateVariant: (projectId: string, style: Exclude<FinalScriptStyle, 'default'>) =>
    request<FinalScript>(`/api/v1/migrate/${projectId}/variant`, { method: 'POST', body: JSON.stringify({ style }) }),
  getFinalScript: (projectId: string) => request<FinalScript>(`/api/v1/migrate/${projectId}`),
  getResultVersions: (projectId: string) => request<ResultVersionsResponse>(`/api/v1/migrate/${projectId}/versions`),
  startRender: (projectId: string, version: RenderVersion, resolution: RenderResolution = '1080p', scriptVersion?: FinalScriptStyle) =>
    request<RenderJobResponse>(`/api/v1/render/${projectId}`, {
      method: 'POST',
      body: JSON.stringify({ version, resolution, ...(scriptVersion ? { script_version: scriptVersion } : {}) }),
    }),
  getRenderJob: (jobId: string) => request<RenderProgressResponse>(`/api/v1/render/${jobId}`),
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
  nlEditStructure: (projectId: string, command: string) =>
    request<{ structure: VideoStructure; changes_summary: string }>(`/api/v1/structure/${projectId}/nl-edit`, {
      method: 'POST',
      body: JSON.stringify({ command }),
    }),
  runOptimization: (projectId: string, payload: {
    product_name: string;
    product_type: string;
    selling_points: string[];
    target_audience?: string;
    offer?: string;
    tone?: string;
    platform?: string;
    version?: string;
  }) =>
    request<{ plan: Record<string, unknown>; success: boolean }>(`/api/v1/optimize/${projectId}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getWaveform: (projectId: string) =>
    request<{ data: number[]; duration: number; labels: Array<{ start: number; end: number; type: string }> }>(`/api/v1/optimize/${projectId}/waveform`),
  getThumbnail: (projectId: string, timeS: number) =>
    request<{ thumbnail: string | null }>(`/api/v1/optimize/${projectId}/thumbnail?t=${timeS.toFixed(1)}`),
  getBlueprintPayloads: (projectId: string) =>
    request<import('../shared/types').BlueprintPayloadsResponse>(`/api/v1/optimize/${projectId}/blueprint-payloads`),
};
