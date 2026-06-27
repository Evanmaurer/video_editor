import { useRef } from "react";
import { formatTimelineTime } from "@/components/timeline/time-format";
import { usePlaybackStore } from "@/stores/playback-store";
import { useTimelineStore } from "@/stores/timeline-store";
import { toggleTimelinePlayback, stopPlayback } from "@/services/playback-controller";
import { usePreviewPlayback } from "./usePreviewPlayback";

export function PreviewWindow() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const document = useTimelineStore((s) => s.document);
  const playheadMs = useTimelineStore((s) => s.playheadMs);
  const isLoading = useTimelineStore((s) => s.isLoading);
  const isPlaying = usePlaybackStore((s) => s.isPlaying);
  const quality = usePlaybackStore((s) => s.quality);
  const useVideoSurface = usePlaybackStore((s) => s.useVideoSurface);
  const stepFrame = usePlaybackStore((s) => s.stepFrame);
  const setQuality = usePlaybackStore((s) => s.setQuality);

  usePreviewPlayback(videoRef, canvasRef);

  const handleTransportToggle = () => {
    void toggleTimelinePlayback(videoRef.current);
  };

  const hasClips =
    document?.tracks.some((track) => track.clips.length > 0) ?? false;
  const canPlay = Boolean(document && hasClips);

  return (
    <div className="h-full flex flex-col bg-primary border-b border-border">
      <div className="px-3 py-2 border-b border-border text-sm font-medium flex items-center justify-between">
        <span>Preview</span>
        <div className="flex items-center gap-2 text-xs">
          <label className="text-muted flex items-center gap-1">
            Quality
            <select
              className="bg-panel border border-border rounded px-1 py-0.5 text-foreground"
              value={quality}
              onChange={(e) => setQuality(e.target.value as "proxy" | "full")}
            >
              <option value="proxy">Proxy</option>
              <option value="full">Full</option>
            </select>
          </label>
        </div>
      </div>
      <div className="flex-1 panel-empty">
        <div className="relative w-full max-w-2xl aspect-video bg-black border border-border rounded-md overflow-hidden">
          {isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-muted text-sm">Loading timeline…</span>
            </div>
          ) : !document ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-muted text-sm">No timeline loaded</span>
            </div>
          ) : !hasClips ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-muted text-sm">Drag clips onto the timeline</span>
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                className={`absolute inset-0 w-full h-full object-contain ${
                  useVideoSurface ? "z-10" : "z-0 pointer-events-none"
                }`}
                style={{ transform: "translateZ(0)" }}
                playsInline
                preload="auto"
              />
              <canvas
                ref={canvasRef}
                className={`absolute inset-0 w-full h-full object-contain ${
                  useVideoSurface ? "z-0 pointer-events-none" : "z-10"
                }`}
              />
            </>
          )}
        </div>
        <div className="flex items-center gap-2 mt-4">
          <button
            type="button"
            className="btn-secondary"
            disabled={!canPlay}
            onClick={() => stepFrame(-1)}
            title="Previous frame"
          >
            ◀◀
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={!canPlay}
            onClick={handleTransportToggle}
            title={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? "⏸" : "▶"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={!canPlay}
            onClick={() => {
              stopPlayback();
              void usePlaybackStore.getState().seekTimeline(0);
            }}
            title="Stop"
          >
            ■
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={!canPlay}
            onClick={() => stepFrame(1)}
            title="Next frame"
          >
            ▶▶
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
