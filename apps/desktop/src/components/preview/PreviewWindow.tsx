import { useTimelineStore } from "@/stores/timeline-store";
import { formatTimelineTime } from "@/components/timeline/time-format";

export function PreviewWindow() {
  const document = useTimelineStore((s) => s.document);
  const playheadMs = useTimelineStore((s) => s.playheadMs);
  const isLoading = useTimelineStore((s) => s.isLoading);

  const hasClips =
    document?.tracks.some((track) => track.clips.length > 0) ?? false;

  return (
    <div className="h-full flex flex-col bg-primary border-b border-border">
      <div className="px-3 py-2 border-b border-border text-sm font-medium">Preview</div>
      <div className="flex-1 panel-empty">
        <div className="w-full max-w-2xl aspect-video bg-panel border border-border rounded-md flex items-center justify-center">
          {isLoading ? (
            <span className="text-muted text-sm">Loading timeline…</span>
          ) : !document ? (
            <span className="text-muted text-sm">No timeline loaded</span>
          ) : hasClips ? (
            <span className="text-muted text-sm text-center px-4">
              Preview playback — M2-004
              <br />
              <span className="text-xs">Playhead: {formatTimelineTime(playheadMs)}</span>
            </span>
          ) : (
            <span className="text-muted text-sm">Drag clips onto the timeline</span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-4">
          <button type="button" className="btn-secondary opacity-50" disabled title="M2-004">
            ◀◀
          </button>
          <button type="button" className="btn-secondary opacity-50" disabled title="M2-004">
            ▶
          </button>
          <button type="button" className="btn-secondary opacity-50" disabled title="M2-004">
            ■
          </button>
          <span className="font-mono text-xs text-muted ml-2">
            {document
              ? `${formatTimelineTime(playheadMs)} / ${formatTimelineTime(document.duration_ms)}`
              : "00:00:00 / 00:00:00"}
          </span>
        </div>
      </div>
    </div>
  );
}
