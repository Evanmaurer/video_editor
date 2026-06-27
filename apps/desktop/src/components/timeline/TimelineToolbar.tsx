interface TimelineToolbarProps {
  canUndo: boolean;
  canRedo: boolean;
  canDelete: boolean;
  snapEnabled: boolean;
  rippleEnabled: boolean;
  isSaving: boolean;
  zoom: number;
  onUndo: () => void;
  onRedo: () => void;
  onSplit: () => void;
  onDelete: () => void;
  onToggleSnap: () => void;
  onToggleRipple: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
}

export function TimelineToolbar({
  canUndo,
  canRedo,
  canDelete,
  snapEnabled,
  rippleEnabled,
  isSaving,
  zoom,
  onUndo,
  onRedo,
  onSplit,
  onDelete,
  onToggleSnap,
  onToggleRipple,
  onZoomIn,
  onZoomOut,
}: TimelineToolbarProps) {
  return (
    <div className="flex items-center gap-1 px-2 py-1 border-b border-border text-xs shrink-0 relative z-10">
      <button
        type="button"
        className="btn-secondary py-0.5 px-2 disabled:opacity-40 disabled:cursor-not-allowed"
        disabled={!canUndo}
        onClick={onUndo}
      >
        Undo
      </button>
      <button
        type="button"
        className="btn-secondary py-0.5 px-2 disabled:opacity-40 disabled:cursor-not-allowed"
        disabled={!canRedo}
        onClick={onRedo}
      >
        Redo
      </button>
      <span className="w-px h-4 bg-border mx-1" />
      <button type="button" className="btn-secondary py-0.5 px-2" onClick={onSplit}>
        Split
      </button>
      <button
        type="button"
        className="btn-secondary py-0.5 px-2 disabled:opacity-40 disabled:cursor-not-allowed text-red-300 hover:text-red-200"
        disabled={!canDelete}
        onClick={onDelete}
        title="Delete selected clip (Delete)"
      >
        Delete
      </button>
      <button
        type="button"
        className={`py-0.5 px-2 rounded border ${snapEnabled ? "bg-accent text-white border-accent" : "btn-secondary"}`}
        onClick={onToggleSnap}
      >
        Snap
      </button>
      <button
        type="button"
        className={`py-0.5 px-2 rounded border ${rippleEnabled ? "bg-accent text-white border-accent" : "btn-secondary"}`}
        onClick={onToggleRipple}
      >
        Ripple
      </button>
      <span className="w-px h-4 bg-border mx-1" />
      <button type="button" className="btn-secondary py-0.5 px-2" onClick={onZoomOut}>
        −
      </button>
      <span className="text-muted w-10 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
      <button type="button" className="btn-secondary py-0.5 px-2" onClick={onZoomIn}>
        +
      </button>
      <span className="ml-auto text-muted">{isSaving ? "Saving…" : ""}</span>
    </div>
  );
}
