export function Toolbar() {
  return (
    <div className="h-10 flex items-center gap-2 px-3 bg-panel border-b border-border text-sm">
      <button type="button" className="btn-secondary opacity-50" disabled>
        Import
      </button>
      <button type="button" className="btn-secondary opacity-50" disabled>
        Generate Timeline
      </button>
      <button type="button" className="btn-secondary opacity-50" disabled>
        Analyze All
      </button>
      <div className="w-px h-6 bg-border mx-1" />
      <button type="button" className="btn-secondary opacity-50" disabled>
        ▶ Play
      </button>
      <div className="flex-1" />
      <button type="button" className="btn-secondary opacity-50" disabled>
        Export
      </button>
      <button type="button" className="btn-secondary opacity-50" disabled>
        Render Queue
      </button>
    </div>
  );
}
