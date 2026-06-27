export function Timeline() {
  return (
    <div className="h-full flex flex-col bg-secondary">
      <div className="px-3 py-2 border-b border-border text-sm font-medium">Timeline</div>
      <div className="panel-empty">
        <p>Drag clips here or generate an AI timeline</p>
        <button type="button" className="btn-secondary opacity-50" disabled>
          Generate Timeline
        </button>
        <p className="text-xs mt-2">Timeline engine — Milestone 5</p>
      </div>
    </div>
  );
}
