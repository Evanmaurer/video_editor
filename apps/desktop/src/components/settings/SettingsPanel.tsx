import { useEffect, useState } from "react";
import type { AppSettings, LlmProviderType } from "@montage/shared-types";
import { DEFAULT_LLM_CONFIG, FALLBACK_LLM_CONFIG } from "@montage/shared-types";
import { getApiClient } from "@/services/api-client";
import { useProjectStore, useSettingsStore } from "@/stores/project-store";

const PROVIDERS: LlmProviderType[] = ["ollama", "openai", "none"];

export function SettingsPanel() {
  const setView = useProjectStore((s) => s.setView);
  const health = useProjectStore((s) => s.health);
  const settings = useSettingsStore((s) => s.settings);
  const setSettings = useSettingsStore((s) => s.setSettings);
  const [local, setLocal] = useState<AppSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const api = getApiClient();
      const loaded = await api.getSettings();
      setSettings(loaded);
      setLocal(loaded);
    })();
  }, [setSettings]);

  if (!local) {
    return (
      <div className="flex-1 panel-empty">
        <p>Loading settings...</p>
      </div>
    );
  }

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const api = getApiClient();
      const saved = await api.updateSettings(local);
      setSettings(saved);
      setLocal(saved);
      setMessage("Settings saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 overflow-auto p-6 max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Settings</h1>
        <button type="button" className="btn-secondary" onClick={() => setView(useProjectStore.getState().project ? "editor" : "welcome")}>
          Back
        </button>
      </div>

      <section className="mb-8 space-y-4">
        <h2 className="text-sm font-medium text-muted uppercase tracking-wide">General</h2>
        <div>
          <label className="text-xs text-muted block mb-1">Default Project Location</label>
          <input
            className="input-field"
            value={local.default_project_path}
            onChange={(e) => setLocal({ ...local, default_project_path: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs text-muted block mb-1">Analysis Workers</label>
          <input
            type="number"
            min={1}
            max={8}
            className="input-field w-24"
            value={local.worker_count}
            onChange={(e) => setLocal({ ...local, worker_count: Number(e.target.value) })}
          />
        </div>
      </section>

      <section className="mb-8 space-y-4">
        <h2 className="text-sm font-medium text-muted uppercase tracking-wide">Hardware</h2>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={local.gpu_enabled}
            onChange={(e) => setLocal({ ...local, gpu_enabled: e.target.checked })}
          />
          Use GPU acceleration when available
        </label>
        {health && (
          <div className="text-sm bg-secondary border border-border rounded-md p-3 space-y-1">
            <p>GPU: {health.gpu_available ? (health.gpu_name ?? "Detected") : "Not detected — CPU mode"}</p>
            {health.performance_note && (
              <p className="text-[#f39c12] text-xs">{health.performance_note}</p>
            )}
          </div>
        )}
      </section>

      <section className="mb-8 space-y-4">
        <h2 className="text-sm font-medium text-muted uppercase tracking-wide">AI Chat (LLM Provider)</h2>
        <p className="text-xs text-muted">
          Provider abstraction — editor works fully without LLM. AI chat disables gracefully if unavailable.
        </p>
        <div>
          <label className="text-xs text-muted block mb-1">Provider</label>
          <select
            className="input-field"
            value={local.llm.provider}
            onChange={(e) =>
              setLocal({
                ...local,
                llm: { ...local.llm, provider: e.target.value as LlmProviderType },
              })
            }
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted block mb-1">Model</label>
          <input
            className="input-field"
            value={local.llm.model}
            onChange={(e) => setLocal({ ...local, llm: { ...local.llm, model: e.target.value } })}
          />
        </div>
        {local.llm.provider === "openai" && (
          <div>
            <label className="text-xs text-muted block mb-1">API Key</label>
            <input
              type="password"
              className="input-field"
              value={local.llm.api_key ?? ""}
              onChange={(e) => setLocal({ ...local, llm: { ...local.llm, api_key: e.target.value } })}
            />
          </div>
        )}
        {local.llm.provider === "ollama" && (
          <div>
            <label className="text-xs text-muted block mb-1">Ollama Base URL</label>
            <input
              className="input-field"
              value={local.llm.base_url ?? ""}
              onChange={(e) => setLocal({ ...local, llm: { ...local.llm, base_url: e.target.value } })}
            />
          </div>
        )}
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-secondary text-xs"
            onClick={() => setLocal({ ...local, llm: { ...DEFAULT_LLM_CONFIG } })}
          >
            Use Qwen3 8B (recommended)
          </button>
          <button
            type="button"
            className="btn-secondary text-xs"
            onClick={() => setLocal({ ...local, llm: { ...FALLBACK_LLM_CONFIG } })}
          >
            Use Llama 3.2 3B (low-end)
          </button>
        </div>
      </section>

      <div className="flex items-center gap-4">
        <button type="button" className="btn-primary" disabled={saving} onClick={() => void handleSave()}>
          {saving ? "Saving..." : "Save Settings"}
        </button>
        {message && <span className="text-sm text-muted">{message}</span>}
      </div>
    </div>
  );
}
