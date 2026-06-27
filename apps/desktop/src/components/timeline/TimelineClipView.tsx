import type { TimelineClip } from "@montage/shared-types";
import { msToPixels } from "./timeline-math";

interface TimelineClipViewProps {
  clip: TimelineClip;
  label: string;
  zoom: number;
  selected: boolean;
  onSelect: (additive: boolean) => void;
  onTrimStart: (event: React.MouseEvent) => void;
  onTrimEnd: (event: React.MouseEvent) => void;
  onMoveStart: (event: React.MouseEvent) => void;
}

export function TimelineClipView({
  clip,
  label,
  zoom,
  selected,
  onSelect,
  onTrimStart,
  onTrimEnd,
  onMoveStart,
}: TimelineClipViewProps) {
  const left = msToPixels(clip.start_ms, zoom);
  const width = Math.max(msToPixels(clip.end_ms - clip.start_ms, zoom), 4);

  return (
    <div
      className={`absolute top-1 bottom-1 rounded text-[10px] overflow-hidden border ${
        selected ? "border-accent ring-1 ring-accent bg-accent/30" : "border-border bg-accent/20"
      }`}
      style={{ left, width }}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(e.shiftKey);
      }}
    >
      <div
        className="absolute left-0 top-0 bottom-0 w-1.5 cursor-ew-resize hover:bg-accent/60 z-10"
        onMouseDown={(e) => {
          e.stopPropagation();
          onTrimStart(e);
        }}
      />
      <div
        className="h-full px-2 flex items-center truncate cursor-grab active:cursor-grabbing"
        onMouseDown={(e) => {
          e.stopPropagation();
          onMoveStart(e);
        }}
      >
        {label}
      </div>
      <div
        className="absolute right-0 top-0 bottom-0 w-1.5 cursor-ew-resize hover:bg-accent/60 z-10"
        onMouseDown={(e) => {
          e.stopPropagation();
          onTrimEnd(e);
        }}
      />
    </div>
  );
}
