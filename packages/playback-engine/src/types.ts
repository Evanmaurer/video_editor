import type { TimelineClip, TimelineTrack } from "@montage/shared-types";

export type PlaybackQuality = "proxy" | "full";

export interface ResolvedVideoFrame {
  clip: TimelineClip;
  track: TimelineTrack;
  timelineMs: number;
  sourceMs: number;
}

export interface PlaybackStats {
  playbackFps: number;
  droppedFrames: number;
  decodeTimeMs: number;
  memoryUsageMb: number;
  gpuAccelerated: boolean;
  cacheHitRate: number;
}

export const EMPTY_PLAYBACK_STATS: PlaybackStats = {
  playbackFps: 0,
  droppedFrames: 0,
  decodeTimeMs: 0,
  memoryUsageMb: 0,
  gpuAccelerated: false,
  cacheHitRate: 0,
};
