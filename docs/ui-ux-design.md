# UI/UX Design

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Design Philosophy

MontageAI's interface follows professional NLE conventions (Premiere Pro, DaVinci Resolve) while surfacing AI capabilities prominently. The design prioritizes:

1. **Familiarity** — Editors should feel at home immediately.
2. **AI visibility** — AI suggestions and reasoning are always accessible, never hidden.
3. **Density** — Professional tools show information densely; avoid excessive whitespace.
4. **Dark theme** — Standard for video editing; reduces eye strain during long sessions.

---

## 2. Design System

### 2.1 Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `bg-primary` | `#1a1a1a` | Main background |
| `bg-secondary` | `#252525` | Panel backgrounds |
| `bg-panel` | `#2d2d2d` | Elevated panels, cards |
| `bg-hover` | `#353535` | Hover states |
| `bg-active` | `#404040` | Active/selected states |
| `accent` | `#6c5ce7` | Primary actions, playhead, links |
| `accent-hover` | `#7d6ff0` | Accent hover |
| `accent-muted` | `#6c5ce720` | Accent backgrounds |
| `text-primary` | `#e8e8e8` | Primary text |
| `text-secondary` | `#999999` | Secondary text, labels |
| `text-muted` | `#666666` | Disabled, timestamps |
| `border` | `#3d3d3d` | Panel borders, dividers |
| `border-focus` | `#6c5ce7` | Focus rings |
| `success` | `#2ecc71` | Success states, high scores |
| `warning` | `#f39c12` | Warnings, medium confidence |
| `danger` | `#e74c3c` | Errors, delete, low confidence |
| `info` | `#3498db` | Informational |

### 2.2 Track Colors

| Track Type | Color | Hex |
|------------|-------|-----|
| Video | Blue | `#4a90d9` |
| Music | Purple | `#9b59b6` |
| Game Audio | Green | `#4caf50` |
| Voice/Discord | Orange | `#e67e22` |
| Effects/Overlay | Yellow | `#f1c40f` |
| Subtitles | Gray | `#95a5a6` |

### 2.3 Event Badge Colors

| Event | Icon | Color |
|-------|------|-------|
| Bomb | 💣 | `#e74c3c` (red) |
| Engagement | ⚔ | `#e67e22` (orange) |
| Wipe | 💀 | `#8e44ad` (purple) |
| Loot | ✨ | `#f1c40f` (gold) |
| Kill Feed | 🎯 | `#3498db` (blue) |

### 2.4 Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| Body | Inter | 13px | 400 |
| Small/Labels | Inter | 11px | 400 |
| Headings | Inter | 15px | 600 |
| Monospace (timecode) | JetBrains Mono | 12px | 400 |
| Scores | Inter | 14px | 700 |

### 2.5 Spacing

Base unit: 4px. Common values: 4, 8, 12, 16, 24, 32.

### 2.6 Border Radius

| Element | Radius |
|---------|--------|
| Buttons | 6px |
| Cards | 8px |
| Panels | 0 (sharp edges for professional feel) |
| Modals | 12px |
| Thumbnails | 4px |

---

## 3. Layout Specifications

### 3.1 Window

- Minimum size: 1280 × 720
- Default size: 1600 × 900
- Panels resizable via drag handles
- Panel sizes persisted in localStorage

### 3.2 Panel Default Sizes

| Panel | Default Size |
|-------|-------------|
| Media Library | 280px width |
| Inspector + Suggestions | 320px width |
| Preview | 55% of center height |
| Timeline | 45% of center height |
| Toolbar | 40px height |
| Menu Bar | 28px (native) |
| Status Bar | 24px height |

### 3.3 Dockable Panels

Chat Panel and Render Queue can be:
- Docked as tabs in right column
- Floating as overlay windows
- Minimized to status bar icons

---

## 4. Interaction Patterns

### 4.1 Media Library

- **Click** clip → select, show in inspector
- **Double-click** → add to timeline at playhead
- **Drag** → drop onto timeline track
- **Right-click** → context menu (analyze, delete, reveal in finder)
- **Hover** clip → preview tooltip with score overlay

### 4.2 Timeline

- **Click** ruler → seek playhead
- **Drag** clip → move along track
- **Drag** clip edge → trim
- **Drag** clip to another track → move track
- **Double-click** clip → open in inspector
- **Scroll** wheel → zoom timeline
- **Cmd+Scroll** → horizontal scroll
- **Right-click** clip → context menu (split, delete, speed, effects)
- **Snap indicator** — vertical line when clip aligns to beat/marker/clip edge

### 4.3 AI Suggestions

- Suggestions appear in panel sorted by confidence (highest first)
- **Preview** → temporarily apply to timeline (revert on cancel)
- **Accept** → permanently apply (undoable)
- **Reject** → dismiss; logged for future model improvement
- Badge count on panel tab when new suggestions arrive

### 4.4 AI Chat

- Dockable panel; default bottom-right
- Message history scrollable
- Quick-action chips for common commands
- Each AI response with undo link
- Typing indicator while processing

---

## 5. Score Visualization

### 5.1 Score Bars

Horizontal bars with color gradient:
- 0-3: Red (`#e74c3c`)
- 3-6: Orange (`#f39c12`)
- 6-8: Yellow-green (`#8bc34a`)
- 8-10: Green (`#2ecc71`)

### 5.2 Confidence Display

| Range | Label | Color |
|-------|-------|-------|
| 90-100% | High | Green |
| 70-89% | Medium | Yellow |
| 50-69% | Low | Orange |
| < 50% | Very Low | Red |

---

## 6. Animation & Transitions

| Interaction | Animation | Duration |
|-------------|-----------|----------|
| Panel resize | Smooth | 150ms |
| Suggestion accept | Clip highlight flash | 300ms |
| Toast notification | Slide in from top-right | 200ms |
| Progress bar | Smooth width transition | 100ms |
| Modal open/close | Fade + scale | 200ms |
| Playhead seek | Instant (no animation) |

Keep animations subtle — this is a professional tool, not a consumer app.

---

## 7. Empty States

Each panel shows helpful empty state when no content:

| Panel | Empty State Message | Action |
|-------|-------------------|--------|
| Media Library | "Import gameplay clips to get started" | [Import Clips] button |
| Timeline | "Drag clips here or generate an AI timeline" | [Generate Timeline] button |
| Preview | "Select a clip or press play" | — |
| Suggestions | "AI suggestions will appear after timeline generation" | — |
| Chat | "Ask me to edit your timeline" + example commands | — |
| Render Queue | "No render jobs" | [Export] button |

---

## 8. Accessibility

- Keyboard navigation for all primary actions
- Focus indicators on interactive elements
- ARIA labels on icon-only buttons
- Color not sole indicator (icons + text accompany colors)
- Minimum contrast ratio 4.5:1 (WCAG AA)
- Screen reader support for AI suggestions (confidence + reasoning read aloud)

---

## 9. Responsive Behavior

See [10-ui-wireframes.md](./10-ui-wireframes.md) section 10.

At minimum supported width (1280px):
- Media library remains visible (not collapsed)
- Chat panel docks as tab
- Timeline track height reduces to 48px per track

---

## 10. Iconography

Use Lucide React icons (consistent, MIT licensed):

| Action | Icon |
|--------|------|
| Import | `Upload` |
| Export | `Download` |
| Play | `Play` |
| Pause | `Pause` |
| Generate Timeline | `Wand2` |
| AI Chat | `MessageSquare` |
| Settings | `Settings` |
| Bomb event | `Bomb` (custom or `Zap`) |
| Analyze | `Scan` |
| Undo/Redo | `Undo2` / `Redo2` |

---

## 11. Figma / High-Fidelity Mockups

High-fidelity mockups will be created in Figma during Milestone 1 for:
- Editor view (full layout)
- Welcome screen
- New project wizard
- AI suggestion card
- Chat panel
- Render queue

Wireframes in [10-ui-wireframes.md](./10-ui-wireframes.md) serve as the layout reference until Figma mockups are complete.
