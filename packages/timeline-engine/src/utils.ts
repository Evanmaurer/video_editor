import type { TimelineClip, TimelineDocument, TimelineTrack } from "@montage/shared-types";

export function newId(prefix = "id"): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function cloneDocument(doc: TimelineDocument): TimelineDocument {
  return structuredClone(doc);
}

export function clipTimelineDurationMs(clip: TimelineClip): number {
  return Math.max(0, (clip.source_out_ms - clip.source_in_ms) / clip.speed);
}

export function syncClipEnd(clip: TimelineClip): TimelineClip {
  const duration = clipTimelineDurationMs(clip);
  return { ...clip, end_ms: clip.start_ms + duration };
}

export function findTrack(doc: TimelineDocument, trackId: string): TimelineTrack | undefined {
  return doc.tracks.find((t) => t.id === trackId);
}

export function findClip(
  doc: TimelineDocument,
  clipId: string,
): { track: TimelineTrack; clip: TimelineClip; index: number } | undefined {
  for (const track of doc.tracks) {
    const index = track.clips.findIndex((c) => c.id === clipId);
    if (index >= 0) {
      const clip = track.clips[index];
      if (clip) {
        return { track, clip, index };
      }
    }
  }
  return undefined;
}

export function sortClipsOnTrack(track: TimelineTrack): TimelineTrack {
  return {
    ...track,
    clips: [...track.clips].sort((a, b) => a.start_ms - b.start_ms),
  };
}

export function computeTimelineDuration(doc: TimelineDocument): number {
  let maxEnd = 0;
  for (const track of doc.tracks) {
    for (const clip of track.clips) {
      maxEnd = Math.max(maxEnd, clip.end_ms);
    }
  }
  return maxEnd;
}

export function hasOverlap(
  clips: TimelineClip[],
  clipId: string,
  startMs: number,
  endMs: number,
): boolean {
  return clips.some((c) => {
    if (c.id === clipId) {
      return false;
    }
    return startMs < c.end_ms && endMs > c.start_ms;
  });
}

export function replaceTrack(doc: TimelineDocument, track: TimelineTrack): TimelineDocument {
  return {
    ...doc,
    tracks: doc.tracks.map((t) => (t.id === track.id ? track : t)),
  };
}

export function updateDocumentDuration(doc: TimelineDocument): TimelineDocument {
  return { ...doc, duration_ms: computeTimelineDuration(doc) };
}

export function frameDurationMs(frameRate: number): number {
  return frameRate > 0 ? 1000 / frameRate : 1000 / 60;
}

export function snapToFrame(timeMs: number, frameRate: number): number {
  const frame = frameDurationMs(frameRate);
  return Math.round(timeMs / frame) * frame;
}
