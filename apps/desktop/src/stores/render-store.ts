import { create } from "zustand";
import type {
  RenderJobDetail,
  RenderJobSummary,
  RenderPresetInfo,
  StartRenderRequest,
} from "@montage/shared-types";
import { getApiClient } from "@/services/api-client";
import { wsClient } from "@/services/websocket-client";

interface RenderState {
  presets: RenderPresetInfo[];
  jobs: RenderJobSummary[];
  selectedJobId: string | null;
  selectedJobDetail: RenderJobDetail | null;
  isLoadingPresets: boolean;
  isStarting: boolean;
  error: string | null;
  pollTimer: ReturnType<typeof setInterval> | null;
  wsUnsubscribe: (() => void) | null;
  loadPresets: () => Promise<void>;
  loadJobs: (projectId: string) => Promise<void>;
  selectJob: (projectId: string, jobId: string | null) => Promise<void>;
  startExport: (projectId: string, request: StartRenderRequest) => Promise<RenderJobSummary>;
  pauseJob: (projectId: string, jobId: string) => Promise<void>;
  resumeJob: (projectId: string, jobId: string) => Promise<void>;
  cancelJob: (projectId: string, jobId: string) => Promise<void>;
  refreshLogs: (projectId: string, jobId: string) => Promise<void>;
  subscribe: (projectId: string) => void;
  unsubscribe: () => void;
  startPolling: (projectId: string) => void;
  stopPolling: () => void;
}

function upsertJob(jobs: RenderJobSummary[], next: RenderJobSummary): RenderJobSummary[] {
  const index = jobs.findIndex((job) => job.id === next.id);
  if (index === -1) {
    return [next, ...jobs];
  }
  const copy = [...jobs];
  copy[index] = { ...copy[index], ...next };
  return copy;
}

function hasActiveJobs(jobs: RenderJobSummary[]): boolean {
  return jobs.some((job) =>
    ["queued", "running", "paused"].includes(job.status),
  );
}

export const useRenderStore = create<RenderState>((set, get) => ({
  presets: [],
  jobs: [],
  selectedJobId: null,
  selectedJobDetail: null,
  isLoadingPresets: false,
  isStarting: false,
  error: null,
  pollTimer: null,
  wsUnsubscribe: null,

  loadPresets: async () => {
    set({ isLoadingPresets: true, error: null });
    try {
      const presets = await getApiClient().listRenderPresets("current");
      set({ presets, isLoadingPresets: false });
    } catch (err) {
      set({
        isLoadingPresets: false,
        error: err instanceof Error ? err.message : "Failed to load export presets",
      });
    }
  },

  loadJobs: async (projectId: string) => {
    const jobs = await getApiClient().listRenderJobs(projectId);
    set({ jobs });
    if (hasActiveJobs(jobs)) {
      get().startPolling(projectId);
    } else {
      get().stopPolling();
    }
  },

  selectJob: async (projectId: string, jobId: string | null) => {
    if (!jobId) {
      set({ selectedJobId: null, selectedJobDetail: null });
      return;
    }
    set({ selectedJobId: jobId });
    const detail = await getApiClient().getRenderJob(projectId, jobId);
    set({ selectedJobDetail: detail });
  },

  startExport: async (projectId: string, request: StartRenderRequest) => {
    set({ isStarting: true, error: null });
    try {
      const job = await getApiClient().startRender(projectId, request);
      set((state) => ({
        jobs: upsertJob(state.jobs, job),
        isStarting: false,
        selectedJobId: job.id,
      }));
      await get().selectJob(projectId, job.id);
      get().startPolling(projectId);
      return job;
    } catch (err) {
      set({
        isStarting: false,
        error: err instanceof Error ? err.message : "Failed to start export",
      });
      throw err;
    }
  },

  pauseJob: async (projectId: string, jobId: string) => {
    const job = await getApiClient().pauseRenderJob(projectId, jobId);
    set((state) => ({ jobs: upsertJob(state.jobs, job) }));
    await get().selectJob(projectId, jobId);
  },

  resumeJob: async (projectId: string, jobId: string) => {
    const job = await getApiClient().resumeRenderJob(projectId, jobId);
    set((state) => ({ jobs: upsertJob(state.jobs, job) }));
    get().startPolling(projectId);
    await get().selectJob(projectId, jobId);
  },

  cancelJob: async (projectId: string, jobId: string) => {
    const job = await getApiClient().cancelRenderJob(projectId, jobId);
    set((state) => ({ jobs: upsertJob(state.jobs, job) }));
    await get().selectJob(projectId, jobId);
  },

  refreshLogs: async (projectId: string, jobId: string) => {
    const logs = await getApiClient().getRenderLogs(projectId, jobId);
    set((state) => {
      if (!state.selectedJobDetail || state.selectedJobDetail.id !== jobId) {
        return state;
      }
      return {
        selectedJobDetail: {
          ...state.selectedJobDetail,
          log_tail: logs.lines.slice(-200),
        },
      };
    });
  },

  subscribe: (projectId: string) => {
    get().unsubscribe();
    const unsubscribe = wsClient.onEvent((event) => {
      if (event.type !== "render.progress" || event.project_id !== projectId) {
        return;
      }
      const summary: RenderJobSummary = {
        id: event.job_id,
        project_id: event.project_id,
        timeline_id: get().jobs.find((job) => job.id === event.job_id)?.timeline_id ?? "",
        preset_id: get().jobs.find((job) => job.id === event.job_id)?.preset_id ?? "",
        status: event.status,
        progress: event.progress,
        output_path: event.output_path,
        error_message: event.error_message,
        eta_seconds: event.eta_seconds,
        elapsed_seconds: event.elapsed_seconds,
        created_at: get().jobs.find((job) => job.id === event.job_id)?.created_at ?? "",
        updated_at: new Date().toISOString(),
      };
      set((state) => ({ jobs: upsertJob(state.jobs, summary) }));
      if (get().selectedJobId === event.job_id) {
        void get().selectJob(projectId, event.job_id);
      }
      if (hasActiveJobs(get().jobs)) {
        get().startPolling(projectId);
      } else {
        get().stopPolling();
      }
    });
    set({ wsUnsubscribe: unsubscribe });
  },

  unsubscribe: () => {
    const { wsUnsubscribe, pollTimer } = get();
    if (wsUnsubscribe) {
      wsUnsubscribe();
    }
    if (pollTimer) {
      clearInterval(pollTimer);
    }
    set({ wsUnsubscribe: null, pollTimer: null });
  },

  startPolling: (projectId: string) => {
    const { pollTimer } = get();
    if (pollTimer) {
      return;
    }
    const timer = setInterval(() => {
      void get()
        .loadJobs(projectId)
        .then(() => {
          const selected = get().selectedJobId;
          if (selected) {
            void get().refreshLogs(projectId, selected);
          }
        })
        .catch(() => {
          // ignore transient polling errors
        });
    }, 2000);
    set({ pollTimer: timer });
  },

  stopPolling: () => {
    const { pollTimer } = get();
    if (pollTimer) {
      clearInterval(pollTimer);
    }
    set({ pollTimer: null });
  },
}));

export function formatRenderEta(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) {
    return "—";
  }
  if (seconds < 60) {
    return `${Math.max(1, Math.ceil(seconds))}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.ceil(seconds % 60);
  return `${minutes}m ${remainder}s`;
}

export function formatRenderProgress(progress: number): string {
  return `${Math.round(Math.max(0, Math.min(progress, 1)) * 100)}%`;
}
