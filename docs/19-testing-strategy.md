# Testing Strategy

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Testing Philosophy

- Every completed feature ships with tests.
- Tests verify behavior, not implementation details.
- Critical user workflows have end-to-end coverage.
- AI agents validated against labeled datasets with measurable accuracy targets.
- No placeholder tests; no tests that assert trivially true conditions.

---

## 2. Test Pyramid

```
         ┌───────┐
         │  E2E  │  5-10 critical workflow tests
         ├───────┤
         │ Integ │  API routes, agent pipelines, render pipeline
         ├───────┤
         │  Unit │  Engine logic, agents, services, utils
         └───────┘
```

| Level | Target Coverage | Tools |
|-------|----------------|-------|
| Unit | ≥ 80% of new code | Vitest (TS), pytest (Python) |
| Integration | All API routes + agent pipelines | pytest + httpx, Vitest |
| E2E | 5-10 critical workflows | Playwright (Electron) |
| AI Validation | Labeled datasets per agent | Custom pytest + metrics |

---

## 3. Frontend Testing

### 3.1 Unit Tests (Vitest)

**Scope:**
- Timeline Engine commands (add, remove, move, trim, split, undo, redo)
- Snap engine
- Store actions and selectors
- Utility functions (time formatting, diff generation)
- API client (mocked HTTP)

**Location:** `apps/desktop/src/**/*.test.ts`

**Example:**
```typescript
describe('TimelineEngine', () => {
  it('should undo clip move', () => {
    const engine = createTestTimeline();
    const originalStart = engine.getClip('clip-1')!.start_ms;
    engine.execute(new MoveClipCommand({ clipId: 'clip-1', newStartMs: 5000 }));
    engine.undo();
    expect(engine.getClip('clip-1')!.start_ms).toBe(originalStart);
  });
});
```

### 3.2 Component Tests (Vitest + Testing Library)

**Scope:**
- ClipCard renders scores and event badges
- SuggestionCard accept/reject buttons
- MediaLibrary filter and sort
- Timeline renders correct number of clips

**Location:** `apps/desktop/src/**/*.test.tsx`

### 3.3 E2E Tests (Playwright)

**Scope:** Critical user workflows in Electron.

**Location:** `tests/e2e/`

| Test | Workflow |
|------|----------|
| `project-lifecycle.spec.ts` | Create project → close → reopen → verify state |
| `import-analyze-export.spec.ts` | Import clips → analyze → generate timeline → export |
| `timeline-editing.spec.ts` | Manual clip placement → trim → split → undo → redo |
| `ai-suggestions.spec.ts` | Generate timeline → accept/reject suggestions |
| `ai-chat-editing.spec.ts` | Chat command → verify timeline change → undo |
| `render-queue.spec.ts` | Export → monitor progress → verify output file |

**Test media:** Small sample clips in `assets/test-media/` (gitignored; downloaded via script).

---

## 4. Backend Testing

### 4.1 Unit Tests (pytest)

**Scope:**
- All services (ProjectService, MediaService, TimelineService, RenderService)
- All repositories
- FFmpeg wrapper (with mocked subprocess)
- Job queue
- Agent logic (with mock frames/audio)

**Location:** `apps/backend/tests/unit/`

**Fixtures:** `apps/backend/tests/conftest.py`

```python
@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine)
    await engine.dispose()
```

### 4.2 Integration Tests (pytest + httpx)

**Scope:**
- All API routes with test database
- Full analysis pipeline (clip → albion → store)
- Timeline generate pipeline
- Render pipeline (with test clips)

**Location:** `apps/backend/tests/integration/`

```python
async def test_import_and_analyze(client, test_project, sample_clip):
    response = await client.post(
        f"/api/v1/projects/{test_project.id}/media/import",
        json={"paths": [str(sample_clip)], "role": "clip"},
    )
    assert response.status_code == 202

    # Wait for analysis job
    await wait_for_job(client, response.json()["job_ids"][0])

    analysis = await client.get(f"/api/v1/media/{media_id}/analysis")
    assert analysis.json()["excitement_score"] is not None
```

### 4.3 WebSocket Tests

```python
async def test_job_progress_events(client, ws_client):
    # Start analysis job
    # Connect WebSocket
    # Assert progress events received
    # Assert completion event received
```

---

## 5. AI Agent Testing

### 5.1 Validation Datasets

| Agent | Dataset | Size | Location |
|-------|---------|------|----------|
| Clip Analyzer | Labeled clips with excitement scores | 50 clips | `tests/fixtures/validation/clips/` |
| Albion Analyzer | Clips with labeled events (bombs, wipes) | 30 clips | `tests/fixtures/validation/albion/` |
| Music Analyzer | Tracks with known BPM | 20 tracks | `tests/fixtures/validation/music/` |
| Style Analyzer | Reference montages with known metrics | 5 montages | `tests/fixtures/validation/style/` |
| Timeline Planner | Full project inputs + expected outputs | 5 projects | `tests/fixtures/validation/timelines/` |
| Chat Assistant | NL commands → expected EditCommands | 50 phrases | `tests/fixtures/validation/chat/` |

### 5.2 Accuracy Metrics

| Agent | Metric | Target |
|-------|--------|--------|
| Clip Analyzer | Excitement score MAE | < 1.5 (on 0-10 scale) |
| Albion Bomb Detector | Precision | ≥ 70% (M3 gate), ≥ 80% (v1.0) |
| Albion Bomb Detector | Recall | ≥ 60% (M3 gate), ≥ 75% (v1.0) |
| Albion Wipe Detector | Precision | ≥ 75% |
| Music Analyzer | BPM accuracy | ±2 BPM on 90% of tracks |
| Music Analyzer | Beat alignment | ±50ms on 85% of beats |
| Style Analyzer | Cut frequency MAE | < 5 cuts/min |
| Timeline Planner | Creator acceptance rate | ≥ 60% (beta) |
| Chat Assistant | Intent classification accuracy | ≥ 85% on test phrases |

### 5.3 Agent Test Pattern

```python
class TestBombDetector:
    @pytest.fixture
    def validation_clips(self):
        return load_validation_set("albion/bombs")

    def test_bomb_precision(self, validation_clips):
        tp, fp = 0, 0
        for clip in validation_clips:
            result = bomb_detector.detect(clip.frames)
            if clip.has_bomb:
                if result.detected:
                    tp += 1
            else:
                if result.detected:
                    fp += 1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        assert precision >= 0.70, f"Bomb precision {precision:.2f} below threshold"
```

---

## 6. Render Pipeline Testing

```python
async def test_render_simple_timeline(test_timeline, tmp_path):
    output = tmp_path / "output.mp4"
    graph = RenderGraphBuilder().build(test_timeline, mode=RenderMode.EXPORT)
    await FFmpegWrapper().render_complex(graph, output)

    assert output.exists()
    probe = await FFmpegWrapper().probe(output)
    assert probe.duration_ms > 0
    assert probe.width == 1920
    assert probe.height == 1080
```

Test cases:
- Single clip render
- Multi-clip with transitions
- Speed change (slow-mo)
- Audio mixing (game + music)
- Partial render (time range)

---

## 7. CI Pipeline

```yaml
# .github/workflows/ci.yml (Milestone 1+)
jobs:
  frontend:
    - pnpm install
    - pnpm lint
    - pnpm typecheck
    - pnpm test:unit

  backend:
    - pip install -r requirements-dev.txt
    - ruff check
    - mypy montage_backend ai
    - pytest tests/unit tests/integration

  e2e:
    - pnpm build
    - npx playwright test (on macOS runner)
```

**Runs on:** Every PR to `main` or milestone branches.

---

## 8. Test Data Management

- Small test clips (< 5s, < 10MB) committed in `tests/fixtures/`
- Large validation sets downloaded via `scripts/download-test-media.sh` (gitignored)
- Test databases created in-memory (SQLite `:memory:`)
- Test projects created in temp directories, cleaned up after tests

---

## 9. Manual Testing Checklist (Per Milestone)

### M1 Manual Tests
- [ ] App launches without errors
- [ ] Create project → folder created on disk
- [ ] Close and reopen project
- [ ] All panels visible and resizable
- [ ] Settings save and persist

### M3 Manual Tests
- [ ] Import 10+ Albion clips
- [ ] Analysis completes with scores
- [ ] Bomb events detected on known bomb clips
- [ ] Filter by bomb event type works
- [ ] Sort by score works

### M5 Manual Tests
- [ ] Drag clip to timeline
- [ ] Trim clip handles
- [ ] Split at playhead
- [ ] Undo/redo all operations
- [ ] Preview plays clips
- [ ] Timeline persists after restart

### M7 Manual Tests
- [ ] Export 1-min montage successfully
- [ ] Output plays in external player
- [ ] Chat: "replace clip at 0:30" works
- [ ] Chat: "make intro faster" works
- [ ] Render queue shows progress

---

## 10. Performance Testing

| Benchmark | Target | Tool |
|-----------|--------|------|
| App cold start | < 5s | Manual / Playwright |
| Import 100 clips | < 60s | pytest benchmark |
| Analyze 1-min clip (GPU) | < 30s | pytest benchmark |
| Timeline render (50 clips) | < 16ms/frame | Performance API |
| Export 3-min 1080p60 | < 5 min | pytest benchmark |

Performance regression tests added at Milestone 8.

---

## 11. Test Ownership

| Area | Owner | Test Location |
|------|-------|---------------|
| Timeline Engine | Frontend | `apps/desktop/src/modules/timeline-engine/` |
| UI Components | Frontend | `apps/desktop/src/components/` |
| API Routes | Backend | `apps/backend/tests/integration/` |
| Services | Backend | `apps/backend/tests/unit/` |
| AI Agents | AI | `ai/agents/tests/` or `apps/backend/tests/unit/` |
| Render Pipeline | Backend | `apps/backend/tests/integration/` |
| E2E Workflows | Full stack | `tests/e2e/` |
