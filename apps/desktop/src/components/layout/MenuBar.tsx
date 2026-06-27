import { useProjectStore, useUIStore } from "@/stores/project-store";

export function MenuBar() {
  const project = useProjectStore((s) => s.project);
  const setView = useProjectStore((s) => s.setView);
  const setShowNewProjectWizard = useUIStore((s) => s.setShowNewProjectWizard);

  return (
    <div className="h-7 flex items-center px-3 bg-secondary border-b border-border text-xs text-muted select-none gap-4">
      <span className="text-[#e8e8e8] font-semibold">MontageAI</span>
      <button type="button" className="hover:text-[#e8e8e8]" onClick={() => setShowNewProjectWizard(true)}>
        File
      </button>
      <button type="button" className="hover:text-[#e8e8e8] opacity-50" disabled>
        Edit
      </button>
      <button type="button" className="hover:text-[#e8e8e8] opacity-50" disabled>
        View
      </button>
      <button type="button" className="hover:text-[#e8e8e8] opacity-50" disabled>
        Timeline
      </button>
      <button type="button" className="hover:text-[#e8e8e8] opacity-50" disabled>
        AI
      </button>
      <button type="button" className="hover:text-[#e8e8e8] opacity-50" disabled>
        Render
      </button>
      <button type="button" className="hover:text-[#e8e8e8]" onClick={() => setView("settings")}>
        Settings
      </button>
      {project && (
        <span className="ml-auto text-muted truncate max-w-xs">{project.name}</span>
      )}
    </div>
  );
}
