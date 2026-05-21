import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { mockAnalysisResult } from '../mocks/analysisResult';
import { mockAssets } from '../mocks/assets';
import { mockGaps } from '../mocks/gaps';
import { mockProjects } from '../mocks/projects';
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
    projects: [...mockProjects],
    videoFile: null,
    isAnalyzing: false,
    progress: 0,
    stage: analysisStages[0],
    analysisResult: null,
    currentStructure: cloneStructure(mockAnalysisResult),
    assets: [...mockAssets],
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
  projects: Project[];
  videoFile: File | null;
  isAnalyzing: boolean;
  progress: number;
  stage: string;
  analysisResult: VideoStructure | null;
  currentStructure: VideoStructure | null;
  assets: Asset[];
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
  addProject: (name: string, description: string) => string;
  removeProject: (id: string) => void;
  findProject: (id: string) => Project | undefined;
  setVideoFile: (file: File | null) => void;
  startAnalysis: () => Promise<void>;
  resetAnalysis: () => void;
  completeAnalysisNow: () => void;
  loadProjectStructure: (projectId: string) => void;
  updateSegment: (id: string, changes: Partial<ScriptSegment>) => void;
  reorderSegments: (activeId: string, overId: string) => void;
  removeSelectedSegment: () => void;
  selectSegment: (id: string | null) => void;
  setDrawerOpen: (open: boolean) => void;
  undo: () => void;
  redo: () => void;
  resetStructure: () => void;
  fixGaps: () => Promise<void>;
  setVersion: (id: string) => void;
  exportResult: () => Promise<void>;
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;
  resetForTest: () => void;
}

function pushHistory(state: AppState): Pick<AppState, 'history' | 'future'> {
  if (!state.currentStructure) return { history: state.history, future: [] };
  return {
    history: [...state.history.slice(-19), cloneStructure(state.currentStructure)],
    future: [],
  };
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      ...initialState(),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setMobileSidebarOpen: (open) => set({ mobileSidebarOpen: open }),
      setRouteLoading: (loading) => set({ routeLoading: loading }),
      addProject: (name, description) => {
        const id = uid('proj');
        const project: Project = {
          id,
          name,
          description,
          status: 'draft',
          updatedAt: new Date().toISOString(),
        };
        set((state) => ({ projects: [project, ...state.projects] }));
        return id;
      },
      removeProject: (id) => set((state) => ({ projects: state.projects.filter((project) => project.id !== id) })),
      findProject: (id) => get().projects.find((project) => project.id === id),
      setVideoFile: (file) => set({ videoFile: file }),
      startAnalysis: () =>
        new Promise((resolve) => {
          set({ isAnalyzing: true, progress: 0, stage: analysisStages[0], analysisResult: null });
          let tick = 0;
          const timer = window.setInterval(() => {
            tick += 1;
            const nextProgress = Math.min(100, tick * 20);
            const stage = analysisStages[Math.min(analysisStages.length - 1, Math.floor(nextProgress / 30))];
            set({ progress: nextProgress, stage });
            if (nextProgress >= 100) {
              window.clearInterval(timer);
              set({
                isAnalyzing: false,
                analysisResult: cloneStructure(mockAnalysisResult),
                currentStructure: cloneStructure(mockAnalysisResult),
                gaps: cloneGaps(mockGaps),
              });
              resolve();
            }
          }, 1000);
        }),
      resetAnalysis: () => set({ videoFile: null, isAnalyzing: false, progress: 0, stage: analysisStages[0], analysisResult: null }),
      completeAnalysisNow: () =>
        set({
          isAnalyzing: false,
          progress: 100,
          stage: analysisStages[analysisStages.length - 1],
          analysisResult: cloneStructure(mockAnalysisResult),
          currentStructure: cloneStructure(mockAnalysisResult),
        }),
      loadProjectStructure: () =>
        set((state) => ({
          currentStructure: state.currentStructure ?? cloneStructure(mockAnalysisResult),
          gaps: state.gaps.length ? state.gaps : cloneGaps(mockGaps),
          assets: state.assets.length ? state.assets : [...mockAssets],
        })),
      updateSegment: (id, changes) =>
        set((state) => {
          if (!state.currentStructure) return state;
          const historyPatch = pushHistory(state);
          const script = state.currentStructure.script.map((segment) => (segment.id === id ? { ...segment, ...changes } : segment));
          return {
            ...historyPatch,
            currentStructure: { ...state.currentStructure, script },
          };
        }),
      reorderSegments: (activeId, overId) =>
        set((state) => {
          if (!state.currentStructure || activeId === overId) return state;
          const oldIndex = state.currentStructure.script.findIndex((segment) => segment.id === activeId);
          const newIndex = state.currentStructure.script.findIndex((segment) => segment.id === overId);
          if (oldIndex < 0 || newIndex < 0) return state;
          const next = [...state.currentStructure.script];
          const [moved] = next.splice(oldIndex, 1);
          next.splice(newIndex, 0, moved);
          return {
            ...pushHistory(state),
            currentStructure: { ...state.currentStructure, script: next },
          };
        }),
      removeSelectedSegment: () =>
        set((state) => {
          if (!state.currentStructure || !state.selectedSegmentId) return state;
          const selected = state.currentStructure.script.find((segment) => segment.id === state.selectedSegmentId);
          if (!selected || selected.locked) return state;
          return {
            ...pushHistory(state),
            currentStructure: {
              ...state.currentStructure,
              script: state.currentStructure.script.filter((segment) => segment.id !== state.selectedSegmentId),
            },
            selectedSegmentId: null,
            drawerOpen: false,
          };
        }),
      selectSegment: (id) => set({ selectedSegmentId: id, drawerOpen: Boolean(id) }),
      setDrawerOpen: (open) => set({ drawerOpen: open }),
      undo: () =>
        set((state) => {
          const previous = state.history.at(-1);
          if (!previous || !state.currentStructure) return state;
          return {
            currentStructure: cloneStructure(previous),
            history: state.history.slice(0, -1),
            future: [cloneStructure(state.currentStructure), ...state.future],
          };
        }),
      redo: () =>
        set((state) => {
          const next = state.future[0];
          if (!next || !state.currentStructure) return state;
          return {
            currentStructure: cloneStructure(next),
            history: [...state.history, cloneStructure(state.currentStructure)].slice(-20),
            future: state.future.slice(1),
          };
        }),
      resetStructure: () => set((state) => ({ ...pushHistory(state), currentStructure: cloneStructure(mockAnalysisResult), gaps: cloneGaps(mockGaps) })),
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
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        projects: state.projects,
        currentStructure: state.currentStructure,
        currentVersionId: state.currentVersionId,
      }),
    },
  ),
);
