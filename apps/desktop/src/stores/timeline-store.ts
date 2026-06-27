import { create } from "zustand";
import type { TimelineClip, TimelineDocument } from "@montage/shared-types";
import {
  TimelineEngine,
  findClip,
  type TimelineCommand,
} from "@montage/timeline-engine";
import { getApiClient } from "@/services/api-client";
import {
  buildDeleteClipCommand,
  buildPasteCommand,
  buildSplitAtPlayheadCommand,
  copyDocumentClips,
} from "@/services/timeline-actions";

const AUTOSAVE_DELAY_MS = 2000;
const MIN_ZOOM = 0.25;
const MAX_ZOOM = 8;

interface TimelineState {
  engine: TimelineEngine | null;
  document: TimelineDocument | null;
  projectId: string | null;
  playheadMs: number;
  zoom: number;
  snapEnabled: boolean;
  rippleEnabled: boolean;
  selectedClipIds: string[];
  canUndo: boolean;
  canRedo: boolean;
  isLoading: boolean;
  isSaving: boolean;
  saveError: string | null;
  lastSavedAt: string | null;

  loadTimeline: (projectId: string) => Promise<void>;
  execute: (command: TimelineCommand) => boolean;
  undo: () => void;
  redo: () => void;
  setPlayhead: (ms: number) => void;
  setZoom: (zoom: number) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  toggleSnap: () => void;
  toggleRipple: () => void;
  selectClip: (clipId: string | null, additive?: boolean) => void;
  clearSelection: () => void;
  splitAtPlayhead: () => boolean;
  deleteSelected: () => void;
  copySelected: () => void;
  cutSelected: () => void;
  pasteAtPlayhead: (trackId: string) => void;
  flushSave: () => Promise<void>;
  reset: () => void;
}

let autosaveTimer: ReturnType<typeof setTimeout> | null = null;
let pendingSave = false;
let loadGeneration = 0;

function syncFromEngine(
  engine: TimelineEngine,
  set: (partial: Partial<TimelineState>) => void,
) {
  set({
    document: engine.getDocument(),
    canUndo: engine.canUndo(),
    canRedo: engine.canRedo(),
  });
}

function scheduleAutosave(get: () => TimelineState) {
  if (autosaveTimer) {
    clearTimeout(autosaveTimer);
  }
  autosaveTimer = setTimeout(() => {
    void get().flushSave();
  }, AUTOSAVE_DELAY_MS);
}

function resolveSplitTimeMs(
  document: TimelineDocument,
  clipId: string,
  playheadMs: number,
): number | null {
  const located = findClip(document, clipId);
  if (!located) {
    return null;
  }
  const { clip } = located;
  const duration = clip.end_ms - clip.start_ms;
  if (duration <= 1) {
    return null;
  }

  if (playheadMs > clip.start_ms && playheadMs < clip.end_ms) {
    return playheadMs;
  }

  return clip.start_ms + duration / 2;
}

export const useTimelineStore = create<TimelineState>((set, get) => ({
  engine: null,
  document: null,
  projectId: null,
  playheadMs: 0,
  zoom: 1,
  snapEnabled: true,
  rippleEnabled: false,
  selectedClipIds: [],
  canUndo: false,
  canRedo: false,
  isLoading: false,
  isSaving: false,
  saveError: null,
  lastSavedAt: null,

  loadTimeline: async (projectId) => {
    const generation = ++loadGeneration;
    set({ isLoading: true, saveError: null, projectId });
    try {
      const api = getApiClient();
      const doc = await api.getActiveTimeline(projectId);
      if (generation !== loadGeneration) {
        return;
      }

      const engine = TimelineEngine.fromDocument(doc as TimelineDocument);
      engine.onChange((updated) => {
        if (generation !== loadGeneration) {
          return;
        }
        set({
          document: updated,
          canUndo: engine.canUndo(),
          canRedo: engine.canRedo(),
        });
        scheduleAutosave(get);
      });
      set({
        engine,
        document: engine.getDocument(),
        canUndo: false,
        canRedo: false,
        isLoading: false,
        playheadMs: 0,
        selectedClipIds: [],
      });
    } catch (err) {
      if (generation !== loadGeneration) {
        return;
      }
      set({
        isLoading: false,
        saveError: err instanceof Error ? err.message : String(err),
      });
    }
  },

  execute: (command) => {
    const { engine } = get();
    if (!engine) {
      return false;
    }
    const applied = engine.execute(command);
    if (applied) {
      syncFromEngine(engine, set);
      scheduleAutosave(get);
    }
    return applied;
  },

  undo: () => {
    const { engine } = get();
    if (!engine?.undo()) {
      return;
    }
    syncFromEngine(engine, set);
    scheduleAutosave(get);
  },

  redo: () => {
    const { engine } = get();
    if (!engine?.redo()) {
      return;
    }
    syncFromEngine(engine, set);
    scheduleAutosave(get);
  },

  setPlayhead: (ms) => set({ playheadMs: Math.max(0, ms) }),

  setZoom: (zoom) =>
    set({ zoom: Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom)) }),

  zoomIn: () => {
    const { zoom } = get();
    set({ zoom: Math.min(MAX_ZOOM, zoom * 1.25) });
  },

  zoomOut: () => {
    const { zoom } = get();
    set({ zoom: Math.max(MIN_ZOOM, zoom / 1.25) });
  },

  toggleSnap: () => set((s) => ({ snapEnabled: !s.snapEnabled })),

  toggleRipple: () => set((s) => ({ rippleEnabled: !s.rippleEnabled })),

  selectClip: (clipId, additive = false) => {
    if (!clipId) {
      set({ selectedClipIds: [] });
      return;
    }
    set((s) => ({
      selectedClipIds: additive
        ? s.selectedClipIds.includes(clipId)
          ? s.selectedClipIds.filter((id) => id !== clipId)
          : [...s.selectedClipIds, clipId]
        : [clipId],
    }));
  },

  clearSelection: () => set({ selectedClipIds: [] }),

  splitAtPlayhead: () => {
    const { engine, document, playheadMs, selectedClipIds } = get();
    if (!engine || !document) {
      return false;
    }
    const targetId =
      selectedClipIds[0] ??
      document.tracks
        .flatMap((t) => t.clips)
        .find((c) => playheadMs >= c.start_ms && playheadMs < c.end_ms)?.id;
    if (!targetId) {
      return false;
    }

    const splitMs = resolveSplitTimeMs(document, targetId, playheadMs);
    if (splitMs === null) {
      return false;
    }

    const applied = engine.execute(buildSplitAtPlayheadCommand(targetId, splitMs));
    if (applied) {
      syncFromEngine(engine, set);
      scheduleAutosave(get);
    }
    return applied;
  },

  deleteSelected: () => {
    const { engine, rippleEnabled, selectedClipIds } = get();
    if (!engine || selectedClipIds.length === 0) {
      return;
    }
    for (const clipId of selectedClipIds) {
      engine.execute(buildDeleteClipCommand(clipId, rippleEnabled));
    }
    set({ selectedClipIds: [] });
    syncFromEngine(engine, set);
    scheduleAutosave(get);
  },

  copySelected: () => {
    const { document, selectedClipIds } = get();
    if (!document || selectedClipIds.length === 0) {
      return;
    }
    copyDocumentClips(document, selectedClipIds);
  },

  cutSelected: () => {
    get().copySelected();
    get().deleteSelected();
  },

  pasteAtPlayhead: (trackId) => {
    const { engine, playheadMs } = get();
    if (!engine) {
      return;
    }
    const command = buildPasteCommand(trackId, playheadMs);
    if (!command) {
      return;
    }
    const applied = engine.execute(command);
    if (applied) {
      syncFromEngine(engine, set);
      scheduleAutosave(get);
    }
  },

  flushSave: async () => {
    const { document, projectId, isSaving } = get();
    if (!document || !projectId || isSaving) {
      pendingSave = Boolean(document && projectId);
      return;
    }
    set({ isSaving: true, saveError: null });
    try {
      const api = getApiClient();
      const result = await api.saveTimeline(projectId, document.id, document);
      set({
        isSaving: false,
        lastSavedAt: result.updated_at,
        document: { ...document, version: result.version, updated_at: result.updated_at },
      });
      if (pendingSave) {
        pendingSave = false;
        scheduleAutosave(get);
      }
    } catch (err) {
      set({
        isSaving: false,
        saveError: err instanceof Error ? err.message : String(err),
      });
    }
  },

  reset: () => {
    loadGeneration += 1;
    if (autosaveTimer) {
      clearTimeout(autosaveTimer);
      autosaveTimer = null;
    }
    set({
      engine: null,
      document: null,
      projectId: null,
      playheadMs: 0,
      selectedClipIds: [],
      canUndo: false,
      canRedo: false,
      isLoading: false,
      isSaving: false,
      saveError: null,
      lastSavedAt: null,
    });
  },
}));

export function getSelectedClips(document: TimelineDocument, ids: string[]): TimelineClip[] {
  return document.tracks.flatMap((t) => t.clips).filter((c) => ids.includes(c.id));
}

export function findClipTrackId(document: TimelineDocument, clipId: string): string | null {
  return findClip(document, clipId)?.track.id ?? null;
}
