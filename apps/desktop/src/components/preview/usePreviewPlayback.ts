import { useEffect, useLayoutEffect, useRef } from "react";
import {
  activePlaybackClipRef,
  loadedPlaybackUrlRef,
  registerPlaybackVideoElement,
  stopPlayback,
  switchToNextClip,
  syncTimelinePlayheadFromSource,
} from "@/services/playback-controller";
import { usePlaybackStore } from "@/stores/playback-store";
import { useTimelineStore } from "@/stores/timeline-store";
import { watchVideoFrames } from "./video-playback";

const TIMELINE_SYNC_MS = 100;

export function usePreviewPlayback(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
) {
  const document = useTimelineStore((s) => s.document);
  const playheadMs = useTimelineStore((s) => s.playheadMs);
  const isPlaying = usePlaybackStore((s) => s.isPlaying);
  const quality = usePlaybackStore((s) => s.quality);
  const frameImage = usePlaybackStore((s) => s.frameImage);
  const useVideoSurface = usePlaybackStore((s) => s.useVideoSurface);
  const updateStats = usePlaybackStore((s) => s.updateStats);

  const statsRafRef = useRef<number | null>(null);
  const statsRef = useRef({ frames: 0, lastTs: 0, dropped: 0, videoFrames: 0, videoTs: 0 });
  const lastTimelineSyncRef = useRef(0);
  const documentRef = useRef(document);
  documentRef.current = document;

  useLayoutEffect(() => {
    registerPlaybackVideoElement(videoRef.current);
    return () => registerPlaybackVideoElement(null);
  });

  useEffect(() => {
    if (isPlaying || !document) {
      return;
    }
    void usePlaybackStore.getState().refreshStillFrame();
    void usePlaybackStore.getState().prefetchAroundPlayhead();
  }, [playheadMs, document, quality, isPlaying]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || useVideoSurface || !frameImage) {
      return;
    }
    const img = new Image();
    img.onload = () => {
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        return;
      }
      if (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
      }
      ctx.drawImage(img, 0, 0);
    };
    img.src = frameImage;
  }, [frameImage, useVideoSurface, canvasRef]);

  useEffect(() => {
    const video = videoRef.current;
    const doc = documentRef.current;
    if (!video || !doc || !isPlaying) {
      video?.pause();
      return;
    }

    statsRef.current.videoFrames = 0;
    statsRef.current.videoTs = performance.now();

    const onFrame = (mediaTimeSec: number) => {
      if (!usePlaybackStore.getState().isPlaying) {
        return;
      }
      const clip = activePlaybackClipRef.current;
      const activeDoc = documentRef.current;
      if (!clip || !activeDoc) {
        return;
      }

      const sourceMs = mediaTimeSec * 1000;
      if (sourceMs >= clip.source_out_ms - 32) {
        void switchToNextClip(video, activeDoc, clip).then((switched) => {
          if (!switched) {
            stopPlayback();
            useTimelineStore.getState().setPlayhead(activeDoc.duration_ms);
          }
        });
        return;
      }

      const now = performance.now();
      if (now - lastTimelineSyncRef.current >= TIMELINE_SYNC_MS) {
        syncTimelinePlayheadFromSource(clip, sourceMs);
        lastTimelineSyncRef.current = now;
      }

      statsRef.current.videoFrames += 1;
      const elapsed = now - statsRef.current.videoTs;
      if (elapsed >= 1000) {
        const fps = (statsRef.current.videoFrames * 1000) / elapsed;
        updateStats({
          playbackFps: Math.round(fps * 10) / 10,
        });
        statsRef.current.videoFrames = 0;
        statsRef.current.videoTs = now;
      }
    };

    return watchVideoFrames(video, onFrame);
  }, [isPlaying, videoRef, updateStats]);

  useEffect(() => {
    if (!isPlaying || !document) {
      if (statsRafRef.current !== null) {
        cancelAnimationFrame(statsRafRef.current);
        statsRafRef.current = null;
      }
      return;
    }

    const frameRate = document.settings.frame_rate;
    statsRef.current = { frames: 0, lastTs: performance.now(), dropped: 0, videoFrames: 0, videoTs: 0 };

    const tick = (now: number) => {
      if (!usePlaybackStore.getState().isPlaying) {
        return;
      }
      statsRef.current.frames += 1;
      const elapsed = now - statsRef.current.lastTs;
      if (elapsed >= 1000) {
        const expectedFrames = (elapsed / 1000) * frameRate;
        statsRef.current.dropped += Math.max(0, Math.round(expectedFrames - statsRef.current.frames));
        updateStats({ droppedFrames: statsRef.current.dropped });
        statsRef.current.frames = 0;
        statsRef.current.lastTs = now;
      }
      statsRafRef.current = requestAnimationFrame(tick);
    };
    statsRafRef.current = requestAnimationFrame(tick);

    return () => {
      if (statsRafRef.current !== null) {
        cancelAnimationFrame(statsRafRef.current);
        statsRafRef.current = null;
      }
    };
  }, [isPlaying, document?.id, updateStats]);

  useEffect(() => {
    loadedPlaybackUrlRef.current = null;
  }, [quality]);
}
