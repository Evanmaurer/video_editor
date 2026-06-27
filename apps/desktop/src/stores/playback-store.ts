import { create } from "zustand";
import type { MediaItem } from "@montage/shared-types";
import {
  EMPTY_PLAYBACK_STATS,
  resolveVideoFrameAtTime,
  snapToFrameMs,
  type PlaybackQuality,
  type PlaybackStats,
} from "@montage/playback-engine";
import { getApiClient } from "@/services/api-client";
import {
  clearFrameCache,
  frameCacheKey,
  getCachedFrame,
  putCachedFrame,
} from "@/services/playback-frame-cache";
import { toggleTimelinePlayback } from "@/services/playback-controller";
import { useMediaStore } from "@/stores/media-store";
import { useTimelineStore } from "@/stores/timeline-store";

interface PlaybackState {
  isPlaying: boolean;
  quality: PlaybackQuality;
  stats: PlaybackStats;
  frameImage: string | null;
  useVideoSurface: boolean;
  playbackError: string | null;
  projectId: string | null;

  setProjectId: (projectId: string | null) => void;
  setQuality: (quality: PlaybackQuality) => void;
  setPlaybackError: (message: string | null) => void;
  markPlaying: () => void;
  togglePlay: () => void;
  play: () => void;
  pause: () => void;
  stepFrame: (delta: number) => void;
  seekTimeline: (timelineMs: number) => Promise<void>;
  refreshStillFrame: () => Promise<void>;
  prefetchAroundPlayhead: () => Promise<void>;
  prefetchAhead: (frameCount?: number) => Promise<void>;
  updateStats: (partial: Partial<PlaybackStats>) => void;
  reportMetrics: () => Promise<void>;
  reset: () => void;
}

let metricsTimer: ReturnType<typeof setInterval> | null = null;
let stillFrameInFlight = false;
let lastMetricsPostAt = 0;
const METRICS_INTERVAL_MS = 5000;

function getFrameRate(): number {
  return useTimelineStore.getState().document?.settings.frame_rate ?? 60;
}

function getMediaPath(item: MediaItem | undefined, quality: PlaybackQuality): string | null {
  if (!item) {
    return null;
  }
  if (quality === "full") {
    return item.file_path;
  }
  return item.proxy_path ?? item.file_path;
}

/** Always prefer proxy for HTML5 video — full-res is for scrub/export decode only. */
export function getRealtimeVideoPath(item: MediaItem | undefined): string | null {
  if (!item) {
    return null;
  }
  return item.proxy_path ?? item.file_path;
}

export const usePlaybackStore = create<PlaybackState>((set, get) => ({
  isPlaying: false,
  quality: "proxy",
  stats: { ...EMPTY_PLAYBACK_STATS },
  frameImage: null,
  useVideoSurface: false,
  playbackError: null,
  projectId: null,

  setProjectId: (projectId) => {
    if (get().projectId === projectId) {
      return;
    }
    get().reset();
    set({ projectId });
    if (projectId && !metricsTimer) {
      metricsTimer = setInterval(() => {
        void get().reportMetrics();
      }, METRICS_INTERVAL_MS);
    }
  },

  setQuality: (quality) => {
    set({ quality, useVideoSurface: false, frameImage: null, playbackError: null });
    get().pause();
    void get().refreshStillFrame();
  },

  setPlaybackError: (message) => set({ playbackError: message }),

  markPlaying: () =>
    set({
      isPlaying: true,
      useVideoSurface: true,
      frameImage: null,
      playbackError: null,
    }),

  togglePlay: () => {
    void toggleTimelinePlayback();
  },

  play: () => {
    void toggleTimelinePlayback();
  },

  pause: () =>
    set({
      isPlaying: false,
      useVideoSurface: false,
    }),

  stepFrame: (delta) => {
    const document = useTimelineStore.getState().document;
    if (!document) {
      return;
    }
    const frameRate = getFrameRate();
    const frameMs = 1000 / frameRate;
    const next = snapToFrameMs(useTimelineStore.getState().playheadMs + delta * frameMs, frameRate);
    void get().seekTimeline(next);
  },

  seekTimeline: async (timelineMs) => {
    get().pause();
    const document = useTimelineStore.getState().document;
    const frameRate = document?.settings.frame_rate ?? 60;
    const snapped = snapToFrameMs(Math.max(0, timelineMs), frameRate);
    useTimelineStore.getState().setPlayhead(snapped);
    await get().refreshStillFrame();
    void get().prefetchAroundPlayhead();
  },

  refreshStillFrame: async () => {
    if (get().isPlaying) {
      return;
    }
    if (stillFrameInFlight) {
      return;
    }
    stillFrameInFlight = true;

    try {
      const { projectId, quality } = get();
      const document = useTimelineStore.getState().document;
      const mediaItems = useMediaStore.getState().items;
      if (!projectId || !document) {
        set({ frameImage: null });
        return;
      }

      const playheadMs = useTimelineStore.getState().playheadMs;
      const resolved = resolveVideoFrameAtTime(document, playheadMs);
      if (!resolved) {
        set({ frameImage: null });
        return;
      }

      const media = mediaItems.find((item) => item.id === resolved.clip.media_item_id);
      const path = getMediaPath(media, quality);
      if (!path) {
        set({ frameImage: null });
        return;
      }

      const sourceMs = Math.round(resolved.sourceMs);
      const cacheKey = frameCacheKey(resolved.clip.media_item_id, sourceMs, quality);
      const cached = getCachedFrame(cacheKey);
      if (cached) {
        set({
          frameImage: cached,
          stats: {
            ...get().stats,
            decodeTimeMs: 0,
            cacheHitRate: 1,
          },
        });
        return;
      }

      const api = getApiClient();
      const frameRate = document.settings.frame_rate;
      const result = await api.decodePlaybackFrame(projectId, {
        media_id: resolved.clip.media_item_id,
        source_ms: sourceMs,
        frame_rate: frameRate,
        quality,
      });
      const dataUrl = `data:image/jpeg;base64,${result.image_base64}`;
      putCachedFrame(cacheKey, dataUrl);
      set({
        frameImage: dataUrl,
        stats: {
          ...get().stats,
          decodeTimeMs: result.decode_time_ms,
          gpuAccelerated: result.gpu_accelerated,
          cacheHitRate: result.cache_hit ? 1 : get().stats.cacheHitRate,
        },
      });
    } catch {
      set({ frameImage: null });
    } finally {
      stillFrameInFlight = false;
    }
  },

  prefetchAhead: async (frameCount = 8) => {
    if (get().isPlaying) {
      return;
    }
    const { projectId, quality } = get();
    const document = useTimelineStore.getState().document;
    if (!projectId || !document) {
      return;
    }
    const playheadMs = useTimelineStore.getState().playheadMs;
    const resolved = resolveVideoFrameAtTime(document, playheadMs);
    if (!resolved) {
      return;
    }
    const frameRate = document.settings.frame_rate;
    const frameMs = 1000 / frameRate;
    const requests = [];
    for (let i = 1; i <= frameCount; i += 1) {
      requests.push({
        media_id: resolved.clip.media_item_id,
        source_ms: Math.max(0, Math.round(resolved.sourceMs + i * frameMs)),
        quality,
      });
    }
    const api = getApiClient();
    await api.prefetchPlaybackFrames(projectId, {
      frame_rate: frameRate,
      requests,
    });
  },

  prefetchAroundPlayhead: async () => {
    if (get().isPlaying) {
      return;
    }
    const { projectId, quality } = get();
    const document = useTimelineStore.getState().document;
    if (!projectId || !document) {
      return;
    }
    const playheadMs = useTimelineStore.getState().playheadMs;
    const resolved = resolveVideoFrameAtTime(document, playheadMs);
    if (!resolved) {
      return;
    }
    const frameRate = document.settings.frame_rate;
    const frameMs = 1000 / frameRate;
    const offsets = [-2, -1, 1, 2].map((n) =>
      Math.max(0, Math.round(resolved.sourceMs + n * frameMs)),
    );
    const api = getApiClient();
    await api.prefetchPlaybackFrames(projectId, {
      frame_rate: frameRate,
      requests: offsets.map((source_ms) => ({
        media_id: resolved.clip.media_item_id,
        source_ms,
        quality,
      })),
    });
  },

  updateStats: (partial) => set((s) => ({ stats: { ...s.stats, ...partial } })),

  reportMetrics: async () => {
    const { projectId, stats, isPlaying } = get();
    if (!projectId) {
      return;
    }
    const now = Date.now();
    if (isPlaying && now - lastMetricsPostAt < METRICS_INTERVAL_MS) {
      return;
    }
    lastMetricsPostAt = now;
    try {
      const api = getApiClient();
      const server = await api.reportPlaybackMetrics(projectId, {
        playback_fps: stats.playbackFps,
        dropped_frames: stats.droppedFrames,
      });
      set({
        stats: {
          playbackFps: server.playback_fps,
          droppedFrames: server.dropped_frames,
          decodeTimeMs: server.decode_time_ms,
          memoryUsageMb: server.memory_usage_mb,
          gpuAccelerated: server.gpu_accelerated,
          cacheHitRate: server.cache_hit_rate,
        },
      });
    } catch {
      // metrics are best-effort
    }
  },

  reset: () => {
    if (metricsTimer) {
      clearInterval(metricsTimer);
      metricsTimer = null;
    }
    stillFrameInFlight = false;
    lastMetricsPostAt = 0;
    clearFrameCache();
    set({
      isPlaying: false,
      quality: "proxy",
      stats: { ...EMPTY_PLAYBACK_STATS },
      frameImage: null,
      useVideoSurface: false,
      playbackError: null,
      projectId: null,
    });
  },
}));

export function getPlaybackMediaPath(
  items: MediaItem[],
  mediaId: string,
  quality: PlaybackQuality,
): string | null {
  const item = items.find((m) => m.id === mediaId);
  return getMediaPath(item, quality);
}
