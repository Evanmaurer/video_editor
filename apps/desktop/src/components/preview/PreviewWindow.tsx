export function PreviewWindow() {
  return (
    <div className="h-full flex flex-col bg-primary border-b border-border">
      <div className="px-3 py-2 border-b border-border text-sm font-medium">Preview</div>
      <div className="flex-1 panel-empty">
        <div className="w-full max-w-2xl aspect-video bg-panel border border-border rounded-md flex items-center justify-center">
          <span className="text-muted text-sm">No timeline loaded</span>
        </div>
        <div className="flex items-center gap-2 mt-4">
          <button type="button" className="btn-secondary opacity-50" disabled>
            ◀◀
          </button>
          <button type="button" className="btn-secondary opacity-50" disabled>
            ▶
          </button>
          <button type="button" className="btn-secondary opacity-50" disabled>
            ■
          </button>
          <span className="font-mono text-xs text-muted ml-2">00:00:00:00 / 00:00:00:00</span>
        </div>
      </div>
    </div>
  );
}
