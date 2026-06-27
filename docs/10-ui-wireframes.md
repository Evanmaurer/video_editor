# UI Wireframes

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

All wireframes use ASCII art for version control compatibility. High-fidelity mockups will be created in Figma during Milestone 1.

---

## 1. Application Shell — Editor View

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ MontageAI          File  Edit  View  Timeline  AI  Render  Help            │
├─────────────────────────────────────────────────────────────────────────────┤
│ [Import] [Generate Timeline] [Analyze All] │ ▶ ■ │ [Export] [Render Queue]│
├──────────────────┬──────────────────────────────────────┬───────────────────┤
│                  │                                      │                   │
│  MEDIA LIBRARY   │         PREVIEW WINDOW               │    INSPECTOR      │
│                  │                                      │                   │
│  [Grid] [List]   │    ┌────────────────────────────┐    │  Clip: Bomb_03    │
│  [Filter ▼]      │    │                            │    │  ─────────────    │
│  [Sort: Score ▼] │    │                            │    │  Duration: 8.2s   │
│                  │    │      (video preview)       │    │  Score: 9.8       │
│  ┌────┐ ┌────┐  │    │                            │    │  Confidence: 96%  │
│  │thumb│ │thumb│  │    │                            │    │  Speed: 1.0x      │
│  │9.8 │ │7.2 │  │    └────────────────────────────┘    │  ─────────────    │
│  │💣  │ │⚔  │  │    00:00:45:12 / 03:00:00            │  Effects          │
│  └────┘ └────┘  │    [◀◀] [▶] [■] [▶▶] [🔊 ──●──]     │  [+ Add Effect]   │
│  ┌────┐ ┌────┐  │                                      │  ─────────────    │
│  │thumb│ │thumb│  │                                      │  Transition Out   │
│  │6.1 │ │8.5 │  │                                      │  Type: [Fade ▼]   │
│  │    │ │💣  │  │                                      │  Duration: 0.3s   │
│  └────┘ └────┘  │                                      │                   │
│  ...             │                                      │                   │
│                  ├──────────────────────────────────────┤                   │
│  Clips: 247       │                                      │ AI SUGGESTIONS    │
│  Analyzed: 231   │                                      │                   │
│  Bombs: 34       │                                      │ ┌───────────────┐ │
│                  │                                      │ │ Bomb Score 9.8│ │
│                  │                                      │ │ Conf: 96%     │ │
│                  │                                      │ │ Reason: ...   │ │
│                  │                                      │ │ [Acc][Rej]    │ │
│                  │                                      │ └───────────────┘ │
│                  │                                      │ ┌───────────────┐ │
│                  │                                      │ │ Sync to drop  │ │
│                  │                                      │ │ Conf: 88%     │ │
│                  │                                      │ │ [Acc][Rej]    │ │
│                  │                                      │ └───────────────┘ │
├──────────────────┴──────────────────────────────────────┴───────────────────┤
│                              TIMELINE                                        │
│  00:00    00:15    00:30    00:45    01:00    01:15    01:30    01:45      │
│  ├────────┼────────┼────────┼────────┼────────┼────────┼────────┼────────┤   │
│  V1 │███│████│ ██ │  ████████  │██│    │████│  │███│                        │
│  ♪  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│   │
│  GA │▓▓▓│▓▓▓▓│ ▓▓ │  ▓▓▓▓▓▓▓▓  │▓▓│    │▓▓▓▓│  │▓▓▓│                        │
│  ▼ drop markers (red triangles on ruler)                                     │
│  ♪ beat markers (small ticks on ruler)                                     │
│  ▲ playhead (blue vertical line at 00:45)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Ready │ Project: ZvZ_Montage_June │ 247 clips │ 3:00 │ [AI Chat 💬]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Panel sizing (default):**
- Media Library: 280px width
- Right column (Inspector + Suggestions): 320px width
- Preview: remaining width, 55% of center column height
- Timeline: remaining width, 45% of center column height

---

## 2. Welcome Screen

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                         ⚡ MontageAI                                        │
│                    AI-Powered Montage Editor                                │
│                                                                             │
│              ┌─────────────────┐    ┌─────────────────┐                    │
│              │                 │    │                 │                    │
│              │  + New Project  │    │  Open Project   │                    │
│              │                 │    │                 │                    │
│              └─────────────────┘    └─────────────────┘                    │
│                                                                             │
│              Recent Projects:                                               │
│              ┌─────────────────────────────────────────────────────┐       │
│              │ ZvZ_Montage_June        Updated 2 hours ago        │       │
│              │ Gank_Highlights_May     Updated 3 days ago         │       │
│              │ Arena_Compilation       Updated 1 week ago         │       │
│              └─────────────────────────────────────────────────────┘       │
│                                                                             │
│              Supported Game: Albion Online                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. New Project Wizard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  New Project                                                          [×]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Step 1 of 3: Project Details                                              │
│                                                                             │
│  Project Name:  [ZvZ_Montage_June_______________]                          │
│                                                                             │
│  Location:      [/Users/creator/Videos/Montages ] [Browse]                 │
│                                                                             │
│  Game:          [Albion Online ▼]                                          │
│                                                                             │
│  Resolution:    [1920 × 1080 ▼]                                            │
│  Frame Rate:    [60 fps ▼]                                                 │
│                                                                             │
│                                          [Cancel]  [Next →]                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  New Project                                                          [×]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Step 2 of 3: Import Media                                                 │
│                                                                             │
│  Gameplay Clips:                                                            │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐       │
│  │  Drag & drop clips or folders here, or click to browse          │       │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘       │
│  247 clips selected (18.4 GB)                                              │
│                                                                             │
│  Music Track:                                                               │
│  [Choose file...]  track.mp3 (3:24)                                        │
│                                                                             │
│  Reference Montages (optional):                                             │
│  [Choose files...]  2 files selected                                       │
│                                                                             │
│                                     [← Back]  [Cancel]  [Next →]           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  New Project                                                          [×]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Step 3 of 3: Analysis & Generation                                      │
│                                                                             │
│  ☑ Analyze all clips on import                                             │
│  ☑ Detect Albion events (bombs, wipes, etc.)                               │
│  ☑ Analyze music (beats, drops, BPM)                                     │
│  ☑ Learn style from reference montages                                     │
│  ☐ Auto-generate timeline after analysis                                   │
│                                                                             │
│  Target Duration: [3:00___] (optional)                                     │
│                                                                             │
│                                     [← Back]  [Cancel]  [Create Project]   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. AI Suggestion Card (Detail)

```
┌─────────────────────────────────────────────┐
│ 💣 Bomb Score: 9.8                    [×]  │
│ Confidence: 96%                             │
│ ─────────────────────────────────────────── │
│ Reason:                                     │
│ Highest estimated kill density              │
│ synchronized with the music drop at 0:45.   │
│                                             │
│ Expected Improvement:                       │
│ +12% engagement score vs current cut        │
│ ─────────────────────────────────────────── │
│ Clip: ZvZ_Bomb_03.mp4                       │
│ Event: Bomb @ 0:04.2 (5 kills estimated)   │
│ ─────────────────────────────────────────── │
│ [Preview Change]  [Accept ✓]  [Reject ✗]   │
└─────────────────────────────────────────────┘
```

---

## 5. AI Chat Panel

```
┌─────────────────────────────────────────────┐
│ AI Chat Assistant                     [─][×]│
├─────────────────────────────────────────────┤
│                                             │
│  You: Replace the clip at 0:45 with a       │
│       better bomb                             │
│                                             │
│  AI: Replaced clip at 0:45 with              │
│      ZvZ_Bomb_03.mp4 (Bomb Score: 9.8,     │
│      96% confidence). The new clip has 5    │
│      estimated kills synced to the drop.     │
│      [Undo this change]                      │
│                                             │
│  You: Make the intro faster                  │
│                                             │
│  AI: Reduced intro segment (0:00-0:15)       │
│      from 15s to 8s by trimming clip       │
│      durations and removing downtime.        │
│      [Undo this change]                      │
│                                             │
├─────────────────────────────────────────────┤
│ [Type a command...                    ] [→] │
│                                             │
│ Suggestions:                                │
│ [Add more bombs] [Sync to drops] [Shorten]  │
└─────────────────────────────────────────────┘
```

---

## 6. Render Queue Panel

```
┌─────────────────────────────────────────────┐
│ Render Queue                          [─][×]│
├─────────────────────────────────────────────┤
│                                             │
│ ▶ Montage_v1.mp4                            │
│   Preset: h264_1080p60                      │
│   Duration: 3:00                            │
│   ████████████░░░░░░░░  67%                 │
│   ETA: 1:42 remaining                       │
│   [Cancel]                                  │
│                                             │
│ ─────────────────────────────────────────── │
│                                             │
│ ✓ Montage_draft.mp4                         │
│   Preset: h264_1080p60 · 245 MB             │
│   Completed in 4:12                         │
│   [Reveal in Finder]  [Play]                │
│                                             │
│ ─────────────────────────────────────────── │
│                                             │
│ ○ Montage_4k.mp4                            │
│   Preset: h265_4k30 · Queued                │
│                                             │
├─────────────────────────────────────────────┤
│ [+ Add to Queue]                            │
│ Preset: [h264_1080p60 ▼]                   │
│ Output: [/Users/.../exports/] [Browse]      │
└─────────────────────────────────────────────┘
```

---

## 7. Analysis Progress Overlay

```
┌─────────────────────────────────────────────┐
│                                             │
│         Analyzing Clips...                  │
│                                             │
│         ████████████░░░░░░  78%             │
│         182 / 234 clips analyzed            │
│                                             │
│         Current: ZvZ_Fight_47.mp4           │
│         Detecting Albion events...          │
│                                             │
│         Bombs found: 34                     │
│         Wipes found: 8                      │
│         Avg excitement: 6.2                 │
│                                             │
│         [Run in Background]  [Cancel]       │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 8. Clip Detail View (Media Library expanded)

```
┌─────────────────────────────────────────────┐
│ ZvZ_Bomb_03.mp4                       [×]  │
├─────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────┐ │
│ │           (thumbnail preview)           │ │
│ └─────────────────────────────────────────┘ │
│ Duration: 0:12.4 │ 1920×1080 │ 60fps      │
│                                             │
│ Scores:                                     │
│   Excitement: ████████░░ 8.2               │
│   Motion:     ███████░░░ 7.1               │
│   Bomb:       █████████░ 9.8               │
│   Rank:       █████████░ 9.5               │
│                                             │
│ Events:                                     │
│   💣 Bomb @ 0:04.2 (conf: 96%, 5 kills)    │
│   ⚔ Engagement @ 0:00.1 - 0:12.4          │
│                                             │
│ AI Reasoning:                               │
│ "Highest kill density in batch. Bomb       │
│  synchronized with multi-kill feed burst."  │
│                                             │
│ [Add to Timeline]  [Set In/Out Points]      │
└─────────────────────────────────────────────┘
```

---

## 9. Settings Panel

```
┌─────────────────────────────────────────────┐
│ Settings                              [×]  │
├──────────┬──────────────────────────────────┤
│ General  │                                  │
│ Analysis │  General Settings                │
│ AI       │                                  │
│ Export   │  Default Project Location:       │
│ Advanced │  [/Users/creator/Videos] [Browse]│
│          │                                  │
│          │  Auto-save interval: [60s ▼]    │
│          │  Theme: [Dark ▼]                │
│          │                                  │
│          │  Backend:                        │
│          │  Status: ● Running (port 48291)  │
│          │  GPU: ● Available (M2 Pro)       │
│          │  Workers: [2 ▼]               │
│          │                                  │
│          │  AI Models:                      │
│          │  CLIP: ✓ Loaded                  │
│          │  Whisper: ✓ Loaded               │
│          │  EasyOCR: ✓ Loaded               │
│          │  LLM: ○ Not configured           │
│          │  [Configure AI Models...]        │
│          │                                  │
│          │              [Save]  [Cancel]   │
└──────────┴──────────────────────────────────┘
```

---

## 10. Responsive Behavior

| Breakpoint | Behavior |
|------------|----------|
| ≥ 1400px | All panels visible (default layout) |
| 1200-1399px | AI Chat docked as tab in right column |
| 1000-1199px | Media library collapsible; suggestions as tab |
| < 1000px | Not supported (minimum window: 1280×720) |

**Minimum window size:** 1280 × 720
