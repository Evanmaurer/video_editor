import type { TimelineClip } from "@montage/shared-types";
import {
  findNextVideoClip,
  resolveVideoFrameAtTime,
  snapToFrameMs,
  timelineMsFromSource,
} from "@montage/playback-engine";
import { useMediaStore } from "@/stores/media-store";
import { usePlaybackStore } from "@/stores/playback-store";
import { useTimelineStore } from "@/stores/timeline-store";
import { prepareVideoForPlayback } from "@/components/preview/video-playback";

export const activePlaybackClipRef: { current: TimelineClip | null } = { current: null };
export const loadedPlaybackUrlRef: { current: string | null } = { current: null };

let registeredVideo: HTMLVideoElement | null = null;

export function registerPlaybackVideoElement(video: HTMLVideoElement | null): void {
  registeredVideo = video;
}

export function getRegisteredPlaybackVideo(): HTMLVideoElement | null {
  return registeredVideo;
}

function resolvePlayheadForStart(): number {
  const document = useTimelineStore.getState().document;
  if (!document) {
    return 0;
  }
  const playheadMs = useTimelineStore.getState().playheadMs;
  const atPlayhead = resolveVideoFrameAtTime(document, playheadMs);
  if (atPlayhead) {
    return playheadMs;
  }
  const next = findNextVideoClip(document, playheadMs) ?? findNextVideoClip(document, 0);
  if (next) {
    useTimelineStore.getState().setPlayhead(next.timelineMs);
    return next.timelineMs;
  }
  return playheadMs;
}

export async function startPlayback(videoOverride?: HTMLVideoElement | null): Promise<void> {
  const document = useTimelineStore.getState().document;
  if (!document) {
    return;
  }

  const timelineMs = resolvePlayheadForStart();
  const mediaItems = useMediaStore.getState().items;
  const video = videoOverride ?? registeredVideo;

  if (!video) {
    usePlaybackStore.getState().setPlaybackError("Preview video element unavailable");
    return;
  }

  try {
    const prepared = await prepareVideoForPlayback(video, {
      document,
      mediaItems,
      timelineMs,
      loadedUrlRef: loadedPlaybackUrlRef,
    });

    if (!prepared) {
      throw new Error("No playable clip at playhead");
    }

    activePlaybackClipRef.current = prepared.clip;
    video.playbackRate = 1;
    usePlaybackStore.getState().markPlaying();
    await video.play();
  } catch (err) {
    video.pause();
    activePlaybackClipRef.current = null;
    usePlaybackStore.getState().pause();
    const message =
      err instanceof Error ? err.message : "Video playback failed — ensure proxy files are ready";
    usePlaybackStore.getState().setPlaybackError(message);
  }
}

export function stopPlayback(): void {
  registeredVideo?.pause();
  activePlaybackClipRef.current = null;
  usePlaybackStore.getState().pause();
}

export async function toggleTimelinePlayback(videoOverride?: HTMLVideoElement | null): Promise<void> {
  if (usePlaybackStore.getState().isPlaying) {
    stopPlayback();
    return;
  }
  await startPlayback(videoOverride);
}

export async function switchToNextClip(
  video: HTMLVideoElement,
  doc: NonNullable<ReturnType<typeof useTimelineStore.getState>["document"]>,
  afterClip: TimelineClip,
): Promise<boolean> {
  const next = findNextVideoClip(doc, afterClip.end_ms);
  if (!next) {
    return false;
  }
  const mediaItems = useMediaStore.getState().items;
  const media = mediaItems.find((item) => item.id === next.clip.media_item_id);
  if (!media) {
    return false;
  }
  const url = await window.montageAPI.getPlaybackVideoUrl(media.file_path, media.proxy_path);
  if (!url) {
    return false;
  }
  activePlaybackClipRef.current = next.clip;
  loadedPlaybackUrlRef.current = url;
  video.src = url;
  video.load();
  video.currentTime = next.sourceMs / 1000;
  useTimelineStore.getState().setPlayhead(next.timelineMs);
  void video.play();
  return true;
}

export function syncTimelinePlayheadFromSource(clip: TimelineClip, sourceMs: number): void {
  const timelineMs = timelineMsFromSource(clip, sourceMs);
  const document = useTimelineStore.getState().document;
  if (!document) {
    return;
  }
  const snapped = snapToFrameMs(timelineMs, document.settings.frame_rate);
  if (Math.abs(snapped - useTimelineStore.getState().playheadMs) >= 0.5) {
    useTimelineStore.getState().setPlayhead(snapped);
  }
}
