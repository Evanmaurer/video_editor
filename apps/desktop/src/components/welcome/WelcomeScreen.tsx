import { useUIStore, useProjectStore } from "@/stores/project-store";
import { getApiClient } from "@/services/api-client";

export function WelcomeScreen() {
  const recentProjects = useProjectStore((s) => s.recentProjects);
  const setProject = useProjectStore((s) => s.setProject);
  const setLoading = useProjectStore((s) => s.setLoading);
  const setError = useProjectStore((s) => s.setError);
  const setShowNewProjectWizard = useUIStore((s) => s.setShowNewProjectWizard);

  const handleOpenProject = async () => {
    const path = await window.montageAPI.openProject();
    if (!path) return;

    setLoading(true);
    setError(null);
    try {
      const api = getApiClient();
      const project = await api.openProject({ path });
      setProject(project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open project");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenRecent = async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const api = getApiClient();
      const project = await api.openProject({ path });
      setProject(project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open project");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-[#e8e8e8] mb-2">MontageAI</h1>
        <p className="text-muted">AI-Powered Montage Editor</p>
      </div>

      <div className="flex gap-4">
        <button type="button" className="btn-primary px-8 py-4 text-base" onClick={() => setShowNewProjectWizard(true)}>
          + New Project
        </button>
        <button type="button" className="btn-secondary px-8 py-4 text-base" onClick={() => void handleOpenProject()}>
          Open Project
        </button>
      </div>

      {recentProjects.length > 0 && (
        <div className="w-full max-w-lg">
          <h2 className="text-sm text-muted mb-2">Recent Projects</h2>
          <div className="bg-panel border border-border rounded-lg divide-y divide-border">
            {recentProjects.map((p) => (
              <button
                key={p.id}
                type="button"
                className="w-full text-left px-4 py-3 hover:bg-hover transition-colors"
                onClick={() => void handleOpenRecent(p.path)}
              >
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-muted truncate">{p.path}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-muted">Supported Game: Albion Online</p>
    </div>
  );
}
