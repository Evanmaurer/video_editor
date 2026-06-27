import type { MediaItem, TimelineDocument } from "@montage/shared-types";
import {
  AddClipCommand,
  MoveClipCommand,
  PasteClipsCommand,
  RemoveClipCommand,
  RippleDeleteClipCommand,
  SplitClipCommand,
  TrimClipCommand,
  copyClipsToClipboard,
  getClipboard,
  type TimelineCommand,
} from "@montage/timeline-engine";

export function buildAddClipFromMediaCommand(
  media: MediaItem,
  trackId: string,
  startMs: number,
): AddClipCommand {
  const durationMs = media.duration_ms ?? 5000;
  return new AddClipCommand({
    media_item_id: media.id,
    track_id: trackId,
    start_ms: startMs,
    source_in_ms: 0,
    source_out_ms: durationMs,
    name: media.file_name,
  });
}

export function buildMoveClipCommand(
  clipId: string,
  startMs: number,
  trackId?: string,
  snapEnabled?: boolean,
): MoveClipCommand {
  return new MoveClipCommand(clipId, startMs, trackId, snapEnabled ? {} : undefined);
}

export function buildSplitAtPlayheadCommand(
  clipId: string,
  playheadMs: number,
): SplitClipCommand {
  return new SplitClipCommand(clipId, playheadMs);
}

export function buildTrimClipCommand(
  clipId: string,
  updates: {
    start_ms?: number;
    end_ms?: number;
    source_in_ms?: number;
    source_out_ms?: number;
    ripple?: boolean;
  },
): TrimClipCommand {
  return new TrimClipCommand({ clipId, ...updates });
}

export function buildDeleteClipCommand(
  clipId: string,
  ripple: boolean,
): RemoveClipCommand | RippleDeleteClipCommand {
  return ripple
    ? new RippleDeleteClipCommand(clipId)
    : new RemoveClipCommand(clipId);
}

export function buildPasteCommand(
  trackId: string,
  startMs: number,
): PasteClipsCommand | null {
  const payload = getClipboard();
  if (!payload || payload.clips.length === 0) {
    return null;
  }
  const templates = payload.clips.map((clip) => ({
    media_item_id: clip.media_item_id,
    source_in_ms: clip.source_in_ms,
    source_out_ms: clip.source_out_ms,
    speed: clip.speed,
    opacity: clip.opacity,
    name: clip.name,
    timelineDurationMs: clip.end_ms - clip.start_ms,
  }));
  return new PasteClipsCommand(templates, trackId, startMs);
}

export function copyDocumentClips(document: TimelineDocument, clipIds: string[]) {
  const clips = document.tracks.flatMap((t) => t.clips).filter((c) => clipIds.includes(c.id));
  return copyClipsToClipboard(clips);
}

export type { TimelineCommand };
