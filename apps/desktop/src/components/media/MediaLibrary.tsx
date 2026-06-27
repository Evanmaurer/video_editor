export function MediaLibrary() {
  return (
    <div className="h-full flex flex-col bg-secondary border-r border-border">
      <div className="px-3 py-2 border-b border-border text-sm font-medium">Media Library</div>
      <div className="panel-empty">
        <p>Import gameplay clips to get started</p>
        <button type="button" className="btn-secondary opacity-50" disabled>
          Import Clips
        </button>
        <p className="text-xs mt-2">Available in Milestone 2</p>
      </div>
    </div>
  );
}
