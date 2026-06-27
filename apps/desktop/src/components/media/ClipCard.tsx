import { useEffect, useState } from "react";
import type { MediaItem, ProcessingStatus } from "@montage/shared-types";
import {
  formatDuration,
  formatFps,
  formatResolution,
  statusLabel,
} from "@/utils/media-format";
import { loadThumbnailSrc, type ThumbnailLoadState } from "@/utils/thumbnail-loader";

interface ClipCardProps {
  item: MediaItem;
  onToggleFavorite: () => void;
  onAddTag: (tag: string) => void;
  onRemoveTag: (tag: string) => void;
  onDelete: () => void;
}

function StatusBadge({ label, status }: { label: string; status: ProcessingStatus }) {
  const color =
    status === "ready"
      ? "text-green-400"
      : status === "processing"
        ? "text-yellow-400"
        : status === "error"
          ? "text-red-400"
          : "text-muted";
  return (
    <span className={`text-[10px] ${color}`}>
      {label}: {statusLabel(status)}
    </span>
  );
}

export function ClipCard({
  item,
  onToggleFavorite,
  onAddTag,
  onRemoveTag,
  onDelete,
}: ClipCardProps) {
  const [thumbnailSrc, setThumbnailSrc] = useState<string | null>(null);
  const [thumbnailState, setThumbnailState] = useState<ThumbnailLoadState>("idle");
  const isProcessing =
    item.import_status === "processing" || item.import_status === "pending";

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    const path = item.thumbnail_path?.trim() ?? "";

    setThumbnailSrc(null);
    setThumbnailState(path ? "loading" : "idle");

    if (!path) {
      return () => {
        cancelled = true;
      };
    }

    void loadThumbnailSrc(path, item.project_id, item.id)
      .then((src) => {
        if (cancelled) {
          if (src?.startsWith("blob:")) {
            URL.revokeObjectURL(src);
          }
          return;
        }
        if (src) {
          if (src.startsWith("blob:")) {
            objectUrl = src;
          }
          setThumbnailSrc(src);
          setThumbnailState("loaded");
          return;
        }
        setThumbnailState("failed");
      })
      .catch(() => {
        if (!cancelled) {
          setThumbnailState("failed");
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [item.thumbnail_path, item.id, item.project_id]);

  const handleThumbnailError = () => {
    setThumbnailSrc(null);
    setThumbnailState("failed");
  };

  const handleAddTag = () => {
    const tag = window.prompt("Add tag");
    if (tag) {
      onAddTag(tag);
    }
  };

  const placeholderText = (() => {
    if (isProcessing && !thumbnailSrc) {
      return "Processing…";
    }
    if (thumbnailState === "loading") {
      return "Loading…";
    }
    return "No thumbnail";
  })();

  return (
    <div
      className="bg-panel border border-border rounded-md overflow-hidden flex flex-col"
      draggable={item.import_status === "ready"}
      onDragStart={(e) => {
        if (item.import_status !== "ready") {
          e.preventDefault();
          return;
        }
        e.dataTransfer.setData("application/montage-media", JSON.stringify(item));
        e.dataTransfer.effectAllowed = "copy";
      }}
    >
      <div className="relative aspect-video bg-secondary">
        {thumbnailSrc ? (
          <img
            src={thumbnailSrc}
            alt={item.file_name}
            className="w-full h-full object-cover object-left"
            onError={handleThumbnailError}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-xs text-muted">
            {placeholderText}
          </div>
        )}
        <button
          type="button"
          className="absolute top-1 right-1 text-lg leading-none px-1"
          onClick={onToggleFavorite}
          title={item.is_favorite ? "Remove favorite" : "Add favorite"}
        >
          {item.is_favorite ? "★" : "☆"}
        </button>
      </div>

      <div className="p-2 flex flex-col gap-1 text-xs">
        <div className="font-medium truncate" title={item.file_name}>
          {item.file_name}
        </div>
        <div className="text-muted grid grid-cols-2 gap-x-2 gap-y-0.5">
          <span>Length: {formatDuration(item.duration_ms)}</span>
          <span>{formatResolution(item.width, item.height)}</span>
          <span>{formatFps(item.frame_rate)}</span>
          <span>{item.codec ?? "—"}</span>
        </div>
        <div className="flex flex-col gap-0.5 mt-1">
          <StatusBadge label="Proxy" status={item.proxy_status} />
          <StatusBadge label="Waveform" status={item.waveform_status} />
          <StatusBadge label="Scenes" status={item.scene_status} />
        </div>
        {item.storage_mode === "reference" && (
          <div className="text-[10px] text-muted truncate" title={item.source_path ?? item.file_path}>
            Reference: {item.source_path ?? item.file_path}
          </div>
        )}
        {item.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {item.tags.map((tag) => (
              <button
                key={tag}
                type="button"
                className="px-1.5 py-0.5 rounded bg-secondary border border-border text-[10px]"
                onClick={() => onRemoveTag(tag)}
                title="Click to remove tag"
              >
                {tag} ×
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-2 mt-2">
          <button type="button" className="btn-secondary text-[10px] py-1 px-2" onClick={handleAddTag}>
            Tag
          </button>
          <button type="button" className="btn-secondary text-[10px] py-1 px-2" onClick={onDelete}>
            Delete
          </button>
        </div>
        {item.error_message && (
          <div className="text-[10px] text-red-400 mt-1">{item.error_message}</div>
        )}
      </div>
    </div>
  );
}
