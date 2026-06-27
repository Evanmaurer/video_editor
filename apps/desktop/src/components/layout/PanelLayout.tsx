import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { MediaLibrary } from "@/components/media/MediaLibrary";
import { PreviewWindow } from "@/components/preview/PreviewWindow";
import { Timeline } from "@/components/timeline/Timeline";
import { Inspector } from "@/components/inspector/Inspector";
import { SuggestionsPanel } from "@/components/ai/SuggestionsPanel";

export function EditorLayout() {
  return (
    <div className="flex-1 min-h-0">
      <PanelGroup direction="horizontal">
        <Panel defaultSize={18} minSize={12} maxSize={30}>
          <MediaLibrary />
        </Panel>
        <PanelResizeHandle className="w-1 bg-border hover:bg-accent transition-colors" />
        <Panel defaultSize={57} minSize={40}>
          <PanelGroup direction="vertical">
            <Panel defaultSize={55} minSize={30}>
              <PreviewWindow />
            </Panel>
            <PanelResizeHandle className="h-1 bg-border hover:bg-accent transition-colors" />
            <Panel defaultSize={45} minSize={25}>
              <Timeline />
            </Panel>
          </PanelGroup>
        </Panel>
        <PanelResizeHandle className="w-1 bg-border hover:bg-accent transition-colors" />
        <Panel defaultSize={25} minSize={18} maxSize={35}>
          <PanelGroup direction="vertical">
            <Panel defaultSize={50} minSize={25}>
              <Inspector />
            </Panel>
            <PanelResizeHandle className="h-1 bg-border hover:bg-accent transition-colors" />
            <Panel defaultSize={50} minSize={25}>
              <SuggestionsPanel />
            </Panel>
          </PanelGroup>
        </Panel>
      </PanelGroup>
    </div>
  );
}
