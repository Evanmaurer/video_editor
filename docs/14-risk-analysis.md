# Risk Analysis

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## Risk Matrix

| ID | Risk | Probability | Impact | Score | Mitigation |
|----|------|-------------|--------|-------|------------|
| R-01 | Albion event detection accuracy too low | High | High | Critical | Heuristic v1 + validation set; iterate with community feedback |
| R-02 | AI timeline quality disappoints creators | Medium | High | High | Transparent suggestions; easy reject/undo; manual override always available |
| R-03 | Performance with 500+ clips | Medium | High | High | Proxy media; virtualized UI; paginated queries; background processing |
| R-04 | FFmpeg render failures | Medium | Medium | Medium | Pre-render validation; detailed error logs; retry mechanism |
| R-05 | Python backend crash | Medium | Medium | Medium | Health monitoring; auto-restart; graceful UI degradation |
| R-06 | Large app bundle size | High | Medium | Medium | Models downloaded on demand; PyInstaller optimization; optional components |
| R-07 | GPU compatibility issues | Medium | Medium | Medium | CPU fallback for all agents; detect GPU at startup |
| R-08 | LLM NL editing unreliable | Medium | Medium | Medium | Rule-based parser for common commands; LLM as enhancement |
| R-09 | Albion UI changes break OCR | Medium | High | High | Configurable UI templates; community template updates |
| R-10 | Scope creep | High | High | Critical | Strict milestone gates; definition of done; defer P2 features |
| R-11 | Electron security vulnerabilities | Low | High | Medium | Context isolation; no nodeIntegration; regular Electron updates |
| R-12 | Cross-platform packaging issues | Medium | Medium | Medium | CI builds for macOS + Windows; test on both platforms each milestone |
| R-13 | Music sync accuracy | Medium | Medium | Medium | Manual beat adjustment UI; snap toggle; visual beat markers |
| R-14 | Data loss on crash | Low | High | Medium | Auto-save every 60s; WAL mode SQLite; timeline JSON on disk |
| R-15 | Model licensing restrictions | Low | Medium | Low | Use open-source models only (CLIP, Whisper, Llama); verify licenses |

---

## Detailed Risk Analysis

### R-01: Albion Event Detection Accuracy (Critical)

**Description:** The Albion analyzer may fail to detect bombs, wipes, and other events reliably due to UI variations, different resolutions, and overlay mods.

**Impact:** Core value proposition fails if creators can't trust auto-detection.

**Mitigation Strategy:**
1. v1 uses heuristic + OCR approach (not ML-dependent) for faster iteration
2. Build validation set of 30+ labeled Albion clips early in Milestone 3
3. Configurable UI region templates (`config.yaml`) for different HUD layouts
4. Show confidence scores — low confidence events still visible for manual review
5. Community feedback loop for template updates
6. Future: fine-tuned detector model on Albion screenshots

**Contingency:** If accuracy < 60% at Milestone 3 gate, extend Milestone 3 by 2 weeks for detector iteration before proceeding.

---

### R-02: AI Timeline Quality (High)

**Description:** Auto-generated timelines may not meet creator quality expectations, leading to distrust of AI features.

**Impact:** Users abandon AI features and use app as manual editor only.

**Mitigation Strategy:**
1. Every placement includes reasoning and confidence — user understands why
2. One-click accept/reject for every suggestion
3. Full undo/redo — AI edits are never destructive
4. Style profile from reference montages aligns output to user expectations
5. Iterative improvement: collect accept/reject data for future model training

**Contingency:** If acceptance rate < 40% in beta, prioritize Timeline Planner algorithm iteration over new features.

---

### R-03: Performance with 500+ Clips (High)

**Description:** Importing and analyzing hundreds of clips may cause UI freezes, excessive memory usage, or multi-hour analysis times.

**Impact:** App feels unusable for target use case (200+ clips per project).

**Mitigation Strategy:**
1. All analysis runs in background job queue — UI never blocks
2. Proxy media (720p30) for analysis — 4x faster than full-res
3. Virtualized media library grid (react-window)
4. Paginated API queries (50 items per page)
5. Configurable worker count (default 2)
6. Progress UI with "run in background" option

**Performance targets:**
- Import 100 clips: < 60s (metadata only)
- Analyze 100 clips (GPU): < 50 min
- Analyze 100 clips (CPU): < 100 min

**Contingency:** If analysis exceeds 2x targets, prioritize GPU optimization and frame sampling rate reduction.

---

### R-04: FFmpeg Render Failures (Medium)

**Description:** Complex filter graphs may fail due to codec incompatibilities, path issues, or resource limits.

**Mitigation Strategy:**
1. Pre-render validation checks all source files exist
2. Full stderr capture saved to log file
3. Simplified fallback graph (no effects) if complex graph fails
4. Test render pipeline with diverse clip combinations each milestone
5. Hardware encoder fallback to software encoder

---

### R-05: Python Backend Crash (Medium)

**Description:** Python backend may crash due to OOM during ML inference, FFmpeg errors, or unhandled exceptions.

**Mitigation Strategy:**
1. Electron main process monitors backend health
2. Auto-restart on crash (max 3 attempts)
3. UI shows "Backend disconnected" overlay with retry button
4. GPU inference serialized to one job at a time (prevent OOM)
5. Structured error handling — agents never throw for low confidence

---

### R-06: Large App Bundle Size (Medium)

**Description:** Electron + Python + ML models could exceed 2GB installed size.

**Mitigation Strategy:**
1. Core app bundle: Electron + Python + FFmpeg (~300MB)
2. AI models downloaded on first run (~1.5GB total):
   - CLIP ViT-B/32 ONNX: ~350MB
   - Whisper base: ~150MB
   - EasyOCR: ~100MB
   - Local LLM (optional): ~2GB
3. Model download UI with progress and skip options
4. Models cached in app data directory

---

### R-09: Albion UI Changes (High)

**Description:** Albion Online game updates may change HUD layout, breaking OCR region templates and event detection.

**Mitigation Strategy:**
1. UI templates externalized in YAML config (not hardcoded)
2. Template versioning with game patch notes
3. Community template sharing (future)
4. Graceful degradation: if OCR region yields no results, skip OCR-based detection and rely on motion/heuristic

---

### R-10: Scope Creep (Critical)

**Description:** Feature requests and AI capability expansion could delay core milestones indefinitely.

**Mitigation Strategy:**
1. Strict milestone gates with definition of done
2. P0/P1/P2 priority system — P2 features deferred post-v1
3. Every milestone produces a working application
4. No placeholder code — features are complete or not started
5. Weekly milestone review against task backlog

**Explicitly deferred:**
- Games beyond Albion
- Cloud rendering
- Real-time collaboration
- Mobile app
- Motion graphics / compositing

---

## Risk Monitoring

| Checkpoint | Review |
|------------|--------|
| Milestone 1 gate | Backend stability, app startup reliability |
| Milestone 3 gate | Albion detection accuracy on validation set |
| Milestone 5 gate | Timeline generation acceptance rate in internal testing |
| Milestone 7 gate | Beta creator feedback; NPS survey |
| Pre-release | Full E2E test suite pass; performance benchmarks |

---

## Assumptions

| # | Assumption | If Wrong |
|---|------------|----------|
| A-1 | Creators have 16GB+ RAM | Reduce concurrent workers; warn at 8GB |
| A-2 | Clips are 1080p H.264 MP4/MKV | Add transcoding on import for exotic codecs |
| A-3 | Albion HUD is consistent within a patch cycle | Template versioning per patch |
| A-4 | Creators accept 720p proxy preview | Offer full-res preview toggle (slower) |
| A-5 | Average project: 100-300 clips, 1-3 min montage | Optimize for this range first |
