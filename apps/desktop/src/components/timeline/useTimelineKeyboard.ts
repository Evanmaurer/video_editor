import { useEffect } from "react";
import { usePlaybackStore } from "@/stores/playback-store";
import { useTimelineStore } from "@/stores/timeline-store";

function isTypingInFormField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return Boolean(
    target.closest("input, textarea, select, [contenteditable='true'], [contenteditable='']"),
  );
}

export function useTimelineKeyboard() {
  const undo = useTimelineStore((s) => s.undo);
  const redo = useTimelineStore((s) => s.redo);
  const splitAtPlayhead = useTimelineStore((s) => s.splitAtPlayhead);
  const deleteSelected = useTimelineStore((s) => s.deleteSelected);
  const copySelected = useTimelineStore((s) => s.copySelected);
  const cutSelected = useTimelineStore((s) => s.cutSelected);
  const document = useTimelineStore((s) => s.document);
  const selectedClipIds = useTimelineStore((s) => s.selectedClipIds);
  const playheadMs = useTimelineStore((s) => s.playheadMs);
  const pasteAtPlayhead = useTimelineStore((s) => s.pasteAtPlayhead);
  const togglePlay = usePlaybackStore((s) => s.togglePlay);
  const stepFrame = usePlaybackStore((s) => s.stepFrame);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (isTypingInFormField(e.target)) {
        return;
      }

      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
        return;
      }
      if (mod && (e.key === "Z" || (e.key === "z" && e.shiftKey))) {
        e.preventDefault();
        redo();
        return;
      }
      if (mod && e.key === "c") {
        copySelected();
        return;
      }
      if (mod && e.key === "x") {
        e.preventDefault();
        cutSelected();
        return;
      }
      if (mod && e.key === "v" && document) {
        e.preventDefault();
        const trackId =
          document.tracks.find((t) => t.type === "video")?.id ?? document.tracks[0]?.id;
        if (trackId) {
          pasteAtPlayhead(trackId);
        }
        return;
      }
      if (e.key === "s" || e.key === "S") {
        if (!mod) {
          e.preventDefault();
          splitAtPlayhead();
        }
        return;
      }
      if (e.key === " " && !mod) {
        e.preventDefault();
        togglePlay();
        return;
      }
      if (e.key === "ArrowLeft" && !mod) {
        e.preventDefault();
        stepFrame(-1);
        return;
      }
      if (e.key === "ArrowRight" && !mod) {
        e.preventDefault();
        stepFrame(1);
        return;
      }
      if (e.key === "Backspace" || e.key === "Delete") {
        if (selectedClipIds.length > 0) {
          e.preventDefault();
          deleteSelected();
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    undo,
    redo,
    splitAtPlayhead,
    deleteSelected,
    copySelected,
    cutSelected,
    pasteAtPlayhead,
    togglePlay,
    stepFrame,
    document,
    selectedClipIds,
    playheadMs,
  ]);
}
