import type { TimelineDocument, TrackType } from "@montage/shared-types";
import { BaseCommand } from "./base";
import { newId, updateDocumentDuration } from "../utils";

export class AddTrackCommand extends BaseCommand {
  readonly type = "add_track";
  readonly trackId: string;

  constructor(
    readonly trackType: TrackType,
    readonly name?: string,
    readonly description = `Add ${trackType} track`,
  ) {
    super();
    this.trackId = newId("track");
  }

  apply(doc: TimelineDocument): TimelineDocument {
    const index = doc.tracks.length;
    const track = {
      id: this.trackId,
      type: this.trackType,
      name: this.name ?? `${this.trackType === "audio" ? "Audio" : "Video"} ${index + 1}`,
      index,
      muted: false,
      locked: false,
      visible: true,
      volume: 1,
      clips: [],
    };

    return updateDocumentDuration({
      ...doc,
      tracks: [...doc.tracks, track],
      updated_at: new Date().toISOString(),
    });
  }
}
