import { useEffect, useState } from "react";
import type { MediaMetadataSummary } from "@montage/shared-types";
import { useProjectStore } from "@/stores/project-store";
import { useTimelineStore, getSelectedClips } from "@/stores/timeline-store";
import { formatMsShort } from "@/components/timeline/time-format";
import { getApiClient } from "@/services/api-client";

export function Inspector() {
  const project = useProjectStore((s) => s.project);
  const document = useTimelineStore((s) => s.document);
  const selectedClipIds = useTimelineStore((s) => s.selectedClipIds);
  const playheadMs = useTimelineStore((s) => s.playheadMs);
  const rippleEnabled = useTimelineStore((s) => s.rippleEnabled);
  const deleteSelected = useTimelineStore((s) => s.deleteSelected);

  const selected =
    document && selectedClipIds.length > 0
      ? getSelectedClips(document, selectedClipIds)
      : [];

  const primaryClip = selected[0] ?? null;
  const [metadata, setMetadata] = useState<MediaMetadataSummary | null>(null);
  const [metadataError, setMetadataError] = useState<string | null>(null);

  useEffect(() => {
    if (!project?.id || !primaryClip?.media_item_id) {
      setMetadata(null);
      setMetadataError(null);
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const summary = await getApiClient().getMediaMetadata(
          project.id,
          primaryClip.media_item_id,
        );
        if (!cancelled) {
          setMetadata(summary);
          setMetadataError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setMetadata(null);
          setMetadataError(err instanceof Error ? err.message : "Metadata unavailable");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [project?.id, primaryClip?.media_item_id, primaryClip?.id]);

  return (
    <div className="h-full flex flex-col bg-secondary border-l border-border">
      <div className="px-3 py-2 border-b border-border text-sm font-medium">Inspector</div>
      <div className="flex-1 overflow-auto p-3 text-xs space-y-3">
        <section>
          <div className="text-muted mb-1">Playhead</div>
          <div>{formatMsShort(playheadMs)}</div>
        </section>

        {selected.length === 0 ? (
          <p className="text-muted">Select a clip to view properties</p>
        ) : (
          selected.map((clip) => (
            <section key={clip.id} className="space-y-1 border-t border-border pt-2">
              <div className="font-medium truncate">{clip.name ?? clip.id.slice(0, 8)}</div>
              <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-muted">
                <span>Start</span>
                <span>{formatMsShort(clip.start_ms)}</span>
                <span>Duration</span>
                <span>{formatMsShort(clip.end_ms - clip.start_ms)}</span>
                <span>Source in</span>
                <span>{formatMsShort(clip.source_in_ms)}</span>
                <span>Source out</span>
                <span>{formatMsShort(clip.source_out_ms)}</span>
                <span>Speed</span>
                <span>{clip.speed.toFixed(2)}×</span>
                <span>Track</span>
                <span className="truncate">{clip.track_id.slice(0, 8)}</span>
              </div>
            </section>
          ))
        )}

        {primaryClip && (
          <section className="border-t border-border pt-2 space-y-2">
            <div className="text-muted uppercase tracking-wide text-[10px]">AI Metadata</div>
            {metadataError && <p className="text-[#e74c3c]">{metadataError}</p>}
            {!metadata && !metadataError && (
              <p className="text-muted">Loading metadata…</p>
            )}
            {metadata && (
              <>
                <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-muted">
                  <span>Status</span>
                  <span>{metadata.status}</span>
                  {metadata.visual && (
                    <>
                      <span>Scenes</span>
                      <span>{metadata.visual.scenes.length}</span>
                      <span>Motion</span>
                      <span>{Math.round(metadata.visual.motion_score * 100)}%</span>
                      <span>Camera</span>
                      <span>{metadata.visual.camera_movement.label}</span>
                      <span>Sharpness</span>
                      <span>{Math.round(metadata.visual.sharpness * 100)}%</span>
                    </>
                  )}
                  {metadata.audio && (
                    <>
                      <span>Speech</span>
                      <span>{metadata.audio.speech.has_speech ? "Yes" : "No"}</span>
                      <span>Beats</span>
                      <span>{metadata.audio.beat_markers.length}</span>
                      <span>Silence</span>
                      <span>{metadata.audio.silence_regions.length} regions</span>
                    </>
                  )}
                </div>
                {metadata.status === "pending" || metadata.status === "processing" ? (
                  <p className="text-[10px] text-muted">
                    Metadata analysis runs in the background after import.
                  </p>
                ) : null}
              </>
            )}
          </section>
        )}
      </div>

      {selected.length > 0 && (
        <div className="p-3 border-t border-border">
          <button
            type="button"
            className="w-full btn-secondary text-xs py-1.5 text-red-300 hover:text-red-200"
            onClick={deleteSelected}
          >
            Remove from timeline{rippleEnabled ? " (ripple)" : ""}
          </button>
          <p className="text-[10px] text-muted mt-1.5 text-center">
            Or press Delete · Undo with ⌘Z
          </p>
        </div>
      )}
    </div>
  );
}
