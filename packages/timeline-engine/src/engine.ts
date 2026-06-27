import type { TimelineClip, TimelineDocument } from "@montage/shared-types";
import type { TimelineCommand } from "./commands/base";
import { cloneDocument, findClip } from "./utils";

export type TimelineChangeListener = (doc: TimelineDocument) => void;

export interface TimelineEngineOptions {
  maxUndoSteps?: number;
}

export class TimelineEngine {
  private document: TimelineDocument;
  private undoStack: TimelineDocument[] = [];
  private redoStack: TimelineDocument[] = [];
  private listeners = new Set<TimelineChangeListener>();
  private readonly maxUndoSteps: number;

  constructor(document: TimelineDocument, options: TimelineEngineOptions = {}) {
    this.document = cloneDocument(document);
    this.maxUndoSteps = options.maxUndoSteps ?? 100;
  }

  static fromDocument(document: TimelineDocument, options?: TimelineEngineOptions): TimelineEngine {
    return new TimelineEngine(document, options);
  }

  getDocument(): TimelineDocument {
    return cloneDocument(this.document);
  }

  getDurationMs(): number {
    return this.document.duration_ms;
  }

  getClip(clipId: string): TimelineClip | undefined {
    return findClip(this.document, clipId)?.clip;
  }

  getClipsAtTime(timeMs: number): TimelineClip[] {
    const clips: TimelineClip[] = [];
    for (const track of this.document.tracks) {
      for (const clip of track.clips) {
        if (timeMs >= clip.start_ms && timeMs < clip.end_ms) {
          clips.push(clip);
        }
      }
    }
    return clips;
  }

  execute(command: TimelineCommand): boolean {
    const before = cloneDocument(this.document);
    const after = command.apply(cloneDocument(this.document));
    if (JSON.stringify(before) === JSON.stringify(after)) {
      return false;
    }

    this.undoStack.push(before);
    if (this.undoStack.length > this.maxUndoSteps) {
      this.undoStack.shift();
    }
    this.redoStack = [];
    this.document = after;
    this.notify();
    return true;
  }

  undo(): boolean {
    const previous = this.undoStack.pop();
    if (!previous) {
      return false;
    }
    this.redoStack.push(cloneDocument(this.document));
    this.document = previous;
    this.notify();
    return true;
  }

  redo(): boolean {
    const next = this.redoStack.pop();
    if (!next) {
      return false;
    }
    this.undoStack.push(cloneDocument(this.document));
    this.document = next;
    this.notify();
    return true;
  }

  canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  replaceDocument(document: TimelineDocument): void {
    this.document = cloneDocument(document);
    this.undoStack = [];
    this.redoStack = [];
    this.notify();
  }

  onChange(listener: TimelineChangeListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    const snapshot = this.getDocument();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}
