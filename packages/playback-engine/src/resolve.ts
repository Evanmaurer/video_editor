import type { TimelineDocument, TimelineTrack } from "@montage/shared-types";
import type { ResolvedVideoFrame } from "./types";

function visibleVideoTracks(tracks: TimelineTrack[]): TimelineTrack[] {
  return tracks
    .filter((track) => track.type === "video" && track.visible)
    .sort((a, b) => a.index - b.index);
}

export function snapToFrameMs(timeMs: number, frameRate: number): number {
  if (frameRate <= 0) {
    return Math.max(0, timeMs);
  }
  const frameMs = 1000 / frameRate;
  return Math.max(0, Math.round(timeMs / frameMs) * frameMs);
}

export function resolveVideoFrameAtTime(
  document: TimelineDocument,
  timelineMs: number,
): ResolvedVideoFrame | null {
  const timeMs = Math.max(0, timelineMs);

  for (const track of visibleVideoTracks(document.tracks)) {
    for (const clip of track.clips) {
      if (timeMs >= clip.start_ms && timeMs < clip.end_ms) {
        const offset = timeMs - clip.start_ms;
        const sourceMs = clip.source_in_ms + offset * clip.speed;
        return {
          clip,
          track,
          timelineMs: timeMs,
          sourceMs: Math.min(sourceMs, clip.source_out_ms),
        };
      }
    }
  }

  return null;
}

export function findNextVideoClip(
  document: TimelineDocument,
  afterTimelineMs: number,
  trackId?: string,
): ResolvedVideoFrame | null {
  const tracks = visibleVideoTracks(document.tracks).filter((track) =>
    trackId ? track.id === trackId : true,
  );

  let best: ResolvedVideoFrame | null = null;

  for (const track of tracks) {
    for (const clip of track.clips) {
      if (clip.start_ms >= afterTimelineMs) {
        const candidate: ResolvedVideoFrame = {
          clip,
          track,
          timelineMs: clip.start_ms,
          sourceMs: clip.source_in_ms,
        };
        if (!best || candidate.clip.start_ms < best.clip.start_ms) {
          best = candidate;
        }
      }
    }
  }

  return best;
}

export function timelineMsFromSource(
  clip: ResolvedVideoFrame["clip"],
  sourceMs: number,
): number {
  const localSource = Math.max(clip.source_in_ms, Math.min(sourceMs, clip.source_out_ms));
  const offset = (localSource - clip.source_in_ms) / clip.speed;
  return clip.start_ms + offset;
}
