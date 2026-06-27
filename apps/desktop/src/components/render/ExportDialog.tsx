import { useEffect, useState } from "react";
import { useProjectStore, useUIStore } from "@/stores/project-store";
import { useRenderStore } from "@/stores/render-store";
import { useTimelineStore } from "@/stores/timeline-store";

export function ExportDialog() {
  const project = useProjectStore((s) => s.project);
  const showExportDialog = useUIStore((s) => s.showExportDialog);
  const setShowExportDialog = useUIStore((s) => s.setShowExportDialog);
  const setShowRenderQueue = useUIStore((s) => s.setShowRenderQueue);
  const document = useTimelineStore((s) => s.document);
  const presets = useRenderStore((s) => s.presets);
  const loadPresets = useRenderStore((s) => s.loadPresets);
  const startExport = useRenderStore((s) => s.startExport);
  const isStarting = useRenderStore((s) => s.isStarting);
  const error = useRenderStore((s) => s.error);

  const [presetId, setPresetId] = useState("h264_1080p60");
  const [outputName, setOutputName] = useState("");
  const [useHardware, setUseHardware] = useState(true);

  useEffect(() => {
    if (showExportDialog) {
      void loadPresets();
    }
  }, [showExportDialog, loadPresets]);

  if (!showExportDialog || !project?.id) {
    return null;
  }

  const hasClips = document?.tracks.some((track) => track.clips.length > 0) ?? false;

  const handleExport = async () => {
    await startExport(project.id, {
      timeline_id: document?.id,
      preset_id: presetId,
      output_name: outputName.trim() || undefined,
      use_hardware_encoding: useHardware,
    });
    setShowExportDialog(false);
    setShowRenderQueue(true);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg bg-panel border border-border rounded-lg shadow-xl">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-medium">Export Timeline</h2>
          <button
            type="button"
            className="text-muted hover:text-foreground"
            onClick={() => setShowExportDialog(false)}
          >
            ✕
          </button>
        </div>
        <div className="p-4 space-y-4 text-sm">
          {!hasClips && (
            <p className="text-[#e74c3c] text-xs">Add clips to the timeline before exporting.</p>
          )}
          <label className="block space-y-1">
            <span className="text-muted text-xs uppercase tracking-wide">Preset</span>
            <select
              className="w-full bg-secondary border border-border rounded px-2 py-1.5"
              value={presetId}
              onChange={(event) => setPresetId(event.target.value)}
            >
              {presets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                  {preset.hardware_available ? " · HW" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-muted text-xs uppercase tracking-wide">Output filename</span>
            <input
              className="w-full bg-secondary border border-border rounded px-2 py-1.5"
              placeholder="Optional — defaults to timeline name"
              value={outputName}
              onChange={(event) => setOutputName(event.target.value)}
            />
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={useHardware}
              onChange={(event) => setUseHardware(event.target.checked)}
            />
            <span>Use hardware encoding when available</span>
          </label>
          {error && <p className="text-[#e74c3c] text-xs">{error}</p>}
        </div>
        <div className="px-4 py-3 border-t border-border flex justify-end gap-2">
          <button type="button" className="btn-secondary text-xs py-1 px-3" onClick={() => setShowExportDialog(false)}>
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary text-xs py-1 px-3"
            disabled={!hasClips || isStarting || presets.length === 0}
            onClick={() => void handleExport()}
          >
            {isStarting ? "Starting…" : "Start Export"}
          </button>
        </div>
      </div>
    </div>
  );
}
