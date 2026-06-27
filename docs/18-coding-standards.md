# Coding Standards

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. General Principles

- **Read before write.** Understand existing patterns before adding code.
- **Minimal scope.** Change only what the task requires.
- **No placeholders.** Never commit stub functions, TODO implementations, or `pass` bodies that will ship.
- **Types everywhere.** TypeScript strict mode; Python type hints on all public functions.
- **Test what you ship.** Every feature includes unit tests; critical paths include integration tests.

---

## 2. TypeScript / Frontend Standards

### 2.1 Configuration

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

### 2.2 Naming

| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `Timeline.tsx` |
| Hooks | camelCase, `use` prefix | `useTimeline.ts` |
| Stores | camelCase, `Store` suffix | `timelineStore.ts` |
| Services | camelCase, `Service` suffix | `apiClient.ts` |
| Types/Interfaces | PascalCase | `TimelineDocument` |
| Constants | SCREAMING_SNAKE | `MAX_UNDO_STACK` |
| Files (non-component) | camelCase | `snapEngine.ts` |

### 2.3 Component Guidelines

```typescript
// ✅ Good: typed props, single responsibility
interface ClipCardProps {
  mediaItem: MediaItem;
  onSelect: (id: string) => void;
}

export function ClipCard({ mediaItem, onSelect }: ClipCardProps) {
  // ...
}

// ❌ Bad: any types, inline styles, business logic in component
export function ClipCard(props: any) {
  const score = calculateExcitement(props.item); // logic belongs in module
  return <div style={{ color: 'red' }}>{score}</div>;
}
```

- Components are presentational; business logic lives in `modules/` or `stores/`.
- Use TailwindCSS classes; no inline styles except dynamic values.
- Export components as named exports (not default).

### 2.4 State Management

- One store per domain (project, media, timeline, ai, ui, render).
- Use selectors to prevent unnecessary re-renders.
- Never mutate state directly; use store actions.

### 2.5 Error Handling

```typescript
// API errors are typed
try {
  await apiClient.importMedia(projectId, paths);
} catch (error) {
  if (error instanceof MontageApiError) {
    toast.error(error.message);
  } else {
    toast.error('An unexpected error occurred');
    logger.error('import_failed', { error });
  }
}
```

---

## 3. Python / Backend Standards

### 3.1 Configuration

- Python 3.11+
- Ruff for linting and formatting (replaces black + isort + flake8)
- mypy strict mode for `montage_backend/` and `ai/`

### 3.2 Naming

| Element | Convention | Example |
|---------|------------|---------|
| Modules | snake_case | `clip_analyzer.py` |
| Classes | PascalCase | `ClipAnalyzerAgent` |
| Functions | snake_case | `analyze_clip()` |
| Constants | SCREAMING_SNAKE | `MAX_FRAME_SAMPLE_FPS` |
| Private | leading underscore | `_parse_ffmpeg_progress()` |

### 3.3 Type Hints

```python
# ✅ Good: full type hints, docstring on public API
async def analyze_clip(
    media_item_id: str,
    video_path: Path,
    sample_fps: float = 2.0,
) -> ClipAnalyzerOutput:
    """Analyze a video clip for scenes, motion, and excitement."""
    ...

# ❌ Bad: missing types
async def analyze_clip(media_item_id, video_path, sample_fps=2.0):
    ...
```

### 3.4 Service Layer

- Services receive repositories and other services via constructor injection.
- Services raise domain exceptions (`MontageError` subclasses), never raw exceptions.
- Services do not import from `api/` layer.

### 3.5 Agent Implementation

```python
class ClipAnalyzerAgent(BaseAgent):
    agent_id = "clip-analyzer"
    agent_version = "1.0.0"

    async def analyze(self, input: ClipAnalyzerInput) -> AgentResult:
        start = time.monotonic()
        # ... analysis logic ...
        return AgentResult(
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            confidence=computed_confidence,
            reasoning="Motion score 8.2 due to sustained combat sequence.",
            data=output.model_dump(),
            processing_time_ms=int((time.monotonic() - start) * 1000),
        )
```

Every agent MUST return confidence and reasoning. Never raise for low-confidence results.

### 3.6 Logging

```python
import structlog
logger = structlog.get_logger()

logger.info(
    "clip_analysis_started",
    media_item_id=media_item_id,
    correlation_id=correlation_id,
)
```

- Use structured key-value logging, not f-strings.
- Include `correlation_id` on all job-related logs.
- Log levels: DEBUG (dev only), INFO (operations), WARNING (recoverable), ERROR (failures).

---

## 4. API Standards

### 4.1 REST Conventions

- Nouns for resources: `/projects`, `/media`, `/timelines`
- HTTP verbs: GET (read), POST (create/action), PUT (update), DELETE (remove)
- Status codes: 200 (OK), 201 (Created), 202 (Accepted/async), 400, 401, 404, 422, 500
- All responses include consistent error format

### 4.2 Versioning

- URL prefix: `/api/v1/`
- Breaking changes increment version

---

## 5. Database Standards

- All tables have `id` (UUID TEXT), `created_at`, and relevant timestamps.
- Foreign keys enforced.
- Migrations via Alembic; never modify schema manually.
- JSON columns validated against JSON Schema before insert.

---

## 6. Git Standards

### 6.1 Branch Naming

```
main                          # production-ready
milestone-{N}-{short-name}    # milestone work
fix/{short-description}       # bug fixes
```

### 6.2 Commit Messages

```
type(scope): concise description

Optional body explaining why.

Types: feat, fix, refactor, test, docs, chore, perf
Scopes: frontend, backend, ai, timeline, render, docs
```

Examples:
```
feat(backend): implement clip analyzer agent
fix(frontend): timeline snap to beat off by one frame
test(ai): add bomb detector validation tests
docs: update API design for render endpoints
```

### 6.3 Pull Requests

- One milestone task per PR when possible
- Include test evidence
- Update PROJECT_STATE.md if meaningful progress
- No merge without passing CI

---

## 7. Documentation Standards

- Public APIs documented with docstrings (Python) or JSDoc (TypeScript).
- Architecture changes update relevant `/docs` files.
- PROJECT_STATE.md updated after every meaningful coding session.
- No redundant comments; code should be self-explanatory.

---

## 8. Security Standards

- Backend binds to `127.0.0.1` only.
- Electron: `contextIsolation: true`, `nodeIntegration: false`.
- No secrets in code; API keys in settings (encrypted local storage).
- Validate all file paths from IPC/API before filesystem access.
- Sanitize user input in chat commands before execution.

---

## 9. Performance Standards

- Frontend: no operation blocks UI thread > 16ms.
- Backend: FFmpeg/OpenCV/ML in thread pool or dedicated workers.
- Database: index all frequently queried columns (see schema doc).
- API: paginate lists > 50 items.
- Memory: unload ML models when not in use; limit concurrent analysis jobs.

---

## 10. File Organization Rules

- One component per file.
- One agent per file.
- One service per file.
- Test files mirror source: `clip_analyzer.py` → `test_clip_analyzer.py`.
- No file > 400 lines without justification; split if exceeded.

---

## 11. Dependency Management

- **Frontend:** pnpm (lockfile committed)
- **Backend:** pip with `requirements.txt` + `pyproject.toml`
- Pin major versions; allow minor/patch updates.
- No unnecessary dependencies; justify each addition in PR.
- AI models not in git; download via script.

---

## 12. Code Review Checklist

- [ ] Types complete (no `any`, no untyped Python)
- [ ] Tests included and passing
- [ ] No placeholder/stub code
- [ ] Confidence + reasoning on AI outputs
- [ ] Error handling with structured logging
- [ ] No secrets or hardcoded paths
- [ ] Follows naming conventions
- [ ] Documentation updated if architecture changed
- [ ] PROJECT_STATE.md updated
