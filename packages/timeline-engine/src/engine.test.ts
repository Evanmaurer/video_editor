import { describe, expect, it } from "vitest";
import type { TimelineDocument } from "@montage/shared-types";
import {
  AddClipCommand,
  MoveClipCommand,
  RemoveClipCommand,
  RippleDeleteClipCommand,
  SplitClipCommand,
  TimelineEngine,
  TrimClipCommand,
  createEmptyTimelineDocument,
} from "./index";

function testDoc(): TimelineDocument {
  const doc = createEmptyTimelineDocument("project-1", {
    width: 1920,
    height: 1080,
    frame_rate: 60,
    sample_rate: 48000,
  });
  return doc;
}

describe("TimelineEngine", () => {
  it("adds and removes clips with undo/redo", () => {
    const engine = TimelineEngine.fromDocument(testDoc());
    const trackId = engine.getDocument().tracks[0]!.id;

    engine.execute(
      new AddClipCommand({
        media_item_id: "media-1",
        track_id: trackId,
        start_ms: 1000,
        source_out_ms: 4000,
        clip_id: "clip-1",
      }),
    );

    expect(engine.getClip("clip-1")).toBeDefined();
    expect(engine.canUndo()).toBe(true);

    engine.undo();
    expect(engine.getClip("clip-1")).toBeUndefined();

    engine.redo();
    expect(engine.getClip("clip-1")).toBeDefined();
  });

  it("moves clips without overlap", () => {
    const engine = TimelineEngine.fromDocument(testDoc());
    const trackId = engine.getDocument().tracks[0]!.id;

    engine.execute(
      new AddClipCommand({
        media_item_id: "media-1",
        track_id: trackId,
        start_ms: 0,
        source_out_ms: 2000,
        clip_id: "clip-a",
      }),
    );
    engine.execute(
      new AddClipCommand({
        media_item_id: "media-2",
        track_id: trackId,
        start_ms: 3000,
        source_out_ms: 2000,
        clip_id: "clip-b",
      }),
    );

    engine.execute(new MoveClipCommand("clip-a", 5000));
    expect(engine.getClip("clip-a")?.start_ms).toBe(5000);
  });

  it("splits a clip at the playhead", () => {
    const engine = TimelineEngine.fromDocument(testDoc());
    const trackId = engine.getDocument().tracks[0]!.id;

    engine.execute(
      new AddClipCommand({
        media_item_id: "media-1",
        track_id: trackId,
        start_ms: 0,
        source_out_ms: 4000,
        clip_id: "clip-1",
      }),
    );

    const cmd = new SplitClipCommand("clip-1", 2000);
    engine.execute(cmd);

    const doc = engine.getDocument();
    const clips = doc.tracks[0]!.clips;
    expect(clips).toHaveLength(2);
    expect(clips[0]!.end_ms).toBe(2000);
    expect(clips[1]!.start_ms).toBe(2000);
  });

  it("trims clip end with ripple", () => {
    const engine = TimelineEngine.fromDocument(testDoc());
    const trackId = engine.getDocument().tracks[0]!.id;

    engine.execute(
      new AddClipCommand({
        media_item_id: "media-1",
        track_id: trackId,
        start_ms: 0,
        source_out_ms: 2000,
        clip_id: "clip-a",
      }),
    );
    engine.execute(
      new AddClipCommand({
        media_item_id: "media-2",
        track_id: trackId,
        start_ms: 2000,
        source_out_ms: 2000,
        clip_id: "clip-b",
      }),
    );

    engine.execute(
      new TrimClipCommand({
        clipId: "clip-a",
        end_ms: 1500,
        ripple: true,
      }),
    );

    expect(engine.getClip("clip-b")?.start_ms).toBe(1500);
  });

  it("ripple delete closes gap", () => {
    const engine = TimelineEngine.fromDocument(testDoc());
    const trackId = engine.getDocument().tracks[0]!.id;

    engine.execute(
      new AddClipCommand({
        media_item_id: "media-1",
        track_id: trackId,
        start_ms: 0,
        source_out_ms: 2000,
        clip_id: "clip-a",
      }),
    );
    engine.execute(
      new AddClipCommand({
        media_item_id: "media-2",
        track_id: trackId,
        start_ms: 2000,
        source_out_ms: 2000,
        clip_id: "clip-b",
      }),
    );

    engine.execute(new RippleDeleteClipCommand("clip-a"));
    expect(engine.getClip("clip-a")).toBeUndefined();
    expect(engine.getClip("clip-b")?.start_ms).toBe(0);
  });

  it("rejects overlapping adds", () => {
    const engine = TimelineEngine.fromDocument(testDoc());
    const trackId = engine.getDocument().tracks[0]!.id;

    engine.execute(
      new AddClipCommand({
        media_item_id: "media-1",
        track_id: trackId,
        start_ms: 0,
        source_out_ms: 3000,
        clip_id: "clip-a",
      }),
    );

    const before = engine.getDocument();
    engine.execute(
      new AddClipCommand({
        media_item_id: "media-2",
        track_id: trackId,
        start_ms: 1000,
        source_out_ms: 2000,
        clip_id: "clip-b",
      }),
    );
    expect(engine.getDocument().tracks[0]!.clips).toHaveLength(1);
    expect(engine.getDocument()).toEqual(before);
  });

  it("remove clip command", () => {
    const engine = TimelineEngine.fromDocument(testDoc());
    const trackId = engine.getDocument().tracks[0]!.id;
    engine.execute(
      new AddClipCommand({
        media_item_id: "media-1",
        track_id: trackId,
        start_ms: 0,
        source_out_ms: 2000,
        clip_id: "clip-1",
      }),
    );
    engine.execute(new RemoveClipCommand("clip-1"));
    expect(engine.getClip("clip-1")).toBeUndefined();
  });
});
