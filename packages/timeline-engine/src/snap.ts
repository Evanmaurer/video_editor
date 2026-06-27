import type { TimelineDocument } from "@montage/shared-types";
import { snapToFrame } from "./utils";

export interface SnapOptions {
  threshold_ms?: number;
  snapToClips?: boolean;
  snapToMarkers?: boolean;
  snapToBeats?: boolean;
  snapToZero?: boolean;
  frameRate?: number;
  snapToFrames?: boolean;
}

const DEFAULT_THRESHOLD_MS = 50;

export function snapTimeMs(
  timeMs: number,
  doc: TimelineDocument,
  options: SnapOptions = {},
): number {
  const threshold = options.threshold_ms ?? DEFAULT_THRESHOLD_MS;
  const candidates: number[] = [];

  if (options.snapToZero !== false) {
    candidates.push(0);
  }

  if (options.snapToClips !== false) {
    for (const track of doc.tracks) {
      for (const clip of track.clips) {
        candidates.push(clip.start_ms, clip.end_ms);
      }
    }
  }

  if (options.snapToMarkers !== false) {
    for (const marker of doc.markers) {
      candidates.push(marker.time_ms);
    }
  }

  if (options.snapToBeats) {
    for (const beat of doc.beat_markers) {
      candidates.push(beat.time_ms);
    }
  }

  let best = timeMs;
  let bestDistance = threshold + 1;

  for (const candidate of candidates) {
    const distance = Math.abs(candidate - timeMs);
    if (distance <= threshold && distance < bestDistance) {
      best = candidate;
      bestDistance = distance;
    }
  }

  if (options.snapToFrames && options.frameRate) {
    const framed = snapToFrame(best, options.frameRate);
    if (Math.abs(framed - timeMs) <= threshold) {
      return framed;
    }
  }

  return best;
}
