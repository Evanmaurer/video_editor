import { describe, expect, it } from "vitest";
import type { TimelineClip, TimelineDocument } from "@montage/shared-types";
import {
  collectPlacedAlbionMarkers,
  mapSourceTimestampToTimeline,
} from "./albion-timeline-markers";

const clip: TimelineClip = {
  id: "clip-1",
  media_item_id: "media-1",
  track_id: "track-1",
  start_ms: 5000,
  end_ms: 15000,
  source_in_ms: 2000,
  source_out_ms: 12000,
  speed: 1,
  opacity: 1,
};

const document: TimelineDocument = {
  id: "timeline-1",
  project_id: "project-1",
  name: "Main",
  version: 1,
  settings: { width: 1920, height: 1080, frame_rate: 60, sample_rate: 48000 },
  duration_ms: 20000,
  tracks: [
    {
      id: "track-1",
      type: "video",
      name: "Video 1",
      index: 0,
      muted: false,
      locked: false,
      visible: true,
      volume: 1,
      clips: [clip],
    },
  ],
  markers: [],
  beat_markers: [],
  metadata: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("mapSourceTimestampToTimeline", () => {
  it("maps source timestamps inside the clip trim window", () => {
    expect(mapSourceTimestampToTimeline(clip, 4000)).toBe(7000);
  });

  it("returns null for timestamps outside the clip trim window", () => {
    expect(mapSourceTimestampToTimeline(clip, 1000)).toBeNull();
    expect(mapSourceTimestampToTimeline(clip, 13000)).toBeNull();
  });
});

describe("collectPlacedAlbionMarkers", () => {
  it("places markers on the timeline for matching media", () => {
    const annotations = new Map([
      [
        "media-1",
        {
          engine_version: "albion-annotation-v1.0",
          cache_key: "test",
          duration_ms: 15000,
          frame_rate: 60,
          summary: {
            marker_count: 1,
            recommendation_count: 0,
            highlight_score: null,
            primary_engagement: null,
            by_marker_type: { bomb: 1 },
            reused_albion_combat: false,
            reused_albion_bomb: true,
            reused_albion_engagement: false,
            reused_albion_ability: false,
            reused_albion_ocr: false,
            reused_albion_highlight: false,
          },
          markers: [
            {
              marker_id: "marker:bomb:4000:0",
              marker_type: "bomb",
              timestamp_ms: 4000,
              end_ms: null,
              seek_ms: 4000,
              label: "Bomb",
              color: "#e74c3c",
              confidence: 0.8,
              reasoning: "Bomb detected",
              search_text: "bomb",
              metadata: {},
            },
          ],
          recommendations: [],
        },
      ],
    ]);

    const placed = collectPlacedAlbionMarkers(document, annotations);
    expect(placed).toHaveLength(1);
    expect(placed[0]?.timeline_ms).toBe(7000);
    expect(placed[0]?.marker_type).toBe("bomb");
  });
});
