import type { TimelineClip, TimelineDocument } from "@montage/shared-types";
import { BaseCommand } from "./base";
import {
  findTrack,
  hasOverlap,
  newId,
  sortClipsOnTrack,
  syncClipEnd,
  updateDocumentDuration,
} from "../utils";

export interface AddClipInput {
  media_item_id: string;
  track_id: string;
  start_ms: number;
  source_in_ms?: number;
  source_out_ms: number;
  speed?: number;
  name?: string;
  clip_id?: string;
}

export class AddClipCommand extends BaseCommand {
  readonly type = "add_clip";
  readonly description: string;
  readonly clipId: string;

  constructor(private readonly input: AddClipInput) {
    super();
    this.clipId = input.clip_id ?? newId("clip");
    this.description = `Add clip ${this.clipId}`;
  }

  apply(doc: TimelineDocument): TimelineDocument {
    const track = findTrack(doc, this.input.track_id);
    if (!track || track.locked) {
      return doc;
    }

    const sourceIn = this.input.source_in_ms ?? 0;
    const speed = this.input.speed ?? 1;
    let clip: TimelineClip = {
      id: this.clipId,
      media_item_id: this.input.media_item_id,
      track_id: this.input.track_id,
      start_ms: Math.max(0, this.input.start_ms),
      end_ms: 0,
      source_in_ms: sourceIn,
      source_out_ms: this.input.source_out_ms,
      speed,
      opacity: 1,
      name: this.input.name,
    };
    clip = syncClipEnd(clip);

    if (hasOverlap(track.clips, clip.id, clip.start_ms, clip.end_ms)) {
      return doc;
    }

    const updatedTrack = sortClipsOnTrack({
      ...track,
      clips: [...track.clips, clip],
    });

    return updateDocumentDuration({
      ...doc,
      tracks: doc.tracks.map((t) => (t.id === track.id ? updatedTrack : t)),
      updated_at: new Date().toISOString(),
    });
  }
}

export class RemoveClipCommand extends BaseCommand {
  readonly type = "remove_clip";

  constructor(
    readonly clipId: string,
    readonly description = `Remove clip ${clipId}`,
  ) {
    super();
  }

  apply(doc: TimelineDocument): TimelineDocument {
    let changed = false;
    const tracks = doc.tracks.map((track) => {
      if (track.locked) {
        return track;
      }
      const nextClips = track.clips.filter((c) => c.id !== this.clipId);
      if (nextClips.length !== track.clips.length) {
        changed = true;
        return { ...track, clips: nextClips };
      }
      return track;
    });

    if (!changed) {
      return doc;
    }

    return updateDocumentDuration({
      ...doc,
      tracks,
      updated_at: new Date().toISOString(),
    });
  }
}

export class RippleDeleteClipCommand extends BaseCommand {
  readonly type = "ripple_delete_clip";

  constructor(
    readonly clipId: string,
    readonly description = `Ripple delete clip ${clipId}`,
  ) {
    super();
  }

  apply(doc: TimelineDocument): TimelineDocument {
    const located = doc.tracks
      .flatMap((track) => track.clips.map((clip) => ({ track, clip })))
      .find(({ clip }) => clip.id === this.clipId);

    if (!located || located.track.locked) {
      return doc;
    }

    const { track, clip } = located;
    const gap = clip.end_ms - clip.start_ms;
    const updatedClips = track.clips
      .filter((c) => c.id !== this.clipId)
      .map((c) =>
        c.start_ms >= clip.end_ms
          ? syncClipEnd({ ...c, start_ms: c.start_ms - gap })
          : c,
      );

    const tracks = doc.tracks.map((t) =>
      t.id === track.id ? sortClipsOnTrack({ ...t, clips: updatedClips }) : t,
    );

    return updateDocumentDuration({
      ...doc,
      tracks,
      updated_at: new Date().toISOString(),
    });
  }
}
