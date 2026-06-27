import { useState } from "react";
import { joinPath } from "@/utils/path";
import { getApiClient } from "@/services/api-client";
import { useProjectStore, useUIStore } from "@/stores/project-store";

export function NewProjectWizard() {
  const setShowNewProjectWizard = useUIStore((s) => s.setShowNewProjectWizard);
  const setProject = useProjectStore((s) => s.setProject);
  const setLoading = useProjectStore((s) => s.setLoading);
  const setError = useProjectStore((s) => s.setError);

  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [step, setStep] = useState(1);

  const handleBrowse = async () => {
    const dir = await window.montageAPI.openDirectory();
    if (dir) {
      setLocation(dir);
    }
  };

  const handleCreate = async () => {
    if (!name.trim() || !location.trim()) {
      setError("Project name and location are required");
      return;
    }

    const rootPath = joinPath(location, name.replace(/[^\w\s-]/g, "").replace(/\s+/g, "_"));

    setLoading(true);
    setError(null);
    try {
      const api = getApiClient();
      const project = await api.createProject({
        name: name.trim(),
        root_path: rootPath,
        width: 1920,
        height: 1080,
        frame_rate: 60,
        target_game: "albion",
      });
      setProject(project);
      setShowNewProjectWizard(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-panel border border-border rounded-xl w-full max-w-md p-6 shadow-xl">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-lg font-semibold">New Project</h2>
          <button type="button" className="text-muted hover:text-[#e8e8e8]" onClick={() => setShowNewProjectWizard(false)}>
            ×
          </button>
        </div>

        {step === 1 && (
          <div className="space-y-4">
            <p className="text-sm text-muted">Step 1 of 1: Project Details</p>
            <div>
              <label className="text-xs text-muted block mb-1">Project Name</label>
              <input
                className="input-field"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="ZvZ_Montage_June"
              />
            </div>
            <div>
              <label className="text-xs text-muted block mb-1">Location</label>
              <div className="flex gap-2">
                <input
                  className="input-field flex-1"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="/Users/you/Videos/Montages"
                />
                <button type="button" className="btn-secondary" onClick={() => void handleBrowse()}>
                  Browse
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted block mb-1">Resolution</label>
                <input className="input-field" value="1920 × 1080" disabled />
              </div>
              <div>
                <label className="text-xs text-muted block mb-1">Frame Rate</label>
                <input className="input-field" value="60 fps" disabled />
              </div>
            </div>
            <div>
              <label className="text-xs text-muted block mb-1">Game</label>
              <input className="input-field" value="Albion Online" disabled />
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <button type="button" className="btn-secondary" onClick={() => setShowNewProjectWizard(false)}>
                Cancel
              </button>
              <button type="button" className="btn-primary" onClick={() => void handleCreate()}>
                Create Project
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
