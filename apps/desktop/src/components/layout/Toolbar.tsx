import { formatTimelineTime } from "@/components/timeline/time-format";
import { useProjectStore, useUIStore } from "@/stores/project-store";
import { useMediaStore } from "@/stores/media-store";
import { usePlaybackStore } from "@/stores/playback-store";
import { useTimelineStore } from "@/stores/timeline-store";

export function Toolbar() {
  const project = useProjectStore((s) => s.project);
  const importPaths = useMediaStore((s) => s.importPaths);
  const document = useTimelineStore((s) => s.document);
  const playheadMs = useTimelineStore((s) => s.playheadMs);
  const isPlaying = usePlaybackStore((s) => s.isPlaying);
  const togglePlay = usePlaybackStore((s) => s.togglePlay);
  const setShowExportDialog = useUIStore((s) => s.setShowExportDialog);
  const setShowRenderQueue = useUIStore((s) => s.setShowRenderQueue);

  const hasClips =
    document?.tracks.some((track) => track.clips.length > 0) ?? false;
  const canPlay = Boolean(project?.id && document && hasClips);
  const canExport = Boolean(project?.id && document && hasClips);

  const handleImport = async () => {
    if (!project?.id) {
      return;
    }
    const paths = await window.montageAPI.openVideoFiles();
    if (paths.length > 0) {
      await importPaths(project.id, paths);
    }
  };

  return (
    <div className="h-10 flex items-center gap-2 px-3 bg-panel border-b border-border text-sm">
      <button type="button" className="btn-secondary text-xs py-1 px-2" onClick={() => void handleImport()}>
        Import
      </button>
      <button type="button" className="btn-secondary text-xs py-1 px-2 opacity-50" disabled>
        Generate Timeline
      </button>
      <button type="button" className="btn-secondary text-xs py-1 px-2 opacity-50" disabled>
        Analyze All
      </button>
      <div className="w-px h-6 bg-border mx-1" />
      <button
        type="button"
        className="btn-secondary text-xs py-1 px-2"
        disabled={!canPlay}
        onClick={() => togglePlay()}
        title={isPlaying ? "Pause (Space)" : "Play (Space)"}
      >
        {isPlaying ? "⏸ Pause" : "▶ Play"}
      </button>
      <div className="flex-1" />
      <button
        type="button"
        className="btn-secondary text-xs py-1 px-2"
        disabled={!canExport}
        onClick={() => setShowExportDialog(true)}
      >
        Export
      </button>
      <button
        type="button"
        className="btn-secondary text-xs py-1 px-2"
        disabled={!project?.id}
        onClick={() => setShowRenderQueue(true)}
      >
        Render Queue
      </button>
      {document && (
        <span className="text-xs text-muted font-mono ml-2">
          {formatTimelineTime(playheadMs)} / {formatTimelineTime(document.duration_ms)}
        </span>
      )}
    </div>
  );
}
