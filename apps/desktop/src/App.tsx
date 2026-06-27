import { useEffect, useState } from "react";
import { MenuBar } from "@/components/layout/MenuBar";
import { Toolbar } from "@/components/layout/Toolbar";
import { StatusBar } from "@/components/layout/StatusBar";
import { EditorLayout } from "@/components/layout/PanelLayout";
import { WelcomeScreen } from "@/components/welcome/WelcomeScreen";
import { NewProjectWizard } from "@/components/welcome/NewProjectWizard";
import { SettingsPanel } from "@/components/settings/SettingsPanel";
import { ExportDialog } from "@/components/render/ExportDialog";
import { RenderQueuePanel } from "@/components/render/RenderQueuePanel";
import { getApiClient, initApiClient } from "@/services/api-client";
import { wsClient } from "@/services/websocket-client";
import { useProjectStore, useUIStore } from "@/stores/project-store";

const STARTUP_TIMEOUT_MS = 30_000;

function getMontageAPI(): Window["montageAPI"] | null {
  return typeof window !== "undefined" && window.montageAPI ? window.montageAPI : null;
}

export function App() {
  const view = useProjectStore((s) => s.view);
  const project = useProjectStore((s) => s.project);
  const error = useProjectStore((s) => s.error);
  const isLoading = useProjectStore((s) => s.isLoading);
  const setHealth = useProjectStore((s) => s.setHealth);
  const setRecentProjects = useProjectStore((s) => s.setRecentProjects);
  const setError = useProjectStore((s) => s.setError);
  const showNewProjectWizard = useUIStore((s) => s.showNewProjectWizard);
  const [backendReady, setBackendReady] = useState(false);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const timeout = setTimeout(() => {
      if (!cancelled) {
        setErrorDetail(
          "Startup timed out. Ensure the backend is running on http://127.0.0.1:8000 with the current code.",
        );
        setError("Startup timed out");
      }
    }, STARTUP_TIMEOUT_MS);

    void (async () => {
      try {
        const montageAPI = getMontageAPI();
        if (!montageAPI) {
          throw new Error(
            "Montage desktop API is unavailable. Launch with pnpm dev from the repo root, not in a browser.",
          );
        }

        await initApiClient();
        const api = getApiClient();
        const health = await api.getHealth();
        if (cancelled) {
          return;
        }
        setHealth(health);
        const recents = await api.getRecentProjects();
        if (cancelled) {
          return;
        }
        setRecentProjects(recents);
        setBackendReady(true);
        void wsClient.connect().catch(() => {
          // WebSocket is optional during M2; API polling covers media progress.
        });
      } catch (err) {
        if (cancelled) {
          return;
        }
        const fetchDetail =
          err instanceof Error
            ? [err.message, err.stack].filter(Boolean).join("\n")
            : String(err);
        let detail = fetchDetail;
        try {
          const montageAPI = getMontageAPI();
          if (montageAPI) {
            const status = await montageAPI.getBackendStatus();
            detail = fetchDetail || status.errorDetail || status.error || detail;
          }
        } catch {
          // keep fetchDetail
        }
        setErrorDetail(detail || null);
        setError(
          err instanceof Error
            ? err.message.split("\n")[0]!
            : "Failed to connect to backend",
        );
      } finally {
        clearTimeout(timeout);
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(timeout);
      wsClient.disconnect();
    };
  }, [setHealth, setRecentProjects, setError]);

  if (!backendReady && !error) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 bg-primary">
        <p className="text-[#e8e8e8] text-lg font-medium">Starting MontageAI…</p>
        <p className="text-muted text-sm">Connecting to backend at http://127.0.0.1:8000</p>
      </div>
    );
  }

  if (error && !backendReady) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4 p-8 max-w-3xl mx-auto">
        <p className="text-[#e74c3c] font-medium">Failed to start</p>
        {errorDetail ? (
          <pre className="w-full text-left text-xs bg-[#1e1e1e] border border-border rounded-md p-4 overflow-auto max-h-80 whitespace-pre-wrap text-[#e74c3c]">
            {errorDetail}
          </pre>
        ) : (
          <p className="text-[#e74c3c]">{error}</p>
        )}
        <p className="text-sm text-muted text-center">
          Run <code className="text-foreground">./scripts/setup.sh</code> from the repo root, then{" "}
          <code className="text-foreground">pnpm dev</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col relative">
      <MenuBar />
      {view === "editor" && project && <Toolbar />}
      <main className="flex-1 min-h-0 flex flex-col">
        {view === "welcome" && <WelcomeScreen />}
        {view === "editor" && project && <EditorLayout />}
        {view === "settings" && <SettingsPanel />}
      </main>
      {error && backendReady && (
        <div className="px-4 py-2 bg-[#e74c3c20] text-[#e74c3c] text-sm border-t border-border">
          {error}
        </div>
      )}
      {isLoading && (
        <div className="absolute inset-0 bg-black/30 flex items-center justify-center z-40">
          <span className="bg-panel px-4 py-2 rounded-md text-sm">Working...</span>
        </div>
      )}
      <StatusBar />
      {showNewProjectWizard && <NewProjectWizard />}
      <ExportDialog />
      <RenderQueuePanel />
    </div>
  );
}
