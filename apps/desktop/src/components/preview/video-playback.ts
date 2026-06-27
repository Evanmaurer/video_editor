import type { TimelineClip, TimelineDocument } from "@montage/shared-types";
import type { MediaItem } from "@montage/shared-types";
import { resolveVideoFrameAtTime } from "@montage/playback-engine";

function waitForVideoReady(video: HTMLVideoElement, timeoutMs = 10000): Promise<void> {
  if (video.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      cleanup();
      reject(new Error(video.error?.message ?? "Video load timed out"));
    }, timeoutMs);

    const onReady = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error(video.error?.message ?? "The element has no supported sources."));
    };
    const cleanup = () => {
      window.clearTimeout(timer);
      video.removeEventListener("loadeddata", onReady);
      video.removeEventListener("canplay", onReady);
      video.removeEventListener("error", onError);
    };

    video.addEventListener("loadeddata", onReady, { once: true });
    video.addEventListener("canplay", onReady, { once: true });
    video.addEventListener("error", onError, { once: true });
  });
}

async function resolvePlaybackUrl(media: MediaItem): Promise<string | null> {
  return window.montageAPI.getPlaybackVideoUrl(media.file_path, media.proxy_path);
}

export async function prepareVideoForPlayback(
  video: HTMLVideoElement,
  options: {
    document: TimelineDocument;
    mediaItems: MediaItem[];
    timelineMs: number;
    loadedUrlRef: { current: string | null };
  },
): Promise<{ clip: TimelineClip; sourceMs: number } | null> {
  const { document, mediaItems, timelineMs, loadedUrlRef } = options;
  const resolved = resolveVideoFrameAtTime(document, timelineMs);
  if (!resolved) {
    return null;
  }

  const media = mediaItems.find((item) => item.id === resolved.clip.media_item_id);
  if (!media) {
    return null;
  }

  const url = await resolvePlaybackUrl(media);
  if (!url) {
    throw new Error("No playable video file found — wait for proxy generation to finish");
  }

  if (loadedUrlRef.current !== url) {
    video.preload = "auto";
    video.src = url;
    loadedUrlRef.current = url;
    video.load();
    await waitForVideoReady(video);
  } else if (video.readyState < HTMLMediaElement.HAVE_FUTURE_DATA) {
    await waitForVideoReady(video);
  }

  const targetSec = resolved.sourceMs / 1000;
  if (Math.abs(video.currentTime - targetSec) > 0.05) {
    video.currentTime = targetSec;
  }

  return { clip: resolved.clip, sourceMs: resolved.sourceMs };
}

type VideoWithFrameCallback = HTMLVideoElement & {
  requestVideoFrameCallback?: (
    callback: (now: DOMHighResTimeStamp, metadata: VideoFrameCallbackMetadata) => void,
  ) => number;
  cancelVideoFrameCallback?: (handle: number) => void;
};

export function watchVideoFrames(
  video: HTMLVideoElement,
  onFrame: (mediaTimeSec: number) => void,
): () => void {
  const videoEl = video as VideoWithFrameCallback;
  if (typeof videoEl.requestVideoFrameCallback === "function") {
    let handle = 0;
    let stopped = false;

    const tick = (_now: DOMHighResTimeStamp, metadata: VideoFrameCallbackMetadata) => {
      if (stopped) {
        return;
      }
      onFrame(metadata.mediaTime);
      handle = videoEl.requestVideoFrameCallback!(tick);
    };

    handle = videoEl.requestVideoFrameCallback!(tick);
    return () => {
      stopped = true;
      videoEl.cancelVideoFrameCallback?.(handle);
    };
  }

  let lastTime = -1;
  const onTimeUpdate = () => {
    if (Math.abs(video.currentTime - lastTime) > 0.0001) {
      lastTime = video.currentTime;
      onFrame(video.currentTime);
    }
  };
  video.addEventListener("timeupdate", onTimeUpdate);
  return () => video.removeEventListener("timeupdate", onTimeUpdate);
}
