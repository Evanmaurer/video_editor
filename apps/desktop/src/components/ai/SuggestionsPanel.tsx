export function SuggestionsPanel() {
  return (
    <div className="h-full flex flex-col bg-secondary border-l border-t border-border">
      <div className="px-3 py-2 border-b border-border text-sm font-medium">AI Suggestions</div>
      <div className="panel-empty">
        <p>AI suggestions will appear after timeline generation</p>
        <p className="text-xs">Every suggestion includes confidence and reasoning</p>
      </div>
    </div>
  );
}
