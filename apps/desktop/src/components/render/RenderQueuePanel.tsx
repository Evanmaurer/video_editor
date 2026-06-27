import { useEffect } from "react";
import { useProjectStore, useUIStore } from "@/stores/project-store";
import {
  formatRenderEta,
  formatRenderProgress,
  useRenderStore,
} from "@/stores/render-store";

function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function RenderQueuePanel() {
  const project = useProjectStore((s) => s.project);
  const showRenderQueue = useUIStore((s) => s.showRenderQueue);
  const setShowRenderQueue = useUIStore((s) => s.setShowRenderQueue);
  const jobs = useRenderStore((s) => s.jobs);
  const selectedJobId = useRenderStore((s) => s.selectedJobId);
  const selectedJobDetail = useRenderStore((s) => s.selectedJobDetail);
  const loadJobs = useRenderStore((s) => s.loadJobs);
  const selectJob = useRenderStore((s) => s.selectJob);
  const pauseJob = useRenderStore((s) => s.pauseJob);
  const resumeJob = useRenderStore((s) => s.resumeJob);
  const cancelJob = useRenderStore((s) => s.cancelJob);
  const refreshLogs = useRenderStore((s) => s.refreshLogs);
  const subscribe = useRenderStore((s) => s.subscribe);
  const unsubscribe = useRenderStore((s) => s.unsubscribe);

  useEffect(() => {
    if (!project?.id || !showRenderQueue) {
      return;
    }
    subscribe(project.id);
    void loadJobs(project.id);
    return () => {
      unsubscribe();
    };
  }, [project?.id, showRenderQueue, loadJobs, subscribe, unsubscribe]);

  useEffect(() => {
    if (!project?.id || !selectedJobId || !showRenderQueue) {
      return;
    }
    void refreshLogs(project.id, selectedJobId);
  }, [project?.id, selectedJobId, showRenderQueue, refreshLogs]);

  if (!showRenderQueue || !project?.id) {
    return null;
  }

  const activeJob = selectedJobDetail ?? jobs.find((job) => job.id === selectedJobId) ?? null;

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-[420px] bg-panel border-l border-border shadow-2xl flex flex-col">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div>
          <h2 className="text-sm font-medium">Render Queue</h2>
          <p className="text-xs text-muted">Background exports with FFmpeg logs</p>
        </div>
        <button
          type="button"
          className="text-muted hover:text-foreground"
          onClick={() => setShowRenderQueue(false)}
        >
          ✕
        </button>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        <div className="max-h-48 overflow-auto border-b border-border">
          {jobs.length === 0 ? (
            <p className="p-4 text-xs text-muted">No export jobs yet.</p>
          ) : (
            jobs.map((job) => (
              <button
                key={job.id}
                type="button"
                className={`w-full text-left px-4 py-2 border-b border-border/50 hover:bg-secondary ${
                  selectedJobId === job.id ? "bg-secondary" : ""
                }`}
                onClick={() => void selectJob(project.id, job.id)}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium truncate">{job.preset_id}</span>
                  <span className="text-[10px] uppercase tracking-wide text-muted">{job.status}</span>
                </div>
                <div className="mt-1 h-1.5 bg-border rounded overflow-hidden">
                  <div
                    className="h-full bg-accent"
                    style={{ width: `${Math.round(job.progress * 100)}%` }}
                  />
                </div>
                <div className="mt-1 flex justify-between text-[10px] text-muted font-mono">
                  <span>{formatRenderProgress(job.progress)}</span>
                  <span>ETA {formatRenderEta(job.eta_seconds)}</span>
                </div>
              </button>
            ))
          )}
        </div>

        {activeJob && (
          <div className="flex-1 min-h-0 flex flex-col">
            <div className="px-4 py-3 space-y-2 border-b border-border text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted">Status</span>
                <span>{statusLabel(activeJob.status)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Progress</span>
                <span className="font-mono">{formatRenderProgress(activeJob.progress)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">ETA</span>
                <span className="font-mono">{formatRenderEta(activeJob.eta_seconds)}</span>
              </div>
              {activeJob.output_path && (
                <div className="space-y-1">
                  <span className="text-muted">Output</span>
                  <p className="font-mono text-[10px] break-all">{activeJob.output_path}</p>
                </div>
              )}
              {activeJob.error_message && (
                <p className="text-[#e74c3c]">{activeJob.error_message}</p>
              )}
              <div className="flex gap-2 pt-1">
                {activeJob.status === "running" && (
                  <button
                    type="button"
                    className="btn-secondary text-xs py-1 px-2"
                    onClick={() => void pauseJob(project.id, activeJob.id)}
                  >
                    Pause
                  </button>
                )}
                {activeJob.status === "paused" && (
                  <button
                    type="button"
                    className="btn-secondary text-xs py-1 px-2"
                    onClick={() => void resumeJob(project.id, activeJob.id)}
                  >
                    Resume
                  </button>
                )}
                {["queued", "running", "paused"].includes(activeJob.status) && (
                  <button
                    type="button"
                    className="btn-secondary text-xs py-1 px-2"
                    onClick={() => void cancelJob(project.id, activeJob.id)}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>

            <div className="flex-1 min-h-0 flex flex-col">
              <div className="px-4 py-2 border-b border-border text-xs font-medium">FFmpeg Log</div>
              <pre className="flex-1 min-h-0 overflow-auto p-3 text-[10px] font-mono whitespace-pre-wrap bg-[#111] text-[#bbb]">
                {(selectedJobDetail?.log_tail ?? []).join("\n") || "Waiting for FFmpeg output…"}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
