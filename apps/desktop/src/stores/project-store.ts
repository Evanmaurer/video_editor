import { create } from "zustand";
import type { AppSettings, HealthResponse, Project, ProjectSummary } from "@montage/shared-types";
import type { ViewState } from "@montage/shared-types";

interface ProjectState {
  project: Project | null;
  recentProjects: ProjectSummary[];
  health: HealthResponse | null;
  view: ViewState;
  isLoading: boolean;
  error: string | null;
  setProject: (project: Project | null) => void;
  setRecentProjects: (projects: ProjectSummary[]) => void;
  setHealth: (health: HealthResponse | null) => void;
  setView: (view: ViewState) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  project: null,
  recentProjects: [],
  health: null,
  view: "welcome",
  isLoading: false,
  error: null,
  setProject: (project) => set({ project, view: project ? "editor" : "welcome" }),
  setRecentProjects: (recentProjects) => set({ recentProjects }),
  setHealth: (health) => set({ health }),
  setView: (view) => set({ view }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}));

interface SettingsState {
  settings: AppSettings | null;
  setSettings: (settings: AppSettings | null) => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: null,
  setSettings: (settings) => set({ settings }),
}));

interface UIState {
  showNewProjectWizard: boolean;
  showExportDialog: boolean;
  showRenderQueue: boolean;
  setShowNewProjectWizard: (show: boolean) => void;
  setShowExportDialog: (show: boolean) => void;
  setShowRenderQueue: (show: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  showNewProjectWizard: false,
  showExportDialog: false,
  showRenderQueue: false,
  setShowNewProjectWizard: (showNewProjectWizard) => set({ showNewProjectWizard }),
  setShowExportDialog: (showExportDialog) => set({ showExportDialog }),
  setShowRenderQueue: (showRenderQueue) => set({ showRenderQueue }),
}));
