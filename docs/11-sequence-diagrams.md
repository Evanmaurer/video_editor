# Sequence Diagrams

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Application Startup

```mermaid
sequenceDiagram
    actor User
    participant Electron as Electron Main
    participant Renderer as React Frontend
    participant Backend as Python Backend

    User->>Electron: Launch MontageAI
    Electron->>Backend: Spawn subprocess
    Backend->>Backend: Load config, models
    Backend-->>Electron: stdout: {"port": 48291, "token": "..."}
    
    loop Health check (max 30s)
        Electron->>Backend: GET /health
        Backend-->>Electron: {"status": "ok"}
    end
    
    Electron->>Renderer: Create window
    Renderer->>Electron: IPC: getBackendUrl()
    Electron-->>Renderer: {url, token}
    Renderer->>Backend: GET /health (with token)
    Backend-->>Renderer: {"status": "ok", "models_loaded": true}
    Renderer->>User: Show Welcome Screen
```

---

## 2. Create Project & Import Media

```mermaid
sequenceDiagram
    actor User
    participant UI as React Frontend
    participant API as Backend API
    participant Media as MediaService
    participant Queue as Job Queue
    participant WS as WebSocket

    User->>UI: New Project Wizard
    UI->>API: POST /api/v1/projects
    API->>Media: create_project()
    Media->>Media: Create folder structure + SQLite
    Media-->>API: Project
    API-->>UI: Project created

    User->>UI: Select 247 clip files
    UI->>API: POST /api/v1/projects/{id}/media/import
    API->>Media: import_files(paths, role=clip)
    
    loop For each file
        Media->>Media: FFprobe validation
        Media->>Media: Register in media_items
        Media->>Queue: Enqueue proxy_generate
        Media->>Queue: Enqueue thumbnail_generate
        Media->>Queue: Enqueue clip_analyze
        Media->>Queue: Enqueue albion_analyze
    end
    
    Media-->>API: ImportResult (247 items)
    API-->>UI: Import started
    
    loop Progress updates
        Queue->>WS: job.progress events
        WS->>UI: Update progress bar
    end
    
    UI->>User: Show analysis progress overlay
```

---

## 3. Clip Analysis Pipeline

```mermaid
sequenceDiagram
    participant Queue as Job Queue
    participant Handler as Analyze Handler
    participant AI as AI Engine
    participant Clip as Clip Analyzer
    participant Albion as Albion Analyzer
    participant Repo as Repository
    participant WS as WebSocket

    Queue->>Handler: clip_analyze job
    Handler->>Handler: Load proxy video path
    Handler->>AI: run_agent("clip-analyzer", input)
    AI->>Clip: analyze(input)
    
    Clip->>Clip: Extract frames (2fps)
    Clip->>Clip: Scene detection
    Clip->>Clip: Motion analysis
    Clip->>Clip: OCR extraction
    Clip->>Clip: Excitement scoring
    Clip-->>AI: ClipAnalyzerOutput
    
    AI->>Albion: analyze(input + clip output)
    Albion->>Albion: Run bomb detector
    Albion->>Albion: Run kill feed detector
    Albion->>Albion: Run engagement detector
    Albion-->>AI: AlbionAnalyzerOutput
    
    AI-->>Handler: PipelineResult
    Handler->>Repo: Save clip_analysis + game_events
    Handler->>WS: analysis.clip_complete event
    Handler->>Queue: Mark job complete
```

---

## 4. Generate AI Timeline

```mermaid
sequenceDiagram
    actor User
    participant UI as React Frontend
    participant API as Backend API
    participant Timeline as TimelineService
    participant AI as AI Engine
    participant Planner as Timeline Planner
    participant Repo as Repository

    User->>UI: Click "Generate Timeline"
    UI->>API: POST /api/v1/timelines/generate
    API->>Timeline: generate_timeline(request)
    Timeline->>Repo: Fetch ranked clips
    Timeline->>Repo: Fetch music analysis
    Timeline->>Repo: Fetch style profile
    Timeline->>Repo: Fetch game events
    
    Timeline->>AI: run_agent("timeline-planner", input)
    AI->>Planner: analyze(input)
    
    Planner->>Planner: Select top clips
    Planner->>Planner: Order by excitement arc
    Planner->>Planner: Align cuts to beat map
    Planner->>Planner: Apply style profile transitions
    Planner->>Planner: Build TimelineDocument
    Planner-->>AI: TimelinePlannerOutput
    
    AI-->>Timeline: Result with timeline + reasoning
    Timeline->>Repo: Save timeline JSON + DB index
    Timeline->>Repo: Create AI suggestions for alternatives
    Timeline-->>API: TimelineDocument
    API-->>UI: Timeline + suggestions
    
    UI->>UI: TimelineEngine.fromJSON()
    UI->>User: Display populated timeline
```

---

## 5. Natural Language Timeline Edit

```mermaid
sequenceDiagram
    actor User
    participant UI as React Frontend
    participant Engine as Timeline Engine
    participant API as Backend API
    participant Chat as Chat Assistant
    participant Edit as Editing Agent

    User->>UI: "Replace clip at 0:45 with better bomb"
    UI->>API: POST /api/v1/ai/chat
    API->>Chat: process(message, timeline, context)
    
    Chat->>Chat: Parse intent: REPLACE
    Chat->>Chat: Extract entities: time=45000, criteria=bomb
    Chat->>Repo: Query top bomb clips
    Chat->>Edit: apply(SwapClipCommand)
    Edit->>Edit: Validate clip fits at position
    Edit->>Edit: Apply swap with beat snap
    Edit-->>Chat: Updated timeline + edit record
    
    Chat->>Chat: Generate response text
    Chat-->>API: ChatResponse (timeline, commands, message)
    API-->>UI: Response
    
    UI->>Engine: execute(BatchCommand)
    Engine->>Engine: Push to undo stack
    UI->>User: Show AI response + updated timeline
    UI->>User: "Replaced clip at 0:45 with ZvZ_Bomb_03.mp4"
```

---

## 6. Accept AI Suggestion

```mermaid
sequenceDiagram
    actor User
    participant UI as React Frontend
    participant Engine as Timeline Engine
    participant API as Backend API
    participant Timeline as TimelineService
    participant Repo as Repository

    User->>UI: Click "Accept" on suggestion card
    UI->>API: POST /api/v1/suggestions/{id}/accept
    API->>Timeline: apply_suggestion(suggestion)
    
    Timeline->>Timeline: Convert suggestion to EditCommand(s)
    Timeline->>Timeline: Apply to timeline document
    Timeline->>Repo: Save updated timeline
    Timeline->>Repo: Update suggestion status = accepted
    
    Timeline-->>API: Updated TimelineDocument
    API-->>UI: Timeline + confirmation
    
    UI->>Engine: execute(commands from suggestion)
    UI->>UI: Remove suggestion from panel
    UI->>User: Timeline updated (undoable)
```

---

## 7. Export / Render

```mermaid
sequenceDiagram
    actor User
    participant UI as React Frontend
    participant API as Backend API
    participant Render as RenderService
    participant Graph as Graph Builder
    participant FFmpeg as FFmpeg
    participant WS as WebSocket

    User->>UI: Click Export (h264_1080p60)
    UI->>API: POST /api/v1/render
    API->>Render: start_render(request)
    Render->>Render: Validate timeline
    Render->>Graph: build(timeline, mode=export)
    Graph->>Graph: Map clips to FFmpeg inputs
    Graph->>Graph: Compile filter graph
    Graph-->>Render: FFmpegGraph
    Render->>Render: Create render_job (queued)
    Render-->>API: RenderJob
    API-->>UI: Job created
    
    Render->>FFmpeg: Execute command
    loop Progress
        FFmpeg-->>Render: stderr (frame=N, time=T)
        Render->>WS: render.progress event
        WS->>UI: Update progress bar
    end
    
    FFmpeg-->>Render: Exit code 0
    Render->>Render: Verify output (FFprobe)
    Render->>WS: job.complete event
    WS->>UI: Show completion
    UI->>User: "Export complete" + reveal button
```

---

## 8. Music Analysis

```mermaid
sequenceDiagram
    actor User
    participant UI as React Frontend
    participant API as Backend API
    participant Queue as Job Queue
    participant AI as AI Engine
    participant Music as Music Analyzer
    participant Repo as Repository

    User->>UI: Import music track
    UI->>API: POST /api/v1/projects/{id}/media/import (role=music)
    API->>Queue: Enqueue music_analyze
    
    Queue->>AI: run_agent("music-analyzer", input)
    AI->>Music: analyze(input)
    Music->>Music: Load audio (librosa)
    Music->>Music: Detect BPM
    Music->>Music: Extract beat grid
    Music->>Music: Compute energy curve
    Music->>Music: Detect drops/peaks
    Music-->>AI: MusicAnalyzerOutput
    
    AI-->>Queue: Result
    Queue->>Repo: Save music_analysis
    Queue->>UI: WS: job.complete
    
    UI->>UI: Display beat markers on timeline ruler
    UI->>User: "Music analyzed: 128 BPM, 4 drops detected"
```

---

## 9. Auto-Save & Crash Recovery

```mermaid
sequenceDiagram
    participant Engine as Timeline Engine
    participant UI as React Frontend
    participant API as Backend API
    participant FS as File System

    loop Every edit (debounced 2s)
        Engine->>Engine: onChange event
        Engine->>UI: Sync to timelineStore
        UI->>API: PUT /api/v1/timelines/{id}
        API->>FS: Write timeline JSON
        API->>FS: Update SQLite index
    end

    Note over UI,FS: --- Crash occurs ---

    User->>UI: Relaunch app, open project
    UI->>API: GET /api/v1/projects/{id}
    API->>FS: Read project.db + timeline JSON
    API-->>UI: Project + timeline
    UI->>Engine: fromJSON(timeline)
    UI->>User: Project restored to last save
```

---

## 10. WebSocket Event Flow

```mermaid
sequenceDiagram
    participant Backend as Python Backend
    participant WS as WebSocket Server
    participant UI as React Frontend
    participant Store as Zustand Stores

    UI->>WS: Connect ws://127.0.0.1:PORT/ws?token=...
    WS-->>UI: Connected

    Note over Backend,Store: Job progress events
    Backend->>WS: {type: "job.progress", progress: 0.45}
    WS->>UI: Event received
    UI->>Store: Update job progress in aiStore/renderStore

    Note over Backend,Store: Analysis complete
    Backend->>WS: {type: "analysis.clip_complete", mediaItemId: "..."}
    WS->>UI: Event received
    UI->>Store: Update media item status in mediaStore
    UI->>UI: Refresh clip card with scores

    Note over Backend,Store: New AI suggestion
    Backend->>WS: {type: "suggestion.new", suggestion: {...}}
    WS->>UI: Event received
    UI->>Store: Add to aiStore.suggestions
    UI->>UI: Show notification badge
```
