import type { TimelineDocument } from "@montage/shared-types";
import { BaseCommand } from "./base";
import { snapTimeMs, type SnapOptions } from "../snap";
import {
  findClip,
  hasOverlap,
  newId,
  sortClipsOnTrack,
  syncClipEnd,
  updateDocumentDuration,
} from "../utils";

export class MoveClipCommand extends BaseCommand {
  readonly type = "move_clip";

  constructor(
    readonly clipId: string,
    readonly newStartMs: number,
    readonly newTrackId?: string,
    readonly snapOptions?: SnapOptions,
    readonly description = `Move clip ${clipId}`,
  ) {
    super();
  }

  apply(doc: TimelineDocument): TimelineDocument {
    const located = findClip(doc, this.clipId);
    if (!located || located.track.locked) {
      return doc;
    }

    const targetTrackId = this.newTrackId ?? located.track.id;
    const targetTrack = doc.tracks.find((t) => t.id === targetTrackId);
    if (!targetTrack || targetTrack.locked) {
      return doc;
    }

    const duration = located.clip.end_ms - located.clip.start_ms;
    let startMs = Math.max(0, this.newStartMs);
    if (this.snapOptions) {
      startMs = snapTimeMs(startMs, doc, {
        ...this.snapOptions,
        frameRate: doc.settings.frame_rate,
      });
    }
    const endMs = startMs + duration;

    const otherClips =
      targetTrackId === located.track.id
        ? targetTrack.clips
        : targetTrack.clips;
    if (hasOverlap(otherClips, this.clipId, startMs, endMs)) {
      return doc;
    }

    const movedClip = syncClipEnd({
      ...located.clip,
      track_id: targetTrackId,
      start_ms: startMs,
    });

    const sourceTrackClips = located.track.clips.filter((c) => c.id !== this.clipId);
    const targetTrackClips =
      targetTrackId === located.track.id
        ? [...sourceTrackClips, movedClip]
        : [...targetTrack.clips, movedClip];

    const tracks = doc.tracks.map((track) => {
      if (track.id === located.track.id && track.id === targetTrackId) {
        return sortClipsOnTrack({ ...track, clips: targetTrackClips });
      }
      if (track.id === located.track.id) {
        return sortClipsOnTrack({ ...track, clips: sourceTrackClips });
      }
      if (track.id === targetTrackId) {
        return sortClipsOnTrack({ ...track, clips: targetTrackClips });
      }
      return track;
    });

    return updateDocumentDuration({
      ...doc,
      tracks,
      updated_at: new Date().toISOString(),
    });
  }
}

export interface TrimClipInput {
  clipId: string;
  /** New timeline start (left trim) */
  start_ms?: number;
  /** New timeline end (right trim) */
  end_ms?: number;
  /** New source in point */
  source_in_ms?: number;
  /** New source out point */
  source_out_ms?: number;
  ripple?: boolean;
}

export class TrimClipCommand extends BaseCommand {
  readonly type = "trim_clip";
  readonly description: string;

  constructor(private readonly input: TrimClipInput) {
    super();
    this.description = `Trim clip ${input.clipId}`;
  }

  apply(doc: TimelineDocument): TimelineDocument {
    const located = findClip(doc, this.input.clipId);
    if (!located || located.track.locked) {
      return doc;
    }

    let clip = { ...located.clip };
    const prevEnd = clip.end_ms;

    if (this.input.source_in_ms !== undefined) {
      clip.source_in_ms = Math.max(0, this.input.source_in_ms);
    }
    if (this.input.source_out_ms !== undefined) {
      clip.source_out_ms = Math.max(clip.source_in_ms + 1, this.input.source_out_ms);
    }
    if (this.input.start_ms !== undefined) {
      clip.start_ms = Math.max(0, this.input.start_ms);
    }
    clip = syncClipEnd(clip);
    if (this.input.end_ms !== undefined) {
      const duration = this.input.end_ms - clip.start_ms;
      clip.source_out_ms = clip.source_in_ms + duration * clip.speed;
      clip = syncClipEnd(clip);
    }

    if (hasOverlap(located.track.clips, clip.id, clip.start_ms, clip.end_ms)) {
      return doc;
    }

    let updatedClips = located.track.clips.map((c) => (c.id === clip.id ? clip : c));

    if (this.input.ripple) {
      const delta = clip.end_ms - prevEnd;
      if (delta !== 0) {
        updatedClips = updatedClips.map((c) => {
          if (c.id === clip.id || c.start_ms < prevEnd) {
            return c;
          }
          return syncClipEnd({ ...c, start_ms: c.start_ms + delta });
        });
      }
    }

    const tracks = doc.tracks.map((t) =>
      t.id === located.track.id ? sortClipsOnTrack({ ...t, clips: updatedClips }) : t,
    );

    return updateDocumentDuration({
      ...doc,
      tracks,
      updated_at: new Date().toISOString(),
    });
  }
}

export class SplitClipCommand extends BaseCommand {
  readonly type = "split_clip";
  readonly newClipId: string;

  constructor(
    readonly clipId: string,
    readonly splitAtMs: number,
    readonly description = `Split clip ${clipId}`,
  ) {
    super();
    this.newClipId = newId("clip");
  }

  apply(doc: TimelineDocument): TimelineDocument {
    const found = findClip(doc, this.clipId);
    if (!found || found.track.locked) {
      return doc;
    }

    const { track, clip } = found;
    if (this.splitAtMs <= clip.start_ms || this.splitAtMs >= clip.end_ms) {
      return doc;
    }

    const timelineOffset = this.splitAtMs - clip.start_ms;
    const sourceSplit =
      clip.source_in_ms + timelineOffset * clip.speed;

    const left = syncClipEnd({
      ...clip,
      source_out_ms: sourceSplit,
    });

    const right = syncClipEnd({
      ...clip,
      id: this.newClipId,
      start_ms: this.splitAtMs,
      source_in_ms: sourceSplit,
    });

    const clips = track.clips.flatMap((c) => (c.id === clip.id ? [left, right] : [c]));

    const tracks = doc.tracks.map((t) =>
      t.id === track.id ? sortClipsOnTrack({ ...t, clips }) : t,
    );

    return updateDocumentDuration({
      ...doc,
      tracks,
      updated_at: new Date().toISOString(),
    });
  }
}

export class PasteClipsCommand extends BaseCommand {
  readonly type = "paste_clips";
  readonly createdClipIds: string[] = [];

  constructor(
    private readonly clips: Array<{
      media_item_id: string;
      source_in_ms: number;
      source_out_ms: number;
      speed: number;
      opacity: number;
      name?: string;
      timelineDurationMs: number;
    }>,
    private readonly trackId: string,
    private readonly startMs: number,
    readonly description = "Paste clips",
  ) {
    super();
  }

  apply(doc: TimelineDocument): TimelineDocument {
    const track = doc.tracks.find((t) => t.id === this.trackId);
    if (!track || track.locked) {
      return doc;
    }

    let cursor = this.startMs;
    const newClips = this.clips.map((template) => {
      const id = newId("clip");
      this.createdClipIds.push(id);
      const clip = syncClipEnd({
        id,
        media_item_id: template.media_item_id,
        track_id: this.trackId,
        start_ms: cursor,
        end_ms: 0,
        source_in_ms: template.source_in_ms,
        source_out_ms: template.source_out_ms,
        speed: template.speed,
        opacity: template.opacity,
        name: template.name,
      });
      cursor = clip.end_ms;
      return clip;
    });

    for (const clip of newClips) {
      if (hasOverlap(track.clips, clip.id, clip.start_ms, clip.end_ms)) {
        return doc;
      }
    }

    const updatedTrack = sortClipsOnTrack({
      ...track,
      clips: [...track.clips, ...newClips],
    });

    return updateDocumentDuration({
      ...doc,
      tracks: doc.tracks.map((t) => (t.id === track.id ? updatedTrack : t)),
      updated_at: new Date().toISOString(),
    });
  }
}
