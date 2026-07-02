import type {
  AlbionTimelineAnnotationResult,
  TimelineClip,
  TimelineDocument,
} from "@montage/shared-types";

export interface PlacedAlbionMarker {
  marker_id: string;
  timeline_ms: number;
  marker_type: string;
  label: string;
  color: string;
  media_item_id: string;
}

export function mapSourceTimestampToTimeline(
  clip: TimelineClip,
  sourceTimestampMs: number,
): number | null {
  if (sourceTimestampMs < clip.source_in_ms || sourceTimestampMs > clip.source_out_ms) {
    return null;
  }
  const offsetInClip = (sourceTimestampMs - clip.source_in_ms) / clip.speed;
  return clip.start_ms + offsetInClip;
}

export function collectPlacedAlbionMarkers(
  document: TimelineDocument,
  annotationsByMediaId: Map<string, AlbionTimelineAnnotationResult>,
): PlacedAlbionMarker[] {
  const placed: PlacedAlbionMarker[] = [];

  for (const track of document.tracks) {
    for (const clip of track.clips) {
      const annotation = annotationsByMediaId.get(clip.media_item_id);
      if (!annotation) {
        continue;
      }
      for (const marker of annotation.markers) {
        const timelineMs = mapSourceTimestampToTimeline(clip, marker.timestamp_ms);
        if (timelineMs === null) {
          continue;
        }
        placed.push({
          marker_id: `${clip.id}:${marker.marker_id}`,
          timeline_ms: timelineMs,
          marker_type: marker.marker_type,
          label: marker.label,
          color: marker.color,
          media_item_id: clip.media_item_id,
        });
      }
    }
  }

  return placed.sort((left, right) => left.timeline_ms - right.timeline_ms);
}

export function uniqueTimelineMediaIds(document: TimelineDocument): string[] {
  const mediaIds = new Set<string>();
  for (const track of document.tracks) {
    for (const clip of track.clips) {
      mediaIds.add(clip.media_item_id);
    }
  }
  return [...mediaIds];
}
