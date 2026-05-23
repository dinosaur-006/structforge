import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../services/api';
import { mockAnalysisResult } from '../mocks/analysisResult';
import { mockGaps } from '../mocks/gaps';
import { mockVersions } from '../mocks/versions';
import { uid } from '../shared/format';
import type { Asset, MaterialGap, Project, ResultVersion, ScriptSegment, ToastMessage, VideoStructure } from '../shared/types';

const analysisStages = [
  '\u6b63\u5728\u62bd\u5e27...',
  '\u6b63\u5728\u8bc6\u522b\u5173\u952e\u5e27...',
  '\u6b63\u5728\u5206\u6790\u811a\u672c\u7ed3\u6784...',
  '\u6b63\u5728\u8bc4\u4f30\u5065\u5eb7\u5ea6...',
];

function cloneStructure(structure: VideoStructure): VideoStructure {
  return JSON.parse(JSON.stringify(structure)) as VideoStructure;
}

function cloneGaps(gaps: MaterialGap[]): MaterialGap[] {
  return JSON.parse(JSON.stringify(gaps)) as MaterialGap[];
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
    progress: 0,
    stage: analysisStages[0],
    analysisResult: null,
    currentStructure: null,
    assets: [] as Asset[],
    assetLoading: false,
    gaps: cloneGaps(mockGaps),
    isFixing: false,
    selectedSegmentId: null,
    drawerOpen: false,
    history: [] as VideoStructure[],
    future: [] as VideoStructure[],
    versions: [...mockVersions],
    currentVersionId: 'original',
    isExporting: false,
    toasts: [] as ToastMessage[],
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
  progress: number;
  stage: string;
  analysisResult: VideoStructure | null;
  currentStructure: VideoStructure | null;
  assets: Asset[];
  assetLoading: boolean;
  gaps: MaterialGap[];
  isFixing: boolean;
  selectedSegmentId: string | null;
  drawerOpen: boolean;
  history: VideoStructure[];
  future: VideoStructure[];
  versions: ResultVersion[];
  currentVersionId: string;
  isExporting: boolean;
  toasts: ToastMessage[];
  toggleSidebar: () => void;
  setMobileSidebarOpen: (open: boolean) => void;
  setRouteLoading: (loading: boolean) => void;
  fetchProjects: () => Promise<void>;
  addProject: (name: string, description: string) => Promise<string>;
  removeProject: (id: string) => Promise<void>;
  findProject: (id: string) => Project | undefined;
  setVideoFile: (file: File | null) => void;
  startAnalysis: (projectId?: string) => Promise<string | undefined>;
  resetAnalysis: () => void;
  completeAnalysisNow: () => void;
  loadProjectStructure: (projectId: string) => Promise<void>;
  fetchAssets: (projectId: string) => Promise<void>;
  uploadAsset: (file: File) => Promise<void>;
  updateSegment: (id: string, changes: Partial<ScriptSegment>) => Promise<void>;
  reorderSegments: (activeId: string, overId: string) => Promise<void>;
  removeSelectedSegment: () => Promise<void>;
  selectSegment: (id: string | null) => void;
  setDrawerOpen: (open: boolean) => void;
  undo: () => Promise<void>;
  redo: () => Promise<void>;
  resetStructure: () => Promise<void>;
  fixGaps: () => Promise<void>;
  setVersion: (id: string) => void;
  exportResult: () => Promise<void>;
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;
  resetForTest: () => void;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '\u672a\u77e5\u9519\u8bef';
}

function projectNameFromFile(file: File): string {
  return file.name.replace(/\.[^.]+$/, '') || '\u672a\u547d\u540d\u9879\u76ee';
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
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
        try {
          const projects = await api.listProjects();
          set({ projects });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u9879\u76ee\u52a0\u8f7d\u5931\u8d25', description: message });
        } finally {
          set({ routeLoading: false });
        }
      },
      addProject: async (name, description) => {
        set({ routeLoading: true, apiError: null });
        try {
          const project = await api.createProject({ name, description });
          set((state) => ({ projects: [project, ...state.projects], activeProjectId: project.id }));
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
          const job = await api.startAnalysis(file, targetProjectId);

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
                gaps: cloneGaps(mockGaps),
              });
              await get().fetchProjects();
              return targetProjectId;
            }
            if (status.status === 'failed') throw new Error(status.error || '\u5206\u6790\u5931\u8d25');
            await wait(1000);
          }
        } catch (error) {
          const message = getErrorMessage(error);
          set({ isAnalyzing: false, apiError: message });
          get().addToast({ tone: 'error', title: '\u5206\u6790\u5931\u8d25', description: message });
          return undefined;
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
          set({
            currentStructure: structure,
            gaps: get().gaps.length ? get().gaps : cloneGaps(mockGaps),
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
          set({ assets });
        } catch (error) {
          const message = getErrorMessage(error);
          set({ apiError: message });
          get().addToast({ tone: 'error', title: '\u7d20\u6750\u4e0a\u4f20\u5931\u8d25', description: message });
        } finally {
          set({ assetLoading: false });
        }
      },
      updateSegment: async (id, changes) => {
        const projectId = get().activeProjectId;
        if (!projectId) return;
        try {
          const currentStructure = await api.updateSegment(projectId, id, changes);
          set({ currentStructure });
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
          set({ currentStructure, gaps: cloneGaps(mockGaps) });
        } catch (error) {
          get().addToast({ tone: 'error', title: '\u91cd\u7f6e\u5931\u8d25', description: getErrorMessage(error) });
        }
      },
      fixGaps: () =>
        new Promise((resolve) => {
          set({ isFixing: true });
          window.setTimeout(() => {
            set((state) => ({
              isFixing: false,
              gaps: state.gaps.map((gap) => ({ ...gap, status: 'fixed' })),
              currentStructure: state.currentStructure
                ? {
                    ...state.currentStructure,
                    script: state.currentStructure.script.map((segment) =>
                      ['seg-hook', 'seg-cta'].includes(segment.id)
                        ? { ...segment, healthScore: Math.max(segment.healthScore, segment.id === 'seg-hook' ? 86 : 78) }
                        : segment,
                    ),
                  }
                : state.currentStructure,
            }));
            get().addToast({ tone: 'success', title: '\u4fee\u590d\u5b8c\u6210', description: '\u7d20\u6750\u7f3a\u53e3\u5df2\u8865\u5168' });
            resolve();
          }, 2000);
        }),
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
