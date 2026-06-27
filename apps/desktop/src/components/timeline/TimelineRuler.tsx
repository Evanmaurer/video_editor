import { useCallback, useRef } from "react";
import { formatTimelineTime } from "./time-format";
import { msToPixels } from "./timeline-math";

interface TimelineRulerProps {
  durationMs: number;
  zoom: number;
  scrollLeft: number;
  viewportWidth: number;
  onSeek: (ms: number) => void;
}

export function TimelineRuler({
  durationMs,
  zoom,
  scrollLeft,
  viewportWidth,
  onSeek,
}: TimelineRulerProps) {
  const scrubbingRef = useRef(false);

  const visibleMs = (viewportWidth / msToPixels(1000, zoom)) * 1000;
  const endMs = Math.max(durationMs + 5000, visibleMs);
  const stepMs = zoom >= 2 ? 1000 : zoom >= 1 ? 2000 : 5000;

  const ticks: number[] = [];
  for (let t = 0; t <= endMs; t += stepMs) {
    ticks.push(t);
  }

  const seekFromClientX = useCallback(
    (clientX: number, target: HTMLElement) => {
      const rect = target.getBoundingClientRect();
      const x = clientX - rect.left + scrollLeft;
      const ms = (x / msToPixels(1000, zoom)) * 1000;
      onSeek(Math.max(0, Math.min(ms, durationMs)));
    },
    [durationMs, onSeek, scrollLeft, zoom],
  );

  return (
    <div
      className="relative h-7 border-b border-border bg-panel shrink-0 cursor-pointer overflow-hidden select-none"
      onPointerDown={(e) => {
        scrubbingRef.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
        seekFromClientX(e.clientX, e.currentTarget);
      }}
      onPointerMove={(e) => {
        if (!scrubbingRef.current) {
          return;
        }
        seekFromClientX(e.clientX, e.currentTarget);
      }}
      onPointerUp={(e) => {
        scrubbingRef.current = false;
        e.currentTarget.releasePointerCapture(e.pointerId);
      }}
      onPointerCancel={() => {
        scrubbingRef.current = false;
      }}
    >
      <div className="absolute inset-0" style={{ width: msToPixels(endMs, zoom) }}>
        {ticks.map((t) => (
          <div
            key={t}
            className="absolute top-0 h-full border-l border-border/60 text-[10px] text-muted pl-1 pt-0.5 pointer-events-none"
            style={{ left: msToPixels(t, zoom) }}
          >
            {formatTimelineTime(t)}
          </div>
        ))}
      </div>
    </div>
  );
}
