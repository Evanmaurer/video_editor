# Albion Online UI Templates

Data-driven template system for OCR regions and event detection. **Do not hardcode a single UI layout.**

## Design

- Templates are YAML files loaded at runtime
- Multiple presets ship for common resolutions and UI scales
- Users can calibrate via wizard (Milestone 3+)
- New templates can be added without modifying core application code

## Presets (planned)

| Preset ID | Resolution | UI Scale |
|-----------|------------|----------|
| `albion_1080p_default` | 1920×1080 | 100% |
| `albion_1440p_default` | 2560×1440 | 100% |
| `albion_1080p_125` | 1920×1080 | 125% |
| `albion_1080p_150` | 1920×1080 | 150% |

## Template Schema (excerpt)

```yaml
id: albion_1080p_default
game_id: albion
resolution: [1920, 1080]
ui_scale: 1.0
regions:
  kill_feed:
    x: 0.78
    y: 0.05
    width: 0.20
    height: 0.40
thresholds:
  bomb_min_kills: 3
  wipe_min_deaths: 5
```

Implementation begins in Milestone 3.
