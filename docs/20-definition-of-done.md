# Definition of Done

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Feature Definition of Done

A feature is **done** when ALL of the following are true:

### Code Quality
- [ ] Implementation complete — no stubs, TODOs, or placeholder code
- [ ] Follows [coding standards](./18-coding-standards.md)
- [ ] TypeScript strict mode passes (no `any`, no type errors)
- [ ] Python type hints on all public functions; mypy passes
- [ ] Linting passes (ESLint + Ruff)
- [ ] No console.log / print statements (use structured logging)
- [ ] Error handling in place — no unhandled exceptions in normal flow

### Testing
- [ ] Unit tests written and passing (≥ 80% coverage of new code)
- [ ] Integration tests for API endpoints and service interactions
- [ ] AI agents tested against validation dataset with metrics meeting targets
- [ ] Manual testing checklist items verified
- [ ] No regressions in existing test suite

### AI Features (Additional)
- [ ] Every AI output includes `confidence` (0-1) and `reasoning` (string)
- [ ] AI suggestions include `expected_improvement` where applicable
- [ ] Low-confidence results returned gracefully (not thrown/discarded)
- [ ] AI-generated timeline elements are fully editable
- [ ] AI edits are undoable

### Documentation
- [ ] Public APIs documented (docstrings / JSDoc)
- [ ] API changes reflected in [12-api-design.md](./12-api-design.md)
- [ ] Architecture changes reflected in relevant design docs
- [ ] PROJECT_STATE.md updated

### Review
- [ ] Code reviewed and approved
- [ ] CI pipeline green

---

## 2. Milestone Definition of Done

A milestone is **done** when ALL of the following are true:

- [ ] All P0 features for the milestone meet Feature Definition of Done
- [ ] All milestone exit criteria (from [16-milestone-breakdown.md](./16-milestone-breakdown.md)) met
- [ ] Working application demonstrated (not partially implemented)
- [ ] E2E test(s) for milestone's primary workflow passing
- [ ] No P0 bugs open for milestone scope
- [ ] Performance targets met (where applicable)
- [ ] PROJECT_STATE.md updated with completed work, known bugs, next priorities
- [ ] Stakeholder approval to proceed to next milestone

---

## 3. Release Definition of Done (v1.0)

The v1.0 release is **done** when:

### Functionality
- [ ] All P0 and P1 features from [01-prd.md](./01-prd.md) complete
- [ ] Full workflow works: import → analyze → generate timeline → edit → chat → export
- [ ] Albion bomb detection ≥ 80% precision on validation set
- [ ] Music BPM detection ±2 BPM on 90% of test tracks
- [ ] AI timeline acceptance rate ≥ 60% in beta testing

### Quality
- [ ] Zero P0 bugs open
- [ ] ≤ 5 P1 bugs open (with workaround documented)
- [ ] Crash-free rate ≥ 99.5% in beta
- [ ] All E2E tests passing
- [ ] Performance benchmarks met

### Platform
- [ ] macOS installer built and tested (13 Ventura+)
- [ ] Windows installer built and tested (10/11)
- [ ] AI models download successfully on first run
- [ ] App cold start < 5s

### Documentation
- [ ] User guide covering primary workflows
- [ ] All design docs reflect shipped architecture
- [ ] PROJECT_STATE.md reflects v1.0 release state

### Release
- [ ] Beta feedback collected from ≥ 5 creators
- [ ] Beta NPS ≥ 30
- [ ] v1.0 tagged in git
- [ ] Release notes published

---

## 4. What Is NOT Done

These explicitly do **not** meet Definition of Done:

| Anti-pattern | Why |
|-------------|-----|
| Feature with `// TODO: implement` | Placeholder code |
| UI that renders but doesn't connect to backend | Partially implemented |
| AI agent that returns hardcoded scores | Not real analysis |
| Test that asserts `expect(true).toBe(true)` | Trivial test |
| Feature without error handling | Incomplete |
| AI output without confidence/reasoning | Violates core principle |
| Timeline changes that aren't undoable | Violates core principle |
| Code merged with failing CI | Broken build |

---

## 5. Bug Severity Classification

| Severity | Definition | Blocks Release? |
|----------|------------|-----------------|
| P0 — Critical | App crash, data loss, export failure, AI completely broken | Yes |
| P1 — Major | Feature unusable but workaround exists; incorrect AI results | No (limit 5) |
| P2 — Minor | UI glitch, slow performance, cosmetic issue | No |
| P3 — Trivial | Typo, minor alignment, nice-to-have | No |

---

## 6. Acceptance Criteria Template

Use this template for each feature task:

```markdown
## Feature: [Name]

### Acceptance Criteria
- [ ] [Specific, testable criterion 1]
- [ ] [Specific, testable criterion 2]
- [ ] [Specific, testable criterion 3]

### Test Evidence
- Unit: [test file path]
- Integration: [test file path]
- Manual: [what was verified]

### AI Transparency (if applicable)
- [ ] Confidence score displayed
- [ ] Reasoning text displayed
- [ ] Expected improvement shown (if suggestion)
- [ ] User can accept/reject/undo
```

---

## 7. Review Checklist (For Reviewers)

- [ ] Does the code match the design doc?
- [ ] Are there any placeholder implementations?
- [ ] Is error handling adequate?
- [ ] Are tests meaningful (not trivial)?
- [ ] Does AI output include confidence + reasoning?
- [ ] Is the feature editable and undoable?
- [ ] Is PROJECT_STATE.md updated?
- [ ] Would I trust this in a demo to a creator?
