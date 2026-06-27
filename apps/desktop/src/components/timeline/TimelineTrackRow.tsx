import { useRef, useState } from "react";
import type { TimelineClip, TimelineTrack } from "@montage/shared-types";
import type { TimelineCommand } from "@montage/timeline-engine";
import { TimelineClipView } from "./TimelineClipView";
import { TRACK_HEIGHT, msToPixels, pixelsToMs } from "./timeline-math";
import {
  buildMoveClipCommand,
  buildTrimClipCommand,
} from "@/services/timeline-actions";

interface TimelineTrackRowProps {
  track: TimelineTrack;
  zoom: number;
  scrollLeft: number;
  selectedClipIds: string[];
  clipLabels: Record<string, string>;
  snapEnabled: boolean;
  rippleEnabled: boolean;
  onExecute: (command: TimelineCommand) => void;
  onSelectClip: (clipId: string | null, additive?: boolean) => void;
  onDropMedia: (trackId: string, startMs: number, mediaJson: string) => void;
}

type DragMode = "move" | "trim-start" | "trim-end";

interface DragState {
  clipId: string;
  mode: DragMode;
  startX: number;
  origStart: number;
  origEnd: number;
  origSourceIn: number;
  origSourceOut: number;
  speed: number;
}

function withPreview(clip: TimelineClip, previewMs: number, mode: DragMode): TimelineClip {
  if (mode === "move") {
    const duration = clip.end_ms - clip.start_ms;
    return { ...clip, start_ms: previewMs, end_ms: previewMs + duration };
  }
  if (mode === "trim-start") {
    return { ...clip, start_ms: previewMs };
  }
  return { ...clip, end_ms: previewMs };
}

export function TimelineTrackRow({
  track,
  zoom,
  scrollLeft,
  selectedClipIds,
  clipLabels,
  snapEnabled,
  rippleEnabled,
  onExecute,
  onSelectClip,
  onDropMedia,
}: TimelineTrackRowProps) {
  const dragRef = useRef<DragState | null>(null);
  const [preview, setPreview] = useState<{ clipId: string; ms: number; mode: DragMode } | null>(
    null,
  );

  const commitDrag = (drag: DragState, deltaMs: number) => {
    if (drag.mode === "move") {
      onExecute(
        buildMoveClipCommand(drag.clipId, drag.origStart + deltaMs, track.id, snapEnabled),
      );
      return;
    }
    if (drag.mode === "trim-start") {
      const newStart = Math.max(0, drag.origStart + deltaMs);
      const sourceDelta = (newStart - drag.origStart) * drag.speed;
      onExecute(
        buildTrimClipCommand(drag.clipId, {
          start_ms: newStart,
          source_in_ms: drag.origSourceIn + sourceDelta,
          ripple: rippleEnabled,
        }),
      );
      return;
    }
    const newEnd = Math.max(drag.origStart + 100, drag.origEnd + deltaMs);
    onExecute(
      buildTrimClipCommand(drag.clipId, {
        end_ms: newEnd,
        ripple: rippleEnabled,
      }),
    );
  };

  const onMouseMove = (e: MouseEvent) => {
    const drag = dragRef.current;
    if (!drag) {
      return;
    }
    const deltaMs = pixelsToMs(e.clientX - drag.startX, zoom);
    if (drag.mode === "move") {
      setPreview({ clipId: drag.clipId, ms: Math.max(0, drag.origStart + deltaMs), mode: drag.mode });
      return;
    }
    if (drag.mode === "trim-start") {
      setPreview({
        clipId: drag.clipId,
        ms: Math.max(0, drag.origStart + deltaMs),
        mode: drag.mode,
      });
      return;
    }
    setPreview({
      clipId: drag.clipId,
      ms: Math.max(drag.origStart + 100, drag.origEnd + deltaMs),
      mode: drag.mode,
    });
  };

  const onMouseUp = (e: MouseEvent) => {
    const drag = dragRef.current;
    if (drag) {
      const deltaMs = pixelsToMs(e.clientX - drag.startX, zoom);
      commitDrag(drag, deltaMs);
    }
    dragRef.current = null;
    setPreview(null);
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
  };

  const startDrag = (clip: TimelineClip, mode: DragMode, clientX: number) => {
    dragRef.current = {
      clipId: clip.id,
      mode,
      startX: clientX,
      origStart: clip.start_ms,
      origEnd: clip.end_ms,
      origSourceIn: clip.source_in_ms,
      origSourceOut: clip.source_out_ms,
      speed: clip.speed,
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

  return (
    <div
      className="flex border-b border-border/60"
      style={{ height: TRACK_HEIGHT }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const mediaJson = e.dataTransfer.getData("application/montage-media");
        if (!mediaJson) {
          return;
        }
        const rect = e.currentTarget.querySelector("[data-track-lane]")?.getBoundingClientRect();
        if (!rect) {
          return;
        }
        const x = e.clientX - rect.left + scrollLeft;
        onDropMedia(track.id, Math.max(0, pixelsToMs(x, zoom)), mediaJson);
      }}
    >
      <div className="shrink-0 w-[120px] px-2 flex items-center text-xs border-r border-border truncate bg-panel">
        <span className="truncate" title={track.name}>
          {track.type === "audio" ? "🔊" : "🎬"} {track.name}
        </span>
      </div>
      <div
        data-track-lane
        className="relative flex-1 bg-secondary/50"
        onClick={() => onSelectClip(null)}
      >
        {track.clips.map((clip) => {
          const isPreview = preview?.clipId === clip.id;
          const displayClip =
            isPreview && preview
              ? withPreview(clip, preview.ms, preview.mode)
              : clip;
          return (
            <TimelineClipView
              key={clip.id}
              clip={displayClip}
              label={clipLabels[clip.id] ?? clip.name ?? clip.media_item_id.slice(0, 8)}
              zoom={zoom}
              selected={selectedClipIds.includes(clip.id)}
              onSelect={(additive) => onSelectClip(clip.id, additive)}
              onMoveStart={(e) => startDrag(clip, "move", e.clientX)}
              onTrimStart={(e) => startDrag(clip, "trim-start", e.clientX)}
              onTrimEnd={(e) => startDrag(clip, "trim-end", e.clientX)}
            />
          );
        })}
      </div>
    </div>
  );
}
