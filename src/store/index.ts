import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api, ApiError } from '../services/api';
import { mockAnalysisResult } from '../mocks/analysisResult';
import { humanizeError } from '../shared/errorMessages';
import { uid } from '../shared/format';
import type {
  AnalysisSample,
  Asset,
  FinalScript,
  FinalScriptStyle,
  MaterialGap,
  Project,
  ProjectBrief,
  RenderResolution,
  RenderStatus,
  RenderVersion,
  ResultVersion,
  ScriptSegment,
  ToastMessage,
  VideoStructure,
} from '../shared/types';

const analysisStages = [
  '\u6b63\u5728\u62bd\u5e27...',
  '\u6b63\u5728\u8bc6\u522b\u5173\u952e\u5e27...',
  '\u6b63\u5728\u5206\u6790\u811a\u672c\u7ed3\u6784...',
  '\u6b63\u5728\u8bc4\u4f30\u5065\u5eb7\u5ea6...',
];

function cloneStructure(structure: VideoStructure): VideoStructure {
  return JSON.parse(JSON.stringify(structure)) as VideoStructure;
}

function initialState() {
  return {
    sidebarCollapsed: false,
    mobileSidebarOpen: false,
    routeLoading: false,
    apiError: null as string | null,
    activeProjectId: null as string | null,
    projects: [] as Project[],
    videoFile: null,
    isAnalyzing: false,
    uploadProgress: 0,
    progress: 0,
    stage: analysisStages[0],
    analysisResult: null,
    analysisSamples: [] as AnalysisSample[],
    sampleLoading: false,
    currentStructure: null,
    assets: [] as Asset[],
    assetLoading: false,
    gapLoading: false,
    gaps: [] as MaterialGap[],
    isFixing: false,
    selectedSegmentId: null,
    drawerOpen: false,
    history: [] as VideoStructure[],
    future: [] as VideoStructure[],
    versions: [] as ResultVersion[],
    evaluationLabel: '',
    currentVersionId: 'original',
    currentScript: null,
    scriptLoading: false,
    renderJobId: null,
    renderStatus: 'idle' as RenderStatus,
    renderProgress: 0,
    outputUrl: null,
    renderError: null,
    isExporting: false,
    toasts: [] as ToastMessage[],
    lastFailedAction: null as string | null,
    lastFailedActionArgs: null as unknown[] | null,
  };
}

interface AppState {
  sidebarCollapsed: boolean;
  mobileSidebarOpen: boolean;
  routeLoading: boolean;
  apiError: string | null;
  activeProjectId: string | null;
  projects: Project[];
  videoFile: File | null;
  isAnalyzing: boolean;
  uploadProgress: number;
  progress: number;
  stage: string;
  analysisResult: VideoStructure | null;
  analysisSamples: AnalysisSample[];
  sampleLoading: boolean;
  currentStructure: VideoStructure | null;
  assets: Asset[];
  assetLoading: boolean;
  gapLoading: boolean;
  gaps: MaterialGap[];
  isFixing: boolean;
  selectedSegmentId: string | null;
  drawerOpen: boolean;
  history: VideoStructure[];
  future: VideoStructure[];
  versions: ResultVersion[];
  evaluationLabel: string;
  currentVersionId: string;
  currentScript: FinalScript | null;
  scriptLoading: boolean;
  renderJobId: string | null;
  renderStatus: RenderStatus;
  renderProgress: number;
  outputUrl: string | null;
  renderError: string | null;
  isExporting: boolean;
  toasts: ToastMessage[];
  lastFailedAction: string | null;
  lastFailedActionArgs: unknown[] | null;
  toggleSidebar: () => void;
  setMobileSidebarOpen: (open: boolean) => void;
  setRouteLoading: (loading: boolean) => void;
  fetchProjects: () => Promise<void>;
  addProject: (name: string, description: string, brief?: ProjectBrief) => Promise<string>;
  updateProjectBrief: (id: string, brief: ProjectBrief) => Promise<void>;
  removeProject: (id: string) => Promise<void>;
  findProject: (id: string) => Project | undefined;
  setVideoFile: (file: File | null) => void;
  startAnalysis: (projectId?: string) => Promise<string | undefined>;
  fetchAnalysisSamples: (projectId: string) => Promise<void>;
  selectReferenceSample: (projectId: string, jobId: string) => Promise<void>;
  resetAnalysis: () => void;
  completeAnalysisNow: () => void;
  loadProjectStructure: (projectId: string) => Promise<void>;
  fetchAssets: (projectId: string) => Promise<void>;
  uploadAsset: (file: File) => Promise<void>;
  fetchGaps: (projectId: string) => Promise<void>;
  fixGap: (gapId: string, strategy: string) => Promise<void>;
  fixAllGaps: () => Promise<void>;
  updateSegment: (id: string, changes: Partial<ScriptSegment>) => Promise<void>;
  reorderSegments: (activeId: string, overId: string) => Promise<void>;
  removeSelectedSegment: () => Promise<void>;
  selectSegment: (id: string | null) => void;
  setDrawerOpen: (open: boolean) => void;
  undo: () => Promise<void>;
  redo: () => Promise<void>;
  resetStructure: () => Promise<void>;
  nlEdit: (command: string) => Promise<void>;
  fixGaps: () => Promise<void>;
  migrateScript: (projectId: string, style?: FinalScriptStyle) => Promise<FinalScript | undefined>;
  loadFinalScript: (projectId: string) => Promise<void>;
  fetchResultVersions: (projectId: string) => Promise<void>;
  startRender: (projectId: string, version: RenderVersion, resolution?: RenderResolution, scriptVersion?: FinalScriptStyle) => Promise<void>;
  pollRenderJob: (jobId: string) => Promise<void>;
  setVersion: (id: string) => void;
  exportResult: () => Promise<void>;
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;
  retryLastAction: () => Promise<void>;
  resetForTest: () => void;
}

function getErrorMessage(error: unknown): string {
  const raw = error instanceof Error ? error.message : '\u672a\u77e5\u9519\u8bef';
  return humanizeError(raw);
}

function trackAction(set: (fn: (state: AppState) => Partial<AppState>) => void, actionName: string, args: unknown[]) {
  set(() => ({ lastFailedAction: actionName, lastFailedActionArgs: args }));
}

function clearTracking(set: (fn: (state: AppState) => Partial<AppState>) => void) {
  set(() => ({ lastFailedAction: null, lastFailedActionArgs: null }));
}

function projectNameFromFile(file: File): string {
  const base = file.name.replace(/\.[^.]+$/, '') || '\u672a\u547d\u540d\u9879\u76ee';
  // Don't use raw filenames as project names \u2014 they're often junk like "\u6296\u97f3202666-620593"
  // Keep it short and recognizable, but mark clearly as user-uploaded
  const cleaned = base.replace(/[_\-\.]+/g, ' ').trim();
  if (cleaned.length > 20) return cleaned.slice(0, 20) + '\u2026';
  return cleaned || '\u65b0\u89c6\u9891\u9879\u76ee';
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isOnline(): boolean {
  return typeof navigator !== 'undefined' ? navigator.onLine : true;
}

async function waitForNetwork(maxWaitMs: number = 30000): Promise<boolean> {
  if (isOnline()) return true;
  const deadline = Date.now() + maxWaitMs;
  while (Date.now() < deadline) {
    await wait(2000);
    if (isOnline()) return true;
  }
  return false;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      ...initialState(),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setMobileSidebarOpen: (open) => set({ mobileSidebarOpen: open }),
      setRouteLoading: (loading) => set({ routeLoading: loading }),
      fetchProjects: async () => {
        set({ routeLoading: true, apiError: null });
        trackAction(set, 'fetchProjects', []);
        try {
          const projects = await api.listProjects();
          set({ projects });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u9879\u76ee\u52a0\u8f7d\u5931\u8d25', description: message });
        } finally {
          set({ routeLoading: false });
          clearTracking(set);
        }
      },
      addProject: async (name, description, brief) => {
        set({ routeLoading: true, apiError: null });
        try {
          const project = await api.createProject({ name, description, ...(brief ? { brief } : {}) });
          set((state) => ({ projects: [project, ...state.projects], activeProjectId: project.id }));
          get().addToast({ tone: 'success', title: '项目已创建' });
          return project.id;
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u9879\u76ee\u521b\u5efa\u5931\u8d25', description: message });
          return '';
        } finally {
          set({ routeLoading: false });
        }
      },
      updateProjectBrief: async (id, brief) => {
        set({ routeLoading: true, apiError: null });
        try {
          const project = await api.updateProject(id, { brief });
          set((state) => ({
            projects: state.projects.map((item) => (item.id === id ? project : item)),
          }));
          get().addToast({ tone: 'success', title: '\u521b\u4f5c\u7b80\u62a5\u5df2\u4fdd\u5b58' });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u521b\u4f5c\u7b80\u62a5\u4fdd\u5b58\u5931\u8d25', description: message });
        } finally {
          set({ routeLoading: false });
        }
      },
      removeProject: async (id) => {
        set({ routeLoading: true, apiError: null });
        try {
          await api.deleteProject(id);
          set((state) => ({
            projects: state.projects.filter((project) => project.id !== id),
            activeProjectId: state.activeProjectId === id ? null : state.activeProjectId,
          }));
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u9879\u76ee\u5220\u9664\u5931\u8d25', description: message });
        } finally {
          set({ routeLoading: false });
        }
      },
      findProject: (id) => get().projects.find((project) => project.id === id),
      setVideoFile: (file) => set({ videoFile: file }),
      startAnalysis: async (projectId) => {
        const file = get().videoFile;
        if (!file) {
          get().addToast({ tone: 'error', title: '\u8bf7\u5148\u9009\u62e9\u89c6\u9891' });
          return undefined;
        }

        set({ isAnalyzing: true, progress: 0, stage: analysisStages[0], analysisResult: null, apiError: null });
        let targetProjectId = projectId || get().activeProjectId || '';

        try {
          if (!targetProjectId) {
            targetProjectId = await get().addProject(projectNameFromFile(file), '');
          }
          if (!targetProjectId) throw new Error('\u9879\u76ee\u521b\u5efa\u5931\u8d25');

          set({ activeProjectId: targetProjectId });
          set({ stage: '正在上传视频...', uploadProgress: 50 });
          const job = await api.startAnalysis(file, targetProjectId);
          set({ uploadProgress: 100, stage: analysisStages[0] });

          for (;;) {
            const status = await api.getAnalysis(job.job_id);
            set({ progress: status.progress, stage: status.stage });
            if (status.status === 'completed') {
              if (!status.result) throw new Error('\u5206\u6790\u7ed3\u679c\u4e3a\u7a7a');
              set({
                isAnalyzing: false,
                progress: 100,
                analysisResult: status.result,
                currentStructure: status.result,
                activeProjectId: targetProjectId,
                gaps: [],
              });
              await get().fetchAnalysisSamples(targetProjectId);
              await get().fetchProjects();
              return targetProjectId;
            }
            if (status.status === 'failed') throw new Error(status.error || '\u5206\u6790\u5931\u8d25');
            await wait(1000);
          }
        } catch (error) {
          const message = getErrorMessage(error);
          // Auto-recovery: if offline, wait for network and retry.
          if (!isOnline()) {
            get().addToast({ tone: 'info', title: '\u7f51\u7edc\u5df2\u65ad\u5f00', description: '\u68c0\u6d4b\u5230\u7f51\u7edc\u6062\u590d\u540e\u5c06\u81ea\u52a8\u91cd\u8bd5' });
            const recovered = await waitForNetwork();
            if (recovered) {
              get().addToast({ tone: 'success', title: '\u7f51\u7edc\u5df2\u6062\u590d', description: '\u6b63\u5728\u81ea\u52a8\u91cd\u8bd5...' });
              set({ isAnalyzing: true, progress: 0 });
              // Retry by recursing
              void get().startAnalysis(projectId);
              return undefined;
            }
          }
          set({ isAnalyzing: false, apiError: message });
          get().addToast({ tone: 'error', title: '\u5206\u6790\u5931\u8d25', description: message });
          return undefined;
        }
      },
      fetchAnalysisSamples: async (projectId) => {
        set({ sampleLoading: true, apiError: null });
        try {
          const analysisSamples = await api.listAnalysisSamples(projectId);
          set({ analysisSamples, activeProjectId: projectId });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '样例加载失败', description: message });
        } finally {
          set({ sampleLoading: false });
        }
      },
      selectReferenceSample: async (projectId, jobId) => {
        set({ sampleLoading: true, apiError: null });
        try {
          const sample = await api.selectAnalysisReference(projectId, jobId);
          if (!sample.result) throw new Error('样例结果不可用');
          set({ analysisResult: sample.result, currentStructure: sample.result, activeProjectId: projectId });
          await get().fetchAnalysisSamples(projectId);
          get().addToast({ tone: 'success', title: '已更新结构模板' });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '模板选择失败', description: message });
        } finally {
          set({ sampleLoading: false });
        }
      },
      resetAnalysis: () => set({ videoFile: null, isAnalyzing: false, progress: 0, stage: analysisStages[0], analysisResult: null }),
      completeAnalysisNow: () =>
        set({
          isAnalyzing: false,
          progress: 100,
          stage: analysisStages[analysisStages.length - 1],
          analysisResult: cloneStructure(mockAnalysisResult),
          currentStructure: cloneStructure(mockAnalysisResult),
        }),
      loadProjectStructure: async (projectId) => {
        set({ routeLoading: true, apiError: null, activeProjectId: projectId });
        try {
          const structure = await api.getStructure(projectId);
          const assets = await api.listAssets(projectId);
          const gapResponse = await api.listGaps(projectId);
          set({
            currentStructure: structure,
            gaps: gapResponse.gaps,
            assets,
          });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message, currentStructure: null });
          get().addToast({ tone: 'error', title: '\u7ed3\u6784\u52a0\u8f7d\u5931\u8d25', description: message });
          throw error;
        } finally {
          set({ routeLoading: false });
        }
      },
      fetchAssets: async (projectId) => {
        set({ assetLoading: true, apiError: null, activeProjectId: projectId });
        try {
          const assets = await api.listAssets(projectId);
          set({ assets });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u7d20\u6750\u52a0\u8f7d\u5931\u8d25', description: message });
        } finally {
          set({ assetLoading: false });
        }
      },
      uploadAsset: async (file) => {
        const projectId = get().activeProjectId;
        if (!projectId) {
          get().addToast({ tone: 'error', title: '\u8bf7\u5148\u9009\u62e9\u9879\u76ee' });
          return;
        }
        set({ assetLoading: true, apiError: null });
        try {
          await api.analyzeAsset(projectId, file);
          await api.matchAssets(projectId);
          const assets = await api.listAssets(projectId);
          const gapResponse = await api.listGaps(projectId);
          set({ assets, gaps: gapResponse.gaps });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u7d20\u6750\u4e0a\u4f20\u5931\u8d25', description: message });
        } finally {
          set({ assetLoading: false });
        }
      },
      fetchGaps: async (projectId) => {
        set({ gapLoading: true, apiError: null, activeProjectId: projectId });
        try {
          const response = await api.listGaps(projectId);
          set({ gaps: response.gaps });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u7f3a\u53e3\u52a0\u8f7d\u5931\u8d25', description: message });
        } finally {
          set({ gapLoading: false });
        }
      },
      fixGap: async (gapId, strategy) => {
        const projectId = get().activeProjectId;
        if (!projectId) return;
        set({ isFixing: true, gapLoading: true, apiError: null });
        try {
          const response = await api.fixGap(projectId, gapId, strategy);
          set({
            currentStructure: response.updated_structure ?? get().currentStructure,
            assets: response.assets ?? get().assets,
            gaps: response.gaps ?? get().gaps,
          });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u7f3a\u53e3\u4fee\u590d\u5931\u8d25', description: message });
        } finally {
          set({ isFixing: false, gapLoading: false });
        }
      },
      fixAllGaps: async () => {
        const projectId = get().activeProjectId;
        if (!projectId) return;
        set({ isFixing: true, gapLoading: true, apiError: null });
        try {
          const response = await api.fixAllGaps(projectId);
          set({
            currentStructure: response.updated_structure ?? get().currentStructure,
            assets: response.assets ?? get().assets,
            gaps: response.gaps,
          });
          const openCount = (response.gaps ?? []).filter((g) => g.status === 'open').length;
          if (openCount === 0) {
            get().addToast({ tone: 'success', title: '\u7d20\u6750\u7f3a\u53e3\u5df2\u5168\u90e8\u8865\u5168', description: '\u7ed3\u6784\u5df2\u5c31\u7eea\uff0c\u70b9\u51fb\u5e95\u90e8\u6309\u94ae\u751f\u6210\u811a\u672c' });
          } else {
            get().addToast({ tone: 'info', title: `\u5df2\u4fee\u590d\uff0c\u5269\u4f59 ${openCount} \u4e2a\u7f3a\u53e3`, description: '\u53ef\u7ee7\u7eed\u8865\u5168\u6216\u76f4\u63a5\u751f\u6210\u811a\u672c' });
          }
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u4e00\u952e\u4fee\u590d\u5931\u8d25', description: message });
        } finally {
          set({ isFixing: false, gapLoading: false });
        }
      },
      updateSegment: async (id, changes) => {
        const projectId = get().activeProjectId;
        if (!projectId) return;
        try {
          const currentStructure = await api.updateSegment(projectId, id, changes);
          set({ currentStructure });
          await get().fetchGaps(projectId);
        } catch (error) {
          get().addToast({ tone: 'error', title: '\u5206\u955c\u66f4\u65b0\u5931\u8d25', description: getErrorMessage(error) });
        }
      },
      reorderSegments: async (activeId, overId) => {
        const { activeProjectId, currentStructure } = get();
        if (!activeProjectId || !currentStructure || activeId === overId) return;
        const oldIndex = currentStructure.script.findIndex((segment) => segment.id === activeId);
        const newIndex = currentStructure.script.findIndex((segment) => segment.id === overId);
        if (oldIndex < 0 || newIndex < 0) return;
        const next = [...currentStructure.script];
        const [moved] = next.splice(oldIndex, 1);
        next.splice(newIndex, 0, moved);
        try {
          const structure = await api.reorderSegments(activeProjectId, next.map((segment) => segment.id));
          set({ currentStructure: structure });
          await get().fetchGaps(activeProjectId);
        } catch (error) {
          get().addToast({ tone: 'error', title: '\u5206\u955c\u91cd\u6392\u5931\u8d25', description: getErrorMessage(error) });
        }
      },
      removeSelectedSegment: async () => {
        const { activeProjectId, currentStructure, selectedSegmentId } = get();
        if (!activeProjectId || !currentStructure || !selectedSegmentId) return;
        const selected = currentStructure.script.find((segment) => segment.id === selectedSegmentId);
        if (!selected || selected.locked) return;
        try {
          const structure = await api.deleteSegment(activeProjectId, selectedSegmentId);
          set({ currentStructure: structure, selectedSegmentId: null, drawerOpen: false });
          await get().fetchGaps(activeProjectId);
        } catch (error) {
          get().addToast({ tone: 'error', title: '\u5206\u955c\u5220\u9664\u5931\u8d25', description: getErrorMessage(error) });
        }
      },
      selectSegment: (id) => set({ selectedSegmentId: id, drawerOpen: Boolean(id) }),
      setDrawerOpen: (open) => set({ drawerOpen: open }),
      undo: async () => {
        const projectId = get().activeProjectId;
        if (!projectId) return;
        try {
          const response = await api.undo(projectId);
          set({ currentStructure: response.structure });
          if (!response.available) get().addToast({ tone: 'info', title: '\u6ca1\u6709\u53ef\u64a4\u9500\u7684\u64cd\u4f5c' });
        } catch (error) {
          get().addToast({ tone: 'error', title: '\u64a4\u9500\u5931\u8d25', description: getErrorMessage(error) });
        }
      },
      redo: async () => {
        const projectId = get().activeProjectId;
        if (!projectId) return;
        try {
          const response = await api.redo(projectId);
          set({ currentStructure: response.structure });
          if (!response.available) get().addToast({ tone: 'info', title: '\u6ca1\u6709\u53ef\u91cd\u505a\u7684\u64cd\u4f5c' });
        } catch (error) {
          get().addToast({ tone: 'error', title: '\u91cd\u505a\u5931\u8d25', description: getErrorMessage(error) });
        }
      },
      resetStructure: async () => {
        const projectId = get().activeProjectId;
        if (!projectId) return;
        try {
          const currentStructure = await api.resetStructure(projectId);
          const gapResponse = await api.listGaps(projectId);
          set({ currentStructure, gaps: gapResponse.gaps });
        } catch (error) {
          get().addToast({ tone: 'error', title: '\u91cd\u7f6e\u5931\u8d25', description: getErrorMessage(error) });
        }
      },
      nlEdit: async (command) => {
        const projectId = get().activeProjectId;
        if (!projectId || !command.trim()) return;
        set({ routeLoading: true, apiError: null });
        try {
          const response = await api.nlEditStructure(projectId, command.trim());
          set({ currentStructure: response.structure });
          await get().fetchGaps(projectId);
          get().addToast({ tone: 'success', title: '\u5df2\u5e94\u7528\u7f16\u8f91', description: response.changes_summary });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u81ea\u7136\u8bed\u8a00\u7f16\u8f91\u5931\u8d25', description: message });
          throw error;
        } finally {
          set({ routeLoading: false });
        }
      },
      fixGaps: () => get().fixAllGaps(),
      migrateScript: async (projectId, style = 'default') => {
        set({ scriptLoading: true, apiError: null, activeProjectId: projectId });
        try {
          const script = await api.migrateScript(projectId, style);
          set({ currentScript: script });
          get().addToast({ tone: 'success', title: '\u811a\u672c\u751f\u6210\u5b8c\u6210' });
          return script;
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u811a\u672c\u751f\u6210\u5931\u8d25', description: message });
          return undefined;
        } finally {
          set({ scriptLoading: false });
        }
      },
      loadFinalScript: async (projectId) => {
        set({ scriptLoading: true, apiError: null, activeProjectId: projectId });
        try {
          const script = await api.getFinalScript(projectId);
          set((state) => ({
            currentScript: script,
            currentVersionId: state.versions.some((version) => version.id === script.version) ? script.version : state.currentVersionId,
          }));
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) {
            set({ currentScript: null });
            return;
          }
          const message = getErrorMessage(error);
          set({ apiError: message, currentScript: null });
          get().addToast({ tone: 'error', title: '\u811a\u672c\u52a0\u8f7d\u5931\u8d25', description: message });
        } finally {
          set({ scriptLoading: false });
        }
      },
      fetchResultVersions: async (projectId) => {
        try {
          const response = await api.getResultVersions(projectId);
          const versions = [response.baseline, ...response.versions];
          const desiredId = get().currentScript?.version ?? get().currentVersionId;
          const currentVersionId = versions.some((version) => version.id === desiredId) ? desiredId : response.baseline.id;
          set({
            versions,
            evaluationLabel: response.evaluationLabel,
            currentVersionId,
            ...(response.versions.length ? {} : { currentScript: null }),
          });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message, versions: [], evaluationLabel: '' });
          get().addToast({ tone: 'error', title: '\u8bc4\u4f30\u6570\u636e\u52a0\u8f7d\u5931\u8d25', description: message });
        }
      },
      startRender: async (projectId, version, resolution = '1080p', scriptVersion) => {
        set({
          isExporting: true,
          renderStatus: 'pending',
          renderProgress: 0,
          renderError: null,
          outputUrl: null,
          apiError: null,
          activeProjectId: projectId,
        });
        try {
          const response = await api.startRender(projectId, version, resolution, scriptVersion);
          set({ renderJobId: response.job_id });
          await get().pollRenderJob(response.job_id);
        } catch (error) {
          const message = getErrorMessage(error);
          set({ isExporting: false, renderStatus: 'failed', renderError: message, apiError: message });
          get().addToast({ tone: 'error', title: '\u6e32\u67d3\u5931\u8d25', description: message });
        }
      },
      pollRenderJob: async (jobId) => {
        try {
          for (;;) {
            const status = await api.getRenderJob(jobId);
            set({
              renderStatus: status.status,
              renderProgress: status.progress,
              outputUrl: status.output_url ?? null,
              renderError: status.error ?? null,
            });
            if (status.status === 'completed') {
              set({ isExporting: false });
              get().addToast({ tone: 'success', title: '\u89c6\u9891\u751f\u6210\u5b8c\u6210' });
              return;
            }
            if (status.status === 'failed') {
              const message = status.error || '\u89c6\u9891\u6e32\u67d3\u5931\u8d25';
              console.error('[StructForge] Render failed:', message, 'warnings:', status.warnings);
              try { sessionStorage.setItem('lastRenderError', JSON.stringify({ error: message, warnings: status.warnings })); } catch {}
              set({ isExporting: false, renderError: message, renderStatus: 'failed' });
              get().addToast({ tone: 'error', title: '\u6e32\u67d3\u5931\u8d25', description: message });
              return;
            }
            await wait(1000);
          }
        } catch (error) {
          const message = getErrorMessage(error);
          set({ isExporting: false, renderStatus: 'failed', renderError: message, apiError: message });
          get().addToast({ tone: 'error', title: '\u6e32\u67d3\u8f6e\u8be2\u5931\u8d25', description: message });
        }
      },
      setVersion: (id) => set({ currentVersionId: id }),
      exportResult: () =>
        new Promise((resolve) => {
          set({ isExporting: true });
          window.setTimeout(() => {
            set({ isExporting: false });
            get().addToast({ tone: 'success', title: '\u5bfc\u51fa\u5b8c\u6210', description: '\u6a21\u62df\u6587\u4ef6\u5df2\u751f\u6210' });
            resolve();
          }, 2000);
        }),
      addToast: (toast) => {
        const id = uid('toast');
        set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
        window.setTimeout(() => get().removeToast(id), 3500);
      },
      removeToast: (id) => set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
      retryLastAction: async () => {
        const { lastFailedAction, lastFailedActionArgs } = get();
        if (!lastFailedAction) return;
        const action = (get() as unknown as Record<string, unknown>)[lastFailedAction];
        if (typeof action === 'function') {
          set({ apiError: null, routeLoading: true });
          try {
            await (action as (...args: unknown[]) => Promise<void>)(...(lastFailedActionArgs ?? []));
          } finally {
            set({ routeLoading: false });
          }
        }
      },
      resetForTest: () => set(initialState()),
    }),
    {
      name: 'structforge-app-store',
      version: 2,
      migrate: (persisted) => {
        const state = persisted as Partial<AppState>;
        return {
          sidebarCollapsed: Boolean(state.sidebarCollapsed),
          currentVersionId: state.currentVersionId ?? 'original',
        };
      },
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        currentVersionId: state.currentVersionId,
      }),
    },
  ),
);
