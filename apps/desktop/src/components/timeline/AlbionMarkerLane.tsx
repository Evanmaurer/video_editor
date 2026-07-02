import type { PlacedAlbionMarker } from "@/services/albion-timeline-markers";
import { msToPixels } from "./timeline-math";

interface AlbionMarkerLaneProps {
  markers: PlacedAlbionMarker[];
  zoom: number;
  onMarkerClick: (timelineMs: number) => void;
}

export function AlbionMarkerLane({ markers, zoom, onMarkerClick }: AlbionMarkerLaneProps) {
  if (markers.length === 0) {
    return null;
  }

  return (
    <div className="flex border-b border-border/60 shrink-0" style={{ height: 22 }}>
      <div className="shrink-0 w-[120px] px-2 flex items-center text-[10px] text-muted border-r border-border bg-panel">
        Events
      </div>
      <div className="relative flex-1 bg-secondary/30">
        {markers.map((marker) => (
          <button
            key={marker.marker_id}
            type="button"
            title={`${marker.label} (${marker.marker_type})`}
            className="absolute top-1/2 -translate-y-1/2 w-2 h-4 rounded-sm hover:scale-125 transition-transform cursor-pointer z-10 border border-black/20"
            style={{
              left: msToPixels(marker.timeline_ms, zoom),
              backgroundColor: marker.color,
            }}
            onClick={(event) => {
              event.stopPropagation();
              onMarkerClick(marker.timeline_ms);
            }}
          />
        ))}
      </div>
    </div>
  );
}
