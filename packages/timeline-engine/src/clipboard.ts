import type { TimelineClip } from "@montage/shared-types";

export interface ClipboardPayload {
  clips: TimelineClip[];
  copied_at: string;
}

let clipboard: ClipboardPayload | null = null;

export function copyClipsToClipboard(clips: TimelineClip[]): ClipboardPayload {
  const payload: ClipboardPayload = {
    clips: clips.map((c) => ({ ...c })),
    copied_at: new Date().toISOString(),
  };
  clipboard = payload;
  return payload;
}

export function getClipboard(): ClipboardPayload | null {
  return clipboard;
}

export function clearClipboard(): void {
  clipboard = null;
}

export function hasClipboard(): boolean {
  return clipboard !== null && clipboard.clips.length > 0;
}
