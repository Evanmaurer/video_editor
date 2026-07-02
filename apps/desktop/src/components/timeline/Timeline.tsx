import { useEffect, useRef, useState } from "react";
import type { AlbionTimelineAnnotationResult, MediaItem } from "@montage/shared-types";
import { useMediaStore } from "@/stores/media-store";
import { useProjectStore } from "@/stores/project-store";
import { usePlaybackStore } from "@/stores/playback-store";
import { useTimelineStore } from "@/stores/timeline-store";
import { buildAddClipFromMediaCommand } from "@/services/timeline-actions";
import { getApiClient } from "@/services/api-client";
import {
  collectPlacedAlbionMarkers,
  type PlacedAlbionMarker,
  uniqueTimelineMediaIds,
} from "@/services/albion-timeline-markers";
import { AlbionMarkerLane } from "./AlbionMarkerLane";
import { TimelineRuler } from "./TimelineRuler";
import { TimelineToolbar } from "./TimelineToolbar";
import { TimelineTrackRow } from "./TimelineTrackRow";
import { TRACK_HEADER_WIDTH, msToPixels } from "./timeline-math";
import { useTimelineKeyboard } from "./useTimelineKeyboard";

export function Timeline() {
  const project = useProjectStore((s) => s.project);
  const mediaItems = useMediaStore((s) => s.items);
  const document = useTimelineStore((s) => s.document);
  const canUndo = useTimelineStore((s) => s.canUndo);
  const canRedo = useTimelineStore((s) => s.canRedo);
  const playheadMs = useTimelineStore((s) => s.playheadMs);
  const zoom = useTimelineStore((s) => s.zoom);
  const snapEnabled = useTimelineStore((s) => s.snapEnabled);
  const rippleEnabled = useTimelineStore((s) => s.rippleEnabled);
  const selectedClipIds = useTimelineStore((s) => s.selectedClipIds);
  const isLoading = useTimelineStore((s) => s.isLoading);
  const isSaving = useTimelineStore((s) => s.isSaving);
  const saveError = useTimelineStore((s) => s.saveError);
  const loadTimeline = useTimelineStore((s) => s.loadTimeline);
  const execute = useTimelineStore((s) => s.execute);
  const undo = useTimelineStore((s) => s.undo);
  const redo = useTimelineStore((s) => s.redo);
  const seekTimeline = usePlaybackStore((s) => s.seekTimeline);
  const zoomIn = useTimelineStore((s) => s.zoomIn);
  const zoomOut = useTimelineStore((s) => s.zoomOut);
  const toggleSnap = useTimelineStore((s) => s.toggleSnap);
  const toggleRipple = useTimelineStore((s) => s.toggleRipple);
  const selectClip = useTimelineStore((s) => s.selectClip);
  const splitAtPlayhead = useTimelineStore((s) => s.splitAtPlayhead);
  const deleteSelected = useTimelineStore((s) => s.deleteSelected);
  const reset = useTimelineStore((s) => s.reset);

  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [viewportWidth, setViewportWidth] = useState(800);
  const [albionMarkers, setAlbionMarkers] = useState<PlacedAlbionMarker[]>([]);

  useTimelineKeyboard();

  useEffect(() => {
    if (!project?.id) {
      reset();
      usePlaybackStore.getState().reset();
      return;
    }
    usePlaybackStore.getState().setProjectId(project.id);
    void loadTimeline(project.id);
    void useMediaStore.getState().loadMedia(project.id);
    return () => {
      reset();
      usePlaybackStore.getState().reset();
    };
  }, [project?.id, loadTimeline, reset]);

  useEffect(() => {
    if (!project?.id || !document) {
      setAlbionMarkers([]);
      return;
    }

    const mediaIds = uniqueTimelineMediaIds(document);
    if (mediaIds.length === 0) {
      setAlbionMarkers([]);
      return;
    }

    let cancelled = false;
    void (async () => {
      const client = getApiClient();
      const annotationsByMediaId = new Map<string, AlbionTimelineAnnotationResult>();
      await Promise.all(
        mediaIds.map(async (mediaId) => {
          try {
            const annotation = await client.getAlbionTimelineAnnotations(project.id, mediaId);
            if (annotation) {
              annotationsByMediaId.set(mediaId, annotation);
            }
          } catch {
            // Albion cache may not exist for this clip yet.
          }
        }),
      );
      if (!cancelled) {
        setAlbionMarkers(collectPlacedAlbionMarkers(document, annotationsByMediaId));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [project?.id, document]);

  const handleSeek = (ms: number) => {
    void seekTimeline(ms);
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) {
      return;
    }
    const observer = new ResizeObserver(() => setViewportWidth(el.clientWidth - TRACK_HEADER_WIDTH));
    observer.observe(el);
    setViewportWidth(el.clientWidth - TRACK_HEADER_WIDTH);
    return () => observer.disconnect();
  }, []);

  const clipLabels: Record<string, string> = {};
  for (const item of mediaItems) {
    clipLabels[item.id] = item.file_name;
  }
  for (const track of document?.tracks ?? []) {
    for (const clip of track.clips) {
      if (!clipLabels[clip.id] && clip.name) {
        clipLabels[clip.id] = clip.name;
      }
    }
  }

  const handleDropMedia = (trackId: string, startMs: number, mediaJson: string) => {
    try {
      const media = JSON.parse(mediaJson) as MediaItem;
      const track = document?.tracks.find((t) => t.id === trackId);
      if (!track || track.locked) {
        return;
      }
      if (track.type === "video" && media.media_type !== "video") {
        return;
      }
      if (track.type === "audio" && media.media_type !== "audio" && media.media_type !== "video") {
        return;
      }
      execute(buildAddClipFromMediaCommand(media, trackId, startMs));
    } catch {
      // invalid drop payload
    }
  };

  const contentWidth = msToPixels(Math.max(document?.duration_ms ?? 0, 30000), zoom);

  return (
    <div className="h-full flex flex-col bg-secondary">
      <div className="px-3 py-2 border-b border-border text-sm font-medium flex items-center justify-between">
        <span>Timeline</span>
        {document && (
          <span className="text-xs text-muted font-normal">{document.name}</span>
        )}
      </div>

      <TimelineToolbar
        canUndo={canUndo}
        canRedo={canRedo}
        canDelete={selectedClipIds.length > 0}
        snapEnabled={snapEnabled}
        rippleEnabled={rippleEnabled}
        isSaving={isSaving}
        zoom={zoom}
        onUndo={undo}
        onRedo={redo}
        onSplit={splitAtPlayhead}
        onDelete={deleteSelected}
        onToggleSnap={toggleSnap}
        onToggleRipple={toggleRipple}
        onZoomIn={zoomIn}
        onZoomOut={zoomOut}
      />

      {saveError && (
        <div className="px-3 py-1 text-xs text-red-400 border-b border-border">{saveError}</div>
      )}

      {isLoading && (
        <div className="panel-empty flex-1">Loading timeline…</div>
      )}

      {!isLoading && document && (
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          <div className="flex shrink-0">
            <div className="shrink-0 w-[120px] border-r border-border bg-panel" />
            <div className="flex-1 overflow-hidden">
              <TimelineRuler
                durationMs={document.duration_ms}
                zoom={zoom}
                scrollLeft={scrollLeft}
                viewportWidth={viewportWidth}
                onSeek={handleSeek}
              />
            </div>
          </div>

          <div
            ref={scrollRef}
            className="flex-1 overflow-auto relative"
            onScroll={(e) => setScrollLeft(e.currentTarget.scrollLeft)}
          >
            <div className="relative" style={{ minWidth: contentWidth + TRACK_HEADER_WIDTH }}>
              <AlbionMarkerLane
                markers={albionMarkers}
                zoom={zoom}
                onMarkerClick={handleSeek}
              />

              {document.tracks.map((track) => (
                <TimelineTrackRow
                  key={track.id}
                  track={track}
                  zoom={zoom}
                  scrollLeft={scrollLeft}
                  selectedClipIds={selectedClipIds}
                  clipLabels={clipLabels}
                  snapEnabled={snapEnabled}
                  rippleEnabled={rippleEnabled}
                  onExecute={execute}
                  onSelectClip={selectClip}
                  onDropMedia={handleDropMedia}
                />
              ))}

              <div
                className="absolute top-0 bottom-0 w-px bg-red-500 z-20 pointer-events-none"
                style={{ left: TRACK_HEADER_WIDTH + msToPixels(playheadMs, zoom) }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
