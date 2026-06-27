import { useCallback, useEffect, useState } from "react";
import type { MediaSortField, MediaSortOrder } from "@montage/shared-types";
import { ClipCard } from "@/components/media/ClipCard";
import { useMediaStore } from "@/stores/media-store";
import { useProjectStore } from "@/stores/project-store";
import { collectDropPaths } from "@/utils/media-import";

export function MediaLibrary() {
  const project = useProjectStore((s) => s.project);
  const items = useMediaStore((s) => s.items);
  const isLoading = useMediaStore((s) => s.isLoading);
  const isImporting = useMediaStore((s) => s.isImporting);
  const error = useMediaStore((s) => s.error);
  const search = useMediaStore((s) => s.search);
  const sortBy = useMediaStore((s) => s.sortBy);
  const sortOrder = useMediaStore((s) => s.sortOrder);
  const tagFilter = useMediaStore((s) => s.tagFilter);
  const favoritesOnly = useMediaStore((s) => s.favoritesOnly);
  const storageMode = useMediaStore((s) => s.storageMode);
  const viewMode = useMediaStore((s) => s.viewMode);
  const loadMedia = useMediaStore((s) => s.loadMedia);
  const importPaths = useMediaStore((s) => s.importPaths);
  const importFolder = useMediaStore((s) => s.importFolder);
  const toggleFavorite = useMediaStore((s) => s.toggleFavorite);
  const addTag = useMediaStore((s) => s.addTag);
  const removeTag = useMediaStore((s) => s.removeTag);
  const deleteItem = useMediaStore((s) => s.deleteItem);
  const startPolling = useMediaStore((s) => s.startPolling);
  const stopPolling = useMediaStore((s) => s.stopPolling);
  const setSearch = useMediaStore((s) => s.setSearch);
  const setSortBy = useMediaStore((s) => s.setSortBy);
  const setSortOrder = useMediaStore((s) => s.setSortOrder);
  const setTagFilter = useMediaStore((s) => s.setTagFilter);
  const setFavoritesOnly = useMediaStore((s) => s.setFavoritesOnly);
  const setStorageMode = useMediaStore((s) => s.setStorageMode);
  const setViewMode = useMediaStore((s) => s.setViewMode);

  const [isDragging, setIsDragging] = useState(false);
  const [importMessage, setImportMessage] = useState<string | null>(null);

  const projectId = project?.id;

  const refresh = useCallback(() => {
    if (projectId) {
      void loadMedia(projectId);
    }
  }, [projectId, loadMedia]);

  useEffect(() => {
    if (!projectId) {
      return;
    }
    void loadMedia(projectId);
    return () => stopPolling();
  }, [projectId, loadMedia, stopPolling, search, sortBy, sortOrder, tagFilter, favoritesOnly]);

  useEffect(() => {
    if (!projectId) {
      return;
    }
    const processing = items.some(
      (item) => item.import_status === "processing" || item.import_status === "pending",
    );
    if (processing) {
      startPolling(projectId);
    }
  }, [items, projectId, startPolling]);

  const handleImportFiles = async () => {
    if (!projectId) {
      return;
    }
    try {
      const paths = await window.montageAPI.openVideoFiles();
      if (paths.length === 0) {
        return;
      }
      const result = await importPaths(projectId, paths);
      const count = result.imported.length;
      if (count > 0) {
        setImportMessage(`Imported ${count} clip${count === 1 ? "" : "s"}`);
      } else if (result.duplicates.length > 0) {
        setImportMessage("Duplicate files skipped");
      }
    } catch {
      // store.error is set by importPaths
    }
  };

  const handleImportFolder = async () => {
    if (!projectId) {
      return;
    }
    try {
      const folderPath = await window.montageAPI.importVideoFolder();
      if (!folderPath) {
        return;
      }
      const result = await importFolder(projectId, folderPath);
      const count = result.imported.length;
      if (count > 0) {
        setImportMessage(`Imported ${count} clip${count === 1 ? "" : "s"} from folder`);
      } else {
        setImportMessage("No video files found in folder");
      }
    } catch {
      // store.error is set by importFolder
    }
  };

  const onDrop = async (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(false);
    if (!projectId) {
      return;
    }

    try {
      const rawPaths = collectDropPaths(
        Array.from(event.dataTransfer.files),
        (file) => window.montageAPI.getPathForFile(file),
      );
      if (rawPaths.length === 0) {
        setImportMessage("No importable files in drop");
        return;
      }

      const paths = await window.montageAPI.resolveImportPaths(rawPaths);
      if (paths.length === 0) {
        setImportMessage("No video files found in drop");
        return;
      }

      const result = await importPaths(projectId, paths);
      const count = result.imported.length;
      if (count > 0) {
        setImportMessage(`Imported ${count} clip${count === 1 ? "" : "s"}`);
      }
    } catch {
      // store.error is set by importPaths
    }
  };

  if (!projectId) {
    return null;
  }

  return (
    <div
      className={`h-full flex flex-col bg-secondary border-r border-border ${isDragging ? "ring-2 ring-accent ring-inset" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => void onDrop(e)}
    >
      <div className="px-3 py-2 border-b border-border space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium">Media Library</span>
          <div className="flex gap-1">
            <button
              type="button"
              className={`text-xs px-2 py-1 rounded ${viewMode === "grid" ? "bg-accent text-white" : "bg-panel border border-border"}`}
              onClick={() => setViewMode("grid")}
            >
              Grid
            </button>
            <button
              type="button"
              className={`text-xs px-2 py-1 rounded ${viewMode === "list" ? "bg-accent text-white" : "bg-panel border border-border"}`}
              onClick={() => setViewMode("list")}
            >
              List
            </button>
          </div>
        </div>

        <input
          className="input-field text-xs"
          placeholder="Search clips…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <div className="flex gap-1 flex-wrap">
          <select
            className="input-field text-xs flex-1 min-w-0"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as MediaSortField)}
          >
            <option value="created_at">Date added</option>
            <option value="name">Name</option>
            <option value="duration">Duration</option>
            <option value="favorite">Favorites</option>
          </select>
          <select
            className="input-field text-xs w-20"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as MediaSortOrder)}
          >
            <option value="desc">Desc</option>
            <option value="asc">Asc</option>
          </select>
        </div>

        <div className="flex gap-1 items-center">
          <input
            className="input-field text-xs flex-1"
            placeholder="Filter by tag"
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
          />
          <label className="text-xs flex items-center gap-1 whitespace-nowrap">
            <input
              type="checkbox"
              checked={favoritesOnly}
              onChange={(e) => setFavoritesOnly(e.target.checked)}
            />
            ★
          </label>
        </div>

        <div className="flex gap-1 items-center text-xs">
          <label className="text-muted">Import:</label>
          <select
            className="input-field text-xs flex-1"
            value={storageMode}
            onChange={(e) => setStorageMode(e.target.value as "copy" | "reference")}
          >
            <option value="copy">Copy into project</option>
            <option value="reference">Reference original</option>
          </select>
        </div>

        <div className="flex gap-1">
          <button
            type="button"
            className="btn-primary text-xs flex-1 py-1.5"
            disabled={isImporting}
            onClick={() => void handleImportFiles()}
          >
            {isImporting ? "Importing…" : "Import Files"}
          </button>
          <button
            type="button"
            className="btn-secondary text-xs flex-1 py-1.5"
            disabled={isImporting}
            onClick={() => void handleImportFolder()}
          >
            Import Folder
          </button>
        </div>
      </div>

      {error && (
        <div className="px-3 py-2 text-xs text-red-400 border-b border-border">{error}</div>
      )}
      {importMessage && !error && (
        <div className="px-3 py-2 text-xs text-green-400 border-b border-border">{importMessage}</div>
      )}

      <div className="flex-1 min-h-0 overflow-auto p-2">
        {isLoading && items.length === 0 ? (
          <div className="panel-empty">Loading media…</div>
        ) : items.length === 0 ? (
          <div className="panel-empty">
            <p>Drop video files here or use Import</p>
            <p className="text-xs text-muted">Supports multi-file and folder import</p>
          </div>
        ) : viewMode === "grid" ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
            {items.map((item) => (
              <ClipCard
                key={item.id}
                item={item}
                onToggleFavorite={() => void toggleFavorite(projectId, item)}
                onAddTag={(tag) => void addTag(projectId, item, tag)}
                onRemoveTag={(tag) => void removeTag(projectId, item, tag)}
                onDelete={() => void deleteItem(projectId, item.id)}
              />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {items.map((item) => (
              <ClipCard
                key={item.id}
                item={item}
                onToggleFavorite={() => void toggleFavorite(projectId, item)}
                onAddTag={(tag) => void addTag(projectId, item, tag)}
                onRemoveTag={(tag) => void removeTag(projectId, item, tag)}
                onDelete={() => void deleteItem(projectId, item.id)}
              />
            ))}
          </div>
        )}
      </div>

      <div className="px-3 py-1.5 border-t border-border text-[10px] text-muted flex justify-between">
        <span>{items.length} clip{items.length === 1 ? "" : "s"}</span>
        <button type="button" className="hover:text-foreground" onClick={refresh}>
          Refresh
        </button>
      </div>
    </div>
  );
}
