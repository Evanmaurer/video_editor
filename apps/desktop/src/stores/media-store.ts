import { create } from "zustand";
import type {
  ImportMediaResponse,
  MediaItem,
  MediaListParams,
  MediaSortField,
  MediaSortOrder,
  StorageMode,
} from "@montage/shared-types";
import { getApiClient } from "@/services/api-client";

interface MediaState {
  items: MediaItem[];
  isLoading: boolean;
  isImporting: boolean;
  error: string | null;
  search: string;
  sortBy: MediaSortField;
  sortOrder: MediaSortOrder;
  tagFilter: string;
  favoritesOnly: boolean;
  storageMode: StorageMode;
  viewMode: "grid" | "list";
  pollTimer: ReturnType<typeof setInterval> | null;
  setSearch: (search: string) => void;
  setSortBy: (sortBy: MediaSortField) => void;
  setSortOrder: (sortOrder: MediaSortOrder) => void;
  setTagFilter: (tag: string) => void;
  setFavoritesOnly: (value: boolean) => void;
  setStorageMode: (mode: StorageMode) => void;
  setViewMode: (mode: "grid" | "list") => void;
  loadMedia: (projectId: string) => Promise<void>;
  importPaths: (projectId: string, paths: string[]) => Promise<ImportMediaResponse>;
  importFolder: (projectId: string, folderPath: string) => Promise<ImportMediaResponse>;
  toggleFavorite: (projectId: string, item: MediaItem) => Promise<void>;
  addTag: (projectId: string, item: MediaItem, tag: string) => Promise<void>;
  removeTag: (projectId: string, item: MediaItem, tag: string) => Promise<void>;
  deleteItem: (projectId: string, mediaId: string) => Promise<void>;
  startPolling: (projectId: string) => void;
  stopPolling: () => void;
}

function listParams(state: MediaState): MediaListParams {
  const tags = state.tagFilter.trim() ? [state.tagFilter.trim()] : [];
  return {
    search: state.search.trim() || undefined,
    sort_by: state.sortBy,
    sort_order: state.sortOrder,
    tags,
    favorites_only: state.favoritesOnly,
  };
}

async function refreshAfterImport(
  projectId: string,
  get: () => MediaState,
): Promise<void> {
  await get().loadMedia(projectId);
  const hasProcessing = get().items.some(
    (item) => item.import_status === "processing" || item.import_status === "pending",
  );
  if (hasProcessing) {
    get().startPolling(projectId);
  }
}

export const useMediaStore = create<MediaState>((set, get) => ({
  items: [],
  isLoading: false,
  isImporting: false,
  error: null,
  search: "",
  sortBy: "created_at",
  sortOrder: "desc",
  tagFilter: "",
  favoritesOnly: false,
  storageMode: "copy",
  viewMode: "grid",
  pollTimer: null,

  setSearch: (search) => set({ search }),
  setSortBy: (sortBy) => set({ sortBy }),
  setSortOrder: (sortOrder) => set({ sortOrder }),
  setTagFilter: (tagFilter) => set({ tagFilter }),
  setFavoritesOnly: (favoritesOnly) => set({ favoritesOnly }),
  setStorageMode: (storageMode) => set({ storageMode }),
  setViewMode: (viewMode) => set({ viewMode }),

  loadMedia: async (projectId) => {
    set({ isLoading: true, error: null });
    try {
      const api = getApiClient();
      const items = await api.listMedia(projectId, listParams(get()));
      set({ items, isLoading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : String(err),
        isLoading: false,
      });
    }
  },

  importPaths: async (projectId, paths) => {
    if (paths.length === 0) {
      return { imported: [], skipped: [], duplicates: [] };
    }
    set({ isImporting: true, error: null });
    try {
      const api = getApiClient();
      const result = await api.importMedia(projectId, {
        paths,
        role: "clip",
        storage_mode: get().storageMode,
      });
      await refreshAfterImport(projectId, get);
      set({ isImporting: false });
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      set({ error: message, isImporting: false });
      throw err;
    }
  },

  importFolder: async (projectId, folderPath) => {
    set({ isImporting: true, error: null });
    try {
      const api = getApiClient();
      const result = await api.importFolder(projectId, {
        path: folderPath,
        role: "clip",
        storage_mode: get().storageMode,
      });
      await refreshAfterImport(projectId, get);
      set({ isImporting: false });
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      set({ error: message, isImporting: false });
      throw err;
    }
  },

  toggleFavorite: async (projectId, item) => {
    const api = getApiClient();
    await api.updateMedia(projectId, item.id, { is_favorite: !item.is_favorite });
    await get().loadMedia(projectId);
  },

  addTag: async (projectId, item, tag) => {
    const normalized = tag.trim();
    if (!normalized || item.tags.includes(normalized)) {
      return;
    }
    const api = getApiClient();
    await api.updateMedia(projectId, item.id, { tags: [...item.tags, normalized] });
    await get().loadMedia(projectId);
  },

  removeTag: async (projectId, item, tag) => {
    const api = getApiClient();
    await api.updateMedia(projectId, item.id, {
      tags: item.tags.filter((t) => t !== tag),
    });
    await get().loadMedia(projectId);
  },

  deleteItem: async (projectId, mediaId) => {
    const api = getApiClient();
    await api.deleteMedia(projectId, mediaId);
    await get().loadMedia(projectId);
  },

  startPolling: (projectId) => {
    const existing = get().pollTimer;
    if (existing) {
      clearInterval(existing);
    }
    const timer = setInterval(() => {
      void (async () => {
        await get().loadMedia(projectId);
        const hasProcessing = get().items.some(
          (item) => item.import_status === "processing" || item.import_status === "pending",
        );
        if (!hasProcessing) {
          get().stopPolling();
        }
      })();
    }, 2000);
    set({ pollTimer: timer });
  },

  stopPolling: () => {
    const timer = get().pollTimer;
    if (timer) {
      clearInterval(timer);
    }
    set({ pollTimer: null });
  },
}));
