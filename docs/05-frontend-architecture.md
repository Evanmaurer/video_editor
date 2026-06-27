# Frontend Architecture

**Product:** MontageAI  
**Stack:** Electron + React + TypeScript + TailwindCSS  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Overview

The frontend is an Electron renderer process running a React SPA. It provides the professional NLE interface and owns all interactive timeline state. Heavy computation is delegated to the Python backend via a typed API client.

## 2. Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Build tool | electron-vite | Fast HMR; unified main/preload/renderer |
| UI framework | React 18 | Ecosystem; component model |
| Language | TypeScript (strict) | Type safety across API boundary |
| Styling | TailwindCSS | Utility-first; dark theme tokens |
| State | Zustand | Lightweight; no boilerplate |
| Data fetching | TanStack Query | Cache, retry, background refresh |
| Timeline canvas | Custom DOM + CSS transforms | Simpler than Canvas for v1; virtualize later |
| Preview | HTML5 `<video>` on proxy URLs | Reliable; WebCodecs upgrade path |
| IPC | electron preload bridge | Security (context isolation) |

## 3. Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│  Components (React) — pure UI, minimal logic            │
├─────────────────────────────────────────────────────────┤
│                    Application Layer                     │
│  Stores (Zustand) + Hooks — UI state orchestration      │
├─────────────────────────────────────────────────────────┤
│                    Domain Layer                          │
│  Timeline Engine, Preview Controller, Project Manager   │
├─────────────────────────────────────────────────────────┤
│                    Service Layer                         │
│  API Client, WebSocket Client, IPC Service              │
├─────────────────────────────────────────────────────────┤
│                    Shared Types                          │
│  packages/shared-types (generated from JSON Schema)     │
└─────────────────────────────────────────────────────────┘
```

**Dependency rule:** Components → Hooks/Stores → Domain Modules → Services. Never reverse.

## 4. Electron Architecture

### 4.1 Main Process Responsibilities

- Create browser window with security settings (`contextIsolation: true`, `nodeIntegration: false`)
- Spawn and monitor Python backend subprocess
- Register application menu (File, Edit, View, Timeline, AI, Render, Help)
- Handle native file dialogs via IPC
- Manage auto-updater (future)
- Graceful shutdown: stop backend, flush saves

### 4.2 Preload Bridge API

```typescript
// Exposed as window.montageAPI
interface MontageAPI {
  openDirectory(): Promise<string | null>;
  openFiles(options: OpenFilesOptions): Promise<string[]>;
  saveFile(options: SaveFileOptions): Promise<string | null>;
  revealInFolder(path: string): void;
  getBackendUrl(): Promise<string>;
  onBackendStatus(callback: (status: BackendStatus) => void): () => void;
}
```

### 4.3 Renderer Security

- CSP restricts script sources
- All file paths validated in main process
- Backend URL and auth token obtained via IPC (not hardcoded)

## 5. State Management

### 5.1 Store Map

| Store | State | Persistence |
|-------|-------|-------------|
| `projectStore` | Active project, settings, recent projects | Backend + localStorage recents |
| `mediaStore` | Media items, filters, sort, selection | Backend |
| `timelineStore` | Active timeline, playhead, selection, zoom | Timeline Engine + auto-save |
| `aiStore` | Suggestions, analysis progress, chat messages | Backend |
| `uiStore` | Panel sizes, dock state, theme, modals | localStorage |
| `renderStore` | Render queue, active jobs | Backend via WS |

### 5.2 Timeline State Ownership

The **Timeline Engine** module owns the authoritative timeline document in memory. The `timelineStore` mirrors it for React reactivity. All mutations go through Timeline Engine commands (enabling undo/redo).

```typescript
// Mutation flow
User action → TimelineEngine.execute(command) → undo stack push → timelineStore sync → debounced save to backend
```

## 6. Timeline Engine (Frontend)

See [08-timeline-engine-design.md](./08-timeline-engine-design.md) for full specification.

Frontend responsibilities:
- Render multi-track timeline UI
- Handle drag-drop, trim, split, ripple delete
- Snap to beats (from music analysis)
- Maintain undo/redo stack (min 100 operations)
- Serialize/deserialize timeline JSON

## 7. Preview System

### 7.1 Preview Controller

```typescript
class PreviewController {
  loadTimeline(timeline: TimelineDocument): void;
  seek(timeMs: number): void;
  play(): void;
  pause(): void;
  getCurrentFrame(): PreviewFrame;
}
```

### 7.2 v1 Preview Strategy

- Play proxy video files sequentially per active clip
- Audio mixed via Web Audio API (music track + clip audio)
- Frame-accurate preview deferred to Milestone 5+; proxy sync sufficient for v1

### 7.3 Upgrade Path

- Milestone 6+: Backend frame server via WebSocket for full-res scrubbing
- WebCodecs for hardware decode where available

## 8. Component Architecture

### 8.1 Layout Shell

```
App
├── MenuBar
├── Toolbar
├── PanelLayout (react-resizable-panels)
│   ├── MediaLibrary
│   ├── CenterColumn
│   │   ├── PreviewWindow
│   │   └── Timeline
│   └── RightColumn
│       ├── Inspector
│       └── SuggestionsPanel
├── ChatPanel (dockable)
├── RenderQueue (dockable)
└── StatusBar
```

### 8.2 Key Component Contracts

| Component | Props Source | Events |
|-----------|-------------|--------|
| `MediaLibrary` | `mediaStore` | `onImport`, `onSelect`, `onFilter` |
| `Timeline` | `timelineStore` | `onClipMove`, `onTrim`, `onSeek` |
| `PreviewWindow` | `PreviewController` | `onPlay`, `onPause`, `onSeek` |
| `SuggestionCard` | suggestion object | `onAccept`, `onReject`, `onPreview` |
| `ChatPanel` | `aiStore.messages` | `onSendMessage` |

## 9. API Integration

### 9.1 API Client

```typescript
class MontageApiClient {
  constructor(baseUrl: string, authToken: string);

  // Projects
  createProject(data: CreateProjectRequest): Promise<Project>;
  openProject(path: string): Promise<Project>;

  // Media
  importMedia(projectId: string, paths: string[]): Promise<ImportJob>;
  getMediaItems(projectId: string, filters?: MediaFilters): Promise<MediaItem[]>;

  // Analysis
  startAnalysis(projectId: string, options: AnalysisOptions): Promise<Job>;
  getAnalysisResults(mediaItemId: string): Promise<ClipAnalysis>;

  // Timeline
  getTimeline(timelineId: string): Promise<TimelineDocument>;
  saveTimeline(timelineId: string, doc: TimelineDocument): Promise<void>;
  generateTimeline(request: GenerateTimelineRequest): Promise<TimelineDocument>;

  // Render
  startRender(request: RenderRequest): Promise<RenderJob>;

  // AI Chat
  sendChatMessage(request: ChatRequest): Promise<ChatResponse>;
}
```

### 9.2 WebSocket Events

```typescript
type WSEvent =
  | { type: 'job.progress'; jobId: string; progress: number; message: string }
  | { type: 'job.complete'; jobId: string; result: unknown }
  | { type: 'job.failed'; jobId: string; error: string }
  | { type: 'analysis.clip_complete'; mediaItemId: string }
  | { type: 'suggestion.new'; suggestion: AISuggestion }
  | { type: 'render.progress'; jobId: string; progress: number };
```

## 10. Routing & Navigation

Single-window app; no URL router needed for v1.

**View states** managed in `uiStore`:
- `welcome` — recent projects, create/open
- `editor` — main editing workspace
- `settings` — modal overlay

## 11. Theming

Tailwind dark theme with design tokens:

```css
:root {
  --bg-primary: #1a1a1a;
  --bg-secondary: #252525;
  --bg-panel: #2d2d2d;
  --accent: #6c5ce7;
  --accent-hover: #7d6ff0;
  --text-primary: #e8e8e8;
  --text-secondary: #999999;
  --border: #3d3d3d;
  --timeline-track: #333333;
  --clip-video: #4a90d9;
  --clip-audio: #4caf50;
  --clip-effect: #e67e22;
  --danger: #e74c3c;
  --success: #2ecc71;
}
```

See [ui-ux-design.md](./ui-ux-design.md) for full design system.

## 12. Performance Guidelines

| Concern | Strategy |
|---------|----------|
| Media library (500+ items) | Virtualized grid (react-window) |
| Timeline (200+ clips) | Virtual horizontal scroll; render visible tracks only |
| Re-renders | Zustand selectors; memoized clip components |
| Auto-save | Debounce 2s; diff-only PATCH |
| WebSocket | Single connection; multiplexed event handlers |

## 13. Error Boundaries

- Top-level error boundary with recovery UI
- Panel-level boundaries (timeline crash doesn't kill preview)
- Backend disconnect overlay with retry

## 14. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Space` | Play/Pause |
| `Cmd+Z` / `Ctrl+Z` | Undo |
| `Cmd+Shift+Z` | Redo |
| `S` | Split at playhead |
| `Delete` | Delete selected clip |
| `←/→` | Frame step |
| `J/K/L` | Reverse/Pause/Forward (Premiere-style) |
| `Cmd+S` | Force save |
| `Cmd+E` | Export |
| `Cmd+I` | Import media |

## 15. Testing (Frontend)

| Level | Tool | Scope |
|-------|------|-------|
| Unit | Vitest | Timeline Engine, utils, stores |
| Component | Vitest + Testing Library | UI components |
| E2E | Playwright | Full workflows in Electron |

See [19-testing-strategy.md](./19-testing-strategy.md).

## 16. Build & Packaging

- **Dev:** `pnpm dev` — electron-vite dev server + backend
- **Prod:** electron-builder produces `.dmg` (macOS) and `.exe` (Windows)
- Python backend bundled via PyInstaller inside Electron resources
