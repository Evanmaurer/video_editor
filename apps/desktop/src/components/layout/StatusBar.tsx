import { useProjectStore } from "@/stores/project-store";
import { usePlaybackStore } from "@/stores/playback-store";

export function StatusBar() {
  const project = useProjectStore((s) => s.project);
  const health = useProjectStore((s) => s.health);
  const stats = usePlaybackStore((s) => s.stats);
  const isPlaying = usePlaybackStore((s) => s.isPlaying);
  const playbackError = usePlaybackStore((s) => s.playbackError);

  return (
    <div className="h-6 flex items-center px-3 bg-secondary border-t border-border text-xs text-muted gap-4 overflow-hidden">
      <span className="text-[#2ecc71] shrink-0">Ready</span>
      {project && <span className="shrink-0">Project: {project.name}</span>}
      {project && (
        <>
          <span className="shrink-0">FPS: {stats.playbackFps.toFixed(1)}</span>
          <span className="shrink-0">Dropped: {stats.droppedFrames}</span>
          <span className="shrink-0">Decode: {stats.decodeTimeMs.toFixed(1)} ms</span>
          <span className="shrink-0">Memory: {stats.memoryUsageMb.toFixed(1)} MB</span>
          {isPlaying && (
            <span className="shrink-0 text-[#2ecc71]">Video playback</span>
          )}
          {playbackError && (
            <span className="shrink-0 text-[#f39c12] truncate" title={playbackError}>
              {playbackError}
            </span>
          )}
        </>
      )}
      {health && (
        <>
          <span className="shrink-0 truncate">
            GPU: {health.gpu_available ? (health.gpu_name ?? "Available") : "CPU only"}
          </span>
          {health.ffmpeg_available === false && (
            <span className="text-[#e74c3c] truncate" title={health.ffmpeg_note ?? undefined}>
              FFmpeg not installed — run: brew install ffmpeg
            </span>
          )}
          {health.performance_note && (
            <span className="text-[#f39c12] truncate" title={health.performance_note}>
              {health.performance_note}
            </span>
          )}
        </>
      )}
    </div>
  );
}
