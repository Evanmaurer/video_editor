import { useProjectStore } from "@/stores/project-store";

export function StatusBar() {
  const project = useProjectStore((s) => s.project);
  const health = useProjectStore((s) => s.health);

  return (
    <div className="h-6 flex items-center px-3 bg-secondary border-t border-border text-xs text-muted gap-4">
      <span className="text-[#2ecc71]">Ready</span>
      {project && <span>Project: {project.name}</span>}
      {health && (
        <>
          <span>
            GPU: {health.gpu_available ? (health.gpu_name ?? "Available") : "CPU only"}
          </span>
          {health.performance_note && (
            <span className="text-[#f39c12] truncate" title={health.performance_note}>
              {health.performance_note}
            </span>
          )}
        </>
      )}
    </div>
  );
}
