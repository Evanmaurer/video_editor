import { describe, expect, it } from "vitest";
import type { TimelineDocument } from "@montage/shared-types";
import {
  findNextVideoClip,
  resolveVideoFrameAtTime,
  snapToFrameMs,
  timelineMsFromSource,
} from "../src/resolve";

function baseDocument(): TimelineDocument {
  return {
    id: "tl-1",
    project_id: "proj-1",
    name: "Test",
    version: 1,
    duration_ms: 10000,
    settings: {
      frame_rate: 60,
      width: 1920,
      height: 1080,
      sample_rate: 48000,
    },
    tracks: [
      {
        id: "track-v1",
        type: "video",
        index: 0,
        name: "V1",
        visible: true,
        locked: false,
        muted: false,
        volume: 1,
        clips: [
          {
            id: "clip-1",
            media_item_id: "media-1",
            track_id: "track-v1",
            start_ms: 0,
            end_ms: 5000,
            source_in_ms: 1000,
            source_out_ms: 6000,
            speed: 1,
            opacity: 1,
            name: "A",
          },
          {
            id: "clip-2",
            media_item_id: "media-2",
            track_id: "track-v1",
            start_ms: 5000,
            end_ms: 9000,
            source_in_ms: 0,
            source_out_ms: 4000,
            speed: 1,
            opacity: 1,
            name: "B",
          },
        ],
      },
      {
        id: "track-v2",
        type: "video",
        index: 1,
        name: "V2",
        visible: false,
        locked: false,
        muted: false,
        volume: 1,
        clips: [],
      },
    ],
    markers: [],
    beat_markers: [],
    metadata: {},
    created_at: "2026-06-27T00:00:00.000Z",
    updated_at: "2026-06-27T00:00:00.000Z",
  };
}

describe("snapToFrameMs", () => {
  it("snaps to nearest frame boundary", () => {
    expect(snapToFrameMs(8, 60)).toBe(0);
    expect(snapToFrameMs(20, 60)).toBeCloseTo(16.667, 2);
    expect(snapToFrameMs(0, 60)).toBe(0);
  });
});

describe("resolveVideoFrameAtTime", () => {
  it("resolves clip and source time", () => {
    const frame = resolveVideoFrameAtTime(baseDocument(), 2500);
    expect(frame?.clip.id).toBe("clip-1");
    expect(frame?.sourceMs).toBe(3500);
  });

  it("ignores hidden tracks", () => {
    const doc = structuredClone(baseDocument());
    doc.tracks[0]!.visible = false;
    doc.tracks[1]!.visible = true;
    doc.tracks[1]!.clips = [
      {
        id: "clip-hidden-track",
        media_item_id: "media-x",
        track_id: "track-v2",
        start_ms: 0,
        end_ms: 2000,
        source_in_ms: 0,
        source_out_ms: 2000,
        speed: 1,
        opacity: 1,
        name: "X",
      },
    ];
    const frame = resolveVideoFrameAtTime(doc, 500);
    expect(frame?.clip.id).toBe("clip-hidden-track");
  });
});

describe("findNextVideoClip", () => {
  it("finds the earliest clip after playhead", () => {
    const next = findNextVideoClip(baseDocument(), 1000);
    expect(next?.clip.id).toBe("clip-2");
  });
});

describe("timelineMsFromSource", () => {
  it("maps source time back to timeline ms", () => {
    const clip = baseDocument().tracks[0]!.clips[0]!;
    expect(timelineMsFromSource(clip, 3500)).toBe(2500);
  });
});
